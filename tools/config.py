import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
# 加载.env
load_dotenv()

class Settings(BaseSettings):
    # deepseek配置
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # PostgreSQL配置
    database_url: str = "postgresql://user:password@localhost:5432/lale"

    # 文件存储路径
    upload_dir: str = "./data/uploads"

    # OCR配置
    ocr_language: str = "chi_sim+eng"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir,exist_ok=True)


