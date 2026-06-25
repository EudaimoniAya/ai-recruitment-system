import os
from langchain_openai import ChatOpenAI
from settings import settings

qwen_llm = ChatOpenAI(
    model="qwen3-max",
    base_url=settings.dashscope_base_url,
    api_key=settings.dashscope_api_key,
)

deepseek_llm = ChatOpenAI(
    model="deepseek-v3.2",
    base_url=settings.deepseek_api_base,
    api_key=settings.deepseek_api_key,
)
