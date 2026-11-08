import { BookOpen } from 'lucide-react';
import { Timetable } from './Timetable';
import { progress } from '../utils';
import type { Catalog, Student, StudentState } from '../types';

export function ResultsPage({
  catalog,
  student,
  state,
  week,
  setWeek,
  onWithdraw,
  disabled = false,
}: {
  catalog: Catalog;
  student: Student;
  state: StudentState;
  week: number;
  setWeek: (week: number) => void;
  onWithdraw?: () => void;
  disabled?: boolean;
}) {
  const enrolledProgress = progress(student, state.enrolled_section_ids, catalog);
  return (
    <div className="results-page">
      <section className="panel result-panel">
        <div className="panel-heading">
          <div>
            <h2>
              <BookOpen size={18} /> {state.phase === 'CLOSED' ? '最终选课结果' : '正式录取进度'}
            </h2>
            <p>只统计已经正式获得的课程</p>
          </div>
          <span className={`badge ${enrolledProgress?.complete ? 'green' : 'neutral'}`}>
            {enrolledProgress?.complete ? '已完成要求' : '尚未选齐'}
          </span>
          {onWithdraw && state.phase === 'ROUND2_OPEN' && (
            <button className="button small-button" disabled={disabled || !state.enrolled_section_ids.length}
              onClick={onWithdraw}>退选课程</button>
          )}
        </div>
        <div className="completion-grid">
          <div>
            <span>必选课程</span>
            <strong>
              {enrolledProgress?.required}
              <small> / {student.required_course_ids.length} 门</small>
            </strong>
          </div>
          <div>
            <span>可选要求</span>
            <strong>
              {enrolledProgress?.optional}
              <small>
                {' '}
                / {student.optional_requirement.target}{' '}
                {student.optional_requirement.mode === 'count' ? '门' : '学分'}
              </small>
            </strong>
          </div>
          <div>
            <span>已获学分</span>
            <strong>
              {state.enrolled_section_ids.reduce(
                (sum, id) => sum + (catalog.courses[catalog.sections[id]?.course_id]?.credits || 0),
                0,
              )}
              <small> 学分</small>
            </strong>
          </div>
        </div>
        {!enrolledProgress?.complete && (
          <p className="result-note">
            尚缺必选：
            {student.required_course_ids
              .filter(
                (id) => !state.enrolled_section_ids.some((sid) => catalog.sections[sid]?.course_id === id),
              )
              .map((id) => catalog.courses[id]?.name)
              .join('、') || '无'}
            ；可选还差 {Math.max(0, student.optional_requirement.target - (enrolledProgress?.optional || 0))}{' '}
            {student.optional_requirement.mode === 'count' ? '门' : '学分'}。
          </p>
        )}
      </section>
      <Timetable
        catalog={catalog}
        sectionIds={state.enrolled_section_ids}
        enrolledIds={state.enrolled_section_ids}
        state={state}
        week={week}
        setWeek={setWeek}
        label="正式录取"
      />
    </div>
  );
}
