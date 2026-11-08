import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Bell, Check, X } from 'lucide-react';
import type { Alert, Catalog, Phase } from '../types';
import { percent } from '../utils';

export function AlertDropdown({
  alerts,
  catalog,
  phase,
  disabled,
  dirty,
  onAdjust,
  onKeep,
}: {
  alerts: Alert[];
  catalog: Catalog | null;
  phase?: Phase;
  disabled: boolean;
  dirty: boolean;
  onAdjust: () => void;
  onKeep: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };

  useEffect(() => {
    setOpen(false);
  }, [phase]);
  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const onOutsideClick = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onOutsideClick);
    return () => document.removeEventListener('pointerdown', onOutsideClick);
  }, [open]);

  return (
    <div
      className="notification-wrapper"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation();
          close();
        }
      }}
      onBlur={(event) => {
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="notification-trigger"
        aria-label={`风险提醒，${alerts.length} 条待处理`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? 'risk-notifications' : undefined}
        onClick={() => setOpen((current) => !current)}
      >
        <Bell size={19} />
        {alerts.length > 0 && <b>{alerts.length > 99 ? '99+' : alerts.length}</b>}
      </button>
      {open && (
        <section
          id="risk-notifications"
          className="notification-dropdown panel"
          role="dialog"
          aria-label="风险提醒"
        >
          <div className="panel-heading">
            <div>
              <h2>
                风险提醒 <span className="count-bubble">{alerts.length}</span>
              </h2>
              <p>关注当前志愿的中签变化</p>
            </div>
            <button ref={closeButton} className="icon-button" aria-label="关闭风险提醒" onClick={close}>
              <X size={16} />
            </button>
          </div>
          <div className="notification-list">
            {alerts.length ? (
              alerts.map((alert) => (
                <div className="alert-card" key={alert.id}>
                  <div>
                    <span className="badge amber">中签估计下降</span>
                    <h3>
                      {catalog?.courses[catalog.sections[alert.section_id]?.course_id]?.name ||
                        alert.section_id}
                    </h3>
                    <p>
                      {alert.section_id} · {percent(alert.baseline_prob)} <ArrowRight size={12} />{' '}
                      {percent(alert.current_prob)}
                    </p>
                    <small>按当前申请情况估计，并非截止时的确定概率。</small>
                  </div>
                  <div className="alert-actions">
                    <button
                      className="button"
                      disabled={disabled || dirty || phase !== 'ROUND1_OPEN'}
                      onClick={() => {
                        close();
                        onAdjust();
                      }}
                    >
                      查看调整方案
                    </button>
                    <button
                      className="text-button"
                      disabled={disabled || phase !== 'ROUND1_OPEN'}
                      onClick={() => onKeep(alert.id)}
                    >
                      保留当前志愿
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="quiet-state">
                <span>
                  <Check size={18} />
                </span>
                <div>
                  <strong>暂无待处理提醒</strong>
                  <p>
                    {!phase
                      ? '提醒将在选课数据加载后显示。'
                      : phase === 'ROUND1_OPEN'
                        ? '提交志愿后，我们会持续关注申请风险。'
                        : '第一轮已结束，无需再处理申请风险提醒。'}
                  </p>
                </div>
              </div>
            )}
          </div>
          <div className="notification-footer">
            自动更新 · 每 12 秒检查{dirty && <p>偏好尚未保存，请先保存后查看调整方案。</p>}
          </div>
        </section>
      )}
    </div>
  );
}
