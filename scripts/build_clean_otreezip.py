#!/usr/bin/env python3
from pathlib import Path
import tarfile
import sys

def build_clean_zip(root: Path, out_name: str = 'otree.otreezip'):
    out = root / out_name
    exclude_dirs = {'env', '__pycache__', '.git', '.idea', '.vscode', 'screenshots', 'tmp_capture'}
    exclude_names = {'db.sqlite3', 'Thumbs.db', 'otree.otreezip', 'oTree_no_env.zip'}
    exclude_suffixes = {'.pyc', '.pyo', '.zip'}

    if out.exists():
        out.unlink()

    with tarfile.open(out, 'w:gz') as tf:
        for p in sorted(root.rglob('*')):
            if p.is_dir():
                continue
            rel = p.relative_to(root)
            if any(part in exclude_dirs for part in rel.parts):
                continue
            if rel.name in exclude_names:
                continue
            if rel.name.startswith('~$'):
                continue
            if rel.suffix.lower() in exclude_suffixes:
                continue
            tf.add(p, arcname=str(rel).replace('\\', '/'))

    print(f'Created: {out}')
    print(f'Size MB: {out.stat().st_size/1024/1024:.2f}')

    # quick verification
    check = 'ME/LinkToProlific.html'
    with tarfile.open(out, 'r:gz') as tf:
        names = tf.getnames()
    print(( 'OK: ' if check in names else 'MISSING: ') + check)


if __name__ == '__main__':
    root = Path('.')
    build_clean_zip(root)
