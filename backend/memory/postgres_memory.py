import json
from typing import List
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Index, JSON, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from pgvector.sqlalchemy import Vector  # <-- pgvector support
from sentence_transformers import SentenceTransformer

from common.config import Config, BaseObject
from common.objects import MessageTurn, messages_from_dict, Message, ChatMemory

Base = declarative_base()


# --------------------------------------
# Base Chatbot Memory (PostgreSQL Sync)
# --------------------------------------
class BaseCustomPostgresChatbotMemory(BaseObject):
    def __init__(
        self,
        config: Config = None,
        connection_string: str = None,
        session_id: str = None,
        database_name: str = None,
        table_name: str = "chat_memory",
        k: int = 5,
        **kwargs,
    ):
        super(BaseCustomPostgresChatbotMemory, self).__init__()
        self.config = config or Config()
        self.session_id = session_id
        self.k = k

        # Example: postgresql+psycopg2://user:password@localhost:5432/chatdb
        if not connection_string.startswith("postgresql"):
            print(connection_string,'...............')
            raise ValueError("Connection string must start with 'postgresql+psycopg2://'")

        try:
            self.engine = create_engine(connection_string, echo=False, future=True)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.logger.info("✅ PostgreSQL (sync) connection established.")
        except SQLAlchemyError as e:
            self.logger.error(f"Database initialization failed: {e}")

        # Ensure pgvector extension exists
        try:
            with self.engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                self.logger.info("🧩 pgvector extension verified/created.")
        except SQLAlchemyError as e:
            self.logger.warning(f"⚠️ Could not ensure pgvector extension: {e}")

    def add_message(self, message_turn: MessageTurn):
        """Insert one message turn with optional embedding"""
        try:
            # Embedding model
            embedder = SentenceTransformer("all-MiniLM-L6-v2")
            history_data = message_turn.model_dump()
            embedding = embedder.encode(str(history_data)).tolist()
            with self.SessionLocal() as session:
                
                record = ChatMemory(
                    ConversationId=message_turn.conversation_id,
                    SessionId=self.session_id,
                    History=history_data,
                    Embedding=embedding,  # Optional: 384-dim vector
                )
                session.add(record)
                session.commit()
                self.logger.info(
                    f"💾 Saved message for conversation <{message_turn.conversation_id}> (embedding={'yes' if embedding else 'no'})"
                )
        except SQLAlchemyError as e:
            self.logger.error(f"SQLAlchemy insert error: {e}")

    def clear_history(self, conversation_id: str = None):
        """Delete messages by conversation or all in session"""
        try:
            with self.SessionLocal() as session:
                if conversation_id:
                    self.logger.info(f"Deleting history of conversation <{conversation_id}> in session <{self.session_id}>")
                    session.query(ChatMemory).filter_by(
                        SessionId=self.session_id, ConversationId=conversation_id
                    ).delete()
                else:
                    self.logger.warning(f"Deleting ALL history for session <{self.session_id}>")
                    session.query(ChatMemory).filter_by(SessionId=self.session_id).delete()
                session.commit()
        except SQLAlchemyError as e:
            self.logger.error(f"SQLAlchemy delete error: {e}")

    def load_history(self, conversation_id: str, query) -> str:
        """Retrieve last K messages"""
        try:
            past_history = self.search_similar_messages(conversation_id, query, 3)

            with self.SessionLocal() as session:
                records = (
                    session.query(ChatMemory.id, ChatMemory.ConversationId, ChatMemory.History, ChatMemory.CreatedAt, ChatMemory.SessionId)
                    .filter_by(SessionId=self.session_id, ConversationId=conversation_id)
                    .order_by(ChatMemory.CreatedAt.desc())
                    .limit(self.k)
                    .all()
                )

                items = [r.History for r in reversed(records)]
                recent_history: List[str] = [messages_from_dict(item) for item in items]
                history = past_history+ "\n".join(recent_history)
                return history
        except SQLAlchemyError as e:
            self.logger.error(f"SQLAlchemy select error: {e}")
            return ""
    
    def search_similar_messages(self, conversation_id: str, query: str, top_k=3) -> str:
        """
        Search for similar messages using vector similarity with comprehensive error handling
        """
        try:
            # Input validation
            if not conversation_id or not isinstance(conversation_id, str):
                self.logger.warning(f"Invalid conversation_id: {conversation_id}")
                return ""
            
            if not query or not isinstance(query, str):
                self.logger.warning(f"Invalid query: {query}")
                return ""
            
            if not isinstance(top_k, int) or top_k <= 0:
                self.logger.warning(f"Invalid top_k value: {top_k}, using default 3")
                top_k = 3
            
            self.logger.debug(f"Starting similarity search - Conversation: {conversation_id}, Query: '{query[:30]}...', TopK: {top_k}")
            
            # Embed the query
            try:
                embedder = SentenceTransformer("all-MiniLM-L6-v2")
                q_emb = embedder.encode(query).tolist()
                self.logger.debug(f"Query embedded successfully, dimension: {len(q_emb)}")
            except Exception as embed_error:
                self.logger.error(f"Failed to embed query: {embed_error}")
                return ""
            
            # Database operations
            with self.SessionLocal() as session:
                from sqlalchemy import text
                from sqlalchemy.exc import SQLAlchemyError
                
                try:
                    stmt = text("""
                        SELECT "History"
                        FROM chat_memory
                        --WHERE "ConversationId" = :conversation_id AND "SessionId" = :session_id
                        WHERE "SessionId" = :session_id
                        ORDER BY "Embedding" <=> (:embedding)::vector
                        LIMIT :top_k;
                    """)
                    
                    self.logger.debug(f"Executing SQL with params - conversation_id: {conversation_id}, session_id: {self.session_id}")
                    
                    result = session.execute(stmt, {
                        'conversation_id': conversation_id,
                        'session_id': self.session_id,
                        'embedding': q_emb,
                        'top_k': top_k
                    })
                    
                    # Process results
                    items = list(result.scalars().all())
                    self.logger.debug(f"Database returned {len(items)} items")
                    
                    if not items:
                        self.logger.info(f"No similar messages found for conversation '{conversation_id}'")
                        return ""
                    
                    # Convert items to messages
                    messages = []
                    processing_errors = 0
                    
                    for i, item in enumerate(items):
                        try:
                            message = messages_from_dict(item)
                            messages.append(message)
                            self.logger.debug(f"Successfully processed message {i+1}")
                        except Exception as process_error:
                            processing_errors += 1
                            self.logger.warning(f"Failed to process message {i+1}: {process_error}")
                            continue
                    
                    if processing_errors > 0:
                        self.logger.warning(f"Failed to process {processing_errors} out of {len(items)} messages")
                    
                    if not messages:
                        self.logger.warning("All messages failed processing")
                        return ""
                    
                    result_text = "\n".join(messages)
                    self.logger.info(f"Similarity search completed successfully. Found {len(messages)} messages")
                    return result_text
                    
                except SQLAlchemyError as db_error:
                    self.logger.error(f"Database execution error: {db_error}")
                    # Rollback is automatic with context manager
                    return ""
                    
        except Exception as unexpected_error:
            self.logger.error(f"Unexpected error in search_similar_messages: {unexpected_error}", exc_info=True)
            return ""

# -----------------------------------
# User-facing wrapper
# -----------------------------------
class CustomPostgresChatbotMemory(BaseObject):
    """Wrapper around BaseCustomPostgresChatbotMemory"""

    def __init__(self, config: Config = None, **kwargs):
        super(CustomPostgresChatbotMemory, self).__init__()
        self.memory = BaseCustomPostgresChatbotMemory(
            connection_string=config.postgres_connection_string,
            session_id=config.session_id,
            database_name=config.postgres_database_name,
            table_name=config.postgres_table_name,
            **kwargs,
        )

    def clear(self, conversation_id: str = None):
        self.memory.clear_history(conversation_id=conversation_id)

    def load_history(self, conversation_id: str, input: str):
        return self.memory.load_history(conversation_id, input)

    def add_message(self, message_turn: MessageTurn):
        self.memory.add_message(message_turn)
    
    def search_similar_messages(self, conversation_id: str, query: str, top_k):
        return self.memory.search_similar_messages(conversation_id, query, top_k)