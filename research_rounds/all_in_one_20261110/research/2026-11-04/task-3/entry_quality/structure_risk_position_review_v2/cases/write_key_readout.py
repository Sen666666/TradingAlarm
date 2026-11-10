"""Compact paper walkthrough over two already extracted original timelines."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def money(x):return f'{D(str(x)):,.2f}'
chosen={'688146_SH':['2026-04-03','2026-04-21','2026-04-22','2026-04-30','2026-05-06','2026-05-27','2026-06-18','2026-06-30'],'000620_SZ':['2022-01-04','2022-01-05','2022-01-06','2022-01-10','2022-01-11','2022-01-12','2022-01-13','2022-01-19','2022-01-20','2022-01-21','2022-01-24','2022-01-25','2022-01-27','2022-01-28','2022-02-07','2022-02-08']}
lines=['两条原路径逐日纸面输入已完成：中船特气58个原CLOSE，盈新21个原CLOSE。0新账户、0策略模拟、0替代股数/收益。','',
'纸面判定只覆盖“原CP申请＋原已持库存保护/风险参考”，不是完整v2行为。现存原i_buy事件和up_reasons逐日附入，允许根线程接入探索申请接口，但身份、proof、风险余额、现金/行业/stress裁决均未定；“没有CP申请”不等于新I联合候选没有申请。没有在本地重算held新I proof。','',
'父线程最小差分假说在此仅作纸面检查：首笔同机会可申请小风险本金；后续CP只产生申请，不自动再领固定NAV份额；真实保护合同前推减少的参考风险可供进一步预算审查。拒绝自动grant，不等于已经证明应拒整笔交易。未使用固定2/5/10%、1R/2R台阶或加仓次数；原股数/原预算只是事实，不移植到替代路径。','',
'风险的分母和时钟','',
'原budget真正使用的marked risk是Σq×max(当前raw close−有效guard/factor,0)，包含已有浮盈到保护线的给回，排除未来费滑点/跳空。另列含买费剩余basis与principal shortfall，不能将后者冒称全部风险。逐CLOSE“释放参考风险”只比较同价、同原实际股数下oldguard与saved postguard的差，不能把价格下跌、卖单pending、重发CP/newID或raw复权因子变化当保护进展。',
'所有替代数量、granted budget、unused risk balance保持UNKNOWN。原价差不是现金，不自动重置/复用；此前已用于风险扩张、已平层或其它股票的额度也不能重复花。替代若曾先行建仓，其股数/路径本已不同，不能借原320/5100股再宣称候选释放了多少钱。','',
'具体发现','',
'中船688146.SH属当前“电子化学品”，这里是半导体供给链例，不在task-4固定25半导体原层名单。2026-04-03已有原新E0/S21/S63和i_buy事件但CPfalse；对应本周期首个实际成交的4/21 mobile申请是既有结构新价格前沿，不是新I根，不冒称最早可申请日。4/22原买320股，含买费22193.51。',
'4/30再申请时，既有layer986的真实保护66.41132775697491→72.24011037628965（同调整坐标），同日CP候选匹配，原I floor仍41.548253366380614。固定原320股的同CLOSE marked risk从4827.76降为2994.79，参考差1832.97。它可以证明保护前推，不能证明新grant的数量。4/30 i_buy只是existing-structure price-frontier事件；5/6原实际买413股（4/30信号，假期后OPEN），含费33891.88，该日i_buy=False、CPfalse，属于旧冻结申请真实执行。',
'其I floor直到5/27才从41.548253366380614提高到128.34879248350688，6/18再到307.3125769445737；此前CP保护已多次前推。6/30两层仍持有733股，guard321.87596801351935，原marked risk24826.94；原财富+200572.21=未实现+200457.28＋股息AR114.9344，未兑现。不能用后来赢家标签认定4月申请当时已经成功。',
'盈新000620.SZ的原1/4、1/5是flat、Ioff且无真实退出请求，只能等待原资格，不虚构减仓。1/6新E0/S21启动原I，1/10是对应首个实际成交的CORE信号，不冒称最早可申请日；1/11买100股，随后mobile依次6300/5700/4200股。1/12、1/13 CP确实使已持mobile保护前推，并不只是重复新ID；这组仍在1/19触线、1/20实际卖，说明真抬线也不保证最后盈利。',
'1/20剩CORE100股的原I线2.255055048923375→3.4053609072125717，当日参考marked-risk减少101元。1/21新S21＋CP，但CORE保护不再推进，本日新增参考释放0；它只产生申请，不能凭CP自动恢复大mobile授权。此前是否还有未使用释放余额并未识别，不能武断宣布整单拒绝或给定股数。',
'1/24有新S63＋CP，已持layer113的保护3.553880661418941→3.904117953737246，固定原5100股参考风险减少1568.34；1/25两mobile进一步抬到4.296491617429432，原已持库存仍浮盈5251.58。该链最后仍亏17850.15，所以“新S21/S63确认＋保护推进＋浮盈”也不是事后认证的安全加仓条件；实时marked给回、stress和预算余额仍需另行定义。',
'退出时钟必须澄清：1/27 I仍on，原首请求是mobile CP保护卖113/122，非I退出。1/28、2/7原单仍未成交；2/7 Ioff才把CORE68并入原pending。最终2/8 09:30按raw OPEN2.77/卖价2.768615卖9900股，最终parts reason统一成I_structure_exit。不能把最终reason倒填为1/27 I退出；旧sealed十大链不改，这里提供逐日语义补充。1/27原marked-risk已夹到仅CORE约56元，mobile库存/损失仍在，绝不等于风险消失或现金释放。','',
'关键日索引（保护线为同一原因果调整坐标；风险只基于原股数）']
selected=[]
for name,dates in chosen.items():
 x=read(name+'_DAILY_PAPER_INPUTS.json');lines+=['',x['spec']['name']+' '+x['spec']['sid'],'日期 | i_buy / 原G1理由 | CP | 原持仓guard before→after | 原marked risk before→after / 参考减少 | 纸面判定']
 for d in x['days']:
  if d['day'] not in dates:continue
  gs='; '.join(f'L{l["layer"]}:{float(l["guard_before_CLOSE_check_adjusted"]):.6f}→{float(l["guard_after_original_CLOSE_adjusted"]):.6f}' for l in d['original_live_layers']) or '原路径flat'
  lines.append(f'{d["day"]} | {d["original_i_buy_event_for_exploration_interface"]} / {d["original_G1"].get("up_reasons") or "无"} | {d["original_CP_cache"].get("receipt")} | {gs} | {money(d["original_mark_to_guard_before_CLOSE"])}→{money(d["original_mark_to_guard_after_CLOSE"])} / {money(d["true_guard_advance_reference_risk_reduction"])} | {d["paper_decision"]}')
  selected.append(dict(sid=x['spec']['sid'],**d))
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n');(O/'KEY_DATES_FOR_REVIEW.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'}
(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('key readout completed:',len(selected),'key CLOSE days; all79 daily rows retained')
