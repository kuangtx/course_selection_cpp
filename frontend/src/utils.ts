import type { Catalog, Student } from './types';
export const percent = (n: number) => `${(n * 100).toFixed(1)}%`;
export const majorName = (id: string) =>
  ({ SE: '软件工程', AI: '人工智能', M1: '专业一', M2: '专业二' })[id] || id;
export function progress(student: Student, ids: string[], catalog: Catalog) {
  const courses = new Set(ids.map((id) => catalog.sections[id]?.course_id).filter(Boolean));
  const required = student.required_course_ids.filter((id) => courses.has(id)).length;
  const optionalIds = student.optional_course_ids.filter((id) => courses.has(id));
  const optional =
    student.optional_requirement.mode === 'count'
      ? optionalIds.length
      : optionalIds.reduce((n, id) => n + (catalog.courses[id]?.credits || 0), 0);
  return {
    required,
    optional,
    complete:
      required === student.required_course_ids.length && optional >= student.optional_requirement.target,
  };
}
export function courseChanges(oldIds: string[], newIds: string[], catalog: Catalog) {
  const before = new Map(oldIds.map((id) => [catalog.sections[id]?.course_id, id]));
  const after = new Map(newIds.map((id) => [catalog.sections[id]?.course_id, id]));
  return [...new Set([...before.keys(), ...after.keys()])]
    .filter((id): id is string => !!id && before.get(id) !== after.get(id))
    .map((id) => ({
      courseId: id,
      before: before.get(id),
      after: after.get(id),
    }));
}
