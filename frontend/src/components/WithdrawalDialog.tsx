import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import type { Catalog, StudentState } from '../types';

export function WithdrawalDialog({ catalog, state, onClose, onConfirm }: {
  catalog: Catalog;
  state: StudentState;
  onClose: () => void;
  onConfirm: (ids: string[]) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const firstRound = state.phase === 'ROUND1_OPEN';
  const ids = firstRound ? state.current_application : state.enrolled_section_ids;
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);
  return (
    <dialog ref={ref} className="confirm-dialog withdrawal-dialog" aria-labelledby="withdrawal-title"
      onCancel={(event) => { event.preventDefault(); onClose(); }}>
      <div className="dialog-top">
        <h2 id="withdrawal-title">{firstRound ? '撤回第一轮志愿' : '第二轮退选'}</h2>
        <button className="icon-button" aria-label="关闭退选窗口" onClick={onClose}><X size={18} /></button>
      </div>
      <div className="dialog-content">
        <p>{firstRound
          ? '将撤回以下全部志愿，并清除对应风险提醒。撤回后可重新生成和提交方案。'
          : '选择要退掉的课程。确认后立即释放名额，其他同学可以补选；重新选择原班次需以当时余量为准。'}</p>
        {!firstRound && <label className="withdrawal-select-all">
          <input type="checkbox" checked={ids.length > 0 && selected.length === ids.length}
            onChange={(event) => setSelected(event.target.checked ? [...ids] : [])} />
          全选已录取课程
        </label>}
        <ul className="withdrawal-list">
          {ids.map((id) => {
            const section = catalog.sections[id];
            const name = catalog.courses[section.course_id].name;
            return <li key={id}><label>
              {!firstRound && <input type="checkbox" aria-label={`退选 ${name} ${id}`}
                checked={selected.includes(id)} onChange={(event) => setSelected((current) =>
                  event.target.checked ? [...current, id] : current.filter((value) => value !== id))} />}
              <span><strong>{name}</strong><small>{id}</small></span>
            </label></li>;
          })}
        </ul>
      </div>
      <div className="dialog-actions">
        <button className="button" onClick={onClose} autoFocus>取消</button>
        <button className="button primary" disabled={!firstRound && selected.length === 0}
          onClick={() => onConfirm(firstRound ? ids : selected)}>
          {firstRound ? '确认撤回志愿' : `确认退选（${selected.length} 门）`}
        </button>
      </div>
    </dialog>
  );
}
