"""Compact complete tables and bounded interpretation; read-only evidence."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import csv,json
import analyze_phase as A
O=A.O
def get(rows,p,g,k):return next(r for r in rows if r['policy']==p and r['grain']==g and r['period']==k)
def num(x):return f'{float(x):,.2f}'
def main():
 periods=A.read(O/'ALL_PERIODS.json');bench=A.read(O/'BENCHMARK_ALL_PERIODS.json');funnel=A.read(O/'FUNNEL_ALL_PERIODS.json');legs=A.read(O/'HS300_ALL_LEGS.json')
 bystock=A.read(O/'PHASE_STOCK_WEALTH_BRIDGES.json');reentry=A.read(O/'REENTRY_PRIOR_CAMPAIGN_SPLIT.json');bb=A.read(O/'BENCHMARK_RESULT_BINDING.json')
 assert A.read(O/'PHASE_AGGREGATION_GATE.json')['passed']and A.read(O/'FUNNEL_GATE.json')['passed']and A.read(O/'STOCK_PHASE_GATE.json')['passed']
 combined=[]
 for r in periods:
  f=get(funnel,r['policy'],r['grain'],r['period']);combined.append(dict(r,signal_clock_counts=f['counts'],actual_priority=f['priority']))
 combined.extend(bench);A.save('COMPLETE_COMPARISON.json',combined)
 flat=[]
 for r in combined:
  flat.append({k:r.get(k)for k in ['policy','grain','period','start','end','days','begin_NAV','end_NAV','net_PnL','return_pct','HS300_return_pct','HS300_left_close_reference_day',
   'mean_lag_exposure_pct','mean_close_exposure_pct','mean_close_cash_pct','ACT_paused_OPEN_days','first_actual_buy','actual_buy_cash','actual_fees','fees','maximum_drawdown_within_period_pct']})
 with(O/'COMPLETE_COMPARISON.csv').open('w')as f:
  w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 # Entire strong path, no selected winner-only interval. Existing finance bridge
 # source, not another economic run or the2022/23 phase market partition.
 strong={}
 for policy,file in [('NO60','NO60_STRONG_DAILY.json'),('PVR','PVR_STRONG_DAILY.json')]:
  rr=A.read(A.FIN/file);assert len(rr)==242
  strong[policy]=dict(period=[rr[0]['day'],rr[-1]['day']],days=242,net_PnL=sum((D(x['wealth_change'])for x in rr),D(0)),
   return_pct=(D(rr[-1]['NAV_end'])/D(rr[0]['NAV_begin'])-1)*100,mean_close_exposure_pct=sum((D(x['exposure_pct'])for x in rr),D(0))/len(rr),
   actual_buy_cash=sum((D(x['actual_buy_cash'])for x in rr),D(0)),actual_fees=sum((D(x['actual_fees'])for x in rr),D(0)),
   passive_or_simple_filter_counterfactual_not_computed=True)
 A.save('COMPLETE_STRONG_WINDOW_CONTROL.json',strong)
 lines=['2022→2023市场阶段、实际参与和绝对亏损：完整只读归因','',
 'No60两年仍亏254,573.04元。相对旧PVR改善不等于已经解决绝对亏损。本分析先固定全部24个月、8季度、484日，再以真HS300单阈值10%划分全部5个事后段；没有新策略运行或源码修改。',
 '市场标签使用未来确认，只用于诊断，永不进入实时信号。HS300为不可交易价格指数；第一月/季度/首段左锚Dec31，另存Jan4close对齐值；ETF账户首执行Jan5OPEN，不把Jan4已发生变动当策略机会。','',
 '完整5段（原生策略收益 / HS300价格背景 / ETF已执行日线proxy）：',
 '段 | 日期 | HS300 | No60 | 旧PVR | ETF MA63 | No60平均前收盘暴露 | ACT暂停OPEN']
 for leg in legs:
  k=leg['id'];n=get(periods,'NO60','HS300_zigzag10_leg',k);p=get(periods,'PVR','HS300_zigzag10_leg',k);m=get(bench,'benchmark_MA63_90','HS300_zigzag10_leg',k)
  lines.append(f"{k} | {n['start']}..{n['end']} | {num(n['HS300_return_pct'])}% | {num(n['return_pct'])}% | {num(p['return_pct'])}% | {num(m['return_pct'])}% | {num(n['mean_lag_exposure_pct'])}% | {n['ACT_paused_OPEN_days']}/{n['days']}")
 lines+=['',
 '1. 下跌损失大，而恢复慢。L01长期下跌中平均前收盘暴露75.53%，70/74个OPEN仍active，损失22.02万；其末才被ACT清空。L02完整反弹18.81%期间，34/45个OPEN暂停，原stock/industry联合Q通过的4505个raw fresh CP1里3079个mobile事件被ACT挡住。June20才恢复首买，平均前收盘暴露20.01%，到该段末已89.99%。随后L03下跌时又平均暴露81.09%，零ACT暂停，亏8.37万。不能把下跌幅当可做空收益，也不能把这组时序当替换ACT后的反事实利润。',
 '2. 仓位高也可能在反弹中亏。L04 HS300上涨19.74%，No60仍亏2.77万，平均前收盘暴露88.72%，ACT全59日on。原raw CP14959、联合Q通过4647，并非无信号；14395个计划角色事件有212个按信号日归属的真实获资成交、4个预留零fill、45个mobile被同股core预留压住。其余OPEN拒绝中有现金/原保留线、行业financial attempt失效和probe/行业风险等；并集不能当独占原因相加。角色计划包含每日重复core，不能叫14395个独立错失机会。',
 '3. L04不能只归罪存量仓。完整期内股票财富桥为：期初持有65股合计−2685.55元；全新立足83股−2986.65；此前买过、期初flat后本段重入64股−22008.86。再按最近一次已真实平仓的旧campaign区分，57只旧campaign负贡献股的本段财富变化−23417.74，7只此前非负股+1408.88。它们是期内实际财富分解，不是删掉重入能省下的资金或利润。',
 '4. 反例必须一起保留。L02原生实际86笔买入、其中新立足65股贡献3.78万，证明当前规则下确有能同时通过信号/单位/资金的机会，但不代表所有raw CP1都可买。L05指数下降18.33%时No60仍赚3.47万：期初存量股−2.04万，新立足+3.19万，重入+2.32万。101只上回campaign为负的重入股本段反而+2.90万，不能直接禁重入或把指数下降全部过滤。2023Q2指数−5.15%而No60+8.88%；完整强窗No60+126.33%也说明没有仓位不能替代趋势参与。','',
 '同日可执行边界：实际成交见NO60_ACTUAL_EXECUTABLE_FILLS.json，保存原signal日/CP1/role/floor/PVR优先、冻结预算/股数上限、实际预留/成交。每笔原target及dated证券最小单位/步长已重核；是原生已模拟获资/成交的下界，不是事后底买顶卖组合。ACT关闭时即使raw信号与整手算术可能存在，原合同也不准入；本分析没有把ACT删掉再预留。只有close size拒绝或OPEN并集理由的记录不被升级成“移门后可成交”的证明。','',
 '机会成本基准：pressure agent独立建立的ETF MA63单边long-only为−4.51%、DD10.14%，平均暴露26.39%，不是全现金；ETF持有为−27.04%。最新独审PASS_WITH_SCOPE已绑定，仍为raw-open日线proxy，缺dated halt/limit，所以execution_verified=false。ETF以冻结portfolio协议15bp单边estimated friction/min5、无额外slip，与股票native多项fee+slip不是同合同；不做暴露线性缩放，不将差额全归某个市场门，不把省费用再投入当所得。','',
 '已支持：绝对损失有明确阶段规模；ACT迟恢复与反弹期重复试错是两个不同大问题；原60门去除没有解决它们。未支持：只加仓/只减仓、禁止所有重入或一见大盘跌就停能构成改进。未验证：任何新策略机制的因果收益、真实开盘可得性、1.2m真实规模/H股/PIT/OOS。下一步应针对这些相反案例提出同一套可证伪机制，再逻辑审查和有限验证，不从一个盈利阶段倒推过滤器。','',
 '复核文件：COMPLETE_COMPARISON.csv/json完整24mo/8q/5leg；ALL_PERIODS/HS300_PIVOTS保全部边界和确认时钟；FUNNEL_ALL_PERIODS与FUNNEL_GATE保全链；ALL_PHASE_STOCK_WEALTH及桥保所有股票；REENTRY_PRIOR_CAMPAIGN_SPLIT保全部分组；SOURCE/GATE和benchmark最新独审绑定保实际范围。净值变化按原生逐日差分，已与独审finance日桥核同；0新No60账户事件、0策略修改。']
 (O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
 A.save('CURRENT_STATUS.json',dict(status='complete_read_only_attribution_awaiting_independent_phase_review',account_days=484,calendar_months=24,calendar_quarters=8,HS300_all_zigzag10_legs=5,
  source_strategy_runs=0,new_strategy_rules=0,all_phase_labels_retrospective_only=True,benchmark_latest_review_status=bb['latest_independent_review_status']['status'],
  boundary_scope='actual native proxy fills only; no alternative route/cash allocation or perfect hindsight trading PnL',strong_control_complete242_days=True))
 A.SRC[str(Path(__file__))]=A.sha(__file__);A.save('PUBLISH_SOURCE_SHA256.json',A.SRC)
 paths=[p for p in O.rglob('*')if p.is_file()and p.name!='ARTIFACT_SHA256.json'];A.save('ARTIFACT_SHA256.json',{str(p.relative_to(O)):A.sha(p)for p in sorted(paths)})
 print('FULL_PHASE_READOUT_PUBLISHED',len(combined),'rows')
if __name__=='__main__':main()
