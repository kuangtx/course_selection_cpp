import type {
  Alert,
  Catalog,
  MutationResult,
  Preferences,
  Purpose,
  Recommendation,
  StudentState,
  SimulationStatus,
} from '../types';

const errors: Record<string, string> = {
  NOT_ENROLLED: '部分课程已不在录取列表中，已刷新状态，请重新选择。',
  DEMO_NEEDS_APPLICATION: '请先为 S001 提交第一轮志愿，再开始模拟，以建立风险提醒基准。',
  WRONG_PHASE: '选课阶段已变化，已刷新页面，请按当前阶段操作。',
  STALE_PLAN: '志愿已在其他页面修改，已刷新最新志愿，请重新生成方案后确认。',
  NO_SEAT: '这个班次的名额刚刚用完，已刷新余量并重新推荐。',
  TIME_CONFLICT: '这个班次与已选课程时间冲突，请选择其他方案。',
  DUPLICATE_COURSE: '同一门课程只能选择一个班次。',
  INVALID_PLAN: '方案不满足选课要求，请重新生成方案。',
  ALERT_EXPIRED: '原志愿已变化，这条提醒已经失效。',
  ALERT_NOT_ACTIVE: '这条提醒已处理或失效。',
  INVALID_PREFERENCES: '请检查课程喜好分和早课偏好。',
  STUDENT_NOT_FOUND: '找不到该学生，请重新加载基础数据。',
};
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public detail?: string,
  ) {
    super(message);
  }
}
async function request<T>(
  path: string,
  body?: unknown,
  method = body === undefined ? 'GET' : 'POST',
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}${path}`, {
      method,
      signal: controller.signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError('BAD_RESPONSE', '接口未返回有效数据，请检查后端服务与代理设置。');
    }
    if (!response.ok) {
      const code = typeof data.code === 'string' ? data.code : `HTTP_${response.status}`;
      const detail =
        typeof data.message === 'string'
          ? data.message
          : typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data.detail ?? '');
      throw new ApiError(
        code,
        errors[code] ||
          (response.status === 422 ? '请求参数未通过校验，请检查输入后重试。' : '请求未完成，请稍后重试。'),
        detail,
      );
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError || signal?.aborted) throw error;
    if (controller.signal.aborted)
      throw new ApiError('TIMEOUT', '请求超时。提交结果可能已生效，请刷新状态后再操作。');
    throw new ApiError('NETWORK', '无法连接选课服务，请确认后端已启动后重试。');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}
export const api = {
  simulation: (signal?: AbortSignal) =>
    request<SimulationStatus>('/demo/simulation', undefined, 'GET', signal),
  simulationControl: (action: 'start' | 'stop') =>
    request<{ ok: true; simulation: SimulationStatus }>(`/demo/simulation/${action}`, {}, 'POST'),
  catalog: (signal?: AbortSignal) => request<Catalog>('/catalog', undefined, 'GET', signal),
  state: (id: string, signal?: AbortSignal) =>
    request<StudentState>(`/state?student_id=${encodeURIComponent(id)}`, undefined, 'GET', signal),
  alerts: (id: string, signal?: AbortSignal) =>
    request<{ alerts: Alert[]; state_version: number }>(
      `/alerts?student_id=${encodeURIComponent(id)}`,
      undefined,
      'GET',
      signal,
    ),
  preferences: (id: string, preferences: Preferences) =>
    request<MutationResult>(`/students/${encodeURIComponent(id)}/preferences`, { preferences }, 'PATCH'),
  recommend: (id: string, purpose: Purpose, signal?: AbortSignal) =>
    request<Recommendation>('/recommend', { student_id: id, purpose, limit: -1 }, 'POST', signal),
  round1: (id: string, section_ids: string[], revision: number) =>
    request<MutationResult>('/round1/submit', {
      student_id: id,
      section_ids,
      expected_plan_revision: revision,
    }),
  round2: (id: string, section_id: string) =>
    request<MutationResult>('/round2/submit', { student_id: id, section_id }),
  withdrawRound1: (id: string, revision: number) =>
    request<MutationResult>('/round1/withdraw', { student_id: id, expected_plan_revision: revision }),
  withdrawRound2: (id: string, section_ids: string[], revision: number) =>
    request<MutationResult>('/round2/withdraw', {
      student_id: id, section_ids, expected_plan_revision: revision,
    }),
  acknowledge: (id: string) =>
    request<MutationResult>(`/alerts/${encodeURIComponent(id)}/ack`, undefined, 'POST'),
  control: (action: 'round1/draw' | 'close' | 'reset') =>
    request<MutationResult>(`/${action}`, undefined, 'POST'),
};
