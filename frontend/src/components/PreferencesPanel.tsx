import { useEffect, useState } from 'react';
import { BookOpen, SlidersHorizontal, Sunrise, Check } from 'lucide-react';
import type { Catalog, Preferences, Student } from '../types';

export function PreferencesPanel({
  student,
  catalog,
  disabled,
  onSave,
  onDirty,
}: {
  student: Student;
  catalog: Catalog;
  disabled: boolean;
  onSave: (p: Preferences) => Promise<void>;
  onDirty: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState<Preferences>(student.preferences);
  const dirty = JSON.stringify(draft) !== JSON.stringify(student.preferences);
  useEffect(() => {
    setDraft(student.preferences);
  }, [student]);
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  return (
    <aside className="preferences panel">
      <div className="panel-heading">
        <div>
          <h2>
            <SlidersHorizontal size={18} /> 我的选课需求
          </h2>
          <p>让每一门课，都更适合你</p>
        </div>
      </div>
      <div className="preference-body">
        <div className="section-label">
          <BookOpen size={15} /> 必选课程 <span>{student.required_course_ids.length} 门</span>
        </div>
        <div className="required-list">
          {student.required_course_ids.map((id) => (
            <div key={id}>
              <Check size={13} />
              <span>{catalog.courses[id]?.name || id}</span>
              <small>{catalog.courses[id]?.credits} 学分</small>
            </div>
          ))}
        </div>
        <div className="optional-heading">
          <h3>可选课程喜好</h3>
          <span>
            需选 {student.optional_requirement.target}{' '}
            {student.optional_requirement.mode === 'count' ? '门' : '学分'}
          </span>
        </div>
        <p className="muted small">分数越高，越希望选到这门课</p>
        <fieldset disabled={disabled} className="preference-fields">
          <legend className="sr-only">课程喜好分</legend>
          {student.optional_course_ids.map((id) => (
            <label className="score-row" key={id}>
              <span>{catalog.courses[id]?.name || id}</span>
              <input
                aria-label={`${catalog.courses[id]?.name || id}喜好分`}
                type="range"
                min="0"
                max="100"
                step="1"
                value={draft.course_scores[id] ?? 80}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    course_scores: { ...draft.course_scores, [id]: Number(e.target.value) },
                  })
                }
              />
              <output>{draft.course_scores[id] ?? 80}</output>
            </label>
          ))}
          <div className="early-card">
            <label htmlFor="early-penalty">
              <Sunrise size={17} />
              <strong>避开早课</strong>
              <output>{draft.early_penalty_per_week}</output>
            </label>
            <input
              id="early-penalty"
              type="range"
              min="0"
              max={Math.max(40, draft.early_penalty_per_week)}
              step="1"
              value={draft.early_penalty_per_week}
              onChange={(e) => setDraft({ ...draft, early_penalty_per_week: Number(e.target.value) })}
            />
            <div>
              <span>不介意</span>
              <span>更想晚一点</span>
            </div>
            <p>数值越高，越偏好没有第 1 节的课表。</p>
          </div>
        </fieldset>
        <button
          className="button primary full"
          disabled={disabled || !dirty}
          onClick={() => void onSave(draft)}
        >
          {dirty ? '保存偏好并重新推荐' : '偏好已保存'}
        </button>
        <button
          className="text-button preference-reset"
          disabled={disabled || !dirty}
          onClick={() => setDraft(student.preferences)}
        >
          恢复已保存的偏好
        </button>
        <p className="small muted preference-note">
          课程要求来自当前样例学生。修改偏好后，已提交志愿仍需手动确认修改。
        </p>
      </div>
    </aside>
  );
}
