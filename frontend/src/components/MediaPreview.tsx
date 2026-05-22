import type { ToolResult } from "../api/types";

type MediaPreviewProps = {
  toolResult: ToolResult | null;
};

function isPreviewableUrl(url: string): boolean {
  return url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:");
}

export function MediaPreview({ toolResult }: MediaPreviewProps) {
  if (!toolResult?.url || !isPreviewableUrl(toolResult.url)) {
    return null;
  }

  const size = typeof toolResult.metadata?.size === "string" ? toolResult.metadata.size : null;

  return (
    <section className="media-preview" aria-label="生成结果预览">
      {toolResult.type === "image" ? (
        <img src={toolResult.url} alt="生成的图片" className="media-preview__image" />
      ) : (
        <video src={toolResult.url} controls className="media-preview__video" />
      )}
      <div className="media-preview__meta">
        {size && <span>{size}</span>}
        {toolResult.url.startsWith("data:") ? (
          <span>模拟预览图（接入真实 API 后将返回真实资源）</span>
        ) : (
          <a href={toolResult.url} target="_blank" rel="noreferrer">
            打开资源
          </a>
        )}
      </div>
    </section>
  );
}
