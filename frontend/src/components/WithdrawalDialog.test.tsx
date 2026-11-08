import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { WithdrawalDialog } from './WithdrawalDialog';
import { catalog, state } from '../test-fixtures';

afterEach(cleanup);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  });
});

it('withdraws the whole first-round application only after confirmation', () => {
  const onConfirm = vi.fn();
  const onClose = vi.fn();
  render(<WithdrawalDialog catalog={catalog} state={{ ...state, current_application: ['MATH_A', 'ART_A'] }}
    onConfirm={onConfirm} onClose={onClose} />);
  expect(onConfirm).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(onClose).toHaveBeenCalledOnce();
  expect(onConfirm).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认撤回志愿' }));
  expect(onConfirm).toHaveBeenCalledWith(['MATH_A', 'ART_A']);
});

it('requires an explicit second-round selection and supports partial or full withdrawal', () => {
  const onConfirm = vi.fn();
  render(<WithdrawalDialog catalog={catalog} state={{ ...state, phase: 'ROUND2_OPEN', enrolled_section_ids: ['MATH_A', 'ART_A'] }}
    onConfirm={onConfirm} onClose={vi.fn()} />);
  expect(screen.getByRole('button', { name: '确认退选（0 门）' })).toBeDisabled();
  fireEvent.click(screen.getByLabelText('退选 高等数学 MATH_A'));
  fireEvent.click(screen.getByRole('button', { name: '确认退选（1 门）' }));
  expect(onConfirm).toHaveBeenLastCalledWith(['MATH_A']);
  fireEvent.click(screen.getByLabelText('全选已录取课程'));
  fireEvent.click(screen.getByRole('button', { name: '确认退选（2 门）' }));
  expect(onConfirm).toHaveBeenLastCalledWith(['MATH_A', 'ART_A']);
});
