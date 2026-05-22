import type { ChatMessage } from "../api/types";

const STORAGE_KEY = "agent_session_id";
const RECENT_PREFIX = "agent_recent_sessions";
const MAX_RECENT = 12;

let activeUserId: string | null = null;

function recentKey(): string {
  return activeUserId ? `${RECENT_PREFIX}:${activeUserId}` : RECENT_PREFIX;
}

export function setAuthUserId(userId: string | null): void {
  activeUserId = userId && userId.trim() ? userId.trim() : null;
}

export function getAuthUserId(): string | null {
  return activeUserId;
}

export function clearTabSessionId(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function clearUserRecentSessions(): void {
  if (activeUserId) {
    localStorage.removeItem(recentKey());
  }
}
const PLACEHOLDER_LABEL = "新会话";

export type RecentSession = {
  id: string;
  label: string;
  updatedAt: number;
};

function generateSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function formatSessionLabel(sessionId: string): string {
  if (sessionId.length <= 12) {
    return sessionId;
  }
  return `${sessionId.slice(0, 8)}…`;
}

/** 至少一条用户消息且有一条有效助手回复（含工具结果）才算有内容。 */
export function sessionHasContent(messages: ChatMessage[]): boolean {
  const hasUser = messages.some(
    (message) => message.role === "user" && message.content.trim(),
  );
  if (!hasUser) {
    return false;
  }
  return messages.some(
    (message) =>
      message.role === "assistant" &&
      (message.content.trim() || message.tool_result != null),
  );
}

export function getOrCreateTabSessionId(): string {
  const existing = sessionStorage.getItem(STORAGE_KEY);
  if (existing && existing.trim()) {
    return existing.trim();
  }
  const created = generateSessionId();
  sessionStorage.setItem(STORAGE_KEY, created);
  return created;
}

export function setTabSessionId(sessionId: string): void {
  sessionStorage.setItem(STORAGE_KEY, sessionId.trim());
}

export function listRecentSessions(): RecentSession[] {
  try {
    const raw = localStorage.getItem(recentKey());
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as RecentSession[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item) => typeof item.id === "string" && item.id.trim())
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

export function rememberSession(sessionId: string, label?: string): void {
  const id = sessionId.trim();
  if (!id) {
    return;
  }
  const trimmedLabel =
    (label ?? formatSessionLabel(id)).trim().slice(0, 40) || formatSessionLabel(id);
  const now = Date.now();
  const others = listRecentSessions().filter((item) => item.id !== id);
  const entry: RecentSession = { id, label: trimmedLabel, updatedAt: now };
  const next = [entry, ...others].slice(0, MAX_RECENT);
  localStorage.setItem(recentKey(), JSON.stringify(next));
}

export function rememberSessionIfHasContent(
  sessionId: string,
  messages: ChatMessage[],
  label?: string,
): void {
  if (sessionHasContent(messages)) {
    rememberSession(sessionId, label);
    return;
  }
  removeRecentSession(sessionId);
}

/** 清理历史上误写入的占位「新会话」条目。 */
export function prunePlaceholderSessions(): void {
  const current = listRecentSessions();
  const next = current.filter((item) => item.label !== PLACEHOLDER_LABEL);
  if (next.length !== current.length) {
    localStorage.setItem(recentKey(), JSON.stringify(next));
  }
}

/** 新会话：仅当旧会话有内容时才写入最近列表，新 id 不预登记。 */
export function startNewTabSession(
  previousId: string,
  previousMessages: ChatMessage[],
  previousLabel?: string,
): string {
  rememberSessionIfHasContent(previousId, previousMessages, previousLabel);
  const created = generateSessionId();
  sessionStorage.setItem(STORAGE_KEY, created);
  return created;
}

export function removeRecentSession(sessionId: string): void {
  const id = sessionId.trim();
  const next = listRecentSessions().filter((item) => item.id !== id);
  localStorage.setItem(recentKey(), JSON.stringify(next));
}

export function clearAllRecentSessions(): void {
  localStorage.removeItem(recentKey());
}
