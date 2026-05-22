import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import {
  clearSession,
  getSession,
  indexAttachmentToKnowledge,
  streamChat,
  uploadAttachments,
} from "./api/client";
import type {
  ChatMessage,
  ChatResponse,
  IntentType,
  TaskPlan,
  ToolResult,
  User,
} from "./api/types";
import { DEFAULT_OPTIONS } from "./api/types";
import { AuthGate } from "./components/AuthGate";
import { ChatTimeline } from "./components/ChatTimeline";
import { Composer } from "./components/Composer";
import { PlanPanel } from "./components/PlanPanel";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { Sidebar } from "./components/Sidebar";
import { ToolResultPanel } from "./components/ToolResultPanel";
import { useConfirm } from "./hooks/useConfirm";
import { ApiError } from "./utils/apiError";
import type { RecentSession } from "./utils/sessionId";
import {
  buildPreviewMap,
  revokePreviewMap,
} from "./utils/attachmentDisplay";
import { intentFromActiveTool, intentFromToolResult } from "./utils/inferIntent";
import { getUseKnowledgeBase, setUseKnowledgeBase as persistKnowledgeMode } from "./utils/knowledgeMode";
import {
  clearAllRecentSessions,
  clearTabSessionId,
  clearUserRecentSessions,
  formatSessionLabel,
  getOrCreateTabSessionId,
  listRecentSessions,
  prunePlaceholderSessions,
  rememberSessionIfHasContent,
  removeRecentSession,
  setTabSessionId,
  startNewTabSession,
} from "./utils/sessionId";

function revokeMessagePreviews(messages: ChatMessage[]) {
  for (const message of messages) {
    revokePreviewMap(message.attachment_previews);
  }
}

function previewFromMessages(messages: ChatMessage[]): string | undefined {
  const firstUser = messages.find((message) => message.role === "user");
  if (!firstUser?.content.trim()) {
    return undefined;
  }
  const text = firstUser.content.trim();
  return text.length > 32 ? `${text.slice(0, 32)}…` : text;
}

type AppContentProps = {
  user: User;
  onLogout: () => void;
};

