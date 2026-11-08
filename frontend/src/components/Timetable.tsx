import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';
import type { Catalog, StudentState } from '../types';
import { SelectMenu } from './SelectMenu';

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
export function Timetable({
  catalog,
  sectionIds,
  enrolledIds,
  state,
  week,
  setWeek,
  label,
}: {
  catalog: Catalog;
  sectionIds: string[];
  enrolledIds: string[];
  state: Pick<StudentState, 'phase' | 'applicant_counts' | 'remaining'>;
  week: number;
  setWeek: (n: number) => void;
  label: string;
}) {
  const { days_per_week: days, periods_per_day: periods, total_weeks: weeks } = catalog.term;
  const colors = Object.keys(catalog.courses);
  const meetings = sectionIds.flatMap((id) => {
    const section = catalog.sections[id];
    return section
      ? section.meetings
          .filter((m) => m.weeks.includes(week))
          .map((meeting, index) => ({ section, meeting, index }))
      : [];
  });
  return (
    <section className="panel timetable-panel" aria-label="每周课表">
      <div className="panel-heading">
        <div>
          <h2>
            <CalendarDays size={18} /> 我的周课表
          </h2>
          <p>{label} · 仅显示本周实际授课安排</p>
        </div>
        <div className="week-control">
          <button
            className="icon-button"
            aria-label="上一周"
            disabled={week <= 1}
            onClick={() => setWeek(week - 1)}
          >
            <ChevronLeft size={17} />
          </button>
          <SelectMenu
            label="选择周次"
            className="week-select-menu"
            value={String(week)}
            options={Array.from({ length: weeks }, (_, i) => ({
              value: String(i + 1),
              label: `第 ${i + 1} 周`,
            }))}
            onChange={(value) => setWeek(Number(value))}
          />
          <button
            className="icon-button"
            aria-label="下一周"
            disabled={week >= weeks}
            onClick={() => setWeek(week + 1)}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
      <div className="schedule-scroll">
        <div
          className="schedule"
          style={{
            gridTemplateColumns: `42px repeat(${days}, minmax(80px, 1fr))`,
            gridTemplateRows: `var(--schedule-header-height, 42px) repeat(${periods}, minmax(0, var(--schedule-row-height, 39px)))`,
          }}
        >
          <div className="schedule-corner">节次</div>
          {Array.from({ length: days }, (_, day) => (
            <div
              className={`day-heading ${day > 4 ? 'weekend' : ''}`}
              key={day}
              style={{ gridColumn: day + 2, gridRow: 1 }}
            >
              {weekdays[day] || `第 ${day + 1} 天`}
            </div>
          ))}
          {Array.from({ length: periods }, (_, period) => (
            <div className="period" key={period} style={{ gridColumn: 1, gridRow: period + 2 }}>
              {String(period + 1).padStart(2, '0')}
            </div>
          ))}
          {Array.from({ length: days * periods }, (_, i) => (
            <div
              key={i}
              aria-hidden
              className="schedule-cell"
              style={{ gridColumn: (i % days) + 2, gridRow: Math.floor(i / days) + 2 }}
            />
          ))}
          {meetings.map(({ section, meeting, index }) => {
            const course = catalog.courses[section.course_id];
            const firstRound = state.phase === 'ROUND1_OPEN' || state.phase === 'DRAWING';
            const countLabel = firstRound ? '申请' : '已选';
            const remaining = state.remaining[section.id];
            const count = firstRound
              ? (state.applicant_counts?.[section.id] ?? 0)
              : remaining === undefined ? undefined : section.capacity - remaining;
            const countText = `${countLabel} ${count ?? '—'} · 容量 ${section.capacity}`;
            const overCapacity = firstRound && count !== undefined && count > section.capacity;
            const status = enrolledIds.includes(section.id)
              ? '已录取'
              : label === '当前志愿'
                ? '申请中'
                : '待提交';
            return (
              <div
                key={`${section.id}-${index}`}
                data-testid="course-block"
                className={`course-block course-color-${colors.indexOf(section.course_id) % 6}`}
                style={{
                  gridColumn: meeting.day + 1,
                  gridRow: `${meeting.start + 1} / span ${meeting.length}`,
                }}
                title={`${course.name} · ${section.id} · 第 ${meeting.start}–${meeting.start + meeting.length - 1} 节 · ${status} · ${countText}（人数/容量）`}
              >
                <strong>{course.name}</strong>
                <span>
                  {section.id.replace(`${section.course_id}_`, '')} 班 · {meeting.start}–
                  {meeting.start + meeting.length - 1} 节
                </span>
                <div className="course-block-footer">
                  <small>{status}</small>
                  <small
                    className={`course-enrollment ${overCapacity ? 'over-capacity' : ''}`}
                    aria-label={`${countLabel}人数/容量：${count ?? '未知'}/${section.capacity}${overCapacity ? `，超额 ${count! - section.capacity} 人` : ''}`}
                    title={overCapacity ? `超过容量 ${count! - section.capacity} 人` : undefined}
                  >
                    {countText}
                  </small>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="schedule-footer">
        <span>
          <i className="status-dot" />{' '}
          {meetings.length ? `本周 ${meetings.length} 个授课时段` : '本周暂无授课安排'}
        </span>
        <span>{weeks} 周学期 · 支持单双周</span>
      </div>
    </section>
  );
}
