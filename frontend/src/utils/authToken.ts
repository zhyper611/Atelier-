const TOKEN_KEY = "agent_access_token";
const USER_KEY = "agent_user";

export type StoredUser = {
  id: string;
  username: string;
};

export function getAccessToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  return token && token.trim() ? token.trim() : null;
}

export function setAuthSession(token: string, user: StoredUser): void {
  localStorage.setItem(TOKEN_KEY, token.trim());
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as StoredUser;
    if (typeof parsed.id === "string" && typeof parsed.username === "string") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
