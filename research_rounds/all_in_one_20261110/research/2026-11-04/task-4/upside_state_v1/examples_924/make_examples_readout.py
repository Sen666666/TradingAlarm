"""Format already saved nine actual layers and61 snapshots; no new indicators."""
from pathlib import Path
from decimal import Decimal as D
import csv
import hashlib
import json

O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

chains=read('ACTUAL_NINE_LAYER_CHAINS.json')
snapshots=read('FINITE_KEYPOINT_SNAPSHOTS.json')
lookup={(x['sid'],x['day']):x for x in snapshots}
rows=[]
for ch in chains:
    t=ch['original_buy'];sid=ch['sid'];signal=t['signal_at'][:10];entry=t['at'][:10]
    exitday=ch['exit_proposals'][0]['at'][:10];sell=ch['actual_sells'][0]
    sig=lookup[sid,signal];ent=lookup[sid,entry];ex=lookup[sid,exitday]
    rows.append(dict(name=ch['name'],layer=ch['layer'],original_role=ch['original_role'],
        actual_entry_category=ch['actual_entry_classification']['classification'],
        signal_CLOSE=signal,buy_OPEN=entry,qty=t['shares'],buy_fill=t['price'],
        original_entry_reason=t['reason'],first_exit_CLOSE=exitday,
        sell_OPEN=sell['at'][:10],sell_fill=sell['price'],original_exit_reason=sell['selected_part']['reason'],
        terminal_net_contribution=ch['terminal_net_contribution'],
        signal_progress=sig['finite_descriptors']['exploratory_price_progress_C_HC20_EMA20_rising'],
        buy_day_CLOSE_progress=ent['finite_descriptors']['exploratory_price_progress_C_HC20_EMA20_rising'],
        exit_CLOSE_above_EMA20=ex['finite_descriptors']['current_close_above_EMA20'],
        exit_CLOSE_EMA20_rising=ex['finite_descriptors']['EMA20_rising_one_observation'],
        signal_BB20_cross=sig['saved_price_features']['bb20_cross']))
