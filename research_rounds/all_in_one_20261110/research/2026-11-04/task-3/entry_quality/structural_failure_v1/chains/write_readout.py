"""Format frozen descriptive chains; does not choose/trade a rule."""
from pathlib import Path
import json,csv,hashlib
from decimal import Decimal as D
O=Path(__file__).resolve().parent
x=json.loads((O/'COMPLETE_ORIGINAL_CHAINS.json').read_text())
v=json.loads((O/'VALIDATION.json').read_text())
def money(a):return f'{D(str(a)):,.2f}'
comments={
'000620.SZ': '首个负事件01-17时已有库存仍浮盈3392.58；01-19 CP请求卖首三mobile，01-20执行。随后新正向event也在01-20成立，01-21新S21、01-24新S63上确认支持了两次追加；它们最后合计亏10706.78。因而“-1暂停、+1恢复”不会挡这两笔。首仓CORE实付306.18，后续五mobile累计92622.48，是授权规模与连续尝试的具体样本；赢家也会如此扩张，不能由本例就设CORE比例或高点门。01-27 I卖单至02-08才真实成交，不能假设01-28任意全售。',
'601326.SH':'05-10首负事件与原三层CP卖单同CLOSE，05-11全售；没有事件后追加。前三个上涨确认与PVR升序发生在实际早期亏损之前，不能用事后CP reason证明信号无效。该链展示已进入仓位后的快速反转，负事件触发以后再加一退出器没有新增提前量。',
'300085.SZ':'10-09授权、10-10 OPEN重入，10-10 CLOSE首负事件已同时触发原CP，10-11卖出。单mobile累计亏5920.08，首个可观察负事件不能倒填10-10 OPEN阻止成交；从当日收盘亏3640.44到最终亏损还含下一OPEN缺口及成本。把“事件后退出”写成能规避全额损失是错误时钟。',
'002911.SZ':'CORE先实际出资、三次mobile随后加仓；08-03首负事件同时原mobile CP已锁，08-04卖mobile。CORE直到09-16 I请求、09-19卖，CORE终局+121.28；不能把mobile保护失败与CORE I持有期统一归因，也不能因延长持有就称退出过晚。',
'000065.SZ':'03-21首负事件比03-22原CP请求早一个CLOSE，触发当时库存已亏1902.21，不能将该下跌算作可避免。四mobile已全部买完，没有后续可冻结新增；仅A原库存局部界限有范围，必须用03-22真实可成交OPEN、原费用/股数验证。',
'000564.SZ':'Nov30真实旧库存已知浮盈24524.05，Dec没有新买；Dec财富−20045.73，但该完整周期最终仍+4478.32。12-09首负事件时旧库存仍浮盈16037.05。此为已经成功趋势的利润回落，非连续首次失败；减少它不是天然研究目标。12-12 CP请求到12-14才成交，12-15 I到12-16，不能用事后峰值或请求日价格估算。',
'000029.SZ':'Dec新重入后两个add全部在12-06首负事件前完成；首负时已亏61.81，12-07 CP、12-08卖。B后续风险冻结覆盖0，A仅可能提前一OPEN；本例不能支持普遍给首次缩量，也不能说缺CORE就是错误，曙光同样无CORE。',
'601601.SH':'10-08后阶段财富−4951.62，但完整周期+7600.88。09-09首负事件以后、09-23新正事件之前，09-18真实追加layer1931最终+2481.60；它是负leg冻结新增的直接赢家机会代价。三个mobile最终同10-09 CP→10-10退出。正常回吐与入场失败需分开。',
'002181.SZ':'12-23已由ACT请求退出，首负event12-24在后、12-25才执行。任何原库存新退出不得篡改已锁ACT clock或把未成交日当自由次OPEN；A新增贡献0。没有后续mobile可拒，故负event控制没有这笔新增覆盖。',
'920808.BJ':'全周期正贡献最大，四mobile、无CORE，逐次上行新前沿与PVR提升与多个亏损例共享；不能按这些来源剔除。05-05首负事件与原CP同CLOSE，05-08退出，原净+75440.87。不存在可由同一负事件提供的提前退出增量。',
'601595.SH':'原CORE+连续mobile扩张形成全周期+48847.91。04-13首负事件时已有mobile CP锁，CORE仍合法；后续三add净−3143.66，但CORE与前期扩张贡献巨大。不能删掉最终坏add后将释放资金当作可获得账户增益，也不能把整个赢家的回吐当初始失败。',
'002583.SZ':'2024-10-14首次CORE后两次mobile扩张，全周期+21949.16；与银之杰同属震荡后的新上行机会却结果相反。11-04负event已同mobile CP，CORE原I维持至11-26请求；尾部不能靠“所有首仓等待”保护而无代价。',
'002317.SZ':'10-25首负event时前三原层尚在，最终合计+27687.65；10-27新+1后第四mobile最终+1260.12。首负就全退会伤真实趋势延续，宽B“首次负之后直到原flat不再买”也误拒该赢家。Nov30旧浮盈38681.18、Dec回落9733.41仍终局+28947.77，不能以Dec终局回吐标签反推过早/过晚。',
}
text=['# 原No60完整交易链：先有时钟和分母，再谈机制','',
'状态：完成10条主链和3条附加赢家/回吐对照的只读取证；未建新账户，未提出已获证据支持的新交易规则。',
'',
'取样固定为完整cycle终局净亏前5、Dec阶段财富最差旧周期、Dec新周期最差、10月8日后阶段最差旧周期、ACT受影响净亏最差、完整周期正贡献最大。附加上海电影、海能达、众生药业3个事先指定的真实赢家。结果只能描述这些链，不能当随机样本。主链36层，7个终局负周期合计 '+money(v['primary_negative_cycle_net'])+'，仅占原1677周期毛负的 '+f'{D(v["selected_negative_share"])*100:.4f}'+'%；不由10个故事外推全账户修复。',
'',
'完整JSON保留每个账户CLOSE的原量价（调整与原始坐标同时保存）、E0事件/确认pivot、I状态/floor/当日买事件、G1理由、source segment、CP canonical receipt/形成区间/新前沿ID/冻结scale/初始保护线、行业attempt/stage/授权、PVR/排序、真实CORE库存、含费remaining basis/浮盈、原intent/funding、实际退出part及请求/成交时间。prior保护线与post-CLOSE ratchet分开标示；无当日报价时保留实际source_day，不把前值冒充当日新证据。',
'',
'## 可执行诊断的边界','',
'T仅取该股实际首次fill之后、真实flat之前首次原events.parquet.event=-1，CLOSE以后才已知；负事件不等于原E0_target失效。A仅隔离T时既有库存：原控制也不再加入T后新合同，比较下一原合法OPEN退出与原库存原退出；必须按层扣除已锁ACT/I/CP，T+1、容量、停牌、权息可卖日、原pending与原费用不得放松。B仅看严格晚于T决策的原mobile合同拒绝范围，T前及T同日已funded/filled/pending不删除。两者是局部原股数/预算边界，不是账户增益；原full-flat只作事后评价截止，不能当新规则当时的reset。精算与不兼容项由 sibling executable_bounds 另行落盘，不把后验净额直接当少亏。',
'',
'尤其B从首次负事件持续到原周期终了，比“-1暂停、下一+1恢复”更宽。盈新01-20已+1，01-21/24大亏追加会被精确恢复规则放行；不得拿宽B覆盖替该候选背书。',
'',
'## 主链与对照','',
'|类别|股票 / 原周期|层 / CORE-mobile|全周期净额|首负事件T|T时已持浮盈|T后原mobile合同|',
'|---|---|---|---:|---|---:|---:|']
rows=[]
for j,c in enumerate(x):
 cc=c['campaign'];t=c['local_diagnostic_trigger'];o=next(y for y in c['observations'] if y['day']==t['first_negative_native_event_after_actual_first_fill']);later=t['later_original_mobile_contracts'];cm=cc['by_role']
 text.append(f'|{"主" if j<10 else "附对照"}|{cc["name"]} {cc["sid"]} {cc["opened"][:10]}→{cc["closed"][:10]}|{cc["layers"]} / {cm.get("core",0)}-{cm.get("mobile",0)}|{money(cc["endpoint_net"])}|{o["day"]}|{money(o["held_unreal"])}|{len(later)}|')
