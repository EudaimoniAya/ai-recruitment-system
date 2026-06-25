import os
from fastapi_mail import FastMail, MessageSchema, MessageType, MultipartSubtypeEnum
from aiosmtplib.errors import (
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from loguru import logger
from agents.resume import extract_candidate_info
from core.cache import HRCache
from core.mail import create_mail_instance
from core.email_templates import render_invite_email
from core.ocr import PaddleOcr
from dependencies import get_cache_instance
from models import AsyncSessionFactory
from models.candidate import ResumeModel
from repository.candidate_repo import ResumeRepo
from schemas.agent_schema import AgentCandidateSchema
from schemas.candidate_schema import TaskInfoSchema
from settings import settings


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


async def ocr_parse_resume_task(resume_id: str, task_id: str):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            resume_repo = ResumeRepo(session=session)
            resume: ResumeModel = await resume_repo.get_by_id(resume_id)
    file_path = os.path.join(settings.resume_dir, resume.file_path)
    # 1. 设置当前的状态为pending，任务的执行状态和过程中的数据可以存储在redis中
    cache: HRCache = get_cache_instance()
    await cache.set_task_info(TaskInfoSchema(task_id=task_id, status="pending"))
    try:
        paddle_ocr = PaddleOcr()
        job_id = await paddle_ocr.create_job(file_path)
        jsonl_url = await paddle_ocr.poll_for_state(job_id)
        contents = await paddle_ocr.fetch_parsed_contents(jsonl_url)
        content = "\n\n".join(contents)
        # TODO： 将content丢给大模型，让大模型识别其中的内容，比如姓名、性别、年龄、技能、教育经历、工作经历
        candidate_info: AgentCandidateSchema = await extract_candidate_info(content)
        # 2. 设置当前状态为done
        result = {"content": content}
        await cache.set_task_info(
            TaskInfoSchema(task_id=task_id, status="done", result=candidate_info)
        )
    except Exception as e:
        # 3. 如果出现了异常，就把状态设置failed
        logger.error(e)
        await cache.set_task_info(
            TaskInfoSchema(task_id=task_id, status="failed", error=str(e))
        )
