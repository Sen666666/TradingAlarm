"""Only saved original NAV high-water arithmetic, no strategy/account run."""
from pathlib import Path
from decimal import Decimal as D
import gzip,json,hashlib
O=Path(__file__).resolve().parent
P=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023/pair/daily.jsonl.gz')
C=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/risk_constraints/no60_continuation2023_finance/COMPARISON.json')
with gzip.open(P,'rt')as f:rows=list(map(json.loads,f))
assert len(rows)==484 and rows[0]['at'][:10]=='2022-01-04'and rows[-1]['at'][:10]=='2023-12-29'
assert D(rows[0]['nav'])==D(1000000)
peak=D(rows[0]['nav']);peak_at=rows[0]['at'];maximum=D(0);worst=None
for r in rows:
 nav=D(r['nav'])
 if nav>peak:peak=nav;peak_at=r['at']
 dd=1-nav/peak
 if dd>maximum:maximum=dd;worst={'peak_NAV':str(peak),'peak_at':peak_at,'trough_NAV':str(nav),'first_trough_at':r['at'],'maximum_CLOSE_drawdown_pct':str(100*dd),'signed_peak_to_trough_return_pct':str(-100*dd)}
report=json.loads(C.read_text())['PVR_SLOT1'];assert D(worst['maximum_CLOSE_drawdown_pct'])==D(report['cumulative_2022_2023_DD']['percent'])
returns=100*(D(rows[-1]['nav'])/D(rows[0]['nav'])-1)
a={'version':'Original PVR_SLOT1 with confirmed60 retained, shared upstream NoAccountBudget; not No60 or CORE permission ON','period':['2022-01-04','2023-12-29'],'original_saved_CLOSEs':len(rows),'formula':'H_t=max(original initial NAV, all observed NAV through t); DD_t=1-NAV_t/H_t; report max DD over full484 CLOSEs','independent_original_NAV_high_water_result':worst,'old_report_maximum_drawdown_field':report['cumulative_2022_2023_DD'],'annual_2023_return_pct_separate':report['year2023_return_pct'],'annual_2023_rebased_maximum_drawdown_pct_separate':report['year2023_DD']['percent'],'cumulative_return_pct_separate':str(returns),'why_two_metrics_numerically_equal_here':'Original initial1m is full-path peak; Sep22 trough is also unchanged year-end NAV after flat account. Drawdown and cumulative return calculated separately, equality is specific to this saved path.','trough_remained_unchanged_through_yearend':all(D(r['nav'])==D(worst['trough_NAV'])for r in rows if r['at']>=worst['first_trough_at']),'parent_chat_clarification':'Parent supplied actual dialogue: approx34 referred to original PVR two-year maximum drawdown; no additional chat provenance search requested/performed.','not_annual_return':True,'new_accounts':0,'new_backtests':0,'source_sha256':{str(P):hashlib.sha256(P.read_bytes()).hexdigest(),str(C):hashlib.sha256(C.read_bytes()).hexdigest()}}
(O/'ORIGINAL_PVR_TWO_YEAR_MAX_DRAWDOWN.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
(O/'READOUT.txt').write_text('原PVR两年最大收盘回撤独立原NAV核算\n\n版本：原PVR_SLOT1，保留confirmed60，非No60。484个原CLOSE，2022-01-04至2023-12-29。\n滚动历史高水位从原100万开始，逐日计算1-NAV/H并取最大：33.74420898330168915%。峰2022-01-04 NAV1000000；首次谷2023-09-22 NAV662557.9101669831085。\n这是最大收盘回撤指标；若写下跌符号为-33.7442%，约-34%。不是2023年度亏损；2023年度收益-7.3357678950%，自身年度重定基最大回撤20.1454257395%。\n已独立与原COMPARISON.PVR_SLOT1.cumulative_2022_2023_DD核同。累计收益另算为-33.7442089833%，恰好同数是因为起点即全路径最高值，9/22谷后空仓净值至年末不变；两个指标定义和计算没有混用。\n父线程已给出对话原文解释，本轮无需再查聊天来源。仅原NAV算术，0新账户/回测。\n')
sha={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='SHA256.json'};(O/'SHA256.json').write_text(json.dumps(sha,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'independent_drawdown':worst,'annual_return2023':report['year2023_return_pct'],'report_field_matches':True,'same_NAV_through_yearend':a['trough_remained_unchanged_through_yearend']},ensure_ascii=False))
