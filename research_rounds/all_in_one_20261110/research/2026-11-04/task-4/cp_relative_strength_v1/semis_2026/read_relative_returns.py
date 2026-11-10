"""Read frozen prices/CP/ledger; compute only fixed relative log-return descriptors.

No model/account/strategy imports. No download, fill simulation or future-return labels.
"""
from pathlib import Path
import csv, gzip, hashlib, json, math
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
U = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
ORIG = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
BM = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
START, END = '2026-01-01', '2026-06-30'
SECTOR, BENCH = 'URFI881121', 'USHI1B0300'
HORIZONS = (5, 20, 60)  # Frozen by parent before data evaluation; no optimisation.
sha = {}

def bind(p):
    p = Path(p)
    if str(p) not in sha:
        sha[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p

def js(p): return json.loads(bind(p).read_text())
def parq(p):
    f = pd.read_parquet(bind(p))
    assert f.index.is_unique and f.index.is_monotonic_increasing
    return f
def dump(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
def clean(x):
    if x is None or (isinstance(x, (float, np.floating)) and not math.isfinite(x)): return None
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, (pd.Timestamp,)): return x.isoformat()
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (tuple,list)): return [clean(v) for v in x]
    return x
def write_rows(name, rows):
    rows = clean(rows)
    dump(name+'.json', rows)
    if rows:
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
            for r in rows:
                w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})

metadata = js(ORIG/'metadata.json')
pool = {sid:m for sid,m in metadata.items() if m.get('sector_id')==SECTOR}
assert len(pool)==126
stock_manifest = {r['symbol']:r for r in js(U/'STOCK_MANIFEST.json')}
industry_manifest = {r['series']:r for r in js(U/'INDUSTRY_MANIFEST.json')}
input_manifest = js(ORIG/'input-manifest.json')
input_records = {r['series_id']:r for r in input_manifest['series']}
im = industry_manifest[SECTOR]
ind = parq(im['refs']['CP1_input'])
market = pd.read_csv(bind(BM/'canonical'/f'{BENCH}.csv'),parse_dates=['date']).set_index('date')
assert market.index.is_unique and market.index.is_monotonic_increasing
calendar = market.index
days = calendar[(calendar>=START)&(calendar<=END)]
all25 = js(ROOT/'upside_state_v1/examples_semis/ALL25_SAVED_ROLE_HOLDING_CHAINS.json')
bought = {r['sid'] for r in all25}
assert len(all25)==25 and len(bought)==18 and bought <= set(pool)
opps, funding = {}, {}
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair'
for filename,target in [('opportunities.jsonl.gz',opps),('funding.jsonl.gz',funding)]:
    with gzip.open(bind(pair/filename),'rt') as f:
        for line in f:
            r=json.loads(line);sid=r.get('sid');d=r.get('day',r.get('at','')[:10])
            if sid in pool and START<=d<=END: target.setdefault((sid,d),[]).append(r)

def value(frame, d, col):
    if d is None or d not in frame.index: return None
    x=frame.at[d,col]
    return None if pd.isna(x) else x

def lr(frame, current, base, seg=False):
    a,b=value(frame,current,'close'),value(frame,base,'close')
    if a is None or b is None or a<=0 or b<=0: return None, 'missing_or_nonpositive_endpoint'
    if seg:
        s=frame.loc[base:current,'segment_id']
        if s.isna().any() or s.nunique()!=1: return None, 'source_segment_crossing_or_unknown'
    return math.log(float(a)/float(b)), None

