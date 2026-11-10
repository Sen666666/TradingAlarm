"""Dated, immutable comparison exports; no account rerun or strategy changes."""
from pathlib import Path
from decimal import Decimal as D
import json,sys,hashlib
R=Path(sys.argv[1]);dt=sys.argv[2];rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
x=next(x for x in rd(R/'DAILY_BASELINE_DIFFERENCES.json') if x['day']==dt);decomp=next(x for x in rd(R/'DAILY_PATH_ACCOUNTING_DECOMPOSITION.json') if x['day']==dt);cp=R/('checkpoint_'+dt.replace('-',''));assert cp.exists();assert rd(cp/'DAY_LEDGER.json')[-1]['day']==dt
nofills=[x for x in rd(cp/'NO_FILLS.json')];name='CHECKPOINT_'+dt.replace('-','')+'_COMPARISON';j=R/(name+'.json');m=R/(name+'.md');assert not j.exists() and not m.exists()
out=dict(checkpoint_day=dt,comparison=x,accounting_decomposition=decomp,no_fills_through_checkpoint=nofills,source_hashes={str(p):sha(p) for p in [Path(__file__),cp/'DAY_LEDGER.json',cp/'NO_FILLS.json',R/'DAILY_BASELINE_DIFFERENCES.json',R/'DAILY_PATH_ACCOUNTING_DECOMPOSITION.json']},not_live_execution_rule=True,not_return_lower_bound=True)
j.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
text=f'''# {dt} 一字bar压力场景对照

- 压力账户NAV：{D(x['scenario_NAV']):,.2f}元；原基线：{D(x['baseline_NAV']):,.2f}元；差额：{D(x['difference_NAV']):+,.2f}元。
- 现金：{D(x['scenario_cash']):,.2f}元；市值：{D(x['scenario_market_value']):,.2f}元；持仓{x['scenario_stocks']}只；仓位{D(x['scenario_weight_pct']):.4f}%。
- 累计无成交{len(nofills)}笔。被挡种子股票整条路径会计差额{D(decomp['blocked_seed_symbol_pnl_difference']):+,.2f}元；其他股票路径差额{D(decomp['other_symbol_pnl_difference']):+,.2f}元。两项相加等于全户NAV差额，但不是独立因果归因。

## 当时不可知的边界

全天raw O=H=L=C只能收盘后判断，本场景仅在完整OPEN意图和预留完成后事后施加不成交条件，不能回到alpha、排序或开盘计划。未成交买款在同批结束前不可再分给后排订单；卖单未成交不得虚构现金。

9月24日后的市场快速普涨，未来速度、覆盖面、行业持续性和逐笔成交可达性均不可提前知道。本场景未重建历史ST/涨跌停价/竞价队列，不证明一字bar真实必然不能成交，也不是收益下界。原费率及raw OPEN ±5bp成本代理保持不变，不作为真实成交价格证据。
'''
m.write_text(text)
print(text)
