#!/usr/bin/env node
// Read-only transport probe: verifies FreeSWITCH SIP-over-WSS upgrade.
import tls from 'node:tls';
import { isIP } from 'node:net';
import { randomBytes } from 'node:crypto';

const host = process.argv[2];
const port = Number(process.argv[3] ?? '7443');
if (!host || !Number.isInteger(port) || port < 1 || port > 65535) {
  process.stderr.write('Usage: node webrtc_wss_probe.mjs HOST [PORT]\n');
  process.exit(2);
}

const key = randomBytes(16).toString('base64');
const socket = tls.connect({ host, port, ...(isIP(host) ? {} : { servername: host }), rejectUnauthorized: false });
socket.setTimeout(8000);
let response = '';
socket.on('secureConnect', () => {
  const cert = socket.getPeerCertificate();
  console.log(JSON.stringify({
    tlsProtocol: socket.getProtocol(),
    authorized: socket.authorized,
    authorizationError: socket.authorizationError ?? null,
    subject: cert.subject ?? null,
    subjectaltname: cert.subjectaltname ?? null,
    validTo: cert.valid_to ?? null,
  }));
  socket.write([
    'GET / HTTP/1.1',
    `Host: ${host}:${port}`,
    'Upgrade: websocket',
    'Connection: Upgrade',
    `Sec-WebSocket-Key: ${key}`,
    'Sec-WebSocket-Version: 13',
    'Sec-WebSocket-Protocol: sip',
    '', '',
  ].join('\r\n'));
});
socket.on('data', chunk => {
  response += chunk.toString('latin1');
  const end = response.indexOf('\r\n\r\n');
  if (end < 0) return;
  const headers = response.slice(0, end);
  console.log(headers);
  const ok = /^HTTP\/1\.1 101 /m.test(headers) &&
    /^Sec-WebSocket-Protocol:\s*sip\s*$/im.test(headers);
  socket.end();
  process.exitCode = ok ? 0 : 1;
});
socket.on('timeout', () => socket.destroy(new Error('WSS upgrade timed out')));
socket.on('error', error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
