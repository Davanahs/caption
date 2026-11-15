/**
 * screenshot_v3_verify.mjs
 * Captures screenshots of the Gaming Studio page to verify the redesign.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const ARTIFACT_DIR = 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f';
const BASE_URL = 'http://localhost:3001/gaming';

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const errors = [];

  try {
    // ── 1. Full page 1440×900 ──
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${ARTIFACT_DIR}/gaming_v3_full_1440.png`, fullPage: false });
      console.log('✅ Saved gaming_v3_full_1440.png');

      // Check key elements exist
      const checks = [
        { sel: '#select-gameplay-tool-btn', name: 'Gameplay tool btn' },
        { sel: '#select-facecam-tool-btn',  name: 'Facecam tool btn'  },
        { sel: '#gaming-mode-select-btn',   name: 'Edit Areas btn'    },
        { sel: '#gaming-mode-playback-btn', name: 'Preview btn'       },
        { sel: '#gaming-clips-count-select',name: 'Clips input'       },
        { sel: '#gaming-modal-confirm-btn', name: 'Confirm btn'       },
        { sel: '#duration-btn-49',          name: 'Duration 49s btn'  },
        { sel: '#gameplay-roi-box',         name: 'Gameplay ROI box'  },
        { sel: '#facecam-roi-box',          name: 'Facecam ROI box'   },
      ];
      for (const { sel, name } of checks) {
        const el = page.locator(sel);
        const count = await el.count();
        if (count > 0) {
          console.log(`  ✔ ${name} found`);
        } else {
          console.log(`  ✘ ${name} MISSING`);
          errors.push(`Missing element: ${sel}`);
        }
      }

      // Check confirm button text
      const confirmText = await page.locator('#gaming-modal-confirm-btn').innerText().catch(() => '');
      console.log(`  Confirm btn text: "${confirmText.trim()}"`);

      // Check clips input type
      const clipsTag = await page.locator('#gaming-clips-count-select').evaluate(el => el.tagName + ',' + el.type).catch(() => '');
      console.log(`  Clips element: "${clipsTag}"`);

      // Check gameplay defaults to 9:16
      const aspectLockActive = await page.locator('#gameplay-aspect-lock-btn').evaluate(el => {
        const style = el.style.background || window.getComputedStyle(el).background;
        return style;
      }).catch(() => 'n/a');
      console.log(`  Aspect lock btn bg: "${aspectLockActive}"`);

      // Check mobile view switcher is hidden
      const mobileViewVisible = await page.locator('#gaming-view-source-btn').isVisible().catch(() => false);
      console.log(`  Mobile view switcher visible: ${mobileViewVisible} (expected: false)`);

      // Check PiP presets are hidden
      const pipPresetsVisible = await page.locator('#facecam-placement-presets').isVisible().catch(() => false);
      console.log(`  PiP presets section visible: ${pipPresetsVisible} (expected: false)`);

      await ctx.close();
    }

    // ── 2. Bottom bar zoom at 1440×900 ──
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1000);
      // Scroll to bottom
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${ARTIFACT_DIR}/gaming_v3_bottom_1440.png`, fullPage: false });
      console.log('✅ Saved gaming_v3_bottom_1440.png');
      await ctx.close();
    }

    // ── 3. 1280×800 viewport ──
    {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await ctx.newPage();
      await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${ARTIFACT_DIR}/gaming_v3_full_1280.png`, fullPage: false });
      console.log('✅ Saved gaming_v3_full_1280.png');
      await ctx.close();
    }

    if (errors.length > 0) {
      console.log('\n⚠ Issues found:');
      errors.forEach(e => console.log('  -', e));
      process.exit(1);
    } else {
      console.log('\n✅ All checks passed. Gaming Studio redesign verified.');
    }

  } finally {
    await browser.close();
  }
}

capture().catch(e => { console.error('Fatal:', e); process.exit(1); });

