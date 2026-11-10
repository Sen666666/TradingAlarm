"""Two pure target branches from the audited pre-A-request common views."""
from c_batch20 import *
import shutil,time,traceback

def main():
    guard();assert read(O/'SYNTHETIC_RESULTS.json')['passed']
    if (O/'AUTHORIZATION_AND_FREEZE.json').exists():raise RuntimeError('existing freeze; inspect rather than rerun')
    archives={}
    for root in (CROOT,C.BASE,O.parent/'g-s-C2-step-cap-projection-v1-20261102'):
        ix=read(root/'ARTIFACT_SHA256.json');assert all(sha(root/n)==v for n,v in ix.items());archives[str(root.resolve())]=dict(index_sha256=sha(root/'ARTIFACT_SHA256.json'),files=len(ix))
    common={}
    for k,day in [('2025_26','2025-07-03'),('2022','2022-01-06')]:
        ip=O/'inputs'/(k+'.json');ip.parent.mkdir(exist_ok=True);shutil.copyfile(CROOT/'inputs'/(k+'.json'),ip);x=read(ip)
        ap=O.parent/'g-s-historical-native-nextsession-20261101/run'/k/'close'/(day+'-CLOSE.json');a=read(ap)['account']
        locks=[v for v in a['policy']['locks'].values() if v['remaining']];duties=[a['exit_duties'][v['eid']] for v in locks]
        assert len(locks)==(16 if k=='2025_26' else 9)
        assert all(v['requested_at']==x['snapshot']['at'] and v['reasons']==['actionable_S_funding'] for v in duties)
        assert not x['snapshot']['assets'] and not a['buys']
        common[k]=dict(common_point=x['evidence']['common_point'],source_post_A_checkpoint_json_sha256=sha(ap),
            actual_post_A_uncompleted_orders=len(locks),all_are_same_close_A_funding=True,pre_request_prior_carry=0,
            actual_orders_not_cancelled=True,comparison_branch_not_installable=True)
    freeze=dict(scope='C_BATCH20 synthesis and Jan6/Jul3 static targets only',parent='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',
        contract_sha256=CONTRACT_SHA,original_archives=archives,common_point_proofs=common,
        source_C10_sha256=C_SHA,source_B_sha256=C.BASE_SHA,source_JF2_sha256=C.JOINT_SHA,
        inputs={k:sha(O/'inputs'/(k+'.json')) for k in ('2025_26','2022')},code={p.name:sha(p) for p in sorted(O.glob('*.py'))},
        healthy_opportunity_cap='.20*original decision NAV; aggregate planned raw gross; not per stock',C10_recomputed=False,
        native_callback_installation=False,financial_events=0)
    save(O/'AUTHORIZATION_AND_FREEZE.json',freeze)
    original_functions=(C.B.evaluate,C.B.necessary_upper)
    for k in ('2025_26','2022'):
        x=read(O/'inputs'/(k+'.json'));out=O/'results'/k;start=time.monotonic();history=[]
        try:
            def progress(row):
                history.append(row);save(out/'PROGRESS.json',dict(completed=history,seconds=time.monotonic()-start,financial_events=0))
                if row['q'] or len(history)%15==0:print('C20_STEP',k,len(history),row['sid'],row['q'],len(row.get('D',{})),round(time.monotonic()-start,2),flush=True)
                if time.monotonic()-start>180:raise RuntimeError('static technical budget exceeded; no approximate output')
            r=solve_C20(x['snapshot'],x['B_demands'],x['industry_evidence'],progress=progress)
            assert (C.B.evaluate,C.B.necessary_upper)==original_functions,'original module globals changed'
            save(out/'C20.json',r);save(out/'RUN.json',dict(seconds=time.monotonic()-start,completed=True,original_module_globals_unchanged=True,financial_events=0))
            print('C20_COMPLETE',k,sum(bool(q) for q in r['Q'].values()),len(r['D']),round(time.monotonic()-start,2),flush=True)
        except BaseException as exc:
            save(out/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),completed_candidate_prefix=history,financial_events=0));raise

if __name__=='__main__':main()
