"""Summarize stored trial-policy ledgers only; no additional economic paths."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import json,csv,collections,statistics
O=Path(__file__).resolve().parents[1];Z=D(0);rows=list(csv.DictReader((O/'full/unit-ledgers.csv').open()));led={(r['layer'],r['arm'],r['cost']):r for r in rows};ids=[r['layer'] for r in rows if r['arm']=='A' and r['cost']=='1'];assert len(ids)==1917 and len(led)==11502
sample=json.loads((O/'sample/VERIFICATION.json').read_text());full=json.loads((O/'full/VERIFICATION.json').read_text())
assert max(D(r['independent_nav_residual']) for r in rows)==0
pairs=[];summary={};groups=[];continuous=[]
def total(rr,k):return sum((D(r[k]) for r in rr),Z)
def writecsv(p,rr):
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
for cost in ['1','2']:
 arm={}
 for a in ['A','B','C']:
  rr=[led[l,a,cost] for l in ids];arm[a]=dict(net_pnl=total(rr,'net_pnl'),negative_count=sum(D(r['net_pnl'])<0 for r in rr),negative_pnl=-sum((min(Z,D(r['net_pnl'])) for r in rr),Z),mean_max_drawdown=statistics.mean(float(r['max_local_drawdown']) for r in rr),median_max_drawdown=statistics.median(float(r['max_local_drawdown']) for r in rr),worst_entry_return=min(D(r['minimum_entry_return']) for r in rr),holding_observations=sum(int(r['holding_observations']) for r in rr),inventory_yuan_observations=total(rr,'inventory_yuan_observations'),buy_fee=total(rr,'buy_fee'),sell_fees=total(rr,'sell_fees'),buy_slippage=total(rr,'buy_slippage'),sell_slippage=total(rr,'sell_slippage'),terminal_shares=sum(int(r['terminal_shares']) for r in rr),terminal_stock_events=sum(int(r['terminal_shares'])>0 for r in rr),terminal_claim=total(rr,'terminal_claim'),terminal_sale_receivable=total(rr,'terminal_sale_receivable'),switches=sum(bool(r['switch_at']) for r in rr),exit_reasons=dict(collections.Counter(r['exit_reason'] for r in rr)))
 comparisons={}
 for a,b,label in [('B','C','B_minus_C'),('B','A','B_minus_A')]:
  ds={l:D(led[l,a,cost]['net_pnl'])-D(led[l,b,cost]['net_pnl']) for l in ids};base_tail={l for l in ids if max(D(led[l,a,'1']['net_return']),D(led[l,b,'1']['net_return']))>=D('.30')};own_tail={l for l in ids if max(D(led[l,a,cost]['net_return']),D(led[l,b,cost]['net_return']))>=D('.30')}
  comp=dict(delta=sum(ds.values(),Z),base_common_tail_count=len(base_tail),base_common_tail_delta=sum((ds[l] for l in base_tail),Z),base_common_ordinary_delta=sum((ds[l] for l in ids if l not in base_tail),Z),own_cost_tail_count=len(own_tail),own_cost_tail_delta=sum((ds[l] for l in own_tail),Z),own_cost_ordinary_delta=sum((ds[l] for l in ids if l not in own_tail),Z),positive_delta_events=sum(v>0 for v in ds.values()),negative_delta_events=sum(v<0 for v in ds.values()),exit_request_changes=sum(led[l,a,cost]['exit_request']!=led[l,b,cost]['exit_request'] for l in ids),actual_sale_time_changes=sum(led[l,a,cost]['last_sell']!=led[l,b,cost]['last_sell'] for l in ids),higher_drawdown_events=sum(D(led[l,a,cost]['max_local_drawdown'])>D(led[l,b,cost]['max_local_drawdown']) for l in ids),lower_drawdown_events=sum(D(led[l,a,cost]['max_local_drawdown'])<D(led[l,b,cost]['max_local_drawdown']) for l in ids),holding_observation_difference=arm[a]['holding_observations']-arm[b]['holding_observations'],inventory_yuan_observation_difference=arm[a]['inventory_yuan_observations']-arm[b]['inventory_yuan_observations'])
  for keys,kind in [(('symbol',),'stock'),(('symbol','source_epoch'),'stock_I_epoch'),(('entry_date',),'entry_date')]:
   gg=collections.defaultdict(list)
   for l in ids:gg[tuple(led[l,a,cost][k] for k in keys)].append(l)
   for k,v in gg.items():groups.append(dict(cost=cost,comparison=label,group_type=kind,group_key='|'.join(k),events=len(v),delta=sum((ds[l] for l in v),Z)))
  stock=[g for g in groups if g['cost']==cost and g['comparison']==label and g['group_type']=='stock'];comp['top_positive_stocks']=sorted(stock,key=lambda x:-x['delta'])[:5];comp['top_negative_stocks']=sorted(stock,key=lambda x:x['delta'])[:5];comp['top5_negative_sum']=sum((g['delta'] for g in comp['top_negative_stocks']),Z);comp['top5_positive_sum']=sum((g['delta'] for g in comp['top_positive_stocks']),Z)
  for rank,(l,v) in enumerate(sorted(ds.items(),key=lambda x:-x[1]),1):continuous.append(dict(cost=cost,comparison=label,rank=rank,layer=l,symbol=led[l,a,cost]['symbol'],delta=v,base_tail=l in base_tail))
  comparisons[label]=comp
 summary[cost]=dict(arms=arm,comparisons=comparisons)
 for l in ids:
  r=led[l,'A',cost];q=dict(layer=l,symbol=r['symbol'],source_epoch=r['source_epoch'],entry_at=r['entry_at'],entry_date=r['entry_date'],cost=cost,initial_shares=r['initial_shares'],initial_cost=r['initial_cost'],original_K=r['original_K'],common_terminal_decision=r['common_terminal_decision'],common_terminal_reason=r['common_terminal_reason'],valuation_date=r['valuation_date'])
  for a in ['A','B','C']:
   for k in ['net_pnl','net_return','switch_at','exit_request','exit_reason','last_sell','max_local_drawdown','minimum_entry_return','holding_observations','inventory_yuan_observations','terminal_claim','terminal_shares']:q[a+'_'+k]=led[l,a,cost][k]
  q['B_minus_C']=D(q['B_net_pnl'])-D(q['C_net_pnl']);q['B_minus_A']=D(q['B_net_pnl'])-D(q['A_net_pnl']);q['base_BC_either_30pct']=max(D(led[l,'B','1']['net_return']),D(led[l,'C','1']['net_return']))>=D('.30');pairs.append(q)
writecsv(O/'paired-units.csv',pairs);writecsv(O/'group-contributions.csv',groups);writecsv(O/'continuous-contributions.csv',continuous);save=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str));save(O/'RESULTS.json',summary)
bc=summary['1']['comparisons']['B_minus_C'];ba=summary['1']['comparisons']['B_minus_A'];arms=summary['1']['arms'];cost2=summary['2'];bctwo=cost2['comparisons']['B_minus_C']
confirmed=[l for l in ids if led[l,'B','1']['switch_at']];unconfirmed=[l for l in ids if not led[l,'B','1']['switch_at']];assert len(confirmed)==876 and len(unconfirmed)==1041
assert all(D(led[l,'B','1']['net_pnl'])==D(led[l,'C','1']['net_pnl']) for l in confirmed)
pre_fast=[l for l in ids if led[l,'B','1']['exit_reason']=='fast_old_protection'];assert len(pre_fast)==493 and all(l in unconfirmed for l in pre_fast)
assert sum((D(led[l,'B','1']['net_pnl'])-D(led[l,'C','1']['net_pnl']) for l in pre_fast),Z)==bc['delta']
coverage=dict(stocks=len(set(r['symbol'] for r in pairs)),stock_epochs=len(set((r['symbol'],r['source_epoch']) for r in pairs)),entry_dates=len(set(r['entry_date'] for r in pairs)),BC_changed_request_stocks=len(set(led[l,'B','1']['symbol'] for l in ids if led[l,'B','1']['exit_request']!=led[l,'C','1']['exit_request'])),confirmed_BC_equal=876,preconfirmation_fast_exits_explain_all_BC=493)
now=datetime.now(timezone.utc);start=datetime(2026,10,29,17,1,50,tzinfo=timezone.utc);milestone=lambda f:datetime.fromtimestamp(f.stat().st_mtime,timezone.utc);proto=milestone(O/'PROTOCOL.txt');sm=milestone(O/'sample/VERIFICATION.json');fu=milestone(O/'full/VERIFICATION.json');timing=dict(start=start.isoformat(),protocol=proto.isoformat(),sample=sm.isoformat(),full=fu.isoformat(),finish=now.isoformat(),design_to_protocol_seconds=(proto-start).total_seconds(),protocol_to_sample_seconds=(sm-proto).total_seconds(),sample_to_full_seconds=(fu-sm).total_seconds(),full_to_report_seconds=(now-fu).total_seconds(),total_wall_seconds=(now-start).total_seconds(),sample_runtime_seconds=sample['runtime_seconds'],full_runtime_seconds=full['runtime_seconds'],total_economic_runtime_seconds=sample['runtime_seconds']+full['runtime_seconds'])
save(O/'TIMING.json',timing);save(O/'POST_VERIFICATION.json',dict(passed=True,mother=1917,ledgers=11502,pairs=3834,unique_keys=True,global_max_independent_nav_residual=str(max(D(r['independent_nav_residual']) for r in rows)),coverage=coverage,all_BC_delta_from_preconfirmation_fast_exits=True,confirmed_BC_equal_all=True,input_identity_unchanged=full['passed'],no_new_economic_paths=True))
report=f'''确认等待三臂局部政策检验完成：明确取舍，不晋升

范围/正确性
全部2352原实际试仓按股票×来源×原I段取首次，固定1917单元369股，排除435后续再试；1917不是事后晋升样本，其中原876晋升、1041未晋升。共有{coverage['entry_dates']}实际入场日期。身份在结果前冻结，全部11502账/3834配对明确完成，未知0。
A全程原TRIAL快保护；B自己的活仓首次原F/CP1高于原K后转纯结构；C入场即同结构。原已发生入口/股数/K与原ACT环境共同固定，不补资金、不追加、不再入。全独立完整订单费用对称，未用原拼单费用偏袒某臂。原N1事实现金残差0，1917实际首次买费核验，B全部1917×2个触发/不触发与原账逐一一致（只事后核验，真实未来晋升时间不参与决策）。样例5/30账与全量完全一致；全11502账最大独立NAV残差0。
旧线优先、已退出/待卖不恢复、新证据次观察切换及截止待卖不假成交的纯边界检查通过；截止未成交估值边界为合成核验，真实本轮末端股票均0。全量有1022次分红/100次送转账观察（含臂/成本重复），各自权息完整计入。准备不明无补0，新指标计算0。

完整净损益（万元，已含原首次买费/买滑点及后续卖费/卖滑点；重叠独立局部合计，非真实组合利润）
                    A全程快保护       B等待确认后结构     C入场即结构       B-C主差额      B-A辅助
base                {arms['A']['net_pnl']/10000:.4f}             {arms['B']['net_pnl']/10000:.4f}              {arms['C']['net_pnl']/10000:.4f}           {bc['delta']/10000:.4f}          {ba['delta']/10000:.4f}
cost2               {cost2['arms']['A']['net_pnl']/10000:.4f}             {cost2['arms']['B']['net_pnl']/10000:.4f}              {cost2['arms']['C']['net_pnl']/10000:.4f}           {bctwo['delta']/10000:.4f}          {cost2['comparisons']['B_minus_A']['delta']/10000:.4f}
cost2只压力入口之后卖费/滑点，原既成入口及K不改，不是整户全流程双成本。费用/滑点已在净额，不能再次扣减。三臂末端股息应收A/B/C为{arms['A']['terminal_claim']:.2f}/{arms['B']['terminal_claim']:.2f}/{arms['C']['terminal_claim']:.2f}元，全部计权益，支付未知不能冒充可用现金。

机制分叉：不能把B-A正值当确认等待胜出
C从1917个实际入口均结构持有，A无切换，B876次合法切换。876个实际等到确认者B与C终值全部相同：同初始股数，确认前没有实际卖出，之后都按同结构退出。
B-C全部差额来自493个B在确认前触旧保护退出的单元；B并未等到确认。这493个涉及{coverage['BC_changed_request_stocks']}股；与C有493次退出申请分叉、491次实际最后成交时点分叉。339单元B省损，152单元B较差，其余相同；少数更大代价超过多数小省损，与低胜率肥尾哲学一致，不能按次数判胜。
B-A有707次退出申请/实际最后成交时点分叉，净+53.66万元，说明停止快保护的动作可增加趋势参与；C比B更高，故这不能证明等待原确认的附加价值。所有单元完整配对保留。

尾部、普通、全部失败
base B-C：任一臂净回报>=30%的210个事后尾部分组差额{bc['base_common_tail_delta']/10000:.4f}万元，其余1707个普通组{bc['base_common_ordinary_delta']/10000:.4f}万元；相加为主差额。该30%是沿用评价尺度，不是数倍股捕获或选股规则。cost2同时保存base共同尾部分组和自身209个跨30%组（自身尾部差{bctwo['own_cost_tail_delta']/10000:.4f}、普通{bctwo['own_cost_ordinary_delta']/10000:.4f}万元），无阈值搜索，完整连续贡献另列。
B-A尾部差+67.23万元、普通−13.57万元；辅助改善同样有普通成本代价。
全部负净损益绝对额A/B/C为{arms['A']['negative_pnl']/10000:.4f}/{arms['B']['negative_pnl']/10000:.4f}/{arms['C']['negative_pnl']/10000:.4f}万元；负单元1145/1243/1142。B较C少负损耗7.8580万元，但也损失更多尾部；C的更高净利润不是没有普通错误。胜率未作为验收条件。

风险与资本占用
平均局部最大回撤A/B/C={arms['A']['mean_max_drawdown']:.2%}/{arms['B']['mean_max_drawdown']:.2%}/{arms['C']['mean_max_drawdown']:.2%}；B较C低回撤474单元、高9单元。最坏相对入场权益变动B−39.66%、C−48.59%（极值未必同单元）；逐单元最坏路径保留，不能拼成组合回撤。cost2相同取舍。
持仓收盘观察合计A/B/C=24991/49032/61282；市值×收盘观察合计2.3320/4.8605/6.0253亿元观察。B较C少12250个层观察和1.1648亿元观察占用；是局部暴露描述，不代表这笔钱在真实账户可以无阻力买到另一只股票，不做事后风险配平。

集中度与裁决
按369股票/1917原I结构/{coverage['entry_dates']}入场日期提供完整组账。B-C损失最大的三股688027/688525/300672合计约−11.64万元；这些仅事后归属，不用于改规则，也不要求删掉最大赢家仍盈利。正负贡献连续序列全部交付，不能挑C赢家反向选股。
事前标准对应“明确取舍”：等待政策B两费用均少净收益且损失肥尾更多，但省负损耗、降低回撤和资金占用有明确证据，因此不满足“无风险优势则直接否定”的停止充分条件；也没有证据支持把它晋升为增厚肥尾的主干。C同样未获可部署晋升。
本结果是等待+初期快保护的整套局部政策差，不是纯预测信息；差额发生在B尚未确认就退出者，仍不能把责任唯一分给F/CP1信息或个人成本门槛。未回答首次未获资、不同再入或有限资金账户，原I/E0和固定历史ACT只是本轮测量环境。当前存续/行业/市值池及已见历史开发偏差、日线开盘/容量/权息代理保留。完成即停，无新阈值/时间臂/组合回放或产品变更。

交付/耗时
PROTOCOL.txt、INPUT_IDENTITY.json、FROZEN_MOTHER.csv；sample/full unit-ledgers.csv、daily-equity.parquet、ledger-audit.jsonl.gz、policy-events.jsonl.gz、VERIFICATION.json；paired-units.csv、RESULTS.json、group-contributions.csv、continuous-contributions.csv、POST_VERIFICATION.json、TIMING.json。
总墙钟截至报告{timing['total_wall_seconds']:.1f}秒，设计阅读至合同{timing['design_to_protocol_seconds']:.1f}秒、合同至样例{timing['protocol_to_sample_seconds']:.1f}秒、样例至全量{timing['sample_to_full_seconds']:.1f}秒、全量至本报告核验汇总{timing['full_to_report_seconds']:.1f}秒；是可追溯墙钟里程碑，不冒充纯CPU分项。样例2.709秒，全量19.317秒，累计有效计算22.026秒（含加载与核验），低于300秒。一次成功全量，失败/规则修改0；无权限、连接或数据阻塞。\n'''
(O/'FINAL_REPORT.txt').write_text(report);save(O/'COMPLETION.json',dict(status='explicit_tradeoff_not_promoted',mother=1917,ledgers=11502,unknown=0,primary='B_minus_C',base_delta=bc['delta'],cost2_delta=bctwo['delta'],B_switches=876,BC_exit_request_changes=493,BC_actual_sale_time_changes=491,successful_full_runs=1,new_portfolio_paths=0,post_result_rule_changes=0,total_economic_runtime_seconds=timing['total_economic_runtime_seconds'],wall_seconds=timing['total_wall_seconds'],next_experiment_started=False))
print(json.dumps(dict(coverage=coverage,base_main=bc['delta'],stress_main=bctwo['delta'],ordinary=bc['base_common_ordinary_delta'],tail=bc['base_common_tail_delta'],timing=timing),ensure_ascii=False,default=str))
