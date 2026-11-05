import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const outputDir = path.resolve(process.cwd(), 'screenshots');

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const viewports = [
  { name: 'overview_1440.png', width: 1440, height: 900 },
  { name: 'overview_1024.png', width: 1024, height: 768 },
  { name: 'overview_390.png', width: 390, height: 844 },
];

async function run() {
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  for (const vp of viewports) {
    const page = await browser.newPage();
    await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });
    await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle0', timeout: 15000 });
    // 等待 1 秒确保 TanStack Query 与过渡动效稳定
    await new Promise((r) => setTimeout(r, 1000));
    const outPath = path.join(outputDir, vp.name);
    await page.screenshot({ path: outPath, fullPage: true });
    console.log(`[Captured] ${vp.name} (${vp.width}x${vp.height}) -> ${outPath}`);
    await page.close();
  }

  await browser.close();
  console.log('All screenshots captured successfully!');
}

run().catch((err) => {
  console.error('Capture failed:', err);
  process.exit(1);
});
