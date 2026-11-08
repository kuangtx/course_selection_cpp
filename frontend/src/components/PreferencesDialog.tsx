import { useEffect, useRef } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { PreferencesPanel } from './PreferencesPanel';
import type { Catalog, Preferences, Student } from '../types';

export function PreferencesDialog({
  open,
  student,
  catalog,
  disabled,
  busy,
  error,
  onClose,
  onSave,
  onDirty,
}: {
  open: boolean;
  student: Student;
  catalog: Catalog;
  disabled: boolean;
  busy: boolean;
  error?: string;
  onClose: () => void;
  onSave: (preferences: Preferences) => Promise<void>;
  onDirty: (dirty: boolean) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);
  useEffect(
    () => () => {
      if (ref.current?.open) ref.current.close();
    },
    [],
  );
  return (
    <dialog
      ref={ref}
      className="preferences-dialog"
      aria-labelledby="preferences-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="dialog-top">
        <div>
          <h2 id="preferences-title">
            <SlidersHorizontal size={18} /> 偏好设置
          </h2>
          <p>选择你喜欢的课程与上课节奏</p>
        </div>
        <button className="icon-button" aria-label="关闭偏好设置" onClick={onClose} autoFocus>
          <X size={19} />
        </button>
      </div>
      <div className="preferences-dialog-body">
        {error && (
          <div className="message error" role="alert">
            {error}
          </div>
        )}
        {busy && (
          <p className="preferences-saving" role="status">
            正在保存偏好或生成推荐，请稍候…
          </p>
        )}
        <PreferencesPanel
          student={student}
          catalog={catalog}
          disabled={disabled}
          onSave={onSave}
          onDirty={onDirty}
        />
      </div>
      <div className="preferences-dialog-footer">
        <span>关闭弹窗后，未保存的调整会暂时保留。</span>
        <button className="button" onClick={onClose}>
          关闭设置
        </button>
      </div>
    </dialog>
  );
}