for j,c in enumerate(x):
 cc=c['campaign'];text.extend(['',f'### {j+1}. {cc["name"]} {cc["sid"]} — {c["selection"]}','',comments[cc['sid']],'',
'|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|','|---|---|---|---:|---:|---:|---|---|'])
 for e in c['entries']:
  a=e['original_signal_and_authorization'];r=e['actual_layer_accounting'];day=a['decision_at'][:10];o=next(y for y in c['observations'] if y['day']==day);fi=a['frozen_intent'];reasons='; '.join(a['G1_up_reasons']) or '无当日新G1来源'
  row=dict(campaign_id=cc['campaign_id'],sid=cc['sid'],layer=e['layer'],role=a['role'],action=r['actual_entry_action'],decision=day,filled=a['opened'][:10],core_held=o['core_actually_funded_and_held_before_new_CLOSE_decision'],close=a['original_stock_state']['close'],initial_adjusted_floor=a['frozen_initial_adjusted_floor'],actual_buycash=a['cost'],known_prior_inventory_unreal=o['held_unreal'],G1_reason=reasons,industry_stage=a['industry_stage'],PVR=fi.get('PVR_score'),rank=fi.get('original_H1_rank'));rows.append(row)
  text.append(f'|{e["layer"]} {a["role"]}/{r["actual_entry_action"]}|{day}→{a["opened"][:10]}|{",".join(map(str,row["core_held"])) or "无"}|{float(row["close"]):.4f} / {float(row["initial_adjusted_floor"]):.4f}|{money(row["actual_buycash"])}|{money(row["known_prior_inventory_unreal"])}|{reasons}|{row["industry_stage"]} / {float(row["PVR"]):.2f}|')
