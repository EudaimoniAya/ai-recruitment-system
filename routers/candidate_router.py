import os, aiofiles
from pathlib import Path
from uuid import uuid4
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import HRCache
from core.ocr import PaddleOcr
from core.pdf import WordToPdfConverter
from dependencies import get_cache_instance, get_current_user, get_session_instance
from models.user import UserModel
from repository.candidate_repo import CandidateRepo, ResumeRepo
from repository.position_repo import PositionRepo
from repository.user_repo import UserRepo
from schemas import ResponseSchema
from schemas.candidate_schema import (
    CandidateCreateSchema,
    CandidateSchema,
    ResumeParseTaskInfoRespSchema,
    ResumeParseTaskRespSchema,
    ResumePaseSchema,
    ResumeUploadRespSchema,
)
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
from settings import settings
from loguru import logger

from tasks import ocr_parse_resume_task, run_candidate_agent

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


# 1. 发起了一个简历识别的请求，创建一个后台任务，把task_id返回给前端
# 2. 前端就可以通过task_id来获取这个任务的执行结果，当执行结果为success时，那么就返回解析后的数据
@router.post(
    "/resume/parse", summary="简历解析", response_model=ResumeParseTaskRespSchema
)
async def parse_resume(
    resume_data: ResumePaseSchema,
    background_tasks: BackgroundTasks,
    _: UserModel = Depends(get_current_user),
):
    # 创建一个识别简历的后台任务
    task_id = str(uuid4())
    background_tasks.add_task(
        ocr_parse_resume_task, resume_id=resume_data.resume_id, task_id=task_id
    )
    return {"task_id": task_id}


@router.get(
    "/resume/parse/{task_id}",
    summary="获取任务状态",
    response_model=ResumeParseTaskInfoRespSchema,
)
async def get_task_status(
    task_id: str,
    cache: HRCache = Depends(get_cache_instance),
    _: UserModel = Depends(get_current_user),
):
    task_info = await cache.get_task_info(task_id)
    return task_info.model_dump()


@router.post("/create", summary="创建候选人", response_model=ResponseSchema)
async def create_candidate(
    candidate_data: CandidateCreateSchema,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_instance),
    current_user: UserModel = Depends(get_current_user),
):
    async with session.begin():
        candidate_dict = candidate_data.model_dump()
        candidate_dict["creator_id"] = current_user.id
        candidate_repo = CandidateRepo(session=session)
        candidate = await candidate_repo.create_candidate(candidate_dict)
    return ResponseSchema()


@router.get("/resume/ocr/test")
async def resume_ocr_test():
    file_path = os.path.join(
        settings.resume_dir, "28e38a36-2962-48a5-8ce9-734a219274a9.pdf"
    )
    paddle_ocr = PaddleOcr()
    job_id = await paddle_ocr.create_job(file_path)
    jsonl_url = await paddle_ocr.poll_for_state(job_id)
    contents = await paddle_ocr.fetch_parsed_contents(jsonl_url)
    logger.info(contents)
    return "success"


@router.get("/agent/test")
async def agent_test(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        candidate_repo = CandidateRepo(session=session)
        position_repo = PositionRepo(session=session)
        user_repo = UserRepo(session=session)

        candidate_model = await candidate_repo.get_by_id("G3HNq6sWFm8AkpXpNv2HR4")
        position_model = await position_repo.get_by_id("BmBu4wPPxbwJo6fV7sSjCS")
        interviewer_model = await user_repo.get_by_id("DzGLB4YZnZ8gicipe8hVQ4")

        background_tasks.add_task(
            run_candidate_agent,
            candidate=CandidateSchema.model_validate(candidate_model),
            position=PositionSchema.model_validate(position_model),
            interviewer=UserSchema.model_validate(interviewer_model),
        )
        return {"result": "success"}
