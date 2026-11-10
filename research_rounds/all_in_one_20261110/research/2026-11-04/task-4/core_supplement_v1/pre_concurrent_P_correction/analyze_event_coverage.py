"""Read-only all-B waiting and evaluation cohorts. No new signal or account."""
from pathlib import Path
from collections import defaultdict,Counter
from bisect import bisect_right
import hashlib,json,pickle,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent; SRC={}
def read(p):
    p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def period(r):
    d=r['day']
    if r['window']=='long':return d[:4] if d<'2024-09-24' else '2024_924_to_end'
    return '2025_H2' if d<'2026-01-01' else '2026_H1'
def stats(rows):
    out=dict(events=len(rows),stocks=len({r['sid']for r in rows}),
             stock_source_E0_epochs=len({(r['sid'],r['source_segment'],r['e0_run_start'])for r in rows}))
    out['future_close_evaluation']={}
    for h in ('5','20','60'):
        vals=[r['future'][h]['close_return_pct']for r in rows if r['future'][h]is not None]
        lows=[r['future'][h]['min_close_return_pct']for r in rows if r['future'][h]is not None]
        out['future_close_evaluation'][h]=dict(known=len(vals),unknown=len(rows)-len(vals),
            mean_pct=float(np.mean(vals))if vals else None,median_pct=float(np.median(vals))if vals else None,
            negative=sum(v<0 for v in vals),min_close_below_minus10pct=sum(v<=-10 for v in lows))
    return out

