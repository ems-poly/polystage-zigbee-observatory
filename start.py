"""Start the local scanner independently of the Codex/terminal session."""
import subprocess,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent
try:
    urllib.request.urlopen('http://127.0.0.1:8765/api/state',timeout=2)
except Exception:
    with (root/'dashboard.log').open('a') as log:
        child=subprocess.Popen([str(root/'.venv/bin/python'),'-u',str(root/'scanner.py')],cwd=root,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (root/'data/scanner.pid').write_text(str(child.pid))
    print('Scanner started:',child.pid)
print('http://127.0.0.1:8765')
