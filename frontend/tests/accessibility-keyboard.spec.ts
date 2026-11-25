import { expect, test } from '@playwright/test';

test('鍵盤可跳至主要內容、操作登入對話框，關閉後回到原按鈕', async ({ page }) => {
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 820 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: '旅程總覽' })).toBeVisible();

    await page.keyboard.press('Tab');
    const skip = page.getByRole('link', { name: '跳到主要內容' });
    await expect(skip).toBeFocused();
    await expect(skip).toBeInViewport();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Tab');
    const create = page.getByRole('button', { name: '建立旅程', exact: true });
    await expect(create).toBeFocused();
    await expect(create).toBeInViewport();
    await page.keyboard.press('Enter');

    const dialog = page.getByRole('dialog');
    await expect(dialog).toHaveAccessibleName(/登入/);
    const close = dialog.getByRole('button', { name: '關閉' });
    await expect(close).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    expect(await dialog.locator(':focus').count()).toBe(1);
    await page.keyboard.press('Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(create).toBeFocused();
    await expect(create).toBeInViewport();

    const filters = page.getByRole('group', { name: '篩選旅程' });
    const confirmed = filters.getByRole('button', { name: '已確認' });
    await confirmed.focus();
    await page.keyboard.press('Space');
    await expect(confirmed).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.trip-card')).toHaveCount(1);
    const card = page.getByRole('button', { name: /開啟\s*多洛米蒂山間漫遊/ });
    await card.focus();
    await page.keyboard.press('Enter');
    const days = page.getByRole('group', { name: '選擇行程日' });
    const first = days.getByRole('button', { name: 'Day 1', exact: true });
    await first.focus();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Space');
    await expect(days.getByRole('button', { name: 'Day 2', pressed: true })).toBeFocused();
    await expect(first).toHaveAttribute('aria-pressed', 'false');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});
