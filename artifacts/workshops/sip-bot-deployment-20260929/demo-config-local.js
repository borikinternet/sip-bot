/* Local WSL workshop only; do not replace the public demo configuration upstream. */
const workshopHost = window.location.hostname;
window.DEMO_PUBLIC_URL = `${window.location.protocol}//${window.location.host}/`;
window.DEMO_QR_ASSET = "/assets/qr-local-workshop.png";
window.DEMO_SIP_CONFIG = {
  wsUrl: `wss://${workshopHost}:7443`,
  sipDomain: "192.168.1.74",
  authUser: "1000",
  password: "Workshop-2026!",
  targetUri: "sip:7100@192.168.1.74",
};
