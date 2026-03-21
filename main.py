import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
from epub_converter import EPUBConverter, BatchEPUBConverter, detect_gpu_acceleration


class Application(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("EPUB 转 DOCX 转换器 - 优化版")
        self.geometry("800x650")
        self.resizable(True, True)

        self.epub_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.status_text = tk.StringVar(value="就绪")

        self.converter = None
        self.is_converting = False

        self.gpu_info = detect_gpu_acceleration()

        self._setup_ui()
        self._display_system_info()

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="EPUB 转 DOCX 格式转换工具",
            font=("Microsoft YaHei", 18, "bold")
        )
        title_label.pack(pady=(0, 15))

        input_frame = ttk.LabelFrame(main_frame, text="输入文件", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(input_frame, textvariable=self.epub_path, width=60).pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        ttk.Button(input_frame, text="浏览单个文件...", command=self._browse_epub).pack(side=tk.LEFT)
        ttk.Button(input_frame, text="批量选择...", command=self._browse_epub_batch).pack(side=tk.LEFT, padx=(5, 0))

        output_frame = ttk.LabelFrame(main_frame, text="输出路径", padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(output_frame, textvariable=self.output_path, width=60).pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        ttk.Button(output_frame, text="浏览...", command=self._browse_output).pack(side=tk.LEFT)

        options_notebook = ttk.Notebook(main_frame)
        options_notebook.pack(fill=tk.X, pady=(0, 10))

        basic_frame = ttk.Frame(options_notebook, padding="10")
        options_notebook.add(basic_frame, text="基本选项")

        perf_frame = ttk.Frame(options_notebook, padding="10")
        options_notebook.add(perf_frame, text="性能优化")

        self.include_toc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            basic_frame,
            text="包含目录(Table of Contents)",
            variable=self.include_toc_var
        ).pack(anchor=tk.W)

        self.include_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            basic_frame,
            text="保留图片",
            variable=self.include_images_var
        ).pack(anchor=tk.W)

        ttk.Separator(basic_frame, orient='horizontal').pack(fill='x', pady=10)

        self.use_parallel_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            perf_frame,
            text="启用多进程并行处理（充分利用多核CPU）",
            variable=self.use_parallel_var
        ).pack(anchor=tk.W)

        self.use_gpu_var = tk.BooleanVar(value=False)
        gpu_check = ttk.Checkbutton(
            perf_frame,
            text="启用GPU加速（如可用）",
            variable=self.use_gpu_var,
            state='normal' if self.gpu_info['gpu_available'] else 'disabled'
        )
        gpu_check.pack(anchor=tk.W)

        ttk.Label(
            perf_frame,
            text=f"系统信息：CPU核心数 {os.cpu_count()}",
            foreground="gray"
        ).pack(anchor=tk.W)

        if self.gpu_info['gpu_available']:
            ttk.Label(
                perf_frame,
                text=f"GPU检测：{self.gpu_info['gpu_name']} 可用",
                foreground="green"
            ).pack(anchor=tk.W)
        else:
            ttk.Label(
                perf_frame,
                text="GPU加速：当前环境不可用（需要CUDA支持）",
                foreground="gray"
            ).pack(anchor=tk.W)

        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X)

        self.status_label = ttk.Label(main_frame, textvariable=self.status_text, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=(5, 0))

        log_frame = ttk.LabelFrame(main_frame, text="转换日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.convert_button = ttk.Button(
            button_frame,
            text="开始转换",
            command=self._start_conversion
        )
        self.convert_button.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="批量转换", command=self._start_batch_conversion).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="清空日志", command=self._clear_log).pack(side=tk.LEFT)

        self.batch_mode = False
        self.batch_files = []

    def _display_system_info(self):
        self._log_message("=" * 50)
        self._log_message("系统信息：")
        self._log_message(f"  CPU核心数：{os.cpu_count()}")
        self._log_message(f"  GPU加速：{'可用' if self.gpu_info['gpu_available'] else '不可用'}")
        if self.gpu_info['gpu_available']:
            self._log_message(f"  GPU设备：{self.gpu_info['gpu_name']}")
        self._log_message("=" * 50)

    def _browse_epub(self):
        filename = filedialog.askopenfilename(
            title="选择 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub"), ("所有文件", "*.*")]
        )
        if filename:
            self.epub_path.set(filename)
            self.batch_mode = False
            self.batch_files = []
            if not self.output_path.get():
                default_output = os.path.splitext(filename)[0] + ".docx"
                self.output_path.set(default_output)

    def _browse_epub_batch(self):
        filenames = filedialog.askopenfilenames(
            title="选择多个 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub"), ("所有文件", "*.*")]
        )
        if filenames:
            self.batch_mode = True
            self.batch_files = list(filenames)
            self._log_message(f"已选择 {len(self.batch_files)} 个EPUB文件")
            if self.batch_files:
                first_file = self.batch_files[0]
                self.epub_path.set(f"{len(self.batch_files)} 个文件已选择")
                default_output = os.path.dirname(first_file)
                if not self.output_path.get():
                    self.output_path.set(default_output)

    def _browse_output(self):
        if self.batch_mode:
            directory = filedialog.askdirectory(title="选择输出目录")
            if directory:
                self.output_path.set(directory)
        else:
            filename = filedialog.asksaveasfilename(
                title="保存 DOCX 文件",
                defaultextension=".docx",
                filetypes=[("DOCX 文件", "*.docx"), ("所有文件", "*.*")]
            )
            if filename:
                self.output_path.set(filename)

    def _log_message(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._display_system_info()

    def _update_progress(self, value, status):
        self.progress_var.set(value)
        self.status_text.set(status)
        self.update_idletasks()

    def _start_conversion(self):
        if self.is_converting:
            return

        if self.batch_mode:
            self._start_batch_conversion()
            return

        epub_file = self.epub_path.get().strip()
        output_file = self.output_path.get().strip()

        if not epub_file:
            messagebox.showerror("错误", "请选择 EPUB 文件")
            return

        if not output_file:
            messagebox.showerror("错误", "请指定输出路径")
            return

        if not os.path.exists(epub_file):
            messagebox.showerror("错误", f"文件不存在: {epub_file}")
            return

        self.is_converting = True
        self.convert_button.configure(state=tk.DISABLED)
        self._clear_log()
        self._display_system_info()
        self._update_progress(0, "正在初始化...")

        thread = threading.Thread(target=self._convert, daemon=True)
        thread.start()

    def _convert(self):
        try:
            epub_file = self.epub_path.get().strip()
            output_file = self.output_path.get().strip()

            options = {
                'include_toc': self.include_toc_var.get(),
                'include_images': self.include_images_var.get(),
                'parallel': self.use_parallel_var.get()
            }

            self._log_message(f"转换选项：并行处理={options['parallel']}")

            self.converter = EPUBConverter(
                epub_file,
                output_file,
                progress_callback=self._update_progress,
                log_callback=self._log_message
            )

            result = self.converter.convert(options)

            if result['success']:
                self._update_progress(100, "转换完成!")
                self._log_message("=" * 50)
                self._log_message(f"转换成功完成!")
                self._log_message(f"输出文件: {output_file}")
                self._log_message(f"处理章节数: {result.get('chapters_processed', 0)}")
                self._log_message(f"处理图片数: {result.get('images_processed', 0)}")
                self._log_message("=" * 50)
                messagebox.showinfo("成功", f"转换完成!\n\n输出文件:\n{output_file}")
            else:
                self._update_progress(0, "转换失败")
                self._log_message(f"转换失败: {result.get('error', '未知错误')}")
                messagebox.showerror("转换失败", result.get('error', '发生未知错误'))

        except Exception as e:
            self._update_progress(0, f"错误: {str(e)}")
            self._log_message(f"异常: {str(e)}")
            messagebox.showerror("错误", f"转换过程中发生错误:\n{str(e)}")

        finally:
            self.is_converting = False
            self.convert_button.configure(state=tk.NORMAL)

    def _start_batch_conversion(self):
        if self.is_converting:
            return

        if not self.batch_mode or not self.batch_files:
            messagebox.showinfo("提示", '请先点击"批量选择"按钮选择多个EPUB文件')
            return

        output_dir = self.output_path.get().strip()
        if not output_dir:
            messagebox.showerror("错误", "请指定输出目录")
            return

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录：{str(e)}")
                return

        self.is_converting = True
        self.convert_button.configure(state=tk.DISABLED)
        self._clear_log()
        self._display_system_info()
        self._update_progress(0, "正在批量转换...")

        thread = threading.Thread(target=self._batch_convert, daemon=True)
        thread.start()

    def _batch_convert(self):
        try:
            batch_converter = BatchEPUBConverter(
                progress_callback=self._update_progress,
                log_callback=self._log_message
            )

            options = {
                'include_toc': self.include_toc_var.get(),
                'include_images': self.include_images_var.get(),
                'parallel': self.use_parallel_var.get()
            }

            results = batch_converter.batch_convert(
                self.batch_files,
                self.output_path.get().strip(),
                options
            )

            success_count = sum(1 for r in results if r['success'])
            fail_count = len(results) - success_count

            self._update_progress(100, "批量转换完成!")
            self._log_message("=" * 50)
            self._log_message(f"批量转换完成！")
            self._log_message(f"成功: {success_count} 个文件")
            if fail_count > 0:
                self._log_message(f"失败: {fail_count} 个文件")
                for r in results:
                    if not r['success']:
                        self._log_message(f"  失败: {r.get('input_file', 'Unknown')}")
                        self._log_message(f"    原因: {r.get('error', 'Unknown')}")
            self._log_message("=" * 50)

            messagebox.showinfo(
                "批量转换完成",
                f"成功转换: {success_count} 个文件\n失败: {fail_count} 个文件"
            )

        except Exception as e:
            self._update_progress(0, f"错误: {str(e)}")
            self._log_message(f"异常: {str(e)}")
            messagebox.showerror("错误", f"批量转换过程中发生错误:\n{str(e)}")

        finally:
            self.is_converting = False
            self.convert_button.configure(state=tk.NORMAL)


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
