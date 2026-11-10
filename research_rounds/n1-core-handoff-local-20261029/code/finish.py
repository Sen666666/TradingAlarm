"""Aggregate existing paired outputs only; never runs a policy or market path."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,json,gzip,collections,statistics
O=Path(__file__).resolve().parents[1];Z=D(0)
rows=list(csv.DictReader((O/'full/paired-layers.csv').open()))
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,default=str))
def summed(rr,k):return sum((D(x[k]) for x in rr),Z)
def ddstat(rr,a):
 vals=[float(x[a+'_max_drawdown']) for x in rr];mins=[float(x[a+'_min_return']) for x in rr]
 return dict(mean_drawdown=statistics.mean(vals),median_drawdown=statistics.median(vals),maximum_drawdown=max(vals),worst_return_from_promotion=min(mins))
summary={};groups=[]
for cost in ['1','2']:
 rr=[x for x in rows if x['cost']==cost];affected=[x for x in rr if x['action_diverged']=='True'];other=[x for x in rr if x['action_diverged']=='False'];assert len(rr)==1084 and len(affected)==470 and len(other)==614 and all(D(x['net_delta'])==0 for x in other)
 for keys,label in [(('symbol',),'stock'),(('symbol','source_epoch'),'stock_epoch'),(('promotion_date',),'promotion_date')]:
  gg=collections.defaultdict(list)
  for x in rr:gg[tuple(x[k] for k in keys)].append(x)
  for key,v in gg.items():groups.append(dict(cost=cost,group_type=label,group_key='|'.join(key),events=len(v),branched=sum(x['action_diverged']=='True' for x in v),A_pnl=summed(v,'A_post_pnl'),B_pnl=summed(v,'B_post_pnl'),delta=summed(v,'net_delta')))
 sg=[g for g in groups if g['cost']==cost and g['group_type']=='stock'];top=sorted(sg,key=lambda x:-x['delta'])[:5]
 allrisk={a:ddstat(rr,a) for a in ['A','B']};branchrisk={a:ddstat(affected,a) for a in ['A','B']}
 entry=dict(events=len(rr),affected=len(affected),unchanged=len(other),unknown=sum(x['status']!='paired' for x in rr),symbols=len(set(x['symbol'] for x in rr)),stock_epochs=len(set((x['symbol'],x['source_epoch']) for x in rr)),promotion_dates=len(set(x['promotion_date'] for x in rr)),affected_symbols=len(set(x['symbol'] for x in affected)),affected_stock_epochs=len(set((x['symbol'],x['source_epoch']) for x in affected)),affected_dates=len(set(x['promotion_date'] for x in affected)),net_delta=summed(rr,'net_delta'),A_post_pnl=summed(rr,'A_post_pnl'),B_post_pnl=summed(rr,'B_post_pnl'),A_fees=summed(rr,'A_fees'),B_fees=summed(rr,'B_fees'),A_slippage=summed(rr,'A_slippage'),B_slippage=summed(rr,'B_slippage'),initial_equity_sum=summed(rr,'initial_equity'),prior_gain_sum=summed(rr,'pre_promotion_lifecycle_gain'),actual_exit_times_changed=sum(x['A_last_sale']!=x['B_last_sale'] for x in rr),positive_delta_events=sum(D(x['net_delta'])>0 for x in rr),negative_delta_events=sum(D(x['net_delta'])<0 for x in rr),all_risk=allrisk,affected_risk=branchrisk,increased_dd_events=sum(D(x['B_max_drawdown'])>D(x['A_max_drawdown']) for x in rr),worse_minimum_events=sum(D(x['B_min_return'])<D(x['A_min_return']) for x in rr),extra_holding_observations=sum(int(x['B_holding_observations'])-int(x['A_holding_observations']) for x in rr),B_terminal_stock_events=sum(int(x['B_terminal_shares'])>0 for x in rr),A_terminal_claim=summed(rr,'A_terminal_claim'),B_terminal_claim=summed(rr,'B_terminal_claim'),top5_stock_delta=top,top5_share_of_net=sum((g['delta'] for g in top),Z)/summed(rr,'net_delta'))
 for a in ['A','B']:
  entry[a+'_negative_pnl_count']=sum(D(x[a+'_post_pnl'])<0 for x in rr);entry[a+'_negative_pnl_amount']=-sum((min(Z,D(x[a+'_post_pnl'])) for x in rr),Z)
 for flag in ['original_layer_30pct','post_either_30pct']:
  entry[flag]={v:dict(count=sum(x[flag]==v for x in rr),delta=sum((D(x['net_delta']) for x in rr if x[flag]==v),Z)) for v in ['True','False']}
 summary[cost]=entry
save(O/'RESULTS.json',summary)
with (O/'group-contributions.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(groups[0]));w.writeheader();w.writerows(groups)
with (O/'continuous-contributions.csv').open('w') as f:
 fields=['cost','rank','layer','symbol','promotion_date','net_delta','A_post_pnl','B_post_pnl','A_max_drawdown','B_max_drawdown'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for c in ['1','2']:
  for n,x in enumerate(sorted([r for r in rows if r['cost']==c],key=lambda r:-D(r['net_delta'])),1):w.writerow(dict(cost=c,rank=n,**{k:x[k] for k in fields if k not in ('rank','cost')}))
a=summary['1'];b=summary['2'];sver=json.loads((O/'sample/VERIFICATION.json').read_text());fver=json.loads((O/'full/VERIFICATION.json').read_text());now=datetime.now(timezone.utc);start=datetime(2026,10,29,16,38,32,tzinfo=timezone.utc)
proto=datetime.fromtimestamp((O/'PROTOCOL.txt').stat().st_mtime,timezone.utc);sample=datetime.fromtimestamp((O/'sample/VERIFICATION.json').stat().st_mtime,timezone.utc);full=datetime.fromtimestamp((O/'full/VERIFICATION.json').stat().st_mtime,timezone.utc)
wall=dict(start_utc=start.isoformat(),protocol_saved_utc=proto.isoformat(),sample_passed_utc=sample.isoformat(),full_passed_utc=full.isoformat(),finished_utc=now.isoformat(),start_to_protocol_seconds=(proto-start).total_seconds(),protocol_to_sample_seconds=(sample-proto).total_seconds(),sample_to_full_seconds=(full-sample).total_seconds(),full_to_report_seconds=(now-full).total_seconds(),total_wall_seconds=(now-start).total_seconds(),sample_runtime_seconds=sver['run_wall_seconds'],full_runtime_seconds=fver['run_wall_seconds'],known_economic_runtime_seconds=sver['run_wall_seconds']+fver['run_wall_seconds'],failed_loader_reserved_budget_seconds=15)
save(O/'TIMING.json',wall)
report=f'''N1晋升后动作语义诊断完成：有收益—风险取舍，不晋升

范围与核验
全1084晋升层、354股票、989股票×原I epoch、364晋升日期，均连接，未知0。470层继承复合保护相关退出发生不同实际退出时点，其余614层两臂精确同路。受影响覆盖{a['affected_symbols']}股/{a['affected_stock_epochs']}股票结构/{a['affected_dates']}日期；事件重复、重叠，不是1084独立行情。
A为事实层重建，不是重跑整户N1：实际买费/成本历史、层分红、实际卖出股数与净款、原拼单分摊独立对账；1084层最大残差0。172层原曾拼单，最低佣金保持原整单分摊；不同B卖单则完整独立计费。样例19（局部保护）/87（I退出）两成本与全量完全一致。旧保护先检顺序和晋升时点未改；新现金、买入、追加、再买及新账户反馈均0。
共同终点是原I失效/原N1下一ACT暂停/截止先到决策对应合法执行。固定历史ACT是条件干预，不能部署或外推账户收益。原I/E0作为本轮测量条件，不是可靠性已证。

主账（元，实际晋升股数尺度；所有费用已含）
                 A原保护晋升后净损益    B结构持有晋升后净损益      B-A
base             {a['A_post_pnl']:.2f}                 {a['B_post_pnl']:.2f}                  {a['net_delta']:.2f}
cost2            {b['A_post_pnl']:.2f}                 {b['B_post_pnl']:.2f}                  {b['net_delta']:.2f}
这些是重叠局部配对净额合计，不是一个账户利润/本金收益率。共同起点权益合计8752566.04元亦不是实际新增本金。晋升前已有生命周期收益合计1155269.99元单列，未算交接创造；历史买费两臂不再扣。cost2固定身份/时点/股数，仅压力后续卖费与滑点。
base卖费A/B为{a['A_fees']:.2f}/{a['B_fees']:.2f}元，卖出滑点{a['A_slippage']:.2f}/{a['B_slippage']:.2f}元，均已进净账；不能再扣一次。末端两臂均无股票，仍有股息应收A/B为8254.36/11631.47元，完整纳入；原支付字段未知继续作为权益，不假定可消费现金。

风险及全部失败代价
base负晋升后损益合计A {a['A_negative_pnl_amount']:.2f}→B {a['B_negative_pnl_amount']:.2f}元，增加{a['B_negative_pnl_amount']-a['A_negative_pnl_amount']:.2f}元；负事件{a['A_negative_pnl_count']}→{a['B_negative_pnl_count']}，不能只看负次数减少。cost2负损耗{b['A_negative_pnl_amount']:.2f}→{b['B_negative_pnl_amount']:.2f}元。
全1084层平均局部最大回撤15.63%→19.15%；受影响470层平均为{a['affected_risk']['A']['mean_drawdown']:.2%}→{a['affected_risk']['B']['mean_drawdown']:.2%}。445层回撤增加，389层晋升后最坏权益变动更差。最坏相对晋升权益变动由−30.36%到−46.44%；这两个极值不一定同一层，逐层配对在主表。
B额外持仓合计{a['extra_holding_observations']}个层×收盘观察，逐层记录同现金等待的最差权益差；不能跨日期加成账户回撤或可实现损失。正常右侧回吐是持有成本，不按峰值差估所谓误杀。

肥尾与集中度
沿固定原A全生命周期净回报>=30%组173层，两臂差额0；收益增量来自原A未成为该标签尾部的911层，不代表新增规则事前识别赢家。按晋升后任一臂净回报>=30%仅作事后分解：129层贡献增量343371.94元，其余955层合计−12644.00元；连续排名全保留，无阈值搜索。30%不等于数倍股捕获率。
base增量前三股票：长光688048 +101923.04、301308 +53923.68、688519 +44814.54元；前五合计占局部总净增量{a['top5_share_of_net']:.2%}。按股票/原epoch/晋升日期的完整组账已保存，不能把重复层当独立证据。集中符合肥尾特征，不自动判败，也不足称普适。

裁决与边界
两成本净增量均正，且470例实际暴露，不能直接否定解除继承复合保护的动作候选；但失败损耗、局部回撤及不利路径明确增加，按事前验收判为取舍，不晋升/不修改产品。它回答在原实际晋升队列与固定历史环境下的持有动作价值，不证明“F/CP1高于个人成本”是有增量的确认条件，也没有比较任意时间切换；更不能证明所有继承保护过紧。
没有重建P0/P1锁拒绝、修改ACT恢复、补容量或扩展止损参数。原复合保护取max的具体胜出来源仍未知，不命名快线误杀。下一阶段是否检验确认信息由主任务审查，本轮到此停止。

产物与耗时
PROTOCOL.txt、INPUT_IDENTITY.json；sample/full的paired-layers.csv、daily-paired-equity.parquet、fill-audit.json.gz、VERIFICATION.json；RESULTS.json、group-contributions.csv、continuous-contributions.csv、TIMING.json。
总墙钟截至报告{wall['total_wall_seconds']:.1f}秒：起点→合同{wall['start_to_protocol_seconds']:.1f}秒，合同→样例通过{wall['protocol_to_sample_seconds']:.1f}秒，样例→全量通过{wall['sample_to_full_seconds']:.1f}秒，全量→核验/汇总本报告{wall['full_to_report_seconds']:.1f}秒，包含阅读、设计、实现、工具与核验，不冒充纯计算分项。样例0.430秒，全量8.619秒，已知有效计算9.049秒；首次加载变量名错误未进经济循环，失败原件保留、规则不变，未实测其CPU秒数，预算保守预扣15秒，仍远低300秒。
无权限/连接阻塞，无账户访问/交易/产品变更。\n'''
(O/'FINAL_REPORT.txt').write_text(report)
save(O/'COMPLETION.json',dict(status='completed_with_tradeoff_not_promoted',mother=1084,paired_layers=1084,unknown=0,changed_exit_times=470,new_portfolio_paths=0,rule_changes_after_economics=0,product_changes=0,known_economic_runtime_seconds=wall['known_economic_runtime_seconds'],total_wall_seconds=wall['total_wall_seconds'],next_experiment_started=False))
print(json.dumps(dict(affected_risk=a['affected_risk'],affected_coverage=[a['affected_symbols'],a['affected_stock_epochs'],a['affected_dates']],delta=a['net_delta'],cost2_delta=b['net_delta'],top5_net_share=a['top5_share_of_net'],wall=wall),ensure_ascii=False,default=str))
