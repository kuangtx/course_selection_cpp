import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api/client';
import { catalog, recommendation, state } from '../test-fixtures';
import type { Recommendation } from '../types';
import { useSelection } from './useSelection';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
beforeEach(() => {
  vi.spyOn(api, 'catalog').mockResolvedValue(structuredClone(catalog));
  vi.spyOn(api, 'state').mockResolvedValue(structuredClone(state));
  vi.spyOn(api, 'alerts').mockResolvedValue({ state_version: 0, alerts: [] });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
async function ready() {
  const hook = renderHook(() => useSelection());
  await waitFor(() => expect(hook.result.current.state).not.toBeNull());
  return hook;
}
describe('async selection lifecycle', () => {
  it('only displays the latest recommendation when responses arrive out of order (T20)', async () => {
    const first = deferred<Recommendation>();
    const second = deferred<Recommendation>();
    vi.spyOn(api, 'recommend').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result } = await ready();
    let a!: Promise<void>;
    let b!: Promise<void>;
    act(() => {
      a = result.current.generate();
    });
    act(() => {
      b = result.current.generate();
    });
    await act(async () => {
      second.resolve({ ...recommendation, searched_nodes: 222 });
      await b;
    });
    await act(async () => {
      first.resolve({ ...recommendation, searched_nodes: 111 });
      await a;
    });
    expect(result.current.recommendation?.searched_nodes).toBe(222);
  });
  it('clears alerts and rejects in-flight results after switching students (T19)', async () => {
    const pending = deferred<Recommendation>();
    vi.spyOn(api, 'recommend').mockReturnValue(pending.promise);
    vi.mocked(api.alerts).mockImplementation(async (id) => ({
      state_version: 0,
      alerts:
        id === 'S001'
          ? [
              {
                id: 'A1',
                student_id: id,
                section_id: 'MATH_A',
                plan_revision: 0,
                baseline_prob: 1,
                current_prob: 0.5,
                status: 'PENDING',
                created_at: 1,
              },
            ]
          : [],
    }));
    const { result } = await ready();
    expect(result.current.alerts).toHaveLength(1);
    let operation!: Promise<void>;
    act(() => {
      operation = result.current.generate();
    });
    act(() => result.current.selectStudent('S002'));
    await waitFor(() => expect(result.current.state).not.toBeNull());
    await act(async () => {
      pending.resolve(recommendation);
      await operation;
    });
    expect(result.current.studentId).toBe('S002');
    expect(result.current.recommendation).toBeNull();
    expect(result.current.alerts).toEqual([]);
  });
  it('refreshes stale revisions without automatically resubmitting', async () => {
    const submit = vi.spyOn(api, 'round1').mockRejectedValue(new ApiError('STALE_PLAN', '志愿版本已变化'));
    const { result } = await ready();
    vi.mocked(api.state).mockResolvedValue({
      ...state,
      state_version: 3,
      plan_revision: 2,
      current_application: ['MATH_B', 'ART_A'],
    });
    await act(async () => {
      await result.current.submitPlan(['MATH_A', 'ART_A'], 0);
    });
    expect(submit).toHaveBeenCalledTimes(1);
    expect(result.current.state?.plan_revision).toBe(2);
    expect(result.current.error?.code).toBe('STALE_PLAN');
    expect(result.current.notice).toBe('');
  });
  it('refreshes seats and recalculates after NO_SEAT without claiming enrollment', async () => {
    vi.mocked(api.state).mockResolvedValue({ ...state, phase: 'ROUND2_OPEN' });
    vi.spyOn(api, 'round2').mockRejectedValue(new ApiError('NO_SEAT', '名额已用完'));
    const recommend = vi
      .spyOn(api, 'recommend')
      .mockResolvedValue({ ...recommendation, purpose: 'supplement' });
    const { result } = await ready();
    await act(async () => {
      await result.current.submitSection('MATH_A');
    });
    expect(recommend).toHaveBeenCalledWith('S001', 'supplement', expect.any(AbortSignal));
    expect(result.current.state?.enrolled_section_ids).toEqual([]);
    expect(result.current.error?.code).toBe('NO_SEAT');
  });
  it('submits only unenrolled sections in order and refreshes supplement recommendations once', async () => {
    vi.mocked(api.state).mockResolvedValue({
      ...state,
      phase: 'ROUND2_OPEN',
      enrolled_section_ids: ['MATH_A'],
    });
    const submit = vi.spyOn(api, 'round2').mockResolvedValue({ ok: true });
    const recommend = vi
      .spyOn(api, 'recommend')
      .mockResolvedValue({ ...recommendation, purpose: 'supplement' });
    const { result } = await ready();
    await act(async () => {
      await result.current.submitSupplementPlan(['MATH_A', 'ART_A', 'MATH_B']);
    });
    expect(submit.mock.calls).toEqual([
      ['S001', 'ART_A'],
      ['S001', 'MATH_B'],
    ]);
    expect(recommend).toHaveBeenCalledTimes(1);
    expect(recommend).toHaveBeenCalledWith('S001', 'supplement', expect.any(AbortSignal));
    expect(result.current.notice).toContain('成功补选 2 门课程');
  });
  it('stops a supplement plan after NO_SEAT and retains earlier enrollments', async () => {
    vi.mocked(api.state)
      .mockResolvedValueOnce({ ...state, phase: 'ROUND2_OPEN' })
      .mockResolvedValue({
        ...state,
        phase: 'ROUND2_OPEN',
        state_version: 1,
        enrolled_section_ids: ['ART_A'],
      });
    const submit = vi
      .spyOn(api, 'round2')
      .mockResolvedValueOnce({ ok: true })
      .mockRejectedValueOnce(new ApiError('NO_SEAT', '名额已用完'));
    const recommend = vi
      .spyOn(api, 'recommend')
      .mockResolvedValue({ ...recommendation, purpose: 'supplement', state_version: 1 });
    const { result } = await ready();
    await act(async () => {
      await result.current.submitSupplementPlan(['ART_A', 'MATH_A', 'MATH_B']);
    });
    expect(submit.mock.calls).toEqual([
      ['S001', 'ART_A'],
      ['S001', 'MATH_A'],
    ]);
    expect(result.current.state?.enrolled_section_ids).toEqual(['ART_A']);
    expect(result.current.error?.code).toBe('NO_SEAT');
    expect(recommend).toHaveBeenCalledTimes(1);
  });
  it('retains a successful submission when the following refresh fails', async () => {
    vi.spyOn(api, 'round1').mockResolvedValue({
      ok: true,
      student_state: {
        ...state,
        current_application: ['MATH_A', 'ART_A'],
        plan_revision: 1,
        state_version: 1,
      },
    });
    const { result } = await ready();
    vi.mocked(api.state).mockRejectedValue(new ApiError('NETWORK', 'offline'));
    await act(async () => {
      await result.current.submitPlan(['MATH_A', 'ART_A'], 0);
    });
    expect(result.current.state?.current_application).toEqual(['MATH_A', 'ART_A']);
    expect(result.current.notice).toContain('志愿已提交');
    expect(result.current.error?.code).toBe('REFRESH_FAILED');
  });
  it('sends complete preference scores and replaces recommendations after saving', async () => {
    const save = vi
      .spyOn(api, 'preferences')
      .mockResolvedValue({ ok: true, student_state: { ...state, state_version: 1 } });
    vi.spyOn(api, 'recommend').mockResolvedValue({ ...recommendation, state_version: 1 });
    const { result } = await ready();
    vi.mocked(api.state).mockResolvedValue({ ...state, state_version: 1 });
    const preferences = { ...catalog.students.S001.preferences, course_scores: { MATH: 80, ART: 99 } };
    await act(async () => {
      await result.current.savePreferences(preferences);
    });
    expect(save).toHaveBeenCalledWith('S001', preferences);
    expect(result.current.catalog?.students.S001.preferences.course_scores.ART).toBe(99);
    expect(result.current.recommendation?.state_version).toBe(1);
  });
  it('does not overwrite an accepted submission with an older state request', async () => {
    const { result } = await ready();
    const oldRead = deferred<typeof state>();
    const accepted = {
      ...state,
      state_version: 1,
      plan_revision: 1,
      current_application: ['MATH_A', 'ART_A'],
    };
    vi.mocked(api.state).mockReturnValueOnce(oldRead.promise).mockResolvedValue(accepted);
    vi.spyOn(api, 'round1').mockResolvedValue({ ok: true, student_state: accepted });
    act(() => result.current.retry());
    await act(async () => {
      await result.current.submitPlan(['MATH_A', 'ART_A'], 0);
    });
    await act(async () => {
      oldRead.resolve(state);
      await oldRead.promise;
    });
    expect(result.current.state?.plan_revision).toBe(1);
    expect(result.current.state?.current_application).toEqual(['MATH_A', 'ART_A']);
  });
  it('discards a recommendation if polling observes a phase change', async () => {
    const pending = deferred<Recommendation>();
    vi.spyOn(api, 'recommend').mockReturnValue(pending.promise);
    const { result } = await ready();
    let calculation!: Promise<void>;
    act(() => {
      calculation = result.current.generate();
    });
    vi.mocked(api.state).mockResolvedValue({ ...state, phase: 'ROUND2_OPEN', state_version: 1 });
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.state?.phase).toBe('ROUND2_OPEN'));
    await act(async () => {
      pending.resolve(recommendation);
      await calculation;
    });
    expect(result.current.recommendation).toBeNull();
    expect(result.current.calculating).toBe(false);
  });
  it('stops polling on unmount', async () => {
    const { unmount } = await ready();
    vi.useFakeTimers();
    const cancelTimer = vi.spyOn(globalThis, 'clearTimeout');
    unmount();
    expect(cancelTimer).toHaveBeenCalled();
    const calls = vi.mocked(api.state).mock.calls.length;
    await act(async () => {
      vi.advanceTimersByTime(60000);
    });
    expect(api.state).toHaveBeenCalledTimes(calls);
  });
});
