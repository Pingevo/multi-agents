import { chromium } from 'playwright';

const URL = process.env.APP_URL || 'http://127.0.0.1:8000';
const TIMEOUT_MS = 20000;
const CONSOLE_LOOP_THRESHOLD = 10; // same message repeated >10 times = loop

const consoleMessages = [];
const messageCounts = new Map();
let crashed = false;
let pageErrorCount = 0;

const browser = await chromium.launch({ headless: false });
const page = await browser.newPage();

page.on('console', (msg) => {
  const text = msg.text();
  consoleMessages.push({ type: msg.type(), text, time: Date.now() });
  const key = text.slice(0, 120); // group similar messages
  messageCounts.set(key, (messageCounts.get(key) || 0) + 1);
});

page.on('pageerror', (err) => {
  pageErrorCount++;
  console.error('[PAGE ERROR]', err.message);
});

page.on('crash', () => {
  crashed = true;
  console.error('[CRASH] Page crashed (tab kill / OOM)');
});

console.log(`[REPRO] Navigating to ${URL} ...`);

try {
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
} catch (e) {
  console.error('[REPRO] Navigation failed:', e.message);
}

// Wait for socket to connect and chat history to load
console.log('[REPRO] Waiting 5s for socket + chat history to load...');
await new Promise((r) => setTimeout(r, 5000));

// Take screenshot after history loads
try {
  await page.screenshot({ path: '/tmp/repro-after-history.png', fullPage: false });
  console.log('[REPRO] Post-history screenshot saved');
} catch(e) {}

// Monitor for TIMEOUT_MS
const start = Date.now();
let responsive = true;

while (Date.now() - start < TIMEOUT_MS) {
  await new Promise((r) => setTimeout(r, 1000));

  if (crashed) {
    console.error('[REPRO] Tab crash detected during monitoring');
    break;
  }

  // Check responsiveness with a short timeout
  try {
    const readyState = await Promise.race([
      page.evaluate(() => document.readyState),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
    ]);
    // console.log(`[REPRO] t=${Math.round((Date.now()-start)/1000)}s readyState=${readyState}`);
  } catch (e) {
    responsive = false;
    console.error('[REPRO] Page became unresponsive at t=' + Math.round((Date.now()-start)/1000) + 's');
    break;
  }
}

// Analyze console messages for loops
let loopDetected = false;
let loopMessage = '';
for (const [key, count] of messageCounts) {
  if (count > CONSOLE_LOOP_THRESHOLD) {
    loopDetected = true;
    loopMessage = `"${key}" repeated ${count} times`;
    console.error(`[REPRO] Console loop: ${loopMessage}`);
  }
}

// Summary
console.log('\n=== REPRO SUMMARY ===');
console.log(`Duration: ${Math.round((Date.now()-start)/1000)}s`);
console.log(`Tab crash: ${crashed}`);
console.log(`Responsive: ${responsive}`);
console.log(`Page errors: ${pageErrorCount}`);
console.log(`Console messages: ${consoleMessages.length}`);
console.log(`Console loop detected: ${loopDetected}`);
if (loopDetected) console.log(`  → ${loopMessage}`);

// Top 5 most frequent console messages
const sorted = [...messageCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
console.log('\nTop console messages:');
for (const [key, count] of sorted) {
  console.log(`  [${count}x] ${key}`);
}

// Take screenshot for visual verification
try {
  await page.screenshot({ path: '/tmp/repro-screenshot.png', fullPage: false });
  console.log('[REPRO] Screenshot saved to /tmp/repro-screenshot.png');
} catch(e) {
  console.log('[REPRO] Screenshot failed:', e.message);
}

await browser.close();

// Exit RED if any failure condition
const isRed = crashed || !responsive || loopDetected || pageErrorCount > 0;
console.log(`\n[REPRO] Result: ${isRed ? 'RED (bug reproduced)' : 'GREEN (no issue)'}`);
process.exit(isRed ? 1 : 0);
