from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$", description="Message author role")
    content: str = Field(..., min_length=1, description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User question")
    history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Previous conversation turns for multi-turn support",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Qual canal tem a melhor performance no último mês?",
                    "history": [],
                },
                {
                    "message": "E qual foi o volume de usuários vindos de Search?",
                    "history": [
                        {"role": "user", "content": "Qual canal tem a melhor performance no último mês?"},
                        {"role": "assistant", "content": "O canal Organic liderou com..."},
                    ],
                },
            ]
        }
    }


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Agent's natural-language response")
    model: str = Field(..., description="LLM model used")
