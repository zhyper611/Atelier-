import type { RecentSession } from "../utils/sessionId";
import { KnowledgePanel } from "./KnowledgePanel";

type SidebarProps = {
  username: string;
  sessionId: string;
  recentSessions: RecentSession[];
  onNewSession: () => void;
  onSwitchSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onDeleteAllSessions: () => void;
  onPromptSelect: (prompt: string) => void;
  onLogout: () => void;
  disabled?: boolean;
};

const examplePrompts = [
  "你好，帮我想一个周末计划",
  "今天有什么 AI 新闻？",
  "帮我生成一张 16:9 的赛博朋克城市图片",
  "生成一段 5 秒的日落海边视频",
];

export function Sidebar({
  username,
  sessionId,
  recentSessions,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onDeleteAllSessions,
  onPromptSelect,
  onLogout,
  disabled,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar__scroll">
      <div className="sidebar__brand">
        <p className="sidebar__eyebrow">FastAPI AI Agent</p>
        <h1>Atelier</h1>
        <p className="sidebar__tagline">高级暗色控制台 · 多模态智能体</p>
      </div>

      <div className="sidebar__user">
        <span className="sidebar__user-name" title={username}>
          {username}
        </span>
        <button type="button" className="sidebar__logout" onClick={onLogout} disabled={disabled}>
          退出登录
        </button>
      </div>

      <div className="sidebar__actions">
        <button
          type="button"
          className="sidebar__new-session"
          onClick={onNewSession}
          disabled={disabled}
        >
          新会话
        </button>
      </div>

      <section className="sidebar__recent">
        <div className="sidebar__recent-header">
          <h2>历史会话</h2>
          {recentSessions.length > 0 && (
            <button
              type="button"
              className="sidebar__delete-all"
              onClick={onDeleteAllSessions}
              disabled={disabled}
            >
              全部删除
            </button>
          )}
        </div>
        {recentSessions.length > 0 ? (
          <ul>
            {recentSessions.map((item) => {
              const isCurrent = item.id === sessionId;
              return (
                <li key={item.id} className="sidebar__recent-row">
                  <button
                    type="button"
                    className={`sidebar__recent-item${isCurrent ? " sidebar__recent-item--current" : ""}`}
                    title={item.label}
                    onClick={() => onSwitchSession(item.id)}
                    disabled={disabled}
                  >
                    <span className="sidebar__recent-label">
                      {item.label}
                      {isCurrent ? "（当前）" : ""}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="sidebar__recent-delete"
                    title="删除此会话"
                    aria-label={`删除会话 ${item.label}`}
                    onClick={() => onDeleteSession(item.id)}
                    disabled={disabled}
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="sidebar__recent-empty">暂无已保存的历史会话</p>
        )}
      </section>

      <KnowledgePanel disabled={disabled} />

      <section className="sidebar__prompts">
        <h2>示例指令</h2>
        <ul>
          {examplePrompts.map((prompt) => (
            <li key={prompt}>
              <button type="button" onClick={() => onPromptSelect(prompt)} disabled={disabled}>
                {prompt}
              </button>
            </li>
          ))}
        </ul>
      </section>
      </div>
    </aside>
  );
}
