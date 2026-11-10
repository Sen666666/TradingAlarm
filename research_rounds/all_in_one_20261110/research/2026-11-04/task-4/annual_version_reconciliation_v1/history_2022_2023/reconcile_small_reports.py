"""Read saved small financial reports only; no account, model, feature or NAV replay."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
RR=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
TASK=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
paths={
 'old_2022':RR/'2022-normal-reference-20261031/QUICK_RESULTS.json',
 'pvr_2022':RR/'pvr-slot1-native-readiness-20261101/COMPARISON.json',
 'old_2023':RR/'recovery-2023-readiness-20261101/COMPARISON_2023.json',
 'pvr_2023':RR/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/COMPARISON_2023.json',
 'no60_2023':TASK/'risk_constraints/no60_continuation2023_finance/COMPARISON.json',
 'current_No60':ROOT/'new_price_trend_v1/analysis/reference_long_PERIODS.json',
}
data={k:json.loads(p.read_text())for k,p in paths.items()}
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rows=[]
def row(version,year,begin,end,ret,dd,source,pointer,cum='',cumdd='',note=''):
 rows.append(dict(version=version,year=year,first_observation='2022-01-04'if year==2022 else'2023-01-03',
                  last_observation=f'{year}-12-30'if year==2022 else'2023-12-29',
                  beginning_NAV=begin,ending_NAV=end,annual_return_pct=ret,annual_max_CLOSE_DD_pct=dd,
                  cumulative_from_original1m_return_pct=cum,cumulative_max_CLOSE_DD_pct=cumdd,
                  source=str(paths[source]),json_pointer=pointer,note=note))
for i,r in enumerate(data['old_2022']):
 a=r['annual'];row(r['reference'],2022,a['start_NAV'],a['end_NAV'],a['return_pct'],a['DD_pct'],'old_2022',f'/{i}/annual',note='Published H1 normal reference, separate new1m 2022 path')
r=data['pvr_2022'][0]['PVR_SLOT1'];end=D(1000000)*(1+D(r['return_pct'])/100)
row('PVR_SLOT1',2022,'1000000',end,r['return_pct'],r['global_DD']['percent'],'pvr_2022','/0/PVR_SLOT1',note='End NAV algebra from published exact return, independently stated in FINANCIAL_RESULTS.txt:53')
r=data['current_No60']['2022'];row('PVR_NO_CONFIRMED60 / current long_OFF',2022,r['begin_NAV'],r['end_NAV'],r['return_pct'],r['max_CLOSE_DD_pct'],'current_No60','/2022',note='Current continuous2022–2024 original No60; its Dec30 NAV exactly matches old own2023 starting NAV')
for i,r in enumerate(data['old_2023']):
 row(r['policy'],2023,r['opening_NAV'],r['ending_NAV'],r['year2023_return_pct'],r['year2023_DD']['percent'],'old_2023',f'/{i}',
     r['cumulative_from_2022_return_pct'],r['cumulative_from_2022_DD']['percent'],'Own2022 state continued, annual denominator ownDec30 NAV')
for name in ['PVR_SLOT1','PVR_NO_CONFIRMED60']:
 r=data['no60_2023'][name]
 row(name,2023,r['initial_2023_own_Dec30_NAV'],r['end_NAV'],r['year2023_return_pct'],r['year2023_DD']['percent'],'no60_2023',f'/{name}',
     r['original_1m_cumulative_return_pct'],r['cumulative_2022_2023_DD']['percent'],'Own2022 continuation; cumulative original1m is a separate two-year measure')
save('VERSION_AND_WINDOW_TABLE.json',rows)
with(OUT/'VERSION_AND_WINDOW_TABLE.csv').open('w',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
cash=[]
for name in ['PVR_SLOT1','PVR_NO_CONFIRMED60']:
 r=data['no60_2023'][name];m=r['cumulative_money_split'];trade=D(m['realized_trading_net']);div=D(m['recognized_dividends'])
 cash.append(dict(version=name,window='original2022 initial1m through2023-12-29, cumulative; NOT one calendar year',
                  cumulative_realized_trading_net=trade,trade_net_pct_original1m=100*trade/D(1000000),
                  recognized_dividend_equity=div,dividend_pct_original1m=100*div/D(1000000),
                  cumulative_total_NAV_return_pct=r['original_1m_cumulative_return_pct'],
                  ending_NAV=r['end_NAV'],calculated_nav_difference=D(1000000)+trade+div-D(r['end_NAV']),
                  source=str(paths['no60_2023']),json_pointer=f'/{name}/cumulative_money_split',
                  prior_conversation_quote_origin='NOT_ESTABLISHED_FROM_REPORT_SEARCH'))
save('TWO_YEAR_CASH_VS_NAV_NOT_ANNUAL.json',cash)
excerpts=[
 (RR/'2022-normal-reference-20261031/RESULTS.txt',[(1,9)]),
 (RR/'recovery-2023-readiness-20261101/RUN_RESULTS.txt',[(4,8)]),
 (RR/'pvr-slot1-native-readiness-20261101/FINANCIAL_RESULTS.txt',[(1,7),(52,54)]),
 (RR/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/RESULTS_2023.txt',[(1,7),(12,17)]),
 (TASK/'risk_constraints/NO60_2023_CONTINUATION_READOUT.md',[(1,22)]),
 (TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/READOUT.txt',[(26,32)]),
]
out=[]
for p,ranges in excerpts:
 lines=p.read_text().splitlines();out.extend([str(p),'SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest()])
 for a,z in ranges:out.extend(f'{i}: {lines[i-1]}'for i in range(a,z+1))
 out.append('')
(OUT/'ORIGINAL_REPORT_EXCERPTS.txt').write_text('\n'.join(out))
search=[]
for p in [RR/'2022-normal-reference-20261031',RR/'recovery-2023-readiness-20261101',TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS']:
 for f in p.rglob('*'):
  if f.is_file()and f.suffix.lower()in['.txt','.md','.json']and f.stat().st_size<180000 and any(t in f.name.lower()for t in ['summary','read','report','result','metric','comparison']):
   search.append(dict(path=str(f),bytes=f.stat().st_size))
save('SEARCH_SCOPE.json',dict(small_report_candidates=search,
    finding='No reviewed report establishes 2022 annual−26% or2023 annual−34%. Several distinct annual/cumulative/realized-cash measures are documented.',
    original_quote_attribution='UNRESOLVED: matching approximate numbers do not prove source of earlier conversation',
    no_new_backtest_or_model=True,no_large_features_used_as_evidence=True))
sources=list(paths.values())+[x[0]for x in excerpts]
save('SOURCE_SHA256.json',[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in dict.fromkeys(sources)])
print(json.dumps(dict(rows=len(rows),cash=cash,small_report_candidates=len(search)),ensure_ascii=False,default=str))
