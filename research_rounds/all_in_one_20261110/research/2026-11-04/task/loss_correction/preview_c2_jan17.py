from pathlib import Path
import sys,pickle,json,hashlib,time
P=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CORE=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-rights-month-resume-v2-20261102')
CP=CORE/'runs/2022-C10/full/2022-01-17-CLOSE.pkl'
sys.path.insert(0,str(CORE));import resume_runtime_v2 as R
sys.path.insert(0,str(OLD/'g-s-C2-step-cap-projection-v1-20261102'));import step_cap as C2
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
    with (P/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=R.E.encode)
def main():
    t=time.perf_counter();before=sha(CP);side=json.loads(CP.with_suffix('.provenance.json').read_text())
    assert before==side['checkpoint_sha256']
    r=pickle.loads(CP.read_bytes())
    assert type(r) is R.ContinuationRunner and r.mode=='C10' and r.window=='2022'
    assert str(r.last_completed_event)=='2022-01-17 15:10:00+08:00'
    cert=r.active;cid=cert['certificate_id'];v=r.trusted[cert['trusted_id']]
    s,ds,e,bb=v['snapshot'],v['demands'],v['evidence'],v['budget_before']
    assert cert['known_at']==s['at']=='2022-01-17T15:10:00+08:00'
    assert cid==R.E.digest({k:z for k,z in cert.items() if k!='certificate_id'})
    assert cert['trusted_id']==R.E.digest(dict(s=s,ds=ds,e=e,bb=bb))
    original=next(z['projection'] for z in r.results if z['certificate']['certificate_id']==cid)
    assert original['Q']==cert['Q'] and original['D']==cert['D']
    source=dict(checkpoint=str(CP),checkpoint_sha256=before,provenance_sha256=sha(CP.with_suffix('.provenance.json')),cursor=str(r.last_completed_event),certificate=cid,trusted_id=cert['trusted_id'],C2_source_sha256=sha(C2.__file__),original_class_module_sha256=sha(R.__file__),financial_events=0,account_restore_calls=0)
    save('C2_JAN17_INPUT.json',dict(snapshot=s,B_demands=ds,industry_evidence=e,budget_before=bb,original_projection=original,certificate=cert,source=source))
    off=C2.C.solve_C(s,ds,e,max_native_checks=250000)
    assert off['Q']==original['Q'] and off['D']==original['D'],'C10 static identity failed'
    save('C2_JAN17_C10_OFF.json',off)
    out=C2.solve_C2(s,ds,e,max_native_checks=250000)
    assert out['financial_events']==0 and out['submit_allowed'] is False
    save('C2_JAN17_C2.json',out)
    save('C2_JAN17_PREVIEW_COMPLETE.json',dict(passed=True,financial_events=0,source=source,full_candidates=len(ds),original_positive_Q=sum(q>0 for q in off['Q'].values()),C2_positive_Q=sum(q>0 for q in out['Q'].values()),original_QD_static_identity=True,seconds=time.perf_counter()-t,checkpoint_source_unchanged=sha(CP)==before,technical_limit=250000))
    print(json.dumps(dict(candidates=len(ds),oldQ={s:q for s,q in off['Q'].items() if q},newQ={s:q for s,q in out['Q'].items() if q},oldD=off['D'],newD=out['D'],seconds=time.perf_counter()-t),default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
