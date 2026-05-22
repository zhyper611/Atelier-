import { useRef, type KeyboardEvent } from "react";

import type { AttachmentRef } from "../api/types";
import { attachmentDisplayInfo } from "../utils/attachmentDisplay";
import { KnowledgeModeToggle } from "./KnowledgeModeToggle";

type ComposerProps = {
  value: string;
  isSending: boolean;
  pendingAttachments: File[];
  useKnowledgeBase: boolean;
  onUseKnowledgeBaseChange: (value: boolean) => void;
  onChange: (value: string) => void;
  onAttachmentsChange: (files: File[]) => void;
  onSubmit: () => void;
  onStop?: () => void;
};

export function Composer({
  value,
  isSending,
  pendingAttachments,
  useKnowledgeBase,
  onUseKnowledgeBaseChange,
  onChange,
  onAttachmentsChange,
  onSubmit,
  onStop,
}: ComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && (value.trim() || pendingAttachments.length > 0)) {
        onSubmit();
      }
    }
  };

  const handleFilesSelected = (files: FileList | null) => {
    if (!files?.length) {
      return;
    }
    onAttachmentsChange([...pendingAttachments, ...Array.from(files)]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (index: number) => {
    onAttachmentsChange(pendingAttachments.filter((_, i) => i !== index));
  };

  return (
    <footer className="composer">
      <KnowledgeModeToggle
        useKnowledgeBase={useKnowledgeBase}
        onChange={onUseKnowledgeBaseChange}
        disabled={isSending}
      />
      {pendingAttachments.length > 0 && (
        <div className="composer__attachments">
          {pendingAttachments.map((file, index) => {
            const info = attachmentDisplayInfo(file.type || "application/octet-stream");
            return (
            <span
              key={`${file.name}-${index}`}
              className={`composer__chip composer__chip--${info.kind}`}
            >
              <span className="composer__chip-type">{info.label}</span>
              <span className="composer__chip-name">{file.name}</span>
              <button
                type="button"
                className="composer__chip-remove"
                onClick={() => removeAttachment(index)}
                aria-label={`移除 ${file.name}`}
              >
                ×
              </button>
            </span>
            );
          })}
        </div>
      )}
      <div className="composer__input-row">
        <input
          ref={fileInputRef}
          type="file"
          className="composer__file-input"
          multiple
          accept="image/*,audio/*,video/*,.pdf,.txt,.md,text/plain,text/markdown,application/pdf"
          onChange={(event) => handleFilesSelected(event.target.files)}
        />
        <button
          type="button"
          className="composer__attach"
          onClick={() => fileInputRef.current?.click()}
          title="上传图片或文档"
          aria-label="上传附件"
        >
          <svg
            className="composer__attach-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isSending
              ? "正在生成回复，可先输入下一条消息"
              : useKnowledgeBase
                ? "基于知识库提问，Enter 发送"
                : "输入消息，Enter 发送，Shift+Enter 换行"
          }
          rows={2}
          aria-busy={isSending}
        />
        {isSending && onStop ? (
          <button type="button" className="composer__stop" onClick={onStop}>
            停止
          </button>
        ) : (
          <button
            type="button"
            className="composer__send"
            onClick={onSubmit}
            disabled={isSending || (!value.trim() && pendingAttachments.length === 0)}
          >
            发送
          </button>
        )}
      </div>
    </footer>
  );
}

export function attachmentRefsFromUpload(
  refs: AttachmentRef[],
): string[] {
  return refs.map((ref) => ref.id);
}
