from pathlib import Path
import sys,json,importlib.util,datetime,time
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/time-confirmation-mechanism-20261029');sp=importlib.util.spec_from_file_location('tc_final',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;t=time.monotonic()
su=H.read(O/'results/summary.json');b=su['1'];c=su['2'];v=H.read(O/'results/verification.json');sv=H.read(O/'sample/verification.json');protocol=H.read(O/'PROTOCOL-v2.json');counts=H.read(O/'results/intent-counts.json')
for row in counts:row['counts']={k:v for k,v in row['counts'].items() if not (k.startswith('reject_') and v==0)}
(O/'results/intent-counts.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2))
logs=pd.read_parquet(O/'results/intent-log.parquet');end=logs[logs.kind.eq('deadline')].copy();cache=pd.read_parquet(S.E1/'market-cache.parquet');cache.date=pd.to_datetime(cache.date);end['date']=pd.to_datetime(end['at']).dt.tz_localize(None).dt.normalize();end=end.merge(cache[['date','symbol','g_ready','g_grade']],on=['date','symbol'],how='left');end['warm']=end.g_ready.fillna(False)&end.g_grade.ge(2).fillna(False)
barriers=[]
for (arm,cost),g in end.groupby(['arm','cost']):barriers.append(dict(arm=arm,cost=int(cost),deadlines=len(g),common_legal_false=int((~g.legal).sum()),G1_not_warm=int((~g.warm).sum()),time_test_false=int((~g.timepass).sum()),legal_but_time_false=int((g.legal&~g.timepass).sum()),accepted=int(g.accept.sum())))
pd.DataFrame(barriers).to_csv(O/'results/deadline-barriers.csv',index=False)
ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());elapsed=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(protocol['frozen_at'])).total_seconds()
S.save(O/'FAILURES.json',dict(technical_sample_only=['numpy boolean JSON type; normalized logs only','prefix validator expected encoded dict, encountered native FillReceipt; support both types'],preserved=['sample-v1-jsonbool-failed','sample-v2-prefix-type-failed','code/study-v1-jsonbool-failed.py','code/study-v2-prefix-type-failed.py'],financial_rule_changes=0,full_economic_runs=1,after_outcome_economic_reruns=0,report_cleanup='Removed zero-valued dynamic reject-order-id keys; numeric result unchanged'))
def m(x):return f'{D(str(x))/10000:,.2f}'
def cnt(arm,cost=1):return next(x['counts'] for x in counts if x['arm']==arm and x['cost']==cost)
cw,ct=cnt('W'),cnt('T')
text=f'''时间确认v2：三臂首次参与机制检验，完成并停止当前候选

裁决：不晋升“低N_eff首次机会等待5观察并要求N_eff>=2”的本候选；停止这套固定规则，不追加3/7天或其他阈值。减少成交/订单峰值确实发生，但代价是更大的盈利及肥尾损失，当前没有证据值得带入有限资金综合。这个结论不否定全部时间确认思想，也不证明原E0/I永久正确；本轮未测试真实ACT组合的容量补偿，不能许诺其必然同向。

口径：全部5349原E0机会，同等独立初始100万元、基础/双成本、原I/E0出口，终点2026-10-27，未持仓的资金不假设再投资。A只读复用10698条实验一I控制；W/T实际新增21396账。所有金额合计是独立机会账求和，不是一个可交易账户。
预先真正受影响的1425个首次Q低分散机会，实际也正好1425个发生低证据意图；其余3924机会两臂资金结果与A完全一致，其中1290无Q现金未启动。全流曾出现低证据的2789个E0不代表都需干预：多数已按原规则入场。全部32899候选的枢轴和N_eff可确定，未知0；没有补零或把G1原因字段缺失当作等级缺失。

基础成本主表（差额万元；平均元/每百万元独立机会）
W−A：{m(b['comparisons']['W-A']['delta'])}，平均−7,869.59；T−A：{m(b['comparisons']['T-A']['delta'])}，平均−8,432.44；T−W：{m(b['comparisons']['T-W']['delta'])}，平均−562.85。
1425真正受影响机会中，T−A平均−31,652.71元，T−W平均−2,112.74元；不能只用5349全分母稀释变化。
双成本W−A {m(c['comparisons']['W-A']['delta'])}、T−A {m(c['comparisons']['T-A']['delta'])}、T−W {m(c['comparisons']['T-W']['delta'])}，方向相同。
绝对净贡献A36068.63、W31859.19、T31558.12万元。T比A省全部负损耗1976.82万元，却少正贡献6487.33万元，净少4510.51万元。费用从A409.02降至T353.22万元已计入净账，不重复扣；损失不能归咎手续费。

尾部与交易哲学
T−A配对尾部−4130.17、普通−380.35万元，两部分均恶化；固定原A尾部集合贡献保留T91.26%、W91.88%。T相对W普通改善13.99万元，但尾部减少315.06万元，最终仍少301.07万元。双成本同向。
尾部沿任一比较臂决策后净收益率>=30%划分，仅事后评价；不同比较的配对尾部集合不同，不能把不同集合的尾部分解跨比较硬相加。净差分解始终精确。平均盈利/平均亏损A3.54、W3.29、T3.26，本轮没有提升高盈亏比目标。

首次不通过与后来恢复
派生D复制W首次实际入场的全账，仅在当时T时间条件会通过时保留，否则持现。不是第四条实际资金臂。W的136个实际入场会被时间条件拒绝，D−W=-1597.15万元；其中后来真实T有99个仍合法入场，T−D追回+1296.08万元，故T−W=-301.07万元。通过组真实T与D净差0；没有把首次拒绝当永久过滤，也没有按事后T确认日给W反配等待。
这组分解是会计诊断，后项含重建/恢复路径；总T−W不是纯信息因果效应。W−A还包括固定等待、共同截止资格失效及截止无新I事件时的意图延续，不应全称为“晚买价格”的效应。

少成交来源（均基础成本；双成本计数相同）
A实际首次成交4057，W3499（少558），T3462（少595）；W/T之间只再少37。W/T与A均无新独有成交；共同成交中W866、T829个较A晚，其余2633同日。没有提前成交。
W低证据意图{cw.get('intent_start',0)}次，截止{cw.get('deadline',0)}次，共同截止资格不满足{cw.get('deadline_legal_false',0)}次、窗内结构失效取消{cw.get('intent_cancel_structure',0)}次；T低证据意图{ct.get('intent_start',0)}次，截止{ct.get('deadline',0)}次，共同资格不满足{ct.get('deadline_legal_false',0)}次、取消{ct.get('intent_cancel_structure',0)}次。详细G1暖/时间条件交叉见deadline-barriers.csv；次数可多次发生于同一机会，不强行当互斥因果加总。
W/T重建起点{cw.get('rebuild_origins',0)}/{ct.get('rebuild_origins',0)}次，零成交日单到期{cw.get('zero_fill_expiry',0)}/{ct.get('zero_fill_expiry',0)}次，预算/最小单拒绝均0。减少成交来自等待、共同资格、证据条件和真实执行路径，未因共享现金或新增资金上限少买。W258、T179次实际入场决策日没有当日新Q，但满足已冻结的截止继续资格，这一接线明确保留，不冒充单纯复制原I日事件。

拥挤与占资（标准化独立机会流，不是实际组合容量成绩）
原I/Q底层信号未改：35316原I、32899合法Q及重复刷新仍可观察。A/W/T提交日单合计4073/3515/3478，日峰值143/90/89；实际首次成交日峰值143/89/88，新增请求起点峰值143/149/149，W/T等待队列峰值均118且不预占现金。少交易并未让观察/排队工作量同步减少。
A/W/T并发持仓峰值366/363/362，T只比A少4（约1.1%）；成本本金×持有收盘合计1483.17/1391.95/1381.85亿元·收盘，总持股收盘158837/147769/146716。T总占用下降，但已成交平均持有39.15→42.38收盘属于筛选后的描述，不是更稳趋势的因果证据。峰值占用改善很小，不能只看少595次成交就说容量问题解决。

末端与核验
A104个仍持股，W/T各91，全部原价估值/应收权益入账；W/T各7个待确认意图未完成，列右截尾而非永久过滤。原股息支付字段未知的权益按既有合同待收，不伪装实际收款。日单、T+1、权息、原保护及日线容量/HLV代理不变。
8股111机会444新账样例2.662秒；8个物理截断枢轴/观察钟前缀通过。全407股一次全量81.277秒，低于300秒，样例全量精确。所有共同高证据/未知状态至首次低证据分叉前的原生资金审计与A完全一致；未干预3924机会全金融值一致。2850个跨成本W/T首共同意图钟逐项一致，分叉后只消费各自未来新I事件，不再强求共同复评。最大现金/NAV残差0；D会计等式、各比较尾部+普通及省损耗+正贡献核对。
输入SHA最终复核不变。开发超过15分钟目标，具体耗时在新增意图状态机、只读A核对及两次类型修复；一次是NumPy日志布尔JSON，另一次是前缀验证器对原生FillReceipt的类型处理，失败代码/目录保留，未改科学规则。全量经济运行只有1次，无结果后经济重跑/调参。v2冻结到归档实际墙钟见COMPLETION，不冒充纯CPU开发耗时。

下一步裁决：停止当前时间确认候选、不晋升。时间集中度作为诊断保留，后续路线可回到已有局部排序和有限资金机会成本，但本轮不自动开新路线。保留全部失败、对照和末端权益；没有产品/交易台修改、账户访问、交易或外部发送。此为已见开发历史及当前池/分类快照，不能推广未来表现。

交付：PROTOCOL-v2.json、input-identity.json、preflight.json、code/study.py；results/units.parquet、A-readonly.parquet、paired-events-cost*.csv、comparisons.csv、affected-subsets.csv、continuous-contributions.csv、intent-log.parquet、orders.csv、fills.csv、fee-components.csv、first-participation-delays.csv、daily-concurrency.parquet、concurrency-summary.csv、deadline-barriers.csv、summary.json及核验。无剩余阻塞。
'''
(O/'FINAL_REPORT.txt').write_text(text)
S.save(O/'COMPLETION.json',dict(status='completed_stop_current_temporal_gate',verdict='Stop this fixed Neff<2 then fifth-observation Neff>=2 admission candidate; reduced fills and peak orders did not compensate lost tail/profit.',main=su,events=5349,first_low=1425,unknown=0,A_readonly_units=10698,new_units=21396,full_economic_runs=1,full_seconds=v['seconds'],sample_seconds=sv['seconds'],frozen_to_archive_wall_seconds=elapsed,development_target_minutes=15,development_target_exceeded=True,inputs_unchanged=len(ident),code_sha256={str(p):H.sha(p) for p in (O/'code').glob('*.py')},product_changes=0,accounts=0,trades=0,additional_arms=0,blockers=[],report=str(O/'FINAL_REPORT.txt')))
print(json.dumps(dict(completed=True,verdict='stop_current_candidate',frozen_to_archive_seconds=elapsed,barriers=barriers,seconds=time.monotonic()-t),ensure_ascii=False))
