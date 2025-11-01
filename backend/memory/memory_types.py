from enum import Enum
from memory import MongoChatbotMemory, BaseChatbotMemory, CustomMongoChatbotMemory, CustomSQLChatbotMemory

class MemoryTypes(str, Enum):
    """Enumerator with the Memory types."""
    BASE_MEMORY = "base-memory"
    MONGO_MEMORY = "mongodb-memory"
    CUSTOM_MEMORY = "custom-memory"
    SQL_MEMORY = "sql-memory"


MEM_TO_CLASS = {
    "mongodb-memory": MongoChatbotMemory,
    "base-memory": BaseChatbotMemory,
    "custom-memory": CustomMongoChatbotMemory,
    "sql-memory": CustomSQLChatbotMemory,
}
