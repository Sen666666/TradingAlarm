"""Bounded read-only arithmetic; no Account, strategy, price loader or indicators."""
import csv, gzip, hashlib, json
from pathlib import Path
from decimal import Decimal as D
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
SOURCES = {
    'M_B': 'ar6_native_feasibility/market_recovery_three_state/diagnostic_v2/FULL_ORIGINAL_INPUT_PLUS_STATIC20.csv',
    'facts': 'act_recovery_candidate_v2/EXISTING_FACTS.json',
    'summary': 'attribution_2024_chain_v2/SUMMARY.json',
    'B_book': 'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz',
    'B_daily': 'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz',
    'D_book': 'market_gross_admission_native_v1/full-long-v1/pair/D_GROSS10.json.gz',
    'D_daily': 'market_gross_admission_native_v1/full-long-v1/pair/daily.jsonl.gz',
    'B_actions': 'attribution_2024_chain_v2/No60_ALL_HISTORICAL_ENTRY_ACTIONS.json',
    'D_actions': 'attribution_2024_chain_v2/D_GROSS10_ALL_HISTORICAL_ENTRY_ACTIONS.json',
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
before = {k: sha(ROOT/p) for k,p in SOURCES.items()}
def save(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rows = list(csv.DictReader(open(ROOT/SOURCES['M_B'])))
ix = {r['day']: i for i,r in enumerate(rows)}
contexts = [('spring22','2022-04-01','2022-07-29'),('late22','2022-10-01','2022-12-30'),('late22_follow','2022-10-01','2023-03-31'),('false23','2023-07-20','2023-09-28'),('spring24','2024-02-01','2024-05-31'),('rally24','2024-09-02','2024-10-31'),('strong','2025-07-01','2026-06-30')]
ctx=[]
for name,lo,hi in contexts:
    rr=[r for r in rows if lo<=r['day']<=hi]
    anchors=[]
    for r in rr:
        if r['trigger20']!='True': continue
        i=ix[r['day']]; future=[z for z in rr if z['day']>r['day']]
        c,s=D(r['market']),D(r['L20'])
        def first(pred):
            z=next((z for z in future if pred(z)),None)
            return None if z is None else {'day':z['day'],'M':z['market'],'M_ratio_pct_from_anchor':(D(z['market'])/c-1)*100}
        anchors.append({'day':r['day'],'next_market_observation_day':rows[i+1]['day'] if i+1<len(rows) else None,'M':r['market'],'prior20high':r['H20'],'frozen_prior20low':r['L20'],'prior63high':r['prior_high63'],'breadth':r['breadth'],'BREAK63_same_CLOSE':r['breakout']=='True','first_B_le_06':first(lambda z:z['fast_on']=='False'),'first_M_le_frozen_S':first(lambda z:D(z['market'])<=s),'first_strict_later_BREAK63':first(lambda z:z['breakout']=='True')})
    ctx.append({'context':name,'lo':lo,'hi':hi,'observations':len(rr),'all_P20_dates':[r['day'] for r in rr if r['trigger20']=='True'],'all_P21_dates':[r['day'] for r in rr if r['trigger21']=='True'],'all_BREAK63_dates':[r['day'] for r in rr if r['breakout']=='True'],'all_P20_anchors':anchors,'warning':'Every anchor overlaps and is NOT an independent trade or account outcome. Fixed-support breaches/ratios are synthetic-price diagnosis only; ends are right-censored. next observation is market calendar only, not individual-stock executable proof.'})
save('SAVED_TRIGGER_CONTEXTS.json',ctx)

footprints={}
for key,arm in [('B','No60'),('D','D_GROSS10')]:
    with gzip.open(ROOT/SOURCES[key+'_book'],'rt') as f: book=json.load(f)
    with gzip.open(ROOT/SOURCES[key+'_daily'],'rt') as f: daily=[json.loads(x) for x in f]
    actions=json.load(open(ROOT/SOURCES[key+'_actions']))
    assert len([t for t in book['trades'] if t['side']=='buy'])==len(actions)
    out=[]
    for year in ['2022','2023','2024']:
        ds=[r for r in daily if r['at'].startswith(year)]
        ts=[r for r in book['trades'] if r['at'].startswith(year)]
        aa=[a for a in actions if a['at'].startswith(year)]
        start=D('1000000') if year=='2022' else D([r for r in daily if r['at'][:4]<year][-1]['nav'])
        sectors=[len({l['sector'] for l in r['layers'] if l['qty'] and l.get('sector')}) for r in ds]
        stocks=[sum(bool(q) for q in r['positions'].values()) for r in ds]
        gross=sum((D(t['gross_cny']) for t in ts if t['side']=='buy'),D(0))
        out.append({'year':year,'start_NAV':start,'end_NAV':ds[-1]['nav'],'wealth_change':D(ds[-1]['nav'])-start,'buy_count':sum(t['side']=='buy' for t in ts),'sell_count':sum(t['side']=='sell' for t in ts),'cumulative_buy_gross':gross,'cumulative_buy_gross_over_start_NAV':gross/start,'explicit_fees':sum((D(t['fees_cny']) for t in ts),D(0)),'mean_CLOSE_gross_pct':sum(D(r['inventory'])/D(r['nav'])*100 for r in ds)/len(ds),'max_held_stocks':max(stocks),'median_held_stocks':median(stocks),'max_held_sectors':max(sectors),'median_held_sectors':median(sectors),'buy_actions':{a:{'count':sum(x['action']==a for x in aa),'gross':sum((D(x['gross']) for x in aa if x['action']==a),D(0))} for a in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']}})
    trips=[]
    cps=[e for e in book['audit'] if e.get('kind')=='risk_checkpoint']
    for i,e in enumerate(cps):
        if e.get('event')!='pause': continue
        later=cps[i+1:]
        trips.append({'pause':e,'first_flat':next((z for z in later if z.get('flat')),None),'resume':next((z for z in later if z.get('event')=='resume'),None),'next_saved_CLOSE':later[0] if later else None})
    footprints[arm]={'years':out,'ACT_pause_footprints':trips,'note':'Gross sums count reused capital across repeated buys. CLOSE exposures are endpoint statistics, not intraday or standard average-NAV turnover. Sector counts do not measure return correlation.'}
save('NATIVE_ACTUAL_FOOTPRINTS.json',footprints)
facts=json.load(open(ROOT/SOURCES['facts']))
summary=json.load(open(ROOT/SOURCES['summary']))
save('REUSED_2024_ACTION_LOSS_AND_D_CYCLES.json',{'D_cycles':[x for x in facts['cycles'] if x['account']=='D_GROSS10'],'2024_actions':{a:{p:summary[a][p]['newfill_actions'] for p in ['pre924','post_oct8','year2024']} for a in summary}})
assert before=={k:sha(ROOT/p) for k,p in SOURCES.items()}
save('SOURCE_BINDING.json',{'sources':{k:{'path':p,'sha256':before[k]} for k,p in SOURCES.items()},'script_SHA256':sha(Path(__file__)),'new_accounts':0,'new_backtests':0,'new_price_loaders':0,'new_indicators':0,'scope':'Saved trigger facts preserved after priority changed to existing algorithm footprints; no recovery parameter expansion or simulation.'})
print(json.dumps({a:x['years'] for a,x in footprints.items()},default=str,ensure_ascii=False))
