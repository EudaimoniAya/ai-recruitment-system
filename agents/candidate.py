from typing import Annotated, List, Optional, TypeVar

from langgraph.graph.message import add_messages
from pydantic import BaseModel
from agents.prompts import CANDIDATE_PROCESS_SYSTEM_PROMPT
from schemas.candidate_schema import CandidateSchema
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
from langchain_core.messages import BaseMessage
from langchain.agents import create_agent
from agents.llms import deepseek_llm
from langchain.agents.middleware import ModelFallbackMiddleware, SummarizationMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from settings import settings

T = TypeVar("T")


def assign_state_property(left: T, right: Optional[T]) -> T:
    return right if right is not None else left


# checkpointer会自动保存state中的数据到数据库中
class CandidateAgentState(BaseModel):
    messages: Annotated[List[BaseMessage], add_messages]
    candidate: Annotated[CandidateSchema, assign_state_property]
    position: Annotated[PositionSchema, assign_state_property]
    interviewer: Annotated[UserSchema, assign_state_property]


class CandidateProcessAgent:
    def __init__(
        self,
        candidate: CandidateSchema | None = None,
        position: PositionSchema | None = None,
        interviewer: UserSchema | None = None,
    ):
        self.candidate = candidate
        self.position = position
        self.interviewer = interviewer
        self._checkpointer = None

    async def ainvoke(self, messages: list[BaseMessage], thread_id: str):
        assert self._checkpointer is not None
        agent = create_agent(
            model=deepseek_llm,
            system_prompt=CANDIDATE_PROCESS_SYSTEM_PROMPT,
            state_schema=CandidateAgentState,
            middleware=[
                ModelFallbackMiddleware(first_model=deepseek_llm),
                SummarizationMiddleware(
                    model=deepseek_llm,
                    trigger=("tokens", 50000),
                    keep=("tokens", 10000),
                ),
            ],
            tools=[],
            checkpointer=self._checkpointer,
        )
        response = await agent.ainvoke(
            {
                "messages": messages,
                "candidate": self.candidate,
                "position": self.position,
                "interviewer": self.interviewer,
            },
            {"thread_id": thread_id},
        )
        return response

    async def __aenter__(self):
        # langchain如果大模型选择了一个工具，那么这个工具消息后的消息必须是工具调用后的结果，否则会报错
        self._checkpointer_conn = AsyncPostgresSaver.from_conn_string(
            settings.DATABASE_AGENT_URL
        )
        self._checkpointer = await self._checkpointer_conn.__aenter__()
        await self._checkpointer.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._checkpointer_conn.__aexit__(exc_type, exc_val, exc_tb)


# async with CandidateProcessAgent(candidate, position, interviewer) as agent:
#     await agent.ainvoke()
