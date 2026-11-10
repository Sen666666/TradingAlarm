from pathlib import Path
from decimal import Decimal as D
import json
O=Path(__file__).parent
read=lambda n:json.loads((O/('GATE_'+n+'.json')).read_text())
fmt=lambda v:f'{D(str(v)):,.2f}'
def tab(head,rs):return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(str(v) for v in r)+' |' for r in rs)+'\n'
a=read('ACTUAL_ENTRY_ROWS');summary=read('SUMMARY');timing=read('WAIT_TIMING_FOCUS');fixed=read('FIXED_OPPORTUNITY_SUMMARY');sector=read('SECTOR_SUMMARY');qa=read('REVIEW_EQUIVALENCE_QA');named=read('NAMED_MAINLINE_ROWS')
text='''# 固定 F OR 当轮 CP 入场门槛：一次本地可观测诊断

状态：DEVELOPMENT_DIAGNOSTIC / NOT_FROZEN / NO_PORTFOLIO_REPLAY。数据截止2025-01-20。未联网、未读受限外部来源、未导入或运行策略引擎、未改生产或冻结基线、未扫描其他公式/阈值。

## 结论

这个门槛确实改变资格，但本次证据不足以支持冻结。它并非“晚期差票被挡、主线照常进入”：晚期仍通过的209轮原路径净−75,348.14；全窗428个等待轮原路径净反而+25,800.72。9/24的28个MATURE只通过3个，25个等待原净+33,542.97；10/24光伏保留聚和、协鑫、钧达，但禾望、爱旭、新强联要等至10/25收盘新CP，最早报价检查通过为10/28OPEN，较原10/24OPEN贵10.85%—11.81%。这些是机会成本证据，不是反事实收益。

等待也不等于亏损永久消失。晚期等待组中湖南白银、东方明珠、光环新网等，一天后已有有效CP，仍可恢复结构资格。并且M降0、sector仍1时，门槛可能退出适用范围，回原RESIDUAL审查。不能把被挡原单的净亏直接记为可挽回收益。

## 1. 固定公式、原始身份与可观测口径

唯一公式：当前真实phase=MATURE的新SEED才应用 G=tri_or(原F, shadow_CP)。shadow_CP要求receipt_day >= original_signal_day，含信号当日；原EVENT/RESIDUAL、ADD和已有持仓退出均不变。未比较strict >、未追加等待天数、旧高、收益或保护线抬升阈值。

合同：mainline_structural_maturity_design_v1/DESIGN.md，SHA256 79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12。CP模型只读绑定 code/model.py，SHA256 85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf。输入与冻结产物按原SOURCE_HASHES/manifest逐一核验。CP身份使用独立ENTRY_CP namespace，绑定模型版本，而不是随源文件未来追加改变身份。

- 从原signal CLOSE开始维护单slot，不从首次MATURE或首次资金拒绝才开始。只读截至当时的原CP receipt，未重算/重启CP模型；旧signal以前的receipt不能继承。
- 当日receipt显式为真、candidate有限正、同源同调整尺度、CLOSE>floor才创建/替换；receipt当天不倒查早先OPEN。新receipt当晚已破则保留此前有效slot，不回退更老的低线。
- 后续任何可验证OPEN/CLOSE<=floor永久失效。单根反弹不复活；新有效receipt才可替换。未知价格/receipt更新缺口持久标U，不因次日receipt=False变T。
- 原I/stock/sector已知false或I保护破坏取消原票；source已知变化取消并清证据。未知source/因子/报价/当前I线暂停；明确未准入行动或桥接不符仍原BLOCK。纯现金桥接每天只核一次，CP连续尺度价线不再次乘因子。
- CLOSE冻结原F及CP，nextOPEN只重核此前证据、报价/source/I，不读该日收盘新receipt。F真可旁路CP未知/失效，但不能旁路原source/I/经济检查。
- 没有账户重放。waiting票只追踪原身份及可观察的结构/报价约束；未重新认证event spent、NAV预算、容量、dated lot、现金、排序、融资迁出或真实下单。M0/sector1仅标RESIDUAL scope恢复，不称已经成交。

CP是原波动尺度下的frontier推进，不是20日高点、回踩确认、原亏损修复或保证盈利。UP回撤时frontier不下降，未发生原I/e0_down重置时可能仍有收复旧峰的迟到成本。原F是真实行业快路径，不保证个股本身也有CP。

## 2. 全窗与晚期原路径分组

分母是原基线已成交MATURE轮，不是新账户全部潜在请求；损益是截至2025-01-20原路径含原ADD/退出/权益的轮级净值。闭合与末日未闭合分开，避免晚期等待组90个未闭合和通过组16个未闭合的构成混淆。

'''
rows=[]
for cohort in ['ALL_MATURE','LATE_MATURE']:
 for st in ['PASS','STRUCTURE_WAIT','UNKNOWN_GATE']:
  rs=[r for r in summary if r['cohort']==cohort and r['status']==st];d={r['state']:r for r in rs}
  rows.append(['全窗' if cohort=='ALL_MATURE' else '11/7—1/20',st,d['ALL']['rounds'],fmt(d['ALL']['net']),f"{d['CLOSED']['rounds']} / {fmt(d['CLOSED']['net'])}",f"{d['OPEN']['rounds']} / {fmt(d['OPEN']['net'])}"])
