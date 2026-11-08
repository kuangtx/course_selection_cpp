import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type {
  Alert,
  Catalog,
  MutationResult,
  Preferences,
  Purpose,
  Recommendation,
  StudentState,
} from '../types';

export function useSelection() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [studentId, setStudentId] = useState('');
  const [state, setState] = useState<StudentState | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [offline, setOffline] = useState(false);
  const epoch = useRef(0);
  const latestState = useRef<StudentState | null>(null);
  const readSequence = useRef(0);
  const recSequence = useRef(0);
  const recAbort = useRef<AbortController | null>(null);
  const mutationLock = useRef(false);

  const invalidate = useCallback(() => {
    ++recSequence.current;
    recAbort.current?.abort();
    setRecommendation(null);
    setCalculating(false);
  }, []);
  const applyState = useCallback(
    (next: StudentState) => {
      const previous = latestState.current;
      if (
        previous &&
        (next.phase !== previous.phase ||
          next.plan_revision !== previous.plan_revision ||
          next.state_version < previous.state_version)
      )
        invalidate();
      latestState.current = next;
      setState(next);
      setUpdatedAt(new Date());
    },
    [invalidate],
  );
  const report = useCallback((err: unknown) => {
    setError(err instanceof ApiError ? err : new ApiError('UNKNOWN', '操作未完成，请刷新后重试。'));
  }, []);

  const loadCatalog = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.catalog(signal);
        if (signal?.aborted) return;
        setCatalog(data);
        setStudentId((current) => (data.students[current] ? current : Object.keys(data.students)[0] || ''));
        if (!Object.keys(data.students).length)
          throw new ApiError('EMPTY_CATALOG', '暂无样例学生，请先配置后端数据。');
      } catch (err) {
        if (!signal?.aborted) report(err);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [report],
  );
  useEffect(() => {
    const controller = new AbortController();
    void loadCatalog(controller.signal);
    return () => controller.abort();
  }, [loadCatalog]);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      if (!studentId) return;
      const session = epoch.current;
      const sequence = ++readSequence.current;
      const [next, notifications] = await Promise.all([
        api.state(studentId, signal),
        api.alerts(studentId, signal),
      ]);
      if (signal?.aborted || session !== epoch.current || sequence !== readSequence.current) return;
      applyState(next);
      setAlerts(
        next.phase === 'ROUND1_OPEN'
          ? notifications.alerts.filter(
              (a) =>
                a.student_id === studentId &&
                a.plan_revision === next.plan_revision &&
                a.status === 'PENDING',
            )
          : [],
      );
      setOffline(false);
      setError((current) => (current?.code === 'POLL_FAILED' ? null : current));
      return next;
    },
    [studentId, applyState],
  );

  useEffect(() => {
    ++epoch.current;
    ++readSequence.current;
    latestState.current = null;
    setState(null);
    setAlerts([]);
    invalidate();
    setError(null);
    setNotice('');
    setUpdatedAt(null);
    setOffline(false);
    if (!studentId) return;
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        if (!mutationLock.current) await refresh(controller.signal);
      } catch (err) {
        if (active) {
          setOffline(true);
          setError(
            new ApiError(
              'POLL_FAILED',
              '暂时无法更新选课状态，请检查后端连接后刷新。',
              err instanceof Error ? err.message : undefined,
            ),
          );
        }
      } finally {
        if (active) timer = setTimeout(poll, 12000);
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
      ++epoch.current;
      ++readSequence.current;
      recAbort.current?.abort();
    };
  }, [studentId, refresh, invalidate, report]);

  const generate = useCallback(
    async (purpose?: Purpose) => {
      const current = latestState.current;
      if (!current || current.phase === 'CLOSED' || current.phase === 'DRAWING') return;
      const chosen =
        purpose ||
        (current.phase === 'ROUND2_OPEN'
          ? 'supplement'
          : current.current_application.length
            ? 'adjustment'
            : 'initial');
      recAbort.current?.abort();
      const controller = new AbortController();
      recAbort.current = controller;
      const sequence = ++recSequence.current;
      const session = epoch.current;
      setCalculating(true);
      setError(null);
      setNotice('');
      setRecommendation(null);
      try {
        const result = await api.recommend(studentId, chosen, controller.signal);
        if (sequence !== recSequence.current || session !== epoch.current || controller.signal.aborted)
          return;
        const now = latestState.current;
        if (
          !now ||
          now.phase !== current.phase ||
          result.plan_revision !== now.plan_revision ||
          result.state_version < current.state_version
        ) {
          throw new ApiError('STALE_RESULT', '状态已变化，请刷新后重新生成方案。');
        }
        setRecommendation(result);
      } catch (err) {
        if (sequence === recSequence.current && session === epoch.current && !controller.signal.aborted) {
          report(err);
          try {
            await refresh();
          } catch {
            setOffline(true);
          }
        }
      } finally {
        if (sequence === recSequence.current && session === epoch.current) setCalculating(false);
      }
    },
    [studentId, refresh, report],
  );

  const mutate = useCallback(
    async (
      operation: () => Promise<MutationResult>,
      success: string,
      after?: () => Promise<void>,
      clearPlans = true,
    ) => {
      if (mutationLock.current) return;
      mutationLock.current = true;
      setBusy(true);
      setError(null);
      setNotice('');
      const session = epoch.current;
      ++readSequence.current;
      if (clearPlans) invalidate();
      try {
        const response = await operation();
        if (session !== epoch.current) return;
        if (response.student_state) applyState(response.student_state);
        setNotice(success);
        // A refresh failure must not relabel an accepted write as a failed submission.
        try {
          await refresh();
          if (after) await after();
        } catch {
          setOffline(true);
          setError(new ApiError('REFRESH_FAILED', '操作已成功，但最新数据暂时无法读取，请刷新状态。'));
        }
      } catch (err) {
        if (session !== epoch.current) return;
        invalidate();
        report(err);
        try {
          const fresh = await refresh();
          if (err instanceof ApiError && err.code === 'NO_SEAT' && fresh?.phase === 'ROUND2_OPEN') {
            await generate('supplement');
            report(err);
          }
        } catch {
          setOffline(true);
        }
      } finally {
        mutationLock.current = false;
        setBusy(false);
      }
    },
    [applyState, generate, invalidate, refresh, report],
  );

  const savePreferences = (preferences: Preferences) =>
    mutate(
      () => api.preferences(studentId, preferences),
      '偏好已保存，正在按新偏好重新生成方案。',
      async () => {
        setCatalog((current) =>
          current
            ? {
                ...current,
                students: {
                  ...current.students,
                  [studentId]: { ...current.students[studentId], preferences },
                },
              }
            : current,
        );
        await generate();
      },
    );
  const submitPlan = (ids: string[], revision: number) =>
    mutate(() => api.round1(studentId, ids, revision), '志愿已提交，等待第一轮抽签；提交不代表正式录取。');
  const withdrawPlan = (revision: number) =>
    mutate(() => api.withdrawRound1(studentId, revision), '第一轮志愿已撤回，可重新生成并提交方案。');
  const withdrawSections = (ids: string[], revision: number) =>
    mutate(() => api.withdrawRound2(studentId, ids, revision), '退选成功，名额已释放，可重新生成补选方案。');
  const submitSection = (id: string) =>
    mutate(
      () => api.round2(studentId, id),
      '补选成功，这门课程已正式录取。',
      () => generate('supplement'),
    );
  const submitSupplementPlan = (ids: string[]) => {
    const enrolledIds = new Set(latestState.current?.enrolled_section_ids || []);
    const pendingIds = ids.filter((id) => !enrolledIds.has(id));
    const success = pendingIds.length
      ? `补选方案已提交，成功补选 ${pendingIds.length} 门课程。`
      : '所选方案中的课程均已录取。';
    return mutate(
      async () => {
        let response: MutationResult = { ok: true };
        for (const id of pendingIds) response = await api.round2(studentId, id);
        return response;
      },
      success,
      async () => {
        await generate('supplement');
        setNotice(success);
      },
    );
  };
  const acknowledge = (id: string) =>
    mutate(() => api.acknowledge(id), '已保留当前志愿，并确认这条提醒。', undefined, false);
  const control = (action: 'round1/draw' | 'close' | 'reset') =>
    mutate(
      () => api.control(action),
      action === 'reset'
        ? '演示数据已重置。'
        : action === 'close'
          ? '选课已结束，可查看最终课表。'
          : '抽签已完成，第二轮补选已开放。',
      action === 'reset'
        ? async () => {
            invalidate();
            setAlerts([]);
            await loadCatalog();
          }
        : undefined,
    );
  return {
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
    selectStudent: (id: string) => {
      if (!mutationLock.current) {
        ++epoch.current;
        invalidate();
        setStudentId(id);
        setState(null);
        setAlerts([]);
        setNotice('');
        setError(null);
      }
    },
    generate,
    savePreferences,
    submitPlan,
    withdrawPlan,
    withdrawSections,
    submitSection,
    submitSupplementPlan,
    acknowledge,
    control,
    retry: () => {
      setError(null);
      if (!catalog || !studentId) void loadCatalog();
      else void refresh().catch(report);
    },
    dismissError: () => setError(null),
  };
}
