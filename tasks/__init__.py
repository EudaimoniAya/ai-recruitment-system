from fastapi_mail import FastMail, MessageSchema, MessageType, MultipartSubtypeEnum
from aiosmtplib.errors import (
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from loguru import logger
from core.mail import create_mail_instance
from core.email_templates import render_invite_email


async def send_email_task(message: MessageSchema) -> bool:
    """发送邮件，成功返回 True，失败返回 False"""
    mail: FastMail = create_mail_instance()
    try:
        await mail.send_message(message)
        logger.info(f"邮件发送成功：{message.subject} -> {message.recipients}")
        return True
    except SMTPSenderRefused as e:
        logger.error(
            f"邮件发送失败（发件人地址必须与 SMTP 登录账号 MAIL_USERNAME 一致）：{e}"
        )
        return False
    except SMTPResponseException as e:
        if e.code == -1 and b"\\x00\\x00\\x00" in str(e).encode():
            logger.info(
                "⚠️ 忽略 QQ 邮箱 SMTP 关闭阶段的非标准响应（邮件已成功发送）",
                enqueue=True,
            )
            return True
        logger.error(f"邮件发送失败！{e}")
        return False
    except SMTPServerDisconnected as e:
        logger.error(f"邮件发送失败（SMTP 连接异常）：{e}")
        return False
    except Exception as e:
        logger.error(f"邮件发送失败！{e}")
        return False


async def send_invite_email_task(
    email: str,
    invite_code: str,
    department_name: str,
) -> bool:
    subject, html_body, plain_body = render_invite_email(
        email=email,
        invite_code=invite_code,
        department_name=department_name,
    )
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=html_body,
        alternative_body=plain_body,
        subtype=MessageType.html,
        multipart_subtype=MultipartSubtypeEnum.alternative,
    )
    return await send_email_task(message)