text+=tab(['原OPEN集合','计划CLOSE分类','轮数','原净损益','已闭合数 / 原净','未闭合数 / 原净'],rows)
text+='''
全窗401个CLOSE通过中，397个原nextOPEN仍通过新门槛及报价/I/source检查，4个CP在原OPEN被打破，需等待而不是购买。上表保留计划CLOSE分类，未把这4个偷偷从PASS净值扣掉。晚期209通过中，67是F与CP都真、19只靠F、123只靠CP；不存在“有CP就可免于晚期本金亏损”的证据。全窗97个靠CP或双通路通过的receipt恰在原signal当日，不能叫额外经过一轮验证。

## 3. 9/24启动与光伏固定机会集

所有窗口按原实际OPEN日，非计划CLOSE日。包含窗口内全部原SEED，不按后来盈利或ADD选股。原seed_cost是实际BUY_SEED现金支出（−cash_delta），不是无费用名义金额。

'''
text+=tab(['固定原OPEN窗口','分类','原轮数','原净损益','原SEED现金支出'],[[r['cohort'],r['status'],r['n'],fmt(r['original_net']),fmt(r['original_seed_cost'])] for r in fixed if r['state']=='ALL'])
text+='''
上述固定窗口所有轮截至末日均已闭合；JSON/CSV保留CLOSED/OPEN分层。

- 9/24 OPEN共64个原SEED：36 EVENT不受此门槛改变；28 MATURE全部只能用9/23及以前收盘证据，其中3通过、25等待。通过原现金支出22,669.77，等待190,077.10。等待25轮原净+33,542.97。9/24收盘出现CP最早只能救9/25OPEN，不能替9/24单辩护。
- 9/25 OPEN共35个原SEED：3 EVENT不改；32 MATURE中23通过（原净+17,023.97）、5等待（+3,977.26）、4未知（+1,248.08）。4未知全为F=-1、CP=0，非CP数据缺失，不补False。
- 常山北明、拓维信息、银之杰在9/23 CLOSE→9/24 OPEN的实际轮都属EVENT，因此本门槛不改变其初始资格，原净分别+32,513.29、+19,147.37、+10,982.60。保留这三只不能代替对其余25个MATURE机会成本的交代。
- 10/24光伏30个MATURE全部原S-only：23通过原净+22,435.28，7等待+12,922.79。更宽的事前固定10/23—29窗口多1个MATURE等待及3个EVENT，已完整包含在上表。

10/24光伏大赢家的原计划CLOSE为10/23：
'''
focus=[r for r in named if r['seed_day']=='2024-10-24' and r['phase']=='MATURE']
text+=tab(['股票','初始分类','原净损益','截至10/23已有效CP确认日','连续调整尺度CP价线'],[[r['name'],r['gate_status'],fmt(r['net']),r['CP_receipt_day'] or '无',r['CP_floor'] or '无'] for r in focus])
text+='''
## 4. 延迟、降级和原false取消必须分开

下表“最早OPEN”仅表示从前一CLOSE生成新候选后，报价/I/source及本门槛可恢复审查，不表示有可用event额度、资金或可执行买单。价格差为同尺度OPEN价格差，不是策略收益。路径始终假定原票仍未成交，故后来取消日期是该未成交票路径的终点，不是强行搬用原已持仓退出。

'''
keep={'新华保险','大名城','新城控股','浦东金桥','新国都','西部矿业','禾望电气','爱旭股份','新强联','先导智能','东方明珠','湖南白银','光环新网','长沙银行','中文在线','太极实业','金龙鱼','神农集团','沪农商行'}
rr=[]
for r in timing:
 if r['name'] not in keep:continue
 e=r['first_quote_I_source_and_gate_eligible_OPEN']
 rr.append([r['name'],r['baseline_actual_OPEN'],r['first_G_true_CLOSE'] or '无',r['first_reclassified_RESIDUAL_CLOSE'] or '无',r['first_original_false_cancellation'] or '无',e['next_OPEN']+' '+e['scope'] if e else '无',fmt(e['open_vs_original_pct'])+'%' if e else '无'])
