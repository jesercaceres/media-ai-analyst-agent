from fastapi import APIRouter, HTTPException, status
from langchain_core.exceptions import LangChainException

from app.agent import run_agent
from app.core.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the Media Analyst Agent",
    description=(
        "Submit a question in natural language. The agent will decide which BigQuery "
        "tools to call, execute the necessary SQL queries, and return an actionable insight."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()

    try:
        history = [turn.model_dump() for turn in request.history]
        answer = await run_agent(
            user_message=request.message,
            history=history,
        )
    except LangChainException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {exc}",
        ) from exc

    return ChatResponse(answer=answer, model=settings.gemini_model)
