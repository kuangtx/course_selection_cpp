import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { catalog, state, recommendation, plan, simulationStatus } from '../src/test-fixtures';

async function mount(page: Page, candidates = recommendation, courseCatalog = catalog, studentState = state) {
  await page.setContent(
    '<html lang="zh-CN"><head><meta charset="utf-8" /></head><body><div id="root"></div></body></html>',
  );
  await page.evaluate(
    ({ catalog, state, recommendation, simulation }) => {
      window.fetch = async (input, init) => {
        const url = String(input);
        let data: unknown;
        if (url.includes('/demo/simulation')) {
          if (url.endsWith('/start')) {
            simulation.running = true;
            simulation.stage = 'round1';
            simulation.active_student = 'S002';
          } else if (url.endsWith('/stop')) {
            simulation.running = false;
            simulation.stage = 'stopped';
            simulation.active_student = null;
          }
          data = url.endsWith('/start') || url.endsWith('/stop') ? { ok: true, simulation } : simulation;
        } else if (url.includes('/catalog')) data = catalog;
        else if (url.includes('/preferences')) {
          catalog.students.S001.preferences = JSON.parse(String(init?.body)).preferences;
          state.state_version += 1;
          data = { ok: true, student_state: state };
        } else if (url.includes('/round1/withdraw') || url.includes('/round2/withdraw')) {
          const payload = JSON.parse(String(init?.body));
          if (payload.student_id !== 'S001' || payload.expected_plan_revision !== state.plan_revision)
            throw new Error('Invalid withdrawal request');
          if (url.includes('/round1/withdraw')) {
            for (const id of state.current_application) state.applicant_counts[id] -= 1;
            state.current_application = [];
          } else {
            for (const id of payload.section_ids) state.remaining[id] += 1;
            state.enrolled_section_ids = state.enrolled_section_ids.filter((id) => !payload.section_ids.includes(id));
          }
          state.plan_revision += 1;
          state.state_version += 1;
          data = { ok: true, student_state: state };
        } else if (url.includes('/round2/submit')) {
          const payload = JSON.parse(String(init?.body));
          state.enrolled_section_ids.push(payload.section_id);
          state.remaining[payload.section_id] -= 1;
          state.plan_revision += 1;
          state.state_version += 1;
          data = { ok: true, student_state: state };
        } else if (url.includes('/round1/submit')) {
          const payload = JSON.parse(String(init?.body));
          if (payload.expected_plan_revision !== state.plan_revision) throw new Error('Wrong plan revision');
          state.current_application = payload.section_ids;
          state.plan_revision += 1;
          state.state_version += 1;
          data = { ok: true, student_state: state };
        } else if (url.includes('/recommend'))
          data = { ...recommendation, state_version: state.state_version, plan_revision: state.plan_revision };
        else if (url.includes('/alerts')) data = { alerts: [], state_version: state.state_version };
        else data = state;
        return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
      };
    },
    { catalog: courseCatalog, state: studentState, recommendation: candidates, simulation: simulationStatus },
  );
  const assets = path.resolve('dist/assets');
  const files = fs.readdirSync(assets);
  await page.addStyleTag({
    content: fs.readFileSync(path.join(assets, files.find((f) => f.endsWith('.css'))!), 'utf8'),
  });
  await page.addScriptTag({
    type: 'module',
    content: fs.readFileSync(path.join(assets, files.find((f) => f.endsWith('.js'))!), 'utf8'),
  });
  await expect(page.getByRole('region', { name: '选课阶段' })).toBeVisible();
}

