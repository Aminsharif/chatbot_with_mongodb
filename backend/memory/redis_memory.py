import json
from typing import List
import redis
from redis.exceptions import RedisError

from common.config import Config, BaseObject
from common.objects import MessageTurn, messages_from_dict, Message

class BaseCustomRedisChatbotMemory(BaseObject):
    def __init__(
        self,
        config: Config = None,
        connection_string: str = None,
        session_id: str = None,
        database_name: str = None,   # Redis DB index
        k: int = 5,
        expire_seconds: int = 3600,  # default 1 hour
        **kwargs,
    ):
        super(BaseCustomRedisChatbotMemory, self).__init__()
        self.config = config if config is not None else Config()
        self.session_id = session_id
        self.k = k
        self.expire_seconds = expire_seconds

        try:
            # Example connection_string: redis://localhost:6379/0
            self.client = redis.from_url(
                connection_string or "redis://localhost:6379/0",
                decode_responses=True,
            )
            self.logger.info("✅ Redis connection established.")
        except RedisError as e:
            self.logger.error(f"❌ Redis connection failed: {e}")
            raise

    def add_message(self, message_turn: MessageTurn):
        """Store one message turn (append to Redis list)"""
        try:
            key = message_turn.conversation_id
            data = json.dumps(message_turn.model_dump(), ensure_ascii=False)
            self.client.rpush(key, data)
            
            # ✅ Set expiry time (refresh on each insert)
            self.client.expire(key, self.expire_seconds)

            self.logger.info(f"💾 Added message turn for conversation <{message_turn.conversation_id}>")

        except RedisError as e:
            self.logger.error(f"Redis insert error: {e}")
    
    def clear_history(self, conversation_id: str = None):
        """Clear messages in one conversation or all of this session"""
        try:
            if conversation_id:
                key = conversation_id
                self.client.delete(key)
                self.logger.info(f"🗑️ Deleted history for conversation <{conversation_id}>")
            else:
                # Delete all keys for this session
                pattern = f"chat:{self.session_id}:*"
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)
                    self.logger.warning(f"⚠️ Deleted all history for session <{self.session_id}>")
        except RedisError as e:
            self.logger.error(f"Redis delete error: {e}")

    def load_history(self, conversation_id: str) -> str:
        """Load the last k messages"""
        try:
            key =  conversation_id
            all_items = self.client.lrange(key, -self.k, -1)
            items = [json.loads(item) for item in all_items]
            messages: List[str] = [messages_from_dict(item) for item in items]
            return "\n".join(messages)
        except RedisError as e:
            self.logger.error(f"Redis read error: {e}")
            return ""


class CustomRedisChatbotMemory(BaseObject):
    """User-facing wrapper that uses Config and hides Redis details"""

    def __init__(self, config: Config = None, **kwargs):
        super(CustomRedisChatbotMemory, self).__init__()
        self.memory = BaseCustomRedisChatbotMemory(
            connection_string=config.redis_connection_string,
            session_id=config.session_id,
            database_name=config.redis_database_name,
            **kwargs,
        )
    
    def add_message(self, message_turn: MessageTurn):
        self.memory.add_message(message_turn)

    def clear(self, conversation_id: str = None):
        self.memory.clear_history(conversation_id=conversation_id)

    def load_history(self, conversation_id: str):
        return self.memory.load_history(conversation_id)