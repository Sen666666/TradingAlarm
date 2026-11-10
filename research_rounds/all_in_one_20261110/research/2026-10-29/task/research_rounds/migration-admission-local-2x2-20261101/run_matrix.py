"""Only two audited opening projections x two allocator/admission policies.
No market loader, indicators, Account, fills or financial path is used here.
"""
from pathlib import Path
import copy,json,hashlib,time,collections,traceback
from decimal import Decimal as D
import variant as V
B=V.B;O=V.O;OLD=V.OLD;Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):
    p=O/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(B.serial(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def unchanged_old():
    a=read(OLD/'ARTIFACT_SHA256.json');assert all(sha(OLD/p)==h for p,h in a.items());return a
def resources(r,pool=None):
    s=r['final_state'];lots=[x for x in s['lots'] if pool is None or x['pool']==pool];orders=[x for x in s['orders'].values() if x['qty']>0 and x['status'] in ['open','cancel_pending'] and (pool is None or x['pool']==pool)]
    return dict(capital=sum(x['qty']*s['prices'][x['stock']] for x in lots)+sum(x['qty']*x['limit'] for x in orders),risk=sum(x['qty']*max(0.,s['prices'][x['stock']]-x['floor']) for x in lots)+sum(x['qty']*max(0.,x['limit']-x['floor']) for x in orders),reserve=sum(x['qty']*(x['limit']+x['fee_per_share']) for x in orders))
def contrast(a,b,s0):
    am={x['sid']:x for x in a['orders']};bm={x['sid']:x for x in b['orders']};held={x['stock'] for x in s0['lots'] if x['qty']>0};changes=[]
    for sid in sorted(set(am)|set(bm)):
        x=am.get(sid);y=bm.get(sid)
        if x is None or y is None or any(x[k]!=y[k] for k in ['role','pool','quantity']):
            changes.append(dict(sid=sid,before=x,after=y,role_change=x is not None and y is not None and x['role']!=y['role'],pool_change=x is not None and y is not None and x['pool']!=y['pool'],quantity_delta=(y['quantity'] if y else 0)-(x['quantity'] if x else 0)))
    return dict(gained_order_stocks=sorted(set(bm)-set(am)),lost_order_stocks=sorted(set(am)-set(bm)),gained_planned_flat_footholds=sorted((set(bm)-set(am))-held),lost_planned_flat_footholds=sorted((set(am)-set(bm))-held),changes=changes,
        capital_delta=b['capital']-a['capital'],risk_delta=b['nominal_risk']-a['nominal_risk'],cash_reserve_delta=b['cash_reserve']-a['cash_reserve'],available_delta=D(b['available'])-D(a['available']),fee_delta=D(b['fees'])-D(a['fees']),not_PnL=True)
def summary(r,view):
    oks={x['key'] for x in r['orders']};exceptions=[]
    for e in r['migrations']:
        if e['phase']=='request' and e['candidate'] in oks and not e['result']:
            order=next(x for x in r['orders'] if x['key']==e['candidate'])
            if order['pool']=='confirmed':exceptions.append(dict(order=order,migration=e))
    for oid,old in view['state']['orders'].items():assert r['final_state']['orders'][oid]==old,'existing pending changed'
    return dict(orders=len(r['orders']),distinct_stocks=len({x['sid'] for x in r['orders']}),role_pool=dict(collections.Counter(x['role']+'|'+x['pool'] for x in r['orders'])),
        capital=r['capital'],nominal_risk=r['nominal_risk'],cash_reserve=r['cash_reserve'],available=r['available'],fees=r['fees'],pool_resources={p:resources(r,p) for p in ['probe','confirmed']},
        migration_calls=len(r['migrations']),failed_migration_reasons=dict(collections.Counter(e['diagnostic']['primary_reason'] for e in r['migrations'] if not e['result'])),
        migration_calls_without_final_order=sum(e['candidate'] not in oks for e in r['migrations']),
        new_confirmed_despite_failed_migration=len(exceptions),new_confirmed_failed_migration_details=exceptions,
        old_pending_count=len(view['state']['orders']),old_pending_unchanged=True,
        rejection_counts=dict(collections.Counter(x['reason'] for x in r['rejected'])),named_stock={sid:dict(order=next((x for x in r['orders'] if x['sid']==sid),None),rejections=[x for x in r['rejected'] if x['sid']==sid]) for sid in ['300308.SZ','300502.SZ']})

def main():
    assert read(O/'TEST_RESULTS.json')['passed'];old=unchanged_old();begun=time.monotonic()
    inputs={d:read(OLD/(d+'_INPUT_VIEW.json')) for d in ['2023-01-20','2022-06-29']}
    freeze=dict(policy='new migration/admission decoupling variant, not historical bugfix',scope='2 fixed audited allocation projections, no historical account progression',sha256={**V.source_hashes(),str(Path(__file__).resolve()):sha(__file__),str(O/'test_variant.py'):sha(O/'test_variant.py'),**{str((OLD/(d+'_INPUT_VIEW.json')).resolve()):sha(OLD/(d+'_INPUT_VIEW.json')) for d in inputs}},old_artifact_manifest_sha=sha(OLD/'ARTIFACT_SHA256.json'),old_artifacts_verified=len(old),account_risk='Bdiag original omission preserved; no3% gate added',no_C1_R1_or_new_stage=True)
    save('FREEZE.json',freeze);allout={};proofs=[]
    cells=[('SC',False,'single_pass'),('TC',False,'two_pass'),('SD',True,'single_pass'),('TD',True,'two_pass')]
    for day,view in inputs.items():
        at=B.J.M.N.iso(day+'T09:30:00+08:00');results={};summaries={}
        for label,decoupled,mode in cells:
            s,intents=V.decode(view,decoupled);expected=read(OLD/(day+('_BASELINE_IDENTITY.json' if mode=='single_pass' else '_TWO_PASS.json')));expected=expected['baseline'] if mode=='single_pass' else expected
            before=B.digest([s.view(),[B.intent_view(i) for i in intents]]);assert before==expected['input_before_sha256'],'projection decoder drift'
            t=time.monotonic();r=V.plan(s,intents,at,mode);seconds=time.monotonic()-t
            assert before==B.digest([s.view(),[B.intent_view(i) for i in intents]])
            if not decoupled:
                assert B.digest(V.old_observable(r))==B.digest(expected),(day,label,'old cell drift')
                proofs.append(dict(day=day,cell=label,passed=True,all_prior_fields_exact=True,excluded_only_new_logging_fields=['first_pass_migrations','diagnostic in migrations and final_state.migrations'],old_result_SHA=B.digest(expected),current_old_fields_SHA=B.digest(V.old_observable(r))))
            save(day+'_'+label+'.json',dict(cell=label,decoupled=decoupled,allocator=mode,seconds=seconds,result=r))
            results[label]=r;summaries[label]=dict(seconds=seconds,**summary(r,view))
        pairs={'gate_effect_given_singlepass':('SC','SD'),'gate_effect_given_twopass':('TC','TD'),'allocator_effect_given_coupling':('SC','TC'),'allocator_effect_given_decoupling':('SD','TD')}
        contrasts={name:contrast(results[a],results[b],view['state']) for name,(a,b) in pairs.items()}
        if day=='2022-06-29':assert all(not r['orders'] for r in results.values())
        allout[day]=dict(cells=summaries,contrasts=contrasts,input_view_sha=sha(OLD/(day+'_INPUT_VIEW.json')),projection_limit='audited allocation-read-set projection only, not complete runner restoration; same explicit unused prior status unknown',existing_pending_at_S0=len(view['state']['orders']))
        save(day+'_SUMMARY.json',allout[day]);print('LOCAL_2X2_DAY',day,{k:v['orders'] for k,v in summaries.items()},flush=True)
    assert unchanged_old()==old;assert all(sha(p)==h for p,h in freeze['sha256'].items())
    save('OLD_CELL_IDENTITY.json',dict(passed=True,cells=proofs,original_artifacts_unchanged=len(old)))
    save('MATRIX_SUMMARY.json',dict(passed=True,seconds=time.monotonic()-begun,cell_definitions={'SC':'single-pass coupled','TC':'two-pass coupled','SD':'single-pass decoupled new policy','TD':'two-pass decoupled new policy'},days=allout,new_financial_paths=0,native_Account_initializations=0,real_submissions=0,real_fills=0,no_after_open_account_progression=True,no_future_returns_read=True))
    print('LOCAL_2X2_COMPLETE',round(time.monotonic()-begun,3),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:save('FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),no_financial_paths=True));raise
