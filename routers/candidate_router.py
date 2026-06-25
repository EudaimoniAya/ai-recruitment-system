import os, aiofiles
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.pdf import WordToPdfConverter
from dependencies import get_current_user, get_session_instance
from models.user import UserModel
from repository.candidate_repo import ResumeRepo
from schemas.candidate_schema import ResumeUploadRespSchema
from settings import settings
from loguru import logger

router = APIRouter(prefix="/candidate", tags=["candidate"])


# 上传简历
@router.post(
    "/resume/upload", summary="上传简历", response_model=ResumeUploadRespSchema
)
async def resume_upload(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session_instance),
    current_user: UserModel = Depends(get_current_user),
):
    # 1. 校验文件类型
    # 简历：图片、pdf、word
    allowed_mime_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]
    if file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该文件不支持！"
        )

    # 2. 保存文件
    resume_dir = settings.resume_dir
    file_extension = os.path.splitext(file.filename)[-1]
    unique_filename = f"{uuid4()}{file_extension}"
    file_path = os.path.join(resume_dir, unique_filename)
    # with open(file_path, "wb") as f:  # 同步模式，不应该出现在异步代码中
    try:
        async with aiofiles.open(file_path, mode="wb") as fp:
            content = await file.read(1024)
            while content:
                await fp.write(content)
                content = await file.read(1024)
    finally:
        await fp.close()

    # 3. 如果是word文档，那么就转化成pdf
    if file_extension == ".doc" or file_extension == ".docx":
        pdf_path = file_path.replace(file_extension, ".pdf")
        converter = WordToPdfConverter(
            word_path=file_path,
            output_pdf_path=pdf_path,
        )
        try:
            await converter.convert()
            file_path = pdf_path
        except Exception as e:
            logger.error(f"Word转PDF失败：{e}")

    # 4. 将简历数据存储到数据库中
    async with session.begin():
        resume_repo = ResumeRepo(session=session)
        # 做一个更改，在数据库中只保存文件名
        file_name = Path(file_path).name
        resume = await resume_repo.create_resume(
            file_path=file_name, uploader_id=current_user.id
        )
    return {"resume": resume}
