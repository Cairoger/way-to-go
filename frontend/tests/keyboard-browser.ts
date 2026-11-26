import { test as base } from '@playwright/test';
import { join } from 'node:path';

export const test = base.extend({
  launchOptions: async ({ browserName, launchOptions, playwright }, run) => {
    if (process.platform !== 'darwin' || browserName !== 'webkit') {
      await run(launchOptions);
      return;
    }
    await run({
      ...launchOptions,
      executablePath: join(__dirname, 'macos-webkit-keyboard.sh'),
      env: {
        ...process.env,
        ...launchOptions.env,
        WAYTOGO_KEYBOARD_WEBKIT: launchOptions.executablePath ?? playwright.webkit.executablePath(),
      },
    });
  },
});
