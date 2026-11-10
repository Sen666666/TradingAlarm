"""Freeze two saved complete OPEN inputs; no native imports or route execution."""
from pathlib import Path
from collections import Counter
import hashlib,json,shutil,time
O=Path(__file__).resolve().parent;ROOT=O.parent.parent
OLD=ROOT/'reentry_v1/funding_agent/private_projection'
DATES=('2026-02-11','2026-06-30');SHA={};start=time.monotonic()
def read(p):
    p=Path(p);SHA[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
s0=read(ROOT/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json')
identity=read(OLD/'OFF_IDENTITY.json');assert identity['passed']
review=read(ROOT/'reentry_v1/review/PRIVATE_OFF_13OPEN_IDENTITY_AUDIT.json');assert review['status']=='PASS_ON_PRIVATE_PROJECTION_ONLY'
checked={c['opening']:c for c in identity['checks']};batches=[];cache={}
for day in DATES:
    assert time.monotonic()-start<20
    pp=OLD/('PREVIEWS_'+day+'.json');xs=read(pp);expected_path=OLD/('OFF_'+day+'.json');expected=read(expected_path)
    assert len(xs)==checked[day]['intents'] and len(expected['orders'])==checked[day]['orders']
    exact=s0[next(k for k in s0 if k[:10]==day)]
    save('S0_'+day+'.json',exact)
    shutil.copyfile(pp,O/pp.name);shutil.copyfile(expected_path,O/('EXPECTED_OFF_'+day+'.json'))
    signal=xs[0]['clock']['session_date'];assert all(x['clock']['session_date']==signal and x['clock']['earliest_execution_at'][:10]==day for x in xs)
    mobiles={x['sid']:x for x in xs if x['role']=='mobile'};proofs={}
    for x in xs:
        if x['role']!='core':continue
        sid=x['sid'];m=mobiles.get(sid);trace=m.get('CP1_trace')if m else None;source='same_day_original_MOBILE_intent_trace'
        if trace is None:
            source=sm[sid]['refs']['receipts']
            if sid not in cache:
                zz=read(source);assert SHA[source]==sm[sid]['output_sha256'][source]
                cache[sid]={r['confirmed_day']:r for r in zz}
            trace=cache[sid].get(signal)
        if trace:
            assert trace['canonical_series']==sid and trace['confirmed_day']==signal and trace['formation_end_inclusive']==signal
            assert not trace['trace_unknown'] and int(trace['source_segment'])==x['epoch'][0]
        proofs[sid]=dict(trace=trace,source=source,same_day_MOBILE_intent_present=m is not None,signal_day=signal,
            eligibility_source='all original CORE intents, independent of original funding/Mobile fill outcome')
    save('CORE_CP_LOOKUP_'+day+'.json',proofs)
    batches.append(dict(OPEN=day,signal_day=signal,intents=len(xs),roles=dict(Counter(x['role']for x in xs)),
        CORE_same_day_CP=sum(z['trace']is not None for z in proofs.values()),CORE_no_same_day_CP=sum(z['trace']is None for z in proofs.values()),
        original_OFF_orders=len(expected['orders']),original_OFF_attempts=len(expected['attempts']),
        original_reviewed_input_sha256=checked[day]['source_input_sha256'],
        native_S0_keys=sorted(exact['state']),preview_schema_keys=sorted(xs[0]),expected_OFF_keys=sorted(expected)))
assert time.monotonic()-start<20
SHA[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();SHA[str(O/'PROTOCOL.txt')]=hashlib.sha256((O/'PROTOCOL.txt').read_bytes()).hexdigest()
save('INPUT_SOURCE_SHA256.json',SHA)
save('PREPARATION.json',dict(passed=True,seconds=time.monotonic()-start,preparation_limit_seconds=20,dates=list(DATES),batches=batches,
    original_PREVIEWS_byte_identical=True,route_executed=False,Runner_constructed=False,Account_constructed=False,new_marks=0,new_facts_reads=0,awaiting_reviewed_adapter_admission=True,OFF_ON_compute_limit_seconds=60))
manifest={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(O.iterdir())if p.is_file()and p.name!='INPUT_FREEZE.json'}
save('INPUT_FREEZE.json',manifest)
print(json.dumps(dict(seconds=time.monotonic()-start,batches=batches,route_executed=False),ensure_ascii=False,indent=2))
