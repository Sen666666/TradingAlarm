"""One bounded three-fixture pure feature assembly. No runner/account imports."""
from pathlib import Path
import sys,json,hashlib,time,traceback,importlib.util,ast
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;O=HERE/'volume_feature_fixtures_v1'
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
END='2026-06-30';CUTS=['2021-12-31','2024-09-23','2026-06-30']
START=None;STAGE='not_started';DEADLINE=None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def budget(stage):
    global STAGE
    STAGE=stage
    assert time.monotonic()<DEADLINE,('180second_budget_exhausted_before',stage)
def module(name,p):
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
def parity(a,b,label):
    try:pd.testing.assert_frame_equal(a,b,check_exact=True,check_dtype=False,check_freq=False,check_names=False)
    except BaseException as exc:
        info=dict(label=label,left_shape=a.shape,right_shape=b.shape,error=str(exc))
        save(O/'PARITY_FAILURE_DETAIL.json',info)
        raise AssertionError(info) from exc
def score_function():
    p=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';tree=ast.parse(p.read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='score')
    env=dict(pd=pd,np=np);exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),env);return env['score']
def assemble(signal,stock,neutral):
    # Original price eligibility, including F2 industry's three invalid source bars.
    f=eligible_prices(signal)[['open','high','low','close','volume','segment_id']].copy()
    f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
    e,_=evidence.build_evidence(f)
    if neutral:
        # Keep original masks/three clocks/ready; replace only original event facts.
        # Do not consume numeric's old target/floor: original B5 e0_policy owns them.
        for _,g in f.groupby('segment_id',sort=False):
            bars=g.loc[g.valid_price_observation,['open','high','low','close','volume']]
            ev=NUM.event_frame_numeric(bars.close,bars.volume,joint=False,event_exit=False)
            assert ev.leg_direction.notna().equals(e.loc[ev.index,'leg_direction'].notna())
            for c in evidence.EVENT_COLUMNS:e.loc[ev.index,c]=ev[c]
        sf,_=B4.strength_frame(f,joint=False)
        for c in sf:e['strength_'+c]=sf[c]
    g=grade.classify(e)[0] if stock else None
    e['decline_candidate']=False
    base,_=policy.e0_policy(e);assert not base.pending.fillna(0).any()
    facts=f[['close','segment_id']].copy();facts['e0_target']=base.target;facts['e0_floor']=base.floor
    if stock:
        ii=policies.project(e,base,g,'G1_I')
        facts['i_target']=ii.target;facts['i_floor']=ii.floor;facts['i_buy']=ii.buy_event
        for col in ['grade','fresh_up','acute_down','ready']:facts['g_'+col]=g[col]
    facts['e0_ready']=base.ready;facts['factor']=signal.adjustment_factor.reindex(facts.index);facts['raw_close']=signal.raw_close.reindex(facts.index)
    if stock:q=facts[['close','segment_id','i_target','i_floor']].copy()
    else:q=facts[['close','segment_id']].copy()
    q['amount']=signal.amount.reindex(q.index);q['e0_down']=e.event.eq(-1);q['e0_valid']=facts['i_target' if stock else 'e0_target'].astype(bool)
    if not stock:q['i_floor']=facts.e0_floor
    cp=CP.calculate(q,price_only=neutral)
    if neutral:cp['effective_amount_multiplier']=1.0  # cp.m remains an unused observed diagnostic.
    ps=signal.copy()
    if neutral:
        # Pure-function D normalization makes b=0/m=1; invalid original D remains invalid.
        # Original observed signal/volume/amount are not mutated or re-exported as fake raw data.
        good=ps.amount.gt(0)&np.isfinite(ps.amount);ps.loc[good,'amount']=1.0
    pvr=SCORE(ps)
    observable=e[['event','confirmation','leg_direction','confirmed_pivot_price','ready','strength_q','strength_qeff','strength_S21','strength_S63','strength_acute_up','strength_acute_down']].copy()
    if neutral:
        ready=observable.strength_q.notna();np.testing.assert_equal(observable.loc[ready,'strength_qeff'],observable.loc[ready,'strength_q'])
        ready_pvr=pvr.u.notna();np.testing.assert_equal(pvr.loc[ready_pvr,'u'],pvr.loc[ready_pvr,'e'])
    return dict(facts=facts,q=q,CP1=cp,PVR=pvr,evidence=observable)
