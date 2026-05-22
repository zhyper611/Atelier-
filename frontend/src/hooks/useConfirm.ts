import { useCallback, useState } from "react";

import type { ConfirmDialogProps } from "../components/ConfirmDialog";

type ConfirmOptions = {
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
};

type ConfirmState = ConfirmOptions & {
  open: boolean;
  resolve: (value: boolean) => void;
};

export function useConfirm() {
  const [state, setState] = useState<ConfirmState | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setState({
        ...options,
        open: true,
        resolve,
      });
    });
  }, []);

  const close = useCallback((result: boolean) => {
    setState((current) => {
      if (current) {
        current.resolve(result);
      }
      return null;
    });
  }, []);

  const dialogProps: ConfirmDialogProps | null = state
    ? {
        open: state.open,
        title: state.title,
        message: state.message,
        detail: state.detail,
        confirmLabel: state.confirmLabel,
        cancelLabel: state.cancelLabel,
        variant: state.variant,
        onConfirm: () => close(true),
        onCancel: () => close(false),
      }
    : null;

  return { confirm, dialogProps };
}
