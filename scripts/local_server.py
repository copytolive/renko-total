#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ.get('COPYTOLIVE_RENKO_ROOT', '/Users/Shared/WorkspaceBersama/COPYTOLIVE_RENKO_TOTAL')).expanduser().resolve()
WEB = ROOT / 'web'
LOGS = ROOT / 'logs'
MANIFESTS = ROOT / 'manifests'
LOGS.mkdir(parents=True, exist_ok=True)
MANIFESTS.mkdir(parents=True, exist_ok=True)
STATE_FILE = MANIFESTS / 'local_jobs.json'
LOCK = threading.Lock()
JOBS: dict[str, dict] = {}


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def which_uv():
    candidates = [
        Path.home() / 'Library/Python/3.13/bin/uv',
        Path.home() / '.local/bin/uv',
        Path.home() / '.cargo/bin/uv',
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return shutil.which('uv')


def which_npm():
    fixed = Path.home() / '.nvm/versions/node/v22.23.2/bin/npm'
    if fixed.exists():
        return str(fixed)
    versions = sorted((Path.home() / '.nvm/versions/node').glob('v*/bin/npm')) if (Path.home() / '.nvm/versions/node').exists() else []
    if versions:
        return str(versions[-1])
    return shutil.which('npm')


def which_node():
    npm = which_npm()
    if npm:
        p = Path(npm).with_name('node')
        if p.exists():
            return str(p)
    return shutil.which('node')


def python_bin():
    p = ROOT / '.venv/bin/python'
    return str(p if p.exists() else Path(shutil.which('python3') or '/usr/bin/python3'))


def run_capture(cmd, cwd=None, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {'ok': p.returncode == 0, 'returncode': p.returncode, 'out': (p.stdout + p.stderr)[-12000:]}
    except Exception as e:
        return {'ok': False, 'returncode': -1, 'out': repr(e)}


def save_jobs():
    with LOCK:
        STATE_FILE.write_text(json.dumps(JOBS, indent=2, sort_keys=True), encoding='utf-8')


def start_job(name: str, cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    with LOCK:
        current = JOBS.get(name)
        if current and current.get('status') == 'running':
            return current
        log = LOGS / f'{name}.log'
        JOBS[name] = {'name': name, 'status': 'running', 'started_at': now(), 'log': str(log), 'cmd': cmd}
        save_jobs()

    def worker():
        try:
            with log.open('a', encoding='utf-8') as f:
                f.write(f'\n[{now()}] START {cmd!r}\n')
                p = subprocess.Popen(cmd, cwd=str(cwd or ROOT), stdout=f, stderr=subprocess.STDOUT, text=True, env=env)
                rc = p.wait()
                f.write(f'[{now()}] EXIT {rc}\n')
            with LOCK:
                JOBS[name].update({'status': 'pass' if rc == 0 else 'fail', 'returncode': rc, 'finished_at': now()})
                save_jobs()
        except Exception as e:
            with LOCK:
                JOBS[name].update({'status': 'fail', 'returncode': -1, 'error': repr(e), 'finished_at': now()})
                save_jobs()

    threading.Thread(target=worker, daemon=True).start()
    return JOBS[name]


def status_payload():
    py = python_bin()
    npm = which_npm()
    node = which_node()
    uv = which_uv()
    duka = ROOT / 'node/node_modules/.bin/dukascopy-node'
    latest = WEB / 'data/latest.json'
    summary = MANIFESTS / 'xauusd_download_summary.json'
    raw_days = len(list((ROOT / 'data/raw/xauusd').glob('year=*/month=*/day=*/manifest.json'))) if (ROOT / 'data/raw/xauusd').exists() else 0
    return {
        'root': str(ROOT),
        'server': 'ONLINE',
        'python': {'path': py, **run_capture([py, '--version'])},
        'uv': {'path': uv, 'ok': bool(uv)},
        'node': {'path': node, **(run_capture([node, '--version']) if node else {'ok': False, 'out': 'not found'})},
        'npm': {'path': npm, **(run_capture([npm, '--version']) if npm else {'ok': False, 'out': 'not found'})},
        'dukascopy_node': {'path': str(duka), 'ok': duka.exists()},
        'latest_result': {'path': str(latest), 'ok': latest.exists()},
        'download_summary': {'path': str(summary), 'ok': summary.exists()},
        'raw_manifest_days': raw_days,
        'jobs': JOBS,
        'updated_at': now(),
    }


def prepare_cmd():
    py = python_bin()
    uv = which_uv()
    npm = which_npm()
    if not uv:
        raise RuntimeError('uv not found')
    if not npm:
        raise RuntimeError('npm not found')
    node_dir = ROOT / 'node'
    node_dir.mkdir(parents=True, exist_ok=True)
    helper = ROOT / 'scripts/bootstrap_stack.py'
    helper.write_text(f'''#!/usr/bin/env python3\nimport subprocess, pathlib, sys\nROOT=pathlib.Path({str(ROOT)!r})\nuv={uv!r}\npy={py!r}\nnpm={npm!r}\ndef run(cmd,cwd=None):\n print('RUN',cmd,flush=True); p=subprocess.run(cmd,cwd=cwd);\n if p.returncode: raise SystemExit(p.returncode)\nrun([uv,'pip','install','--python',py,'duckdb','pyarrow','pandas','numpy','polars'])\nnode=ROOT/'node'; node.mkdir(parents=True,exist_ok=True)\nif not (node/'package.json').exists(): run([npm,'init','-y'],cwd=node)\nrun([npm,'install','dukascopy-node@1.50.0','lightweight-charts@5.2.1'],cwd=node)\nprint('STACK READY')\n''', encoding='utf-8')
    return [py, str(helper)]


def backtest_cmd(params: dict):
    csvs = sorted((ROOT / 'data/raw/xauusd').glob('year=*/month=*/day=*/*.csv'))
    if not csvs:
        raise RuntimeError('No XAUUSD CSV found. Run smoke or total history first.')
    csv_path = csvs[-1]
    brick = int(params.get('brick', 100))
    sl = int(params.get('sl', 2))
    tp = int(params.get('tp', 4))
    qty = float(params.get('qty', 100))
    out = WEB / 'data/latest.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    return [python_bin(), str(ROOT/'scripts/run_csv_backtest.py'), str(csv_path), '--price-unit', '0.01', '--brick', str(brick), '--sl-bricks', str(sl), '--tp-bricks', str(tp), '--quantity-oz', str(qty), '--out', str(out)]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        with (LOGS / 'web_access.log').open('a', encoding='utf-8') as f:
            f.write(f'[{now()}] {self.address_string()} {fmt % args}\n')

    def send_json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/status':
            return self.send_json(status_payload())
        if path.startswith('/api/log/'):
            name = path.split('/')[-1]
            if not name.replace('-', '').replace('_', '').isalnum():
                return self.send_json({'ok': False, 'error': 'bad log name'}, 400)
            p = LOGS / f'{name}.log'
            return self.send_json({'ok': p.exists(), 'name': name, 'content': p.read_text(encoding='utf-8', errors='replace')[-30000:] if p.exists() else ''})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get('Content-Length', '0') or 0)
        body = self.rfile.read(min(n, 100000)) if n else b''
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
        except Exception:
            payload = {}
        try:
            if path == '/api/prepare':
                return self.send_json({'ok': True, 'job': start_job('prepare_stack', prepare_cmd(), ROOT)})
            if path == '/api/smoke':
                d = str(payload.get('date') or '2026-09-01')
                cmd = [python_bin(), str(ROOT/'scripts/download_xauusd.py'), '--base', str(ROOT), '--from', d, '--to', d, '--smoke']
                return self.send_json({'ok': True, 'job': start_job('xauusd_smoke', cmd, ROOT)})
            if path == '/api/full-history':
                cmd = [python_bin(), str(ROOT/'scripts/download_xauusd.py'), '--base', str(ROOT), '--from', '1999-06-03']
                return self.send_json({'ok': True, 'job': start_job('xauusd_total_history', cmd, ROOT)})
            if path == '/api/backtest':
                return self.send_json({'ok': True, 'job': start_job('backtest_latest', backtest_cmd(payload), ROOT)})
            return self.send_json({'ok': False, 'error': 'not found'}, 404)
        except Exception as e:
            return self.send_json({'ok': False, 'error': str(e)}, 400)


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    print(f'COPYTOLIVE RENKO LOCAL SERVER http://127.0.0.1:5173 root={ROOT}', flush=True)
    httpd = ThreadingHTTPServer(('127.0.0.1', 5173), Handler)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
