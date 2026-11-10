from pathlib import Path
import sys,json,time,traceback,hashlib
import engine_known_halt_v1 as E
import test_known_halt_v1 as T
from halt_evidence_v1 import HaltEvidence
HERE=Path(__file__).resolve().parent
out=HERE/sys.argv[1];out.mkdir(exist_ok=False)
def save(name,v):(out/name).write_text(json.dumps(v,default=str,ensure_ascii=False,indent=2)+'\n')
def clean(v):
    if hasattr(v,'to_dict'):return clean(v.to_dict())
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if hasattr(v,'item'):v=v.item()
    if isinstance(v,float) and not __import__('math').isfinite(v):return None
    if isinstance(v,E.D):return str(v)
    return v
start=time.monotonic()
try:
    s=E.bridge.load_original('2022')
    legacy=T.old.test_suite(s);save('LEGACY_SYNTHETIC.json',legacy)
    cases=T.suite(s);save('HALT_SYNTHETIC.json',cases)
    del s
    # Frozen bounded prefix only, never a complete cohort run.
    s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,halt_evidence=HaltEvidence.load(HERE/'HALT_EVIDENCE_V1.json'))
    days=s.cal[(s.cal>=s.pd.Timestamp('2022-01-04'))&(s.cal<=s.pd.Timestamp('2022-01-17'))];daily=[]
    for n,d in enumerate(days):
        op=b.open_phase(d)['reconciliation'] if n else None;cl=b.close_phase(d)
        daily.append(dict(day=d,OPEN=op,CLOSE=cl,stock_state=__import__('copy').deepcopy(b.states.get('600595.SH'))))
    sid='600595.SH';s.load(sid);j12=s.pd.Timestamp('2022-01-12');j13=s.pd.Timestamp('2022-01-13');j14=s.pd.Timestamp('2022-01-14')
    assert not s.raw[sid].get(j13,{}) and s.raw[sid].get(j12,{})['raw_close']==4.85 and s.raw[sid].get(j14,{})['raw_open']==4.63
    x13=next(x for x in daily if x['day']==j13);x14=next(x for x in daily if x['day']==j14)
    assert x13['stock_state']['state']==E.HALT and x13['OPEN']['NAV'] is None and x13['CLOSE']['NAV'] is None
    assert x14['OPEN']['NAV'] is None and x14['CLOSE']['certified']
    assert not any(a['day'] in ('2022-01-13','2022-01-14') and a['side'].startswith('buy') for a in s.actions)
    assert not any(a['type']=='PROMOTED' and str(a['day'].date()) in ('2022-01-13','2022-01-14') for a in b.audit)
    old=json.loads((HERE.parent/'indexed_execution_v1/cohort_2022/ACTIONS.json').read_text())
    prefix=lambda a:[r for r in a if r['day']<'2022-01-13']
    assert prefix(old)==prefix(s.actions)
    save('BOUNDED_DAYS.json',daily);save('BOUNDED_ACTIONS.json',s.actions);save('BOUNDED_AUDIT.json',b.audit);save('BOUNDED_ARCHIVES.json',s.archives)
    save('FIXED_SOURCE_FACTS.json',clean(dict(sid=sid,Jan12=s.raw[sid].get(j12,{}),Jan13=s.raw[sid].get(j13,{}),Jan14=s.raw[sid].get(j14,{}),I_Jan14=s.facts[sid].get(j14,{}),CP_Jan14=s.cp[sid].get(j14,{}),stock_actions=[x for x in s.actions if x['sid']==sid],source_hashes={**s.hashes,**b.source_hashes})))
    import report_known_halt_v1
    reports=report_known_halt_v1.reports(b,days[-1]);save('BOUNDED_REPORTS.json',reports)
    save('EXECUTED_CODE_HASHES.json',{str(p):E.bridge.sha(p) for p in HERE.glob('*.py')})
    for p,h in dict(s.hashes,**b.source_hashes).items():assert E.bridge.sha(p)==h
    save('RESULT.json',dict(status='AUTHOR_PASS_BOUNDED_ONLY_INDEPENDENT_REVIEW_PENDING',synthetic=len(cases),legacy_groups=len(legacy),fixed_start=str(days[0]),fixed_end=str(days[-1]),seconds=time.monotonic()-start,no_full_cohort_run=True))
except BaseException:
    save('FAILURE.json',dict(error=traceback.format_exc(),seconds=time.monotonic()-start));raise
finally:save('OUTPUT_SEAL.json',{p.name:E.bridge.sha(p) for p in out.iterdir() if p.is_file()})
