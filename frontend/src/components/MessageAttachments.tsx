import type { AttachmentRef } from "../api/types";
import {
  attachmentDisplayInfo,
  formatAttachmentSize,
} from "../utils/attachmentDisplay";

type MessageAttachmentsProps = {
  attachments: AttachmentRef[];
  previews?: Record<string, string>;
  onAddToKnowledge?: (attachmentId: string) => void | Promise<void>;
};

function isDocumentMime(mime: string) {
  return (
    mime === "application/pdf" ||
    mime === "text/plain" ||
    mime === "text/markdown"
  );
}

export function MessageAttachments({
  attachments,
  previews,
  onAddToKnowledge,
}: MessageAttachmentsProps) {
  if (!attachments.length) {
    return null;
  }

  return (
    <ul className="message-attachments" aria-label="消息附件">
      {attachments.map((item) => {
        const info = attachmentDisplayInfo(item.mime_type);
        const previewUrl = previews?.[item.id];

        return (
          <li
            key={item.id}
            className={`message-attachments__item message-attachments__item--${info.kind}`}
          >
            {previewUrl ? (
              <img
                className="message-attachments__thumb"
                src={previewUrl}
                alt={item.filename}
              />
            ) : (
              <span
                className={`message-attachments__icon message-attachments__icon--${info.kind}`}
                aria-hidden="true"
              >
                {info.shortLabel}
              </span>
            )}
            <div className="message-attachments__meta">
              <span className="message-attachments__type">{info.label}</span>
              <span className="message-attachments__name" title={item.filename}>
                {item.filename}
              </span>
              <span className="message-attachments__size">
                {formatAttachmentSize(item.size_bytes)}
              </span>
              {onAddToKnowledge && isDocumentMime(item.mime_type) && (
                <button
                  type="button"
                  className="message-attachments__kb"
                  onClick={() => void onAddToKnowledge(item.id)}
                >
                  加入知识库
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
