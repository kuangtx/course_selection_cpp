import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api/client';
import { simulationStatus } from '../test-fixtures';
import { useDemoSimulation } from './useDemoSimulation';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
async function tick(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

it('stops polling a missing endpoint until explicit retry', async () => {
  const read = vi.spyOn(api, 'simulation').mockRejectedValue(new ApiError('HTTP_404', 'missing'));
  const { result } = renderHook(() => useDemoSimulation(true, vi.fn()));
  await tick();
  expect(result.current.error).toContain('当前后端尚未提供');
  await tick(12000);
  expect(read).toHaveBeenCalledTimes(1);
  read.mockResolvedValue(simulationStatus);
  act(() => result.current.retry());
  await tick();
  expect(read).toHaveBeenCalledTimes(2);
  expect(result.current.error).toBe('');
});

it('continues polling while running off-page and refreshes only changed server versions', async () => {
  const read = vi
    .spyOn(api, 'simulation')
    .mockResolvedValue({ ...simulationStatus, running: true, stage: 'round1' });
  const refresh = vi.fn();
  const { rerender, unmount } = renderHook(({ visible }) => useDemoSimulation(visible, refresh), {
    initialProps: { visible: true },
  });
  await tick();
  rerender({ visible: false });
  await tick(1500);
  expect(read).toHaveBeenCalledTimes(2);
  expect(refresh).toHaveBeenCalledTimes(1);
  read.mockResolvedValue({ ...simulationStatus, running: true, stage: 'round1', state_version: 2 });
  await tick(1500);
  expect(refresh).toHaveBeenCalledTimes(2);
  unmount();
  await tick(10000);
  expect(read).toHaveBeenCalledTimes(3);
});

it('keeps rejected start instructions visible when status polling succeeds', async () => {
  vi.spyOn(api, 'simulation').mockResolvedValue(simulationStatus);
  const write = vi
    .spyOn(api, 'simulationControl')
    .mockRejectedValue(new ApiError('DEMO_NEEDS_APPLICATION', '请先为 S001 提交志愿'));
  const { result } = renderHook(() => useDemoSimulation(true, vi.fn()));
  await tick();
  act(() => {
    result.current.start();
    result.current.start();
  });
  await tick(3000);
  expect(write).toHaveBeenCalledTimes(1);
  expect(result.current.error).toContain('S001');
});
