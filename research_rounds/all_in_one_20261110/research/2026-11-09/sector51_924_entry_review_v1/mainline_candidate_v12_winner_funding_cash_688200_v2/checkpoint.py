"""Trusted local, exact-manifest certified-state storage. No loop or migration API.

Only load receipts whose SHA came from the caller's separately trusted run log.
Pickle is never an exchange format; untrusted/arbitrary checkpoints are unsupported.
"""
from pathlib import Path
import gzip
import hashlib
import inspect
import json
import os
import pickle
import shutil
import sys
O=Path(__file__).resolve().parent
SCHEMA='M12_EXACT_MANIFEST_CERTIFIED_CHECKPOINT_V1'
MANIFEST=O/'SOURCE_HASHES.json'
CACHE_FIELDS=('meta',)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in sorted(v.items(),key=lambda p:str(p[0]))}
    if isinstance(v,(tuple,list)):return [clean(x) for x in v]
    if v is None or isinstance(v,(str,int,float,bool)):return v
    return str(v)


def digest(v):return hashlib.sha256(json.dumps(clean(v),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def data_identity(data):
    return dict(class_name=type(data).__qualname__,fields=sorted(vars(data)),end=str(data.end),
                days=[str(d) for d in data.days],calendar=[str(d) for d in data.cal],
                ids=list(data.ids),events_digest=digest(data.events),admission_digest=digest(data.admission),
                source_hashes=dict(data.hashes))


def verify_files(hashes):
    for p,h in hashes.items():assert sha(p)==h,('CHECKPOINT_SOURCE_DRIFT',p)


def make_binding(data):
    manifest=json.loads(MANIFEST.read_text());files=manifest['files']
    for p in (O/'engine.py',O/'stream_output.py',Path(__file__).resolve(),O/'ADMISSION_LOCK.json',O/'CONTRACT.md'):
        assert str(p) in files,('CHECKPOINT_CODE_NOT_SEALED',str(p))
    verify_files(files);verify_files(data.hashes)
    binding=dict(schema=SCHEMA,source_manifest_path=str(MANIFEST),source_manifest_sha256=sha(MANIFEST),
                 code_and_evidence_hashes=files,data_identity=data_identity(data),
                 python=list(sys.version_info[:3]),cache_fields=list(CACHE_FIELDS),source_migration_allowed=False)
    binding['binding_id']=digest(binding)
    return binding


def validate_binding(data,binding,verify_sources):
    payload={k:v for k,v in binding.items() if k!='binding_id'}
    assert binding['binding_id']==digest(payload) and binding['schema']==SCHEMA,'CHECKPOINT_BINDING_TAMPER'
    assert binding['source_migration_allowed'] is False and binding['cache_fields']==list(CACHE_FIELDS)
    assert binding['source_manifest_path']==str(MANIFEST) and sha(MANIFEST)==binding['source_manifest_sha256'],'CHECKPOINT_CODE_MANIFEST_CHANGED'
    assert binding['python']==list(sys.version_info[:3]),'CHECKPOINT_PYTHON_CHANGED'
    assert binding['data_identity']==data_identity(data),'CHECKPOINT_DATA_MANIFEST_CHANGED'
    if verify_sources:
        verify_files(binding['code_and_evidence_hashes']);verify_files(data.hashes)


def assert_certified(engine,day):
    assert engine.ledger and engine.ledger[-1]['day']==str(day),'CHECKPOINT_NOT_LAST_CERTIFIED_DAY'
    assert not engine.blockers and not getattr(engine,'uncertified_day',None),'CHECKPOINT_FAILED_DAY_FORBIDDEN'
    assert all(engine.archive[a['id']] is a for a in engine.active.values()),'CHECKPOINT_ALIAS_BROKEN'


def save_checkpoint(engine,pending,prev,path,binding):
    """Call only after atomic_step returned successfully; prev is that certified day.

    make_binding verifies all sources once at start. Each save rechecks manifest,
    Data identity and code hashes; frozen runtime never mutates source Data fields.
    Caller must retain the returned receipt SHA outside the checkpoint directory.
    """
    validate_binding(engine.d,binding,verify_sources=False)
    for p,h in binding['code_and_evidence_hashes'].items():
        if Path(p).suffix=='.py':assert sha(p)==h,('CHECKPOINT_CODE_DRIFT',p)
    day=str(prev.date()) if hasattr(prev,'date') else str(prev)
    assert_certified(engine,day)
    assert Path(inspect.getfile(type(engine))).resolve()==O/'engine.py','CHECKPOINT_WRONG_ENGINE_CLASS'
    path=Path(path).resolve();assert path.is_relative_to(O),'CHECKPOINT_LOCAL_CANDIDATE_ONLY'
    assert shutil.disk_usage(O).free>8*1024**3,'CHECKPOINT_DISK_RESERVE'
    path.mkdir(parents=True,exist_ok=False)
    # One pickle graph preserves engine/pending/cache and active/archive aliases.
    bundle=dict(schema=SCHEMA,binding_id=binding['binding_id'],certified_day=day,prev=prev,
                engine_state={k:v for k,v in vars(engine).items() if k!='d'},pending=pending,
                data_cache={k:getattr(engine.d,k) for k in CACHE_FIELDS},engine_class=type(engine).__qualname__)
    body=path/'STATE.pickle.gz'
    with body.open('xb') as output:
        with gzip.GzipFile(filename='',fileobj=output,mode='wb',mtime=0,compresslevel=6) as gz:
            pickle.dump(bundle,gz,protocol=5)
        output.flush();os.fsync(output.fileno())
    receipt=dict(schema=SCHEMA,status='CERTIFIED_COMMITTED',certified_day=day,binding=binding,
                 state_file=body.name,state_sha256=sha(body),state_bytes=body.stat().st_size,
                 engine_class=type(engine).__qualname__,history_authorization=False,
                 continuation_requires_separate_run_approval=True)
    temporary=path/'COMMIT.json.pending'
    with temporary.open('x') as output:
        json.dump(receipt,output,ensure_ascii=False,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
    os.replace(temporary,path/'COMMIT.json')
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),receipt_sha256=sha(path/'COMMIT.json'),state_sha256=receipt['state_sha256'],certified_day=day,binding_id=binding['binding_id'])


def load_checkpoint(path,expected_receipt_sha256,data,engine_class,binding):
    """Verify same code/data and authenticated local bytes BEFORE unpickling.

    Caller supplies freshly initialized same-manifest Data. This does not advance
    any day, select a branch, waive preflight, or authorize an experimental run.
    """
    path=Path(path).resolve();assert path.is_relative_to(O),'CHECKPOINT_LOCAL_CANDIDATE_ONLY'
    assert isinstance(expected_receipt_sha256,str) and len(expected_receipt_sha256)==64
    assert sha(path/'COMMIT.json')==expected_receipt_sha256,'CHECKPOINT_UNTRUSTED_RECEIPT'
    receipt=json.loads((path/'COMMIT.json').read_text())
    assert receipt['schema']==SCHEMA and receipt['status']=='CERTIFIED_COMMITTED'
    assert receipt['binding']==binding,'CHECKPOINT_CROSS_MANIFEST_FORBIDDEN'
    validate_binding(data,binding,verify_sources=True)
    assert Path(inspect.getfile(engine_class)).resolve()==O/'engine.py' and engine_class.__qualname__==receipt['engine_class'],'CHECKPOINT_CROSS_ENGINE_FORBIDDEN'
    assert receipt['state_file']=='STATE.pickle.gz'
    body=path/receipt['state_file'];assert body.stat().st_size==receipt['state_bytes'] and sha(body)==receipt['state_sha256'],'CHECKPOINT_STATE_TAMPER'
    with gzip.open(body,'rb') as stream:
        bundle=pickle.load(stream);assert stream.read(1)==b'','CHECKPOINT_TRAILING_DATA'
    assert bundle['schema']==SCHEMA and bundle['binding_id']==binding['binding_id'] and bundle['certified_day']==receipt['certified_day']
    assert bundle['engine_class']==receipt['engine_class'] and set(bundle['data_cache'])==set(CACHE_FIELDS)
    assert 'd' not in bundle['engine_state']
    engine=object.__new__(engine_class);vars(engine).update(bundle['engine_state']);engine.d=data
    for k,v in bundle['data_cache'].items():setattr(data,k,v)
    assert_certified(engine,bundle['certified_day'])
    return engine,bundle['pending'],bundle['prev']


def save_latest(engine,pending,prev,cache,binding,receipt_log):
    """Bounded research cache: keep old certified bytes until new commit verifies.

    Normal storage is one complete state, transiently two. Only the previous
    state in THIS cache is removed after pointer commit. Never touches v1 outputs.
    Returned receipt SHA belongs in the external append-only run log.
    """
    cache=Path(cache).resolve();assert cache.is_relative_to(O),'CHECKPOINT_CACHE_SCOPE'
    cache.mkdir(parents=True,exist_ok=True)
    pointer=cache/'LATEST.json';old=None
    if pointer.exists():
        old=json.loads(pointer.read_text())
        assert old['state_directory'].startswith('state_') and '/' not in old['state_directory']
        prior=cache/old['state_directory']
        assert prior.resolve().parent==cache and sha(prior/'COMMIT.json')==old['receipt_sha256'],'LATEST_POINTER_INVALID'
    # Fail closed on leftovers rather than silently accumulate or remove unknown files.
    allowed={'LATEST.json',old['state_directory']} if old else set()
    assert {p.name for p in cache.iterdir()}<=allowed,'CHECKPOINT_CACHE_UNCOMMITTED_LEFTOVERS'
    stamp=str(prev.date()) if hasattr(prev,'date') else str(prev)
    name='state_'+stamp.replace('-','');assert not (cache/name).exists(),'CHECKPOINT_DAY_ALREADY_STORED'
    receipt=save_checkpoint(engine,pending,prev,cache/name,binding)
    assert sha(cache/name/'COMMIT.json')==receipt['receipt_sha256']
    assert sha(cache/name/'STATE.pickle.gz')==receipt['state_sha256']
    value=dict(receipt,state_directory=name,latest_only=True,previous_state_removed_after_verified_commit=True)
    receipt_log=Path(receipt_log).resolve()
    assert receipt_log.is_relative_to(O) and not receipt_log.is_relative_to(cache) and receipt_log.name=='CHECKPOINT_RECEIPTS.jsonl','CHECKPOINT_EXTERNAL_RECEIPT_LOG_SCOPE'
    # Trust anchor must be durable BEFORE publishing latest or removing old bytes.
    append_receipt(receipt_log,value)
    temporary=cache/'LATEST.json.pending'
    with temporary.open('x') as output:
        json.dump(value,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
    os.replace(temporary,pointer)
    fd=os.open(cache,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    if old:shutil.rmtree(cache/old['state_directory'])
    value['latest_pointer_sha256']=sha(pointer)
    return value


def append_receipt(path,receipt):
    with Path(path).open('a') as output:
        output.write(json.dumps(receipt,ensure_ascii=False)+'\n');output.flush();os.fsync(output.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
