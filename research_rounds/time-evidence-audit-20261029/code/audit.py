"""Audit unchanged E0 event facts and cached I/G1 timing; no economic paths."""
from pathlib import Path
import sys,json,time,math,hashlib,importlib.util,datetime,collections
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/time-evidence-audit-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029'
sp=importlib.util.spec_from_file_location('time_reuse_h',E1/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
sys.path.insert(0,str(ROOT/'research_rounds/pv-strength-b5-20261025/code'));sp=importlib.util.spec_from_file_location('time_original_evidence',ROOT/'research_rounds/pv-strength-b5-20261025/code/evidence.py');EV=importlib.util.module_from_spec(sp);sp.loader.exec_module(EV)
START=H.START;END=H.END
def save(p,x):H.save(p,x)
def prepare():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    save(O/'RUN_PLAN.json',dict(scope='Read original code, reconstruct only unchanged pure E0 event facts where no full407 cache exists; aggregate cached states/signals. No new entry policy, indicator modification, economic path or account.',implementation_clock_started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),prior_code_reading_not_separately_timed=True,development_budget_minutes_from_this_stage=15,diagnostic_full_compute_budget_seconds=120,philosophy='Low win rate acceptable, preserve fat tail and cover every trial cost; no promise fewer signals means better economics.',metrics='For latest confirmed up pivot through signal, causal record-frontier log increments f_i. N_eff=(sum f)^2/sum f^2, max-share=max f/sum f, trigger-day share. Single interval age1 is exact; majority-share>1/2 descriptive, not tuned entry filter. Original E0 structure and I event ages/G1 warmth separate.',populations=['all new E0 starts within period','all pure E0 up receipts','first observed I event in each intersecting E0 epoch','all/repeated I events','first and repeated full-Q candidates'],no_return_conditioned_rule_selection=True))
    ps=[ROOT/'TradingAlarm/desk/refresh.py',ROOT/'research_rounds/pv-strength-b5-20261025/code/evidence.py',ROOT/'research_rounds/pv-strength-b5-20261025/code/policy.py',ROOT/'research_rounds/pv-strength-b5-20261025/code/arithmetic.py',ROOT/'research_rounds/pv-strength-b4-20261025/code/model.py',ROOT/'research_rounds/b5-g1-20261025/code/grade.py',ROOT/'research_rounds/b5-g1-20261025/code/policies_g1.py',ROOT/'research_rounds/ix-a-share-entry-20261025/code/entry_rules.py',E1/'market-cache.parquet',E1/'opportunities.parquet']
    for r in H.roster():
        s=r['symbol'];ps += [H.SNAP/'signals'/f'{s}.parquet',H.SNAP/'facts'/f'{s}.parquet',ROOT/'research_rounds/ix-a-share-entry-20261025/signals'/f'{s}.parquet']
    save(O/'input-identity.json',dict(sha256={str(p):H.sha(p) for p in ps},snapshot=str(H.SNAP),before_diagnostic=True,seconds=time.monotonic()-t));H.progress(stage='diagnostic_frozen',inputs=len(ps),seconds=time.monotonic()-t)
def metrics(prices,vol,anchor,t):
    maximum=float(prices[anchor]);increments=[]
    for j in range(anchor+1,t+1):
        c=float(prices[j])
        if EV.compare(c,maximum)>0:increments.append(EV.log_ratio(c,maximum));maximum=c
        else:increments.append(0.)
    total=math.fsum(increments);sq=math.fsum(x*x for x in increments);positive=[x for x in increments if x>0]
    return dict(leg_age=t-anchor,frontier_days=len(positive),frontier_neff=total*total/sq if sq>0 else np.nan,max_frontier_share=max(increments)/total if total>0 else np.nan,last_frontier_share=increments[-1]/total if total>0 and increments else np.nan,last_volume_share=float(vol[t]/math.fsum(vol[anchor+1:t+1])) if t>anchor else np.nan,net_displacement=EV.log_ratio(float(prices[t]),float(prices[anchor])))
