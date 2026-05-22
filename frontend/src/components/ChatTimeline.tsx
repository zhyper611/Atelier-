import { useState } from "react";

import type { AgentStepSummary, ChatMessage, KnowledgeCitation, ToolResult } from "../api/types";
import { CitationFooter } from "./CitationFooter";
import { MediaPreview } from "./MediaPreview";
import { MessageAttachments } from "./MessageAttachments";
import { MessageContent } from "./MessageContent";

type ChatTimelineProps = {
  messages: ChatMessage[];
  streamingText?: string;
  pendingStatus?: string | null;
  pendingToolResult?: ToolResult | null;
  sessionId?: string;
  messageKey?: (message: ChatMessage, index: number) => string;
  onIndexAttachmentToKnowledge?: (attachmentId: string) => Promise<void>;
};

const toolNameLabels: Record<string, string> = {
  web_search: "联网搜索",
  fetch_url: "网页阅读",
  generate_image: "文生图",
  generate_video: "文生视频",
  calculator: "计算器",
  parse_document: "文档解析",
  analyze_image: "识图",
  search_knowledge: "知识库检索",
};

function knowledgeCitationsFromToolResult(
  toolResult: ToolResult | null | undefined,
): KnowledgeCitation[] {
  if (!toolResult || toolResult.type !== "knowledge") {
    return [];
  }
  const raw = toolResult.metadata?.citations;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw as KnowledgeCitation[];
}

function RunSteps({ steps }: { steps: AgentStepSummary[] }) {
  const [open, setOpen] = useState(false);

  if (!steps.length) {
    return null;
  }

  return (
    <details
      className="run-steps"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>本回合工具调用 ({steps.length} 步)</summary>
      <ol className="run-steps__list">
        {steps.map((step) => (
          <li key={`${step.step}-${step.tool_name ?? "step"}`}>
            <span className="run-steps__name">
              {toolNameLabels[step.tool_name ?? ""] ?? step.tool_name ?? "工具"}
            </span>
            {step.observation_preview && (
              <p className="run-steps__preview">{step.observation_preview}</p>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

function defaultMessageKey(message: ChatMessage, index: number): string {
  const attachLen = message.attachments?.length ?? 0;
  const previewLen = message.attachment_previews
    ? Object.keys(message.attachment_previews).length
    : 0;
  return `${index}-${message.role}-${attachLen}-${previewLen}-${message.content.length}`;
}

export function ChatTimeline({
  messages,
  streamingText,
  pendingStatus,
  pendingToolResult,
  messageKey = defaultMessageKey,
  onIndexAttachmentToKnowledge,
}: ChatTimelineProps) {
  const hasStreaming = Boolean(streamingText);
  const showThinking = Boolean(pendingStatus) && !hasStreaming;

  return (
    <div className="chat-timeline" role="log" aria-live="polite">
      {messages.length === 0 && !hasStreaming && !showThinking && (
        <div className="chat-timeline__empty">
          <p className="chat-timeline__eyebrow">Studio Console</p>
          <h2>开始与智能体对话</h2>
          <p>支持对话、联网搜索、计算、代码、文档解析、识图、文生图与文生视频。可上传附件。</p>
        </div>
      )}

      {messages.map((message, index) => {
        if (message.role === "tool") {
          return null;
        }

        return (
          <article
            key={messageKey(message, index)}
            className={`message message--${message.role}`}
          >
            <header className="message__meta">
              <span>{message.role === "user" ? "你" : "助手"}</span>
            </header>
            <div className="message__body">
              {message.role === "user" &&
                message.attachments &&
                message.attachments.length > 0 && (
                  <MessageAttachments
                    attachments={message.attachments}
                    previews={message.attachment_previews}
                    onAddToKnowledge={
                      onIndexAttachmentToKnowledge
                        ? (id) => onIndexAttachmentToKnowledge(id)
                        : undefined
                    }
                  />
                )}
              <MessageContent
                content={message.content}
                markdown={message.role === "assistant"}
                suppressMarkdownImages={
                  message.role === "assistant" &&
                  (message.tool_result?.type === "image" || message.tool_result?.type === "video")
                }
              />
              {message.role === "assistant" && message.plan && (
                <details className="run-steps message__plan">
                  <summary>任务计划：{message.plan.goal}</summary>
                  <ol className="run-steps__list">
                    {message.plan.steps.map((step) => (
                      <li key={step.id}>
                        <span className="run-steps__name">{step.title}</span>
                        {step.description && (
                          <p className="run-steps__preview">{step.description}</p>
                        )}
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              {message.role === "assistant" && message.steps && message.steps.length > 0 && (
                <RunSteps steps={message.steps} />
              )}
              {message.role === "assistant" && message.tool_result && (
                <MediaPreview toolResult={message.tool_result} />
              )}
              {message.role === "assistant" &&
                knowledgeCitationsFromToolResult(message.tool_result).length > 0 && (
                  <CitationFooter
                    answer={message.content}
                    citations={knowledgeCitationsFromToolResult(message.tool_result)}
                  />
                )}
            </div>
          </article>
        );
      })}

      {showThinking && (
        <article className="message message--assistant message--thinking" aria-busy="true">
          <header className="message__meta">
            <span>助手</span>
            <span className="message__pulse">{pendingStatus}</span>
          </header>
          <div className="message__body message__body--thinking">
            <span className="thinking-dots" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </div>
        </article>
      )}

      {hasStreaming && (
        <article className="message message--assistant message--streaming">
          <header className="message__meta">
            <span>助手</span>
          </header>
          <div className="message__body">
            <MessageContent
              content={streamingText ?? ""}
              markdown
              suppressMarkdownImages={
                pendingToolResult?.type === "image" || pendingToolResult?.type === "video"
              }
            />
            {pendingToolResult &&
              (pendingToolResult.type === "image" || pendingToolResult.type === "video") && (
                <MediaPreview toolResult={pendingToolResult} />
              )}
            {knowledgeCitationsFromToolResult(pendingToolResult).length > 0 && (
              <CitationFooter
                answer={streamingText ?? ""}
                citations={knowledgeCitationsFromToolResult(pendingToolResult)}
              />
            )}
          </div>
        </article>
      )}
    </div>
  );
}
