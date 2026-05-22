__all__ = ["KnowledgeStore"]


def __getattr__(name: str):
    if name == "KnowledgeStore":
        from app.knowledge.store import KnowledgeStore

        return KnowledgeStore
    raise AttributeError(name)
