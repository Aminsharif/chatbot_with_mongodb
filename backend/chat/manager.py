from typing import Any, Dict, Optional
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

from config import settings
from database.mongodb import MongodbClient
from dotenv import load_dotenv
load_dotenv()

class ChatManager:
    """ Manager for chat interactions with LLMs"""

    def __init__(self,
                 model_name: Optional[str]=None,
                 temperature: float = 0.7,
                 ):
        """Initialize the chat manager.
        
        Args:
            model_name: Name of the model to use, defaults to configuration.
            temperature: Temperature for generation, higher means more creative.
        """
         
        self.model_name = model_name or settings.base_model_name
        self.temperature = temperature

        #initialize database client
        self.db = MongodbClient()
        
        #initialize chat components
        self._init_chat_components()

    def _init_chat_components(self) -> None:
        """Initialize chat components."""

        #create the prompt template
        self.template = ChatPromptTemplate.from_template(
        """
        You are a helpful AI Assistant.
        Be concise, friendly and helpfull

        Chat History:
        {history}

        User: {input}
        AI:
        """
        )

        #create the caht model - using groq for now
        groq_api_key = os.getenv("GROQ_API_KEY")
        self.model = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            api_key=groq_api_key,
        )

        self.output_parser = StrOutputParser()

        #create the chain
        self.chain = self.template | self.model | self.output_parser

    async def process_message(self, user_input: str, conversation_id: str):
        """Process a user message and return the AI response.
        Agrs:
            user_input: Messages from user.
            conversation_id: ID of the coversation.    
         
        Returns:
            Response from tha AI.
        """

        #Get conversation history
        history = self.db.format_history(conversation_id)

        #generate response
        response = await self.chain.ainvoke({
            "history": history,
            "input": user_input
        })
        
        #add message pair to history
        self.db.add_conversation_message(
            conversation_id=conversation_id,
            user_message=user_input,
            ai_message=response
        )
        
        return response
    
    def clear_history(self, conversation_id: str) -> None:
        """Clear the conversation history.
        
        Args:
            conversation_id: ID of the conversation.
        """
        self.db.clear_conversation_history(conversation_id)
    
    def close(self) -> None:
        """Close resources."""
        self.db.close() 