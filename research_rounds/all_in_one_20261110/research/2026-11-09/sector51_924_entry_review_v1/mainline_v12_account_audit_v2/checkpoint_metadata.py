"""Checkpoint receipt/opaque bytes only. Deliberately no pickle or engine import."""
from pathlib import Path
import json,hashlib,sys
from compression_integrity import sha
SCHEMA='M12_EXACT_MANIFEST_CERTIFIED_CHECKPOINT_V1'
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in sorted(x.items(),key=lambda p:str(p[0]))}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None or isinstance(x,(str,int,float,bool)):return x
    return str(x)
def digest(v):return hashlib.sha256(json.dumps(clean(v),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def audit(directory,expected_receipt_sha256,candidate_root,certified_end,verify_sources=True):
    root=Path(candidate_root).resolve();directory=Path(directory).resolve()
    assert directory.is_relative_to(root),'checkpoint_outside_exact_candidate'
    assert len(expected_receipt_sha256)==64 and sha(directory/'COMMIT.json')==expected_receipt_sha256,'external_receipt_hash_required'
    r=json.loads((directory/'COMMIT.json').read_text())
    assert r['schema']==SCHEMA and r['status']=='CERTIFIED_COMMITTED'
    assert r['certified_day']<=certified_end and r['history_authorization'] is False and r['continuation_requires_separate_run_approval'] is True
    assert r['state_file']=='STATE.pickle.gz'
    body=(directory/r['state_file']).resolve();assert body.parent==directory
    assert body.stat().st_size==r['state_bytes'] and sha(body)==r['state_sha256'],'opaque_checkpoint_byte_mismatch'
    b=r['binding'];assert b['schema']==SCHEMA and b['binding_id']==digest({k:v for k,v in b.items() if k!='binding_id'})
    assert b['source_migration_allowed'] is False and b['cache_fields']==['meta']
    assert Path(b['source_manifest_path']).resolve()==root/'SOURCE_HASHES.json'
    assert b['python']==list(sys.version_info[:3])
    if verify_sources:
        assert sha(root/'SOURCE_HASHES.json')==b['source_manifest_sha256']
        m=json.loads((root/'SOURCE_HASHES.json').read_text());assert m['files']==b['code_and_evidence_hashes']
        for p,h in {**b['code_and_evidence_hashes'],**b['data_identity']['source_hashes']}.items():assert sha(p)==h,('checkpoint_bound_source_changed',p)
    return dict(verdict='PASS_RECEIPT_BINDING_OPAQUE_STATE_HASH' if verify_sources else 'PASS_SYNTHETIC_METADATA_ONLY',receipt_sha256=expected_receipt_sha256,state_sha256=r['state_sha256'],certified_day=r['certified_day'],binding_id=b['binding_id'],pickle_opened=False,state_restoration_independently_executed=False,not_covered=['Opaque state contents, active/archive/CP aliases, pending ownership and runtime cache restoration require separate source-bound synthetic review.','Receipt integrity never authorizes history or cross-manifest migration.'])
