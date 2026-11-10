"""Saved original JSON NAV/quantity/cash prefix comparisons; no strategy calls."""
from pathlib import Path
from decimal import Decimal as D
import gzip,json,hashlib
O=Path(__file__).resolve().parent;ROOT=O.parent;W=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');R=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
paths={'current_No60':ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair','old_No60_2022':W/'pvr_pool_feasibility/runs/2022/pair','old_No60_2023_continuation':W/'pvr_pool_feasibility/continuation2023/run-2023/pair','old_PVR_2022':R/'pvr-slot1-native-readiness-20261101/runs/2022/pair','old_PVR_2023_continuation':R/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023/pair'}
books={k:load(p/'B.json.gz')for k,p in paths.items()};daily={k:load(p/'daily.jsonl.gz',True)for k,p in paths.items()};cur=daily['current_No60'];checks={};table=[]
for key in ['old_No60_2022','old_No60_2023_continuation']:
 old=daily[key];cut=old[-1]['at'];subset=[r for r in cur if r['at']<=cut];tx=[t for t in books['current_No60']['trades']if t['at']<=cut]
 checks[key]={'original_path':str(paths[key]),'first_at':old[0]['at'],'last_at':cut,'old_CLOSEs':len(old),'current_prefix_CLOSEs':len(subset),'daily_complete_object_exact':old==subset,'actual_trade_complete_object_prefix_exact':books[key]['trades']==tx}
for key in ['current_No60','old_PVR_2023_continuation']:
 byday={r['at'][:10]:r for r in daily[key]};first=daily[key][0];year22=byday['2022-12-30'];year23=byday['2023-12-29'];initial=D(1000000)
 for year,start,end in [(2022,first,year22),(2023,year22,year23)]:
  table.append({'version':key,'year':year,'start_at':start['at'],'end_at':end['at'],'start_NAV':start['nav'],'end_NAV':end['nav'],'year_NAV_change':D(end['nav'])-D(start['nav']),'year_return_pct':100*(D(end['nav'])/D(start['nav'])-1),'cumulative_from_initial1m_return_pct':100*(D(end['nav'])/initial-1),'end_available_cash':end['available'],'end_inventory':end['inventory'],'end_dividend_receivable':end['dividend_receivable'],'cumulative_fees':end['fees_cny'],'annual_reset':False})
comp=json.loads(bind(W/'risk_constraints/no60_continuation2023_finance/COMPARISON.json').read_text());matching=[]
for key in ['PVR_SLOT1','PVR_NO_CONFIRMED60']:
 r=comp[key];split=r['cumulative_money_split'];net=D(split['realized_trading_net']);div=D(split['recognized_dividends']);ending=D(r['end_NAV']);assert abs(D(1000000)+net+div-ending)<D('.000001')
 matching.append({'source_version':key,'window':'2022-01-04 through 2023-12-29, continuous initial1m','realized_trading_net':net,'trading_net_over_original1m_pct':100*net/D(1000000),'recognized_dividend':div,'end_NAV':ending,'NAV_cumulative_return_pct':r['original_1m_cumulative_return_pct'],'year2023_return_pct':r['year2023_return_pct'],'year2023_DD_pct':r['year2023_DD']['percent'],'cumulative_2022_2023_DD_pct':r['cumulative_2022_2023_DD']['percent'],'not_proven_original_chat_quote_source':True})
result={'prefix_checks':checks,'NAV_year_table':table,'old_report_cumulative_NAV_and_trading_net_near_old_quote':matching,'source_trace_scope':'Read saved original NAV books and old reports, not infer a prior chat quote provenance from numeric proximity.','new_accounts':0,'new_backtests':0}
save('ORIGINAL_NAV_VERSION_COMPARISON.json',result);save('SOURCE_SHA256.json',sources)
print(json.dumps(result,ensure_ascii=False,default=str))
