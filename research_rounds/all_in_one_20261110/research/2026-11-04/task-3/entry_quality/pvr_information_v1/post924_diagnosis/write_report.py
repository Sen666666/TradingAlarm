"""Present previously computed descriptive tables, no new selection/filter."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def m(v):return f'{D(str(v)):,.2f}'
def pct(v):return f'{D(str(v))*100:.2f}%'
s=read('CORE_TABLES.json');r=read('ALL_JOINED_LAYER_ROWS.json');ov=read('DESCRIPTIVE_CENTRAL80_OVERLAP.json');pairs=read('SYSTEMATIC_TOP10_AND_TAIL_CONTROLS.json');own=read('POST_OWN13_TAIL_CONTROLS.json');p=s['post303'];t=s['strong_tail123'];ordinary=s['strong_ordinary1048'];post=[x for x in r['2022_2024'] if x['opened'][:10]>'2024-10-08'];tails=[x for x in r['strong'] if D(x['net'])/D(x['cost'])>=D('.3')]
lines=['结论：原303层主要损失呈现为入场后较快失败，但现有事前字段尚无可靠分界；本线不提出新交易规则。','',
'全部沿原No60 BASELINE、原3436实际层与已审持有/退出/source语义；0新导出、0模型重算、0金融账户。这个结论没有把模型授权合法当作真实趋势正确，也没有把亏损退出的reason当因果归因。短持有、首CP触发、最终尾部均是评价标签，不能反向门控入场。','',
'母体和已实现/未实现口径','',
'303严格为2024-10-08之后actual OPEN填单的原新增层，204股、65行业、累计买款2839637.22（周转，不是同时暴露）；219负层毛负−219220.96，84正层毛正+106763.36，净−112457.60，分摊实际买卖费4464.44。全部303至原2024-12-31已平；贡献仍按原已实现/股息AR口径，不称全为即时可用现金。',
'P10整个账户还含75旧库存层阶段财富−54596.72，不能把303新增层净额冒称整段账户损耗；桥在P10_NEW_VS_OLD_COHORT_BRIDGE.json。',
'强窗是独立初始100万元的2025-07-01—2026-06-30原1171层，净+1263281.23。实际原净贡献/自身买款>=30%的123层（85股、44行业）贡献+1676775.12；其中91已退出，32仍开仓，32贡献+789300.56是截止日原mark财富，不是已兑现现金。其余1048普通层净−413493.88。123与普通分组是事后评价分母，非可交易名单。303自身13尾贡献+50390.52全部保留，不可把整个post日期区间直接设成不可买。','',
'一、首先拆动作，不能统称为重复重入','',
'动作/角色 | post层数 | post毛负 | post毛正 | post净额 | strong尾层数/贡献 | strong普通层数/净额']
for k,v in p['by_role_action'].items():
 a=t['by_role_action'].get(k,{});b=ordinary['by_role_action'].get(k,{})
 lines.append(f'{k} | {v["layers"]} | {m(v["negative"])} | {m(v["positive"])} | {m(v["net"])} | {a.get("layers",0)}/{m(a.get("net",0))} | {b.get("layers",0)}/{m(b.get("net",0))}')
lines += ['', 'mobile first53层毛负56838.93，说明同股旧失败/重入门本来不能覆盖全部；mobile add85和reentry112也各有实质正贡献，不能把它们整体当坏行为。','',
'二、损失集中于较快失败，且多数不是后来ratchet过快','',
'评价组 | post层数 | 毛负 | 毛正 | 净额 | 303毛负覆盖']
for k in ['POSTHOC_held_CLOSE_at_most5','POSTHOC_primary_CP_request','POSTHOC_primary_CP_at_most1_held_CLOSE','POSTHOC_primary_CP_at_most5_held_CLOSE','POSTHOC_primary_CP_unchanged_entry_line','POSTHOC_primary_CP_short5_unchanged_entry_line']:
 v=p['predicates'][k];lines.append(f'{k} | {v["layers"]} | {m(v["negative"])} | {m(v["positive"])} | {m(v["net"])} | {pct(v["negative_money_coverage"])}')
lines += ['', '152层持有<=5个真实已持CLOSE，其中139负层亏165083.09，占303毛负75.30%；其余151层净+44730.13。强窗普通层中也有338短持层净−470089.06，短期失败不是post独有。强尾123全>5个CLOSE只是幸存结果，不能要求先等5天再入；旧统一小首仓/高点等待/5日反馈的赢家代价保留。',
'短期CP负82层亏132138.54，其中61层自entry到触线没有保护线抬升，亏108898.34，占该82层损失82.41%；后抬的21层亏23240.20。因此不能将主损失解释为后续CP ratchet普遍过快，更不能等待事后ratchet证明后才给仓位。未抬线组亏损本就与entry价高于出场保护有关，机械后验关系不是新信号。',
'16层在第一个已持CLOSE便请求CP，亏33926.12（303毛负15.48%）；信号t CLOSE→填单下一合法OPEN→首次触线CLOSE→随后OPEN的时钟不能倒填。303中301层在原请求后的下一native session OPEN退出，只有2层延后一步，合计净−4099.95；执行延迟不是普遍解释。实际成交约束原样保留，未计算能避损多少。','',
'三、原授权合法有效，但不等于真实趋势或未来收益有效','',
'事前状态关联 | post层数/毛负/正贡献 | strong尾层数/正贡献']
for k in ['original_I_target_on','original_E0_target_on','I_buy_now','mobile_fresh_CP_new_unconsumed_frontier','mobile_same_CLOSE_I_buy_and_CP','no_new_industry_receipt_at_decision','same_industry_auth_as_prior_actual_buy','no_new_industry_receipt_since_prior_actual_buy','mobile_CP_formation_before_prior_actual_fill','actual_fill_nominal_risk_exceeds_frozen_full_plan','fill_open_above_decision_close']:
 a=p['predicates'][k];b=t['predicates'][k];lines.append(f'{k} | {a["layers"]}/{m(a["negative"])}/{m(a["positive"])} | {b["layers"]}/{m(b["positive"])}')
lines += ['', '303当日原I/E0均on；250个mobile均有canonical fresh CP与新未消费前沿，235同时有原I_buy当日事件。I_buy常是既有S21结构内当日新价格前沿，并不等于独立新I段。其余15个mobile通过persistent I仍是原授权合法路径；去掉I_buy=False并未获得本线经济证据。',
'G1仅既有结构价格前沿来源的post209层净−108509.41，同时strong123尾中101层来自同类，不能把源类型当坏信号。行业扩张stage的post209层净−110458.88，虽集中但strong尾也有80层在expanded、贡献+1158078.74；扩张标签不能当风险门。','',
'四、行业分散/许可延续与当日量价背景','',
'303实际买款跨65行业，买款行业HHI='+str(round(float(p['filled_industry_concentration']['cost_HHI']),6))+'；45个实际出资决策日，每日实际被填行业数中位5。毛负最多五行业为IT服务20317.22、半导体16513.63、软件开发15167.85、文化传媒12666.69、电池8757.10，合计仅覆盖303毛负约33.49%；最大正贡献行业通信设备+22713.87。分散后的失败不等于单一行业集中度问题。',
'这里只统计实际被原资金/排名选中并填单的分散与扩张，不是全市场eligible信号扩散宽度。全候选行业/个股可融资扩散没有本轮现存逐层关联字段，保持UNKNOWN，不从303实际fills倒造市场广度门。',
'行业最后receipt age中位：post303=3个原有效观察、strong尾=2；CP scale冻结到确认中位二者均2。42个post mobile形成锚早于上一实际填单，但有新canonical前沿；strong尾同条件20层+308162.34。行业授权本来允许多个独立个股CP共享背景，不因此构成重复消费凭据。',
'当日r<0但E>0在post303为0，量额平滑正而纯价平滑非正在post也为0。旧confirmed-mobile“历史背离后freshCP”精确复得post223净−85273.69、strong683净+888637.86；本表包含probe的全部mobile为236/753，不能混分母。持久背离锁已失败，不重复包装。','',
'事前数字（post负219 vs strong尾123）；没有按结果挑阈值','',
'字段 | post负p10/median/p90 | strong尾p10/median/p90 | post毛负在尾中央80%范围内 | 尾正贡献在post负中央80%范围内']
for k,v in ov.items():
 fmt=lambda vals:'/'.join(f'{a:.5g}' for a in vals)
 lines.append(f'{k} | {fmt(v["loss_p10_median_p90"])} | {fmt(v["tail_p10_median_p90"])} | {pct(v["loss_negative_money_inside_tail_central80"])} | {pct(v["tail_positive_money_inside_loss_central80"])}')
lines += ['', 'PVR score与E是同一单调变换，不能当两条独立证据。PVR负层中位89.93甚至高于强尾88.67；量额倍数m负层1.439与强尾1.379、日r与CPcredit也重叠。mobile保护log距离/usedscale中位两者均sqrt(21)，多数是原保护公式的机械结果。固定中央80%仅描述重叠，不构成阈值扫描、预测准确率或可回避损失。当前字段并未提供“更高分、更强量或更老授权就应减仓”的单调依据。','',
'五、金额最大的原完整campaign及同类真实赢家（全部名单保留）','',
'亏链/新层净贡献 | 最大负贡献层(动作/持有CLOSE/退出) | 同行业+动作尾部对照（无同业则注明）']
for pair in pairs:
 a=pair['selected_loss_largest_contributor'];b=pair['tail_control'];lines.append(f'{a["name"]} {pair["post_campaign"]} / {m(pair["post_campaign_new_layer_contribution"]["net"])} | L{a["layer"]} {a["simple_action"]}/{a["held_close_observations"]}/{a["actual_exit_class"]}, {a["decision_at"][:10]}→{a["opened"][:10]}, {m(a["net"])} | {b["name"]} L{b["layer"]} {b["opened"][:10]} {b["simple_action"]}, {m(b["net"])} ({"OPEN mark" if b["closed"] is None else "closed"}; {pair["control_match_scope"]})')
lines += ['', '这十链按全部post新增层的campaign净贡献排序，避免把同次退出多层当独立失败次数；同campaign若含10月8日旧层，其旧贡献不混入303，原完整层ID与P10阶段财富仍保存。配对只用于反例评价，不是以未来赢家选股。SYSTEMATIC_TOP10_AND_TAIL_CONTROLS.json保留完整原信号/CP/请求线/时钟/规模字段。13个post自身尾也单独完整保存。','',
'裁决与可证伪边界','',
'当前最大的现象是“原模型看起来很强且允许出资，随后较快失败”，而非普遍权限非法、当日r负却被E掩盖、sector单一集中、原CP后来太快收紧或退出执行普遍拖延。它尚未被现有事前字段分离出来；亏损标签也不能证明买入方向在当时可识别为错、或把卖出reason当作错误退出。',
'本线裁决 NO_NEW_ENTRY_MECHANISM_SUPPORTED，0新规则/账户。不会拿短持有、首CP、无ratchet的后验优势拼成门，不复活统一CORE缩量/旧高等待、同股连败、5日反馈、旧价格前沿来源过滤、formation撤权、量价符号或持久背离、D10 P1/P2行业票据预算。P1/P2另有不同D_GROSS10原母体，不能把其227mobile混成此No60的250mobile。',
'下一项有证据的问题仅是信息测量：原PVR/E与CP承认的“强”可能对应不同的价格推进持续性/正贡献集中程度；这不是已经获支持的新交易机制。根线程已冻结的新增信息分量全母体分析会检验该区别，须同时保13 post尾、123强尾、1048普通层、全部UNKNOWN和真实资金竞争。如果新分量仍广泛覆盖真实早启动赢家，或只在已看日期/少数大亏上有利，停止，不调窗口/阈值硬救。根新特征尚未回本线，不对它们报效果或临时另造第二条门。',
'', '限制：当前存续池及当前行业快照非历史PIT，实盘竞价/涨跌停及真实容量边界沿原日线代理；32强尾open按截止日mark。所有亏损覆盖与赢家代价为原路径描述关联，非策略收益、可用释放资金或账户因果归因。']
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'}
(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('wrote report, top10 campaign pairs and all13/123 tails retained')
