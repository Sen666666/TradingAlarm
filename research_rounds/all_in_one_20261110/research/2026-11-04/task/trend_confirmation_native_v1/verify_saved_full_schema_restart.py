"""Read saved JSON evidence only; no native imports or account execution."""
from pathlib import Path
import gzip, hashlib, json

O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
direct=O/'full-schema-direct9-v1'
head=O/'full-schema-head4-v2'
resume=O/'full-schema-resume9-v2'
assert read(resume/'PROCESS_EXIT.json')['success'] is True
assert read(resume/'WINDOW_RESULT.json')['source_post_exact'] is True
assert read(head/'PROCESS_IDENTITY.json')['pid']!=read(resume/'PROCESS_IDENTITY.json')['pid']
files=[]
for p in sorted((direct/'pair').glob('*.gz')):
    q=resume/'pair'/p.name
    a=gzip.decompress(p.read_bytes());b=gzip.decompress(q.read_bytes())
    assert a==b,p.name
    files.append(dict(name=p.name,decompressed_SHA256=hashlib.sha256(a).hexdigest(),exact=True))
assert len(files)==12
cache=read(resume/'DERIVED_CACHE_RESTART.json')
assert cache['fixed_end']=='2024-12-31' and cache['available_through']=='2022-01-14'
assert cache['derived_cache_empty'] is True and cache['original_history_rebuild_not_restart_seed'] is True
assert read(resume/'STARTED.json')['full_schema']==read(head/'STARTED.json')['full_schema']
record=dict(passed=True,scope='producer saved-result technical comparison; independent review remains separate',
    direct9_reused_under_restore_only_source_equivalence=True,financial_and_used_flags_plans_exact=files,
    head_pid=read(head/'PROCESS_IDENTITY.json')['pid'],resume_pid=read(resume/'PROCESS_IDENTITY.json')['pid'],
    head_checkpoint_SHA256=sha(head/'checkpoint.pkl'),derived_cache_contract=cache,
    real_accounts_executed_only_through='2022-01-14',full_economic_accounts_executed=0)
p=O/'FULL_SCHEMA_RESTART_PRODUCER_EXACT.json';assert not p.exists()
p.write_text(json.dumps(record,indent=2)+'\n')
print(p,sha(p))
