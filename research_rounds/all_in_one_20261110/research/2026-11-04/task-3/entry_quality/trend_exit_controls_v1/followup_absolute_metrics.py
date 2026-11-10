"""Read-only presentation of the already independently audited 35 NAV rows."""
from pathlib import Path
import json,csv,hashlib
O=Path(__file__).resolve().parent;P=O/'followup_synthesis';P.mkdir(exist_ok=True)
r=json.loads((O/'NAV_SUMMARY.json').read_text())
names={'BASELINE':'原退出','EARLY_EMA20':'EMA20提前保护','EARLY_EMA60':'EMA60提前保护','EARLY_BOLL20_MID':'布林中轨/MA20提前保护','EARLY_BOLL20_LOWER':'布林下轨提前保护'}
periods={'full_2022_2024':'2022—24完整连续账户','bear2022':'2022熊市截段','year2023':'2023修复截段','year2024':'2024全年截段','from924':'2024-09-24起至年末','after1008':'2024-10-08收盘后至年末','strong':'2025-07-01—2026-06-30独立上涨窗口'}
cols=['arm','window','period','first_day','last_day','days','starting_NAV','ending_NAV','wealth_change','return_pct','max_local_drawdown_pct','max_since_account_start_drawdown_pct','mean_exposure_pct','trade_count','buy_count','sell_count','fees','gross_turnover']
with (P/'ABSOLUTE_WINDOW_MATRIX.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(r)
lines=['绝对账户及区间结果，全部来自已完成、独立核同的10条原生路径。',
'每格交易数是实际成交记录数，买/卖分别列出；同一卖单因送拆股份可卖时钟分两天成交计两笔，不是信号数或往返交易数。',
'财富收益=区间末NAV−区间前一市场收盘NAV；没有外部充提。收益率除以本臂自己的区间起点。NAV含现金、库存标记和已确认AR，非全部已实现现金。',
'子窗口不重新建账；最大局部回撤以该区间起点和后续NAV运行峰计，另列从完整账户起点运行峰的回撤。两种口径不能混用。','']
for k,label in periods.items():
 lines.extend([label,'臂 | 起始NAV元 | 期末NAV元 | 财富收益元 | 收益率% | 局部DD% | 账户起点DD% | 成交(买/卖) | 费用元'])
 for x in r:
  if x['period']!=k:continue
  nums=[f"{float(x[c]):,.2f}" for c in ['starting_NAV','ending_NAV','wealth_change','return_pct','max_local_drawdown_pct','max_since_account_start_drawdown_pct']]
  lines.append(' | '.join([names[x['arm']],*nums,f"{x['trade_count']}({x['buy_count']}/{x['sell_count']})",f"{float(x['fees']):,.2f}"]))
 lines.append('')
(P/'ABSOLUTE_WINDOW_TABLES.txt').write_text('\n'.join(lines)+'\n')
composition=[]
for arm in names:
 for window,pk in [('2022_2024','full_2022_2024'),('strong','strong')]:
  x=next(z for z in r if z['arm']==arm and z['period']==pk);mp=O/'runs'/arm/window/'RUN_METADATA.json';m=json.loads(mp.read_text())
  assert m['fresh_cash']==1000000 and m['no_checkpoint_import'] is True and m['yearly_reset'] is False
  composition.append(dict(arm=arm,window=window,initial_cash=m['fresh_cash'],start=m['start'],end=m['end'],native_closes=x['days'],ending_NAV=x['ending_NAV'],return_pct=x['return_pct'],max_drawdown_pct=x['max_local_drawdown_pct'],trade_count=x['trade_count'],buy_count=x['buy_count'],sell_count=x['sell_count'],no_original_intermediate_account_import=True,annual_cash_reset=False,metadata_sha256=hashlib.sha256(mp.read_bytes()).hexdigest()))
(P/'TEN_ACCOUNT_COMPOSITION.json').write_text(json.dumps(composition,ensure_ascii=False,indent=2)+'\n')
print('ABSOLUTE_PRESENTATION_COMPLETE',len(r),len(composition))
