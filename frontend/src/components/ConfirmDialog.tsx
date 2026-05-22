import { useEffect, useRef } from "react";

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  detail,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    confirmRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onCancel]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="confirm-overlay"
      role="presentation"
      onClick={onCancel}
    >
      <div
        className={`confirm-dialog confirm-dialog--${variant}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-desc"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog__icon" aria-hidden="true">
          {variant === "danger" ? "!" : "?"}
        </div>
        <p className="confirm-dialog__eyebrow">确认操作</p>
        <h2 id="confirm-dialog-title" className="confirm-dialog__title">
          {title}
        </h2>
        <p id="confirm-dialog-desc" className="confirm-dialog__message">
          {message}
        </p>
        {detail && <p className="confirm-dialog__detail">{detail}</p>}
        <div className="confirm-dialog__actions">
          <button type="button" className="button--ghost confirm-dialog__cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`confirm-dialog__confirm confirm-dialog__confirm--${variant}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
