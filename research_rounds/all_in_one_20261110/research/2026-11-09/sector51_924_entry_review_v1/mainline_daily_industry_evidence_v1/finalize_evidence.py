from pathlib import Path
from collections import Counter
import ast,json,hashlib,math
import numpy as np
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/mainline_daily_industry_evidence_v1')
R=O.parent;B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
d=read(O/'DAILY_EVIDENCE.json');members=read(O/'EVENT_MEMBERS.json');a=read(O/'MEMBER_DAILY.json');entries=read(O/'FIXED_WINDOW_ENTRY_CLASSIFICATION.json');e=read(O/'E_GATE_AUDIT.json');qa=read(O/'QA.json');hs=read(O/'SOURCE_HASHES.json')
primary=[x for x in d if x['cohort']=='BIRTH_PRICE_KNOWN'];full=[x for x in d if x['cohort']=='ALL_FIXED'];qualified=[x for x in d if x['cohort']=='BIRTH_QUALIFIED']
# Independent aggregate checks use atomic member rows, not builder's metric helper.
for row in d:
 eid=row['event_id'];scope={x['sid'] for x in members if x['event_id']==eid and (row['cohort']=='ALL_FIXED' or x['in_'+row['cohort']])}
 rows=[x for x in a if x['event_id']==eid and x['close_day']==row['close_day'] and x['sid'] in scope]
 assert len(rows)==row['N_fixed']==len(scope)
 for key in ['positive','advance','decline','profitable_advance','new_event_high','CP_receipt','CP_frontier_advance','new_positive','lost_positive']:
  k=sum(x[key]==1 for x in rows);u=sum(x[key]==-1 for x in rows)
  assert k==row[key+'_n'] and u==row[key+'_unknown']
  gt=-1 if not len(rows) else 1 if k>len(rows)/2 else 0 if k+u<=len(rows)/2 else -1
  assert gt==row[key+'_majority']
 if row['event_return_known']==row['N_fixed']:
  assert abs(float(np.median([x['event_return'] for x in rows]))-row['event_return_median_exact'])<1e-13
 assert row['G']==row['profitable_advance_majority']
 if row['close_day']==row['birth_day']:assert row['positive_n']==0 and row['new_event_high_n']==0
# Single rule must not mutate per membership choice.
pmap={(x['sector51'],x['close_day']):x for x in primary}
for ent in entries:
 rr=pmap[(ent['sector51'],ent['plan_day'])]
 assert ent['G']==rr['G']
 assert (ent['phase']=='MATURE')==(ent['decision'] in ['PASS','MARKET_PROGRESS_WAIT','UNKNOWN_WAIT'])
