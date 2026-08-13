"""
serve.py — local server that makes the dashboard's Update button work.

A static HTML page cannot run Python. This serves output/ over localhost and
exposes a small API, namespaced per universe so the URL itself says what to
rebuild (the page only ever calls a relative "api/..." path):

    GET  /<universe>/api/status    -> {"live":true,"running":bool,...}
    POST /<universe>/api/refresh   -> runs update.py + make_dashboard.py
                                      for that universe, in the background

    python3 serve.py            # http://localhost:8760  (index of universes)
    python3 serve.py --port N
    python3 serve.py --animate  # also rebuild animation files on refresh

Opened any other way (double-clicked file, hosted copy), the page finds no
API and the Update button falls back to copying the refresh command.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVE_DIR = os.path.join(ROOT, "output")

STATE: dict = {}          # per-universe {running, error, finished}
LOCK = threading.Lock()
ANIMATE = False


def _state(u: str) -> dict:
    return STATE.setdefault(u, {"running": False, "error": None, "finished": 0})


def _run_pipeline(u: str) -> None:
    base = [sys.executable]
    cmds = [base + ["update.py", "--universe", u] + (["--animate"] if ANIMATE else []),
            base + ["make_dashboard.py", "--universe", u]]
    try:
        for cmd in cmds:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               timeout=900)
            if p.returncode != 0:
                tail = (p.stderr or p.stdout or "").strip().splitlines()
                raise RuntimeError(tail[-1] if tail else
                                   f"{cmd[1]} exited {p.returncode}")
        with LOCK:
            _state(u)["error"] = None
    except Exception as exc:                       # surfaced in the UI
        with LOCK:
            _state(u)["error"] = str(exc)[:300]
    finally:
        with LOCK:
            s = _state(u)
            s["running"] = False
            s["finished"] += 1


def _asof(u: str) -> str | None:
    p = os.path.join(SERVE_DIR, u, "dashboard.html")
    if not os.path.exists(p):
        return None
    return datetime.datetime.fromtimestamp(
        os.path.getmtime(p)).strftime("%d %b %Y %H:%M")


def _split_api(path: str) -> tuple[str, str] | None:
    """'/countries/api/refresh' -> ('countries', 'refresh')"""
    parts = path.split("?")[0].strip("/").split("/")
    if len(parts) == 3 and parts[1] == "api" and parts[0] in config.UNIVERSES:
        return parts[0], parts[2]
    return None


INDEX_HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>rrg-kit</title><style>
:root{color-scheme:light dark;
--line:#363b45;--accent:#5b9bd5;--ok:#4caf6a;--busy:#d9a441;--err:#e06c5b;
--muted:#767d88}
body{margin:0;background:#14161a;color:#e6e8ec;
font:15px system-ui,-apple-system,sans-serif;display:flex;
min-height:100vh;align-items:center;justify-content:center}
@media(prefers-color-scheme:light){body{background:#faf9f7;color:#16181d}
:root{--line:#cfccc6;--muted:#8a8880}}
.w{max-width:620px;padding:32px;width:100%}
.top{display:flex;align-items:baseline;justify-content:space-between;
gap:12px;flex-wrap:wrap;margin-bottom:4px}
h1{font-size:22px;margin:0;letter-spacing:-.02em}
p{opacity:.65;margin:0 0 24px;font-size:14px}
.row{display:flex;align-items:center;gap:12px;padding:12px 16px;
margin-bottom:8px;border:1px solid var(--line);border-radius:6px}
.row a{flex:1;display:flex;flex-direction:column;gap:2px;
text-decoration:none;color:inherit;min-width:0}
.row a:hover b{color:var(--accent)}
b{font-size:15px}
.meta{font-family:ui-monospace,Menlo,monospace;font-size:11px;
color:var(--muted);letter-spacing:.05em}
.asof{font-family:ui-monospace,Menlo,monospace;font-size:11px;
color:var(--muted);text-align:right;min-width:120px}
button{font-family:ui-monospace,Menlo,monospace;font-size:11px;
letter-spacing:.06em;text-transform:uppercase;padding:6px 12px;
border:1px solid var(--line);border-radius:4px;background:transparent;
color:inherit;cursor:pointer;white-space:nowrap}
button:hover:not(:disabled){border-color:var(--accent)}
button:disabled{opacity:.5;cursor:default}
button.busy{color:var(--busy);border-color:var(--busy)}
button.done{color:var(--ok);border-color:var(--ok)}
button.err{color:var(--err);border-color:var(--err)}
#all{padding:7px 14px}
</style></head><body><div class="w">
<div class="top"><h1>rrg-kit</h1>
<button id="all" type="button">Refresh all</button></div>
<p>Relative rotation dashboards &middot; refresh pulls fresh prices and
rebuilds every page.</p>
"""

