from __future__ import annotations

from app.agent.tools.definitions import TOOL_DEFINITIONS

_WEB_TOOLS = frozenset({"web_search", "fetch_url"})
_KB_TOOLS = frozenset({"search_knowledge"})

_KNOWLEDGE_INSUFFICIENT_REPLY = (
    "我在当前知识库中没有找到足够信息回答这个问题。"
)

KNOWLEDGE_GROUNDING_RULES = f"""【检索模式：知识库 · 严格作答】
本轮仅根据已提供的知识库检索上下文、search_knowledge 的 observation 与对话历史作答；
系统会自动向量检索相关片段，必要时可调用 search_knowledge；禁止 web_search、fetch_url。

必须遵守：
1) 只基于上述证据作答，不得凭空补充事实。
2) 当上下文证据不足、没有明确结论、或与问题不相关时，必须明确回答：
   「{_KNOWLEDGE_INSUFFICIENT_REPLY}」
3) 不要编造来源、时间、数据、链接、文件名、术语定义或业务规则。
4) 若问题超出知识库范围，可给出简短的澄清建议（如建议用户补充文档或更具体关键词），
   但不得把建议伪装成事实答案。
5) 优先输出简洁、可执行、与问题直接相关的结论；有多条依据时按要点列出。
6) 若上下文存在冲突，请明确指出「知识库信息存在冲突」，并分别说明冲突点。

有依据时在正文中用 [1][2] 标注引用，与 observation / 自动检索片段编号一致。"""


def knowledge_priority_system_addon(*, use_knowledge_base: bool) -> str:
    if use_knowledge_base:
        return KNOWLEDGE_GROUNDING_RULES
    return (
        "【检索模式：联网】\n"
        "本轮不检索用户知识库，勿调用 search_knowledge。"
        "需要外部信息时使用 web_search，必要时 fetch_url。"
    )


def tool_definitions_for_run(*, use_knowledge_base: bool) -> list[dict]:
    exclude = _WEB_TOOLS if use_knowledge_base else _KB_TOOLS
    return [
        tool
        for tool in TOOL_DEFINITIONS
        if tool.get("function", {}).get("name") not in exclude
    ]
