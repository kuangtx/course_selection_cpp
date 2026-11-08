import { useEffect, useState } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Compass,
  LayoutGrid,
  LoaderCircle,
  RefreshCw,
  Settings2,
  Sparkles,
  X,
} from 'lucide-react';
import { useDemoSimulation } from './hooks/useDemoSimulation';
import { SimulationPanel } from './components/SimulationPanel';
import { useSelection } from './hooks/useSelection';
import { PreferencesDialog } from './components/PreferencesDialog';
import { SideNavigation } from './components/SideNavigation';
import { ResultsPage } from './components/ResultsPage';
import { usePageNavigation } from './hooks/usePageNavigation';
import { Timetable } from './components/Timetable';
import { PlanDetails } from './components/PlanDetails';
import { ConfirmDialog } from './components/ConfirmDialog';
import { WithdrawalDialog } from './components/WithdrawalDialog';
import { AlertDropdown } from './components/AlertDropdown';
import { SelectMenu } from './components/SelectMenu';
import { majorName, percent } from './utils';

const phaseLabels = {
  ROUND1_OPEN: '第一轮 · 志愿申请',
  DRAWING: '正在抽签',
  ROUND2_OPEN: '第二轮 · 余量补选',
  CLOSED: '选课已结束',
};
type View = 'candidate' | 'application' | 'enrolled';

const recommendationTopRatio = Number(import.meta.env.VITE_RECOMMEND_TOP_RATIO || 0.25);
const recommendationPageSize = Number(import.meta.env.VITE_RECOMMEND_PAGE_SIZE || 2);

