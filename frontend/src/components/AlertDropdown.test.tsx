import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AlertDropdown } from './AlertDropdown';
import { catalog } from '../test-fixtures';
import type { Alert } from '../types';

afterEach(cleanup);
const alerts: Alert[] = [
  {
    id: 'A1',
    student_id: 'S001',
    section_id: 'MATH_A',
    plan_revision: 0,
    baseline_prob: 1,
    current_prob: 0.5,
    status: 'PENDING',
    created_at: 1,
  },
];
const props = { catalog, phase: 'ROUND1_OPEN' as const, disabled: false, dirty: false };

it('opens only on click, closes on Escape/outside click, and restores keyboard focus', () => {
  render(<AlertDropdown {...props} alerts={[]} onAdjust={vi.fn()} onKeep={vi.fn()} />);
  const bell = screen.getByRole('button', { name: '风险提醒，0 条待处理' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(bell);
  expect(bell).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('暂无待处理提醒')).toBeVisible();
  fireEvent.keyDown(screen.getByRole('button', { name: '关闭风险提醒' }), { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(bell).toHaveFocus();
  fireEvent.click(bell);
  fireEvent.pointerDown(document.body);
  expect(bell).toHaveAttribute('aria-expanded', 'false');
});

it('opening is read-only, keep acknowledges only the chosen alert, and adjustment closes the panel', () => {
  const onKeep = vi.fn();
  const onAdjust = vi.fn();
  render(<AlertDropdown {...props} alerts={alerts} onAdjust={onAdjust} onKeep={onKeep} />);
  fireEvent.click(screen.getByRole('button', { name: '风险提醒，1 条待处理' }));
  expect(screen.getByText(/50.0%/)).toBeVisible();
  expect(onKeep).not.toHaveBeenCalled();
  expect(onAdjust).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '保留当前志愿' }));
  expect(onKeep).toHaveBeenCalledWith('A1');
  fireEvent.click(screen.getByRole('button', { name: '查看调整方案' }));
  expect(onAdjust).toHaveBeenCalledOnce();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('blocks adjustment for unsaved preferences and closes when switching student or phase', () => {
  const callbacks = { onAdjust: vi.fn(), onKeep: vi.fn() };
  const { rerender } = render(<AlertDropdown key="S001" {...props} {...callbacks} alerts={alerts} dirty />);
  fireEvent.click(screen.getByRole('button', { name: '风险提醒，1 条待处理' }));
  expect(screen.getByRole('button', { name: '查看调整方案' })).toBeDisabled();
  rerender(<AlertDropdown key="S002" {...props} {...callbacks} alerts={[]} />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '风险提醒，0 条待处理' }));
  rerender(<AlertDropdown key="S002" {...props} {...callbacks} alerts={[]} phase="ROUND2_OPEN" />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
