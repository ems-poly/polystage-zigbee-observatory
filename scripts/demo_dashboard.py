#!/usr/bin/env python3
"""Serve the real dashboard with isolated, visibly synthetic documentation data.

Run: .venv/bin/python scripts/demo_dashboard.py
Views: / (energy), /?view=history, /?portable=1
This server neither imports the scanner nor reads the project's data directory.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatory import Observatory  # noqa: E402

BANNER = """<aside id="docs-demo-banner" role="note">DOCS DEMO / SYNTHETIC DATA
<span>Illustration only — these are generated examples, not a household survey.</span></aside>"""
DEMO_STYLE = """<style>
#docs-demo-banner{position:fixed;top:0;left:0;right:0;z-index:99;background:#9df4bc;color:#102019;padding:11px 24px;font:700 13px system-ui;letter-spacing:.06em;box-shadow:0 2px 12px #0005}
#docs-demo-banner span{font-weight:400;letter-spacing:0;margin-left:18px}
body{padding-top:46px}
@media(max-width:760px){#docs-demo-banner{font-size:11px;padding:9px 14px}#docs-demo-banner span{display:block;margin-left:0;font-size:10px}body{padding-top:51px}}
</style>"""
HISTORY_STYLE = """<style>
main>section.panel:has(#chart),#portablePanel{display:none!important}
main>header{margin-bottom:12px}main>header h1{font-size:30px}
main>.toolbar,main>.grid{display:none}
#trend{height:200px}
main>.bottom:has(#history){grid-template-columns:1fr}
main>.bottom:has(#history)>section:not(:has(#history)){display:none}
#history{height:220px}
</style>"""


class Demo:
    def __init__(self, directory: Path):
        self.obs = Observatory(directory)
        self.obs.configure({
            "networks": {"Hue": 11, "iHost": 20, "HAN": 15},
            "location": "Demo lab", "han_band": "2.4GHz",
            "han_model": "Demonstration hub", "wifi_channel": 6,
            "wifi_width": 20,
        })
        self.anchor = time.time()
        self.sequence = 0
        self.latest = None
        for index in range(180):
            self.append(self.anchor - (179 - index) * 5)
        self.obs.add_event({
            "network": "iHost", "kind": "delay",
            "note": "Synthetic example: delayed response", "latency": 420,
        }, now=self.anchor - 250)
        self.obs.add_event({
            "network": "iHost", "kind": "recovery",
            "note": "Synthetic example: normal response resumed",
        }, now=self.anchor - 100)

    def append(self, stamp: float):
        channels = []
        for channel in range(11, 27):
            curve = 25 + 88 * math.exp(-((channel - 19) / 2.4) ** 2)
            wave = 11 * math.sin(self.sequence / 8 + channel / 2)
            pulse = 65 * math.exp(-((self.sequence - 129) / 11) ** 2)
            pulse *= math.exp(-((channel - 20) / 1.4) ** 2)
            value = max(0, min(255, round(curve + wave + pulse + (channel % 4) * 5)))
            channels.append({"channel": channel, "raw": value,
                             "percent": round(value * 100 / 255, 1)})
        self.latest = {"time": stamp, "channels": channels,
                       "location": "Demo lab", "synthetic": True}
        self.obs.add_scan(self.latest)
        self.sequence += 1

    def advance(self):
        now = time.time()
        while self.latest["time"] + 5 <= now:
            self.append(self.latest["time"] + 5)

    @staticmethod
    def portable(request):
        return request.cookies.get("docs_demo_portable") == "1"

    async def index(self, request):
        html = (ROOT / "dashboard/index.html").read_text()
        # macOS headless Chrome can retain a minimum 500px layout viewport even
        # for a 390px screenshot. Constrain only this documentation capture.
        mobile_style = "<style>body,main{width:390px;max-width:100vw}</style>" if request.query.get("view") == "mobile" else ""
        html = html.replace("<main>", DEMO_STYLE + (HISTORY_STYLE if request.query.get("view") == "history" else "") + mobile_style + BANNER + "<main>", 1)
        html = html.replace("<title>Zigbee channel observatory</title>",
                            "<title>PolyStage · Documentation demo</title>")
        html = html.replace("no generated readings.",
                            "DOCS DEMO: all displayed readings and events are synthetic.")
        response = web.Response(text=html, content_type="text/html")
        response.set_cookie("docs_demo_portable", "1" if request.query.get("portable") == "1" else "0", samesite="Strict")
        return response

    async def state(self, request):
        self.advance()
        return web.json_response({
            "status": "scanning", "error": None, "updated": self.latest["time"],
            "channels": self.latest["channels"], "history": [], "scans": self.sequence,
            "location": "Demo lab", "networks": self.obs.settings["networks"],
            "settings": self.obs.settings, "radio": {"description": "Synthetic documentation fixture"},
            "transport": "portable" if self.portable(request) else "uart",
            "synthetic": True,
        })

    async def settings(self, request):
        return web.json_response(self.obs.settings)

    async def analysis(self, request):
        self.advance()
        try:
            minutes = int(request.query.get("minutes", "15"))
            if not 1 <= minutes <= 1440:
                raise ValueError("Invalid history window")
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc))
        value = self.obs.summary(minutes, request.query.get("location") or None,
                                 request.query.get("session") or None)
        value["synthetic"] = True
        return web.json_response(value)

    async def portable_status(self, request):
        self.advance()
        latest = None
        if self.portable(request):
            latest = {
                "location": "Demo lab", "device_ip": "demo-device.local",
                "received_at": self.latest["time"], "captured_at": self.latest["time"],
                "wifi_off_during_zigbee": True, "queue_dropped": 0,
                "wifi": [
                    {"ssid": "Demo AP north", "channel": 1, "rssi": -67},
                    {"ssid": "Demo AP lab", "channel": 6, "rssi": -48},
                    {"ssid": "Demo AP south", "channel": 11, "rssi": -75},
                ], "synthetic": True,
            }
        return web.json_response({"enabled": self.portable(request), "latest": latest,
                                  "samples_received": self.sequence, "synthetic": True})

    async def portable_access(self, request):
        return web.json_response({"url": "http://demo-dashboard.invalid", "code": None,
                                  "synthetic": True})

    async def unavailable(self, request):
        raise web.HTTPNotFound(text="No real device data is available in this documentation demo")

    async def read_only(self, request):
        raise web.HTTPForbidden(text="Documentation demo is read-only and uses synthetic data")

    async def export(self, request):
        return web.json_response({"synthetic": True, "notice": "Documentation fixture, not real measurements",
                                  "latest": self.latest})

    def application(self):
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_get("/api/state", self.state)
        app.router.add_get("/api/settings", self.settings)
        app.router.add_get("/api/analysis", self.analysis)
        app.router.add_get("/api/export", self.export)
        app.router.add_get("/api/portable/status", self.portable_status)
        app.router.add_get("/api/portable/access", self.portable_access)
        app.router.add_get("/api/ihost-export", self.unavailable)
        for path in ("settings", "events", "sessions", "networks"):
            app.router.add_post("/api/" + path, self.read_only)
        app.router.add_static("/dashboard/", ROOT / "dashboard", show_index=False)
        return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8875)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="polystage-docs-demo-") as directory:
        demo = Demo(Path(directory))
        try:
            print("DOCS DEMO / SYNTHETIC DATA — no hardware or private runtime files are used", flush=True)
            web.run_app(demo.application(), host="127.0.0.1", port=args.port)
        finally:
            demo.obs.db.close()


if __name__ == "__main__":
    main()