test('first-round withdrawal can be cancelled, confirmed and resubmitted', async ({ page }) => {
  await mount(page, recommendation, catalog, { ...state, current_application: ['MATH_A', 'ART_A'],
    applicant_counts: { MATH_A: 1, MATH_B: 0, ART_A: 1 }, plan_revision: 1 });
  await page.getByRole('button', { name: '撤回志愿', exact: true }).click();
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await expect(page.getByTestId('course-block')).toHaveCount(2);
  await page.getByRole('button', { name: '撤回志愿', exact: true }).click();
  await page.screenshot({ path: 'test-results/withdrawal-round1.png' });
  await page.getByRole('button', { name: '确认撤回志愿', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('第一轮志愿已撤回');
  await expect(page.getByTestId('course-block')).toHaveCount(0);
  await page.getByRole('button', { name: '生成推荐方案', exact: true }).click();
  await page.getByRole('button', { name: '提交所选方案' }).click();
  await page.getByRole('button', { name: '确认操作', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('志愿已提交');
  await expect(page.getByTestId('course-block')).toHaveCount(2);
});

test('second-round withdrawal releases a selected course and allows supplementing again', async ({ page }) => {
  await mount(page, { ...recommendation, purpose: 'supplement' }, catalog, {
    ...state, phase: 'ROUND2_OPEN', enrolled_section_ids: ['MATH_A', 'ART_A'],
    remaining: { MATH_A: 0, MATH_B: 2, ART_A: 1 }, plan_revision: 1,
  });
  await page.getByRole('button', { name: '退选课程', exact: true }).click();
  await page.getByLabel('退选 艺术鉴赏 ART_A').check();
  await page.screenshot({ path: 'test-results/withdrawal-round2.png' });
  await page.getByRole('button', { name: '确认退选（1 门）', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('退选成功');
  await expect(page.getByTestId('course-block')).toHaveCount(1);
  await page.getByRole('button', { name: '生成补选方案', exact: true }).click();
  await expect(page.getByLabel('已选人数/容量：0/2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '提交所选方案' }).click();
  await page.getByRole('button', { name: '确认操作', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('成功补选 1 门');
  await page.getByRole('button', { name: '录取结果', exact: true }).click();
  await page.getByRole('button', { name: '退选课程', exact: true }).click();
  await page.getByLabel('全选已录取课程').check();
  await page.getByRole('button', { name: '确认退选（2 门）', exact: true }).click();
  await expect(page.getByTestId('course-block')).toHaveCount(0);
});

test('every student can manually withdraw; closed selection has no withdrawal entry', async ({ page }) => {
  await mount(page, recommendation, catalog, { ...state, current_application: ['MATH_A'] });
  await page.getByRole('combobox', { name: '选择学生' }).click();
  await page.getByRole('option', { name: 'S002 · 人工智能' }).click();
  await expect(page.getByRole('button', { name: '撤回志愿', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '撤回志愿', exact: true }).click();
  await expect(page.getByRole('button', { name: '确认撤回志愿', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.reload();
  await mount(page, recommendation, catalog, { ...state, phase: 'CLOSED', enrolled_section_ids: ['MATH_A'] });
  await expect(page.getByRole('button', { name: '退选课程', exact: true })).toHaveCount(0);
});

test('timetable counts remain visible in both selection rounds', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mount(page, recommendation, catalog, {
    ...state, current_application: ['MATH_A', 'ART_A'],
    applicant_counts: { MATH_A: 28, MATH_B: 0, ART_A: 3 },
  });
  const applicants = page.getByLabel('申请人数/容量：28/1，超额 27 人', { exact: true });
  await expect(applicants).toBeVisible();
  await page.screenshot({ path: 'test-results/timetable-counts-round1.png' });
  await page.reload();
  await mount(page, recommendation, catalog, {
    ...state, phase: 'ROUND2_OPEN', enrolled_section_ids: ['MATH_A', 'ART_A'],
    applicant_counts: { MATH_A: 28, MATH_B: 0, ART_A: 3 },
    remaining: { MATH_A: 0, MATH_B: 2, ART_A: 1 },
  });
  const occupied = page.getByLabel('已选人数/容量：1/1', { exact: true });
  await expect(occupied).toBeVisible();
  for (const count of await page.locator('.course-enrollment').all()) {
    const bounds = await count.boundingBox();
    const card = await count.locator('..').locator('..').boundingBox();
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(card!.y + card!.height);
  }
  await page.screenshot({ path: 'test-results/timetable-counts-round2.png' });
});

test('desktop rail expands on hover, collapses after mouse exit, and does not shift the page', async ({
  page,
}) => {
  await mount(page);
  const rail = page.getByRole('complementary', { name: '功能导航' });
  const mainBefore = await page.locator('main').boundingBox();
  await expect.poll(async () => Math.round((await rail.boundingBox())!.width)).toBe(68);
  await expect(rail.locator('.nav-copy').first()).toBeHidden();
  await rail.hover();
  await expect.poll(async () => Math.round((await rail.boundingBox())!.width)).toBe(230);
  await expect(rail.getByText('课程喜好与早课安排')).toBeVisible();
  await page.getByRole('button', { name: '选课工作台', exact: true }).click();
  await page.mouse.move(700, 100);
  await expect.poll(async () => Math.round((await rail.boundingBox())!.width)).toBe(68);
  expect((await page.locator('main').boundingBox())!.x).toBe(mainBefore!.x);
});

test('results and demo controls are separate pages, including browser back navigation', async ({ page }) => {
  await mount(page);
  await expect(page.locator('.result-panel')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '结束第一轮并抽签', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '录取结果', exact: true }).click();
  await expect(page.getByRole('heading', { name: '正式录取进度' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '为你推荐' })).toHaveCount(0);
  await expect(page.locator('.timetable-panel')).toContainText('正式录取');
  await page.getByRole('button', { name: '演示控制', exact: true }).click();
  await expect(page.getByRole('button', { name: '结束第一轮并抽签', exact: true })).toBeVisible();
  await expect(page.locator('.timetable-panel')).toHaveCount(0);
  await page.goBack();
  await expect(page.getByRole('heading', { name: '正式录取进度' })).toBeVisible();
});

test('preferences live in a modal, retain drafts on close, and can reset or save them', async ({ page }) => {
  await mount(page);
  const modal = page.getByRole('dialog', { name: '偏好设置', exact: true });
  await expect(modal).toBeHidden();
  await page.getByRole('button', { name: '偏好设置', exact: true }).click();
  await expect(modal).toBeVisible();
  const slider = modal.getByRole('slider', { name: '艺术鉴赏喜好分' });
  await slider.focus();
  await slider.press('ArrowLeft');
  await expect(slider).toHaveValue('89');
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(page.getByRole('button', { name: '生成推荐方案', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '偏好设置', exact: true }).click();
  await expect(slider).toHaveValue('89');
  await modal.getByRole('button', { name: '恢复已保存的偏好' }).click();
  await expect(slider).toHaveValue('90');
  await slider.focus();
  await slider.press('ArrowLeft');
  await modal.getByRole('button', { name: '保存偏好并重新推荐' }).click();
  await expect(modal.getByRole('button', { name: '偏好已保存' })).toBeVisible();
  await expect(modal.locator('.preferences-saving')).toHaveCount(0);
  await modal.getByRole('button', { name: '关闭偏好设置' }).click();
  await expect(page.getByRole('button', { name: '提交所选方案' })).toBeEnabled();
  await page.getByRole('button', { name: '偏好设置', exact: true }).click();
  await expect(slider).toHaveValue('89');
  const box = (await modal.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(1000);
});

test('plan details open only on demand, close with Escape, and return focus without stretching the page', async ({
  page,
}) => {
  await mount(page);
  await page.getByRole('button', { name: '生成推荐方案', exact: true }).click();
  const modal = page.getByRole('dialog', { name: '方案 1 · 详情', exact: true });
  await expect(modal).toHaveCount(0);
  await page.getByRole('button', { name: '预览方案 1 课表' }).click();
  await expect(modal).toHaveCount(0);
  const heightBefore = await page.locator('main').evaluate((el) => el.scrollHeight);
  const trigger = page.getByRole('button', { name: '查看方案 1 详情' });
  await trigger.click();
  await expect(modal).toBeVisible();
  await expect(modal.locator('.section-list')).toContainText('MATH_A');
  expect(await page.locator('main').evaluate((el) => el.scrollHeight)).toBe(heightBefore);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test('two plans per page with one footer button submitting the selected plan', async ({ page }) => {
  // Twelve candidates retain three visible plans across two pages.
  const candidates = {
    ...recommendation,
    plans: Array.from({ length: 12 }, (_, i) => ({
      ...plan,
      section_ids: i === 1 ? ['MATH_B', 'ART_A'] : i === 2 ? ['MATH_B'] : ['MATH_A', 'ART_A'],
      recommendation_score: 0.99 - i * 0.01,
    })),
  };
  await mount(page, candidates);
  await page.getByRole('button', { name: '生成推荐方案', exact: true }).click();
  await expect(page.locator('.plan-card')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '提交所选方案' })).toHaveCount(1);
  await expect(page.locator('.plan-card .plan-submit-button')).toHaveCount(0);
  await expect(page.locator('.plan-submit-footer')).toContainText('方案 1');
  await expect(page.getByRole('navigation', { name: '推荐方案分页' })).toContainText('第 1 / 2 页');
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.locator('.plan-card')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '提交所选方案' })).toBeEnabled();
  await expect(page.locator('.plan-submit-footer')).toContainText('方案 3');
  await expect(page.getByRole('button', { name: '下一页' })).toBeDisabled();
  await page.getByRole('button', { name: '上一页' }).click();
  await expect(page.locator('.plan-card')).toHaveCount(2);
  await page.getByRole('button', { name: '查看方案 2 详情' }).click();
  const modal = page.getByRole('dialog', { name: '方案 2 · 详情', exact: true });
  await expect(modal.locator('.section-list')).toContainText('MATH_B');
  await expect(modal.locator('.section-list')).not.toContainText('MATH_A');
  await modal.getByRole('button', { name: '关闭方案详情' }).click();
  await page.getByRole('button', { name: '预览方案 1 课表' }).click();
  await expect(page.locator('.plan-submit-footer')).toContainText('方案 1');
  await page.getByRole('button', { name: '预览方案 2 课表' }).click();
  await expect(page.locator('.plan-submit-footer')).toContainText('方案 2');
  await page.getByRole('button', { name: '提交所选方案' }).click();
  const confirmation = page.getByRole('dialog', { name: '确认提交第一轮志愿', exact: true });
  await confirmation.getByRole('button', { name: '再想想' }).click();
  await expect(modal).toHaveCount(0);
  const unchanged = await page.evaluate(async () => (await fetch('/api/state?student_id=S001')).json());
  expect(unchanged.current_application).toEqual([]);
  await page.getByRole('button', { name: '提交所选方案' }).click();
  await expect(confirmation).toContainText('将提交方案 2');
  await confirmation.getByRole('button', { name: '确认操作', exact: true }).click();
  await expect(modal).toHaveCount(0);
  await expect(page.locator('.message.success')).toContainText('志愿已提交');
  const submitted = await page.evaluate(async () => (await fetch('/api/state?student_id=S001')).json());
  expect(submitted.current_application).toEqual(['MATH_B', 'ART_A']);
  await expect(page.locator('.timetable-panel')).toContainText('当前志愿');
});

test('long plan details scroll inside the dialog while return action stays visible', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 800 });
  const longCatalog = structuredClone(catalog);
  const ids = Array.from({ length: 20 }, (_, i) => `COURSE_${i}`);
  for (const id of ids) {
    longCatalog.courses[id] = { id, name: `课程 ${id}`, credits: 2 };
    longCatalog.sections[id] = { ...catalog.sections.ART_A, id, course_id: id };
  }
  await mount(page, { ...recommendation, plans: [{ ...plan, section_ids: ids }] }, longCatalog);
  await page.getByRole('button', { name: '生成推荐方案', exact: true }).click();
  await page.getByRole('button', { name: '查看方案 1 详情' }).click();
  const modal = page.getByRole('dialog', { name: '方案 1 · 详情', exact: true });
  const box = (await modal.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(800);
  const body = modal.locator('.details-body');
  expect(await body.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  const submit = modal.getByRole('button', { name: '返回课表' });
  await expect(submit).toBeInViewport();
  const before = await submit.boundingBox();
  await body.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(modal.getByText('COURSE_19 · 2 学分', { exact: true })).toBeInViewport();
  expect(await submit.boundingBox()).toEqual(before);
});

test('desktop viewport fits all thirteen periods and the fixed submit action without page scrolling', async ({
  page,
}) => {
  await mount(page);
  await page.getByRole('button', { name: '生成推荐方案', exact: true }).click();
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport);
    for (const locator of [
      page.locator('.timetable-panel'),
      page.locator('.period').last(),
      page.getByRole('button', { name: '提交所选方案' }),
    ]) {
      const box = (await locator.boundingBox())!;
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    expect(await page.locator('.schedule-scroll').evaluate((el) => el.scrollHeight <= el.clientHeight)).toBe(
      true,
    );
    expect(await page.locator('.schedule-scroll').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
      true,
    );
    const submit = page.getByRole('button', { name: '提交所选方案' });
    const before = await submit.boundingBox();
    await page.locator('.recommendation-body').evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    expect(await submit.boundingBox()).toEqual(before);
    await expect(page.locator('.period').last()).toHaveText('13');
  }
});

for (const enrolled of [false, true]) {
  test(`results summary and full timetable fit desktop windows (${enrolled ? 'enrolled' : 'empty'})`, async ({
    page,
  }) => {
    await mount(
      page,
      recommendation,
      catalog,
      enrolled ? { ...state, phase: 'CLOSED', enrolled_section_ids: ['MATH_B', 'ART_A'] } : state,
    );
    await page.getByRole('button', { name: '录取结果', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: enrolled ? '最终选课结果' : '正式录取进度' }),
    ).toBeVisible();
    await expect(page.locator('.result-panel')).toContainText(enrolled ? '已完成要求' : '尚未选齐');
    await expect(page.locator('.completion-grid > div').last()).toContainText(enrolled ? '6 学分' : '0 学分');
    await page.getByRole('combobox', { name: '选择周次' }).click();
    await page.getByRole('option', { name: '第 2 周' }).click();
    if (enrolled) {
      await expect(page.getByTestId('course-block')).toHaveCount(2);
      await expect(page.getByTestId('course-block').filter({ hasText: '高等数学' })).toContainText('12–13');
    } else {
      await expect(page.locator('.result-note')).toContainText('高等数学');
    }
    for (const viewport of [
      { width: 1280, height: 720 },
      { width: 1366, height: 768 },
      { width: 1440, height: 900 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      for (const locator of [
        page.locator('.result-panel'),
        page.locator('.timetable-panel'),
        page.locator('.period').last(),
      ]) {
        const box = (await locator.boundingBox())!;
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
        expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
      }
      expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
      expect(
        await page
          .locator('.schedule-scroll')
          .evaluate((el) => el.scrollHeight <= el.clientHeight && el.scrollWidth <= el.clientWidth),
      ).toBe(true);
      await expect(page.locator('.period').last()).toHaveText('13');
    }
  });
}

test('simulation controls stay active across page navigation and can stop the background task', async ({
  page,
}) => {
  await mount(page);
  await page.getByRole('button', { name: '演示控制', exact: true }).click();
  const panel = page.getByRole('region', { name: '其他同学自动选课' });
  await expect(panel).toContainText('S001 由你操作');
  await panel.getByRole('button', { name: '开始自动选课' }).click();
  await expect(panel).toContainText('正在处理 S002');
  await expect(panel.getByRole('button', { name: '开始自动选课' })).toBeDisabled();
  await page.getByRole('button', { name: '选课工作台', exact: true }).click();
  await expect(panel).toHaveCount(0);
  await page.getByRole('button', { name: '模拟运行中' }).click();
  await panel.getByRole('button', { name: '停止自动选课' }).click();
  await expect(panel.getByRole('button', { name: '继续自动选课' })).toBeEnabled();
  await expect(panel.getByRole('button', { name: '停止自动选课' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '模拟运行中' })).toHaveCount(0);
});
