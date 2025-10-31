from typing import Optional, ClassVar
from langchain.tools import BaseTool
from langchain.callbacks.manager import CallbackManagerForToolRun
from duckduckgo_search import DDGS


class CustomSearchTool(BaseTool):
    name: ClassVar[str] = "custom_search"
    description: ClassVar[str] = "Useful for answering questions about current events, news, facts, or general knowledge."

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use DuckDuckGo to search the web."""
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=5)
                if not results:
                    return "No results found."

                formatted_results = "\n\n".join(
                    f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}"
                    for r in results
                )
                return formatted_results
        except Exception as e:
            return f"Search failed: {str(e)}"