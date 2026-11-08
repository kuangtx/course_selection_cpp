import { Play, Square, Users, LoaderCircle } from 'lucide-react';
import type { useDemoSimulation } from '../hooks/useDemoSimulation';

const stages = {
  idle: '尚未开始',
  round1: '第一轮自动提交中',
  waiting_draw: '等待抽签',
  round2: '第二轮自动补选中',
  finished: '本轮已结束',
  stopped: '已停止',
  error: '任务异常停止',
};
export function SimulationPanel({
  simulation,
  disabled,
}: {
  simulation: ReturnType<typeof useDemoSimulation>;
  disabled: boolean;
}) {
  const { status, error, busy, start, stop, retry } = simulation;
  return (
    <section className="panel simulation-panel" aria-label="其他同学自动选课">
      <div className="panel-heading">
        <div>
          <h2>
            <Users size={18} /> 其他同学自动选课
          </h2>
          <p>S001 由你操作，其他同学随机顺序提交各自偏好分最高的候选方案。</p>
        </div>
        <span className={`badge ${status?.running ? 'green' : 'neutral'}`}>
          {status ? stages[status.stage] : '读取状态…'}
        </span>
      </div>
      <div className="simulation-body">
        <div className="simulation-intro">
          <p>
            先为 S001
            提交志愿，再开始模拟。申请人数增加后，中签概率下降达到阈值时，顶部铃铛会收到真实风险提醒。
          </p>
          <p>
            第一轮处理完毕后等待你抽签；抽签后自动保留已录取课程，逐班补齐缺口。切换页面或关闭浏览器，后台任务仍会继续。
          </p>
        </div>
        {error && (
          <div className="message error" role="alert">
            <span>{error}</span>
            <button className="button small-button" onClick={retry} disabled={busy}>
              重试模拟状态
            </button>
          </div>
        )}
        {status && (
          <>
            <div className="simulation-stats">
              <div>
                <span>第一轮已处理</span>
                <strong>
                  {status.round1_processed}
                  <small> / {status.total_students} 人</small>
                </strong>
              </div>
              <div>
                <span>本次提交志愿</span>
                <strong>
                  {status.round1_submitted}
                  <small> 人</small>
                </strong>
              </div>
              <div>
                <span>本次补选成功</span>
                <strong>
                  {status.round2_submitted}
                  <small> 门次</small>
                </strong>
              </div>
              <div>
                <span>S001 待处理提醒</span>
                <strong>
                  {status.pending_alerts}
                  <small> 条</small>
                </strong>
              </div>
            </div>
            <div className="simulation-actions">
              <button
                className="button primary"
                onClick={start}
                disabled={
                  disabled || busy || status.running || !['ROUND1_OPEN', 'ROUND2_OPEN'].includes(status.phase)
                }
              >
                <Play size={15} />
                {status.stage === 'stopped' ? '继续自动选课' : '开始自动选课'}
              </button>
              <button className="button" onClick={stop} disabled={busy || !status.running}>
                <Square size={14} />
                停止自动选课
              </button>
              <span className="muted small">
                {busy
                  ? '正在处理…'
                  : status.active_student
                    ? `正在处理 ${status.active_student}`
                    : status.stage === 'waiting_draw'
                      ? '可以先查看 S001 的风险提醒，再结束第一轮。'
                      : '停止后保留已提交结果；重置演示会停止任务并清空数据。'}
              </span>
              {busy && <LoaderCircle size={15} className="spin" />}
            </div>
            {status.error && <p className="inline-warning">{status.error}</p>}
            {status.limited_searches > 0 && (
              <p className="simulation-note">
                部分搜索达到预算；选择的是已找到候选中的最高偏好分，不保证全局最优。提醒是否出现取决于实际竞争情况。
              </p>
            )}
            <div className="simulation-log" role="region" aria-label="模拟运行记录">
              {status.events.length ? (
                <ol>
                  {status.events.map((event, i) => (
                    <li key={`${event.time}-${i}`}>
                      <time>
                        {new Date(event.time * 1000).toLocaleTimeString('zh-CN', { hour12: false })}
                      </time>
                      <strong>{event.student_id || '系统'}</strong>
                      <span
                        className={
                          event.kind === 'warning' || event.kind === 'error' ? 'simulation-warning' : ''
                        }
                      >
                        {event.message}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted small">开始后，这里会显示提交、补选和阶段变化记录。</p>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
