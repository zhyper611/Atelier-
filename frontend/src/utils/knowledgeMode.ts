const STORAGE_KEY = "atelier_use_knowledge_base";

export function getUseKnowledgeBase(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "false") {
      return false;
    }
    return true;
  } catch {
    return true;
  }
}

export function setUseKnowledgeBase(value: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
  } catch {
    // ignore quota / private mode
  }
}
