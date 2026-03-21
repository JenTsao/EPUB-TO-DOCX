import os
import re
import tempfile
import shutil
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from bs4 import BeautifulSoup
from ebooklib import epub
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

try:
    import cupy as cp
    _CUPY_AVAILABLE = True
    _CUPY_CUDA_AVAILABLE = hasattr(cp, 'cuda') and hasattr(cp.cuda, 'is_available') and cp.cuda.is_available()
except ImportError:
    _CUPY_AVAILABLE = False
    _CUPY_CUDA_AVAILABLE = False

try:
    from numba import cuda
    NUMBA_CUDA_AVAILABLE = cuda.is_available()
except ImportError:
    NUMBA_CUDA_AVAILABLE = False

try:
    from lxml import etree
    _LXML_AVAILABLE = True
except ImportError:
    _LXML_AVAILABLE = False

_PARSER = 'lxml' if _LXML_AVAILABLE else 'html.parser'

_NEWLINE_COLLAPSE = re.compile(r'\n{3,}')
_WHITESPACE_COLLAPSE = re.compile(r'[ \t]+')
_LEADING_WHITESPACE = re.compile(r'^[ \t]+', re.MULTILINE)
_EMPTY_HEADING_TAG = re.compile(r'##\s*##')

def get_optimal_worker_count():
    return max(1, cpu_count() - 1)

def detect_gpu_acceleration():
    gpu_info = {
        'gpu_available': False,
        'gpu_name': None,
        'compute_units': None,
        'recommended': False
    }

    if _CUPY_AVAILABLE and _CUPY_CUDA_AVAILABLE:
        try:
            gpu_info['gpu_available'] = True
            device_count = cp.cuda.runtime.getDeviceCount()
            if device_count > 0:
                device = cp.cuda.Device(0)
                gpu_info['gpu_name'] = f'CUDA GPU (Device 0)'
                gpu_info['compute_units'] = device.compute_capability
                gpu_info['recommended'] = True
                return gpu_info
        except Exception as e:
            pass

    if NUMBA_CUDA_AVAILABLE:
        try:
            device = cuda.get_current_device()
            gpu_info['gpu_available'] = True
            gpu_info['gpu_name'] = f'CUDA Device {device.id}'
            gpu_info['compute_units'] = device.compute_capability
            gpu_info['recommended'] = True
            return gpu_info
        except Exception:
            pass

    return gpu_info

def _fast_clean_text(text):
    text = _NEWLINE_COLLAPSE.sub('\n\n', text)
    text = _EMPTY_HEADING_TAG.sub('', text)
    text = _WHITESPACE_COLLAPSE.sub(' ', text)
    text = _LEADING_WHITESPACE.sub('', text)
    return text.strip()

def process_chapter_html(html_content):
    soup = BeautifulSoup(html_content, _PARSER)

    for element in soup.find_all(['script', 'style', 'nav', 'head']):
        element.decompose()

    for tag in soup.find_all(True):
        if tag.name not in ['html', 'body']:
            tag.attrs = {}

    text_parts = []

    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        heading_text = heading.get_text(strip=True)
        if heading_text:
            text_parts.append(f'\n\n## {heading_text} ##\n\n')

    for p in soup.find_all(['p', 'div']):
        p_text = p.get_text(strip=True)
        if p_text:
            text_parts.append(f'\n\n{p_text}')

    for br in soup.find_all('br'):
        br.replace_with('\n')

    text = ''.join(text_parts)

    return _fast_clean_text(text)

def process_chapter_worker(args):
    chapter_data, include_images, temp_dir = args

    chapter_id = chapter_data['id']
    chapter_title = chapter_data['title']
    html_content = chapter_data['content']

    text = process_chapter_html(html_content)

    return {
        'id': chapter_id,
        'title': chapter_title,
        'text': text,
        'content': html_content if include_images else None
    }

def _batch_process_text_gpu(texts, batch_size=1000):
    if not _CUPY_AVAILABLE or not _CUPY_CUDA_AVAILABLE:
        return texts

    try:
        processed = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            lengths = cp.array([len(t) for t in batch])

            max_len = int(cp.max(lengths).item())
            padded = []
            for t in batch:
                arr = cp.array([ord(c) for c in t], dtype=cp.int32)
                if len(arr) < max_len:
                    arr = cp.pad(arr, (0, max_len - len(arr)), constant_values=0)
                padded.append(arr)

            matrix = cp.stack(padded)

            mask = (matrix != 0).astype(cp.int32)
            processed_batch = []
            for j in range(len(batch)):
                valid_chars = matrix[j][:int(lengths[j].item())]
                text = ''.join([chr(int(c)) for c in valid_chars.get()])
                processed_batch.append(text)

            processed.extend(processed_batch)

            del matrix, lengths, padded
            cp.cuda.Stream.null.synchronize()

        return processed
    except Exception:
        return texts

