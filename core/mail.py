# core/mail.py
from fastapi_mail import FastMail, ConnectionConfig
from pydantic import SecretStr, EmailStr
from settings import settings


def create_mail_instance() -> FastMail:
    """创建 FastMail 实例（每次调用返回新实例，线程/协程安全）"""
    mail_config = ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=SecretStr(settings.mail_password),
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_STARTTLS=settings.mail_starttls,
        MAIL_SSL_TLS=settings.mail_ssl_tls,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    return FastMail(mail_config)
