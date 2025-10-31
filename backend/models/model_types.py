from enum import Enum
from langchain_groq import ChatGroq
# from langchain_openai import ChatOpenAI

class ModelTypes(str, Enum):
    # OPENAI = "OPENAI"
    GROQ = "GROQ"


MODEL_TO_CLASS = {
    # "OPENAI": ChatOpenAI,
    "GROQ": ChatGroq
}
