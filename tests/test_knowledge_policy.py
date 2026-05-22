from app.agent.react.knowledge_policy import (
    KNOWLEDGE_GROUNDING_RULES,
    knowledge_priority_system_addon,
    tool_definitions_for_run,
)


def test_tool_definitions_hide_web_when_kb_mode() -> None:
    names = {
        t["function"]["name"]
        for t in tool_definitions_for_run(use_knowledge_base=True)
    }
    assert "web_search" not in names
    assert "fetch_url" not in names
    assert "search_knowledge" in names


def test_tool_definitions_hide_kb_when_web_mode() -> None:
    names = {
        t["function"]["name"]
        for t in tool_definitions_for_run(use_knowledge_base=False)
    }
    assert "search_knowledge" not in names
    assert "web_search" in names


def test_system_addon_kb_mode() -> None:
    addon = knowledge_priority_system_addon(use_knowledge_base=True)
    assert addon == KNOWLEDGE_GROUNDING_RULES
    assert "严格作答" in addon
    assert "我在当前知识库中没有找到足够信息回答这个问题" in addon
    assert "web_search" in addon
    assert "不得凭空补充事实" in addon


def test_system_addon_web_mode() -> None:
    addon = knowledge_priority_system_addon(use_knowledge_base=False)
    assert "联网" in addon
    assert "search_knowledge" in addon
