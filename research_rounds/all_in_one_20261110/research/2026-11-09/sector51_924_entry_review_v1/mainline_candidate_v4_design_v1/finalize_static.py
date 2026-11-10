from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;Z=D(0)
read=lambda n:json.loads((O/(n+'.json')).read_text())
su=read('SNAPSHOT_SUMMARY');req=read('ALL_REAL_REQUESTS');chosen=read('ALL_SELECTED_REQUESTS');sec=read('ALL50_STATIC_FEASIBILITY');ev=read('EVENT_CAPITAL_IDENTITIES');don=read('ALL_PLANNED_DONORS')
checks=[]
for s in su:
 day=s['snapshot_day'];r=[x for x in chosen if x['snapshot_day']==day];event=sum((D(x['planned_cost']) for x in r if x['phase']=='EVENT'),Z);fund=sum((D(x['static_funded_cost']) for x in r),Z);assert event==D(s['event_reserved_actual_cost']) and fund==D(s['close_conditional_funded_cost']);assert D(s['mature_budget_after_event'])==D(s['budget_before_event'])-event;assert event<=D(s['event_core_safe_credit']);assert D(s['closing_cash_after_conditional_orders'])>=D(s['reserve']);assert sum((D(x['net_cash']) for x in don if x['snapshot_day']==day),Z)==D(s['actual_planned_donor_net'])
 for q in r:
  if q['kind']=='SEED':assert q['static_funded_q'] in [0,q['unit_q']];assert D(q['surcharge'])<=D(q['proxy_roundtrip_slip'])
  if q['phase']=='EVENT':assert next(x for x in ev if x['snapshot_day']==day and x['sector51']==q['sector51'])['priority_available']
 for x in [x for x in ev if x['snapshot_day']==day]:
  cost=sum((D(q['planned_cost']) for q in r if q['phase']=='EVENT' and q['sector51']==x['sector51']),Z);assert cost<=D(x['remaining'])
 checks.append(dict(day=day,independent_static_arithmetic='PASS',event_reserve=event,conditional_funded=fund))
# First 14 sectors' independent sizing crosscheck: these are capacity plans, not an account run.
fresh=[x for x in chosen if x['snapshot_day']=='2024-09-26' and x['phase']=='EVENT'];assert len(fresh)==39 and len({x['sector51'] for x in fresh})==14;assert sum((D(x['planned_cost']) for x in fresh),Z)==D('328099.8273272193975')
(O/'STATIC_ARITHMETIC_QA.json').write_text(json.dumps(dict(result='PASS',snapshots=checks,new_account_runs=0,fee_gate_at_OPEN=False,raw_frozen_requests_not_changed=True),ensure_ascii=False,indent=2,default=str)+'\n')
lines=['# M4 唯一候选：四个事前截面结果','', '仅把机制套在封存M3的四个独立真实CLOSE快照上，不是M4历史账户，不能把9/26与9/27名单串联为M4加仓轨迹。尺寸、排名和全部资本都不读取次日OPEN/HLC。', '', '| CLOSE | 首次事件代表/买款 | 成熟T买款 | 旧票残余现金买款 | 总新SEED只数 | 全部条件买款 | 计划净供出 |','|---|---:|---:|---:|---:|---:|---:|']
for s in su:lines.append(f"|{s['snapshot_day']}|{s['event_funded']} / {D(s['event_funded_cost']):,.2f}|{D(s['mature_funded_cost']):,.2f}|{D(s['residual_funded_cost']):,.2f}|{s['funded_new_seed_names']}|{D(s['close_conditional_funded_cost']):,.2f}|{D(s['actual_planned_donor_net']):,.2f}|")
lines+=['', '## 9/26的关键差异','', '- 14个新FALSE→TRUE行业、373条真实合法A票，全部能在原2%票预算和容量内形成q_econ。若全部买经济单位需3,179,447元，远超资本；每行业事件2%并逐行业轮流选择后是39股、328,099.83元，不是把全部A前移。','- 半导体：002049×200、603986×100、688709×455，总25,382.35元；电池：300457×500、603659×600、002709×500，总23,558.27元。都只是9/26价格条件下的计划，不能证明9/27OPEN能成交。','- 先冻结真实事件款328,099.83元后，成熟B由1,040,676.87降为712,577.05元，再解T；没有事件额与T双领资本。全日成熟T仍获179,621.22元。','- 全日能计划净供出514,056.62元，主要煤炭161,362.12、地产96,704.76、证券76,667.84、白酒31,212.75、软件31,158.81等。初次新方向试仓需要牺牲仍强旧主线的机动ADD，不是免费获得仓位。','', '## 一次机会而非永久插队','', '9/27快照中9/26事件已在当日OPEN真实尝试过，即使原M3现金拒绝也已消费priority_attempted。因此新优先事件金额为0；旧票按M TRUE原T或非M残余现金继续，不会长期挤在成熟ADD前面。该日全部333,438.84元走成熟T，半导体2股16,770.45元、电池10股81,329.79元。','', '## 尺寸与核心的代价','', 'q_econ只压低可避免的最低佣金额外惩罚，所有印花/比例费照付；不是“总费<=10bp”。每只经济单位约7千元起，相对一手可能显著扩大首仓和失败试探损失。M3原SEED等股量首ADD核心规则保留，较大SEED还会形成更大未来不可供出核心。这不是纯费用修复，也不是已经优化出最佳阈值。','', '当前仍M TRUE且盈利的已确认SEED不因未ADD而出售。新可让位的原冻结SEED市值在9/20、9/23为0，9/26为7,015元，9/27为73,472元；它们须当前M FALSE且事实known。全部194个已确认未ADD赢家不能被叫作无效碎仓。','', '四日63/175/716/690个真实SEED请求均能形成经济单位，但事件资本、优先机会、T与真实现金再淘汰大多数。四日名额不是任何固定2股参数；各新事件9/26实际1–3股。大量成熟M中选多少仍受E/T影响，本轮未改变其资本判断，不宣称解决集中少数主线。','', '## 封存与下一步','', 'STATIC_MECHANISM.md给出唯一待冻结机制；ALL_REAL_REQUESTS、ALL50_STATIC_FEASIBILITY、ALL_SELECTED_REQUESTS、ALL_PLANNED_DONORS、EVENT_CAPITAL_IDENTITIES和CURRENT_SEED_RETIREMENT_AND_CORE保留全量名单/身份/资本/拒因。早期两份静态草稿分别保存在draft子目录，已明确不作为最终候选。','', 'STATIC_ARITHMETIC_QA通过。正式历史尚未运行，仍需精确合同、M3迁移重放及合成/独审准入。未来应逐日记录机会使用和实际消费为独立状态、失败闭合轮费用、被放弃的广度收益、扩大的核心、所有买单执行不确定性；不得用这些未来结果回选本次名单。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
files=[p for p in O.iterdir() if p.is_file() and p.name!='FINAL_STATIC_INDEX.json'];(O/'FINAL_STATIC_INDEX.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},ensure_ascii=False,indent=2)+'\n')
print('STATIC_FINAL_PASS',len(chosen))
