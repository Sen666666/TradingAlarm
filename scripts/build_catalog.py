#!/usr/bin/env python3
"""Index preserved research without importing or executing experiment modules."""
import ast
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'TradingAlarm/research'

def main():
    groups = {}
    for kind in ('data', 'results'):
        rows = []
        for p in sorted((R / kind).iterdir()):
            files = [f for f in (p.rglob('*') if p.is_dir() else [p]) if f.is_file()]
            rows.append({'path': str(p.relative_to(ROOT)), 'files': len(files),
                         'bytes': sum(f.stat().st_size for f in files),
                         'metadata': [str(f.relative_to(ROOT)) for f in files if f.suffix == '.json' and any(k in f.name for k in ('protocol','review','summary','validation','manifest','coverage','findings'))]})
        groups[kind] = rows
    scripts = []
    absolute = []
    for p in sorted(R.glob('*.py')):
        content = p.read_text()
        try: desc = ast.get_docstring(ast.parse(content))
        except SyntaxError: desc = None
        scripts.append({'path': str(p.relative_to(ROOT)), 'description': desc})
        if '/Users/bytedance/' in content: absolute.append(str(p.relative_to(ROOT)))
    groups.update(scripts=scripts, absolute_path_scripts=absolute,
                  note='Metadata links are an inventory, not a claim that every experiment succeeded or was rerun during handoff.')
    (ROOT / 'docs/catalog.json').write_text(json.dumps(groups, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':main()