# Safe isolated pure functions, no script/engine imports.
wanted={'finite','btri','ntri','AND','majority','median_bounds','metric'}
tree=ast.parse((O/'build_evidence.py').read_text());nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in wanted]
ns=dict(np=np,pd=pd,math=math);exec(compile(ast.Module(body=nodes,type_ignores=[]),'pure_checks','exec'),ns)
tests=[]
def test(name,val):assert bool(val),name;tests.append(dict(name=name,PASS=True))
test('python_bool_true',ns['btri'](True)==1)
test('numpy_bool_true',ns['btri'](np.bool_(True))==1)
test('numpy_bool_false',ns['btri'](np.bool_(False))==0)
test('numeric_not_receipt_boolean',ns['btri'](1)==-1)
test('nan_unknown',ns['btri'](np.nan)==-1)
test('none_unknown',ns['btri'](None)==-1)
test('known_false_over_unknown',ns['AND'](0,-1)==0)
test('true_and_unknown',ns['AND'](1,-1)==-1)
test('strict_half_is_not_majority',ns['majority'](24,0,48)==0)
test('unknown_can_change_majority',ns['majority'](23,2,48)==-1)
test('lower_bound_majority_passes',ns['majority'](25,2,48)==1)
test('upper_bound_no_majority_fails',ns['majority'](23,1,48)==0)
test('empty_cohort_unknown',ns['majority'](0,0,0)==-1)
test('median_partial_unknown',ns['median_bounds']([-.1,.1],3)['median_positive']==-1)
test('median_lower_positive',ns['median_bounds']([.1,.2,.3],4)['median_positive']==1)
test('median_upper_nonpositive',ns['median_bounds']([-.3,-.2,-.1],4)['median_positive']==0)
test('median_exact',abs(ns['median_bounds']([.1,.2],2)['median_exact']-.15)<1e-14)
review_paths=[R/'mainline_candidate_v1/engine.py',R/'mainline_candidate_v5_expansion_competition/engine.py',R/'mainline_candidate_v7_demand_capped/engine.py',
 R/'mainline_seed_entry_diagnostic_v1/READOUT.md',R/'mainline_seed_entry_diagnostic_v1/STRUCTURE_READOUT.md',R/'mainline_seed_entry_diagnostic_v1/GATE_READOUT.md',
 R/'mainline_tail_capture_baseline_v1/ALLOCATION_SCALING_READOUT.md',
 Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')]
source=read(B/'SOURCE_HASHES.json')
for p in review_paths:
 h=sha(p)
 if str(p) in source:assert h==source[str(p)]
 hs[str(p)]=h
for p,h in hs.items():assert sha(p)==h,('SOURCE_CHANGED_DURING_RESEARCH',p)
seal=read(B/'OUTPUT_HASHES.json')
for n in qa['baseline_output_hashes_verified']:assert sha(B/n)==seal.get(n,seal.get(str(B/n)))
qa.update(dict(independent_aggregate_rows=len(d),synthetic_checks=len(tests),synthetic_result='PASS',
 primary_cohort='BIRTH_PRICE_KNOWN',primary_daily_rows=len(primary),primary_any_price_unknown_rows=sum(x['positive_unknown']>0 or x['advance_unknown']>0 for x in primary),
 full_universe_event_return_unknown_stock_days=sum(x['event_return'] is None for x in a),
 full_universe_daily_return_unknown_stock_days=sum(x['daily_return'] is None for x in a),
 birth_membership_fixed_without_future_pruning=True,primary_cohort_selection_does_not_use_account_PnL=True,
 gated_classification_only_original_M7_filled_requests=True,baseline_and_consumed_sources_unchanged=True,consumed_source_files=len(hs)))
qa['W_numeric_rows_independently_checked']=sum(x['actual_W'] is not None and x['previous_raw_e'] is not None for x in e);qa['first_export_day_W_without_previous_export']=sum(x['actual_W'] is not None and x['previous_raw_e'] is None for x in e)
save('QA',qa);save('SYNTHETIC_QA',tests);save('SOURCE_HASHES',hs)
def pct(v):
 return '未知' if v is None else f'{100*v:+.2f}%'
def num(v):return '未知' if v is None else f'{v:.6f}'
def tri(v):return {1:'T',0:'F',-1:'U'}[v]
lines=['# 每日行业进展与事件出生后盈利扩散：局部市场证据诊断','',
'## 结论','',
'本轮**不建议把一个新的行业门槛直接冻结为“假主线识别器”**。可计算的方向是只对新增 MATURE SEED 要求“出生后多数股票今天仍在推进”，但证据只支持它暂停部分停滞日扩张，已经明确反证了它能普遍辨别假主线。它不改变已有赢家的 ADD、退出或资金保护，也没有与资金竞争规则组合测试。','',
'1. 软件 9/23 CLOSE 创建事件，9/24 OPEN 的常山北明、拓维信息、银之杰 3 个 EVENT 不改；9/24 CLOSE 固定出生可观察 65 股中 58 股已有正价差且当天上涨，9/25 OPEN 的原 5 个 MATURE 可以立即恢复原审查。光伏 10/23 为 37/37，原 10/24 的 30 个 MATURE 同样无固定等待。',
'2. 证券 11/7 是 52/52 正价差且当天涨、51 个事件新高、41 个原 CP receipt。该晚看见的市场进展不弱于真启动，原 11/8 的 13 个 MATURE 仍通过。医疗 11/7 的 20/21 也通过原次日 8 个。不能用后来的亏损标签反过来称当时没有推进。',
'3. 游戏 12/10 只有 23/48 推进，出生以来收益中位 −0.06%，可等待原 12/11 的 34 个 MATURE；但 12/11 已变 29/48，可最早支持 12/12 OPEN 再审。它不是永久避开，不等于挽回这 34 轮原损失。医疗 11/12 的 10/21 可等待原次日 6 个；此后本观察窗没有恢复。',
'4. E 被 M 截断、首次 M 虚奖资格跳变的前提不成立：全部 4,650 行 raw_e 与原 E 相同，1,658 个 M=0 行仍 E>0，原 W 直接减未截断前日 E。不能以此“修复”原权重。',
'5. 当日 ΔE 也不是市场推进的替代：软件 9/26 ΔE<0 而 60/65 仍推进；游戏 12/10 ΔE>0 却缺多数推进。提高 CP receipt 广度同样未得到支持：软件 9/24 为 14/65、光伏 10/23 为 17/37，证券失败前反而 41/52。','',
'## 范围与不能跨越的边界','',
'- 原账户只读基线是 mainline_m7_cash_batch_design_v6/once_20260630，认证终点 2025-01-20。不是名称暗示的 2026-06-30。未使用 INVALID_IMPLEMENTATION 的旧 V11，没有导入策略引擎、Data、history 或重新产生 CP。',
'- 6 个行业、341 个冻结名单股票、10 个事件锚、57 个 CLOSE×行业，三种固定集合合计 171 行。游戏段额外纳入 11/29 出生收盘，才能把 12/2 OPEN 首 EVENT 与 12/3 OPEN 扩张放在正确时序。',
'- 全部是已观察开发段，不是样本外。输入的行业映射、股票总体与历史调整价格继承冻结研究的非 PIT 限制。出生时冻结集合只消除这次计算的未来收益/未来持仓择样，**不能把当前行业映射变成真正历史时点的成分档案**。如要生产证明，需要先前合法提供的 PIT 成分资料，本轮没有联网补源。',
'- 收益是市场调整收盘相对事件出生收盘的价差，不是账户盈利、盈亏平衡价、净清算价值，也不是可覆盖本金风险的额度。没有收益覆盖本金要求、共用风险池、总仓阈值或新增等待天数。',
'- 原 M7 实际订单仅用来对齐 CLOSE→nextOPEN 和初始/扩张阶段，不用于选择行业成员、调整门槛、推算资金回流或计算节省收益。若以后以修正版 V11 作基准，其原 F OR 有效入场 CP 仍是另一项既有条件；本轮没有做叠加候选。','',
'## 1. E、真实增量与不存在的 M 截断','',
'原 mainline_candidate_v1/engine.py 的 compute_evidence 对所有日计算 E=max(RS5,0)×n/N；M 只控制是否有资格参与扩张分配。mainline_candidate_v5_expansion_competition/engine.py 的 classify_reference 从完整日序列取前日 E，W=E+max(E−E_prev,0)。前日未知不额外奖励，绝不是把 M=0 的 E 人为归零。','',
'同口径 raw_e(t)：若原 RS5、n、N 均已知且 N>0，取 max(RS5,0)×n/N；否则 UNKNOWN。n 是原已知真个股数，原行业个股未知仍由 U 保留；RS5 继承原有效样本中位数口径，不冒充全体成分真实中位数。Δraw_e 仅在相邻两日 raw_e 都已知时可算。UNKNOWN 不补 0。','',
'供核对的“假设 M 截断 E”另列：M=1 时 raw_e，M=0 时 0，M=UNKNOWN 时 UNKNOWN。它是被否证前提的反事实演示，**不是现有引擎**。全窗 133 次前日 M=0→当日 M=1 中，98 次前日 E 已正。320 行有可对照前日导出的实际数值 W 逐项一致；9/2 互联网电商的 1 行 W 因前日不在账户导出中未作数值复建，其取值逻辑仅由源码核实，不冒称全行复建。',
'',
'| 行业 / 首 M CLOSE | 前日 raw_e | 当日 E | 真实 ΔE | 原 W | 假设截断后的 ΔE（非原实现） |',
'|---|---:|---:|---:|---:|---:|']
keys={('软件与IT服务','2024-09-24'),('光伏风电设备','2024-10-23'),('医疗服务','2024-11-07'),('证券保险','2024-11-07'),('游戏传媒','2024-12-10')}
for x in e:
 if (x['sector51'],x['day']) in keys:lines.append('| '+x['sector51']+' '+x['day']+' | '+' | '.join(num(x[k]) for k in ['previous_raw_e','raw_e','raw_delta','actual_W','hypothetical_M_gated_delta'])+' |')
lines += ['','统一缩放所有 W 不决定投满与否，原需求封顶分配仍由可用预算及合法需求 D、可动存量 K 决定，沿用已核验 ALLOCATION_SCALING_READOUT，不重做那个已解决问题。','',
'## 2. 出生时固定集合、分母和未知','',
'每个 event 以原行业 0→1 出生 CLOSE b 为锚，读取原 event_id/birth_day；不读最终 status 判断过去是否活跃，每日活跃性使用当日 state。出生前或已 false 的行只显示最近旧锚的市场价格，不允许该旧锚自行恢复入场资格。','',
'- ALL_FIXED：完整原冻结行业名单 N，出生报价未知者仍留在分母。它用于对照原 M/E 的宽度和给缺失上下界，不把未知补成下跌或悄悄删除。N 中可能含当时没有报价的股票，不能直接称其全部是当时可观察成员。',
'- BIRTH_PRICE_KNOWN（本报告市场方向主集合）：从原行业名单只纳入出生 CLOSE 当时有效报价、非合成、来源完整且调整价格一致的成员，立即固定，之后不因涨跌、停牌、持仓或未来上市增删。它是当日可观察价格集合，不是按后来幸存者筛选。出生缺报价者明确排除并留在 ALL_FIXED 对照，不能推断他们当时一定不存在。',
'- BIRTH_QUALIFIED（只作描述）：在出生可观察集合内再要求当日 stock=1、I=true、有效 I 线且 C>I。按出生一刻固定，不要求之后一直合格，不加入后来 B 股；未知出生资格另列。它不是最终赢家名单，也没有依据本段好坏选择它替代主集合。',
'- 修正说明：初次快报先以原 N 给保守下界；完整报告补足“出生时可观察集合”以兑现时点定义，保留原 N 和合格子集的所有结果。未据收益选择分母；实际入场等待/通过的关键结论在原 N 与出生可观察集合上一致。金属 11/6 原 N 给 U，而出生可观察集合给 T；当晚没有原实际 MATURE，仍完整披露。',
'',
'| event | 原 N | 出生可观察固定 N_e | 出生合格固定 N_q | 出生资格未知 |',
'|---|---:|---:|---:|---:|']
for eid in sorted({x['event_id'] for x in members}):
 rows=[x for x in members if x['event_id']==eid]
 lines.append(f"| {eid.replace('|',' / ')} | {len(rows)} | {sum(x['in_BIRTH_PRICE_KNOWN'] for x in rows)} | {sum(x['in_BIRTH_QUALIFIED'] for x in rows)} | {sum(x['birth_qualification']==-1 for x in rows)} |")
lines += ['',
'每个价格比较先核 observed/price/volume eligibility 显式布尔、非 invalid/非 synthetic、原 OHLCV 与 factor 有限正、source_kind/source_path/segment 非空、raw_close×factor 与 close 一致。事件累计量还要求从 b 至 t 每个交易日价格有效、同 lineage；当日比较只要求相邻两日有效同 lineage。缺口保守标 U，不以前值填充，也不因恢复一天就声称已经核清整段。使用原连续调整尺度，不把股票除息误判为自然回吐；这不是公司行动的新增账户准入。',
'',
'对任何 0/1/U 成员指标，固定分母 N：已知真 k、未知 u，比例区间=[k/N,(k+u)/N]。严格多数：2k>N 为 T；2(k+u)≤N 为 F；否则 U。空集合 U。0 是已知没有，不是缺失。中位数同时给已知样本值、全体精确值（仅全覆盖）、未知填−∞/+∞得到的保守上下界；上下界未能确定正负时为 U。完整文件保留 upper/lower、known/unknown。',
'',
f"本窗口完整原 N 有 {qa['full_universe_event_return_unknown_stock_days']} 个事件收益未知股票日、{qa['full_universe_daily_return_unknown_stock_days']} 个相邻收益未知股票日。出生可观察主集合的 57 行均无事件/相邻价格缺失；这只是本窗事实，不能删除一般 U 分支。原行业 state/M/F 仍会未知，例如光伏 10/29、医疗 11/13。",
'',
'## 3. 每日市场量的可计算定义','',
'固定成员 i 的调整收盘为 C_i(t)，事件出生 b：',
'- event_return_i(t)=C_i(t)/C_i(b)−1。positive_i=1[event_return>0]。出生当日等于 0，不是已有盈利。',
'- advance_i=1[C_i(t)>C_i(t−1)]，decline_i=1[C_i(t)<C_i(t−1)]；平盘单列在余额中，不等同回吐。',
'- profitable_advance_i=tri_AND(positive_i,advance_i)。这表示同一只股票已有出生后正价差且今天还在推进，不是把“正收益股比例”和“上涨股比例”分开取交集假象。',
'- new_event_high_i=1[C_i(t)>max(C_i(b…t−1))]；出生当日记 0。不是前 20 日新高。event_peak_drawdown=C_i(t)/max(C_i(b…t))−1。',
'- new_positive/lost_positive 是相邻两日由非正→正、正→非正的成员数，出生首日没有前一出生后收益则 U。这些字段均在机器表，不只展示上涨。',
'- CP_receipt_i：直接读冻结原 CP1 parquet 的当日 receipt，必须 isinstance(x,(bool,np.bool_))；true 还需 candidate 有限正、当日价高于 candidate、delta_frontier>0 才计已知 receipt。false 是 0，缺失/类型或必要资料不明是 U。只读原记录，不重跑模型。',
'- CP_frontier_advance_i：原 ready 真且 delta_frontier>0，表示原 CP 状态机当天确有 frontier 新位移；比 receipt 更早，不要求已攒够原波动尺度门槛。原 reset 后推进可来自新结构，不伪称收复历史最高价。这两列都不是持仓 information_confirmed 或可立即 ADD 的证明。','',
'## 4. 完整逐日表：出生可观察固定集合','',
'表中收益是出生以来中位数；“正/推进”分别为 positive 与 profitable_advance，分母均为该事件固定 N_e。“涨/跌/平”是相邻 CLOSE，CP 两列为 receipt/frontier。nextOPEN 只列原 M7 实际 EVENT/MATURE 笔数，不代表门槛改动后的新账户。state/M 为 −1 时原状态未知；G 可由价格独立算出，但不能旁路原资格。']
for seq in dict.fromkeys(x['sequence'] for x in primary):
 rows=[x for x in primary if x['sequence']==seq]
 lines+=['','### '+seq+' / '+rows[0]['sector51'],'',
 '| CLOSE → nextOPEN | 出生 / N_e | state/M; S/F | 正 / 推进 | 累计中位 | 涨/跌/平 | 新event高 | CP receipt/frontier | ΔE | G | 原次日 EVENT/MATURE |',
 '|---|---|---|---|---:|---|---:|---|---:|---|---|']
 for x in rows:
  N=x['N_fixed'];flat=x['advance_known']-x['advance_n']-x['decline_n']
  lines.append(f"| {x['close_day']} → {x['next_OPEN']} | {x['birth_day']} / {N} | {x['state']}/{x['M']}; {x['S']}/{x['F']} | {x['positive_n']}/{N} ; {x['profitable_advance_n']}/{N} | {pct(x['event_return_median_exact'])} | {x['advance_n']}/{x['decline_n']}/{flat} | {x['new_event_high_n']} | {x['CP_receipt_n']}/{x['CP_frontier_advance_n']} | {num(x['raw_delta_E'])} | {tri(x['G'])} | {x['next_OPEN_actual_EVENT']}/{x['next_OPEN_actual_MATURE']} |")
lines += ['','## 5. 当时能区分与不能区分','',
'### 软件：不牺牲 924 首 EVENT，也不人为多等一天',
'9/23 CLOSE 的 M=0 是前日宽度不足，不妨碍原 EVENT。9/24 的涨幅、事件高点、原 CP 都是真实当日进展，G=T 最早支持 9/25 OPEN 的 5 个 MATURE。9/25 至 9/30 主集合 G 持续 T。9/26 虽然 ΔE 负，绝对市场价差仍普遍推进，说明拿相对市场五日 E 变化当价格持续性会误挡这一类大启动。已有赢家 ADD 不通过这个新 SEED 门槛。',
'',
'### 光伏：主线会回吐，回吐不等于结构失败',
'10/22 出生，10/23 OPEN 3 个 EVENT；10/23 收盘 37/37 真实推进，10/24 原 30 个 MATURE 不延迟。原研究已说明这一批同时包含赢家与 20 个亏损轮，广度不会预先选出最终赢家。10/24 回吐日仅 4/37，原 10/25 的天顺风能新种子会等；10/25 变 35/37，市场条件最早 10/28 再审，不能把反弹恢复否认掉。既有 30 轮不会因为一天 G=F 而强制退出/停 ADD。10/28 再回吐、10/31 已多数推进但 sector=0，后者仍无资格，不能用新价差条件复活已取消票。',
'',
'### 证券与医疗：真正的反证，不隐藏',
'证券 11/7 的价格进展、事件新高和 CP receipt 是实际已发生的，并非 M 资格跳变凭空造的证据。11/8 才出现普遍回吐，已经晚于原 13 个 MATURE 入场的决策 CLOSE。医疗 11/7 同样明确推进，原 8 个 MATURE 通过；11/12 仍有 19/21 高于出生、行业 M=1，但同股继续推进只有 10/21，才可对原次日 6 个新增种子给 WAIT。要求“出生后大多数已有正收益”本身在 11/12 仍会通过，所以必须分清已有价差与今日新增推进。',
'',
'### 游戏：可阻止停滞日批量扩张，但不能称永久避开',
'11/29 出生，12/2 OPEN 原 3 个 EVENT；12/2 收盘 40/48 推进，12/3 原 18 个 MATURE 仍过，是清楚保留的假信号代价。12/9 新事件当天 3 个 EVENT 支持 12/10 OPEN，不变。12/10 的 23/48 可等待原 12/11 的 34 个 MATURE。可是 12/11 的 29/48 已恢复，最早 12/12 OPEN 重新审查；原单后来盈亏不能作为节省收益。12/13 虽有 28/48 当天上涨，只有 24/48 同时高于出生，严格多数仍 F，不能偷偷用上涨数替换定义。',
'',
'### 金属：不同分母能改变结论，不能按结果挑选',
'11/7 主集合为 61/106 推进，原 N 也是已知 61/112 达多数，原次日 3 个 MATURE 仍过；出生合格子集恰好 22/44 不达严格多数。后者看起来更能挡这个已知失败案例，但不能据此把主集合改成合格股。完整保留三个集合。11/6 原 N 的 55 已知推进、6 未知导致 U，出生可观察集合 55/106 为 T；原当晚无实际 MATURE，仍不掩饰分母差异。',
'',
'## 6. 唯一可计算方向与 WAIT 合同（未实现、未冻结）','',
'候选 G_e(t)=strict_majority_{i∈BIRTH_PRICE_KNOWN(e)} [ C_i(t)>C_i(b_e) AND C_i(t)>C_i(t−1) ]，严格使用上述三值规则。它是一个“同股正价差继续推进广度”因子，不扫描窗口、涨幅阈值、分位数或连续天数。','',
'适用且仅适用：当前真实 phase=MATURE、kind=SEED 的新种子，在 CLOSE 构造独立合法需求 D **之前**检查 G。EVENT/RESIDUAL、已有赢家 ADD、I/CP保护、退出以及原融资归类均不在本研究中更改。不需要利润覆盖风险，不把行业回吐当已有赢家个股结构破坏。',
'',
'如果以后单独获准实施，必须同时实现以下语义：',
'1. G=T：只是继续原所有资格、F/CP（若所在基准有）、经济量、dated lot、source/factor、公司行动、容量和资金检查；不是成交承诺。',
'2. G=F：INDUSTRY_PROGRESS_WAIT；G=U：UNKNOWN_WAIT。只冻结该新种子的当前成熟需求，不在 OPEN 最后拒绝却保留前晚为其构造的卖出计划。WAIT 本身不占现金，也不新增共用风险预算。',
'3. 保留原 ticket_id、signal_day、出生 NAV/原试仓预算、原 source 身份与只上调 I 线。不得重新出生 event 或刷新 EVENT 2% 额度，不允许用等待制造新的优先尝试。',
'4. 每 CLOSE 继续原票条件和桥接。原 I/stock/sector 已知 false、原保护破位或源改变，按原语义取消；未知暂停。G单独 false 不是永久取消，不能把以后恢复票算消失。',
'5. G 在某 CLOSE 恢复，最早 nextOPEN 重新审查；保留开盘报价/保护/来源/容量/费用与资金校验，不读该 OPEN 当天尚未来到的收盘。',
'6. 每日按真实 M/event 重算 phase。若降回 RESIDUAL，按原事件剩余额度与资格审查，不把原 MATURE 标签永久焊死，也不把 RESIDUAL 当作无限扩张旁路。',
'7. 这条新 SEED WAIT 不撤掉有效 CP 支持的已有赢家 ADD。若资金分配仍通过别的规则供资卖赢家，那是独立竞争机制；本研究没有悄悄替它加一条保护。',
'',
'当前证据足以否证“只要要求行业盈利扩散，就能把证券/医疗初段假主线限制为试仓”的强说法。可继续研究的只是“没有当天真实进展时，不批量吸收新成员”这一窄命题。考虑证券 11/7、医疗 11/7、游戏 12/2、金属 11/7 均会通过，本轮不建议据这些局部分类直接宣布新策略更优；也不为提高挡损数字而追加 CP多数、连续天数、旧高或阈值。',
'',
'## 7. 原实际入场对齐统计，绝非新账户收益','',
'| 固定段 | 原 EVENT 保留 | 原 MATURE 通过 | 原 MATURE 等待 | 未知等待 |',
'|---|---:|---:|---:|---:|']
for seq in dict.fromkeys(x['sequence'] for x in primary):
 rs=[x for x in entries if x['sequence']==seq]
 lines.append(f"| {seq} | {sum(x['phase']=='EVENT' for x in rs)} | {sum(x['decision']=='PASS' for x in rs)} | {sum(x['decision']=='MARKET_PROGRESS_WAIT' for x in rs)} | {sum(x['decision']=='UNKNOWN_WAIT' for x in rs)} |")
lines+=['',
'这些数只在原 M7 已实际成交机会集上标记。没成交但有需求的全部原计划数也在 DAILY_EVIDENCE 中，可改变 D 与资金竞争；本轮没有重算预算、供资、NAV、可执行量、信息确认或 ADD。没有对等待组原损益求和并称之为可节省收益。',
'',
'## 8. 验证与交付','',
f"- 原 E 对照 4,650 行、逐日集合聚合独立复核 {len(d)} 行，{len(tests)} 个纯函数三值/布尔/中位数回归全部通过。合成检查覆盖 Python bool、NumPy bool、receipt 数字不冒充布尔、未知可改变多数、严格半数不通过、空集合未知和中位数上下界。",
f"- 输入 SHA256 共 {len(hs)} 项，冻结原 6 份关键账户输出复核字节未变，消费的本地输入全部复核未漂移。未遍历 manifest 所列的其他公告/网站材料，未联网、未读取新源、未触发 403 路径。",
'- READOUT.md：本报告；DAILY_EVIDENCE.json/csv：三种集合所有日；MEMBER_DAILY.json/csv：每个成员原子结果；EVENT_MEMBERS：出生固定名单与资格；E_GATE_AUDIT/E_FIRST_M_ROWS：全窗 E/ΔE/W 核实；FIXED_WINDOW_ENTRY_CLASSIFICATION：原实际种子分类；QA/SYNTHETIC_QA/SOURCE_HASHES/OUTPUT_SEAL：复核与可追溯封存。',
'- build_evidence.py 只读取已授权冻结市场/账户导出并写本新目录；finalize_evidence.py 只独立复核聚合、写报告。没有改正式策略、历史引擎或既有冻结研究。','']
(O/'READOUT.md').write_text('\n'.join(lines))
save('OUTPUT_SEAL',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps(dict(QA=qa,entry_counts=dict(Counter(x['decision'] for x in entries)),report_lines=len(lines)),ensure_ascii=False))
