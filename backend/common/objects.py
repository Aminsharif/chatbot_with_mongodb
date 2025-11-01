from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from datetime import datetime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Message(BaseModel):
    message: str = Field(description="User message")
    role: str = Field(description="Message role in conversation")


class MessageTurn(BaseModel):
    human_message: Message = Field(description="Message of human")
    ai_message: Message = Field(description="Message of AI")
    conversation_id: str = Field(description="The id of user in this turn")


class ChatRequest(BaseModel):
    input: str
    conversation_id: Optional[str]


def messages_from_dict(message: dict) -> str:
    human_message = message["human_message"]
    ai_message = message["ai_message"]

    human_message = Message(message=human_message["message"], role=human_message["role"])
    ai_message = Message(message=ai_message["message"], role=ai_message["role"])
    return f"{human_message.role}: {human_message.message}\n{ai_message.role}: {ai_message.message}"


class ChatMemory(Base):
    __tablename__ = "chat_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ConversationId = Column(String(255), nullable=False)
    SessionId = Column(String(255), nullable=False)
    History = Column(MySQLJSON, nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_sessionid", "SessionId"),
    )
