"""Render saved evidence and two design hypotheses; no selector/account call."""
from pathlib import Path
from decimal import Decimal as D
import json, gzip, hashlib

O = Path(__file__).resolve().parent
R = O.parent

def read(p):
    p = Path(p)
    return json.loads(gzip.open(p, 'rt').read() if p.suffix == '.gz' else p.read_text())

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')

def main():
    batches = read(O / 'THREE_BATCHES.json')
    middle = read(O / 'MIDDLE_TIMELINE.json')
    b = batches[0]
    op = R / 'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-18-OPEN.json.gz'
    lp = R / 'g-s-C-August-continuation-v1-20261102/analysis/C10-LAYERS.json'
    state = read(op)
    layers = read(lp)
    new = {z['sid']: z for z in layers if z['opened'][:10] == '2025-08-18'}
    positive_q = {s: q for s, q in b['original_Q'].items() if q}
    assert len(positive_q) == 8 and len(b['original_D']) == 6
    assert set(new) == {r['sid'] for r in b['rows'] if r['side'] == 'Q' and r['actual_qty']}
    net = sum((D(z['realized_trade_PNL']) for z in new.values()), D(0))
    assert net == D('11429.3639816959500')
    assert all(D(z['unrealized_net_buy_cost']) == 0 and D(z['booked_dividend_income']) == 0 for z in new.values())
    old_parts = [dict(p, sid=z['sid'], layer=z['layer']) for z in layers
        for p in z['actual_sell_parts'] if p['at'][:10] == '2025-08-18'
        and z['sid'] in b['original_D'] and p['reason']=='actionable_S_funding']
    old_net = sum((D(p['realized_trade_PNL']) for p in old_parts), D(0))
    assert old_net == D('-6769.0579849795100')
    native_rejections = [r for r in state['account']['rejections']
        if r['at'][:10] == '2025-08-18' and r['sid'] in positive_q]
    details = dict(
        financial_events=0, new_price_labels=0, new_indicators=0,
        original_certificate=b['certificate'],
        full_original_Q=b['original_Q'], full_original_D=b['original_D'],
        actual_source_sell_parts=old_parts, actual_source_realized_net=str(old_net),
        actual_new_layers=list(new.values()),
        original_open_rejections=native_rejections,
        original_open_event=state['events'][-1],
        realized_new_net=str(net),
        no_one_to_one_cash_source_claim=True,
        sources_sha256={str(op.resolve()): sha(op), str(lp.resolve()): sha(lp)},
    )
    save(O / 'AUG18_NATIVE_DETAILS.json', details)

    # Descriptive pair comparisons only. These are NOT new allocations.
    comparisons = []
    for z in batches:
        comparisons.append(dict(arm=z['arm'], day=z['day'],
            dependent_pair_count=len(z['edge_comparisons']),
            two_scale_dominance_edges=sum(e['same_scale_PVR_H1_dominance'] for e in z['edge_comparisons']),
            current_G1_warm_donors=[r['sid'] for r in z['rows'] if r['side']=='D' and r['G1_warm_original']],
            no_actual_pairwise_cash_allocation_saved=True))
    control = batches[1]
    nav = D(control['planning']['decision_nav'])
    risk = D(control['planning']['actual_resources']['risk'])
    headroom = nav * D('.06') - risk
    huasheng = next(r for r in control['rows'] if r['sid']=='600410.SH')
    # Necessary, fee-free lower-bound comparison for ORIGINAL authorized Q.
    new_risk = D(huasheng['authorized_qty']) * (
        D(huasheng['mark_close']) * D('1.0005') - D(huasheng['floor_close']))
    assert new_risk > headroom
    save(O / 'DESIGN_CHECKS.json', dict(financial_events=0,
        no_new_policy_result=True, comparisons=comparisons,
        Huasheng_original_authorized_qty=huasheng['authorized_qty'],
        Huasheng_original_actual_qty=huasheng['actual_qty'],
        account6_headroom_before_new_orders=str(headroom),
        Huasheng_original_Q_nominal_risk_before_fees=str(new_risk),
        free_cash_above_original10reserve=str(D(control['planning']['available'])-nav*D('.1')),
        conclusion='Warm-old universal privilege cannot preserve original full Q without other resource release; not proof of zero possible Huasheng fill.',
        future_prices_used_for_rule=False))

    out = []
    out.append('中际 Aug14→Aug18 资本替换：既有证据、完整包与可反驳设计\n')
    out.append('范围：只读原 C10/C20 已存账及因果缓存；金融事件0、选择器调用0、新指标0、新前瞻标签0。不是连续新策略收益。\n\n')
    out.append('一、先纠正六批报告\n')
    out.append('V2另存，V1原件不改。Jan旧D含分摊买费的已实现净额为−14440.25979803元；原−14283.59062793漏买费156.66917010。mark_price_gain_before_sell_excluding_buyfees明确只是未扣买费的市值价差。D+21是起始后21交易日、含起始共22收盘观察；D+5含6。130价格标签和风险分母完全沿用。中际144层Aug14买300、Aug18筹资卖−1582.09389246，截至Aug29未再入；全股含July旧层净+3840.90863661，二者不能混。\n\n')
    out.append('二、中际失去资本时，什么变了、什么没变\n')
    out.append('Aug13 CLOSE：I/E0 target=1，G1=4，fresh CP1/UP且frontier新增0.11031102；PVR81.7775、个股H1 97.9154，通信行业H1第1/90且当日price_advance，F1 permit/support/mature均真。Aug14 OPEN实际246.5232买300，毛款73956.96、买费19.53203314，原有效raw保护线216.57974664。\n')
    out.append('Aug15 CLOSE：mark238.05，保护线仍216.57974664；I/E0仍1、UP未重置，无fresh但不因此失去持有资格。G1降到3仍属原暖级，非acute_down；PVR降68.0011、个股H1仍97.1669。通信行业降第5，permit/support/mature仍真、最后推进Aug13。资本退出唯一责任actionable_S_funding，无保护破线/ACT退出。Aug18原代理实际241.49919卖300，层净−1582.09。\n')
    out.append('所以并非“完全没有近期示弱”，也并非“原趋势已坏”：近期推进排序下降，而较长尺度强度和原结构仍在。G1等级这里只是解释字段，原C供资条件并不要求G1转冷。原C先加行业H1头键，再比较原PVR_SLOT1完整键；中际的8个正量接收者原个股键也都排在它前面，不能把这次全部归为行业头键翻转。\n\n')

    out.append('三、Aug15授权→Aug18完整正量D/Q（完整含零Q域另见JSON）\n')
    out.append('旧D全部mobile/confirmed/S、同属通信设备#5、F1许可/支持/成熟真，最近推进Aug13；全部I=1且close高于自己的原线。原同批共享供资，未保存逐元D→Q归属，不能捏造“中际款独自买了某票”。\n')
    out.append('D 股票 | 股数 | CLOSE/本层raw线 | PVR/个股H1/G1\n')
    for r in b['rows']:
        if r['side'] != 'D': continue
        out.append(f"{r['sid']} {r['name']} | {r['authorized_qty']} | {float(r['mark_close']):.2f}/{float(r['floor_close']):.4f} | {r['PVR']:.2f}/{r['stock_H1']:.2f}/{r['G1_grade']:.0f}\n")
    out.append('\nQ 股票 | 批准→实际股数 | CLOSE/授权raw线 | PVR/个股H1/G1 | 行业H1名次 | 实际新层净贡献\n')
    for r in b['rows']:
        if r['side'] != 'Q': continue
        pnl = f"{D(new[r['sid']]['realized_trade_PNL']):.2f}" if r['sid'] in new else '无新层'
        out.append(f"{r['sid']} {r['name']} | {r['authorized_qty']}→{r['actual_qty']} | {float(r['mark_close']):.2f}/{float(r['floor_close']):.4f} | {r['PVR']:.2f}/{r['stock_H1']:.2f}/{r['G1_grade']:.0f} | #{r['industry_H1_rank']} {r['industry']} | {pnl}\n")
    out.append('新8票均I/E0=1、G1=4、fresh CP1真；6票其他电源设备为行业#1、当日Aug15推进，博威行业#2最近推进Aug13，网宿IT#3最近推进Aug4。原S成熟/许可是参与用途；后两者未因当天没有行业推进而失去资格。\n')
    out.append('资金/执行：决策NAV950140.65、可用现金347190.00、原持仓资本602027.48、风险55584.00（6%粗上限57008.44，费用会再影响预算权益）。原完整Q的筹资现金need181612.08；非把全部卖出都解释为现金不足，风险/行业容量也在联合投影内。实际D毛卖382716.35，Q毛买344377.10；中恒/上海/博威缩量，新雷能S准入sector_risk5拒绝，后续T回退另受sector/account/probe风险，不是8票均成交。\n')
    out.append('接收实际7层均到Aug20/21已平：正2层18985.93、负5层−7556.57，净+11429.36，未实现/股息均0。西子+7925.53、科士达+11060.40。原6层当次供资已实现−6769.06；这不是与中际假设留仓收益可直接相减的反事实利润。\n\n')
    out.append('四、同口径正例与不可知分叉\n')
    out.append('Aug7→8华胜：旧中科星图59.74/70.68/G3，艾迪53.69/30.75/G3；新华胜84.43/94.87/G4，原批准7300、实7100，原层实际净+59068.22。双方当时I有效/高于原线，旧两股也仍暖；新华胜在PVR与个股H1两维同时更强，且与中科同属IT。行业最近推进Aug4，不能靠“同行业当天推进”保住此正例。\n')
    out.append(f'此例现金高于10%保留额尚有{D(control["planning"]["available"])-nav*D(".1"):.2f}，不是现金短缺；但6%全账风险余量仅{headroom:.2f}，新华胜原7300股按原CLOSE预览新增风险{new_risk:.2f}（尚未计费/其他新单）。禁止全部暖旧仓供资，无法保留原完整授权，不能因此断言所有替代集合下华胜一定零成交。\n')
    out.append('Jan12→13翰宇：新87.63/99.67/G4，6700全成交，明显高于9个原D的PVR与个股H1；典型隧道为71.11/32.58/G−3。原翰宇Jan17筹资退出净+27717.32，整批新层净+17534.88。部分旧D仍暖，因此“旧I有效永久不卖”仍会删掉有益纠偏；但同口径双维占优可以保留这些供资边。不能说双维占优便能保证原整包全量不变。\n')
    out.append('反例就在本次Aug18：8新PVR全高于中际，个股H1却全低于中际；西子、科士达后来确实获利。它们相对中际的原供资边若被禁止，可能失去有益替换；是否能改由其他合法D/真实闲钱支持，未调用联合求解器，未知。不可用中际后来的+71.30%价格标签消掉这笔真实正收益。\n\n')
    out.append('五、两个可反驳机制，建议只将第一个交最小包审查\n')
    out.append('A. 双尺度相对替换资格：不动原信号/新Q目标/行业H1→业内PVR顺序、原费用/整手/全部资源约束和保护退出；仅给健康旧mobile的机会性供资增加条件。健康=原I/持有支持仍有效、mark高于本层真实保护线、无独立必须退出责任；不要求旧股fresh，不借新CP1换旧线，不用持仓浮盈定义健康。新股须在同一决策CLOSE、同一原评分域同时满足PVR_new≥PVR_old及stockH1_new≥stockH1_old，至少一维严格更高，才可为该接收增量新增这份健康D。NA不得填0；比较缺失则该边UNKNOWN，不静默假通过。行业分数只负责用途/队列，不冒充每股强度。\n')
    out.append('A允许真正跨行业纠偏：只要新股同时较强且原供资域允许，旧仓仍暖/盈利也可以让位；真实闲钱与独立退出结算资金不受此边条件阻挡。它会保留中际/光库相对Aug18这些接收者的资本，但会限制近期强、252尺度尚落后的早期新趋势；原西子/科士达正收益供资边是现成代价对照。PVR/H1仍是相对历史证据，双维占优不是未来持续概率，也不是保护退出触发器。\n')
    out.append('A需要的最小实施前条文：必须逐接收增量、在固定原prefix与同一联合资源约束下记录新增D及可执行Q；新增健康D不得超过本次增量实际需要，整手超额公开，不能以很小的占优接收者解锁整份D再虚称全用于其他不占优目标。已有待单/风险锁不可影子释放，原未ACK/未成交/未结算规则保留；资金真实释放后的资源反馈须独立列出，不宣称逐元一对一。原求解器的局部减量不是全局最小换手证明。当前仅有比较边表，没有新Q/D，尚未解决完整包分配，禁止直接接runner。\n')
    out.append('B. 现成持续状态优先：旧I有效且原current G1仍暖时禁止机会供资，等失暖后再按原排名放行，保护退出照常；不用最低持有日、不新增G1阈值。这能阻止Aug15中际/光库被卖，却同时阻止Aug7原中科/艾迪这两份暖仓供资，破坏华胜原完整获资路径；其风险反例已在上文给出。因此不建议把它作为通用持仓特权推进，也不能将“仍暖”冒称持续性已被证明。\n\n')
    out.append('六、下一最小可证伪验收（本轮未执行）\n')
    out.append('复用固定六批全Q/D及健康旧仓域，只做同态完整包比较，不再挑赢家：A是否真减少对仍强旧仓的供资、会否使华胜/翰宇原合法增量缺资、Aug18西子/科士达可否由其他合法资源承接，失去多少真实量；其他批特别机械失败、欧陆通双方转弱全部保留。若所谓改善只来自拒绝多数新买、或大赢家较长H1滞后而普遍无法替换，应否定/缩小该机制；不拿本6批胜负比例推80批，更不把未执行量乘事后涨跌叫已赚/省亏。相同旧新价格/指标路径不应因谁先成交或旧股无fresh而得到不同强弱值。\n')
    out.append('已支持：原近期强度与长期相对强度冲突时，原C供资可在结构仍有效/仍暖时迅速回转；新篮子有真实正收益，不是明显坏单。已反驳：一概等旧暖证据失效才换，可以无代价保留肥尾。未知：A整包可执行量、替代D、连续净收益及重参与；本轮不编码政策、不跑金融路径。\n\n')
    out.append('源码定位：c_selector.py:21–56只改行业头键；B selector.py:95–137按队列、较后rank的合法mobile枚举供资，并非G1冷却条件；policies_g1.py:18–19定义原warm/cold。trace.py读取原CLOSE/PVR/H1/CP1及原native库存，不调用引擎；AUG18_NATIVE_DETAILS保留原OPEN拒绝/财务桥，全部成交均沿原日线代理，不能声称真实开盘可执行。\n')
    (O / 'REPORT.txt').write_text(''.join(out))

    before = read(R / 'replacement-quality-six-batches-v2-20261102/V1_BEFORE_FEE_CORRECTION.json')
    # Preserve the original reporting error and all completed financial paths.
    assert all(sha(p) == h for p, h in before.items()), 'original V1 was modified'
    checks = read(O / 'SOURCE_CHECKS.json')
    assert all(sha(p) == h for p, h in checks['sources_sha256'].items())
    # Original snapshot hashes are independently bound in SOURCE_CHECKS.
    sources = dict(checks['sources_sha256'], **details['sources_sha256'])
    for p in [R/'g-s-C-industry-first-projection-v1-20261102/c_selector.py',
              R/'g-s-B-joint-target-v2-20261102/selector.py',
              Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py')]:
        sources[str(p.resolve())] = sha(p)
    save(O / 'DELIVERABLE_MANIFEST.json', dict(
        schema='READONLY_AUG18_REPLACEMENT_EVIDENCE_AND_DESIGN_V1',
        financial_events=0, selector_calls=0, new_indicators=0, new_price_labels=0,
        original_sources_unchanged=True, policy_implementation=False,
        original_six_batch_V1_all_files_unchanged=True,
        sources_sha256=sources,
        corrected_six_batch_manifest_sha256=sha(R/'replacement-quality-six-batches-v2-20261102/DELIVERABLE_MANIFEST.json'),
        outputs_sha256={p.name: sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='DELIVERABLE_MANIFEST.json'}))
    print('READONLY_NOTE_READY', sha(O/'REPORT.txt'), sha(O/'DELIVERABLE_MANIFEST.json'))

if __name__ == '__main__':
    main()
