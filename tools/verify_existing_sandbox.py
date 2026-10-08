"""Verify attached-project filesystem boundaries using the installed sandbox."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from existing_fixture import make
from context_loop.config import load
from context_loop.transport import profile

codex=shutil.which('codex')
with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as directory:
    root,vault,originals=make(Path(directory),git=True)
    _,config=load(root)
    def run(code, writable=True):
        command=[codex,'sandbox','-P','context-loop','-C',str(root),*profile(root,'context-loop',writable,config),'--',sys.executable,'-B','-c',code]
        return subprocess.run(command,capture_output=True,text=True,timeout=15)
    result=run("from pathlib import Path; Path('src/allowed.py').write_text('allowed')")
    assert result.returncode==0,result.stderr
    print('PASS: explicit source directory supports new code files')
    targets=[root/'AGENTS.md',root/'docs/Build.md',root/'src/AGENTS.md',root/'src/Policy.md',root/'context-loop.json',root/'Context Loop/Approval.json',root/'Context Loop/Progress.md',root/'.context-loop/state.json',root/'.git/HEAD',root/'README.md',vault/'Guidance.md']
    for target in targets:
        before=target.read_bytes()
        result=run(f'from pathlib import Path; Path({str(target)!r}).write_text("forbidden")')
        assert result.returncode!=0,f'Unexpected protected write allowed: {target}'
        assert target.read_bytes()==before,f'Protected content changed: {target}'
    print('PASS: governing docs, nested instructions, control, runtime, Git, unrelated code and external notes protected')
    before=(root/'src/Policy.md').read_bytes()
    result=run("import os; from pathlib import Path; Path('src/replacement.tmp').write_text('forbidden'); os.replace('src/replacement.tmp','src/Policy.md')")
    assert result.returncode!=0,'Atomic replacement bypassed source protection'
    assert (root/'src/Policy.md').read_bytes()==before
    print('PASS: atomic replacement cannot bypass nested-source protection')
    result=run("from pathlib import Path; Path('src/Policy.md').unlink()")
    assert result.returncode!=0,'Unlink bypassed source protection'
    assert (root/'src/Policy.md').read_bytes()==before
    print('PASS: deleting a nested governing source is denied')
    result=run("from pathlib import Path; Path('src/.codex').mkdir()")
    assert result.returncode!=0,'Project configuration directory was writable'
    print('PASS: creation of nested .codex configuration denied')
    result=run(f"from pathlib import Path; Path('src/escape').symlink_to({str(vault/'Guidance.md')!r}); Path('src/escape').write_text('forbidden')")
    assert result.returncode!=0,'Symlink escaped write boundaries'
    print('PASS: symlink cannot escape write boundaries')
    result=run("from pathlib import Path; Path('src/app.py').write_text('forbidden')",False)
    assert result.returncode!=0,'Check profile permitted code writes'
    print('PASS: acceptance checks remain read-only in original layout')
print('7 existing-project sandbox groups passed (17 write probes)')
