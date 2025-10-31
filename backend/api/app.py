"""FastApi application for the chatbot"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings, Settings
from chat.manager import ChatManager
from .models import ChatRequest, ChatResponse

@asynccontextmanager
async def lifespan(app:FastAPI):
    """Application lifespan context manager for setup and teardown"""
    #setup: create chat manager

    chat_manager = ChatManager()
    app.state.chat_manager = chat_manager

    yield

    #shutdown: close resources
    app.state.chat_manager.close()

def create_app() -> FastAPI:
    """Create the fastAPI application
    Returns:
        FastApi application.
    
    """
    settings = get_settings()

    app = FastAPI(
        title="Langchain chatbot API",
        description="API for langchain chatbot",
        version="1.0.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/chat", response_model = ChatResponse)
    async def chat(request: ChatRequest, settings: Settings = Depends(get_settings)):
        """ Process a chat message.

        Agrs: 
            request: chat request containing user message and conversation.
        
        Returns:
            AI response
        """

        conversation_id  = request.conversation_id or "default"

        response = await app.state.chat_manager.process_message(
            user_input = request.input,
            conversation_id = conversation_id
        )

        return ChatResponse(
            output=response,
            conversation_id=conversation_id
        )
    
    @app.post("/clear/{conversation_id}")
    async def clear_history(conversation_id: str):
        """Clear the conversation history.
        
        Args:
            conversation_id: ID of the conversation.
            
        Returns:
            Status message.
        """
        app.state.chat_manager.clear_history(conversation_id)
        return {
            "status": "success",
            "message": f"History for conversation {conversation_id} cleared"
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint.
        
        Returns:
            Status message.
        """
        return {"status": "healthy"}
    
    return app 