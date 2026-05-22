from __future__ import annotations

from app.core.config import Settings
from app.knowledge.models import KnowledgeCitation, KnowledgeSearchResult
from app.knowledge.store import KnowledgeStore


def format_citations_observation(citations: list[KnowledgeCitation]) -> str:
    if not citations:
        return (
            "知识库检索结果：未找到与查询相关的片段。\n"
            "若用户问题需要事实性回答，你必须明确说明："
            "「我在当前知识库中没有找到足够信息回答这个问题。」"
            "可简短建议用户补充文档或换更具体的关键词，但不得编造内容。"
        )
    lines = [
        "知识库检索结果（仅可依据下列片段作答，不得补充片段外事实）：",
    ]
    for c in citations:
        lines.append(
            f"[{c.index}] 《{c.filename}》片段 {c.chunk_index}（相关度 {c.score:.3f}）：\n{c.excerpt}"
            if c.score is not None
            else f"[{c.index}] 《{c.filename}》片段 {c.chunk_index}：\n{c.excerpt}"
        )
    lines.append(
        "请在最终回答中用 [n] 标注引用；若片段不足以得出结论，"
        "必须回答「我在当前知识库中没有找到足够信息回答这个问题。」"
    )
    return "\n\n".join(lines)


def format_auto_retrieve_context(citations: list[KnowledgeCitation]) -> str:
    if not citations:
        return ""
    lines = [
        "【知识库自动检索上下文】以下片段来自用户已上传的课程/实验/内部文档。",
        "严格规则：只基于本段与对话历史作答，不得编造；证据不足时必须说明",
        "「我在当前知识库中没有找到足够信息回答这个问题。」；",
        "有依据时用 [1][2] 标注引用；禁止 web_search、fetch_url。",
    ]
    for c in citations:
        lines.append(f"[{c.index}] 《{c.filename}》：{c.excerpt}")
    return "\n".join(lines)


class KnowledgeRetriever:
    def __init__(self, store: KnowledgeStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    async def search(
        self,
        user_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> KnowledgeSearchResult:
        k = top_k or self.settings.knowledge_top_k
        citations = await self.store.search(user_id, query, top_k=k)
        summary = "\n".join(
            f"[{c.index}] {c.filename}: {c.excerpt[:120]}..."
            if len(c.excerpt) > 120
            else f"[{c.index}] {c.filename}: {c.excerpt}"
            for c in citations
        )
        return KnowledgeSearchResult(query=query, citations=citations, summary=summary)

    async def has_documents(self, user_id: str) -> bool:
        docs = await self.store.list_documents(user_id)
        return len(docs) > 0
