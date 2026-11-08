import { test, expect, type Page } from '@playwright/test';
import { catalog, state, recommendation, plan } from '../src/test-fixtures';

async function load(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('region', { name: '选课阶段' })).toBeVisible();
}
async function confirm(page: Page) {
  await page.getByRole('button', { name: '确认操作', exact: true }).click();
}

test('real API: preferences, first-round submit, draw, supplement a different student, close', async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  await request.post('/api/reset');
  await load(page);
  await page.getByRole('button', { name: '偏好设置', exact: true }).click();
  const slider = page.getByRole('slider', { name: '艺术鉴赏喜好分' });
  // Use the actual catalog label; the demo course can have a different title.
  const firstSlider = (await slider.count()) ? slider : page.getByRole('slider').first();
  await firstSlider.focus();
  await firstSlider.press('Home');
  await firstSlider.press('ArrowRight');
  await page.getByRole('button', { name: '保存偏好并重新推荐' }).click();
  await expect(page.locator('.preferences-saving')).toHaveCount(0, { timeout: 60000 });
  await page.getByRole('button', { name: '关闭偏好设置' }).click();
  await expect(page.getByRole('button', { name: '查看方案 1 详情' })).toBeVisible({ timeout: 60000 });
  await expect(page.getByTestId('course-block').first()).toBeVisible();
  await page.getByRole('combobox', { name: '选择周次' }).click();
  await page.getByRole('option', { name: '第 2 周' }).click();
  await expect(page.getByRole('combobox', { name: '选择周次' })).toContainText('第 2 周');
  await page.getByRole('button', { name: '提交所选方案' }).click();
  await expect(page.getByRole('dialog', { name: '确认提交第一轮志愿', exact: true })).toContainText(
    '不代表正式录取',
  );
  await confirm(page);
  await expect(page.getByRole('status')).toContainText('志愿已提交');
  await expect(page.getByTestId('course-block').first()).toBeVisible();
  await expect(page.locator('.timetable-panel')).toContainText('当前志愿');
  const firstState = await (await request.get('/api/state?student_id=S001')).json();
  expect(firstState.current_application.length).toBeGreaterThan(0);
  expect(firstState.enrolled_section_ids).toEqual([]);
  await page.getByRole('button', { name: '演示控制', exact: true }).click();
  await page.getByRole('button', { name: '结束第一轮并抽签', exact: true }).click();
  await confirm(page);
  await expect(page.locator('.phase-current')).toContainText('第二轮');
  await page.getByRole('button', { name: '录取结果', exact: true }).click();
  await expect(page.locator('.result-panel')).toContainText('已完成要求');
  await page.getByRole('combobox', { name: '选择学生' }).click();
  await page.getByRole('option', { name: 'S002 · 软件工程' }).click();
  await page.getByRole('button', { name: '选课工作台', exact: true }).click();
  await expect(page.getByRole('button', { name: '生成补选方案' })).toBeEnabled();
  await page.getByRole('button', { name: '生成补选方案' }).click();
  await page.getByRole('button', { name: '查看方案 1 详情' }).click({ timeout: 60000 });
  await expect(page.getByRole('button', { name: '补选此班' }).first()).toBeEnabled({ timeout: 60000 });
  await page.getByRole('button', { name: '补选此班' }).first().click();
  await expect
    .poll(
      async () =>
        (await (await request.get('/api/state?student_id=S002')).json()).enrolled_section_ids.length,
    )
    .toBe(1);
  await expect(page.getByRole('button', { name: '生成补选方案' })).toBeEnabled({ timeout: 60000 });
  await page.getByRole('button', { name: '录取结果', exact: true }).click();
  await expect(page.locator('.completion-grid')).not.toContainText('NaN');
  await page.getByRole('button', { name: '演示控制', exact: true }).click();
  await page.getByRole('button', { name: '关闭选课', exact: true }).click();
  await confirm(page);
  await expect(page.locator('.phase-current')).toContainText('已结束');
  await page.getByRole('button', { name: '录取结果', exact: true }).click();
  await expect(page.getByRole('heading', { name: '最终选课结果' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile layout has no page overflow and exposes a scrollable seven-day schedule', async ({
  page,
  request,
}) => {
  await request.post('/api/reset');
  await page.setViewportSize({ width: 390, height: 844 });
  await load(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const schedule = page.locator('.schedule-scroll');
  expect(await schedule.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  await page.getByRole('button', { name: '生成推荐方案' }).click();
  await expect(page.getByRole('button', { name: '查看方案 1 详情' })).toBeVisible({ timeout: 60000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });
});

test('alerts, explicit acknowledgement, and changed-section comparison', async ({ page }) => {
  let pending = true;
  const application = { ...state, current_application: ['MATH_A', 'ART_A'], plan_revision: 1 };
  await page.route('**/api/catalog', (route) => route.fulfill({ json: catalog }));
  await page.route('**/api/state?*', (route) => route.fulfill({ json: application }));
  await page.route('**/api/alerts?*', (route) =>
    route.fulfill({
      json: {
        state_version: 0,
        alerts: pending
          ? [
              {
                id: 'A1',
                student_id: 'S001',
                section_id: 'MATH_A',
                plan_revision: 1,
                baseline_prob: 1,
                current_prob: 0.5,
                status: 'PENDING',
                created_at: 1,
              },
            ]
          : [],
      },
    }),
  );
  await page.route('**/api/recommend', (route) =>
    route.fulfill({
      json: {
        ...recommendation,
        purpose: 'adjustment',
        plan_revision: 1,
        current_plan: plan,
        plans: [
          {
            ...plan,
            section_ids: ['MATH_B', 'ART_A'],
            comparison: {
              changed_course_count: 1,
              preference_delta: -2,
              risk_improvement: 0.2,
              fallback_coverage_delta: 0,
              switched_sections: [{ course_id: 'MATH', old_section_id: 'MATH_A', new_section_id: 'MATH_B' }],
              added_course_ids: [],
              removed_course_ids: [],
            },
          },
        ],
      },
    }),
  );
  await page.route('**/api/alerts/A1/ack', (route) => {
    pending = false;
    return route.fulfill({ json: { ok: true, student_state: application } });
  });
  await load(page);
  await page.getByRole('button', { name: '风险提醒，1 条待处理' }).click();
  await expect(page.locator('.alert-card')).toContainText('50.0%');
  await page.getByRole('button', { name: '查看调整方案' }).click();
  await page.getByRole('button', { name: '查看方案 1 详情' }).click();
  await expect(page.locator('.changes')).toContainText('换班');
  await expect(page.locator('.comparison-metrics')).toContainText('-2.0 分');
  await expect(page.locator('.comparison-metrics')).toContainText('-20.0 个百分点');
  await page.getByRole('button', { name: '关闭方案详情' }).click();
  await page.getByRole('button', { name: '风险提醒，1 条待处理' }).click();
  await page.getByRole('button', { name: '保留当前志愿' }).click();
  await expect(page.getByRole('status')).toContainText('已保留当前志愿');
  await expect(page.locator('.alert-card')).toHaveCount(0);
});

test('different empty-search states are not incorrectly described as infeasible', async ({ page }) => {
  let limited = true;
  await page.route('**/api/catalog', (route) => route.fulfill({ json: catalog }));
  await page.route('**/api/state?*', (route) => route.fulfill({ json: state }));
  await page.route('**/api/alerts?*', (route) => route.fulfill({ json: { state_version: 0, alerts: [] } }));
  await page.route('**/api/recommend', (route) =>
    route.fulfill({
      json: {
        ...recommendation,
        plans: [],
        decision: 'NO_PLAN',
        search_status: limited ? 'LIMIT_REACHED' : 'INFEASIBLE',
      },
    }),
  );
  await load(page);
  await page.getByRole('button', { name: '生成推荐方案' }).click();
  await expect(page.getByRole('heading', { name: '暂未找到候选方案' })).toBeVisible();
  limited = false;
  await page.getByRole('button', { name: '生成推荐方案' }).click();
  await expect(page.getByRole('heading', { name: '没有找到完整方案' })).toBeVisible();
});

test('offline startup can be retried without a blank screen', async ({ page }) => {
  let offline = true;
  await page.route('**/api/catalog', (route) => (offline ? route.abort() : route.fulfill({ json: catalog })));
  await page.route('**/api/state?*', (route) => route.fulfill({ json: state }));
  await page.route('**/api/alerts?*', (route) => route.fulfill({ json: { state_version: 0, alerts: [] } }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('无法连接');
  offline = false;
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.getByRole('heading', { name: '我的选课需求' })).toBeVisible();
});
