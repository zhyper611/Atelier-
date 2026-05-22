import { useCallback, useEffect, useRef, useState } from "react";

import {
  deleteKnowledgeDocument,
  listKnowledgeDocuments,
  uploadKnowledgeDocuments,
} from "../api/client";
import type { KnowledgeDocument } from "../api/types";
import { useConfirm } from "../hooks/useConfirm";
import { ConfirmDialog } from "./ConfirmDialog";

const DOCUMENT_ACCEPT =
  ".pdf,.txt,.md,application/pdf,text/plain,text/markdown";

type KnowledgePanelProps = {
  disabled?: boolean;
};

export function KnowledgePanel({ disabled }: KnowledgePanelProps) {
  const { confirm, dialogProps: confirmDialogProps } = useConfirm();
  const [open, setOpen] = useState(false);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listKnowledgeDocuments();
      setDocuments(res.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载知识库失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) {
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await uploadKnowledgeDocuments(Array.from(files));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    const confirmed = await confirm({
      title: "删除知识库文档",
      message: "将从知识库中永久移除此文档及其向量索引。",
      detail: filename,
      confirmLabel: "删除",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }
    setError(null);
    try {
      await deleteKnowledgeDocument(docId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <section className="sidebar__knowledge">
      {confirmDialogProps && <ConfirmDialog {...confirmDialogProps} />}
      <button
        type="button"
        className="sidebar__knowledge-toggle"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        aria-expanded={open}
      >
        知识库 {documents.length > 0 ? `(${documents.length})` : ""}
      </button>
      {open && (
        <div className="knowledge-panel">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={DOCUMENT_ACCEPT}
            className="knowledge-panel__file-input"
            onChange={(e) => void handleUpload(e.target.files)}
            disabled={disabled || uploading}
          />
          <button
            type="button"
            className="knowledge-panel__upload"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
          >
            {uploading ? "索引中…" : "上传文档"}
          </button>
          {error && (
            <p className="knowledge-panel__error" role="alert">
              {error}
            </p>
          )}
          {loading && <p className="knowledge-panel__muted">加载中…</p>}
          {!loading && documents.length === 0 && (
            <p className="knowledge-panel__muted">暂无文档</p>
          )}
          <ul className="knowledge-panel__list">
            {documents.map((doc) => (
              <li key={doc.doc_id} className="knowledge-panel__item">
                <span className="knowledge-panel__filename" title={doc.filename}>
                  {doc.filename}
                </span>
                <button
                  type="button"
                  className="knowledge-panel__delete"
                  onClick={() => void handleDelete(doc.doc_id, doc.filename)}
                  disabled={disabled}
                  aria-label={`删除 ${doc.filename}`}
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