rows=[];coverage=[];canonical=[];cp_mismatches=[];facts_input_mismatches=[]
for sid,meta in pool.items():
    sm=stock_manifest[sid]
    q=parq(sm['refs']['CP1_input']); cp=parq(sm['refs']['CP1']); facts=parq(sm['refs']['facts'])
    # Source equivalence check only; never recompute original CP or signal.
    idx=q.index.intersection(facts.index)
    mism=int((q.loc[idx,'close'] != facts.loc[idx,'close']).sum())
    if mism: facts_input_mismatches.append({'sid':sid,'different_close_rows':mism})
    assert mism==0
    receipts={r['confirmed_day']:r for r in js(sm['refs']['receipts']) if START<=r['confirmed_day']<=END}
    cp_days={d.strftime('%Y-%m-%d') for d in cp.loc[START:END].index[cp.loc[START:END,'receipt'].eq(True)]}
    if cp_days != set(receipts):cp_mismatches.append({'sid':sid,'cached_only':sorted(cp_days-set(receipts)),'canonical_only':sorted(set(receipts)-cp_days)})
    assert cp_days==set(receipts)
    for d in days:
        ds=d.strftime('%Y-%m-%d'); oi=opps.get((sid,ds),[]); fu=funding.get((sid,ds),[])
        r={'sid':sid,'name':meta['name'],'sector_id_static':SECTOR,'day':ds,'in_original_bought18':sid in bought,
           'stock_close_CP_input':value(q,d,'close'),'stock_raw_close_facts':value(facts,d,'raw_close'),
           'stock_factor_facts':value(facts,d,'factor'),'industry_close':value(ind,d,'close'),'market_close':value(market,d,'close'),
           'CP_cached_receipt':bool(value(cp,d,'receipt')) if value(cp,d,'receipt') is not None else None,
           'CP_canonical_receipt_id':receipts.get(ds,{}).get('receipt_id'),
           'original_CP_candidate':value(cp,d,'candidate'),'original_CP_delta_frontier':value(cp,d,'delta_frontier'),
           'original_i_target':value(facts,d,'i_target'),'original_i_buy':value(facts,d,'i_buy'),
           'original_e0_target':value(facts,d,'e0_target'),
           'original_opportunity_count':len(oi),'original_core_Q':None,'original_mobile_Q':None,
           'original_opportunity_roles':None,'original_opportunity_barriers':None,
           'original_funding_results':None}
        if len(oi)==1:
            o=oi[0];r.update(original_core_Q=o.get('core_Q'),original_mobile_Q=o.get('mobile_Q'),original_opportunity_roles=o.get('roles'),original_opportunity_barriers=o.get('barriers'))
        if fu:r['original_funding_results']=[{'role':x.get('role'),'result':x.get('result')} for x in fu]
        pos=calendar.get_loc(d)
        for n in HORIZONS:
            base=calendar[pos-n] if pos>=n else None
            r[f'base_day_{n}']=base.strftime('%Y-%m-%d') if base is not None else None
            sr,se=lr(q,d,base,True);ir,ie=lr(ind,d,base,True);mr,me=lr(market,d,base)
            r.update({f'stock_logreturn_{n}':sr,f'industry_logreturn_{n}':ir,f'market_logreturn_{n}':mr,
                      f'RS_stock_{n}':sr-ir if sr is not None and ir is not None else None,
                      f'RS_ind_{n}':ir-mr if ir is not None and mr is not None else None,
                      f'missing_reason_{n}':';'.join(f'{k}:{v}' for k,v in [('stock',se),('industry',ie),('market',me)] if v) or None})
        rows.append(r)
        if ds in receipts:
            z=dict(r);z['original_canonical_receipt']=receipts[ds];z['original_opportunities']=oi;z['original_funding']=fu;canonical.append(z)
    sub=[r for r in rows[-len(days):]]
    coverage.append({'sid':sid,'name':meta['name'],'in_original_bought18':sid in bought,'source_first':q.index.min().strftime('%Y-%m-%d') if len(q) else None,'source_last':q.index.max().strftime('%Y-%m-%d') if len(q) else None,
                     'H1_stock_endpoint_rows':sum(r['stock_close_CP_input'] is not None for r in sub),'H1_market_days':len(days),'H1_canonical_CP':len(receipts),
                     **{f'H1_RS_stock{n}_available':sum(r[f'RS_stock_{n}'] is not None for r in sub) for n in HORIZONS},
                     **{f'H1_CP_RS_stock{n}_available':sum(r[f'RS_stock_{n}'] is not None for r in sub if r['CP_canonical_receipt_id']) for n in HORIZONS},
                     'original_refs':sm['refs']})
