"use client";

import React, { useEffect } from "react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape" && !busy) {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      <div className="modal-box">
        <h2 id="confirm-modal-title">{title}</h2>
        <p className="muted">{description}</p>
        {children}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? "btn danger" : "btn primary"}
            onClick={onConfirm}
            disabled={busy}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
