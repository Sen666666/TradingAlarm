"""Archive measured evidence and a bounded verdict; no new replay."""
from pathlib import Path
import json,gzip,time,datetime,hashlib
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-local-finite-capital-20261029')
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
started=time.monotonic();budget=read(O/'COMPUTE_BUDGET.json');assert budget['used_seconds']<295
r=read(O/'MECHANISM_RESULTS.json');assert r['passed'];summ=pd.read_csv(O/'summary.csv');trace=rows(O/'admission-trace.jsonl.gz');out=[];costs=[];objs={};cs={v:pd.read_csv(O/v/'analysis/campaigns.csv',dtype=str) for v in ['baseline','local']}
for v in ['baseline','local']:
 for sc in ['base','cost2','delay1']:
    obj=read(O/v/'accounts-v2'/f'I__S0_{sc}.json');objs[(v,sc)]=obj
    slip=sum((abs(D(x['price'])-D(x['raw_open']))*x['receipt']['shares'] for x in obj['audit_log'] if x['kind']=='fill'),D(0));fees=sum((D(x['fees_cny']) for x in obj['fills']),D(0));costs.append(dict(policy=v,scenario=sc,fees=fees,slippage=slip,total_explicit_and_slippage=fees+slip))
for c in trace:
 sc=c['account'].rsplit('_',1)[-1];obj=objs[('local',sc)];fm={}
 for x in obj['audit_log']:
    if x['kind']=='fill' and x['receipt']['side']=='buy':fm.setdefault(x['order_id'],[]).append(x['receipt'])
 for rec in c['recommendations']:
    gained=sorted(set(rec['local'])-set(rec['original']));lost=sorted(set(rec['original'])-set(rec['local']))
    for sid in gained:
        ic=next((x for x in c['entry_contracts'] if x['sid']==sid),None);ff=fm.get(ic['order_id'],[]) if ic else [];first=ff[0]['at'] if ff else None;cc=cs['local'];cc=cc[cc.scenario.eq(sc)&cc.symbol.eq(sid)&cc.first_buy_at.eq(first)] if first else cc.iloc[:0]
        ss=[s for k in rec['priority_change_indices'] for s in c['priority_changes'][k]['promotions'] if s['chosen']==sid];head=ss[0]['head'] if ss else None
        out.append(dict(scenario=sc,decision_at=c['at'],promoted=sid,local_anchor_head=head,shadow_selected_lost='|'.join(lost),actual_order_id=ic['order_id'] if ic else None,reserved=ic is not None,buy_fills=len(ff),first_fill=first,gross_and_fees_used=sum((D(x['gross_cny'])+D(x['fees_cny']) for x in ff),D(0)),first_order_cycle_pnl=cc.iloc[0].net_pnl if len(cc) else None,terminal_event_pnl_includes_later_retries=True,rejection_reason='|'.join(reason for s,reason in c['rejected'] if s==sid),head_h1=ss[0]['h1_head'] if ss else None,chosen_h1=ss[0]['h1_chosen'] if ss else None,head_pvr=ss[0]['pvr_head'] if ss else None,chosen_pvr=ss[0]['pvr_chosen'] if ss else None))
out=pd.DataFrame(out).drop_duplicates(['scenario','decision_at','promoted','actual_order_id']);out.to_csv(O/'capital-displacement-orders.csv',index=False);pd.DataFrame(costs).to_csv(O/'actual-costs.csv',index=False)
funding={}
for sc,g in out.groupby('scenario'):
 funding[sc]=dict(recommendation_new_candidates=len(g),reserved_orders=int(g.reserved.sum()),orders_with_buy_fill=int(g.buy_fills.gt(0).sum()),funded_dates=int(g[g.buy_fills.gt(0)].decision_at.nunique()),gross_and_fees_used=sum(g.gross_and_fees_used,D(0)))
timeline=[]
for v in ['baseline','local']:
 for sc in ['base','cost2']:
    cp={x['at'][:10]:x for x in objs[(v,sc)]['audit_log'] if x['kind']=='risk_checkpoint'}
    for day in ['2026-07-10','2026-07-13','2026-07-14','2026-07-17','2026-07-20']:
        x=cp[day];timeline.append(dict(policy=v,scenario=sc,date=day,**{k:x[k] for k in ['nav','peak','episode_drawdown','on','event']}))
