const { chromium } = require('playwright');
const fs = require('fs');

async function run() {
  console.log("Starting Clean-Slate UI Run...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordHar: { path: 'clean_slate.har' }
  });
  
  const page = await context.newPage();
  const consoleLogs = [];
  const errors = [];
  
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => errors.push(err.message));

  await page.goto('http://localhost:3000/');
  console.log("Navigated to dashboard");

  await page.waitForTimeout(2000);
  
  // Upload base.mp4
  const fileInput = await page.$('input[type=file]');
  if (fileInput) {
    await fileInput.setInputFiles('../uploads/base.mp4');
    console.log("File selected");
    
    // Check if there is an explicit upload/submit button or if it auto-submits
    // Usually there is a "Upload Video" or "Process" button
    const uploadBtn = await page.$('button:has-text("Upload & Process")');
    if (uploadBtn) {
      await uploadBtn.click();
    } else {
       // if we click Upload it triggers form submission
       const uploadTrigger = await page.$('button:has-text("Upload")');
       if(uploadTrigger) await uploadTrigger.click();
    }
  } else {
    console.log("Could not find file input");
  }

  console.log("Waiting for job to process...");
  // Wait up to 300 seconds for the job to show as completed in UI
  try {
     await page.waitForSelector('text="Done!"', { timeout: 300000 });
     console.log("Processing complete!");
  } catch(e) {
     console.log("Processing timed out or failed to reach Done state.");
  }

  // Dump logs
  fs.writeFileSync('clean_slate_logs.txt', consoleLogs.join('\n'));
  fs.writeFileSync('clean_slate_errors.txt', errors.join('\n'));
  
  await browser.close();
  console.log("Clean-slate run complete. HAR and logs saved.");
}

run().catch(console.error);
