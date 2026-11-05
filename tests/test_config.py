# 在 LaLe/src 目录下创建 test_env.py
import sys
import platform

print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
print(f"系统平台: {platform.platform()}")

# 测试已安装的包
try:
    import fastapi
    print("✓ FastAPI 已安装")
except ImportError:
    print("✗ FastAPI 未安装")

try:
    import langchain
    print("✓ LangChain 已安装")
except ImportError:
    print("✗ LangChain 未安装")