lookup={(r['sid'],r['day']):r for r in rows}
signals=[]
for x in all25:
    ds=x['signal_at'][:10];r=lookup.get((x['sid'],ds))
    signals.append({'layer':x['layer'],'sid':x['sid'],'name':x['name'],'role':x['role'],'original_signal_at':x['signal_at'],'original_opened':x['opened'],
                    'original_buy_receipt_daily_proxy':x['actual_buy'],'RS_at_original_signal':r,
                    'scope':'Original bought layer signal descriptor; no counterfactual performance or execution claim.'})

write_rows('ALL_STATIC126_DAILY_RS',rows)
write_rows('ALL_CANONICAL_CP_H1_RS',canonical)
write_rows('ALL_BOUGHT18_DAILY_RS',[r for r in rows if r['in_original_bought18']])
write_rows('ALL25_ORIGINAL_SIGNAL_RS',signals)
write_rows('SOURCE_COVERAGE_BY_STOCK',coverage)
examples=[r for r in canonical if r['sid'] in ['300666.SZ','301611.SZ','603061.SH','688146.SH']]
write_rows('REQUESTED_FOUR_ALL_CP_NOT_SELECTED_BY_OUTCOME',examples)
bridge=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/a-industry-index-bridge.csv')
bridge_records=list(csv.DictReader(bind(bridge).open()))
source_info={'sector':{'series_id':SECTOR,'name':'半导体','bridge_record':next(r for r in bridge_records if r['index_symbol']==SECTOR),
                       'original_price_manifest_record':input_records[SECTOR],'original_CP_manifest_record':im},
             'market':{'series_id':BENCH,'local_name':'沪深300','local_publication_record':next(r for r in js(BM/'protocol.json')['symbols'] if r['symbol']==BENCH),
                       'checkpoint':js(BM/'checkpoints'/f'{BENCH}.json'),'server_names_source':str(bind(BM/'server-names.json'))},
             'original_stock_price_manifest_records':[input_records[sid] for sid in sorted(pool)],
             'static_pool':{'scope_date':input_manifest['scope_date'],'research_basis':input_manifest['research_basis'],'size':len(pool),'metadata':str(ORIG/'metadata.json')},
             'actual_basis':'Original No60 strong_OFF daily-bar-proxy ledger; no broker execution or historical quote timestamp proof.'}
dump('SOURCE_IDENTITY_AND_CONVENTIONS.json',source_info)
summary={'window':[START,END],'market_days':len(days),'static_pool_size':len(pool),'bought_stocks':len(bought),'bought_layers':len(all25),'daily_rows':len(rows),
         'canonical_CP_count':len(canonical),'stocks_with_CP':len({r['sid'] for r in canonical}),'bought18_CP_count':sum(r['in_original_bought18'] for r in canonical),
         'CP_cached_canonical_day_differences':cp_mismatches,'facts_vs_CP_input_close_differences':facts_input_mismatches,
         'RS20_CP_positive':sum(r['RS_stock_20'] is not None and r['RS_stock_20']>0 for r in canonical),
         'RS20_CP_negative':sum(r['RS_stock_20'] is not None and r['RS_stock_20']<0 for r in canonical),
         'RS20_CP_missing':sum(r['RS_stock_20'] is None for r in canonical),
         'fixed_horizons':list(HORIZONS),'RS_units':'Natural log return differences, dimensionless; x100 is log-percentage-points, not arithmetic excess return.',
         'no_model_account_order_or_future_return_computed':True}
dump('SUMMARY.json',summary)
bind(__file__);dump('SOURCE_SHA256.json',sha)
print(json.dumps(summary,ensure_ascii=False,indent=2))