text+=tab(['股票','原OPEN','首次G真CLOSE','首次RESIDUAL CLOSE','原false取消','最早可恢复审查OPEN','较原OPEN价差'],rr)
text+='''
特别是太极实业11/11收盘M=0但sector=1，G仍未真，也已退出MATURE门槛适用范围；11/12OPEN只恢复原RESIDUAL审查，11/12收盘原false取消。金龙鱼同理。不能强制它们永远等G，也不能把RESIDUAL scope标签等同于原event/现金认证。

湖南白银原12/12轮净−3,598.68、东方明珠原12/11轮−3,277.35、光环新网原12/13轮−3,050.28都不是“挡掉就永久避开”：新CP很快出现。中文在线的两张票则在无G/RESIDUAL恢复前分别于12/3、12/16原false取消。两种路径应分别报告。

三个真实日线序列（完整逐日、OPEN检查和receipt日志见WAIT_TIMING_FOCUS）：
'''
for name,day,limit in [('大名城','2024-09-24','2024-09-25'),('禾望电气','2024-10-24','2024-10-28'),('湖南白银','2024-12-12','2024-12-13')]:
 r=next(r for r in timing if r['name']==name and r['baseline_actual_OPEN']==day)
 text+=f"\n### {name}：原signal {r['original_signal_day']}，原计划CLOSE {r['baseline_plan_CLOSE']} → 原OPEN {day}\n\n"
 pp=[p for p in r['path'] if p['phase']=='CLOSE' and p['day']<=limit]
 text+=tab(['CLOSE日','原base','M/F','CP状态','确认日 / 连续价线','结果'],[[p['day'],p.get('base'),str(p.get('M'))+'/'+str(p.get('F')),p.get('CP_state','取消'),str(p.get('CP_receipt_day') or '无')+' / '+str(p.get('CP_floor') or '无'),p.get('reason') or ('可恢复原审查' if p.get('ready_for_original_eligibility_review') else '等待或未知')] for p in pp])
text+='''
## 5. 晚期主要亏损行业的MATURE子集

行业顺序取954个新轮的原净损失排序，再展示其中MATURE，不混淆954全phase与479 MATURE。其他phase未被新门槛筛掉。

'''
rank=json.loads((O/'STRUCTURE_LATE_INDUSTRY_RANK.json').read_text())
ss=[]
for r in rank[:10]:
 s=r['sector51'];z={v['status']:v for v in sector if v['sector51']==s and v['state']=='ALL'}
 ss.append([s,fmt(r['all_954_net']),str(z['PASS']['rounds'])+' / '+fmt(z['PASS']['net']),str(z['STRUCTURE_WAIT']['rounds'])+' / '+fmt(z['STRUCTURE_WAIT']['net'])])
