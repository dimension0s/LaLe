import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（从项目根目录）
# BASE_DIR 是项目根目录（即 LaLe/）
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(BASE_DIR / ".env")

# 路径配置
DATA_DIR = BASE_DIR / "data"


# 确保目录存在
for dir_path in [DATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 数据文件路径
COCA_CSV_PATH = DATA_DIR / "COCA20000.csv"

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/lale")

# API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 应用配置，暂时没有
ENVIRONMENT = os.getenv("ENVIRONMENT","development")
DEBUG = ENVIRONMENT == "development"

# 词典api配置（预留，后续可能使用）
YOUDAO_APP_KEY = os.getenv("YOUDAO_APP_KEY", "")
YOUDAO_APP_SECRET = os.getenv("YOUDAO_APP_SECRET", "")

# 翻译 API 配置（预留，后续使用）
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")