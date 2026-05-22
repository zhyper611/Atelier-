import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { normalizeAssistantMarkdown } from "../utils/markdownNormalize";

type MessageContentProps = {
  content: string;
  markdown?: boolean;
  /** 已有 tool_result 预览图时，避免 Markdown 再渲染新闻缩略图等外链图片 */
  suppressMarkdownImages?: boolean;
};

export function MessageContent({
  content,
  markdown = false,
  suppressMarkdownImages = false,
}: MessageContentProps) {
  if (!markdown) {
    return <div className="message__text">{content}</div>;
  }

  const normalized = normalizeAssistantMarkdown(content);

  return (
    <div className="message__markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          img: suppressMarkdownImages
            ? () => null
            : undefined,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
          pre: ({ children }) => <pre className="message__code-block">{children}</pre>,
          code: ({ className, children, ...props }) => {
            if (className) {
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className="message__code-inline" {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
