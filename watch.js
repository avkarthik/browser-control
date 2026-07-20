const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const URL = 'https://example.com';
const CHECK_EVERY_MS = 60_000;
const SCREENSHOT_DIR = path.join(__dirname, 'shots');
const MODEL = 'gemma4';
const TARGET_TEXT = 'Example Domain';

if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function askOllama(prompt) {
  const res = await fetch('http://localhost:11434/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      prompt,
      stream: false
    })
  });
  const data = await res.json();
  return data.response || '';
}

function ts() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

async function runCheck() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 2200 } });

  try {
    await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(2000);

    const bodyText = await page.locator('body').innerText();
    const lower = bodyText.toLowerCase();

    let matched = lower.includes(TARGET_TEXT.toLowerCase());
    let reason = matched ? `Found direct text match: ${TARGET_TEXT}` : 'No direct text match';

    if (!matched) {
      const prompt = `
You are checking whether a webpage contains the content I want.
Wanted content: "${TARGET_TEXT}"

Page text:
${bodyText.slice(0, 12000)}

Reply in exactly one line:
MATCH - reason
or
NO_MATCH - reason
      `.trim();

      const result = await askOllama(prompt);
      if (result.startsWith('MATCH')) {
        matched = true;
        reason = result;
      } else {
        reason = result || reason;
      }
    }

    const shot = path.join(SCREENSHOT_DIR, `${matched ? 'match' : 'check'}-${ts()}.png`);
    await page.screenshot({ path: shot, fullPage: true });

    console.log(JSON.stringify({
      url: URL,
      matched,
      reason,
      screenshot: shot,
      checkedAt: new Date().toISOString()
    }, null, 2));
  } catch (err) {
    console.error('Check failed:', err.message);
  } finally {
    await browser.close();
  }
}

runCheck();
setInterval(runCheck, CHECK_EVERY_MS);
