import { useEffect, useRef } from 'react';
import { ArrowRight, Check, Info, X } from 'lucide-react';
import type { Catalog, Plan, StudentState } from '../types';
import { courseChanges, percent } from '../utils';

export function PlanDetails({
  plan,
  catalog,
  state,
  baseIds,
  disabled,
  planNumber,
  onClose,
  onSupplement,
}: {
  plan: Plan;
  catalog: Catalog;
  state: StudentState;
  baseIds: string[];
  disabled: boolean;
  planNumber: number;
  onClose: () => void;
  onSupplement: (id: string) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus({ preventScroll: true });
    };
  }, []);
  const changes = courseChanges(baseIds, plan.section_ids, catalog);
  const comparison = plan.comparison;
  return (
    <dialog
      ref={ref}
      className="panel details-panel plan-dialog"
      aria-labelledby="plan-details-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="panel-heading">
        <div>
          <h2 id="plan-details-title">方案 {planNumber} · 详情</h2>
          <p>{plan.is_complete ? '满足全部必选与可选要求' : '部分方案 · 仍有要求未完成'}</p>
        </div>
        <span className={`badge ${plan.is_complete ? 'green' : 'amber'}`}>
          {plan.is_complete ? '完整方案' : '未补齐'}
        </span>
        <button className="icon-button" aria-label="关闭方案详情" onClick={onClose} autoFocus>
          <X size={18} />
        </button>
      </div>
      <div className="details-body">
        {!plan.is_complete && (
          <div className="inline-warning">
            缺少必选课：
            {plan.unmet_requirements.required_course_ids
              .map((id) => catalog.courses[id]?.name || id)
              .join('、') || '无'}
            ；可选还差 {plan.unmet_requirements.optional.gap}{' '}
            {plan.unmet_requirements.optional.mode === 'count' ? '门' : '学分'}。
          </div>
        )}
        <div className="score-explanation">
          <div>
            <span>可选课喜好</span>
            <b>{plan.preference_score.details.course_preference.toFixed(1)}</b>
          </div>
          <div>
            <span>时间舒适度</span>
            <b>{plan.preference_score.details.time_score.toFixed(1)}</b>
          </div>
          <div>
            <span>平均每周早课</span>
            <b>
              {plan.preference_score.details.average_early_days_per_week.toFixed(1)} <small>天</small>
            </b>
          </div>
        </div>
        {plan.recommendation_score != null && (
          <p className="ranking-caption">
            综合推荐分 <strong>{(plan.recommendation_score * 100).toFixed(1)}</strong> / 100 ·
            仅用于排序，不是成功概率
          </p>
        )}
        {comparison && (
          <div className="comparison-metrics">
            <span>
              偏好变化{' '}
              <b>
                {comparison.preference_delta > 0 ? '+' : ''}
                {comparison.preference_delta.toFixed(1)} 分
              </b>
            </span>
            <span>
              失败风险变化{' '}
              <b>
                {-comparison.risk_improvement > 0 ? '+' : ''}
                {(-comparison.risk_improvement * 100).toFixed(1)} 个百分点
              </b>
            </span>
            <p>综合分提高不代表每一项都改善，请结合改课情况确认。</p>
          </div>
        )}
        {baseIds.length > 0 && (
          <div className="changes">
            <h3>与{state.phase === 'ROUND1_OPEN' ? '当前志愿' : '已录取课程'}比较</h3>
            {changes.length ? (
              changes.map((change) => (
                <div className="change-row" key={change.courseId}>
                  <span className={`badge ${!change.before ? 'green' : !change.after ? 'amber' : 'blue'}`}>
                    {!change.before ? '新增' : !change.after ? '移除' : '换班'}
                  </span>
                  <strong>{catalog.courses[change.courseId]?.name}</strong>
                  <span>
                    {change.before || '未选择'} <ArrowRight size={12} /> {change.after || '不再选择'}
                  </span>
                </div>
              ))
            ) : (
              <p className="muted small">课程与班次没有变化。</p>
            )}
          </div>
        )}
        <div className="section-list">
          {plan.section_ids.map((id) => {
            const section = catalog.sections[id];
            if (!section) return null;
            const enrolled = state.enrolled_section_ids.includes(id);
            return (
              <div className="section-row" key={id}>
                <div>
                  <strong>{catalog.courses[section.course_id]?.name}</strong>
                  <small>
                    {id} · {catalog.courses[section.course_id]?.credits} 学分
                  </small>
                </div>
                <div className="section-action">
                  {state.phase === 'ROUND1_OPEN' ? (
                    <span className="muted small">
                      中签估计{' '}
                      {plan.risk?.section_probabilities[id] == null
                        ? '—'
                        : percent(plan.risk.section_probabilities[id])}
                    </span>
                  ) : enrolled ? (
                    <span className="enrolled-label">
                      <Check size={14} /> 已录取
                    </span>
                  ) : (
                    <>
                      <small>余 {state.remaining[id] ?? 0} 席</small>
                      <button
                        className="button small-button"
                        disabled={
                          disabled || state.phase !== 'ROUND2_OPEN' || (state.remaining[id] ?? 0) <= 0
                        }
                        onClick={() => onSupplement(id)}
                      >
                        补选此班
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {plan.fallback && (
          <details className="fallback-details">
            <summary>
              <Info size={15} /> 了解补选路径与分析范围
            </summary>
            <p>
              共 {plan.fallback.total} 种中签情景，已确认可补全 {plan.fallback.covered} 种、不可补全{' '}
              {plan.fallback.uncovered} 种、未确认 {plan.fallback.unknown} 种。
            </p>
            <p>包含全部中签情景；覆盖比例未经概率加权，不是最终选齐率，也不保证第二轮名额。</p>
            {plan.fallback.examples.map((example, index) => (
              <p key={index}>
                路径 {index + 1}：若 {example.lost_section_ids.join('、') || '无课程'} 落选，可尝试{' '}
                {example.added_section_ids.join('、') || '无需补选'}。
              </p>
            ))}
          </details>
        )}
      </div>
      <div className="plan-dialog-footer">
        <p className="small muted">
          {state.phase === 'ROUND1_OPEN'
            ? '可在推荐区域底部提交所选方案，提交早晚不影响抽签顺序。'
            : '可整套提交或逐班补选，成功后立即占用名额；整套提交中途失败时，已录取课程会保留。'}
        </p>
        <div className="plan-dialog-actions">
          <button className="button" onClick={onClose}>
            返回课表
          </button>
        </div>
      </div>
    </dialog>
  );
}
