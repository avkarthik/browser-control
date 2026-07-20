from pydantic import BaseModel, Field
from typing import Literal


class TaskRequest(BaseModel):
    task: str = Field(
        ...,
        examples=["find cheapest iPhone 16 Pro on bestbuy.ca"],
        description="Natural language task for the browser agent",
    )
    max_steps: int = Field(
        default=10,
        examples=[10],
        description="Maximum browser steps before auto-stop",
    )
    provider: Literal["gemini", "ollama", "deepseek", "openrouter"] = Field(
        default="gemini",
        examples=["gemini"],
        description="LLM provider: gemini, ollama, deepseek, or openrouter",
    )
    provider_model: str | None = Field(
        default=None,
        examples=["gemini-3.1-flash-lite"],
        description="Optional model override, e.g. gemini-2.5-flash or ollama:qwen3:14b",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "task": "find cheapest iPhone 16 Pro on bestbuy.ca",
                "max_steps": 10,
                "provider": "gemini",
                "provider_model": None,
            }
        }
    }


class ResumeRequest(BaseModel):
    instruction: str = Field(
        default="",
        examples=[""],
        description="Optional new instruction before resuming (empty = just continue)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "instruction": "",
            }
        }
    }


class StopRequest(BaseModel):
    reason: str = Field(
        default="",
        examples=["User cancelled"],
        description="Optional reason for stopping",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "User cancelled",
            }
        }
    }