pd.DataFrame(timeline).to_csv(O/'july-risk-chain.csv',index=False)
d=rows(O/'local/accounts-v2/decisions.jsonl.gz');dm={sc:{x['at']:x for x in d if x['account']=='I__S0_'+sc} for sc in ['base','cost2']};cc=[dict(at=at,base_accepted=x['accepted'],cost2_accepted=dm['cost2'][at]['accepted']) for at,x in dm['base'].items() if at[:10]>='2025-06-27' and set(x['accepted'])!=set(dm['cost2'][at]['accepted'])];save(O/'COST_PATH_FIRST_DIFFERENCES.json',dict(first_acceptance_set_changes_after_common_June_resume=cc[:10],funding_funnel=funding))
freeze=read(O/'FREEZE.json');impl=read(O/'IMPLEMENTATION_FREEZE.json');now=datetime.datetime.now(datetime.timezone.utc);timing=dict(adaptation_window_seconds=(datetime.datetime.fromisoformat(impl['recorded_at'])-datetime.datetime.fromisoformat(freeze['recorded_at'])).total_seconds(),freeze_to_archive_wall_seconds=(now-datetime.datetime.fromisoformat(freeze['recorded_at'])).total_seconds(),note='Wall-clock implementation windows include communication and overlap with baseline/sample/full calculation. Pure development seconds were not separately instrumented; do not subtract overlapping calculation time.')
report='''本轮裁决：确已改变实际资金去向，但成本压力下整户增益反向，暂不晋升局部PVR规则；保留局部信息线索，不扩大邻域、不改天数或生产策略。

1. 正确性与范围
固定407科技/11行业、2023-12-29决策至2026-10-27，100万元ACTIVE，原I/E0、H1行业优先、6股3行业、仓位与ACT20_BREAK不变。仅waiting队列采用已批准H1锚点邻域移除递推；continuing/部分成交不改。正常/双成本/延迟一合法执行事件共6条完整路径，外加1条技术短段前缀；无额外策略、起点、阈值或经济重跑。
原基线三路径2043日账、全部决策和完整账户对象/138、136、116成交均精确复现。样例原4941行业日顺序逐一匹配，最早6个潜在首位变化样例保留，单条技术路径物理截断至2024-08-30后与完整路径日账、成交和决策前缀完全一致。两臂资金、费用、整股/T+1、保护与权益由原引擎独立审计，最大NAV差0。原缓存52个缺失快照沿原序；三情景运行累计156次缺失值触及亦沿原序，无新增缺失行或填值。原输入与适配冻结哈希均未变。

2. 整户结果（净收益% / 最大回撤%；差额按同初始100万元）
正常：原ACT 298.4160 / 26.8736；局部330.3935 / 22.9963；净差+319774.80元。
双成本：原ACT 295.8373 / 26.8905；局部285.0092 / 26.8372；净差−108281.01元。
延迟：原ACT 66.4258 / 36.4817；局部68.9879 / 36.7677；净差+25621.71元。
胜率非验收门槛；三情景仍未达到20%回撤研究目标。正常收益和回撤改善不能掩盖双成本反向与延迟回撤恶化。

3. 真正发生了什么
正常/双成本各147个收盘队列变化，但仅3个收盘的同状态纯接纳推荐改变。初始行业第一名未必改变，递推后的行业第二名也影响每行业2席，所以首个实际分叉就是2023-12-29：2024-01-02局部买智微智能001339/传音688036，原ACT买信维300136/淳中603516；其余初始持仓相同。两新增订单实际含费占资298504.48元。正常两新仓首次周期合计+10909.64，两个被替代初始周期合计−30997.81；这只是不同退出日的首次周期算术，未包含资金退出后的再投，不当作完整机会成本净效应。
2024-09-27局部推荐301285替代同状态002947，正常获资129684.03元、首次周期+531.20。2025-10-28推荐688692代600602，两者都被原预算/数量约束拒绝，实际没有新资金。故正常/双成本各4个推荐新候选、4?项推荐记录中3个订单真正成交，只有2个获资日期；具体精确计数见funding_funnel与capital-displacement-orders.csv。
延迟初始两替换虽获预留但原日单均未实际成交；首次真实成交分叉在2024-02-19，新易盛300502来自2/08替代中际300308的订单。不能把初始未成交快照算盈利或亏损，亦不能把以后同E0事件的重试收益归给这张空单。
最终实际接纳日期不同为正常22、双成本9、延迟55，远多于3次同状态推荐变化；其中包括后续仓位、资金、整股与ACT路径传导。capital-displacement-orders.csv按真实订单去重，first_order_cycle_pnl与event_final_pnl（含后续重试）分开，后者不可按推荐行重复加总。

4. 肥尾、失败与被挤出机会
正常原尾部已平周期利润345.01万元→386.75万元，但普通周期−46.60万元→−56.36万元；全部亏损周期损失62.41万元→76.03万元，亏损周期41→42。不是减少失败成本的改进，而是本路径尾部新增超过普通损耗。
统一因果E0事件归簇（允许同事件多次真实试错，全部成本计入）后，正常配对任一臂30%尾部差+418497.03、普通差−98722.23，合计+319774.80；双成本尾部−78030.32、普通−30250.69；延迟尾部+92710.19、普通−67088.48。归簇定义与单持仓周期定义不同，不能混用数值。30%仅事后评价，不能代替抓住数倍行情。
正常原本尾部事件在局部的净贡献保留89.996%，所以“新政策尾部总利润更多”不等于“原赢家全部保住”。连续贡献分布与逐事件明细已保存。
正常逐资金事件会计分为：仅新政策获资事件+638968.01、仅原ACT获资事件的差额−389663.31、两臂都获资事件+70470.10，精确合计319774.80。这些是实际账簿分组，后续新机会多数由路径传导产生，不能全称PVR预测增益。最大逐股正差603115约+47.86万，已超过总增益；负差300903约−32.55万、300814约−11.87万，结果稀疏、集中，不删大赢家改判。

5. 为何成本压力会反向
正常局部在2026-07-13的ACT阶段回撤22.6401%已暂停，原ACT19.7366%尚持；原ACT7/17才暂停。7/13局部仅领先36261.30元，7/14卖出后反而落后约36.23万，7/20最后领先319774.80元。早停这一条实际路径最终有利，并不证明普遍早停优势。双成本局部7/13阶段回撤19.7631%，两臂均7/17才暂停。
不是单纯把固定成交表多扣费用：局部正常72周期、双成本67周期；同规则在原费用扰动后，10/31/2025开始新增接纳股票集合已经不同（正常接纳601360，双成本无新接纳），以后持仓构成与ACT峰值/触发日不同。额外费用/滑点、整股、现金、后续股票与ACT相互传导；无额外消融，不能给它们编造唯一因果百分比。实际费用/滑点表与逐日状态在actual-costs、daily-transmission、july-risk-chain、ACT-transmission中。
按当日两臂ACT状态分组的ΔNAV增量也已精确核对；共同暂停阶段仍可能正在下一开盘清仓，它是描述性会计标签，不是“ACT创造的纯收益”。

6. 资金与期末权益
正常持股观察日总数2794→2685，少占用109个股票日；均仓62.27%→60.20%。全失败费用已计；释放资金不预设再投必赚。六路径截止均无股票、预留或卖款应收，但保留应收股息：正常原4002.832/局部7945.144元；双成本3228.624/3260.768元；延迟详见MECHANISM_RESULTS。总权益包含这些应收，未伪造成已付现金。未成交空单、当时资金未启用与无匹配机会并非同义。

7. 收口与下一依赖
本轮已识别排序确会改变实际获资；未获得跨预设成本/延迟情景一致的整户增益。裁决为成本反转及路径依赖下不确定/有取舍，不晋升，不因此否定先前PVR局部信息，也不继续扫描邻域/仓位参数。I/E0/PVR本体没有被本轮同时重新验证。
下一依赖是单独裁决有限资金下的仓位/机会成本与ACT路径敏感性，先说明新资金为何获得或失去那份预算，再设计一个固定对照；不能继续拿最终NAV否定或证明局部预测，更不能直接改ACT阈值求好结果。该下一轮尚未实施。本轮无生产/交易台更改、无交易账户访问、无安装依赖、无其他任务文件覆盖，现已收口。
'''
report=report.replace('各4个推荐新候选、4?项推荐记录中3个订单真正成交','各4个推荐新候选中3个订单真正成交')
spent=time.monotonic()-started;budget['used_seconds']+=spent;budget['stages'].append(dict(stage='final_order_level_report',status='complete',seconds=spent,error=None));save(O/'COMPUTE_BUDGET.json',budget)
report+=f"\n计时：基线63.02秒；样例+全量+核账86.19秒；机制归因2.74秒；最终订单级归档{spent:.2f}秒；上述累计{budget['used_seconds']:.2f}秒。另几次只读结果复核合计约3秒，总计算不足160秒，低于300秒预算。样例17.31秒；完整局部含加载65.44秒。实现窗口与归档墙钟见DEVELOPMENT_TIMING.json，与计算重叠，未伪造纯开发秒数。\n"
(O/'FINAL_REPORT.txt').write_text(report)
save(O/'DEVELOPMENT_TIMING.json',timing)
save(O/'FINAL_VERDICT.json',dict(status='completed_not_promoted_cost_reversal_and_path_dependence',actual_order_identified=True,economic_full_paths=6,additional_short_technical_prefix_paths=1,economic_reruns=0,rule_changes_after_returns=0,funding_funnel=funding,correctness_passed=True,formal_compute_budget_seconds=budget['used_seconds'],additional_read_only_result_checks_approx_seconds=3,source_inputs_unchanged=True,product_changes=0,account_access=0,remaining_blockers=[],next_dependency='Isolate cash/position opportunity cost and ACT path transmission before claiming portfolio robustness; not started.'))
deliverables=['FINAL_REPORT.txt','FINAL_VERDICT.json','MECHANISM_RESULTS.json','BASELINE_VERIFICATION.json','SAMPLE_VERIFICATION.json','LOCAL_VERIFICATION.json','summary.csv','capital-displacement-orders.csv','ACT-transmission.csv','event-contributions.csv','COMPUTE_BUDGET.json']
save(O/'COMPLETION.json',dict(completed=True,new_full_economic_paths=6,technical_prefix_paths=1,failed_attempts=0,not_promoted=True,files_sha256={x:sha(O/x) for x in deliverables}))
print(json.dumps(dict(funding_funnel=funding,timing=timing,compute_seconds=budget['used_seconds'],verdict='not_promoted_cost_reversal_path_dependent'),ensure_ascii=False,default=str))