INDEX_TAIL = """
<script>
function status(u){return fetch('/'+u+'/api/status',{cache:'no-store'})
  .then(function(r){return r.json()})}
function paint(u){status(u).then(function(s){
  var el=document.querySelector('[data-asof="'+u+'"]');
  if(el&&s.asof)el.textContent='data: '+s.asof;
  if(s.running)track(u);
}).catch(function(){})}
function track(u){
  var b=document.querySelector('[data-r="'+u+'"]');
  if(b){b.disabled=true;b.className='busy';b.textContent='Refreshing\\u2026';}
  (function tick(){setTimeout(function(){status(u).then(function(s){
    if(s.running)return tick();
    if(b){b.disabled=false;
      b.className=s.error?'err':'done';
      b.textContent=s.error?'Failed \\u2014 retry':'Refreshed';
      setTimeout(function(){b.className='';b.textContent='Refresh';},4000);}
    paint(u);
  }).catch(tick)},2000)})();
}
function refresh(u){return fetch('/'+u+'/api/refresh',{method:'POST'})
  .then(function(){track(u)})}
var US=[].map.call(document.querySelectorAll('[data-r]'),
  function(b){return b.dataset.r});
US.forEach(paint);
document.querySelectorAll('[data-r]').forEach(function(b){
  b.addEventListener('click',function(){refresh(b.dataset.r)});
});
document.getElementById('all').addEventListener('click',function(){
  var b=this;b.disabled=true;b.textContent='Refreshing\\u2026';
  (function next(i){
    if(i>=US.length){b.disabled=false;b.textContent='Refresh all';return}
    var u=US[i];
    refresh(u);
    (function wait(){setTimeout(function(){status(u).then(function(s){
      s.running?wait():next(i+1)}).catch(wait)},2000)})();
  })(0);
});
</script></body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SERVE_DIR, **kw)

    def _json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if self.path.endswith((".html", "/")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def do_GET(self):
        api = _split_api(self.path)
        if api and api[1] == "status":
            u = api[0]
            with LOCK:
                s = _state(u)
                return self._json({"live": True, "universe": u,
                                   "running": s["running"], "error": s["error"],
                                   "finished": s["finished"], "asof": _asof(u)})
        if self.path.split("?")[0] in ("/", "/index.html"):
            rows = []
            for u, spec in config.UNIVERSES.items():
                if not os.path.exists(os.path.join(SERVE_DIR, u,
                                                   "dashboard.html")):
                    continue
                bench = spec.get("benchmark_label", spec["benchmark"])
                rows.append(
                    f'<div class="row"><a href="/{u}/dashboard.html">'
                    f'<b>{spec["label"]}</b>'
                    f'<span class="meta">{len(spec["members"])} vs {bench}'
                    f'</span></a>'
                    f'<span class="asof" data-asof="{u}"></span>'
                    f'<button type="button" data-r="{u}">Refresh</button>'
                    f'</div>')
            if not rows:
                rows = ["<p>Nothing built yet — run <code>python3 update.py"
                        "</code>.</p>"]
            page = (INDEX_HEAD + "".join(rows) + INDEX_TAIL).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        return super().do_GET()

    def do_POST(self):
        api = _split_api(self.path)
        if not api or api[1] != "refresh":
            return self._json({"error": "not found"}, 404)
        u = api[0]
        with LOCK:
            s = _state(u)
            if s["running"]:
                return self._json({"started": False, "running": True})
            s["running"] = True
            s["error"] = None
        threading.Thread(target=_run_pipeline, args=(u,), daemon=True).start()
        return self._json({"started": True})

    def log_message(self, fmt, *args):
        # args can contain non-strings (e.g. HTTPStatus from send_error) —
        # coerce before filtering, or a 404 kills the request thread.
        if "/api/" not in " ".join(str(a) for a in args):
            super().log_message(fmt, *args)


def main() -> None:
    global ANIMATE
    ap = argparse.ArgumentParser(description="Serve the RRG dashboards")
    ap.add_argument("--port", type=int, default=8760)
    ap.add_argument("--animate", action="store_true",
                    help="rebuild animation files on refresh too (slower)")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    ANIMATE = args.animate

    url = f"http://localhost:{args.port}/"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError:
        # Port taken. If it's a previous instance of THIS app, don't crash —
        # just open the browser at the running server and bow out.
        import urllib.request
        try:
            probe = json.load(urllib.request.urlopen(
                f"{url}{list(config.UNIVERSES)[0]}/api/status", timeout=3))
        except Exception:
            probe = None
        if probe and probe.get("live"):
            print(f"rrg-kit is already running at {url} — opening it.")
            if not args.no_open:
                webbrowser.open(url)
            return
        raise SystemExit(
            f"port {args.port} is taken by something else — "
            f"try: python3 serve.py --port {args.port + 1}")

    print(f"rrg-kit: {url}\nUpdate button is live. Ctrl-C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