with (O/'ACTUAL_CHAIN_TABLE.csv').open('w',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
failed=[x for x in rows if D(x['terminal_net_contribution'])<0]
win=[x for x in rows if D(x['terminal_net_contribution'])>0]
flat=[dict(sid=x['sid'],name=x['name'],day=x['day'],raw=x['raw_ohlcv'],prev_CLOSE=x['prev_raw_close'])
      for x in snapshots if x['flat_day_proxy']]
vshape=[lookup[('300339.SZ','2024-10-11')],lookup[('688593.SH','2024-10-14')]]
summary=dict(scope='Only parent-named outcome-selected5 examples,9 actual layers and61 finite snapshots; no universe screening, new permission, order, account or strategy result.',
    fixed_descriptor='D_t := same-source known20 prior CLOSEs AND C_t > max(C_(t-20)..C_(t-1)) AND C_t > EMA20_t AND EMA20_t > EMA20_(t-1). EMA60 and BB are context only; D is not a first-entry AND gate and not an exit override.',
    actual_layer_rows=rows,
    sample_observations=dict(all_9_actual_entry_signal_days_progress_true=all(x['signal_progress']for x in rows),
        all_6_losing_layers_entry_day_CLOSE_progress_false=all(not x['buy_day_CLOSE_progress']for x in failed),
        all_3_HaiNengDa_layers_entry_day_CLOSE_progress_true=all(x['buy_day_CLOSE_progress']for x in win),
        all_6_losing_layers_CP_exit_still_above_EMA20_and_EMA20_rising=all(x['exit_CLOSE_above_EMA20']and x['exit_CLOSE_EMA20_rising']for x in failed),
        all_9_actual_entry_signal_days_BB20_fresh_cross_false=all(not x['signal_BB20_cross']for x in rows)),
    flat_day_examples=flat,
    V_shape_known_day_examples=[dict(name=x['name'],day=x['day'],raw_CLOSE=x['original_fields']['raw_close'],
        prior_CLOSE=x['prev_raw_close'],prior20_close_high_raw_equiv=x['finite_descriptors']['prior20_close_high_raw_equivalent'],
        I_buy=x['original_fields']['i_buy'],CP_receipt=x['original_CP1_fields']['receipt'],
        progress=x['finite_descriptors']['exploratory_price_progress_C_HC20_EMA20_rising'])for x in vshape],
    limits=['These observations cannot estimate general signal precision, strategy return or a new order quantity.',
        'No historical peak/final price is used in D; future net contribution is evaluation only.',
        'No real slow-bull sample was selected: a slow recovery that remains below a previous20-close high can have D=false despite E0/I/EMA remaining healthy. This is a logical coverage gap, not a measured failure rate.',
        'Flat daily bars are rejected by original execution proxy; actual historical limit queue/depth is unavailable. Earlier funding rejection and execution unavailability must not be conflated.',
        'CP-triggered Mobile exits are binding actual protection contracts. A separate structural I signal for Core is not authority to substitute its broader line for Mobile.',
        'Candidate finite-stage permissions, target quantities, stage consumption, risk budgets, stress charge and executable-order legality are not defined or simulated here.'])
save('KEYPOINT_FINDINGS.json',summary)
save('EXTRACTION_CHANGELOG.json',dict(
    initial_saved_extraction=dict(seconds=5.581348874606192,snapshots=58,limitation='Incorrectly attempted historical exit lookup in final B.exits map, which is empty after flattening; no new finance run.'),
    corrected_saved_extraction=dict(seconds=5.592652167193592,snapshots=61,correction='Historical CLOSE exit proposals read from original B.audit pilot_layer_exit records. Required exit-proposal dates added for all9 layers.'),
    schema_inspection_errors=['Read-only schema probes encountered empty B.exits and stopped with KeyError/StopIteration; no data mutation or finance object.'],
    extraction_compute_seconds_total=11.174001041799784,
    new_accounts=0,new_backtests=0,new_parameter_tests=0))

table=['股票/层 | 原角色/数量 | 实买OPEN→实卖OPEN | 原退出 | 实际层净贡献元 | 买后当日D',
       '--- | --- | --- | --- | --- | ---']
for r in rows:
    table.append(f"{r['name']}/{r['layer']} | {r['original_role']}/{r['qty']} | {r['buy_OPEN']}→{r['sell_OPEN']} | {r['original_exit_reason']} | {D(r['terminal_net_contribution']):.2f} | {r['buy_day_CLOSE_progress']}")
text='''924上行收益端：5个指定样本的有限事实快照（不产生新策略结果）

核心结论
原入口不应简单再加“站上EMA/20日收盘新高”当万能确认：这9个实际买入层的原信号日
都满足当前价格推进D，六个亏损层也全部满足。另一个时间点有可复核差异：三笔海能达
在实际买入当日CLOSE继续推进，六个亏损层的买入当日CLOSE均不再推进。但样本由已知
结果指定，不能把9层的分离当胜率/收益改善证据，也没有计算任何可新增单。

固定描述量及钟
D(t) = C(t)>max(C(t-20)..C(t-1)) 且 C(t)>EMA20(t) 且 EMA20(t)>EMA20(t-1)。
20个为前20个同源已知收盘，不是日内high，不包含当前t；未知/跨段不给D。
EMA/BB直接复用已审PRICE_FEATURES，EMA adjust=False、alpha=2/(n+1)、同源完整历史
为种子并至少n观察预热。BB前上轨为t-20..t-1收盘均值+2总体标准差，fresh_cross
还要求前一收盘不在其前上轨外。数值从原facts权息坐标比较，表内raw等价仅为阅读。
D在t真实收盘后才已知，最早t+1实际OPEN讨论增量；不使用t+1 high/low/volume触发。
原E0/I/CP授权和实际风险/现金/执行门是其它独立条件，D不是首入AND门，也不覆盖退出。
EMA60仅上下文，不能借此给V形首入额外迟滞；不把BB fresh cross重新加到首入。

真实链小表（layer净cash+已确认dividend含费用，不是反事实收益或全部已付现金）
'''+ '\n'.join(table)+'''

赢家的早期小仓与真实资源限制
海能达1994在10/14 CLOSE形成I_early_core，10/15 OPEN仅100股@8.90445；10/15、
10/16收盘均继续D=true且CP有新收据，但10/16、10/17 OPEN实际资金日志分别为
probe_risk。10/18收盘信号才在10/21 OPEN以confirmed池加1100股@12.006，
10/21收盘信号又在10/22 OPEN加1000股@14.007。10/23、24、25、28 OPEN后续Mobile
申请又是sector_capital+sector_risk；10/30另有probe_risk，11/1还包括现金。
这些是实际拒因组合，不能冒充先后第一约束。趋势状态不能创造风险或行业容量；
没有证明新机制能更早合法加仓。每天D或CP重复出现也不能自动无限刷新加仓档。
10/17、10/28、10/30的D=true而CP receipt=false，说明二者不是逐点同一个事件；
是否比旧CP预算合同额外有效仍需排重与约束审核，这里未宣称新发现可增加收益。

原CP快线与I结构的同股对照
海能达两Mobile在11/4 CLOSE因CP快线退出：raw C22.84，实际Mobile线约23.6377；
此时I_target/E0仍true，EMA20 raw等价17.1609且仍上升。11/5 OPEN卖Mobile2100股，
fill22.9885，两层净贡献12055.58和8958.04。原Core100股仍持有，初始I线raw7.58，
直到11/26 E0/I失效，11/27 OPEN以18.37081退出，净贡献935.54。
这是不同角色真实合同及仓位路径，不能据“EMA还在”判Mobile卖错；后来实际Core
成交价更低也不能直接替代Mobile的反事实账。将Mobile改用I宽线属于改变风险责任。
六个亏损Mobile在各自CP退出时也仍C>EMA20且EMA20上升；EMA持有若覆盖CP会延后
真实失败退出。CP在原策略是实际生效的保护，名称“快线”不等于可合法软化；原初始
硬线、I/ACT、已锁退出优先级须由独立合同审核，这里不撤单、不改保护线。

反例与覆盖边界
银之杰/润和/软通/新相微10/9入场信号全部D=true，次日落入失败链，说明只看首入
日的价格推进无法识别假突破。新相微10/18、润和10/21又D=true，分别真实再入仍亏
1980.09和1424.71，不能将第一次失败归咎于一次凭据并忽略后续失败。
V形：润和10/11 C50.38相对前收43.05反弹，但低于此前20收盘高53.81；原I_buy与
CP新收据均true，D=false。新相微10/14 C17.47相对前收15.16反弹，仍低于20收盘高
18.14，原I_buy与CP true，D=false。D会晚于这种V形早期授权；这不等于损失全部可赚。
早启动：海能达9/23 C4.76、EMA20约3.940、EMA60约3.963，D已经true而EMA20<EMA60；
机械EMA20>60硬门会漏掉该点。它也不代表当日/次日能买到。
慢牛：这5股不能代表慢牛。若温和恢复仍低于窗口旧高，D可能连续false，即使原E0/I
与EMA健康；所以D=false不能自动剥夺已有健康持仓。这里未抽取真实慢牛/完整V形
全样本，没有测其漏加仓/等待成本，保持字段缺口而不临时挑有利股票。

买不到的边界
海能达9/23、9/24、10/29，银之杰9/30与10/8，润和10/8与10/9，新相微10/8，
原OHLC为H=L且相对前收上涨的一价日；原日线代理会拒窗口。海能达9/24实记行业
失效在前，不能把它所有早期未成交归为涨停。非一价日也没有真实涨停排队/深度
证据；技术D=true和一根未来日线的价格不能倒推实际能按收盘或开盘无限买入。
海能达所列关键点及9个真实入场信号的BB fresh_cross均为false；润和10/11、新相微
10/14的反弹点则为true。已持续在上轨外不等同“今天刚穿上轨”，新cross也不等同
20收盘新高。这是避免旧BB首入AND重做的局部例证，不是新消融。

交付与缺口
ACTUAL_CHAIN_TABLE.csv列9层的信号—实际成交—退出提案—实际退出；KEYPOINT_TABLE.csv
及FINITE_KEYPOINT_SNAPSHOTS.json保留61点原E0/I/CP、已算EMA/BB、实际持层保护线、
原始OHLCV及D的20个历史输入日期。SAVED_KEYPOINT_FUNDING/OPPORTUNITIES保留实际
资格与资源拒因。SOURCE_SHA256绑定原账、facts、CP、raw、已审特征源。
尚未定义有限目标档、一次状态消费、授权寿命、可执行保护/压力和加仓数量，不提供
新单或新收益。数据仍有当前成分回溯/退市缺口、原日线执行代理及真实队列未知限制。
本次原账只读提取2次共11.174秒，首次误取期末空pending-exit map，已改读历史audit
退出提案并补3个关键点；无Account/Runner/Market/RiskBook、账户回放、参数测试或新回测。
'''
(O/'READOUT.txt').write_text(text)
files=[p for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json']
save('OUTPUT_SHA256.json',{p.name:sha(p)for p in sorted(files)})
print(json.dumps(dict(actual_layers=len(rows),finite_snapshots=len(snapshots),negative_layers=len(failed),positive_layers=len(win),new_accounts=0)))