class EPUBConverter:
    def __init__(self, epub_path, output_path, progress_callback=None, log_callback=None):
        self.epub_path = epub_path
        self.output_path = output_path
        self.progress_callback = progress_callback
        self.log_callback = log_callback

        self.gpu_info = detect_gpu_acceleration()
        self.use_multiprocessing = True

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _report_progress(self, value, status):
        if self.progress_callback:
            self.progress_callback(value, status)

    def _extract_images_parallel(self, epub_book, temp_dir, max_workers=None):
        if max_workers is None:
            max_workers = min(8, cpu_count() * 2)

        images = {}
        image_items = []

        for item in epub_book.items:
            if item.get_type() == 9:
                image_items.append(item)

        def extract_single_image(item):
            try:
                image_data = item.get_content()
                image_filename = item.get_name()

                if not image_filename:
                    ext = self._detect_image_extension(image_data)
                    image_filename = f'image_{item.get_id()}{ext}'

                image_path = os.path.join(temp_dir, image_filename)

                with open(image_path, 'wb') as f:
                    f.write(image_data)

                return image_filename, image_path
            except Exception as e:
                return None, str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(extract_single_image, item): item for item in image_items}

            for future in as_completed(futures):
                try:
                    filename, result = future.result()
                    if filename:
                        images[filename] = result
                        self._log(f"提取图片：{filename}")
                except Exception as e:
                    self._log(f"提取图片失败：{str(e)}")

        return images

    def _detect_image_extension(self, data):
        if not data or len(data) < 4:
            return '.png'

        if data[0:2] == b'\xff\xd8':
            return '.jpg'
        elif data[0:4] == b'\x89PNG':
            return '.png'
        elif data[0:4] == b'GIF8':
            return '.gif'
        elif data[0:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
            return '.webp'
        elif data[0:2] == b'BM':
            return '.bmp'
        return '.png'

    def _preload_epub(self, epub_path):
        return epub.read_epub(epub_path)

    def convert(self, options=None):
        if options is None:
            options = {}

        include_toc = options.get('include_toc', True)
        include_images = options.get('include_images', True)
        use_parallel = options.get('parallel', self.use_multiprocessing)
        use_gpu = options.get('use_gpu', False)

        result = {
            'success': False,
            'chapters_processed': 0,
            'images_processed': 0,
            'error': None,
            'gpu_used': False
        }

        try:
            self._log("=" * 50)
            self._log("开始转换...")
            self._log(f"GPU加速可用：{self.gpu_info.get('gpu_available', False)}")
            self._log(f"GPU加速启用：{use_gpu}")
            self._log(f"CPU核心数：{cpu_count()}")
            self._log(f"HTML解析器：{_PARSER}")
            self._log(f"使用并行处理：{use_parallel}")
            self._log("=" * 50)

            self._report_progress(5, "正在解析 EPUB 文件...")

            book = self._preload_epub(self.epub_path)

            title = book.get_metadata('DC', 'title')
            doc_title = title[0][0] if title and title[0] else os.path.splitext(os.path.basename(self.epub_path))[0]

            author = book.get_metadata('DC', 'creator')
            doc_author = author[0][0] if author and author[0] else 'Unknown'

            self._log(f"书籍标题：{doc_title}")
            self._log(f"作者：{doc_author}")

            self._report_progress(15, "正在创建 DOCX 文档...")

            doc = Document()

            title_heading = doc.add_heading(doc_title, level=0)
            title_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

            if doc_author:
                author_para = doc.add_paragraph(doc_author)
                author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

            doc.add_paragraph()

            temp_dir = tempfile.mkdtemp()

            try:
                images = {}
                if include_images:
                    self._report_progress(20, "正在提取图片...")
                    images = self._extract_images_parallel(book, temp_dir)
                    self._log(f"提取了 {len(images)} 张图片")
                    result['images_processed'] = len(images)

                chapters_data = []
                for item in book.items:
                    if item.get_type() == 9:
                        content = item.get_content()
                        if isinstance(content, bytes):
                            content = content.decode('utf-8', errors='ignore')

                        if '<body' in content.lower():
                            chapter_title = item.get_name()
                            if chapter_title:
                                chapter_title = os.path.splitext(chapter_title)[0]
                                chapter_title = chapter_title.replace('_', ' ').replace('-', ' ')

                            chapters_data.append({
                                'id': item.get_id(),
                                'title': chapter_title or '未命名',
                                'content': content
                            })

                self._log(f"找到 {len(chapters_data)} 个章节")

                if include_toc:
                    self._report_progress(25, "正在处理目录...")
                    self._log("正在添加目录...")

                    doc.add_heading("目录", level=1)

                    try:
                        toc = book.toc
                        for item in toc:
                            if isinstance(item, tuple):
                                for sub_item in item:
                                    if hasattr(sub_item, 'title') and sub_item.title:
                                        doc.add_paragraph(sub_item.title, style='List Bullet')
                            elif hasattr(item, 'title') and item.title:
                                doc.add_paragraph(item.title, style='List Bullet')
                    except Exception as e:
                        self._log(f"目录处理提示：{str(e)}")

                    doc.add_page_break()

                processed_chapters = []

                if use_parallel and len(chapters_data) > 1:
                    self._report_progress(30, "正在并行处理章节...")
                    self._log(f"使用多进程并行处理 {len(chapters_data)} 个章节...")

                    worker_args = [(ch, include_images, temp_dir) for ch in chapters_data]

                    with Pool(processes=get_optimal_worker_count()) as pool:
                        processed_chapters = pool.map(process_chapter_worker, worker_args)

                    self._log("并行处理完成")
                else:
                    self._log("使用单线程处理...")
                    for ch in chapters_data:
                        processed = process_chapter_worker((ch, include_images, temp_dir))
                        processed_chapters.append(processed)

                if use_gpu and self.gpu_info['gpu_available'] and len(processed_chapters) > 10:
                    self._log("使用GPU加速文本后处理...")
                    texts = [ch['text'] for ch in processed_chapters]
                    processed_texts = _batch_process_text_gpu(texts)
                    for i, ch in enumerate(processed_chapters):
                        ch['text'] = processed_texts[i] if i < len(processed_texts) else ch['text']
                    result['gpu_used'] = True

                total_chapters = len(processed_chapters)
                progress_start = 35
                progress_end = 90

                for idx, chapter in enumerate(processed_chapters):
                    progress = progress_start + (idx / total_chapters) * (progress_end - progress_start)
                    self._report_progress(progress, f"正在转换章节 {idx + 1}/{total_chapters}...")

                    self._log(f"处理章节：{chapter['title']}")

                    if chapter['title']:
                        doc.add_heading(chapter['title'], level=1)

                    if chapter['text']:
                        for paragraph in chapter['text'].split('\n\n'):
                            para_text = paragraph.strip()
                            if para_text:
                                if para_text.startswith('## ') and '##' in para_text[3:]:
                                    heading_text = para_text.replace('## ', '').replace(' ##', '').strip()
                                    if heading_text:
                                        doc.add_heading(heading_text, level=2)
                                else:
                                    doc.add_paragraph(para_text)

                    result['chapters_processed'] += 1

                self._report_progress(95, "正在保存文件...")

                output_dir = os.path.dirname(self.output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                doc.save(self.output_path)

                self._report_progress(100, "转换完成")
                result['success'] = True
                self._log("=" * 50)
                self._log(f"转换成功完成！")
                self._log(f"输出文件：{self.output_path}")
                self._log(f"处理章节数：{result['chapters_processed']}")
                self._log(f"处理图片数：{result['images_processed']}")
                self._log(f"使用GPU加速：{result['gpu_used']}")
                self._log("=" * 50)

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        except Exception as e:
            result['error'] = str(e)
            self._log(f"错误：{str(e)}")
            import traceback
            self._log(f"详细错误：{traceback.format_exc()}")

        return result


class BatchEPUBConverter:
    def __init__(self, progress_callback=None, log_callback=None):
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.gpu_info = detect_gpu_acceleration()

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _report_progress(self, value, status):
        if self.progress_callback:
            self.progress_callback(value, status)

    def batch_convert(self, epub_files, output_dir, options=None):
        if options is None:
            options = {}

        results = []
        total = len(epub_files)

        self._log(f"开始批量转换：{total} 个文件")
        self._log(f"GPU加速：{self.gpu_info.get('gpu_available', False)}")

        for idx, epub_file in enumerate(epub_files):
            try:
                self._report_progress(
                    (idx / total) * 100,
                    f"正在转换 {idx + 1}/{total}..."
                )

                filename = os.path.basename(epub_file)
                output_file = os.path.join(output_dir, os.path.splitext(filename)[0] + '.docx')

                converter = EPUBConverter(
                    epub_file,
                    output_file,
                    progress_callback=self._progress_sub,
                    log_callback=self._log_sub
                )

                result = converter.convert(options)
                result['input_file'] = epub_file
                result['output_file'] = output_file
                results.append(result)

            except Exception as e:
                self._log(f"转换失败 {epub_file}：{str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'input_file': epub_file
                })

        success_count = sum(1 for r in results if r['success'])
        self._log(f"批量转换完成：{success_count}/{total} 成功")

        return results

    def _progress_sub(self, value, status):
        pass

    def _log_sub(self, message):
        pass
