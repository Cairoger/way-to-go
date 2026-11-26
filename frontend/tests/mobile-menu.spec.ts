import { expect } from '@playwright/test';
import { test } from './keyboard-browser';

test.use({ viewport: { width: 390, height: 844 } });

test('手機側欄保留鍵盤焦點，關閉或切換對話框後回到選單按鈕', async ({ page }) => {
  await page.goto('/');
  const trigger = page.locator('button[aria-label="開啟選單"]');
  const menu = page.getByRole('dialog', { name: '工作空間選單' });
  const close = menu.getByRole('button', { name: '收合選單' });

  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  await expect(menu).toHaveAttribute('id', (await trigger.getAttribute('aria-controls'))!);
  await expect(close).toBeFocused();
  await expect(page.getByRole('main')).toHaveCount(0);

  const profile = menu.getByRole('button', { name: /登入你的帳號/ });
  await expect(profile).toBeEnabled();
  await page.keyboard.press('Shift+Tab');
  await expect(profile).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(menu.getByRole('button', { name: /WayToGo/ })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');

  await trigger.click();
  await menu.getByRole('button', { name: '輸入邀請碼' }).click();
  const join = page.getByRole('dialog', { name: '加入旅程' });
  await expect(join.getByLabel('你的暱稱')).toBeVisible();
  await expect(menu).toHaveCount(0);
  await expect(join.locator(':focus')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(join).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test('手機側欄支援導覽與背景點按，切換桌面後可以正常操作頁面', async ({ page }) => {
  await page.goto('/');
  const trigger = page.locator('button[aria-label="開啟選單"]');
  const menu = page.getByRole('dialog', { name: '工作空間選單' });

  await trigger.click();
  await menu.getByRole('button', { name: '已封存' }).click();
  await expect(page.getByRole('heading', { name: '已封存', exact: true })).toBeVisible();
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await trigger.click();
  await page.locator('.mobile-shade').click({ position: { x: 350, y: 400 } });
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await trigger.click();
  await page.setViewportSize({ width: 1280, height: 820 });
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeHidden();
  await expect(page.getByRole('button', { name: /WayToGo/ })).toBeFocused();
  await page
    .getByRole('navigation', { name: '工作空間' })
    .getByRole('button', { name: '旅程總覽' })
    .click();
  await expect(page.getByRole('heading', { name: '旅程總覽' })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('navigation', { name: '工作空間' })).toHaveCount(0);
});
