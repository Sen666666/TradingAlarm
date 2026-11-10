from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
x=json.loads((O/'SIX_SINGLE_ORDER_ARITHMETIC.json').read_text())
def m(v):return f'{D(str(v)):,.6f}'
lines=['# 盈新六笔：单笔stress风险数量纸算','',
'只对六个已经保存的原前缀独立算术，不回测、不拼账户、不改原q。新MOBILE风险数量替代旧2%gross，旧intent cap/gross只对照，不压新q；CLOSE先冻结新risk cap与stock10% remaining cap，OPEN只能缩量。','',
's63=1.4826×median(|此前63个log日收益|)，原PVR有效观察与source segment重置规则，shift排除当前；使用64个原warm close取63个收益。全部与原缓存current_z相同，不是CP形成时冻结的used_scale，不年化、不另调窗口。h是该原intent真实I/CP线除原factor；stressH=h·exp(−2s63)只进入本纸算stress价，不改原真实持有/退出线。p为该时点raw报价加原5bp买slip，卖stress价再扣原5bp，全部dated费用含最低佣金与卖印花。','',
'R(q)=q[p−stressH(1−0.0005)]+buyfee(q)+sellfee(q)，单笔β=.0025×该原signal NAV。六笔各有自己的β；不沿用v3共享B/D/κ，也不加入累计已损D硬拒。','',
'|层 / 信号→OPEN|原实际q|单笔β|s63|原h / stressH|CLOSE risk / 新stockcap / 冻结q|OPEN risk+stock上限|同原槽现金必要cap|加现金必要门后上限|','|---|---:|---:|---:|---|---:|---:|---:|---:|']
for r in x:lines.append(f'|{r["layer"]} {r["signal"]}→{r["OPEN"]}|{r["original_actual_q"]}|{m(r["single_order_beta"])}|{r["s63"]:.12f}|{m(r["raw_h"])} / {m(r["raw_stressH"])}|{r["q_signal_risk_only"]} / {r["new_signal_stockcap_qty"]} / {r["q_signal_frozen"]}|{r["q_OPEN_conditional_local"]}|{r["same_original_slot_cash_necessary_qcap"]}|{r["q_OPEN_after_known_cash_necessary_gate"]}|')
lines+=['','六笔最小100股在单笔β下都可容纳，没有最小手归零。新stock10% remaining cap在六笔均不约束；OPEN风险变化只缩量或不变，绝不超过新CLOSE冻结q。全部求解是有限dated股数格点，费用按一张新buy与一张对应stress sell单计算，不按每股固定费近似。','',
'同原PVR reserve槽位的现金必要门单独列示，不是新账现金路径或原唯一缩量原因：首笔available100061.4232403，原现金保留99568.8148106，必要可花492.6084298；100股含买费306.1772120可，200股607.3544241不可。因此风险上限2100在该原槽位仍至多100。其余五笔现金必要cap大于各自新risk上限，不能由此宣称pool/sector等最终门已通过。','',
'当前并发口径由根线程另核：stock结构风险并发.005×currentNAV、industry .01×currentNAV，live K含已付买费一次。此六笔没有重构新组合、没有把各新q带到下一笔；并发/行业/pool等未核，所有正数均为conditional上限，非final grant。已实现PL仍按原账/NAV审计，单笔β本身不封顶连续亏损。','',
'文件：SIX_SINGLE_ORDER_TABLE.csv为两时点小表；SIX_SINGLE_ORDER_ARITHMETIC.json保费用、原q/旧cap对照、CLOSE与OPEN各门、最小手R、下一风险格点；CAUSAL_S63_WINDOW_EVIDENCE.json逐笔列63收益和64原价、block与端点；SOURCE_MANIFEST/VALIDATION/PROTOCOL固定来源及边界。0新账户、0新策略路径、0新收益计算。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
digest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json' and p.suffix!='.log'};(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(digest,indent=2)+'\n')
print('six point readout saved; risk-only quantities preserved, cash gate separate, final grant not asserted')
