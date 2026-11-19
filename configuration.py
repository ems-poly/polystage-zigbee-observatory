"""Local-only configuration; generated identifiers are unrelated to hardware MACs."""
import json,secrets
from pathlib import Path


def ensure_auth(root):
    path=Path(root)/'data/portable-auth.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():return json.loads(path.read_text())
    auth={'device_id':secrets.token_hex(8),'token':secrets.token_urlsafe(32),'dashboard_code':secrets.token_hex(4)}
    path.write_text(json.dumps(auth));path.chmod(0o600)
    return auth
