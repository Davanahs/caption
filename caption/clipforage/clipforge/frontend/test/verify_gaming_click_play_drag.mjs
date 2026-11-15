import { chromium } from 'playwright';
import assert from 'assert';

const BASE_URL = 'http://localhost:3001/gaming';

async function testClickPlayDragInteraction() {
  console.log('Testing Gaming Studio Click-to-Play/Pause vs Direct Drag Interaction...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1000);

    // 1. Enter sample YouTube URL & open modal
    const urlInput = page.locator('#gaming-youtube-url-input');
    await urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    const openBtn = page.locator('#open-gaming-studio-url-btn');
    await openBtn.click();

    // 2. Wait for modal & video container
    await page.waitForSelector('#gaming-selection-modal-dialog', { state: 'visible' });
    const videoContainer = page.locator('#gaming-source-video-container');
    await videoContainer.waitFor({ state: 'visible' });

    // 3. Verify ROI boxes exist
    const gameplayBox = page.locator('#gameplay-roi-box');
    const facecamBox = page.locator('#facecam-roi-box');
    await gameplayBox.waitFor({ state: 'visible' });
    await facecamBox.waitFor({ state: 'visible' });

    // 4. Click video backdrop (outside ROI boxes) -> triggers playback
    // Click near bottom-center of video container where no ROI box is located
    const containerBox = await videoContainer.boundingBox();
    assert.ok(containerBox, 'Video container bounding box must exist');

    // Initial state: badge says Paused or Playing
    const panelHeader = page.locator('.shrink-0.flex.items-center.justify-between.px-6.py-3').first();
    let statusText = await panelHeader.innerText();
    console.log('  Initial status:', statusText.replace(/\n/g, ' '));

    // Click outside ROI boxes (at x: 50%, y: 50% or bottom center)
    // Note: Gameplay is centered at x ≈ 34% to 66%, y: 0 to 100% in 9:16 portrait.
    // Far left (x: containerBox.x + 50, y: containerBox.y + containerBox.height / 2) is completely outside both boxes!
    const outsideX = containerBox.x + 50;
    const outsideY = containerBox.y + containerBox.height / 2;
    await page.mouse.click(outsideX, outsideY);
    await page.waitForTimeout(400);

    statusText = await panelHeader.innerText();
    console.log('  After clicking video backdrop (outside ROI):', statusText.replace(/\n/g, ' '));
    assert.ok(statusText.includes('Playing'), 'Video should transition to Playing after clicking video backdrop');

    // 5. Click on Gameplay ROI box
    const gpBox = await gameplayBox.boundingBox();
    assert.ok(gpBox, 'Gameplay box must exist');
    await page.mouse.click(gpBox.x + gpBox.width / 2, gpBox.y + gpBox.height / 2);
    await page.waitForTimeout(300);

    // Verify video is STILL playing (did not pause!)
    statusText = await panelHeader.innerText();
    console.log('  After clicking Gameplay ROI box:', statusText.replace(/\n/g, ' '));
    assert.ok(statusText.includes('Playing'), 'Video must KEEP PLAYING when clicking on ROI box');
    assert.ok(statusText.includes('Gameplay (Active)'), 'Gameplay must be active');

    // 6. Click on Facecam ROI box and drag to reposition
    const fcBox = await facecamBox.boundingBox();
    assert.ok(fcBox, 'Facecam box must exist');
    await page.mouse.click(fcBox.x + fcBox.width / 2, fcBox.y + fcBox.height / 2);
    await page.waitForTimeout(300);

    // Verify video is STILL playing (did not pause!)
    statusText = await panelHeader.innerText();
    console.log('  After clicking Facecam ROI box:', statusText.replace(/\n/g, ' '));
    assert.ok(statusText.includes('Playing'), 'Video must KEEP PLAYING when clicking on Facecam box');
    assert.ok(statusText.includes('Facecam (Active)'), 'Facecam must be active');

    // Drag facecam box by 40px
    const initialFcX = fcBox.x;
    await page.mouse.move(fcBox.x + fcBox.width / 2, fcBox.y + fcBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(fcBox.x + fcBox.width / 2 - 40, fcBox.y + fcBox.height / 2 - 20, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(200);

    // Verify video is STILL playing after drag
    statusText = await panelHeader.innerText();
    console.log('  After dragging Facecam box:', statusText.replace(/\n/g, ' '));
    assert.ok(statusText.includes('Playing'), 'Video must KEEP PLAYING after dragging Facecam box');

    const newFcBox = await facecamBox.boundingBox();
    assert.ok(newFcBox, 'New facecam box must exist');
    console.log(`  Facecam moved: initial x=${Math.round(initialFcX)}, new x=${Math.round(newFcBox.x)}`);
    assert.ok(newFcBox.x < initialFcX, 'Facecam box must have moved to the left');

    // 7. Click back onto the video outside ROI boxes
    await page.mouse.click(outsideX, outsideY);
    await page.waitForTimeout(400);

    statusText = await panelHeader.innerText();
    console.log('  After clicking back outside ROI boxes:', statusText.replace(/\n/g, ' '));
    assert.ok(statusText.includes('Paused'), 'Video must PAUSE when clicking back onto video outside ROI boxes');

    // Capture screenshot of the modal in action
    await page.screenshot({ path: 'C:/Users/Chinmaygouda/.gemini/antigravity/brain/e57be485-0b37-45b3-9624-f5c62f6f0e2f/gaming_click_play_verified.png' });
    console.log('✅ Click-to-Play/Pause vs Direct Drag Interaction verified successfully!');
  } finally {
    await browser.close();
  }
}

testClickPlayDragInteraction().catch(err => {
  console.error('❌ Verification failed:', err);
  process.exit(1);
});
