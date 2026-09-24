/* Conference-only local WSL inputs. Replace the URL and QR asset for the final deployment. */
window.DEMO_PUBLIC_URL = window.DEMO_PUBLIC_URL || "https://192.168.1.74:8443/";
window.DEMO_QR_ASSET = window.DEMO_QR_ASSET || "/assets/qr-demo-ip.png";
window.DEMO_SIP_CONFIG = window.DEMO_SIP_CONFIG || {
  wsUrl: window.location.hostname === "172.16.15.72"
    ? "wss://172.16.15.72:17445"
    : "wss://192.168.1.74:7443",
  sipDomain: "192.168.1.74",
  authUser: "1000",
  password: "Workshop-2026!",
  targetUri: "sip:7100@192.168.1.74",
};