text+=tab(['行业','954新轮行业原净','MATURE通过数 / 原净','MATURE等待数 / 原净'],ss)
text+='''
游戏传媒通过组原净为正而等待组亏，医疗服务、证券保险的多数或全部MATURE亏损却仍通过。行业表现不一致，不足以把F或CP讲成统一的退潮识别器，也不据分组好坏另选公式。

## 6. 计划通过但nextOPEN破位的4单

'''
failed=read('NEXT_OPEN_FAILED_ROWS')
text+=tab(['股票','计划CLOSE','原OPEN','CP确认日','CP价线','OPEN调整价','原轮净'],[[r['name'],r['plan_day'],r['seed_day'],r['CP_receipt_day'],r['CP_floor'],r['actual_next_OPEN_check']['adjusted_open'],fmt(r['net'])] for r in failed])
text+='''
这4单原I检查尚未取消，只有新CP失效，故应回结构等待；若把新门槛拒绝套进旧“非资金拒绝即取消”，会改变已固定状态机。四个未成交票在该日CLOSE又遇原false取消，未再出现可恢复的下一OPEN。

## 7. 审查修复与覆盖证明

修复不改变公式，只修持久未知、Q0暂停/已知false取消、当前I线必须已知、明确模型版本和source取消清slot。修前结果保存在GATE_PRE_REVIEW_SNAPSHOT.json。

- 原49份已有诊断逐一SHA256核对，全部未变。STRUCTURE来源归因另已完成，没有重写。
- 833个实际MATURE逐一比对gate_status、CP_state、receipt日、floor、通路与原nextOPEN检查，差异0。26个重点等待票首次G、首次RESIDUAL、原false取消、最早可恢复时点/价差差异0。
- 全部原signal→plan覆盖1,952票×CLOSE、1,119中间OPEN；计划通过401个原nextOPEN也检查。receipt/source/factor/当前I线/报价缺失边界计数均0，而非仅凭末日4个UNKNOWN推断中间日完整。
- 26票延伸至取消覆盖162 CLOSE、136 OPEN；原state未知4次单列，包含10/29光伏sector未知，不能笼统说所有状态都已知。CP更新/报价/source/factor/I线边界仍0。
- GATE_SYNTHETIC_QA.json的22个人工状态回归全部PASS，使用诊断中的同一函数，不是重跑市场模型。覆盖未知更新在有/无slot时持久、nextOPEN永久破位、新receipt当日不倒查OPEN、低新线替换、已破新receipt不替换旧线、当前I缺线暂停、未知source/因子/缺行、已知I false优先、桥接一次与不双倍调整、模型hash身份等。不是完整账户引擎接入验收。

审查保留的实现限制：这只是当前完整源链样本的描述诊断，不是通用Q0链实现。lin辅助函数没有覆盖原known_origin的全部文本哨兵语义；桥接辅助函数只核当日action，没有实现缺报价日action_inventory到恢复日的完整区间追踪。若合法除息发生在缺factor日、次日新factor恢复，此辅助函数可能误报BLOCK，不能用于候选执行。追加逐行核查实际使用的3,634个去重sid/day/OPEN或CLOSE（2,054 CLOSE、1,580 OPEN），文本unknown/None/null/nan/NA等源哨兵和缺报价/因子均0，见SOURCE_SENTINEL_COVERAGE；本次分类不受该未覆盖通用边界影响。真正候选必须继承原Q0，不复制该辅助函数替代原链。22个合成测试没有证明跨缺口行动链。

## 8. 交付与限制

主要入口：GATE_READOUT.md；完整833行ACTUAL_ENTRY_ROWS；固定窗口FIXED_OPPORTUNITY_ROWS；重点26票WAIT_TIMING_FOCUS；全/晚期SUMMARY及SECTOR_SUMMARY；命名主线NAMED_MAINLINE_ROWS；CP_LIFECYCLE；INPUT_COVERAGE、REVIEW_EQUIVALENCE_QA、SYNTHETIC_QA与SOURCE_HASHES。机器文件同时提供JSON/CSV。

该小窗已经被观察，属于开发诊断，不是样本外。没有NAV闭环、现金重分配、真实捕获率、反事实ADD或donor迁出验证。原路径分组损益不能相加减成新策略收益；最早候选恢复价格也不是保证可成交价格。当前不冻结、不据此启动历史账户引擎；保留不利主线延迟和快路径亏损反证供复核。
'''
(O/'GATE_READOUT.md').write_text(text)
print('GATE_READOUT.md',len(text),'characters')
