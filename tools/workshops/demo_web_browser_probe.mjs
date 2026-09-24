#!/usr/bin/env node
// One-off, bounded check of the actual conference page from the Windows host.
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const modules = process.env.RUNTIME_NODE_MODULES;
const url = process.env.DEMO_TEST_URL ?? 'https://172.16.15.72:8443/';
if (!modules) throw new Error('RUNTIME_NODE_MODULES is required');
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright', 'index.mjs')).href);
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
});
let result = { url, phases: [] };
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, permissions: ['microphone'] });
  const page = await context.newPage();
  page.on('pageerror', (error) => result.phases.push(`pageerror: ${error.message}`));
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.locator('#call-button').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('#call-button').disabled, null, { timeout: 15000 });
  result.secureContext = await page.evaluate(() => window.isSecureContext);
  result.mediaDevices = await page.evaluate(() => Boolean(navigator.mediaDevices?.getUserMedia));
  result.callerId = await page.locator('#caller-id').textContent();
  result.phases.push(`ready: ${await page.locator('#status-text').textContent()}`);
  await page.locator('#call-button').click();
  const deadline = Date.now() + 30000;
  let last = '';
  while (Date.now() < deadline) {
    const phase = await page.locator('#call-message').textContent();
    if (phase && phase !== last) {
      result.phases.push(phase);
      last = phase;
    }
    if (/SIP-соединение установлено|Звонок не начался|SIP-вызов не состоялся/.test(phase ?? '')) break;
    await page.waitForTimeout(200);
  }
  result.callConnected = result.phases.some((phase) => phase.includes('SIP-соединение установлено'));
  if (result.callConnected) {
    result.hangupButton = await page.locator('#call-button').textContent();
    await page.waitForTimeout(10000);
    result.audioElement = await page.evaluate(() => {
      const audio = document.querySelector('#remote-audio');
      return {
        paused: audio.paused,
        muted: audio.muted,
        volume: audio.volume,
        currentTime: audio.currentTime,
        readyState: audio.readyState,
        tracks: audio.srcObject?.getAudioTracks().map((track) => ({ readyState: track.readyState, muted: track.muted })) ?? [],
      };
    });
    result.audioStatus = await page.locator('#audio-message').textContent();
    result.rtp = await page.evaluate(async () => {
      const connection = typeof state !== 'undefined' ? state.call?.connection : null;
      if (!connection) return null;
      const stats = await connection.getStats();
      return [...stats.values()]
        .filter((item) => item.type === 'inbound-rtp' || item.type === 'outbound-rtp')
        .map((item) => ({ type: item.type, kind: item.kind, bytesReceived: item.bytesReceived, bytesSent: item.bytesSent, packetsLost: item.packetsLost }));
    });
  }
  if (result.callConnected) await page.locator('#call-button').click();
  await page.waitForTimeout(500);
  console.log(JSON.stringify(result, null, 2));
  if (!result.callConnected) process.exitCode = 1;
} finally {
  await browser.close();
}
