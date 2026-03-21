from epub_converter import _PARSER, detect_gpu_acceleration

print(f"HTML解析器: {_PARSER}")
info = detect_gpu_acceleration()
print(f"GPU可用: {info['gpu_available']}")
print(f"GPU名称: {info['gpu_name']}")
