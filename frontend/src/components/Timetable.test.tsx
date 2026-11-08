import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Timetable } from './Timetable';
import { catalog, state } from '../test-fixtures';
afterEach(cleanup);
describe('term-aware timetable', () => {
  it('filters odd/even weeks and renders the last Sunday period without truncating the term', () => {
    const props = {
      catalog,
      state,
      sectionIds: ['MATH_A', 'MATH_B'],
      enrolledIds: [],
      setWeek: vi.fn(),
      label: '推荐预览',
    };
    const { rerender } = render(<Timetable {...props} week={1} />);
    expect(screen.getAllByTestId('course-block')).toHaveLength(1);
    expect(screen.getByTitle(/MATH_A/)).toHaveStyle({ gridColumn: '2', gridRow: '2 / span 2' });
    expect(screen.queryByTitle(/MATH_B/)).not.toBeInTheDocument();
    rerender(<Timetable {...props} week={2} />);
    expect(screen.queryByTitle(/MATH_A/)).not.toBeInTheDocument();
    expect(screen.getByTitle(/MATH_B/)).toHaveStyle({ gridColumn: '8', gridRow: '13 / span 2' });
    expect(screen.getByText('周日')).toBeInTheDocument();
    expect(screen.getByText('13')).toBeInTheDocument();
  });
  it('labels pending and enrolled courses with text, not only color', () => {
    render(
      <Timetable
        catalog={catalog}
        state={state}
        sectionIds={['MATH_A', 'ART_A']}
        enrolledIds={['ART_A']}
        week={1}
        setWeek={vi.fn()}
        label="当前志愿"
      />,
    );
    expect(screen.getByText('申请中')).toBeInTheDocument();
    expect(screen.getByText('已录取')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上一周' })).toBeDisabled();
  });
  it('shows live applicants in round one and occupied seats in round two', () => {
    const props = {
      catalog, sectionIds: ['MATH_A'], enrolledIds: [], week: 1,
      setWeek: vi.fn(), label: '推荐预览',
    };
    const firstRound = { ...state, applicant_counts: { MATH_A: 3 } };
    const { rerender } = render(<Timetable {...props} state={firstRound} />);
    expect(screen.getByLabelText('申请人数/容量：3/1，超额 2 人')).toHaveTextContent('申请 3 · 容量 1');
    rerender(<Timetable {...props} state={{ ...firstRound, applicant_counts: { MATH_A: 4 } }} />);
    expect(screen.getByLabelText('申请人数/容量：4/1，超额 3 人')).toBeInTheDocument();
    rerender(<Timetable {...props} state={{ ...firstRound, phase: 'ROUND2_OPEN', remaining: { MATH_A: 0 } }} />);
    expect(screen.getByLabelText('已选人数/容量：1/1')).toHaveTextContent('已选 1 · 容量 1');
    expect(screen.queryByText('申请 4 · 容量 1')).not.toBeInTheDocument();
  });
  it('defaults missing applicants to zero and preserves unknown second-round counts', () => {
    const props = {
      catalog, sectionIds: ['MATH_A'], enrolledIds: [], week: 1,
      setWeek: vi.fn(), label: '推荐预览',
    };
    const { rerender } = render(<Timetable {...props} state={state} />);
    expect(screen.getByLabelText('申请人数/容量：0/1')).toBeInTheDocument();
    rerender(<Timetable {...props} state={{ ...state, applicant_counts: {} }} />);
    expect(screen.getByLabelText('申请人数/容量：0/1')).toBeInTheDocument();
    rerender(<Timetable {...props} state={{ ...state, phase: 'ROUND2_OPEN', remaining: {} }} />);
    expect(screen.getByText('已选 — · 容量 1')).toBeInTheDocument();
  });
});