function AppContent({ user, onLogout }: AppContentProps) {
  const { confirm, dialogProps: confirmDialogProps } = useConfirm();
  const [sessionId, setSessionId] = useState(getOrCreateTabSessionId);
  const [recentSessions, setRecentSessions] = useState<RecentSession[]>(() => listRecentSessions());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [knowledgeIndexNotice, setKnowledgeIndexNotice] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [intent, setIntent] = useState<IntentType | null>(null);
  const [reactStep, setReactStep] = useState<{ step: number; maxSteps: number } | null>(null);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [toolResult, setToolResult] = useState<ToolResult | null>(null);
  const [stepLimitReached, setStepLimitReached] = useState(false);
  const [activePlan, setActivePlan] = useState<TaskPlan | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<File[]>([]);
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(getUseKnowledgeBase);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const initialHistoryLoaded = useRef(false);

  const handleApiError = useCallback(
    (err: unknown, fallback: string): string => {
      if (err instanceof ApiError && err.status === 401) {
        onLogout();
        return err.message;
      }
      return err instanceof Error ? err.message : fallback;
    },
    [onLogout],
  );

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = scrollRef.current;
    if (!container) {
      return;
    }
    container.scrollTo({ top: container.scrollHeight, behavior });
  }, []);

  const pendingStatus = (() => {
    if (!isSending || streamingText) {
      return null;
    }
    if (activeTool === "knowledge") {
      return "正在检索知识库…";
    }
    if (activeTool === "search") {
      return "正在搜索…";
    }
    if (activeTool === "fetch") {
      return "正在抓取网页…";
    }
    if (activeTool === "image") {
      return "正在生成图片…";
    }
    if (activeTool === "video") {
      return "正在生成视频…";
    }
    if (activeTool === "calc") {
      return "正在计算…";
    }
    if (activeTool === "code") {
      return "正在运行代码…";
    }
    if (activeTool === "document") {
      return "正在解析文档…";
    }
    if (activeTool === "vision") {
      return "正在识图…";
    }
    if (stepLimitReached) {
      return "已达步骤上限，正在汇总…";
    }
    if (reactStep) {
      return `ReAct 步骤 ${reactStep.step}…`;
    }
    return "正在思考…";
  })();

  useEffect(() => {
    const behavior: ScrollBehavior =
      streamingText || pendingStatus ? "auto" : "smooth";
    const frame = window.requestAnimationFrame(() => {
      scrollToBottom(behavior);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, streamingText, pendingStatus, toolResult, stepLimitReached, scrollToBottom]);

  useEffect(() => {
    prunePlaceholderSessions();
    setRecentSessions(listRecentSessions());
  }, []);

  const refreshRecentSessions = useCallback(() => {
    setRecentSessions(listRecentSessions());
  }, []);

  const loadSessionHistory = useCallback(
    async (targetSessionId: string, options?: { clearOnStart?: boolean }) => {
      setIsLoadingHistory(true);
      setHistoryError(null);
      if (options?.clearOnStart) {
        setMessages([]);
      }
      try {
        const history = await getSession(targetSessionId);
        setMessages(history.messages);
        rememberSessionIfHasContent(
          targetSessionId,
          history.messages,
          previewFromMessages(history.messages) ?? formatSessionLabel(targetSessionId),
        );
        refreshRecentSessions();
        const lastToolResult = [...history.messages]
          .reverse()
          .find((message) => message.role === "assistant" && message.tool_result)?.tool_result;
        setToolResult(lastToolResult ?? null);
      } catch (err) {
        const message = handleApiError(err, "加载会话失败");
        if (!(err instanceof ApiError && err.status === 401)) {
          setHistoryError(message);
        }
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [handleApiError, refreshRecentSessions],
  );

  useEffect(() => {
    if (initialHistoryLoaded.current) {
      return;
    }
    initialHistoryLoaded.current = true;
    void loadSessionHistory(sessionId);
  }, [sessionId, loadSessionHistory]);

  const applyResponse = useCallback(
    (response: ChatResponse) => {
      setIntent(response.intent);
      const persistedToolResult = response.tool_result ?? null;
      setToolResult(persistedToolResult);
      if (response.plan) {
        setActivePlan(response.plan);
      }
      setMessages((prev) => {
        const next = [
          ...prev,
          {
            role: "assistant" as const,
            content: response.answer,
            tool_result: persistedToolResult,
            steps: response.steps ?? [],
            plan: response.plan ?? undefined,
          },
        ];
        rememberSessionIfHasContent(
          sessionId,
          next,
          previewFromMessages(next),
        );
        refreshRecentSessions();
        return next;
      });
    },
    [sessionId, refreshRecentSessions],
  );

  const handleSend = async () => {
    const trimmed = input.trim();
    const hasAttachments = pendingAttachments.length > 0;
    if ((!trimmed && !hasAttachments) || isSending) {
      return;
    }
    const messageText = trimmed || "请分析我上传的附件。";

    setIsSending(true);
    setStreamingText("");
    setHistoryError(null);
    setKnowledgeIndexNotice(null);
    setIntent(null);
    setReactStep(null);
    setActiveTool(null);
    setToolResult(null);
    setStepLimitReached(false);
    setActivePlan(null);
    const filesToUpload = [...pendingAttachments];
    const userMessage: ChatMessage = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setPendingAttachments([]);

    let attachmentIds: string[] = [];
    if (filesToUpload.length > 0) {
      try {
        const uploaded = await uploadAttachments(sessionId, filesToUpload);
        attachmentIds = uploaded.attachments.map((item) => item.id);
        userMessage.attachments = uploaded.attachments;
        userMessage.attachment_previews = buildPreviewMap(
          filesToUpload,
          uploaded.attachments,
        );
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = userMessage;
          return next;
        });
      } catch (err) {
        const message = handleApiError(err, "附件上传失败");
        if (!(err instanceof ApiError && err.status === 401)) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `抱歉，${message}` },
          ]);
        }
        setIsSending(false);
        return;
      }
    }

    const payload = {
      session_id: sessionId,
      message: messageText,
      options: DEFAULT_OPTIONS,
      attachments: attachmentIds,
      use_knowledge_base: useKnowledgeBase,
    };

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let draft = "";
      let streamError: Error | null = null;
      const response = await streamChat(
        payload,
        (event) => {
          if (event.event === "plan_created") {
            const plan = event.data.plan as TaskPlan | undefined;
            if (plan) {
              setActivePlan(plan);
            }
          } else if (event.event === "step_started") {
            const step = Number(event.data.step ?? 1);
            const maxSteps = Number(event.data.max_steps ?? 6);
            setReactStep({ step, maxSteps });
          } else if (event.event === "tool_started") {
            const tool = String(event.data.tool ?? "tool");
            setActiveTool(tool);
            const inferred = intentFromActiveTool(tool);
            if (inferred) {
              setIntent(inferred);
            }
          } else if (event.event === "tool_result") {
            setActiveTool(null);
            const { run_id: _runId, ...toolPayload } = event.data;
            const result = toolPayload as unknown as ToolResult;
            setToolResult(result);
            const inferred = intentFromToolResult(result);
            if (inferred) {
              setIntent(inferred);
            }
          } else if (event.event === "delta") {
            const text = String(event.data.text ?? "");
            draft += text;
            flushSync(() => setStreamingText(draft));
          } else if (event.event === "step_limit") {
            setStepLimitReached(true);
          } else if (event.event === "error") {
            setActiveTool(null);
            const msg = String(event.data.message ?? event.data.error ?? "生成失败");
            streamError = new Error(msg);
          }
        },
        controller.signal,
      );
      if (streamError) {
        throw streamError;
      }
      setStreamingText("");
      applyResponse(response);
    } catch (err) {
      setStreamingText("");
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "已停止生成。" },
        ]);
        return;
      }
      const message = handleApiError(err, "发送失败");
      if (!(err instanceof ApiError && err.status === 401)) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `抱歉，${message}` },
        ]);
      }
    } finally {
      setIsSending(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleNewSession = () => {
    abortRef.current?.abort();
    revokeMessagePreviews(messages);
    const nextId = startNewTabSession(
      sessionId,
      messages,
      previewFromMessages(messages),
    );
    setSessionId(nextId);
    setMessages([]);
    setStreamingText("");
    setHistoryError(null);
    setIntent(null);
    setReactStep(null);
    setActiveTool(null);
    setToolResult(null);
    setStepLimitReached(false);
    setActivePlan(null);
    setPendingAttachments([]);
    setIsSending(false);
    refreshRecentSessions();
    void loadSessionHistory(nextId);
  };

  const handleSwitchSession = (targetSessionId: string) => {
    if (targetSessionId === sessionId) {
      return;
    }
    abortRef.current?.abort();
    revokeMessagePreviews(messages);
    setTabSessionId(targetSessionId);
    setSessionId(targetSessionId);
    setMessages([]);
    setStreamingText("");
    setHistoryError(null);
    setIntent(null);
    setReactStep(null);
    setActiveTool(null);
    setToolResult(null);
    setStepLimitReached(false);
    setActivePlan(null);
    setPendingAttachments([]);
    setIsSending(false);
    void loadSessionHistory(targetSessionId);
  };

  const resetCurrentChatUi = useCallback(() => {
    setMessages((prev) => {
      revokeMessagePreviews(prev);
      return [];
    });
    setStreamingText("");
    setHistoryError(null);
    setIntent(null);
    setReactStep(null);
    setActiveTool(null);
    setToolResult(null);
    setStepLimitReached(false);
    setActivePlan(null);
    setPendingAttachments([]);
  }, []);

  const handleDeleteSession = async (targetSessionId: string) => {
    const label = formatSessionLabel(targetSessionId);
    const isCurrent = targetSessionId === sessionId;
    const confirmed = await confirm({
      title: isCurrent ? "删除当前会话" : "删除历史会话",
      message: isCurrent
        ? "将永久删除当前会话在服务器上的全部聊天记录。"
        : "将永久删除该会话在服务器上的全部聊天记录。",
      detail: `会话 ${label}`,
      confirmLabel: "删除",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    setIsLoadingHistory(true);
    try {
      await clearSession(targetSessionId);
      removeRecentSession(targetSessionId);
      refreshRecentSessions();

      if (targetSessionId === sessionId) {
        resetCurrentChatUi();
      }
    } catch (err) {
      const message = handleApiError(err, "删除会话失败");
      if (!(err instanceof ApiError && err.status === 401)) {
        setHistoryError(message);
      }
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleDeleteAllSessions = async () => {
    const ids = listRecentSessions().map((item) => item.id);
    if (ids.length === 0) {
      return;
    }
    const confirmed = await confirm({
      title: "删除全部历史会话",
      message: `将永久删除列表中的 ${ids.length} 个会话及其聊天记录。`,
      detail: "此操作不可撤销。",
      confirmLabel: "全部删除",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    setIsLoadingHistory(true);
    const deletingCurrent = ids.includes(sessionId);
    const deletedIds: string[] = [];
    let failed = false;
    try {
      for (const id of ids) {
        try {
          await clearSession(id);
          deletedIds.push(id);
          removeRecentSession(id);
        } catch {
          failed = true;
          break;
        }
      }
      refreshRecentSessions();
      if (deletingCurrent && deletedIds.includes(sessionId)) {
        resetCurrentChatUi();
      }
      if (failed) {
        setHistoryError("部分会话删除失败，列表已同步已删除项。");
      }
    } catch (err) {
      const message = handleApiError(err, "批量删除失败");
      if (!(err instanceof ApiError && err.status === 401)) {
        setHistoryError(message);
      }
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const sidebarBusy = isLoadingHistory;

  return (
    <div className="app-shell">
      <div className="app-shell__backdrop" aria-hidden="true" />
      {confirmDialogProps && <ConfirmDialog {...confirmDialogProps} />}
      <Sidebar
        username={user.username}
        sessionId={sessionId}
        recentSessions={recentSessions}
        onNewSession={handleNewSession}
        onSwitchSession={handleSwitchSession}
        onDeleteSession={(id) => void handleDeleteSession(id)}
        onDeleteAllSessions={() => void handleDeleteAllSessions()}
        onPromptSelect={setInput}
        onLogout={() => {
          abortRef.current?.abort();
          clearTabSessionId();
          clearUserRecentSessions();
          onLogout();
        }}
        disabled={sidebarBusy}
      />

      <main className="workspace">
        <div ref={scrollRef} className="workspace__scroll">
          <PlanPanel plan={activePlan} />
          {historyError && (
            <p className="workspace__error" role="alert">
              {historyError}
            </p>
          )}
          {knowledgeIndexNotice && (
            <p className="workspace__error" role="status">
              {knowledgeIndexNotice}
            </p>
          )}
          <ChatTimeline
            messages={messages}
            streamingText={streamingText}
            pendingStatus={pendingStatus}
            pendingToolResult={toolResult}
            sessionId={sessionId}
            onIndexAttachmentToKnowledge={async (attachmentId) => {
              setKnowledgeIndexNotice(null);
              try {
                await indexAttachmentToKnowledge(sessionId, attachmentId);
                setKnowledgeIndexNotice("已加入知识库，可在侧栏知识库中查看。");
              } catch (err) {
                const message = handleApiError(err, "加入知识库失败");
                if (!(err instanceof ApiError && err.status === 401)) {
                  setKnowledgeIndexNotice(`抱歉，${message}`);
                }
              }
            }}
          />
        </div>
        <Composer
          value={input}
          isSending={isSending}
          pendingAttachments={pendingAttachments}
          useKnowledgeBase={useKnowledgeBase}
          onUseKnowledgeBaseChange={(value) => {
            setUseKnowledgeBase(value);
            persistKnowledgeMode(value);
          }}
          onChange={setInput}
          onAttachmentsChange={setPendingAttachments}
          onSubmit={() => void handleSend()}
          onStop={handleStop}
        />
      </main>

      <ToolResultPanel
        intent={intent}
        reactStep={reactStep}
        activeTool={activeTool}
        toolResult={toolResult}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthGate>
      {(user, onLogout) => <AppContent user={user} onLogout={onLogout} />}
    </AuthGate>
  );
}
