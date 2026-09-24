#!/usr/bin/env node
// Local-only FreeSWITCH SIP/WSS and WebRTC media probe using two JsSIP UAs.
import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const host = process.argv[2];
const password = process.env.WEBRTC_PROBE_PASSWORD;
const modules = process.env.RUNTIME_NODE_MODULES;
if (!host || !password || !modules) {
  process.stderr.write('Usage: WEBRTC_PROBE_PASSWORD=... RUNTIME_NODE_MODULES=... node webrtc_browser_probe.mjs WSL_IP\n');
  process.exit(2);
}
const { chromium } = await import(pathToFileURL(path.join(modules, 'playwright', 'index.mjs')).href);
const jsSipUrl = 'https://jssip.net/download/releases/jssip-3.10.0.min.js';
const jsSipResponse = await fetch(jsSipUrl);
if (!jsSipResponse.ok) throw new Error(`JsSIP download: HTTP ${jsSipResponse.status}`);
const jsSipBundle = await jsSipResponse.text();
const server = http.createServer((_req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end('<!doctype html><title>Local WebRTC SIP probe</title>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
    args: [
      '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
      // Isolated disposable browser process only: local FreeSWITCH has a self-signed WSS cert.
      '--ignore-certificate-errors',
      '--disable-features=WebRtcHideLocalIpsWithMdns',
    ],
  });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, permissions: ['microphone'] });
  const page = await context.newPage();
  page.on('console', message => {
    if (message.text().startsWith('probe:')) console.log(message.text());
  });
  page.on('pageerror', error => console.error(`browser page error: ${error.message}`));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.addScriptTag({ content: jsSipBundle });
  const result = await page.evaluate(async ({ host, password }) => {
    const log = [];
    const record = (event, details = {}) => {
      log.push({ at: new Date().toISOString(), event, ...details });
      console.log(`probe: ${event} ${JSON.stringify(details)}`);
    };
    const timeout = (name, ms = 20000) => new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${name} timed out after ${ms}ms`)), ms));
    const once = (emitter, success, failure, name, ms = 20000) =>
      Promise.race([
        new Promise((resolve, reject) => {
          emitter.once(success, resolve);
          for (const event of failure) emitter.once(event, value => reject(new Error(`${name}: ${event} ${JSON.stringify(value?.cause ?? '')}`)));
        }),
        timeout(name, ms),
      ]);
    const makeUA = extension => {
      const socket = new JsSIP.WebSocketInterface(`wss://${host}:7443`);
      const ua = new JsSIP.UA({
        sockets: [socket], uri: `sip:${extension}@${host}`, password,
        register: true, register_expires: 120,
        session_timers: false,
      });
      ua.on('connected', () => record(`${extension}.wss_connected`));
      ua.on('registered', () => record(`${extension}.registered`));
      ua.on('registrationFailed', event => record(`${extension}.registration_failed`, { cause: event.cause }));
      return ua;
    };
    const callerUA = makeUA('1000');
    const calleeUA = makeUA('1001');
    let callerSession;
    let calleeSession;
    let failure;
    try {
      const registered = Promise.all([
        once(callerUA, 'registered', ['registrationFailed'], '1000 registration'),
        once(calleeUA, 'registered', ['registrationFailed'], '1001 registration'),
      ]);
      callerUA.start();
      calleeUA.start();
      await registered;
      const incoming = once(calleeUA, 'newRTCSession', [], 'incoming call');
      callerSession = callerUA.call(`sip:1001@${host}`, {
        mediaConstraints: { audio: true, video: false },
        pcConfig: { iceServers: [] },
      });
      callerSession.on('failed', event => record('caller.failed', {
        cause: event.cause, originator: event.originator,
        status: event.message?.status_code, reason: event.message?.reason_phrase,
      }));
      callerSession.on('confirmed', () => record('caller.confirmed'));
      const callConfirmed = once(callerSession, 'confirmed', ['failed'], 'caller confirmation', 30000);
      const incomingEvent = await incoming;
      calleeSession = incomingEvent.session;
      record('callee.incoming', { offerHasIce: /a=ice-ufrag:/.test(incomingEvent.request?.body ?? ''),
        offerHasFingerprint: /a=fingerprint:/.test(incomingEvent.request?.body ?? '') });
      calleeSession.on('failed', event => record('callee.failed', {
        cause: event.cause, originator: event.originator,
        status: event.message?.status_code, reason: event.message?.reason_phrase,
      }));
      calleeSession.answer({ mediaConstraints: { audio: true, video: false }, pcConfig: { iceServers: [] } });
      await callConfirmed;
      await new Promise(resolve => setTimeout(resolve, 4500));
      const sdpFeatures = sdp => ({
        fingerprint: /a=fingerprint:/.test(sdp ?? ''),
        ice: /a=ice-ufrag:/.test(sdp ?? ''),
        rtcpMux: /a=rtcp-mux/.test(sdp ?? ''),
      });
      const summarize = async (session, side) => {
        const pc = session.connection;
        const report = await pc.getStats();
        const values = [...report.values()];
        const outbound = values.filter(s => s.type === 'outbound-rtp' && s.kind === 'audio');
        const inbound = values.filter(s => s.type === 'inbound-rtp' && s.kind === 'audio');
        const selected = values.find(s => s.type === 'candidate-pair' && s.selected) ??
          values.find(s => s.type === 'transport' && s.selectedCandidatePairId && report.get(s.selectedCandidatePairId));
        const stats = {
          side, signalingState: pc.signalingState, connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState, dtlsState: values.find(s => s.type === 'transport')?.dtlsState,
          outbound: outbound.map(s => ({ packetsSent: s.packetsSent, bytesSent: s.bytesSent })),
          inbound: inbound.map(s => ({ packetsReceived: s.packetsReceived, bytesReceived: s.bytesReceived })),
          candidatePair: selected ? { state: selected.state, bytesSent: selected.bytesSent, bytesReceived: selected.bytesReceived } : null,
          localSdpFeatures: sdpFeatures(pc.localDescription?.sdp),
          remoteSdpFeatures: sdpFeatures(pc.remoteDescription?.sdp),
        };
        record(`${side}.stats`, stats);
        return stats;
      };
      const sides = await Promise.all([summarize(callerSession, 'caller'), summarize(calleeSession, 'callee')]);
      const mediaOk = sides.every(s =>
        s.connectionState === 'connected' && s.dtlsState === 'connected' &&
        s.localSdpFeatures.fingerprint && s.localSdpFeatures.ice &&
        s.remoteSdpFeatures.fingerprint && s.remoteSdpFeatures.ice &&
        s.outbound.some(t => t.bytesSent > 0 && t.packetsSent > 0) &&
        s.inbound.some(t => t.bytesReceived > 0 && t.packetsReceived > 0));
      if (!mediaOk) throw new Error('ICE/DTLS or bidirectional RTP counters are not healthy');
      const ended = once(calleeSession, 'ended', ['failed'], 'callee BYE', 10000);
      callerSession.terminate();
      await ended;
      record('bye.completed');
      return { ok: true, log, sides };
    } catch (error) {
      failure = error.message;
      record('probe.failed', { message: failure });
      return { ok: false, failure, log };
    } finally {
      if (callerSession && !callerSession.isEnded()) callerSession.terminate();
      if (calleeSession && !calleeSession.isEnded()) calleeSession.terminate();
      callerUA.unregister();
      calleeUA.unregister();
      await new Promise(resolve => setTimeout(resolve, 1000));
      callerUA.stop();
      calleeUA.stop();
    }
  }, { host, password });
  console.log(JSON.stringify(result, null, 2));
  if (!result.ok) process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
