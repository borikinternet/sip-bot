from __future__ import annotations

from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def test_conference_page_defaults_to_public_browser_endpoints() -> None:
    config = (FRONTEND / "demo-config.js").read_text(encoding="utf-8")
    app = (FRONTEND / "app.js").read_text(encoding="utf-8")
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")

    assert '"https://demo.libnas.ru/"' in config
    assert '"wss://demo.libnas.ru:7443"' in config
    assert '"demo.libnas.ru"' in config
    assert '"sip:7100@demo.libnas.ru"' in config
    assert '"/assets/qr-demo-domain.png"' in config
    assert 'new URL(url, window.DEMO_PUBLIC_URL).href' in app
    assert 'new URL(`/ws/${status.session_id}`, window.DEMO_PUBLIC_URL)' in app
    assert 'src="/assets/jssip-3.10.0.min.js"' in html
    assert not (FRONTEND / "assets" / "qr-demo-ip.png").exists()

    qr = FRONTEND / "assets" / "qr-demo-domain.png"
    assert qr.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    for local_address in ("192.168.1.74", "172.16.15.72", "127.0.0.1"):
        assert local_address not in config + app + html
    assert "http://localhost" not in config + app + html
    assert "ws://localhost" not in config + app + html
