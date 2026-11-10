"""Read original saved fields only; no Account, loader, strategy or new prices."""
from pathlib import Path
from decimal import Decimal as D
import collections, gzip, hashlib, json

O = Path(__file__).resolve().parent
T = O.parent
RR = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
MR = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def read(p):
    with gzip.open(p, 'rt') as f:
        return json.load(f)
def lines(p):
    with gzip.open(p, 'rt') as f:
        return [json.loads(x) for x in f]
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def saved_risk(r):
    return D(str(r['pool_probe'][1])) + D(str(r['pool_confirmed'][1]))
def view(r):
    return {k:r[k] for k in ('at','nav','inventory','available','pool_probe','pool_confirmed','shared_loss','on','counts')} | dict(
        sum_saved_nominal=str(saved_risk(r)),
        sum_saved_nominal_pct_NAV=str(saved_risk(r)/D(r['nav'])*100),
        inventory_pct_NAV=str(D(r['inventory'])/D(r['nav'])*100))
files = {
    'No60_book':T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz',
    'No60_daily':T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz',
    'D_daily':T/'market_gross_admission_native_v1/full-long-v1/pair/daily.jsonl.gz',
    'J':RR/'case-stage-ledger-20261031/v3/joint_v3.py',
    'model':RR/'case-stage-ledger-20261031/budget_v3/model.py',
    'no_account_adapter':RR/'account-risk-ablation-20261031/adapter.py',
    'no_account_model':RR/'account-risk-ablation-20261031/model_without_account_check.py',
    'no_account_route':RR/'account-risk-ablation-20261031/route_without_account_check.py',
    'no60_component':T/'pvr_pool_feasibility/component.py',
    'no60_native':T/'pvr_pool_feasibility/native_adapter.py',
    'gross_guard':T/'market_gross_admission_native_v1/gross_adapter.py',
    'lot_risk':MR/'lot-risk-allocation-20261029/code/study.py',
    'ACT':MR/'actual-risk-recovery-20261027/code/risk_policy.py',
    'ledger':MR/'rs-h1-execution-20261025/code/sector_account.py',
    'layers':MR/'probe-pyramid-pilot-20261029/code/pilot.py',
    'existing_initial_risk':T/'risk_constraints/entry_initial_risk_scale_v1/THIN_ENTRIES.json',
}
source={k:dict(path=str(p),sha256=sha(p)) for k,p in files.items()}
b=read(files['No60_book']); B=lines(files['No60_daily']); DD=lines(files['D_daily'])
out=dict(scope='SAVED_FIELDS_ARITHMETIC_AND_READ_ONLY_SOURCE_NO_NEW_VALUATION', new_accounts=0,new_backtests=0,source=source)
for label,rows in [('No60',B),('D_GROSS10',DD)]:
    pick=['2022-01-05','2022-01-17','2022-01-20','2022-04-20','2023-07-20','2024-06-11','2024-09-30','2024-10-08','2024-11-29','2024-12-23']
    result={'fixed_saved_CLOSEs':[view(next(r for r in rows if r['at'].startswith(day)))for day in pick]}
    result['saved_CLOSE_count']=len(rows)
    result['saved_total_nominal_over_3pct_CLOSEs']=sum(saved_risk(r)>D('.03')*D(r['nav'])for r in rows)
    result['saved_confirmed_capital_over_60pct_CLOSEs']=sum(D(str(r['pool_confirmed'][0]))>D('.6')*D(r['nav'])for r in rows)
    result['year_max_saved_nominal_pct_NAV']={year:view(max([r for r in rows if r['at'].startswith(year)],key=lambda r:saved_risk(r)/D(r['nav'])))for year in ('2022','2023','2024')}
    result['first_saved_shared_loss_ge_20000']=view(next(r for r in rows if D(str(r['shared_loss']))>=D(20000)))
    out[label]=result
first=[r for r in b['journal']if r['kind']=='real_buy_fill'and r['at'].startswith('2022-01-05')]
out['No60_first_execution_OPEN']=dict(count=len(first),role_pool_counts=[dict(role=k[0],pool=k[1],fills=v)for k,v in collections.Counter((r['role'],r['pool'])for r in first).items()],actual_fill_journal=first)
dec=next(r for r in b['decisions']if r['at'].startswith('2022-01-04'))
out['No60_first_decision']=dict(at=dec['at'],NAV=dec['nav'],intents=len(dec['intents']),two_fixed_stock_intents=[r for r in dec['intents']if r['sid']in('002246.SZ','600664.SH')])
sale=next(r for r in b['audit']if r['kind']=='fill'and isinstance(r.get('receipt'),dict)and r['receipt'].get('side')=='sell')
settlement=next(r for r in b['audit']if r['kind']=='settle'and r['settlement']['settlement_id']==sale['receipt']['settlement_id'])
out['first_sale_cash_timing']=dict(fill=sale,settle=settlement,interpretation='Actual saved sale receipt and due/settle same OPEN. Native opening settles after sells and before new routes; no causal allocation of fungible cash to individual buys asserted.')
entries=json.loads(files['existing_initial_risk'].read_text())
out['two_initial_1m_examples']=[x for x in entries if x['population']=='2022_2023_at_2023_cutoff'and x['layer']in(1,4)]
out['math_example_only']=dict(initial_NAV='1000000',hypotheses=['44 confirmed mobile entries across 11 sectors, 4 per sector; each gross 2% of current NAV, price-to-floor distance10%; fees/gaps omitted for arithmetic only','Each sector gross8% and nominal0.8%, under confirmed level1 capital10% and sector nominal1%; stock gross2%; total gross88% and nominal8.8%; no global3% predicate in current No60','If three successive complete risk losses of8.8% and full legal replenishment occur, terminal ratio .912^3; not actual trade path or strategy outcome'],one_round_nominal='88000',three_round_wealth=str(D(1000000)*D('.912')**3),three_round_loss_pct=str((1-D('.912')**3)*100))
(O/'SAVED_RISK_FACTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
(O/'SOURCE_BINDING.json').write_text(json.dumps(dict(new_accounts=0,new_backtests=0,sources=source,script_sha256=sha(__file__),output_sha256=sha(O/'SAVED_RISK_FACTS.json')),ensure_ascii=False,indent=2)+'\n')
print('SAVED_FIELDS_ONLY',sha(O/'SAVED_RISK_FACTS.json'))
