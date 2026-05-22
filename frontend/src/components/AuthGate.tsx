import {
  useCallback,
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import { getMe, login, register } from "../api/client";
import { AuthAlert } from "./AuthAlert";
import { ApiError } from "../utils/apiError";
import type { User } from "../api/types";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  setAuthSession,
  type StoredUser,
} from "../utils/authToken";
import { setAuthUserId } from "../utils/sessionId";

type AuthGateProps = {
  children: (user: User, onLogout: () => void) => ReactNode;
};

type AuthMode = "login" | "register";

export function AuthGate({ children }: AuthGateProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  /** Edge/Chrome 会在加载时注入密码；聚焦前只读可阻断，配合诱饵字段 */
  const [inputsReady, setInputsReady] = useState(false);
  const formInstanceId = useId().replace(/:/g, "");

  const applyUser = useCallback((next: StoredUser) => {
    setAuthUserId(next.id);
    setUser({
      id: next.id,
      username: next.username,
    });
  }, []);

  const handleLogout = useCallback(() => {
    clearAuthSession();
    setAuthUserId(null);
    setUser(null);
    setUsername("");
    setPassword("");
    setConfirmPassword("");
    setError(null);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const token = getAccessToken();
      const stored = getStoredUser();
      if (!token || !stored) {
        if (!cancelled) {
          setAuthUserId(null);
          setLoading(false);
        }
        return;
      }

      try {
        const me = await getMe();
        if (!cancelled) {
          setAuthSession(token, { id: me.id, username: me.username });
          applyUser({ id: me.id, username: me.username });
        }
      } catch {
        clearAuthSession();
        if (!cancelled) {
          setAuthUserId(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [applyUser]);

  const resetAuthFields = useCallback(() => {
    setUsername("");
    setPassword("");
    setConfirmPassword("");
    setInputsReady(false);
  }, []);

  useEffect(() => {
    if (!user && !loading) {
      resetAuthFields();
      // Edge 常在首屏渲染后再注入已保存密码，延迟清空一次
      const timer = window.setTimeout(() => {
        resetAuthFields();
      }, 150);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [user, loading, mode, resetAuthFields]);

  const handleInputFocus = () => {
    setInputsReady(true);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    const trimmedUsername = username.trim();
    if (trimmedUsername.length < 3) {
      setError("用户名至少 3 个字符");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 个字符");
      return;
    }
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setSubmitting(true);
    try {
      const response =
        mode === "register"
          ? await register(trimmedUsername, password)
          : await login(trimmedUsername, password);
      setAuthSession(response.access_token, {
        id: response.user.id,
        username: response.user.username,
      });
      applyUser({
        id: response.user.id,
        username: response.user.username,
      });
      setPassword("");
      setConfirmPassword("");
    } catch (exc) {
      if (exc instanceof ApiError) {
        setError(exc.message);
      } else if (exc instanceof TypeError) {
        setError("无法连接服务器，请确认后端已启动");
      } else {
        setError("操作失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="auth-screen">
        <p className="auth-screen__hint">正在验证登录状态…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <p className="auth-card__eyebrow">FastAPI AI Agent</p>
          <h1 className="auth-card__title">Atelier</h1>
          <p className="auth-card__subtitle">登录或注册以使用多模态智能体</p>

          <div className="auth-card__tabs">
            <button
              type="button"
              className={mode === "login" ? "auth-card__tab auth-card__tab--active" : "auth-card__tab"}
              onClick={() => {
                setMode("login");
                setError(null);
                resetAuthFields();
              }}
            >
              登录
            </button>
            <button
              type="button"
              className={
                mode === "register" ? "auth-card__tab auth-card__tab--active" : "auth-card__tab"
              }
              onClick={() => {
                setMode("register");
                setError(null);
                resetAuthFields();
              }}
            >
              注册
            </button>
          </div>

          <form
            className="auth-form"
            onSubmit={handleSubmit}
            autoComplete="off"
            data-form-type="other"
          >
            {/* 诱饵：Edge 常把已保存账号填进这里，而非下方真实输入框 */}
            <div className="auth-form__trap" aria-hidden="true">
              <input
                tabIndex={-1}
                type="text"
                name="username"
                autoComplete="username"
                defaultValue=""
              />
              <input
                tabIndex={-1}
                type="password"
                name="password"
                autoComplete="current-password"
                defaultValue=""
              />
            </div>

            <label className="auth-form__field">
              <span>用户名</span>
              <input
                id={`${formInstanceId}-user`}
                type="text"
                name={`field-${formInstanceId}-user`}
                autoComplete="one-time-code"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                readOnly={!inputsReady}
                data-lpignore="true"
                data-1p-ignore="true"
                data-ms-editor="false"
                value={username}
                onFocus={handleInputFocus}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="3–32 个字符，字母数字与 _ -"
                disabled={submitting}
              />
            </label>
            <label className="auth-form__field">
              <span>密码</span>
              <input
                id={`${formInstanceId}-pass`}
                type={inputsReady ? "password" : "text"}
                className={inputsReady ? undefined : "auth-form__secret"}
                name={`field-${formInstanceId}-pass`}
                autoComplete="new-password"
                readOnly={!inputsReady}
                data-lpignore="true"
                data-1p-ignore="true"
                data-ms-editor="false"
                value={password}
                onFocus={handleInputFocus}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 8 个字符"
                disabled={submitting}
              />
            </label>
            {mode === "register" && (
              <label className="auth-form__field">
                <span>确认密码</span>
                <input
                  id={`${formInstanceId}-pass2`}
                  type={inputsReady ? "password" : "text"}
                  className={inputsReady ? undefined : "auth-form__secret"}
                  name={`field-${formInstanceId}-pass2`}
                  autoComplete="new-password"
                  readOnly={!inputsReady}
                  data-lpignore="true"
                  data-1p-ignore="true"
                  data-ms-editor="false"
                  value={confirmPassword}
                  onFocus={handleInputFocus}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  disabled={submitting}
                />
              </label>
            )}
            {error && <AuthAlert message={error} />}
            <button type="submit" className="auth-form__submit" disabled={submitting}>
              {submitting ? "处理中…" : mode === "login" ? "登录" : "注册"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return <>{children(user, handleLogout)}</>;
}
