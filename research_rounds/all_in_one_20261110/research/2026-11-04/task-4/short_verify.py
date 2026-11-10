"""Read-only evidence census and saved-book aggregation; no model/runner imports."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal as D
import hashlib, json, gzip, math, time
import pandas as pd
import numpy as np

O=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
OLD=W/'pvr-slot1-native-readiness-20261101'
L=T/'loss_correction/no60_behavior_v1'
CASES={'2022':('2022-01-01','2022-12-31'),'2023':('2023-01-01','2023-12-31'),
       'POST924':('2024-09-24','2024-12-31'),'2026H1':('2026-01-01','2026-06-30')}
SRC={}
def bind(p):
    p=Path(p); h=hashlib.sha256(p.read_bytes()).hexdigest()
    if str(p) in SRC: assert SRC[str(p)]==h
    SRC[str(p)]=h; return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
    with gzip.open(bind(p),'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def frame(p,**kw):return pd.read_parquet(bind(p),**kw)
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(D,Path,pd.Timestamp)):return str(x)
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def week(d):return str(pd.Timestamp(d).to_period('W-FRI').end_time.date())

def industry_census():
    cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
    nodes=[n for n in cat if n['domain']=='NATIVE1709'];assert len(nodes)==90
    rows=[];contexts=[];semis=None
    for n in nodes:
        d=frame(n['daily_result_path']);p=frame(n['input_file'])
        d.index=pd.DatetimeIndex(d.index)
        assert d.index.equals(p.index)
        assert np.allclose(d.close,p.price_input,equal_nan=True)
        prior=p.price_input.shift(1).rolling(20,min_periods=20).max()
        seg=p.price_source_segment_id
        comparable=(seg.shift(1).rolling(20,min_periods=20).min()==seg)&(seg.shift(1).rolling(20,min_periods=20).max()==seg)
        prior=prior.where(comparable)
        cur=None;prev_literal=None
        for i,r in enumerate(d.itertuples()):
            at=str(r.Index.date());events=list(r.events)
            if any(e.startswith('price_failure') or e=='source_changed_context_ended' for e in events):
                if cur:cur['ended']=at;contexts.append(cur)
                cur=None;prev_literal=None
            for kind in ['break_started','repair_restored']:
                if kind in events:
                    if cur:cur['superseded']=at;contexts.append(cur)
                    cur=dict(sector=n['sector'],industry=n['name'],start=at,origin=kind,
                             start_price=r.close,start_breadth=r.breadth,
                             first_promotion=None,promotion_price=None,literal_events=[],ended=None)
                    prev_literal=None
            live=bool(cur and r.mode=='ACTIVE' and pd.isna(r.pending_failure_at))
            high=bool(pd.notna(r.close) and pd.notna(prior.iloc[i]) and r.close>prior.iloc[i])
            breadth=bool(cur and pd.notna(r.breadth) and pd.notna(cur['start_breadth']) and r.breadth>=cur['start_breadth'])
            literal=bool(live and at>cur['start'] and high and breadth)
            lower_than_previous=bool(literal and prev_literal is not None and r.close<=prev_literal)
            if literal:
                cur['literal_events'].append(dict(day=at,price=r.close,breadth=r.breadth,
                    prior20_high=prior.iloc[i],previous_awarded_high=prev_literal,
                    not_above_last_awarded_high=lower_than_previous))
                prev_literal=r.close
                if cur['first_promotion'] is None:
                    cur['first_promotion']=at;cur['promotion_price']=r.close
                    cur['wait_observations']=i-d.index.get_loc(pd.Timestamp(cur['start']))
                    cur['price_change_before_promotion_pct']=(r.close/cur['start_price']-1)*100
            for case,(lo,hi) in CASES.items():
                if lo<=at<=hi:
                    rows.append(dict(case=case,day=at,sector=n['sector'],industry=n['name'],price=r.close,
                       breadth=r.breadth,prior20_high=prior.iloc[i],live_context=live,
                       context_start=cur['start'] if cur else None,origin=cur['origin'] if cur else None,
                       initial_breadth=cur['start_breadth'] if cur else None,
                       original_permit=bool(r.permit_next_open),original_events=events,
                       price20_break=high,breadth_not_worse_than_start=breadth,
                       literal_tier_event=literal,not_above_last_awarded_high=lower_than_previous,
                       first_promotion=cur['first_promotion'] if cur else None,
                       promoted=bool(cur and cur['first_promotion']),unknown=list(r.unknown)))
        if cur:contexts.append(cur)
        if n['name']=='半导体':semis=d.copy()
    out=pd.DataFrame(rows);out.to_parquet(O/'INDUSTRY_DAILY_BEHAVIOR.parquet',index=False)
    stats={}
    for case,(lo,hi) in CASES.items():
        a=out[out.case.eq(case)];breaks=[c for c in contexts if c['origin']=='break_started' and lo<=c['start']<=hi]
        promoted=[c for c in breaks if c['first_promotion'] is not None and c['first_promotion']<=hi]
        waits=[c['wait_observations'] for c in promoted];costs=[c['price_change_before_promotion_pct'] for c in promoted]
        stats[case]=dict(industry_observations=len(a),industries=a.sector.nunique(),days=a.day.nunique(),
          live_observations=int(a.live_context.sum()),literal_tier_days=int(a.literal_tier_event.sum()),
          literal_tier_days_with_no_new_awarded_high=int(a.not_above_last_awarded_high.sum()),
          literal_break_origin_days=int((a.literal_tier_event&a.origin.eq('break_started')).sum()),
          literal_repair_origin_days=int((a.literal_tier_event&a.origin.eq('repair_restored')).sum()),
          break_contexts_started_in_window=len(breaks),promoted_by_window_end=len(promoted),
          not_promoted_by_window_end=len(breaks)-len(promoted),
          promotion_wait_median=float(np.median(waits)) if waits else None,
          promotion_wait_max=max(waits) if waits else None,
          price_change_to_promotion_median_pct=float(np.median(costs)) if costs else None,
          price_change_to_promotion_max_pct=max(costs) if costs else None)
    relevant=[c for c in contexts if any(c['start']<=hi and (c['ended'] is None or c['ended']>=lo) for lo,hi in CASES.values())]
    save('INDUSTRY_CONTEXTS.json',relevant);save('INDUSTRY_BEHAVIOR_SUMMARY.json',stats)
    return out,semis

def saved_semis(diagnostic,semis):
    den=read(OLD/'semiconductor-2026H1-readonly/SEMICONDUCTOR_ALL_STOCKS_HINDSIGHT_DENOMINATOR.json')
    assert len(den)==126
    ids={x['sid'] for x in den};sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    policyroots={'PVR_BASELINE':OLD/'runs/2025_26/pair','PVR_NO60':T/'pvr_pool_feasibility/runs/2025_26/pair'}
    weekly=[];dailies={};stockrows=[]
    for pol,root in policyroots.items():
        funnel=read(L/(pol+'-SEMICONDUCTOR_FUNNEL.json'))['all_market_receipts']
        assert len(funnel)==833
        lifecycles=read(L/'SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json')[pol]['all_actual_layers']
        accepted=read(L/(pol+'-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json'))
        heldids={x['sid'] for x in accepted}
        prices={s:frame(sm[s]['refs']['facts'],columns=['raw_close']) for s in heldids}
        daily=gz(root/'daily.jsonl.gz',True)
        book=gz(root/'B.json.gz');trades=[x for x in book['trades'] if x['security_id'] in ids]
        dividends=[x['receivable'] for x in book['audit'] if x['kind']=='dividend_accrual' and x['receivable']['security_id'] in ids]
        flow=D(0);div=D(0);curve=[];before=None
        for r in daily:
            day=r['at'][:10]
            if day<'2025-12-31':continue
            inv=sum((D(q)*D(str(prices[s].loc[:day].raw_close.iloc[-1])) for s,q in r['positions'].items() if s in ids and q),D(0))
            flow=sum(((D(x['gross_cny']) if x['side']=='sell' else -D(x['gross_cny']))-D(x['fees_cny']) for x in trades if x['at'][:10]<=day),D(0))
            div=sum((D(x['net_local']) for x in dividends if x['ex_at'][:10]<=day),D(0))
            wealth=inv+flow+div
            if day=='2025-12-31':before=wealth
            if '2026-01-01'<=day<='2026-06-30':
                curve.append(dict(day=day,week=week(day),inventory=float(inv),weight_pct=float(inv/D(r['nav'])*100),
                  cash_pct=float(D(r['available'])/D(r['nav'])*100),portfolio_exposure_pct=float(D(r['inventory'])/D(r['nav'])*100),
                  cumulative_H1_wealth=float(wealth-before),industry_stock_count=sum(1 for s,q in r['positions'].items() if q and s in ids)))
        assert len(curve)==116
        assert abs(D(str(curve[-1]['cumulative_H1_wealth']))-sum((D(x['net']) for x in lifecycles),D(0)))<D('.000001')
        dailies[pol]=curve
        df=pd.DataFrame(curve)
        for wk,g in df.groupby('week'):
            days=set(g.day);receipts=[x for x in funnel if x['signal_day'] in days];fills=[x for x in lifecycles if x['opened'] in days]
            st=semis.loc[min(days):max(days)];dg=diagnostic[diagnostic.case.eq('2026H1')&diagnostic.industry.eq('半导体')&diagnostic.day.isin(days)]
            weekly.append(dict(policy=pol,week=wk,first_day=min(days),last_day=max(days),industry_close=float(st.close.iloc[-1]),
                breadth_last=float(st.breadth.iloc[-1]),F1_events=[f'{t.date()}:{e}' for t,r in st.iterrows() for e in r.events],
                tier_days=dg.loc[dg.literal_tier_event,'day'].tolist(),mature_CP1_Q_receipts=len(receipts),
                categories=dict(Counter(x['category'] for x in receipts)),planned_receipts=sum(x['frozen_intent'] is not None for x in receipts),
                actual_all_role_filled_layers=len(fills),actual_buy_cost=sum(float(x['buy_cost']) for x in fills),
                mean_industry_weight_pct=float(g.weight_pct.mean()),last_industry_weight_pct=float(g.weight_pct.iloc[-1]),
                mean_portfolio_exposure_pct=float(g.portfolio_exposure_pct.mean()),mean_cash_pct=float(g.cash_pct.mean()),
                cumulative_H1_wealth=float(g.cumulative_H1_wealth.iloc[-1])))
        for s in den:
            rr=[x for x in funnel if x['sid']==s['sid']];a=[x for x in lifecycles if x['sid']==s['sid']]
            stockrows.append(dict(policy=pol,sid=s['sid'],name=s['name'],price_status=s['status'],
                H1_price_return_pct=s.get('price_return_pct'),market_receipts=len(rr),actual_layers=len(a),
                actual_buy_cost=sum(float(x['buy_cost']) for x in a),actual_net=sum(float(x['net']) for x in a),
                outcome_categories=dict(Counter(x['category'] for x in rr)),
                group='funded' if a else 'market_receipt_unfunded' if rr else 'no_833_market_receipt'))
    save('SEMICONDUCTOR_WEEKLY_CHAIN.json',weekly);pd.DataFrame([{k:v for k,v in r.items() if k not in ['categories','F1_events','tier_days']} for r in weekly]).to_csv(O/'SEMICONDUCTOR_WEEKLY_CHAIN.csv',index=False)
    save('SEMICONDUCTOR_ALL126_COMPARISON.json',stockrows);save('SEMICONDUCTOR_DAILY_MONEY.json',dailies)
    grouped=[]
    for (pol,group),rs in pd.DataFrame(stockrows).groupby(['policy','group']):
        ret=pd.to_numeric(rs.H1_price_return_pct,errors='coerce')
        grouped.append(dict(policy=pol,group=group,stocks=len(rs),known_H1_price_labels=int(ret.notna().sum()),
          H1_price_return_median_pct=float(ret.median()),H1_price_return_mean_pct=float(ret.mean()),
          H1_price_ge100_stocks=int((ret>=100).sum()),H1_price_negative_stocks=int((ret<0).sum()),
          actual_net=float(rs.actual_net.sum()),actual_buy_cost=float(rs.actual_buy_cost.sum())))
    save('SEMICONDUCTOR_GROUP_SUMMARY.json',grouped)

def main():
    start=time.monotonic();bind(__file__);bind(O/'PROTOCOL.txt');bind(O/'review/INDUSTRY_TWO_LAYER_LOGIC_REVIEW.txt')
    assert not (O/'COMPLETION.json').exists()
    evidence,semis=industry_census();saved_semis(evidence,semis)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in SRC.items())
    save('SOURCE_SHA256.json',SRC);save('COMPLETION.json',dict(seconds=time.monotonic()-start,new_accounts=0,
        new_financial_events=0,indicator_reruns=0,new_daily_tier_diagnostic=True,source_files=len(SRC)))
    print((O/'INDUSTRY_BEHAVIOR_SUMMARY.json').read_text());print((O/'SEMICONDUCTOR_GROUP_SUMMARY.json').read_text())
if __name__=='__main__':main()
