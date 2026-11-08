import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

export function ConfirmDialog({
  title,
  children,
  onClose,
  onConfirm,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="confirm-dialog"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-labelledby="confirm-title"
    >
      <div className="dialog-top">
        <h2 id="confirm-title">{title}</h2>
        <button className="icon-button" aria-label="关闭确认窗口" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="dialog-content">{children}</div>
      <div className="dialog-actions">
        <button className="button" onClick={onClose} autoFocus>
          再想想
        </button>
        <button className="button primary" onClick={onConfirm}>
          确认操作
        </button>
      </div>
    </dialog>
  );
}