export default function App() {
  const selection = useSelection();
  const { page, navigate } = usePageNavigation();
  const simulation = useDemoSimulation(page === 'demo', () => {
    if (!selection.busy) selection.retry();
  });
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const pageTitle = { selection: '选课工作台', results: '录取结果', demo: '演示控制' }[page];
  const {
    catalog,
    studentId,
    state,
    alerts,
    recommendation,
    error,
    notice,
    loading,
    calculating,
    busy,
    updatedAt,
    offline,
  } = selection;
  const [week, setWeek] = useState(1);
  const [selectedPlan, setSelectedPlan] = useState(0);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [withdrawalOpen, setWithdrawalOpen] = useState(false);
  const [planPage, setPlanPage] = useState(0);
  const [view, setView] = useState<View>('application');
  const [dirty, setDirty] = useState(false);
  const [confirmation, setConfirmation] = useState<{
    title: string;
    text: string;
    action: () => void;
  } | null>(null);
  useEffect(() => {
    setWeek(1);
    setSelectedPlan(0);
    setPlanPage(0);
    setView('application');
    setDirty(false);
    setConfirmation(null);
    setPreferencesOpen(false);
  }, [studentId]);
  useEffect(() => {
    setSelectedPlan(0);
    setPlanPage(0);
    setView(
      recommendation?.plans.length
        ? 'candidate'
        : state?.phase && state.phase !== 'ROUND1_OPEN'
          ? 'enrolled'
          : 'application',
    );
  }, [recommendation, state?.phase]);
  useEffect(() => {
    setConfirmation(null);
    if (state) setView(state.phase === 'ROUND1_OPEN' ? 'application' : 'enrolled');
  }, [state?.phase, state?.plan_revision]);

  useEffect(() => {
    setDetailsOpen(false);
  }, [studentId, recommendation, state?.phase, state?.plan_revision, page]);
  useEffect(() => {
    setWithdrawalOpen(false);
  }, [studentId, state?.phase, state?.plan_revision, page]);

  const student = catalog?.students[studentId];
  const visiblePlans = recommendation
    ? recommendation.purpose === 'supplement'
      ? recommendation.plans
      : recommendation.plans
          .filter((candidate) => candidate.recommendation_score !== null)
          .sort((a, b) => (b.recommendation_score ?? 0) - (a.recommendation_score ?? 0))
          .slice(0, Math.ceil(recommendation.plans.length * recommendationTopRatio))
    : [];
  const planPageCount = Math.ceil(visiblePlans.length / recommendationPageSize);
  const currentPlanPage = Math.min(planPage, Math.max(planPageCount - 1, 0));
  const planPageStart = currentPlanPage * recommendationPageSize;
  const pagePlans = visiblePlans.slice(planPageStart, planPageStart + recommendationPageSize);
  const plan = visiblePlans[selectedPlan];
  const pendingSupplementIds =
    plan && state?.phase === 'ROUND2_OPEN'
      ? plan.section_ids.filter((id) => !state.enrolled_section_ids.includes(id))
      : [];
  const locked = busy || calculating || !state || offline;
  const closed = state?.phase === 'CLOSED' || state?.phase === 'DRAWING';
  const hasSubmittedFirstRound = state?.phase === 'ROUND1_OPEN' && state.current_application.length > 0;
  const stale = !!recommendation && !!state && recommendation.state_version !== state.state_version;
  const previewIds =
    view === 'candidate'
      ? plan?.section_ids || []
      : view === 'application'
        ? state?.current_application || []
        : state?.enrolled_section_ids || [];
  const labels: Record<View, string> = {
    candidate: '推荐预览',
    application: '当前志愿',
    enrolled: '正式录取',
  };

  return (
    <div className={`app-shell ${page === 'selection' || page === 'results' ? 'desktop-workspace' : ''}`}>
      <SideNavigation
        page={page}
        preferencesOpen={preferencesOpen}
        ready={!!student && !!state}
        dirty={dirty}
        onNavigate={navigate}
        onPreferences={() => setPreferencesOpen(true)}
      />
      <header className="app-header">
        <span className="header-title">{pageTitle}</span>
        <span className="header-divider" aria-hidden="true" />
        <h1 className="header-tagline">
          {page === 'selection'
            ? '把喜欢的课，排进这一周。'
            : page === 'results'
              ? '查看正式录取课程与完成情况。'
              : '管理本地演示的选课阶段。'}
        </h1>
        <div className="header-right">
          {simulation.status?.running && (
            <button className="simulation-indicator" onClick={() => navigate('demo')}>
              <i className="status-dot" />
              模拟运行中
            </button>
          )}
          <span className="local-tag">本地演示</span>
          <AlertDropdown
            key={studentId}
            alerts={alerts}
            catalog={catalog}
            phase={state?.phase}
            disabled={locked}
            dirty={dirty}
            onAdjust={() => {
              navigate('selection');
              void selection.generate('adjustment');
              document.getElementById('recommendations')?.scrollIntoView({ block: 'start' });
            }}
            onKeep={(id) => void selection.acknowledge(id)}
          />
          {catalog && (
            <div className="student-picker">
              <span className="avatar">{student?.major_id === 'AI' ? 'AI' : 'SE'}</span>
              <span>
                <small>当前学生</small>
                <SelectMenu
                  label="选择学生"
                  className="student-select-menu"
                  value={studentId}
                  disabled={busy}
                  searchable
                  placeholder="搜索学号或专业"
                  options={Object.values(catalog.students).map((s) => ({
                    value: s.id,
                    label: `${s.id} · ${majorName(s.major_id)}`,
                  }))}
                  onChange={selection.selectStudent}
                />
              </span>
            </div>
          )}
        </div>
      </header>
      <main id="main" className="main-container">
        <div className="page-heading">
          <div className="heading-context">
            <div className="breadcrumb">
              <LayoutGrid size={13} /> 学习空间 <ChevronRight size={12} /> <span>{pageTitle}</span>
            </div>
          </div>
          <div className="sync-status">
            <span className={offline ? 'offline' : ''}>
              <i className="status-dot" />
              {offline
                ? '连接中断 · 数据可能过期'
                : updatedAt
                  ? `更新于 ${updatedAt.toLocaleTimeString('zh-CN', { hour12: false })}`
                  : '等待连接'}
            </span>
            <button className="button refresh-button" onClick={selection.retry} disabled={busy || loading}>
              <RefreshCw size={14} />
              刷新状态
            </button>
          </div>
        </div>
        {error && (
          <div className="message error" role="alert">
            <div>
              <strong>{error.message}</strong>
              {error.detail && (
                <details>
                  <summary>查看接口详情</summary>
                  <code>{error.detail}</code>
                </details>
              )}
            </div>
            <button className="button small-button" onClick={selection.retry} disabled={busy}>
              重试
            </button>
            <button className="icon-button" aria-label="关闭错误提示" onClick={selection.dismissError}>
              <X size={16} />
            </button>
          </div>
        )}
        {notice && (
          <div className="message success" role="status">
            <Check size={17} />
            {notice}
          </div>
        )}
        {!catalog || !student || !state ? (
          <div className="panel loading-panel">
            {!error ? (
              <>
                <LoaderCircle className="spin" size={26} />
                <h2>正在读取选课数据</h2>
                <p>连接课程、学生与当前选课状态…</p>
              </>
            ) : (
              <>
                <Compass size={32} />
                <h2>暂时无法加载选课工作台</h2>
                <p>请检查后端服务，然后点击上方重试。</p>
              </>
            )}
          </div>
        ) : (
          <>
            <section className="phase-strip" aria-label="选课阶段">
              <div className="phase-current">
                <span className="live-dot" />
                <div>
                  <strong>{phaseLabels[state.phase]}</strong>
                  <small>
                    {state.phase === 'ROUND1_OPEN'
                      ? '先提交志愿，截止后统一抽签'
                      : state.phase === 'ROUND2_OPEN'
                        ? '已录取课程保留，剩余名额先到先得'
                        : state.phase === 'CLOSED'
                          ? '本轮选课已完成，查看最终结果'
                          : '请等待抽签完成'}
                  </small>
                </div>
              </div>
              <ol className="phase-steps">
                {['规划与申请', '抽签与补选', '最终课表'].map((name, i) => {
                  const step = state.phase === 'ROUND1_OPEN' ? 0 : state.phase === 'CLOSED' ? 2 : 1;
                  return (
                    <li key={name} className={i === step ? 'active' : i < step ? 'done' : ''}>
                      <b>{i < step ? <Check size={13} /> : `0${i + 1}`}</b>
                      <span>{name}</span>
                      {i < 2 && <ArrowRight size={14} />}
                    </li>
                  );
                })}
              </ol>
            </section>
            {page === 'selection' && (
              <div className="workspace-layout">
                <div className="main-column">
                  <div className="workspace-toolbar">
                    <div className="segmented" role="group" aria-label="课表内容">
                      <button
                        className={view === 'application' ? 'active' : ''}
                        onClick={() => setView('application')}
                      >
                        当前志愿 <span>{state.current_application.length}</span>
                      </button>
                      <button
                        className={view === 'enrolled' ? 'active' : ''}
                        onClick={() => setView('enrolled')}
                      >
                        正式录取 <span>{state.enrolled_section_ids.length}</span>
                      </button>
                      <button
                        className={view === 'candidate' ? 'active' : ''}
                        disabled={!plan}
                        onClick={() => setView('candidate')}
                      >
                        推荐预览
                      </button>
                    </div>
                    <div className="workspace-withdrawal">
                      <span className="muted small">
                        {majorName(student.major_id)} · {catalog.term.total_weeks} 周
                      </span>
                      {!closed && (
                        <button className="button small-button" disabled={locked ||
                          (state.phase === 'ROUND1_OPEN' ? !state.current_application.length : !state.enrolled_section_ids.length)}
                          onClick={() => setWithdrawalOpen(true)}>
                          {state.phase === 'ROUND1_OPEN' ? '撤回志愿' : '退选课程'}
                        </button>
                      )}
                    </div>
                  </div>
                  <Timetable
                    catalog={catalog}
                    sectionIds={previewIds}
                    enrolledIds={state.enrolled_section_ids}
                    state={state}
                    week={week}
                    setWeek={setWeek}
                    label={labels[view]}
                  />
                </div>
                <aside className="recommendation-column">
                  <section id="recommendations" className="panel recommendations">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          <Sparkles size={18} /> 为你推荐
                        </h2>
                        <p>偏好、风险与补选路径，一起考虑</p>
                      </div>
                    </div>
                    <div className="recommendation-body">
                      <button
                        className="button primary full"
                        disabled={locked || closed || dirty}
                        onClick={() => void selection.generate()}
                      >
                        {calculating ? <LoaderCircle size={17} className="spin" /> : <Sparkles size={17} />}
                        {calculating
                          ? '正在生成方案…'
                          : state.phase === 'ROUND2_OPEN'
                            ? '生成补选方案'
                            : state.current_application.length
                              ? '生成调整方案'
                              : '生成推荐方案'}
                      </button>
                      <button
                        className="button full preferences-shortcut"
                        onClick={() => setPreferencesOpen(true)}
                      >
                        设置选课偏好
                      </button>
                      {dirty && (
                        <p className="inline-warning">
                          偏好尚未保存。
                          <button className="text-button" onClick={() => setPreferencesOpen(true)}>
                            继续设置偏好
                          </button>
                        </p>
                      )}
                      {closed ? (
                        <div className="empty-recommendation">
                          <Check size={30} />
                          <h3>{state.phase === 'CLOSED' ? '本次选课已结束' : '正在统一抽签'}</h3>
                          <p>
                            {state.phase === 'CLOSED'
                              ? '在录取结果页面查看最终课表和完成情况。'
                              : '抽签完成后将开放第二轮补选。'}
                          </p>
                        </div>
                      ) : !recommendation && !calculating ? (
                        <div className="empty-recommendation">
                          <div className="empty-illustration">
                            <Compass size={40} strokeWidth={1.2} />
                            <span />
                            <i />
                          </div>
                          <h3>
                            {state.phase === 'ROUND2_OPEN'
                              ? '录取课程已保留'
                              : hasSubmittedFirstRound
                                ? '当前志愿已提交'
                                : '你的下一周，从这里开始'}
                          </h3>
                          <p>
                            {state.phase === 'ROUND2_OPEN'
                              ? '生成补选方案，查看可补选课程；已录取课程会保留。'
                              : hasSubmittedFirstRound
                                ? '可生成调整方案进行比较，确认提交后才会替换当前志愿。'
                                : '在偏好设置中调整喜好，生成候选课表。比较后，再决定如何选择。'}
                          </p>
                          <div className="mini-feature">
                            <Check size={13} /> 检查时间冲突{' '}
                            <Check size={13} />
                            {state.phase === 'ROUND2_OPEN'
                              ? '保留已录取课程'
                              : hasSubmittedFirstRound
                                ? '提交前不替换志愿'
                                : '保留你的选择'}
                          </div>
                        </div>
                      ) : null}
                      {calculating && (
                        <div className="calculating-state" role="status">
                          <div className="skeleton" />
                          <div className="skeleton" />
                          <div className="skeleton" />
                          <p>正在查找合适的班次与补选路径…</p>
                        </div>
                      )}
                      {recommendation && (
                        <>
                          {recommendation.search_status === 'LIMIT_REACHED' && (
                            <p className="inline-warning">
                              搜索已达到预算，展示已找到的方案；尚不能确认无解或最优。
                            </p>
                          )}
                          {stale && (
                            <p className="inline-warning">
                              申请人数或余量有更新，评分可能过期；可重新生成方案，提交时会再次校验。
                            </p>
                          )}
                          {!recommendation.plans.length && (
                            <div className="empty-recommendation">
                              <Compass size={28} />
                              <h3>
                                {recommendation.decision === 'KEEP_CURRENT'
                                  ? '建议保留当前志愿'
                                  : recommendation.search_status === 'LIMIT_REACHED'
                                    ? '暂未找到候选方案'
                                    : '没有找到完整方案'}
                              </h3>
                              <p>
                                {recommendation.decision === 'KEEP_CURRENT'
                                  ? '当前搜索到的候选中没有其他完整方案。'
                                  : recommendation.search_status === 'LIMIT_REACHED'
                                    ? '搜索尚未完成，不能据此认定无解。'
                                    : '当前条件下无法补齐全部要求，请检查下方缺口。'}
                              </p>
                            </div>
                          )}
                          <div className="plan-list">
                            {pagePlans.map((candidate, i) => {
                              const planIndex = planPageStart + i;
                              return (
                                <article
                                  className={`plan-card ${selectedPlan === planIndex ? 'selected' : ''}`}
                                  key={candidate.section_ids.join('|')}
                                >
                                  <div className="plan-card-heading">
                                    <span className="plan-number">0{planIndex + 1}</span>
                                    <strong>
                                      {planIndex === 0 ? '优先推荐' : `备选方案 ${planIndex + 1}`}
                                    </strong>
                                    <button
                                      className="button plan-details-button"
                                      aria-label={`查看方案 ${planIndex + 1} 详情`}
                                      aria-haspopup="dialog"
                                      onClick={() => {
                                        setSelectedPlan(planIndex);
                                        setView('candidate');
                                        setDetailsOpen(true);
                                      }}
                                    >
                                      详情 <ChevronRight size={12} />
                                    </button>
                                    <span className="radio-mark" aria-hidden="true">
                                      {selectedPlan === planIndex && <Check size={11} />}
                                    </span>
                                  </div>
                                  <button
                                    className="plan-preview-button"
                                    aria-label={`预览方案 ${planIndex + 1} 课表`}
                                    aria-pressed={selectedPlan === planIndex}
                                    onClick={() => {
                                      setSelectedPlan(planIndex);
                                      setView('candidate');
                                    }}
                                  >
                                    <div className="plan-score">
                                      <strong>{candidate.preference_score.total.toFixed(1)}</strong>
                                      <span>偏好分 / 100</span>
                                      <span className={`badge ${candidate.is_complete ? 'green' : 'amber'}`}>
                                        {candidate.is_complete ? '完整' : '未补齐'}
                                      </span>
                                    </div>
                                    <div className="plan-metrics">
                                      <div>
                                        <span>第一轮全中估计</span>
                                        <b>
                                          {candidate.risk
                                            ? percent(candidate.risk.first_round_all_win_probability)
                                            : '不适用'}
                                        </b>
                                      </div>
                                      <div>
                                        <span>已确认补选覆盖</span>
                                        <b>
                                          {candidate.fallback
                                            ? percent(candidate.fallback.coverage_lower_bound)
                                            : '不适用'}
                                        </b>
                                      </div>
                                    </div>
                                    <div className="plan-card-footer">
                                      <span>
                                        {candidate.section_ids.length} 门课程
                                        {candidate.comparison
                                          ? ` · 改动 ${candidate.comparison.changed_course_count} 门`
                                          : ''}
                                      </span>
                                      <span>
                                        查看课表 <ArrowRight size={12} />
                                      </span>
                                    </div>
                                  </button>
                                </article>
                              );
                            })}
                          </div>
                          {planPageCount > 1 && (
                            <nav className="plan-pagination" aria-label="推荐方案分页">
                              <button
                                className="button"
                                disabled={currentPlanPage === 0}
                                onClick={() => {
                                  const previousPage = currentPlanPage - 1;
                                  setPlanPage(previousPage);
                                  setSelectedPlan(previousPage * recommendationPageSize);
                                  setView('candidate');
                                }}
                              >
                                <ChevronLeft size={14} /> 上一页
                              </button>
                              <span aria-live="polite">
                                第 {currentPlanPage + 1} / {planPageCount} 页 · 共 {visiblePlans.length} 套
                              </span>
                              <button
                                className="button"
                                disabled={currentPlanPage >= planPageCount - 1}
                                onClick={() => {
                                  const nextPage = currentPlanPage + 1;
                                  setPlanPage(nextPage);
                                  setSelectedPlan(nextPage * recommendationPageSize);
                                  setView('candidate');
                                }}
                              >
                                下一页 <ChevronRight size={14} />
                              </button>
                            </nav>
                          )}
                          {visiblePlans.length > 0 && (
                            <p className="recommendation-note">
                              <CircleHelp size={14} />
                              基于当前候选与申请情况计算，不代表全局最优；推荐不会自动占用名额。
                            </p>
                          )}
                        </>
                      )}
                    </div>
                    {recommendation &&
                      plan &&
                      (state.phase === 'ROUND1_OPEN' || state.phase === 'ROUND2_OPEN') && (
                        <div className="plan-submit-footer">
                          <p className="small muted" aria-live="polite">
                            当前选择：<strong>方案 {selectedPlan + 1}</strong> ·{' '}
                            {state.phase === 'ROUND2_OPEN'
                              ? `${pendingSupplementIds.length} 门待补选`
                              : `${plan.section_ids.length} 门课程`}
                          </p>
                          <button
                            className="button primary full plan-submit-button"
                            disabled={
                              locked ||
                              dirty ||
                              closed ||
                              !plan.is_complete ||
                              (state.phase === 'ROUND2_OPEN' && pendingSupplementIds.length === 0)
                            }
                            onClick={() => {
                              setView('candidate');
                              setConfirmation({
                                title:
                                  state.phase === 'ROUND2_OPEN'
                                    ? '确认提交补选方案'
                                    : state.current_application.length
                                      ? '确认修改第一轮志愿'
                                      : '确认提交第一轮志愿',
                                text:
                                  state.phase === 'ROUND2_OPEN'
                                    ? `将按顺序提交方案 ${selectedPlan + 1} 中尚未录取的 ${pendingSupplementIds.length} 门课程，每门成功后立即占用名额。若中途名额不足或提交失败，后续课程将不再提交；已成功的课程会保留，不会回滚。`
                                    : `将提交方案 ${selectedPlan + 1}，包含 ${plan.section_ids.length} 门课程${state.current_application.length ? '，并替换当前志愿' : ''}。提交后等待统一抽签，不代表正式录取。`,
                                action: () =>
                                  state.phase === 'ROUND2_OPEN'
                                    ? void selection.submitSupplementPlan(plan.section_ids)
                                    : void selection.submitPlan(
                                        plan.section_ids,
                                        recommendation.plan_revision,
                                      ),
                              });
                            }}
                          >
                            提交所选方案 <ArrowUpRight size={15} />
                          </button>
                        </div>
                      )}
                  </section>
                </aside>
              </div>
            )}
            {page === 'results' && (
              <ResultsPage catalog={catalog} student={student} state={state} week={week} setWeek={setWeek}
                onWithdraw={() => setWithdrawalOpen(true)}
                disabled={locked} />
            )}
            {page === 'demo' && (
              <>
                <SimulationPanel simulation={simulation} disabled={locked || simulation.busy} />
                <section className="panel demo-controls">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        <Settings2 size={18} /> 演示控制
                      </h2>
                      <p>推进阶段与重置数据</p>
                    </div>
                  </div>
                  <div>
                    <p>以下操作影响所有样例学生。用于本地联调和演示。</p>
                    <div className="demo-buttons">
                      <button
                        className="button"
                        disabled={locked || state.phase !== 'ROUND1_OPEN'}
                        onClick={() =>
                          setConfirmation({
                            title: '结束第一轮并抽签',
                            text: '将冻结所有样例学生的第一轮志愿，执行抽签并开放第二轮补选。',
                            action: () => void selection.control('round1/draw'),
                          })
                        }
                      >
                        结束第一轮并抽签
                      </button>
                      <button
                        className="button"
                        disabled={locked || state.phase !== 'ROUND2_OPEN'}
                        onClick={() =>
                          setConfirmation({
                            title: '关闭选课',
                            text: '将结束所有样例学生的第二轮补选，保留最终录取结果。',
                            action: () => void selection.control('close'),
                          })
                        }
                      >
                        关闭选课
                      </button>
                      <button
                        className="button danger"
                        disabled={busy || calculating}
                        onClick={() =>
                          setConfirmation({
                            title: '重置演示数据',
                            text: '将清空所有样例学生的志愿、录取和提醒，并恢复初始偏好。此操作无法撤销。',
                            action: () => void selection.control('reset'),
                          })
                        }
                      >
                        重置演示
                      </button>
                    </div>
                  </div>
                </section>
              </>
            )}
          </>
        )}
        <footer className="page-footer">
          <span>
            有序选课 <span> / </span> 为每一周留出更多可能
          </span>
          <span>自主选择 · 清晰规划</span>
        </footer>
      </main>
      {catalog && student && state && (
        <PreferencesDialog
          key={studentId}
          open={preferencesOpen}
          student={student}
          catalog={catalog}
          disabled={locked || closed}
          busy={busy || calculating}
          error={error?.message}
          onClose={() => setPreferencesOpen(false)}
          onDirty={setDirty}
          onSave={async (preferences) => {
            navigate('selection');
            await selection.savePreferences(preferences);
          }}
        />
      )}
      {detailsOpen && plan && catalog && state && page === 'selection' && (
        <PlanDetails
          plan={plan}
          planNumber={selectedPlan + 1}
          onClose={() => setDetailsOpen(false)}
          catalog={catalog}
          state={state}
          baseIds={state.phase === 'ROUND1_OPEN' ? state.current_application : state.enrolled_section_ids}
          disabled={locked || dirty || closed}
          onSupplement={(id) => void selection.submitSection(id)}
        />
      )}
      {withdrawalOpen && catalog && state && !closed && (
        <WithdrawalDialog catalog={catalog} state={state} onClose={() => setWithdrawalOpen(false)}
          onConfirm={(ids) => {
            setWithdrawalOpen(false);
            if (state.phase === 'ROUND1_OPEN') void selection.withdrawPlan(state.plan_revision);
            else void selection.withdrawSections(ids, state.plan_revision);
          }} />
      )}
      {confirmation && (
        <ConfirmDialog
          title={confirmation.title}
          onClose={() => setConfirmation(null)}
          onConfirm={() => {
            const action = confirmation.action;
            setConfirmation(null);
            action();
          }}
        >
          <p>{confirmation.text}</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
