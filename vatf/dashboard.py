from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .interfaces import DashboardServer


HTML = """<!doctype html>
<html><head><meta charset='utf-8'><title>V-ATF Dashboard</title>
<style>body{font-family:Arial;margin:20px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}pre{background:#f7f7f7;padding:10px}</style>
</head><body>
<h1>V-ATF Runs</h1>
<div id='runs'></div>
<script>
async function load(){
 const runs=await (await fetch('/api/runs')).json();
 let h='<table><tr><th>Run</th><th>Scenario</th><th>Status</th><th>Duration</th><th>Commit</th><th>Device</th></tr>';
 for (const r of runs){h+=`<tr><td><a href='#' onclick='detail("${r.run_id}","${r.scenario_id}")'>${r.run_id}</a></td><td>${r.scenario_id}</td><td>${r.status}</td><td>${r.duration_s}s</td><td>${r.git_commit.slice(0,8)}</td><td>${r.device_name}</td></tr>`}
 h+='</table><h2>Run Detail</h2><pre id="detail">Select a run</pre><h2>Failure View</h2><pre id="fail">Loading...</pre>';
 document.getElementById('runs').innerHTML=h;
 failures = runs.filter(r=>r.status!=='PASS').reduce((a,r)=>{a[r.scenario_id]=(a[r.scenario_id]||0)+1;return a;},{});
 document.getElementById('fail').textContent=JSON.stringify(failures,null,2);
}
async function detail(run,scenario){
 const data=await (await fetch(`/api/runs/${run}/${scenario}`)).json();
 document.getElementById('detail').textContent=JSON.stringify(data,null,2);
}
load();
</script>
</body></html>"""


class LocalDashboardServer(DashboardServer):
    def __init__(self, out_root: str = "out") -> None:
        self.out_root = Path(out_root)

    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        out_root = self.out_root

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, payload: object, status: int = 200) -> None:
                body = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/":
                    body = HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if path == "/api/runs":
                    index = out_root / "run_index.json"
                    data = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
                    self._send_json(data)
                    return

                parts = [p for p in path.split("/") if p]
                if len(parts) == 4 and parts[:2] == ["api", "runs"]:
                    _, _, run_id, scenario_id = parts
                    result_file = out_root / run_id / scenario_id / "scenario_result.json"
                    if not result_file.exists():
                        self._send_json({"error": "not found"}, status=404)
                        return
                    self._send_json(json.loads(result_file.read_text(encoding="utf-8")))
                    return

                self._send_json({"error": "not found"}, status=404)

        server = ThreadingHTTPServer((host, port), Handler)
        print(f"Dashboard running on http://{host}:{port}")
        server.serve_forever()
