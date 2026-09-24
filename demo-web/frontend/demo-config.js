/* Browser-facing conference endpoint; internal service connections are configured elsewhere. */
window.DEMO_PUBLIC_URL = window.DEMO_PUBLIC_URL || "https://demo.libnas.ru/";
window.DEMO_QR_ASSET = window.DEMO_QR_ASSET || "/assets/qr-demo-domain.png";
window.DEMO_SIP_CONFIG = window.DEMO_SIP_CONFIG || {
  wsUrl: "wss://demo.libnas.ru:7443",
  sipDomain: "demo.libnas.ru",
  authUser: "1000",
  password: "Workshop-2026!",
  targetUri: "sip:7100@demo.libnas.ru",
};
