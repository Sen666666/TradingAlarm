from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import json, csv, hashlib, math
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
OUT=ROOT/'mainline_seed_entry_diagnostic_v1'
BASE=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630'
DIAG=ROOT/'mainline_m7_extended_capture_diagnostic_v1'
END='2025-01-20'
Z=D(0)
hashes={}
def read(p):
    hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())
def save(name,x):
    (OUT/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
    if isinstance(x,list) and x:
        with (OUT/(name+'.csv')).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
orders=read(BASE/'ORDERS.json')
attempts=read(BASE/'ATTEMPTS.json')
plans=read(BASE/'EVENT_REQUEST_PLANS.json')
sectors=read(BASE/'SECTOR_DAILY.json')
ledger=read(BASE/'DAY_LEDGER.json')
rounds=read(DIAG/'ACTUAL_ROUNDS.json')
holds=read(BASE/'HOLDINGS.json')
assert ledger[-1]['day']==END and len(ledger)==93
sector={(r['day'],r['sector51']):r for r in sectors}
roundmap={r['round_id']:r for r in rounds}
seedorders=[o for o in orders if o['side']=='BUY_SEED']
days=[r['day'] for r in ledger]
holdlast={}
for h in holds:holdlast[h['round_id']]=max(h['day'],holdlast.get(h['round_id'],h['day']))
losses=defaultdict(list)
for a in attempts:
    if a.get('exit_day') and not a['final_qty'] and D(a['marked_net_pnl'])<0:
        losses[a['sid']].append(a)
manifest_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
manifest={m['symbol']:m for m in read(manifest_path)}
frames={}
def frame(sid):
    if sid in frames:return frames[sid]
    m=manifest[sid];p=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
    h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m['source_sha256'][str(p)];hashes[str(p)]=h
    z=pd.read_parquet(p).loc[:END].copy()
    cols=['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']
    ok=z.observed_bar.eq(True)&z.price_eligible.eq(True)&z.volume_eligible.eq(True)&z.source_invalid.eq(False)&z.synthetic_event_bar.eq(False)
    for c in cols:ok &= z[c].notna()&z[c].gt(0)
    for c in ['source_kind','source_path','segment_id']:ok &= z[c].notna()&z[c].astype(str).ne('')
    z['_C']=z.raw_close*z.adjustment_factor
    ok &= ((z['_C']/z.close)-1).abs().lt(1e-10)
    z['_ok']=ok
    frames[sid]=z
    return z
# G2 is a causal-observability classification on actual baseline history.
# It is NOT a simulated filtered history: failures of baseline rounds that a filter
# would have rejected remain baseline facts here. No counterfactual NAV is claimed.
g2={}
failures=[];unlocks=[]
for sid, aa in losses.items():
    z=frame(sid);events=defaultdict(list)
    for a in aa:
        end=holdlast.get(a['id'])
        span=z.loc[a['signal_day']:end] if end else z.iloc[:0]
        known=bool(len(span) and span['_ok'].all() and len(span[['source_kind','source_path','segment_id']].drop_duplicates())==1)
        high=float(span['_C'].max()) if known else None
        ev=dict(sid=sid,round_id=a['id'],signal_day=a['signal_day'],exit_day=a['exit_day'],last_held_close=end,known=known,failure_high=high,realized_net=a['marked_net_pnl'])
        failures.append(ev);events[a['exit_day']].append(ev)
    anchor=None;unknown=False;anchor_rounds=[]
    for d in days:
        for ev in events[d]:
            anchor_rounds.append(ev['round_id'])
            if not ev['known']:unknown=True
            elif anchor is None or ev['failure_high']>anchor:anchor=ev['failure_high']
        row=z.loc[pd.Timestamp(d)] if pd.Timestamp(d) in z.index else None
        price_known=row is not None and bool(row['_ok'])
        prior_anchor=anchor;prior_rounds=list(anchor_rounds)
        if anchor_rounds and not unknown and price_known and float(row['_C'])>anchor:
            unlocks.append(dict(sid=sid,day=d,close=float(row['_C']),failed_structure_high=anchor,failed_rounds=list(anchor_rounds)))
            anchor=None;anchor_rounds=[]
        status='PASS_NO_FAILED_STRUCTURE' if not anchor_rounds else 'UNKNOWN' if unknown or not price_known else 'BLOCK_NOT_ABOVE_FAILED_STRUCTURE'
        g2[(sid,d)]=dict(G2=status,G2_anchor=anchor,G2_anchor_rounds=list(anchor_rounds),G2_close=float(row['_C']) if price_known else None,G2_unlocked_today=bool(prior_rounds and not anchor_rounds),G2_prior_anchor=prior_anchor)
# request classification, including rejected/capital-retained requests
request_rows=[]
for p in plans:
    if p['kind']!='SEED':continue
    s=sector[(p['day'],p['sector51'])]
    r5=s.get('return5_median')
    g1='PASS_NOT_MATURE' if p['allocation_phase']!='MATURE' else ('UNKNOWN' if r5 is None else 'PASS' if r5>0 else 'BLOCK_NONPOSITIVE_SECTOR_RETURN5')
    r={**p,**{k:s.get(k) for k in ['state','n','N','S','F','rs5','rs10','rs20','return5_median','return10_median','M_streak']},'G1':g1,
       **g2.get((p['sid'],p['day']),dict(G2='PASS_NO_FAILED_STRUCTURE',G2_anchor=None,G2_anchor_rounds=[],G2_close=None,G2_unlocked_today=False,G2_prior_anchor=None))}
    request_rows.append(r)
requestmap={(r['day'],r['sid'],r['signal_day']):r for r in request_rows}
filled=[]
for o in seedorders:
    p=requestmap[(o['plan_day'],o['sid'],o['signal_day'])]
    a=roundmap[o['round_id']]
    assert o['allocation_phase']==p['allocation_phase']
    row=dict(round_id=o['round_id'],sid=o['sid'],name=o['name'],sector51=o['sector51'],plan_day=o['plan_day'],seed_day=o['day'],signal_day=o['signal_day'],phase=o['allocation_phase'],seed_cost=-D(o['cash_delta']),
             net=D(a['final_marked_net']),peak_net=D(a['peak_close_net']),peak_day=a['peak_close_day'],final_qty=a['final_qty'],add_count=a['add_count'],exit_day=a.get('exit_day'),exit_reason=a.get('exit_reason'),
             **{k:p[k] for k in ['M','E','state','n','N','S','F','rs5','rs10','rs20','return5_median','return10_median','M_streak','stock_excess5','stock_true_streak','G1','G2','G2_anchor','G2_anchor_rounds','G2_close','G2_unlocked_today']})
    filled.append(row)
def summary(rs):
    net=sum((r['net'] for r in rs),Z)
    return dict(rounds=len(rs),net=net,loss=-sum((min(Z,r['net']) for r in rs),Z),gain=sum((max(Z,r['net']) for r in rs),Z),losing=sum(r['net']<0 for r in rs),positive=sum(r['net']>0 for r in rs),closed=sum(not r['final_qty'] for r in rs),open=sum(bool(r['final_qty']) for r in rs),seed_cost=sum((r['seed_cost'] for r in rs),Z),peak_positive_sum=sum((max(Z,r['peak_net']) for r in rs),Z))
summary_rows=[]
for period,sel in [('all',filled),('startup_0923_0930',[r for r in filled if '2024-09-23'<=r['plan_day']<='2024-09-30']),('new_since_1106',[r for r in filled if r['seed_day']>'2024-11-06'])]:
    for gate in ['G1','G2']:
        for status in ['ALL','PASS','BLOCK','UNKNOWN']:
            rs=[r for r in sel if status=='ALL' or r[gate].startswith(status)]
            summary_rows.append(dict(period=period,gate=gate,status=status,**summary(rs)))
sector_rows=[]
for gate in ['G1','G2']:
    new=[r for r in filled if r['seed_day']>'2024-11-06']
    for sec in sorted({r['sector51'] for r in new}):
        for status in ['ALL','BLOCK','PASS','UNKNOWN']:
            rs=[r for r in new if r['sector51']==sec and (status=='ALL' or r[gate].startswith(status))]
            sector_rows.append(dict(gate=gate,sector51=sec,status=status,**summary(rs)))
request_summary=[]
for label,rs in [('startup_0923_0930',[r for r in request_rows if '2024-09-23'<=r['day']<='2024-09-30']),('late_1106_0120',[r for r in request_rows if r['day']>='2024-11-06'])]:
    for gate in ['G1','G2']:
        for status in ['ALL','PASS','BLOCK','UNKNOWN']:
            xs=[r for r in rs if status=='ALL' or r[gate].startswith(status)]
            request_summary.append(dict(period=label,gate=gate,status=status,requests=len(xs),unique_signals=len({(r['sid'],r['signal_day']) for r in xs}),baseline_close_approved=sum(r['reference_q']>0 for r in xs),phases=dict(Counter(r['allocation_phase'] for r in xs))))
# Earliest later passing baseline request for blocked fills, never invent a fill.
delays=[]
for r in filled:
    for gate in ['G1','G2']:
        if not r[gate].startswith('BLOCK'):continue
        z=frame(r['sid'])
        later=[p for p in request_rows if p['sid']==r['sid'] and p['day']>r['plan_day'] and p[gate].startswith('PASS')]
        pp=min(later,key=lambda p:p['day']) if later else None
        ix=z.index;start=pd.Timestamp(r['seed_day']);base=float(z.at[start,'raw_open'])*float(z.at[start,'adjustment_factor'])
        future=z.loc[start:END];future=future[future['_ok']]
        latest=float(future.iloc[-1]['_C']) if len(future) else None
        nextopen=None;nextday=None
        if pp:
            dates=ix[ix>pd.Timestamp(pp['day'])]
            if len(dates):
                dt=dates[0];bar=z.loc[dt]
                if bool(bar['_ok']):nextopen=float(bar.raw_open*bar.adjustment_factor);nextday=str(dt.date())
        delays.append(dict(gate=gate,**r,next_passing_request=pp['day'] if pp else None,next_request_phase=pp['allocation_phase'] if pp else None,next_request_original_decision=pp['decision'] if pp else None,next_possible_open_day=nextday,next_open_price_change_pct=(nextopen/base-1)*100 if nextopen else None,baseline_seed_adjusted_open=base,maximum_subsequent_close_change_pct=(float(future['_C'].max())/base-1)*100 if len(future) else None,end_close_change_pct=(latest/base-1)*100 if latest else None,prices_only_not_executable_return=True))
notes=['No engine run, no strategy changes, no grid search. G1 and G2 are independent diagnostics, never stacked.',
       'All filters use plan_day CLOSE, not entry-day CLOSE. Only certified data through 2025-01-20 are used.',
       'G1 only changes MATURE SEED admission. EVENT/RESIDUAL, ADD, exits and capital allocation remain outside scope.',
       'G2 starts clear on 2024-09-02 because no earlier actual portfolio history is available. A known losing completed baseline round creates a lock. A new failed round cannot lower the locked high. First valid close strictly above the high clears it. Unknown pauses and cannot clear.',
       'G2 uses actual baseline completed loss history, including trades the proposed filter might block. This is observable baseline classification, not a causal filtered ledger.',
       'Removed round net/loss/gain include all its baseline ADDs/exits and terminal mark. They are not expected savings or portfolio improvement; cash recycling, retained requests, changed orders and missed profits require later approved replay.',
       'Next passing request is from frozen baseline requests only; baseline-held stocks have no new request. Missing later request does not prove no daily breakout occurred. Price-only opportunity excludes fees, limits, capacity and funding.',
       'Startup and late window were already observed, so all conclusions are development diagnostics, not out-of-sample validation. Source universe, mapping and corporate-action conventions inherit baseline limitations.']
save('FORMULAS',dict(G1='SEED and allocation_phase=MATURE requires sector.return5_median(plan_CLOSE)>0; other phases unchanged.',G2='After actual fully closed losing round, lock stock at maximum valid adjusted close from original signal_day to last held CLOSE; all later new SEED phases require CLOSE strictly above persistent failed-structure high; no failed round lowers a still-locked anchor. Retained unfilled capital tickets are not losses.',notes=notes))
for name,x in [('REQUEST_CLASSIFICATION',request_rows),('FILLED_SEED_CLASSIFICATION',filled),('SUMMARY',summary_rows),('SECTOR_SUMMARY',sector_rows),('REQUEST_SUMMARY',request_summary),('KNOWN_FAILURE_ANCHORS',failures),('G2_UNLOCKS',unlocks),('DELAY_OPPORTUNITY_DIAGNOSTIC',delays),('SOURCE_HASHES',hashes)]:save(name,x)
print(json.dumps(dict(summary=summary_rows,request_summary=request_summary,output=str(OUT)),ensure_ascii=False,default=str))
