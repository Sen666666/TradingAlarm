"""Read-only complete waiting/activation/mother audit. No signal/account changes."""
from pathlib import Path
from collections import defaultdict,Counter
from bisect import bisect_left,bisect_right
import hashlib,json,time,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1];R=Path(__file__).resolve().parent
def j(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b,label):
    if b is None:assert a is None,label
    elif isinstance(b,float):assert math.isclose(a,b,abs_tol=1e-10),label
    else:assert a==b,label
def period(r):
    return (r['day'][:4]if r['day']<'2024-09-24'else'2024_924_to_end')if r['window']=='long'else('2025_H2'if r['day']<'2026-01-01'else'2026_H1')
def ekey(r):return r['window'],r['sid'],r['source_segment'],r['e0_run_start']
def main():
    start=time.monotonic();sources=j(O/'COVERAGE_SOURCE_SHA256.json')|j(O/'ACTIVATION_OVERLAP_SOURCE_SHA256.json')
    assert all(sha(p)==h for p,h in sources.items());B=j(O/'B_EVENTS.json');P=j(O/'P_EVENTS.json');wait=j(O/'ALL_B_TO_P_WAIT.json');episodes=j(O/'ALL_A_GAP_EPISODES.json');act=j(O/'A_BREAKOUT_NATIVE_I_OVERLAP.json');ap=j(O/'A_PULLBACK_NATIVE_I_OVERLAP.json')
    assert len(B)==len(wait)==155917 and len(P)==35699 and len(episodes)==13295
    bmap={(r['window'],r['sid'],r['day']):r for r in B};wmap={(r['window'],r['sid'],r['day']):r for r in wait};assert set(bmap)==set(wmap)
    pmap=defaultdict(list);bsid=defaultdict(list);esid=defaultdict(list)
    for r in P:pmap[ekey(r)].append(r)
    for a in pmap.values():a.sort(key=lambda r:r['day'])
    for r in B:bsid[r['sid']].append(r)
    for r in episodes:esid[r['sid']].append(r)
    recs=j('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');first_I={};positions={};closes={};mother=0;observations=0;A2=0
    for rec in recs:
        assert time.monotonic()-start<60,'bounded coverage audit time exceeded'
        sid=rec['symbol'];f=pd.read_parquet(rec['refs']['facts'],columns=['close','segment_id','e0_target','i_target']);c=f.close.to_numpy(float);valid=np.isfinite(c)&(c>0)&f.segment_id.notna().to_numpy();on=pd.Series(valid,index=f.index)&f.e0_target.eq(1).fillna(False)
        source_change=f.segment_id.ne(f.segment_id.shift()).fillna(True);newrun=on&(~on.shift(fill_value=False)|source_change);rid=newrun.cumsum();run_start=pd.Series(f.index.strftime('%Y-%m-%d'),index=f.index).where(newrun).ffill();ion=on&f.i_target.eq(1);ever=ion.groupby(rid,sort=False).cummax();rawA=on&f.i_target.eq(0)&~ever;A2+=int((on&f.i_target.eq(0)&ever).sum());dates=list(f.index.strftime('%Y-%m-%d'));pos={d:i for i,d in enumerate(dates)};positions[sid]=pos;closes[sid]=c
        saved={(r['window'],r['e0_run_start']):r for r in esid[sid]};seen=set()
        for w,lo,hi in [('long','2022-01-01','2024-12-31'),('strong','2025-07-01','2026-06-30')]:
            mask=rawA&(f.index>=lo)&(f.index<=hi);observations+=int(mask.sum())
            for run,a in f.loc[mask].groupby(rid[mask],sort=False):
                begin=str(run_start.loc[a.index[0]]);key=w,begin;r=saved[key];seen.add(key);mother+=1
                assert r['gap_first_day']==str(a.index[0].date())and r['gap_last_day']==str(a.index[-1].date())and r['gap_observations']==len(a)
                i_dates=f.index[(rid==run)&ion&(f.index>=a.index[0])&(f.index<=hi)];i=str(i_dates[0].date())if len(i_dates)else None
                assert r['first_original_I_active']==i;first_I[w,sid,begin]=i
        assert seen==set(saved)
        # Independently check all B->P waits and B 20-observation price maturity.
        blocks=(source_change|pd.Series(~valid,index=f.index)|pd.Series(~valid,index=f.index).shift(fill_value=True)).cumsum().to_numpy()
        for b in bsid[sid]:
            key=b['window'],sid,b['day'];r=wmap[key];ps=pmap[ekey(b)];pdys=[p['day']for p in ps];n=bisect_left(pdys,b['day']);p=ps[n]if n<len(ps)else None;n2=bisect_right(pdys,b['day']);later=ps[n2]['day']if n2<len(ps)else None
            i=pos[b['day']];distance=pos[p['day']]-i if p else None;hit=p is not None and distance<=20;hi='2024-12-31'if b['window']=='long'else'2026-06-30';end=i+20;mature=end<len(f)and dates[end]<=hi and blocks[end]==blocks[i]
            expected=dict(next_P_day=p['day']if p else None,next_P_state=p['state']if p else None,next_P_observation_wait=distance,next_P_natural_days=(pd.Timestamp(p['day'])-pd.Timestamp(b['day'])).days if p else None,P_within20=hit,price_horizon20_known=bool(mature),no_P20_with_20_price_observations=bool(mature and not hit),insufficient20_price_evaluation=not mature,period=period(b))
            for field,v in expected.items():eq(r[field],v,(key,field))
            assert r.get('P_concurrent_with_B',p is not None and p['day']==b['day'])==(p is not None and p['day']==b['day'])
            if 'strictly_later_P_day'in r:assert r['strictly_later_P_day']==later
            if mature:
                eq(r['first_B_close_return20_pct'],(c[end]/c[i]-1)*100,(key,'ret20'));eq(r['first_B_max_close_return20_pct'],(float(c[i+1:end+1].max())/c[i]-1)*100,(key,'max20'))
    assert mother==13295 and observations==104968 and A2==0
    firsts={}
    for r in sorted(wait,key=lambda r:(r['window'],r['sid'],r['day'])):firsts.setdefault(ekey(r),r)
    for s in j(O/'B_WAIT_SUMMARY.json'):
        rows=wait if s['unit']=='all_B'else list(firsts.values());a=[r for r in rows if (r['window'],r['period'],r['state'])==(s['window'],s['period'],s['state'])];hits=[r for r in a if r['P_within20']];known=[r for r in a if r['price_horizon20_known']];missing=[r for r in known if not r['P_within20']]
        expected=dict(B=len(a),P_within20=len(hits),P_within20_still_A=sum(r['next_P_state']=='A_I_never_started_in_E0'for r in hits),mature20=len(known),mature_no_P20=len(missing),mature_no_P20_but_positive_end20=sum(r['first_B_close_return20_pct']>0 for r in missing),mature_no_P20_but_max20_above20pct=sum(r['first_B_max_close_return20_pct']>=20 for r in missing),next_P_wait_median_observations=float(np.median([r['next_P_observation_wait']for r in hits]))if hits else None,insufficient20=len(a)-len(known))
        for field,v in expected.items():eq(s[field],v,(s['unit'],s['window'],s['period'],field))
    amap={(r['window'],r['sid'],r['day']):r for r in act};assert len(amap)==len(act)==5626
    for key,r in amap.items():
        w,sid,d=key;i=first_I[w,sid,r['e0_run_start']];n=positions[sid][i]-positions[sid][d]if i else None;assert i is None or i>d
        expected=dict(native_I_day=i,native_I_wait_observations=n,native_I_within20=n is not None and n<=20,native_I_before_or_on_P=bool(i and(r['next_P_day']is None or i<=r['next_P_day'])),price_progress_B_to_native_I_pct=(closes[sid][positions[sid][i]]/closes[sid][positions[sid][d]]-1)*100 if i else None)
        for field,v in expected.items():eq(r[field],v,(key,field))
        for field in ['next_P_day','P_within20','no_P20_with_20_price_observations']:assert r[field]==wmap[key][field]
    afirst={}
    for r in sorted(act,key=lambda r:(r['window'],r['sid'],r['day'])):afirst.setdefault(ekey(r),r)
    critical=[]
    for s in j(O/'A_BREAKOUT_NATIVE_I_SUMMARY.json'):
        rows=act if s['unit']=='all_A_B'else list(afirst.values());a=[r for r in rows if (r['window'],period(r))==(s['window'],s['period'])];missing=[r for r in a if r['price_horizon20_known']and not r['P_within20']];progress=[r['price_progress_B_to_native_I_pct']for r in a if r['native_I_within20']]
        expected=dict(A_B=len(a),native_I_within20=sum(r['native_I_within20']for r in a),native_I_before_or_on_P=sum(r['native_I_before_or_on_P']for r in a),mature_no_P20=len(missing),mature_no_P20_but_native_I_within20=sum(r['native_I_within20']for r in missing),mature_no_P20_and_no_native_I20=sum(not r['native_I_within20']for r in missing),no_P_or_native_I20_but_max_close20_above20pct=sum(not r['native_I_within20']and r['first_B_max_close_return20_pct']>=20 for r in missing),native_I20_median_wait=float(np.median([r['native_I_wait_observations']for r in a if r['native_I_within20']]))if progress else None,median_price_progress_to_native_I_pct=float(np.median(progress))if progress else None)
        for field,v in expected.items():eq(s[field],v,(s['unit'],s['window'],s['period'],field))
        if s['unit'].startswith('first')and s['period']in ['2024_924_to_end','2026_H1']:critical.append(s)
    assert len(ap)==1211
    for r in ap:
        w,sid,d=r['window'],r['sid'],r['day'];p=next(p for p in P if p['window']==w and p['sid']==sid and p['day']==d);i=first_I[w,sid,p['e0_run_start']];assert r['native_I_day']==i
        eq(r['native_I_wait_after_P'],positions[sid][i]-positions[sid][d]if i else None,(w,sid,d,'P wait'))
    sem=j(O/'SEMICONDUCTOR_ALL126_EVENT_COVERAGE.json');assert len(sem)==126
    for r in sem:
        p=[v for v in P if v['window']=='strong'and v['sid']==r['sid']and v['day']>='2026-01-01'];assert r['P_by_state']==dict(Counter(v['state']for v in p));assert r['A_P_dates']==[v['day']for v in p if v['state']=='A_I_never_started_in_E0']
    top=sorted([r for r in sem if r['H1_price_return_pct']is not None],key=lambda r:-float(r['H1_price_return_pct']))[:20];AP=[r for r in sem if r['A_P_dates']]
    result=dict(passed=True,status='PASS_INCLUSIVE_WAIT_NATIVE_I_AND_COMPLETE_A_MOTHER',all_B_wait_rows=155917,P_rows=35699,all_A_episodes_independently_rebuilt=mother,A_observations=observations,A2_raw=0,all_B20_prices_and_waits_exact=True,all_native_I_dates_independently_rebuilt=True,all_wait_activation_summary_groups_exact=True,A_P_semiconductor_stocks=len(AP),A_P_semiconductor_events=sum(len(r['A_P_dates'])for r in AP),endpoint_top20_semiconductor_A_P_events=sum(len(r['A_P_dates'])for r in top),critical_first_observed_groups=critical,seconds=time.monotonic()-start,new_accounts=0,new_authorizations=0,caveats=['First B means first observed within each fixed window and source/E0 epoch; not guaranteed full-history first B or first B since each reporting subperiod.','P on the B date is current permission using an earlier anchor and is included as wait0; strictly later P is a distinct field.','Price horizon unknown is retained, not a known missing supplemental signal. E0 can end within a known price-label horizon.','Original I activation is permission state only, not S0 acceptance, funding, fill or profit. An additive supplement does not remove original legal entries.'])
    (R/'COVERAGE_AND_ACTIVATION_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
