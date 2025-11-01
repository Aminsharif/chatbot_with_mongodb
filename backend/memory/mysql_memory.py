import json
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError

from common.config import Config, BaseObject
from common.objects import MessageTurn, ChatMemory, messages_from_dict

Base = declarative_base()



class BaseCustomSQLChatbotMemory(BaseObject):
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
        super(BaseCustomSQLChatbotMemory, self).__init__()
        self.config = config if config is not None else Config()
        self.session_id = session_id
        self.k = k

        # Example: mysql+pymysql://user:password@localhost:3306/chatdb
        if not connection_string.startswith("mysql"):
            raise ValueError("Connection string must start with 'mysql+pymysql://' or 'mysql+mysqlconnector://'")

        try:
            self.engine = create_engine(connection_string, echo=False, future=True)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        except SQLAlchemyError as e:
            self.logger.error(f"Database initialization failed: {e}")

    def add_message(self, message_turn: MessageTurn):
        """Insert one message turn"""
        try:
            with self.SessionLocal() as session:
                history_data = message_turn.dict()
                record = ChatMemory(
                    ConversationId=message_turn.conversation_id,
                    SessionId=self.session_id,
                    History=history_data,
                )
                session.add(record)
                session.commit()
                self.logger.info(f"Saved 1 message turn for conversation <{message_turn.conversation_id}>")
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

    def load_history(self, conversation_id: str) -> str:
        """Retrieve last K messages from database"""
        try:
            with self.SessionLocal() as session:
                records = (
                    session.query(ChatMemory)
                    .filter_by(SessionId=self.session_id, ConversationId=conversation_id)
                    .order_by(ChatMemory.CreatedAt.desc())
                    .limit(self.k)
                    .all()
                )

                items = [r.History for r in reversed(records)]
                messages: List[str] = [messages_from_dict(item) for item in items]
                return "\n".join(messages)
        except SQLAlchemyError as e:
            self.logger.error(f"SQLAlchemy select error: {e}")
            return ""


class CustomSQLChatbotMemory(BaseObject):
    """User-facing wrapper that uses Config and hides the internal Base class"""

    def __init__(self, config: Config = None, **kwargs):
        super(CustomSQLChatbotMemory, self).__init__()
        self.memory = BaseCustomSQLChatbotMemory(
            connection_string=config.sql_connection_string,
            session_id=config.session_id,
            database_name=config.sql_database_name,
            table_name=config.sql_table_name,
            **kwargs,
        )

    def clear(self, conversation_id: str = None):
        self.memory.clear_history(conversation_id=conversation_id)

    def load_history(self, conversation_id: str):
        return self.memory.load_history(conversation_id)

    def add_message(self, message_turn: MessageTurn):
        self.memory.add_message(message_turn)
