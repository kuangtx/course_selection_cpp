import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { SimulationStatus } from '../types';

export function useDemoSimulation(visible: boolean, onChange: () => void) {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const callback = useRef(onChange);
  callback.current = onChange;
  const version = useRef<number | null>(null);
  const sequence = useRef(0);
  const mutation = useRef(false);
  const mounted = useRef(true);
  const active = visible || !!status?.running;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      ++sequence.current;
    };
  }, []);

  const errorMessage = (err: unknown) =>
    err instanceof ApiError
      ? err.code === 'HTTP_404'
        ? '当前后端尚未提供自动选课功能，请启动包含本次更新的后端服务，然后点击重试。'
        : err.message
      : '无法读取模拟状态，请重试。';
  function accept(next: SimulationStatus) {
    if (!next.stage || !Array.isArray(next.events)) throw new Error('Invalid simulation status');
    setStatus(next);
    setError('');
    if (version.current !== next.state_version) {
      version.current = next.state_version;
      callback.current();
    }
  }
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    let unsupported = false;
    async function poll() {
      const request = ++sequence.current;
      try {
        if (!mutation.current) {
          const next = await api.simulation(controller.signal);
          if (alive && request === sequence.current) accept(next);
        }
      } catch (err) {
        if (alive && request === sequence.current) {
          setError(errorMessage(err));
          if (err instanceof ApiError && err.code === 'HTTP_404') {
            unsupported = true;
            setStatus(null);
          }
        }
      } finally {
        if (alive && !unsupported) timer = setTimeout(poll, 1500);
      }
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
      ++sequence.current;
    };
  }, [active, retry]);

  async function control(action: 'start' | 'stop') {
    if (mutation.current) return;
    mutation.current = true;
    ++sequence.current;
    setBusy(true);
    setError('');
    setActionError('');
    try {
      const result = await api.simulationControl(action);
      if (mounted.current) accept(result.simulation);
    } catch (err) {
      if (mounted.current) setActionError(errorMessage(err));
    } finally {
      mutation.current = false;
      if (mounted.current) {
        setBusy(false);
        setRetry((n) => n + 1);
      }
    }
  }
  return {
    status,
    error: error || actionError,
    busy,
    start: () => void control('start'),
    stop: () => void control('stop'),
    retry: () => {
      setActionError('');
      setRetry((n) => n + 1);
    },
  };
}
