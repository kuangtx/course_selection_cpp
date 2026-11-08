import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';
import { useSelection } from './hooks/useSelection';
import { catalog, recommendation, state } from './test-fixtures';

vi.mock('./hooks/useSelection', () => ({ useSelection: vi.fn() }));
afterEach(cleanup);

it('returns to the submitted application instead of leaving an empty candidate timetable', () => {
  const controller: ReturnType<typeof useSelection> = {
    catalog,
    studentId: 'S001',
    state,
    alerts: [],
    recommendation: null,
    error: null,
    notice: '',
    loading: false,
    calculating: false,
    busy: false,
    updatedAt: new Date(),
    offline: false,
    selectStudent: vi.fn(),
    generate: vi.fn(async () => {}),
    savePreferences: vi.fn(async () => {}),
    submitPlan: vi.fn(async () => {}),
    withdrawPlan: vi.fn(async () => {}),
    withdrawSections: vi.fn(async () => {}),
    submitSection: vi.fn(async () => {}),
    submitSupplementPlan: vi.fn(async () => {}),
    acknowledge: vi.fn(async () => {}),
    control: vi.fn(async () => {}),
    retry: vi.fn(),
    dismissError: vi.fn(),
  };
  vi.mocked(useSelection).mockReturnValue(controller);
  const { rerender } = render(<App />);
  vi.mocked(useSelection).mockReturnValue({ ...controller, recommendation });
  rerender(<App />);
  expect(within(screen.getByRole('region', { name: '每周课表' })).getByText(/推荐预览/)).toBeInTheDocument();
  vi.mocked(useSelection).mockReturnValue({
    ...controller,
    state: { ...state, plan_revision: 1, current_application: ['MATH_A', 'ART_A'] },
  });
  rerender(<App />);
  const timetable = screen.getByRole('region', { name: '每周课表' });
  expect(within(timetable).getByText(/当前志愿/)).toBeInTheDocument();
  expect(within(timetable).getAllByText('申请中')).toHaveLength(2);
  expect(within(timetable).getAllByTestId('course-block')).toHaveLength(2);
});
