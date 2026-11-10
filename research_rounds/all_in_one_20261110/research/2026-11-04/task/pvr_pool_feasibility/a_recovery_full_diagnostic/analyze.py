"""Frozen A source-clause / all original ACT episodes. No Account, Runner or S0."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,hashlib,csv,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
M=Path('/Users/bytedance/Documents/ChatGPT/money');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def book(p):
    SRC[str(p.resolve())]=sha(p)
    with gzip.open(p,'rt')as f:return json.load(f)
def stream(p):
    SRC[str(p.resolve())]=sha(p)
    with gzip.open(p,'rt')as f:
        for line in f:yield json.loads(line)
def horizon(f,day,h):
    t=f.index.get_loc(pd.Timestamp(day));w=f.iloc[t:t+h+1];known=bool(w.known.all())
    vals=w.market.to_numpy(float);base=vals[0];dd=vals/np.maximum.accumulate(vals)-1
    complete=len(w)==h+1 and known
    return dict(horizon=h,complete=complete,available_observations_after=len(w)-1,price_known=known,
      end_day=str(w.index[-1].date()),end_change=float(vals[-1]/base-1)if complete else None,
      max_up=float(np.max(vals/base-1))if complete else None,max_down=float(np.min(vals/base-1))if complete else None,
      max_peak_drawdown=float(dd.min())if complete else None,
      observed_prefix_end_change=float(vals[-1]/base-1),observed_prefix_max_peak_drawdown=float(dd.min()),
      market_price_context_not_trading_return=True)
def main():
    start=time.monotonic();assert not (O/'RESULTS.json').exists(),'preserve prior results; no automatic rerun'
    freeze=read(O/'PROTOCOL_FREEZE.json')
    for p,h in freeze['sources'].items():assert sha(p)==h,(p,'frozen input changed')
    rec=W/'mainline-absolute-Q4-20261031/recovery.csv';SRC[str(rec)]=sha(rec)
    f=pd.read_csv(rec,index_col=0,parse_dates=True)
    prepared=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/input-preparation/prepared-v2/NATIVE1709/market.parquet');SRC[str(prepared)]=sha(prepared)
    k=pd.read_parquet(prepared).reindex(f.index)
    assert np.allclose(f.market,k.market_as_run,rtol=0,atol=1e-12)
    assert np.array_equal(f.breakout.to_numpy(bool),k.breakout_as_run.to_numpy(bool))
    f['known']=k.price_observed.eq(True)&k.price_input.gt(0)&k.breadth.notna()&k.breadth_industries_ready.ge(8)
    f['prior_known']=f.known.shift().rolling(63,min_periods=63).sum().eq(63)
    f['prior_mean63']=f.market.shift().rolling(63,min_periods=63).mean()
    f['up']=f.market.diff().gt(0)
    f['A_input']=f.known&f.prior_known&f.market.gt(f.prior_mean63)&f.up&f.fast_on
    assert np.array_equal(f.fast_on.to_numpy(bool),f.breadth.gt(.6).to_numpy(bool))
    assert np.array_equal(f.breakout.to_numpy(bool),(f.market.gt(f.prior_high63)&f.up&f.fast_on).to_numpy(bool))
    configs=[('2022_2024',ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',726),('strong',O.parent/'runs/2025_26/pair',242)]
    results={};allrows=[]
    for label,run,totaldays in configs:
        b=book(run/'B.json.gz');rr=[r for r in b['audit']if r['kind']=='risk_checkpoint'];assert len(rr)==totaldays
        daily={r['at'][:10]:r for r in stream(run/'daily.jsonl.gz')};assert len(daily)==totaldays
        paused=None;episodes=[];previous_on=True;population=[]
        for r in rr:
            day=r['at'][:10];v=f.loc[pd.Timestamp(day)];ev=r.get('event')
            assert r['fast']==bool(v.fast_on)and r['breakout']==bool(v.breakout)
            if ev=='pause':
                assert paused is None and previous_on and not r['on']
                paused=dict(id=label+'_pause_'+day,pause_day=day,pause_NAV=r['nav'],pause_peak=r['peak'],resume_day=None,rows=[])
            elif not previous_on:assert paused is not None
            if paused is not None:
                eligible=bool(not previous_on and r['flat'])
                x=dict(episode=paused['id'],day=day,old_pre_on=previous_on,old_post_on=r['on'],old_event=ev,original_flat=r['flat'],
                  eligible_old_paused_flat=eligible,market=float(v.market),prior_high63=float(v.prior_high63),prior_mean63=float(v.prior_mean63),
                  breadth=float(v.breadth),fast=bool(v.fast_on),up=bool(v.up),known=bool(v.known and v.prior_known),
                  old_BREAK=bool(v.breakout),A_input=bool(v.A_input),A_eligible=bool(eligible and v.A_input),
                  A_incremental=bool(eligible and v.A_input and not v.breakout),old_NAV=r['nav'],old_available=daily[day]['available'])
                if x['A_eligible']or(eligible and v.breakout):x['future_market_context']={str(h):horizon(f,day,h)for h in [21,63]}
                paused['rows'].append(x);population.append(x)
                if ev=='resume':
                    assert eligible and v.breakout and r['on'];paused['resume_day']=day;episodes.append(paused);paused=None
            previous_on=bool(r['on'])
        if paused is not None:episodes.append(paused)
        incdays={x['day']for x in population if x['A_incremental']}
        opportunities={day:[]for day in incdays};opcounts={day:Counter()for day in incdays};denom=Counter()
        for q in stream(run/'opportunities.jsonl.gz'):
            day=q['day'];denom[day]+=1
            if day not in incdays:continue
            c=opcounts[day];c['all_stock_days']+=1;c['core_Q_true']+=q['core_Q']is True;c['mobile_Q_true']+=q['mobile_Q']is True
            c['raw_fresh_CP1']+=bool(q['CP1_id']);c['fresh_CP1_mobile_Q_true']+=bool(q['CP1_id'])and q['mobile_Q']is True
            c['original_core_role']+='core'in q['roles'];c['original_mobile_role']+='mobile'in q['roles']
            other=[z for z in q['barriers']if z!='ACT_paused'];c['non_ACT_barrier_free_role_events']+=len(q['roles'])if not other else 0
            if q['roles']:
                opportunities[day].append(dict(sid=q['sid'],sector=q['sector'],original_rank=q['rank'],roles=q['roles'],core_Q=q['core_Q'],mobile_Q=q['mobile_Q'],
                  CP1_id=q['CP1_id'],barriers=q['barriers'],non_ACT_barriers=other,held=q['held']))
        assert len(denom)==totaldays and set(denom.values())=={1709}
        for x in population:
            if x['A_incremental']:
                x['Q_freshCP1_counts']=dict(opcounts[x['day']]);assert opcounts[x['day']]['all_stock_days']==1709
        for ep in episodes:
            er=ep['rows'];first=lambda predicate:next((x for x in er if predicate(x)),None)
            ep.update(first_flat=first(lambda x:x['eligible_old_paused_flat']),first_A=first(lambda x:x['A_eligible']),
              first_incremental_A=first(lambda x:x['A_incremental']),first_eligible_old_BREAK=first(lambda x:x['eligible_old_paused_flat']and x['old_BREAK']),
              all_A_days=[x['day']for x in er if x['A_eligible']],all_incremental_A_days=[x['day']for x in er if x['A_incremental']],
              paused_flat_closes=sum(x['eligible_old_paused_flat']for x in er),right_censored=ep['resume_day']is None)
        selected=[x for x in population if x['A_incremental']]
        result=dict(original_closes=totaldays,all_opportunity_stock_days=sum(denom.values()),actual_pause_episodes=len(episodes),episodes=episodes,
          incremental_A_days=len(selected),all_A_days=sum(x['A_eligible']for x in population),
          incremental_Q_freshCP1_counts=dict(sum((opcounts[x['day']]for x in selected),Counter())),
          complete_21=sum(x['future_market_context']['21']['complete']for x in selected),complete_63=sum(x['future_market_context']['63']['complete']for x in selected))
        save(label+'_ALL_EPISODES.json',episodes);save(label+'_ALL_PAUSED_ROWS.json',population)
        save(label+'_INCREMENTAL_OPPORTUNITIES.json',opportunities)
        save(label+'_SUMMARY.json',{k:v for k,v in result.items()if k!='episodes'})
        results[label]=result;allrows+=population
        print('A_FULL',label,'episodes',len(episodes),'incdays',len(selected),'firsts',[(e['pause_day'],e['first_incremental_A']['day']if e['first_incremental_A']else None,e['resume_day'])for e in episodes],flush=True)
    negative=M/'research_rounds/recovery-only-20261027/results/comparison.csv';SRC[str(negative)]=sha(negative)
    with negative.open()as h:old=[x for x in csv.DictReader(h)if x['version']in ['ACT20_BREAK','REC21','REC21_P5','RECEMA_P5']]
    assert len(old)==12
    save('OLD_RECOVERY_NEGATIVE_CONTROLS.json',dict(rows=old,source=str(negative),source_sha256=sha(negative),same_candidate=False,
      source_domain='OLD407/11/2024_to2026Oct26; actual old strategy accounts, not new A native1709 account'))
    SRC[str(Path(__file__))]=sha(__file__)
    for p,h in freeze['sources'].items():assert sha(p)==h,(p,'frozen source changed')
    for p,h in SRC.items():assert sha(p)==h
    save('SOURCE_SHA256.json',SRC)
    save('RESULTS.json',dict(results=results,seconds=time.monotonic()-start,new_accounts=0,new_strategy_events=0,new_S0=0,
      new_policy_future_path_inferred=False,market_horizon_not_trading_return=True,minimum_unit_boundary='pending exact source-only feasibility; rawQ/CP1 is not execution proof'))
    save('GATE.json',dict(passed=True,closes=[726,242],all_source_ACT_inputs_exact=True,all_original_pause_episodes_included=True,
      all_stock_day_denominator=[1709*726,1709*242],all_incremental_A_days_retained=True,source_unchanged=True,new_accounts=0,new_S0=0))
if __name__=='__main__':main()
