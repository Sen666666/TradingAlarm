"""Display-only narrow-panel correction found by browser visual inspection."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'report/index.html';s=p.read_text()
assert 'id="narrow-panel-fix"' not in s
before=hashlib.sha256(p.read_bytes()).hexdigest()
s=s.replace('</style>','</style><style id="narrow-panel-fix">.toolbar>label{min-width:0;max-width:100%}.toolbar>label:first-child{flex:1 1 380px}.toolbar select{display:block;width:100%;max-width:100%}.toolbar input[type=date]{max-width:100%}.card{min-width:0;overflow-wrap:anywhere}</style>',1)
p.write_text(s)
with (ROOT/'audit/layout-fix.json').open('x') as f:json.dump({'before_sha256':before,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'reason':'Narrow-panel select overflow seen in actual browser screenshot','algorithm_changes':0},f,indent=2)
