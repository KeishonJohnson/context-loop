"""Exercise the installed Codex sandbox, not a mock (no credentials or remote traffic)."""
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from context_loop.transport import profile, check_command

codex = shutil.which('codex')
assert codex, 'Codex CLI required'
with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as directory:
    root = Path(directory)
    (root / 'workspace').mkdir()
    (root / 'Goal.md').write_text('owner contract')
    def run(code, writable=False):
        command = [codex, 'sandbox', '-P', 'context-loop', '-C', str(root / 'workspace'), *profile(root, 'context-loop', writable), '--', sys.executable, '-B', '-c', code]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return result
    result = run("from pathlib import Path; Path('allowed.txt').write_text('allowed')", True)
    assert result.returncode == 0, result.stderr
    print('PASS: writable profile can create workspace code')
    for path in [root / 'Goal.md', root / 'outside.txt']:
        result = run(f'from pathlib import Path; Path({str(path)!r}).write_text("forbidden")', True)
        assert result.returncode != 0, f'Unexpected write allowed: {path}'
    assert (root / 'Goal.md').read_text() == 'owner contract'
    assert not (root / 'outside.txt').exists()
    print('PASS: owner contract and sibling paths remain protected')
    result = run("from pathlib import Path; Path('check-write.txt').write_text('forbidden')")
    assert result.returncode != 0
    print('PASS: acceptance profile is read-only')
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'local fixture')
        def log_message(self, *args): pass
    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        assert urllib.request.urlopen(url, timeout=2).read() == b'local fixture'
        for writable in (False, True):
            result = run(f'import urllib.request; urllib.request.urlopen({url!r}, timeout=2).read()', writable)
            assert result.returncode != 0, 'Network unexpectedly allowed'
        print('PASS: both profiles block direct network access (reachable local fixture)')
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
print('4 real sandbox boundary checks passed')
