"""Read cached as-of H1 rows and frozen snapshot JSON. No strategy events."""
from c_selector import *
import numpy as np, pandas as pd

FACT=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/industry-evidence-ranking-readonly-v1')
STATIC=FACT.parent/'g-s-static-capital-competition-v1'
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')

def main():
    guard();assert read(HERE/'SYNTHETIC_RESULTS.json')['passed']
    idx=read(BASE/'ARTIFACT_SHA256.json');assert all(sha(BASE/n)==v for n,v in idx.items())
    assert sha(H1)==read(FACT/'SOURCE_SHA256.json')[str(H1)]
    z=np.load(H1,allow_pickle=False);di={str(v)[:10]:i for i,v in enumerate(z['dates'])};ci={str(v):i for i,v in enumerate(z['symbols'])}
    sectors=sorted(s for s in ci if s.startswith('URFI'))
    def evidence(day,at):
        return dict(day=day,known_at=at,industry_H1={s:float(z['score'][di[day],ci[s]]) if np.isfinite(z['score'][di[day],ci[s]]) else None for s in sectors},
            source_path=str(H1),source_sha256=sha(H1),source_row=di[day],industry_domain=90,formula='original_industry_H1_cached_not_recomputed')
    for k in ('2025_26','2022'):
        x=read(BASE/'inputs'/(k+'.json'));x['industry_evidence']=evidence(x['snapshot']['at'][:10],x['snapshot']['at'])
        x['original_input_sha256']=sha(BASE/'inputs'/(k+'.json'));transform(x['snapshot'],x['B_demands'],x['industry_evidence'])
        save(HERE/'inputs'/(k+'.json'),x)
    # Only the already-audited market opportunity lists. Never infer a GS account.
    raw=pd.read_parquet(FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet')
    sources={str(H1):sha(H1),str(FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet'):sha(FACT/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet')}
    coverage={}
    for day in ('2026-04-30','2026-05-07'):
        f=STATIC/(day+'-ALL_SECTOR_FRESH_COMPETITION.json');assert sha(f)==read(STATIC/'PACKAGE_SHA256.json')[f.name];sources[str(f)]=sha(f)
        stocks=read(f);daily=raw[raw['day'].astype(str).str[:10]==day].copy();assert len(daily)==90
        ev=evidence(day,day+' 15:10:00+08:00');ordering=sorted(sectors,key=lambda s:(-round(ev['industry_H1'][s],12),s));ir={s:i+1 for i,s in enumerate(ordering)}
        rows=[]
        for rec in daily.to_dict('records'):
            sec=rec['sector'];items=[s for s in stocks if s['details']['sector']==sec]
            rows.append(dict(day=day,sector=sec,industry=rec['industry'],industry_H1=rec['industry_H1_score'],industry_H1_rank=ir[sec],
                market_F1_permit=bool(rec['F1_permit']),market_F1_mature=bool(rec['F1_mature']),
                all_stage_canonical_CP1_Q=int(rec['canonical_CP1_Q']),frozen_market_expansion_list_count=len(items),
                source_support_purposes=sorted({s['details']['fresh_use'] for s in items}),
                first_original_B_stock_rank=min((s['competition_rank'] for s in items),default=None),
                GS_account_ACT_holdings_receipts='UNKNOWN',joint_capacity='NOT_COMPUTED_missing_full_fee_and_quantity_specs_and_GS_account'))
        rows.sort(key=lambda r:r['industry_H1_rank']);save(HERE/'market-2026'/(day+'-INDUSTRIES.json'),rows)
        ordered=sorted(stocks,key=lambda s:(ir[s['details']['sector']],s['competition_rank']))
        out=[]
        for i,s in enumerate(ordered):
            d=s['details'];out.append(dict(day=day,sid=s['sid'],name=d['name'],sector=d['sector'],C_market_only_rank=i+1,
                industry_H1_rank=ir[d['sector']],original_B_rank=s['competition_rank'],original_H1_rank=s['original_H1_rank'],
                PVR=s['PVR'],PVR_ready=s['PVR_ready'],market_only_purpose=d['fresh_use'],
                canonical_receipt_id=d['fresh_receipt_id'],minimum_quantity=d.get('minimum_quantity'),close_buy_proxy=d.get('close_buy_proxy'),
                fresh_raw_floor=d.get('fresh_raw_floor'),source_minimum_fee=d.get('minimum_fee'),
                full_fee_schedule_available='fees' in d,full_dated_quantity_rule_available='quantity' in d,
                actual_GS_eligibility='UNKNOWN',amount=None))
        save(HERE/'market-2026'/(day+'-STOCK_ORDER.json'),out)
        coverage[day]=dict(original_industries=90,frozen_market_expansion_stocks=len(stocks),with_full_fee_schedule=sum(r['full_fee_schedule_available'] for r in out),
            with_full_dated_quantity_rule=sum(r['full_dated_quantity_rule_available'] for r in out),empty_account_fixture_executed=False,
            numerical_capacity_computed=False,reason='source stores minimum fee/minimum quantity but not full fee/dated quantity contract; stop at ranks and counts',
            actual_GS_full_state='not available; no original account imported')
    save(HERE/'market-2026/COVERAGE.json',coverage)
    save(HERE/'AUTHORIZATION_AND_FREEZE.json',dict(scope='synthetic + Jan6/Jul3 static C joint target projections; Apr30/May7 market-only rankings; no account events',
        parent='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',policy='C_INDUSTRY_FIRST',contract_sha256=CONTRACT_SHA,
        frozen_code={p.name:sha(p) for p in sorted(HERE.glob('*.py'))},source_B_sha256=BASE_SHA,source_joint_sha256=JOINT_SHA,
        inputs={k:sha(HERE/'inputs'/(k+'.json')) for k in ('2025_26','2022')},market_only_sources=sources,
        frozen_B_artifact_sha256=sha(BASE/'ARTIFACT_SHA256.json'),original_B_files_unchanged=len(idx),financial_events=0,new_indicators=0,
        numerical_2026_fixture='NOT_EXECUTED; if later enabled must be common B/C 1m cash / zero positions / zero old orders, not a historical continuation'))
    print('C_INPUT_AND_MARKET_LISTS_FROZEN',coverage,flush=True)

if __name__=='__main__':main()
