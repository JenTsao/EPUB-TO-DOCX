# EPUB 转 DOCX 格式转换器

一款功能完善的图形界面 EPUB 转 DOCX 格式转换工具。

## 功能特点

- **图形用户界面**：使用 Tkinter 构建直观的操作界面
- **EPUB 解析**：使用 EbookLib 库解析 EPUB 文件
- **DOCX 生成**：使用 python-docx 生成标准 DOCX 文档
- **目录支持**：可选择保留书籍目录
- **图片支持**：可选择保留书籍中的图片
- **进度显示**：实时显示转换进度
- **错误处理**：完善的异常捕获和错误提示
- **跨平台支持**：支持 Windows、macOS、Linux

## 系统要求

- Python 3.8 或更高版本
- 操作系统：Windows / macOS / Linux

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或者手动安装：

```bash
pip install ebooklib python-docx beautifulsoup4 lxml
```

### 2. 运行程序

```bash
python main.py
```

在 Windows 系统上，也可以双击 `run.bat` 运行。

## 使用方法

1. **选择 EPUB 文件**：点击"浏览..."按钮选择要转换的 EPUB 文件
2. **设置输出路径**：指定转换后的 DOCX 文件保存位置
3. **配置选项**（可选）：
   - 包含目录：勾选后会在 DOCX 中添加目录
   - 保留图片：勾选后会在转换时保留图片
4. **开始转换**：点击"开始转换"按钮进行转换
5. **查看结果**：转换完成后会显示成功提示

## 目录结构

```
EPUB TO DOCX/
├── main.py              # 主程序入口
├── epub_converter.py    # EPUB 解析和转换模块
├── requirements.txt     # Python 依赖列表
├── run.bat              # Windows 快速启动脚本
└── README.md            # 本说明文档
```

## 常见问题

### Q: 转换失败怎么办？
A: 请确保：
1. EPUB 文件格式正确且未损坏
2. 有足够的磁盘空间
3. 输出路径有写入权限

### Q: 转换后的格式不正确？
A: 由于 EPUB 和 DOCX 格式差异，部分格式可能无法完美转换，程序会尽可能保留文本内容和基本结构。

### Q: 图片没有正确显示？
A: 请确保转换时勾选了"保留图片"选项，部分 EPUB 格式的图片引用方式可能导致图片无法提取。

## 技术栈

- **GUI 框架**：Tkinter（Python 内置）
- **EPUB 解析**：EbookLib
- **DOCX 生成**：python-docx
- **HTML 解析**：BeautifulSoup4 + lxml

## 许可证

MIT License

## 版本历史

- v1.0.0 - 初始版本，支持基本的 EPUB 转 DOCX 功能
