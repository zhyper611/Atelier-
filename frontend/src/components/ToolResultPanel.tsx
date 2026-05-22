import { useState } from "react";

import type { IntentType, KnowledgeCitation, ToolResult } from "../api/types";

type ToolResultPanelProps = {
  intent: IntentType | null;
  reactStep: { step: number; maxSteps: number } | null;
  activeTool: string | null;
  toolResult: ToolResult | null;
};

const intentLabels: Record<IntentType, string> = {
  chat: "对话",
  search: "联网搜索",
  image: "文生图",
  video: "文生视频",
};

const toolLabels: Record<string, string> = {
  search: "联网搜索",
  fetch: "网页阅读",
  image: "文生图",
  video: "文生视频",
  calc: "计算器",
  code: "代码运行",
  document: "文档解析",
  vision: "识图",
  calculation: "计算器",
  analysis: "识图",
  knowledge: "知识库",
};

function toolStatusLabel(activeTool: string | null, toolResult: ToolResult | null, intent: IntentType | null) {
  if (activeTool) {
    return {
      tone: "active" as const,
      text: `正在运行：${toolLabels[activeTool] ?? activeTool}`,
    };
  }
  if (toolResult) {
    return {
      tone: "done" as const,
      text: `已完成：${toolLabels[toolResult.type] ?? toolResult.type}`,
    };
  }
  if (intent && intent !== "chat") {
    return {
      tone: "muted" as const,
      text: `等待执行：${intentLabels[intent]}`,
    };
  }
  if (intent === "chat") {
    return {
      tone: "muted" as const,
      text: "本次为对话，未调用工具",
    };
  }
  return {
    tone: "muted" as const,
    text: "等待下一条消息…",
  };
}

function KnowledgeCitationsList({ citations }: { citations: KnowledgeCitation[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  return (
    <ul className="tool-panel__citations">
      {citations.map((citation) => (
        <li key={`${citation.doc_id}-${citation.chunk_index}`}>
          <button
            type="button"
            className="tool-panel__citation-head"
            onClick={() =>
              setExpanded((prev) =>
                prev === citation.index ? null : citation.index,
              )
            }
          >
            <span className="tool-panel__citation-index">[{citation.index}]</span>
            <span>{citation.filename}</span>
            {citation.score != null && (
              <span className="tool-panel__citation-score">
                {citation.score.toFixed(3)}
              </span>
            )}
          </button>
          {expanded === citation.index && (
            <p className="tool-panel__citation-excerpt">{citation.excerpt}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

export function ToolResultPanel({
  intent,
  reactStep,
  activeTool,
  toolResult,
}: ToolResultPanelProps) {
  return (
    <aside className="tool-panel">
      <header className="tool-panel__header">
        <p className="tool-panel__eyebrow">Runtime</p>
        <h2>执行轨迹</h2>
      </header>

      <div className="tool-panel__scroll">
      <section className="tool-panel__section">
        <h3>ReAct 循环</h3>
        {reactStep || intent ? (
          <div className="tool-panel__card tool-panel__card--react">
            {reactStep && (
              <div className="react-status__step">
                <div className="react-status__step-head">
                  <span className="react-status__step-label">循环次数</span>
                  <span className="react-status__step-count" aria-label={`第 ${reactStep.step} 步`}>
                    {reactStep.step}
                  </span>
                </div>
              </div>
            )}
            {intent && (
              <div
                className={`react-status__intent${reactStep ? " react-status__intent--bordered" : ""}`}
              >
                <span className="react-status__intent-label">识别意图</span>
                <span className="intent-pill">{intentLabels[intent]}</span>
              </div>
            )}
          </div>
        ) : (
          <p className="tool-panel__muted">等待下一条消息…</p>
        )}
      </section>

      <section className="tool-panel__section">
        <h3>工具状态</h3>
        {(() => {
          const status = toolStatusLabel(activeTool, toolResult, intent);
          return (
            <p
              className={
                status.tone === "active"
                  ? "tool-panel__active"
                  : status.tone === "done"
                    ? "tool-panel__done"
                    : "tool-panel__muted"
              }
            >
              {status.text}
            </p>
          );
        })()}
      </section>

      {toolResult && (
        <section className="tool-panel__section">
          <h3>工具结果</h3>
          <div className="tool-panel__card tool-panel__card--result">
            {toolResult.type === "search" && (
              <>
                <p>{toolResult.content}</p>
                {Array.isArray(toolResult.metadata?.sources) && (
                  <ul>
                    {(toolResult.metadata.sources as string[]).map((source) => (
                      <li key={source}>
                        <a href={source} target="_blank" rel="noreferrer">
                          {source}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            {toolResult.type === "knowledge" && (
              <>
                {toolResult.content && <p>{toolResult.content}</p>}
                {Array.isArray(toolResult.metadata?.citations) && (
                  <KnowledgeCitationsList
                    citations={toolResult.metadata.citations as KnowledgeCitation[]}
                  />
                )}
              </>
            )}
            {toolResult.type === "fetch" && (
              <>
                {toolResult.content && (
                  <pre className="tool-panel__pre">{toolResult.content}</pre>
                )}
                {Array.isArray(toolResult.metadata?.urls) && (
                  <ul>
                    {(toolResult.metadata.urls as string[]).map((source) => (
                      <li key={source}>
                        <a href={source} target="_blank" rel="noreferrer">
                          {source}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            {(toolResult.type === "calculation" ||
              toolResult.type === "code" ||
              toolResult.type === "document" ||
              toolResult.type === "analysis") &&
              toolResult.content && (
              <pre className="tool-panel__pre">{toolResult.content}</pre>
            )}
            {(toolResult.type === "image" || toolResult.type === "video") &&
              toolResult.url &&
              (toolResult.url.startsWith("http") || toolResult.url.startsWith("data:")) && (
              <div className="tool-panel__media">
                {toolResult.type === "image" ? (
                  <img src={toolResult.url} alt="生成的图片" />
                ) : (
                  <video src={toolResult.url.split("#")[0]} controls />
                )}
                {!toolResult.url.startsWith("data:") && (
                  <a href={toolResult.url.split("#")[0]} target="_blank" rel="noreferrer">
                    打开资源
                  </a>
                )}
              </div>
            )}
          </div>
        </section>
      )}
      </div>
    </aside>
  );
}
