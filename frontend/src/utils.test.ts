import { describe, expect, it } from 'vitest';
import { courseChanges, progress } from './utils';
import { catalog } from './test-fixtures';
describe('completion and comparison', () => {
  it('counts optional credits and unique courses, preserving required gaps', () => {
    expect(progress(catalog.students.S002, ['ART_A', 'ART_A'], catalog)).toEqual({
      required: 0,
      optional: 2,
      complete: false,
    });
    expect(progress(catalog.students.S001, ['MATH_A', 'ART_A'], catalog).complete).toBe(true);
  });
  it('distinguishes a section switch, course removal and addition', () => {
    expect(courseChanges(['MATH_A', 'ART_A'], ['MATH_B'], catalog)).toEqual([
      { courseId: 'MATH', before: 'MATH_A', after: 'MATH_B' },
      { courseId: 'ART', before: 'ART_A', after: undefined },
    ]);
    expect(courseChanges([], ['ART_A'], catalog)[0].before).toBeUndefined();
  });
});
