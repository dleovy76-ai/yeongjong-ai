from pydantic import BaseModel, Field


class ChefChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