text.extend(['','## 算法裁决','',
'这批原链支持“相同上行确认、行业扩张和连续CP授权既出现在严重失败，也出现在稀疏大赢家”。没有发现重复消费同一个receipt或用新ID伪装无新证据的直接执行错误；每个原mobile的canonical新前沿/receipt可逐项追溯。行业授权持续本来就是预算存续，不能因未新发行业receipt便宣称无效。CORE存在与否也不能直接识别质量：若干最差周期无CORE，而最大正周期曙光同样无CORE。',
'',
'事件早退最多在北方/深房等提供一个CLOSE的局部提前量；秦港/银之杰已与CP重叠，粤传媒已ACT锁。供销/众生/太保的阶段大亏主要包含此前真实已知浮盈回落，减少回吐不是自动正确的目标。需要等局部真实执行价验证才能说早一OPEN是否少亏，更不能说峰值可回收。',
'',
'当前不应由这些案例新建“首仓缩量、旧高等待、CORE出资比例、负事件全退、首次负事件后不再买”规则。原量价负leg与持续I授权的分歧是可证伪诊断方向，必须使用全3436原实际动作、固定原83/94尾、真实强窗新启动的前向时钟覆盖验证；负事件后再出现原+1时要按真实恢复逐笔计，不能把宽上限当精确候选。若大额坏合同在原+1之后、或主损失已在首负前/已锁退出，冻结新增不能解决该失效点；若大量赢家扩张也处在同负leg，停止而不加冷却/高点/额外阈值硬救。',
'',
'本交付结论为 NO_NEW_MECHANISM_PROMOTED；静态局部边界并不改变这个判定。原当前存续池、当前行业快照、OHLCV下一OPEN代理和真实竞价成交的差异沿原限制保留。'])
(O/'READOUT.md').write_text('\n'.join(text)+'\n')
with (O/'ENTRY_DECISION_TABLE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
manifest={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'}
(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('wrote forensic readout and',len(rows),'actual entry decisions')
