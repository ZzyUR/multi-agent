"""Tool definition schema — maps Python functions to Function Calling schemas."""

from typing import Any, Callable, Coroutine

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    """A single tool that can be passed to the model as a function."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── Built-in tool definitions (P1) ────────────────────────────────────────────

WEB_SEARCH = ToolDefinition(
    name="web_search",
    description=(
        "在互联网上搜索信息。返回相关网页的标题、URL 和摘要。"
        "适合获取某个话题的概览或寻找相关资料。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题，尽量简洁精确",
            },
            "max_results": {
                "type": "integer",
                "description": "返回结果数量，默认 5，最多 10",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)

FETCH_PAGE = ToolDefinition(
    name="fetch_page",
    description=(
        "获取指定 URL 的网页正文内容，自动切片存入向量库，并返回内容摘要。"
        "在 web_search 找到相关链接后，用此工具获取页面详细内容。"
        "相同 URL 不会重复抓取（自动去重）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要获取内容的网页 URL",
            },
        },
        "required": ["url"],
    },
)

VECTOR_SEARCH = ToolDefinition(
    name="vector_search",
    description=(
        "在已抓取的网页内容中进行语义检索，返回与查询最相关的文本片段。"
        "适合在 fetch_page 之后，精准找出与当前研究问题最相关的段落。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索查询（自然语言问题或关键词）",
            },
            "n_results": {
                "type": "integer",
                "description": "返回片段数量，默认 5，最多 10",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)