def run(sample=False):
    t=time.monotonic();ids=set(H.SAMPLE) if sample else {r['symbol'] for r in H.roster()};dest=O/('sample' if sample else 'diagnostic');dest.mkdir(exist_ok=False);cache=pd.read_parquet(E1/'market-cache.parquet');qsets={s:set(g.loc[g.Q,'date']) for s,g in cache.groupby('symbol')};records=[];audit=[];sources={};coverage=[]
    for n,s in enumerate(sorted(ids)):
        st=time.monotonic();facts=pd.read_parquet(H.SNAP/'facts'/f'{s}.parquet');sig=pd.read_parquet(H.SNAP/'signals'/f'{s}.parquet').reindex(facts.index);old=pd.read_parquet(ROOT/'research_rounds/ix-a-share-entry-20261025/signals'/f'{s}.parquet');common=facts.index.intersection(old.index)
        for a,b in [('g_grade','grade'),('g_fresh_up','fresh_up'),('g_acute_down','acute_down')]:np.testing.assert_allclose(facts.loc[common,a].astype(float),old.loc[common,b].astype(float),rtol=0,atol=0,equal_nan=True)
        firststudyI=set();firststudyQ=set();e0start=None;lastpivot=None;warmrun=0;knownphase=0;unknownphase=0;rawI=0;newE0=0
        for seg,g in facts.groupby('segment_id',sort=False):
            bars=sig.loc[g.index,['close','volume']];ev,_=EV._event_facts(bars);dv=bars[bars.gt(0).all(axis=1)&np.isfinite(bars).all(axis=1)];prices=dv.close.to_numpy(float);vol=dv.volume.to_numpy(float);positions={d:j for j,d in enumerate(dv.index)};prevE=prevI=False;e0at=iat=None;e0id=None;lastpivot=None;warmrun=0
            for j,(r,ee) in enumerate(zip(g.itertuples(),ev.itertuples())):
                day=r.Index
                isE=pd.notna(r.e0_target) and bool(r.e0_target);isI=pd.notna(r.i_target) and bool(r.i_target);isBuy=bool(r.i_buy);ready=pd.notna(r.g_ready) and bool(r.g_ready);warm=ready and r.g_grade>=2;newE=isE and not prevE;newI=isI and not prevI;up=ee.event==1
                if ready:warmrun=warmrun+1 if warm else 0
                if newE:
                    assert up,(s,day,'NR1 first E0 must be original up receipt');e0start=day;e0at=j;e0id=f'{s}|{int(seg)}|{day.date()}';assert EV.compare(float(r.e0_floor),float(ee.confirmed_pivot_price))==0
                if prevE and not isE:assert EV.compare(float(r.close),float(g.iloc[j-1].e0_floor))<=0
                if newI:iat=j
                expected=bool(isI and isE and warm and (newE or bool(r.g_fresh_up)));assert isBuy==expected,(s,day,'I buy definition')
                if up:lastpivot=pd.Timestamp(ee.confirmed_pivot_date)
                inside=START<=day<=END
                if inside and (newE or isBuy or up):
                    anchor=pd.Timestamp(ee.confirmed_pivot_date) if up else lastpivot;assert anchor is not None and day in positions and anchor in positions
                    m=metrics(prices,vol,positions[anchor],positions[day]);phase=old.loc[day,'phase'] if day in old.index else None;reasons=old.loc[day,'up_reasons'] if day in old.index else None;z21=float(old.loc[day,'z21']) if day in old.index and pd.notna(old.loc[day,'z21']) else np.nan
                    firstI=isBuy and e0id not in firststudyI;isQ=day in qsets[s];firstQ=isQ and e0id not in firststudyQ
                    records.append(dict(symbol=s,date=day,segment=int(seg),e0_epoch=e0id,E0_new=newE,E0_up_receipt=up,I_buy=isBuy,Q=isQ,first_I_in_study_epoch=firstI,first_Q_in_study_epoch=firstQ,I_state_new=newI,E0_age=j-e0at if e0at is not None else np.nan,I_state_age=j-iat if iat is not None else np.nan,carry_E0=bool(e0start is not None and e0start<START),warm_age=warmrun,grade=r.g_grade,fresh=bool(r.g_fresh_up),event=float(ee.event),confirmation=float(ee.confirmation),pivot_date=anchor,phase=phase,up_reasons=reasons,z21=z21,**m))
                    if isBuy:firststudyI.add(e0id);rawI+=1;knownphase+=phase is not None;unknownphase+=phase is None
                    if isQ:firststudyQ.add(e0id)
                    if newE:newE0+=1
                prevE=isE;prevI=isI
                if not isE:lastpivot=None;e0at=None;e0id=None
                if not isI:iat=None
        audit.append(dict(symbol=s,raw_I=rawI,new_E0=newE0,old_G1_identity_rows=len(common),G1_reason_known=knownphase,G1_reason_unknown=unknownphase,seconds=time.monotonic()-st))
        if sample or (n+1)%50==0:H.progress(stage='original_fact_diagnostic',sample=sample,stocks=n+1,rows=len(records),seconds=time.monotonic()-t)
        if not sample and time.monotonic()-t>120:raise TimeoutError('120s original fact diagnostic budget exceeded')
    df=pd.DataFrame(records);df.to_parquet(dest/'event-timing.parquet',index=False);pd.DataFrame(audit).to_csv(dest/'source-checks.csv',index=False)
    if not sample:
        a=pd.read_parquet(O/'sample/event-timing.parquet');b=df[df.symbol.isin(H.SAMPLE)];keys=['symbol','date'];pd.testing.assert_frame_equal(a.sort_values(keys).reset_index(drop=True),b.sort_values(keys).reset_index(drop=True),check_exact=True)
    save(dest/'verification.json',dict(passed=True,no_economic_paths=True,pure_original_event_kernel_only=True,all_NR1_entry_is_original_up=True,all_I_buy_definition_exact=True,old_G1_phase_fields_identity=True,old_G1_reason_unknown_rawI=sum(x['G1_reason_unknown'] for x in audit),sample_full_exact=not sample,stocks=len(ids),rows=len(df),seconds=time.monotonic()-t))
    H.progress(stage='diagnostic_done',sample=sample,stocks=len(ids),rawI=int(df.I_buy.sum()),seconds=time.monotonic()-t)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='sample':run(True)
    elif sys.argv[1]=='full':run(False)
