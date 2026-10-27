// Browser checks for the running app: tooltips by mouse and keyboard, chart/table switches, day and cut-off selection,
// stale data kept on screen while refetching, 503 error and retry, theme and patterns toggles, no console errors.
// 42 checks. Not part of "npm test" (it needs a browser and a running server).
//
//   cd frontend
//   npm install --no-save playwright-core          # once; uses your installed Google Chrome (channel "chrome")
//   BASE_URL=http://localhost:8000 node e2e/ui-check.mjs
//   BASE_URL=https://YOUR-PROJECT.vercel.app node e2e/ui-check.mjs      # against a deployment
//
// Some checks mock /api/decision to prove the error state, so they work on any URL. Exit status is not set; read the PASS/FAIL list.

import { chromium } from 'playwright-core';

const BASE = (process.env.BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const results = [];
const check = (name, ok, detail = '') => { results.push({ name, ok: !!ok, detail }); };

async function fresh(opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...opts });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  return { ctx, page, errors };
}

// ---- Decision view
{
  const { ctx, page, errors } = await fresh();
  await page.goto(`${BASE}/?view=decision&day=2026-01-14&cutoff=09:20`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.headline');

  const headline = await page.textContent('.headline');
  check('decision headline names the delivery day', /Thursday 15 January/.test(headline ?? ''), headline);

  check('decision page asks the question in plain words', /How much wind should you count on for/.test(headline ?? ''), headline);
  check('answer sentence gives the expected and cautious wind', /The forecast says about [\d.]+.GW/.test((await page.textContent('.lead')) ?? '') && /cautious plan counts on/.test((await page.textContent('.lead')) ?? ''), await page.textContent('.lead'));
  const stepHeads = await page.locator('.step-h').allTextContents();
  check('three numbered steps explain the answer', stepHeads.length === 3 && stepHeads.every((t, i) => t.startsWith(`${i + 1}.`)), stepHeads.join(' | '));
  check('tabs use plain names', (await page.locator('.views button').allTextContents()).join('|') === 'Tomorrow’s wind|Track record');
  check('day strip and decision time start collapsed', (await page.locator('details.disclosure[open]').count()) === 0);

  // hover tooltip
  await page.locator('.chart-wrap').first().scrollIntoViewIfNeeded();
  const box = await page.locator('.chart-wrap').first().boundingBox();
  await page.mouse.move(box.x + box.width * 0.4, box.y + 150);
  await page.waitForSelector('.tip');
  const tip = await page.textContent('.tip');
  check('chart tooltip shows forecast and likely range', /Forecast/.test(tip) && /Likely range/.test(tip), tip);
  await page.mouse.move(5, 5);
  check('tooltip clears when pointer leaves', (await page.locator('.tip').count()) === 0);

  // keyboard
  await page.locator('.chart-wrap').first().focus();
  const t0 = await page.textContent('.tip');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  const t1 = await page.textContent('.tip');
  check('keyboard arrows move the reading', t0 !== t1, `${t0} -> ${t1}`);
  const live = await page.locator('.chart-wrap .sr-only').first().textContent();
  check('live region announces the reading', /Forecast/.test(live ?? ''), live);
  await page.keyboard.press('Escape');
  check('Escape closes the tooltip', (await page.locator('.tip').count()) === 0);

  // actual toggle
  await page.getByLabel('Show what actually happened').check();
  await page.waitForSelector('.happened');
  const legend = await page.textContent('.legend');
  check('legend gains the actual series', /What actually happened/.test(legend ?? ''), legend);
  check('what-happened sentence present', /Wind averaged/.test((await page.textContent('.happened')) ?? ''), await page.textContent('.happened'));

  // table behind chart
  await page.getByRole('button', { name: 'Table' }).first().click();
  const rows = await page.locator('.chart-frame table.dt tbody tr').count();
  check('table view has 48 half-hour rows', rows === 48, String(rows));
  const heads = await page.locator('.chart-frame table.dt th').allTextContents();
  check('table includes actual columns when toggled', heads.some((h) => /Actual/.test(h)), heads.join(' | '));
  await page.getByRole('button', { name: 'Chart' }).first().click();

  // strip click (the strip sits behind "Jump to another day")
  await page.getByText('Jump to another day').click();
  await page.locator('[data-day="2026-01-20"]').click();
  await page.waitForFunction(() => /21 January/.test(document.querySelector('.headline')?.textContent ?? ''));
  check('clicking a day tile selects it and updates the URL', page.url().includes('day=2026-01-20'), page.url());

  // strip keyboard
  await page.locator('[data-day="2026-01-20"]').focus();
  await page.keyboard.press('ArrowRight');
  await page.waitForFunction(() => /22 January/.test(document.querySelector('.headline')?.textContent ?? ''));
  check('arrow keys move the day selection', (await page.evaluate(() => document.activeElement?.getAttribute('data-day'))) === '2026-01-21');

  // tile tooltip
  await page.locator('[data-day="2026-01-10"]').hover();
  await page.waitForSelector('.tip');
  check('day tile tooltip names the day and error', /Buy Sat 10 Jan for Sun 11 Jan/.test((await page.textContent('.tip')) ?? ''), await page.textContent('.tip'));
  await page.mouse.move(5, 5);

  // decision time 09:50 (behind its own disclosure)
  await page.getByText(/^Decision time:/).click();
  await page.getByRole('button', { name: '09:50' }).click();
  await page.waitForFunction(() => /09:30/.test(document.querySelector('.basis')?.textContent ?? ''));
  check('09:50 cut-off picks the 09:30 forecast', true, await page.textContent('.basis'));

  // invalid cutoff
  await page.locator('#cutoff').fill('');
  check('empty cut-off shows a message', /Enter a time/.test((await page.textContent('.control')) ?? '') || (await page.locator('.field-error').count()) === 1);

  // theme + patterns
  await page.getByRole('button', { name: 'Dark mode' }).click();
  check('dark mode toggle sets data-theme', (await page.evaluate(() => document.documentElement.dataset.theme)) === 'dark');
  await page.getByRole('button', { name: 'Patterns' }).click();
  check('patterns toggle sets data-patterns', (await page.evaluate(() => document.documentElement.dataset.patterns)) === 'on');
  const fill = await page.evaluate(() => { const el = document.querySelector('.strip .mark-over'); return el ? getComputedStyle(el).fill : null; });
  check('patterns mode fills over-forecast marks with the hatch', /hatch-over/.test(fill ?? ''), fill);

  check('no console errors on decision view', errors.length === 0, errors.join('; '));
  await ctx.close();
}

// ---- Stale data stays on screen while refetching
{
  const { ctx, page } = await fresh();
  await page.goto(`${BASE}/?view=decision&day=2026-01-14&cutoff=09:20`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.headline');
  await page.route('**/api/decision?**', async (route) => { await new Promise((r) => setTimeout(r, 1500)); await route.continue(); });
  await page.getByText('Jump to another day').click();
  await page.locator('[data-day="2026-01-20"]').click();
  await page.waitForTimeout(300);
  const staleHeadline = await page.textContent('.headline');
  const isStale = await page.locator('.view.is-stale').count();
  const updating = await page.locator('.updating').count();
  check('previous headline stays on screen while refetching', /Thursday 15 January/.test(staleHeadline ?? ''), staleHeadline);
  check('stale view is dimmed and Updating is shown', isStale === 1 && updating === 1, `stale=${isStale} updating=${updating}`);
  await page.waitForFunction(() => /21 January/.test(document.querySelector('.headline')?.textContent ?? ''));
  check('new data replaces it', (await page.locator('.view.is-stale').count()) === 0);
  await ctx.close();
}

// ---- Error state
{
  const { ctx, page } = await fresh();
  await page.route('**/api/decision?**', (route) => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Data snapshot not found (x.gz). Generate it with: python backend/scripts/fetch_snapshot.py' }) }));
  await page.goto(`${BASE}/?view=decision&day=2026-01-14&cutoff=09:20`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[role=alert]');
  const txt = await page.textContent('[role=alert]');
  check('503 shows a clear message and a retry button', /Data snapshot not found/.test(txt ?? '') && (await page.getByRole('button', { name: 'Try again' }).count()) === 1, txt);
  await page.unroute('**/api/decision?**');
  await page.getByRole('button', { name: 'Try again' }).click();
  await page.waitForSelector('.headline');
  check('retry recovers', true);
  await ctx.close();
}

// ---- Accuracy view
{
  const { ctx, page, errors } = await fresh();
  await page.goto(`${BASE}/?view=accuracy&day=2026-01-14&cutoff=09:20`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.headline');
  const h = await page.textContent('.headline');
  check('accuracy headline states typical miss and share too high', /2,042/.test(h ?? '') && /85%/.test(h ?? ''), h);
  const aStepHeads = await page.locator('.step-h').allTextContents();
  check('track record has three numbered steps', aStepHeads.length === 3 && aStepHeads.every((t, i) => t.startsWith(`${i + 1}.`)), aStepHeads.join(' | '));
  const mainRows = await page.locator('#size-h ~ table.report tbody tr').count();
  check('four headline measures are shown up front', mainRows === 4, String(mainRows));
  check('analyst detail starts collapsed', (await page.locator('details.more-detail[open]').count()) === 0);
  await page.getByText('More detail for analysts').click();
  await page.waitForSelector('.chart-grid svg');
  const frames = await page.locator('.chart-frame').count();
  const toggles = await page.locator('.chart-frame .seg').count();
  check('every chart frame has a Chart/Table switch', frames === toggles && frames === 5, `frames=${frames} toggles=${toggles}`);
  // bar tooltip
  const bars = page.locator('.chart-grid .chart-wrap').first();
  await bars.scrollIntoViewIfNeeded();
  const bb = await bars.boundingBox();
  await page.mouse.move(bb.x + bb.width * 0.5, bb.y + 120);
  await page.waitForSelector('.tip');
  check('bar chart tooltip works', /Typical miss/.test((await page.textContent('.tip')) ?? ''), await page.textContent('.tip'));
  await page.mouse.move(5, 5);
  // table behind each chart
  for (let i = 0; i < 5; i += 1) await page.locator('.chart-frame .seg').nth(i).getByRole('button', { name: 'Table' }).click();
  const tables = await page.locator('.chart-frame table.dt').count();
  check('all five charts have a table behind them', tables === 5, String(tables));
  const daily = await page.locator('.chart-frame').first().locator('tbody tr').count();
  check('period table lists 31 daily averages', daily === 31, String(daily));
  check('calibration note present', /Does the likely range hold/.test((await page.textContent('#cal-h')) ?? ''));
  check('by-level table present', (await page.locator('#level-h').count()) === 1);
  check('no console errors on accuracy view', errors.length === 0, errors.join('; '));
  await ctx.close();
}

// ---- Light theme actually light, and focus ring visible
{
  const { ctx, page } = await fresh({ colorScheme: 'light' });
  await page.goto(`${BASE}/?view=decision&day=2026-01-14&cutoff=09:20`, { waitUntil: 'networkidle' });
  const bg = await page.evaluate(() => getComputedStyle(document.querySelector('.sheet')).backgroundColor);
  check('light scheme uses the light sheet', bg === 'rgb(251, 248, 243)', bg);
  await page.keyboard.press('Tab');
  const outline = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return `${s.outlineStyle} ${s.outlineWidth}`; });
  check('keyboard focus shows an outline', /solid 2px/.test(outline), outline);
  await ctx.close();
}

await browser.close();
for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.ok ? '' : `  -> ${r.detail}`}`);
console.log(`\n${results.filter((r) => r.ok).length}/${results.length} passed`);
