const { chromium } = require('playwright');
const fs = require('fs');

async function runForensics() {
  console.log("Starting Stage 2: Event Forensics");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Mock API responses
  await page.route('**/api/stats', async route => {
    await route.fulfill({ json: { "disk_usage_mb": 0, "db_size_mb": 0 } });
  });
  await page.route('**/api/jobs/stats', async route => {
    await route.fulfill({ json: { "queued": 0, "processing": 0, "completed": 0, "failed": 0 } });
  });
  await page.route('**/api/jobs/', async route => {
    // Initial poll returns no jobs
    await route.fulfill({ json: [] });
  });

  // Inject a mock WebSocket and fetch interceptor into the page before it loads
  await page.addInitScript(() => {
    window.wsLogs = [];
    window.pollingCount = 0;
    
    // Intercept fetch to count polling
    const origFetch = window.fetch;
    window.fetch = async (...args) => {
      if (typeof args[0] === 'string' && args[0].includes('/api/jobs/')) {
         window.pollingCount++;
      }
      return origFetch.apply(this, args);
    };

    class MockWebSocket {
      constructor(url) {
        this.url = url;
        window.wsLogs.push(`WS Connected: ${url}`);
        this.readyState = 1;
        setTimeout(() => {
          if (this.onopen) this.onopen();
        }, 10);
      }
      send() {}
      close() {
        window.wsLogs.push(`WS Closed: ${this.url}`);
        this.readyState = 3;
        if (this.onclose) this.onclose();
      }
    }
    // Only mock the WS if the URL contains /ws/
    const origWS = window.WebSocket;
    window.WebSocket = function(url) {
      if (url.includes('/api/jobs/ws/')) {
        window.mockWsInstance = new MockWebSocket(url);
        return window.mockWsInstance;
      }
      return new origWS(url);
    };
  });

  await page.goto('http://localhost:3000/');
  await page.waitForTimeout(1000);

  // 1. Inject a Job into the React state by triggering a fake API response for /api/jobs/
  console.log("Injecting job...");
  await page.route('**/api/jobs/', async route => {
    await route.fulfill({ json: [{ id: 'job-123', status: 'processing', progress: 50, video_title: 'Test' }] });
  });
  
  // Trigger a poll artificially or wait for it
  await page.evaluate(() => {
    // We can't trigger it directly, but the app polls every 10s or 2s. Let's wait.
  });
  await page.waitForTimeout(2500); // 2s polling interval should hit it
  
  const jobsVisible = await page.evaluate(() => {
    return document.body.innerText.includes('Test');
  });
  console.log(`Job visible in UI: ${jobsVisible}`);
  
  // 2. Stale Event Injection (Job is deleted, then we push a WS message)
  console.log("Simulating Stale Event Injection...");
  // Clear the jobs from the poll so it's "deleted"
  await page.route('**/api/jobs/', async route => {
    await route.fulfill({ json: [] });
  });
  await page.waitForTimeout(2500); // Wait for poll to clear it
  const jobsVisibleAfterDelete = await page.evaluate(() => {
    return document.body.innerText.includes('Test');
  });
  console.log(`Job visible after delete: ${jobsVisibleAfterDelete}`);
  
  // Inject stale event
  await page.evaluate(() => {
    if (window.mockWsInstance && window.mockWsInstance.onmessage) {
      window.mockWsInstance.onmessage({ data: JSON.stringify({ id: 'job-123', status: 'completed', progress: 100 }) });
    }
  });
  await page.waitForTimeout(500);
  const jobsVisibleAfterStale = await page.evaluate(() => {
    return document.body.innerText.includes('Test');
  });
  console.log(`Job resurrected by stale event? ${jobsVisibleAfterStale}`);

  // 3. Duplicate / Malformed Events
  console.log("Injecting Malformed Event...");
  // First, add the job back
  await page.route('**/api/jobs/', async route => {
    await route.fulfill({ json: [{ id: 'job-123', status: 'processing', progress: 50, video_title: 'Test' }] });
  });
  await page.waitForTimeout(2500);
  
  // Send duplicate / malformed
  const errorHandled = await page.evaluate(() => {
    try {
       window.mockWsInstance.onmessage({ data: "INVALID JSON DATA" });
       window.mockWsInstance.onmessage({ data: JSON.stringify({ id: 'job-123' }) }); // Missing fields
       return true;
    } catch(e) {
       return false;
    }
  });
  console.log(`Malformed events handled safely without crash? ${errorHandled}`);

  // 4. Polling Teardown
  console.log("Testing Polling Teardown...");
  const initialPolls = await page.evaluate(() => window.pollingCount);
  // Navigate away
  await page.click('text=Clips');
  await page.waitForTimeout(4000); // Wait for 2 poll intervals
  const finalPolls = await page.evaluate(() => window.pollingCount);
  console.log(`Polls stopped after navigation? (Initial: ${initialPolls}, Final: ${finalPolls}) ${finalPolls - initialPolls <= 1}`);
  
  await browser.close();
  
  const report = `
## Stage 2: Real-time Event Forensics

* **Stale Event Injection**: UI does not resurrect job when stale websocket event arrives: **${!jobsVisibleAfterStale}**
* **Duplicate/Malformed Events**: Frontend parsing try-catch safely handles invalid JSON: **${errorHandled}**
* **Polling Teardown**: Polling interval clears upon navigating away from dashboard: **${finalPolls - initialPolls <= 1}**
`;
  fs.writeFileSync('forensics_report.md', report);
  console.log("Report generated.");
}

runForensics().catch(console.error);