def write_features(folder,z):
    folder.mkdir(exist_ok=False)
    for k,v in z.items():v.to_parquet(folder/(k+'.parquet'))
def main():
    global START,DEADLINE,NUM,B4,CP,SCORE,evidence,policy,grade,policies,eligible_prices
    START=time.monotonic();DEADLINE=START+180
    freeze=read(O/'EXECUTION_FREEZE.json');assert freeze['pure_feature_fixture_only'] and freeze['fixture_count']==3
    for p,h in freeze['sources'].items():assert sha(p)==h,('changed_frozen_source',p)
    assert not (O/'COMPLETED.json').exists() and not (O/'FAILED.json').exists(),'one execution only'
    sys.path[:0]=[str(RR/'b5-g1-20261025/code'),str(RR/'pv-strength-b5-20261025/code'),str(RR/'pv-participation-response-20261020/code')]
    import evidence as evmod,policy as pomod,grade as grmod,policies_g1 as pgmod,data_utils
    evidence,policy,grade,policies=evmod,pomod,grmod,pgmod;eligible_prices=data_utils.eligible_prices
    NUM=module('volume_fixture_original_numeric',RR/'pv-participation-response-20261020/code/numeric.py')
    B4=evidence._load_frozen_b4();CP=module('volume_fixture_original_CP1',RR/'continuous-protection-lines-20261028/code/model.py');SCORE=score_function()
    import arithmetic
    imported={k:str(Path(m.__file__).resolve()) for k,m in [('evidence',evidence),('policy',policy),('grade',grade),('policies_g1',policies),('arithmetic',arithmetic),('data_utils',data_utils),('B4',B4),('numeric',NUM),('CP1',CP)]}
    for k,p in imported.items():assert p in freeze['sources'],('unexpected imported file',k,p)
    save(O/'IMPORT_IDENTITIES.json',imported)
    refs=freeze['fixtures'];raws={};truths={};receipts=[]
    # ALL true-volume gates finish first. No neutral fixture is run after any mismatch.
    for fixture in refs:
        for stock,sid in [(True,fixture['sid']),(False,fixture['sector'])]:
            budget('true_cold_'+sid);ref=freeze['series'][sid];signal=pd.read_parquet(ref['raw_signal']).loc[:END];raws[sid]=signal
            z=assemble(signal,stock,False);truths[sid]=z
            cached=pd.read_parquet(ref['facts']).loc[:END];parity(z['facts'].reindex(columns=cached.columns),cached,sid+'_true_fullwarm_facts')
            cq=pd.read_parquet(ref['CP1_input']).loc[:END];parity(z['q'].reindex(columns=cq.columns),cq,sid+'_true_fullwarm_CP1_input')
            cc=pd.read_parquet(ref['CP1']).loc[:END];parity(z['CP1'],cc,sid+'_true_fullwarm_CP1')
            scope=dict(sid=sid,fullwarm_facts_rows=len(cached),fullwarm_CP1_rows=len(cc))
            if stock:
                old8=pd.read_parquet(ref['PVR8']);parity(z['PVR'].reindex(old8.index),old8,sid+'_all_existing_PVR8_points')
                s2024=pd.read_parquet(ref['scores2024']);ss=pd.read_parquet(ref['scores_old']);strong=ss.loc['2025-07-01':'2026-06-30'];cal=pd.concat([s2024,strong]);assert len(cal)==968 and cal.index.is_unique
                parity(z['PVR'][['score']].reindex(cal.index),cal,sid+'_968_existing_strategy_score_days')
                scope.update(PVR8_existing_points=len(old8),PVR_score_existing_days=len(cal),PVR_fullwarm_no_old_reference_rows=len(z['PVR'])-len(old8),PVR_scope='all fullwarm generated by original frozen source; only existing8field dates and968score days are independently frozen reference')
            write_features(O/(sid+'_REAL'),z);receipts.append(scope)
            save(O/'TRUE_PARITY_PROGRESS.json',dict(complete_series=receipts,wall_seconds=time.monotonic()-START));print('TRUE_FULLWARM_PARITY',sid,len(cached),flush=True)
    save(O/'TRUE_ALL_6_SERIES_GATE.json',dict(passed=True,series=receipts,account_events=0,wall_seconds=time.monotonic()-START))
    differences=[];prefixes=[]
    for fixture in refs:
        for stock,sid in [(True,fixture['sid']),(False,fixture['sector'])]:
            budget('neutral_'+sid);raw=raws[sid];real=truths[sid];neu=assemble(raw,stock,True);write_features(O/(sid+'_NEUTRAL'),neu)
            # Shared raw fields/eligibility/source domains remain the original source.
            parity(real['facts'][['close','segment_id','factor','raw_close']],neu['facts'][['close','segment_id','factor','raw_close']],sid+'_shared_price_domain')
            np.testing.assert_equal(real['evidence'].ready,neu['evidence'].ready)
            mask=real['facts'].index
            joined=pd.DataFrame(index=mask)
            for col in ['e0_target','e0_floor']+(['i_target','i_buy','g_grade','g_fresh_up','g_acute_down'] if stock else []):
                joined['real_'+col]=real['facts'][col];joined['neutral_'+col]=neu['facts'][col]
            for col in ['event','strength_qeff','strength_S21','strength_S63']:
                joined['real_'+col]=real['evidence'][col];joined['neutral_'+col]=neu['evidence'][col]
            for col in ['receipt','candidate','reset_reason','delta_frontier']:
                joined['real_CP1_'+col]=real['CP1'][col];joined['neutral_CP1_'+col]=neu['CP1'][col]
            joined['real_PVR_score']=real['PVR'].score.reindex(mask);joined['neutral_PVR_score']=neu['PVR'].score.reindex(mask)
            joined.to_parquet(O/(sid+'_PAIRED_TRACE.parquet'))
            report=dict(sid=sid,role='stock' if stock else 'industry',rows=len(mask),differences={})
            for label,a,b in [('E0target',real['facts'].e0_target,neu['facts'].e0_target),('CP1receipt',real['CP1'].receipt,neu['CP1'].receipt)]+([('Itarget',real['facts'].i_target,neu['facts'].i_target),('Ibuy',real['facts'].i_buy,neu['facts'].i_buy),('G1grade',real['facts'].g_grade,neu['facts'].g_grade)] if stock else []):
                known=a.notna()&b.notna();diff=known&a.ne(b);report['differences'][label]=dict(changed_observations=int(diff.sum()),dates=[str(t.date()) for t in a.index[diff]])
            differences.append(report)
            for cut in CUTS:
                budget('physical_prefix_'+sid+'_'+cut);small=assemble(raw.loc[:cut].copy(),stock,True)
                for key in neu:parity(small[key],neu[key].loc[:cut],sid+'_neutral_physical_prefix_'+cut+'_'+key)
                prefixes.append(dict(sid=sid,cut=cut,all_outputs_exact=True))
            print('NEUTRAL_TRACE_CAUSAL',sid,flush=True)
    save(O/'DIFFERENCES.json',differences);save(O/'PHYSICAL_PREFIXES.json',prefixes)
    save(O/'ACT_BOUNDARY.json',dict(account_events=0,ACT_features_computed=False,no_three_stock_toy_breadth=True,
        true_hook='desk.refresh.compute_recovery line34: r*min(1,sqrtDoverB) EW21 then exact stock/sector breadth',neutral_hook='only predictive multiplier1 ->r EW21; original64warm/5stocks/8sectors/.6/price63/ACT20feedback unchanged',full1709_recovery_rebuild_not_authorized=True))
    for p,h in freeze['sources'].items():assert sha(p)==h,('source_changed_during_fixture',p)
    save(O/'COMPLETED.json',dict(passed=True,only_three_preselected_fixtures=True,account_events=0,economic_outputs=0,wall_seconds=time.monotonic()-START,source_freeze_sha256=sha(O/'EXECUTION_FREEZE.json'),
        true_fullwarm_facts_and_CP1_exact=True,PVR_reference_scope='13/21/21existing8fieldpoints and968actualscore days each; no invented fullwarm old8fieldtable',
        interpretation='Pure feature identities/causal differences, not improved entry quality, profit or volume economic increment.'))
    print('THREE_FIXTURES_COMPLETED',time.monotonic()-START,flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as exc:
        save(O/'FAILED.json',dict(stage=STAGE,reason=repr(exc),traceback=traceback.format_exc(),account_events=0,economic_outputs=0,wall_seconds=None if START is None else time.monotonic()-START,no_automatic_retry=True))
        print('FIXTURE_STOPPED',STAGE,repr(exc),flush=True);raise
