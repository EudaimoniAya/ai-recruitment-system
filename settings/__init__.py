from pydantic_settings import BaseSettings
from pydantic import computed_field
from pathlib import Path
from datetime import timedelta
import secrets

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class DBSettings(BaseSettings):
    # --- 数据库配置 ---
    db_username: str = Field(...)
    db_password: str = Field(...)
    db_host: str = Field(...)
    db_port: int = Field(...)
    db_name: str = Field(...)

    # --- Redis配置 ---
    redis_host: str = Field(...)
    redis_port: str = Field(...)

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


class LLMSettings(BaseSettings):
    deepseek_api_key: str = Field(...)
    deepseek_api_base: str = Field(...)
    openai_api_key: str = Field(...)
    openai_base_url: str = Field(...)
    langchain_api_key: str = Field(...)
    langchain_project: str = Field(...)
    langchain_tracing_v2: bool = Field(...)


class EmailSettings(BaseSettings):
    mail_username: str = Field(...)
    mail_password: str = Field(...)
    mail_from: str = Field(..., validation_alias="MAIL_USERNAME")
    mail_port: int = 587
    mail_server: str = "smtp.qq.com"
    mail_from_name: str = "Aya"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False


class Settings(DBSettings, LLMSettings, EmailSettings):

    # --- 邀请码过期时间 ---
    invite_code_expire: int = 60 * 60 * 24 * 2

    # --- 安全配置 ---
    jwt_secret_key: str = Field(
        default=secrets.token_urlsafe(32),
        description="鉴权使用的JWT密钥，每次服务器重启都不一样，作为服务器的签名",
    )
    # 使用双token机制进行JWT鉴权
    jwt_access_token_expires: timedelta = Field(
        timedelta(hours=2), description="短期令牌过期时间"
    )
    jwt_refresh_token_expires: timedelta = Field(
        timedelta(days=30), description="长期令牌过期时间"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
