import sys

print("=" * 50)
print("GPU 检测报告")
print("=" * 50)

try:
    import torch
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"GPU 设备数: {torch.cuda.device_count()}")
        print(f"GPU 设备名称: {torch.cuda.get_device_name(0)}")
        print(f"GPU 计算能力: {torch.cuda.get_device_capability(0)}")
except ImportError:
    print("PyTorch 未安装")

print()
print("-" * 50)

try:
    import cupy
    print(f"CuPy 版本: {cupy.__version__}")
    print("CuPy 可用")
except ImportError:
    print("CuPy 未安装")

print()
print("-" * 50)

try:
    from numba import cuda
    print(f"NumBA CUDA 可用: {cuda.is_available()}")
    if cuda.is_available():
        device = cuda.get_current_device()
        print(f"Numba CUDA 设备: {device}")
except ImportError:
    print("Numba CUDA 未安装")

print("=" * 50)

if not any([torch.cuda.is_available() if 'torch' in dir() else False]):
    print("\n⚠ GPU加速不可用的原因：")
    print("1. 未安装支持CUDA的PyTorch/CuPy")
    print("2. 系统没有NVIDIA GPU")
    print("3. NVIDIA驱动未正确安装")
    print("4. CUDA工具包未安装")