def main():
    start=time.monotonic();SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    B=read(O/'B_EVENTS.json');P=read(O/'P_EVENTS.json');E=read(O/'ALL_A_GAP_EPISODES.json')
    fp=O.parent/'new_price_trend_v1/PRICE_FEATURES.pkl';SRC[str(fp)]=hashlib.sha256(fp.read_bytes()).hexdigest()
    with fp.open('rb')as h:features=pickle.load(h)
    pmap=defaultdict(list)
    for r in P:pmap[(r['window'],r['sid'],r['source_segment'],r['e0_run_start'])].append(r)
    for rows in pmap.values():rows.sort(key=lambda r:r['day'])
    wait=[];firsts={}
    for r in B:
        key=(r['window'],r['sid'],r['source_segment'],r['e0_run_start']);a=pmap[key];days=[x['day']for x in a]
        n=bisect_right(days,r['day']);p=a[n]if n<len(a)else None
        idx=features[r['sid']].index;bpos=idx.get_loc(pd.Timestamp(r['day']))
        distance=idx.get_loc(pd.Timestamp(p['day']))-bpos if p else None
        within=p is not None and distance<=20
        mature=r['future']['20']is not None
        z=dict(window=r['window'],sid=r['sid'],source_segment=r['source_segment'],e0_run_start=r['e0_run_start'],
               day=r['day'],period=period(r),state=r['state'],next_P_day=p['day']if p else None,
               next_P_state=p['state']if p else None,next_P_observation_wait=distance,
               next_P_natural_days=(pd.Timestamp(p['day'])-pd.Timestamp(r['day'])).days if p else None,
               P_within20=within,price_horizon20_known=mature,
               no_P20_with_20_price_observations=bool(mature and not within),
               insufficient20_price_evaluation=not mature,
               first_B_close_return20_pct=r['future']['20']['close_return_pct']if mature else None,
               first_B_max_close_return20_pct=r['future']['20']['max_close_return_pct']if mature else None)
        wait.append(z);firsts.setdefault(key,z)
    summaries=[]
    for unit,rows in [('all_B',wait),('first_B_per_E0_epoch',list(firsts.values()))]:
        groups=defaultdict(list)
        for r in rows:groups[(r['window'],r['period'],r['state'])].append(r)
        for key,a in groups.items():
            hits=[r for r in a if r['P_within20']];known=[r for r in a if r['price_horizon20_known']]
            missing=[r for r in known if not r['P_within20']]
            summaries.append(dict(unit=unit,window=key[0],period=key[1],state=key[2],B=len(a),
                 P_within20=len(hits),P_within20_still_A=sum(r['next_P_state']=='A_I_never_started_in_E0'for r in hits),
                 mature20=len(known),mature_no_P20=len(missing),
                 mature_no_P20_but_positive_end20=sum(r['first_B_close_return20_pct']>0 for r in missing),
                 mature_no_P20_but_max20_above20pct=sum(r['first_B_max_close_return20_pct']>=20 for r in missing),
                 next_P_wait_median_observations=float(np.median([r['next_P_observation_wait']for r in hits]))if hits else None,
                 insufficient20=len(a)-len(known)))
    pgroups=defaultdict(list)
    for r in P:pgroups[(r['window'],period(r),r['state'])].append(r)
    pc=[dict(window=k[0],period=k[1],state=k[2],**stats(a))for k,a in pgroups.items()]
    # Current-industry and endpoint labels are evaluation only and keep zero/unknown members.
    sem=read(O.parent/'SEMICONDUCTOR_ALL126_COMPARISON.json');sem={r['sid']:r for r in sem if r['policy']=='PVR_BASELINE'}
    assert len(sem)==126
    all126=[]
    for sid,meta in sorted(sem.items()):
        pr=[r for r in P if r['sid']==sid and r['window']=='strong'and r['day']>='2026-01-01']
        br=[r for r in B if r['sid']==sid and r['window']=='strong'and r['day']>='2026-01-01']
        w=[r for r in wait if r['sid']==sid and r['window']=='strong'and r['day']>='2026-01-01']
        all126.append(dict(sid=sid,name=meta['name'],H1_price_status=meta['price_status'],
            H1_price_return_pct=meta['H1_price_return_pct'],original_PVR_actual_layers=meta['actual_layers'],
            P_by_state=dict(Counter(r['state']for r in pr)),B_by_state=dict(Counter(r['state']for r in br)),
            A_P_dates=[r['day']for r in pr if r['state']=='A_I_never_started_in_E0'],
            A_mature_B_without_P20=sum(r['state']=='A_I_never_started_in_E0'and r['no_P20_with_20_price_observations']for r in w)))
    top=read(O.parent/'new_price_trend_v1/analysis/ORIGINAL_TOP10_WINNER_COVERAGE.json');winners=[]
    for q in top:
        w=q['window'];old=q['original_winner'];a=[r for r in P if r['sid']==old['sid']and r['window']==w]
        winners.append(dict(window=w,original=old,P_by_state=dict(Counter(r['state']for r in a)),
                            P_dates=[dict(day=r['day'],state=r['state'])for r in a]))
    save('ALL_B_TO_P_WAIT.json',wait);save('B_WAIT_SUMMARY.json',summaries);save('P_PERIOD_EVALUATION.json',pc)
    save('SEMICONDUCTOR_ALL126_EVENT_COVERAGE.json',all126);save('ORIGINAL_TOP10_EVENT_COVERAGE.json',winners)
    scope=dict(seconds=time.monotonic()-start,new_accounts=0,signals_unchanged=True,
         all_B_rows=len(wait),P_rows=len(P),A_gap_epochs=len(E),all126=len(all126),
         first_B_epoch_rows=len(firsts),
         caveats=['B and P repeated observations are not independent opportunities.',
             'Next P beyond20 observations does not cover this B; its later anchor is a different proof.',
             'No-P20 uses a known20 source-continuous price horizon; insufficient/end/source cuts remain unknown.',
             'A P occurring after native I activation is not a never-I-started supplemental opportunity.',
             'Supplement is additive to old legal entries; no P on an old winner does not mean the old entry would be blocked. Account crowding is not yet tested.',
             'Forward close return and minimum close are price evaluations, not executable or fee-inclusive account returns.',
             'Semiconductor price/industry labels and old top winners are evaluation only, never signal inputs.'])
    save('COVERAGE_SCOPE.json',scope);save('COVERAGE_SOURCE_SHA256.json',SRC)
    print(json.dumps(scope,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
