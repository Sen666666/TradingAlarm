"""Publish saved verified 2023 continuation results only, no account imports."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;P=O.parent;R=O/'run-2023'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def f(x):return f'{D(str(x)):.2f}'
def main():
    a,b=read(O/'COMPARISON_2023.json');obs=read(O/'analysis-2023/ALL_ROLE_COMPARISON.json')
    assert read(R/'VERIFICATION.json')['passed'] and read(O/'analysis-2023/COMPLETION.json')['passed']
    assert read(O/'analysis-2023/BEHAVIOR_SUPPLEMENT_GATE.json')['passed']
    assert read(O/'analysis-2023/SC_BASELINE_IMMUTABILITY.json')['old_entry_exact']
    start=D(b['initial2023_NAV'])-D(a['initial2023_NAV']);end=D(b['end_NAV'])-D(a['end_NAV']);gap=end-start
    parts={k:D(b['new2023_layers'][k])-D(a['new2023_layers'][k]) for k in ['closed_positive','closed_negative']}
    parts['old_layer_year_change']=D(b['old_layer2023_wealth_change'])-D(a['old_layer2023_wealth_change'])
    residual=sum(parts.values(),D(0))-gap;assert abs(residual)<D('.00000001')
    save('analysis-2023/YEAR_ACCOUNTING_DELTA_BRIDGE.json',dict(opening_advantage=start,year_profit_difference=gap,ending_wealth_difference=end,parts=parts,residual=residual))
    stocks={m['reference']:{x['sid']:x for x in read(O/'analysis-2023'/m['reference']/'STOCK_YEAR_CONTRIBUTIONS.json')} for m in [a,b]}
    delta=[dict(sid=s,name=(stocks['SC'].get(s) or stocks['PVR_SLOT1'][s])['name'],SC=stocks['SC'].get(s,{}).get('year_net','0'),PVR_SLOT1=stocks['PVR_SLOT1'].get(s,{}).get('year_net','0'),delta=D(stocks['PVR_SLOT1'].get(s,{}).get('year_net','0'))-D(stocks['SC'].get(s,{}).get('year_net','0'))) for s in stocks['SC'].keys()|stocks['PVR_SLOT1'].keys()]
    save('analysis-2023/ALL_STOCK_YEAR_DELTA.json',sorted(delta,key=lambda x:x['delta']))
    verdict=O/'independent-2023-financial-audit/VERDICT.json'
    audited=verdict.exists() and read(verdict)['financial_technical_verdict'].startswith('PASS')
    lines=['PVR_SLOT1自身2022→2023连续验证｜唯一剩余路径完成，'+('金融独审通过，终点分类已修正' if audited else '待独立结果审计'),
      '从已审1/3收盘检查点接续到12/29；SC2023仅复用，原2022及Jan3均未重跑。初始持仓、现金、ACT、损耗不同，因此2023差是完整政策接续结果，不是纯当年排序alpha。无SD/C1/R1/两遍/新stage/阈值或资金重置。','',
      '参考 | 2023收益/DD | 平均/峰值曝险 | 平均现金 | 2023费用 | 原1m累计收益/DD']
    for m in [a,b]:lines.append(f"{m['reference']} | {f(m['return2023_pct'])}%/{f(m['DD2023']['percent'])}% | {f(m['mean_exposure_pct'])}%/{f(m['peak_exposure_pct'])}% | {f(m['mean_cash_pct'])}% | {f(m['fees2023'])}元 | {f(m['continuous_from_original1m_return_pct'])}%/{f(m['continuous_DD']['percent'])}%")
    lines += [f"期末SC663330.80元、PVR662557.91元，PVR少{f(-end)}元。期初优势{f(start)}元被2023年度差{f(gap)}元消耗；本次没有保留2022少亏优势。",'',
      '季度收益SC→PVR：'+', '.join(f"{x['quarter']} {f(x['return_pct'])}%→{f(y['return_pct'])}%" for x,y in zip(a['quarters'],b['quarters'])),
      'Q2平均曝险66.01%对65.20%，收益8.88%对0.49%，不能只说资金没投入。SC8/24 ACT暂停、8/25全清；PVR9/21暂停、9/22全清。两者Q4均空仓且未恢复，全年暂停98→66收盘。PVR更晚暂停、多承受一段弱化，非C1低cap恢复阻塞。','',
      '资金/闭合损耗：']
    for m in [a,b]:
      c=m['new2023_layers'];lines.append(f"{m['reference']}: 实买款{f(m['buy_cash2023'])}、买/卖fill {m['actual_buy_fills']}/{m['actual_sell_fills']}；新层closed正{f(c['closed_positive'])}、负{f(c['closed_negative'])}、闭合肥尾{f(c['closed_tail'])}元，末open贡献0。")
    lines += [f"年度差账桥：新层正差{f(parts['closed_positive'])}、负差{f(parts['closed_negative'])}、旧层年度变化差{f(parts['old_layer_year_change'])}元。PVR新层净−51168.36元、继承旧层年度变化−1283.07元，不能归罪旧book；这是账差分解，不是独立可实现反事实PnL。",
      'PVR2023已实现交易净变化−63324.37元、期初未实现亏损转为0的差额+6762.03元、确认分红+4110.92元=年度财富−52451.43元。末实际未实现价差0，累计已实现交易净−343546.85+累计确认分红6104.76=原1m累计−337442.09元；6104.76仍为应收，不能再投。',
      '首次参与/已有股追加/全清重入：PVR272/160/269层净−13379.55/−17963.49/−19825.31；SC222/131/259层净+6691.65/+14584.21/−25268.90。相关层不作独立胜率，不据此自动禁止某类。','',
      '全机会漏斗：共同市场fresh canonical CP1、Q通过、行业confirmed/expanded母体9095张；3638个stock×industryattempt，其中187组的行业attempt起于窗前，不能据此认定股票机会历史也已完整或左删失。末收盘45张下一开盘在窗外，ACT暂停不删母体(2533→2051张)。',
      'SC→PVR非零mobile意图6202→6657、预留452→525、有真实fill的mobile凭据447→521，其中confirmed391→485。预留不等成交；core-first可能实际买core而不买mobile。']
    for o in obs:
      e=o['competing_endpoints']
      lines.append(f"{o['reference']}: 首次市场资格时已持有{o['already_held_at_first_eligibility']}组另列；未持有{o['initially_unheld']}组中{o['initially_unheld_later_anyrole_funded']}后来由任一角色获资；未获资{o['initially_unheld_no_observed_later_buy']}分为行业attempt先结束{e['industry_attempt_ended_before_funding']}与观察末仍有效右删失{e['still_active_at_observation_cutoff_right_censored']}。仅获资子集延迟median/max {o['funded_only_anyrole_median_sessions']}/{o['funded_only_anyrole_max_sessions']}市场session，市场资格不等开盘全部资源可执行。")
    lines += ['平均confirmed35.68→43.66%，平均probe3.24→4.11%；旧/失效attempt probe平均7315.93→15832.09元。PVR132层等待中82观察到迁入、20先退出、30先attempt结束；仅后来迁入者median/max3/28观察。原耦合/共存约束保留，没有证明某个阻挡的独占因果。','',
      '固定样例及正负控制：',
      '中际两臂均未参与：PVR1/3 core-Q/CP1可见，1/4首次core路由industry_invalidated，只是首阻挡而非全年原因。后来反复probe风险/行业资本/池限制；PVR仅1次OPEN冻结目标最小单位失败，另有21次CLOSE core风险/整手目标失败(SC22次)，不能混算或统一归整手。市场confirmed母体13张，不把首次core-Q与首次confirmed资格混称。',
      '新易SC未参与；PVR3/31 fresh CP1 mobile/probe100股，含费4505.60元，4/20峰1.07%，4/27原近保护请求、4/28实卖，净+1983.13。4/26已知复权保护430.82063，4/27复权close381.38869、I仍有效，属于mobile退出；无追加/重入。',
      '上海电影PVR继承旧层1/12结构退出请求、1/13卖；3/13 fresh重入probe1000，3/21/22/23/28 confirmed加900/900/800/100，4/12峰15.42%(含涨价，非新买越10%)；4/13近保护请求、4/14实卖；4/26 fresh重入200、4/27confirmed加400。全年+47822.08，对SC+8003.15，闭环真实成立但并非普遍。',
      '确定性最差永鼎−6351.02：4/11confirmed2700，4/13近保护→4/14卖；4/24 fresh重入2100、4/25加2000，4/27 I失效→4/28卖。北方国际−5831.62、新华网−3898.04同列完整链；确有按保护执行但反复试错累积损耗，不自动加禁入门。',
      '主要股票年度贡献差(账差，非逐股因果)：']
    for x in sorted(delta,key=lambda x:x['delta'])[:3]+sorted(delta,key=lambda x:-x['delta'])[:3]:lines.append(f"  {x['name']}({x['sid']}): SC{x['SC']}→PVR{x['PVR_SLOT1']}，差{f(x['delta'])}元。")
    lines += ['',
      '支持：排序会改变实际资本与持有路径；本次更多获资没有带来更好恢复财富。否定的具体假说：2022少亏优势会在下一整年自然保留，本次不成立。未知：逐股可交换资本因果、PVR成本/D1稳健性、强2025/26未平利润后续兑现。当前不调整规则或自动新增试验。',
      '核验：484日钱/股/权益/费用/池桥；2956历史fill、5历史split；4个2023季度checkpoint身份；242决策冻结PVR键、10704缓存末SHA。2022与Jan3六流水解压行字节prefix和旧book数组prefix exact。源码native5ec91c...697c、导入edd7170...5218未变。',
      '真实启动/开始事件/完成记录在ACTUAL_START/EVENT_LOOP_START/TIMING，加载108.76秒、总307.67秒。报告差额桥1e−22元Decimal末位差已留PUBLISH_PRECISION_ERRATA并按既有1e−8容差核同，未重跑账户。',
      'snapshot非PIT、97无观察身份、1365权益时点未知代理、日线OHLCV可执行性限制保持；原strict诊断gate失败记录保持，这是探索试验的连续验证，不是实盘/未见样本认证。']
    (O/'RESULTS_2023.txt').write_text('\n'.join(lines)+'\n')
    ready=dict(ready_for_independent_audit=True,independent_result_audit_pending=not audited,independent_financial_audit_pass=audited,one_remaining_path_completed=True,
      source_native_sha256=sha(P/'native_rank.py'),source_horizon_sha256=sha(O/'horizon_import.py'),source_launcher_sha256=sha(O/'run_continuation.py'),
      authorization_sha256=sha(O/'FULL_2023_RUN_AUTHORIZATION.json'),actual_start=read(R/'ACTUAL_START.json'),event_loop_start=read(R/'EVENT_LOOP_START.json'),completion=read(R/'TIMING.json'),
      normalized2023={'SC':a['return2023_pct'],'PVR_SLOT1':b['return2023_pct']},DD2023={'SC':a['DD2023'],'PVR_SLOT1':b['DD2023']},terminal_wealth={'SC':a['end_NAV'],'PVR_SLOT1':b['end_NAV']},
      year_accounting_delta_bridge=parts,verification=read(R/'VERIFICATION.json'),SC_immutable_evidence=read(O/'analysis-2023/SC_BASELINE_IMMUTABILITY.json'),
      source_behavior_contract_sha256=sha(O/'CONTINUATION_CONTRACT_PROPOSAL.txt'),no_2022_Jan3_SC_replay=True,no_extra_variant_or_live_action=True,
      all_eligible_evidence='analysis-2023/*/ALL_ROLE_FIRST_ELIGIBLE_DELAYS.json',cash_realized_unrealized_evidence='COMPARISON_2023.json',
      old_firstsession_report_errata='first-session/REPORT_ERRATA.json',next_scope_not_authorized=True)
    save('READINESS_2023_FOR_INDEPENDENT_AUDIT.json',ready)
    (O/'AUDIT_GUIDE_2023.txt').write_text('从已审Jan3checkpoint27d1...f0cd严格之后接续；FULL_2023_RUN_AUTHORIZATION→ACTUAL_START/RESTORED_START/EVENT_LOOP_START→TIMING/DONE记录真实时间。源checkpoint freeze不改，入口/授权另由EXECUTION_FREEZE绑定。verify_continuation只读核484日独立股数/fees/权益及旧2022+Jan3解压字节前缀、4季度实际class/function/SHA、10704缓存。analyze_continuation仅将已审account行数242改484；carry扣真实2022末cash/div/库存，不假设旧仓空。real_bridge分开realized/unrealized/dividend，不用open层类别代替。behavior_supplement复用已修时序wait_endpoint，分开mobile凭据与任一角色股票立足；全部未获资和左右删失保留。SC书对旧DELIVERABLE_SHA256核同。FOCUSED_BEHAVIOR_READOUT保存当时已知保护、触发close/I和实际实卖。两初态不同，不称纯2023排序alpha；强窗原未平问题未解决。\n')
    cp=O.parents[2]/'CURRENT_RESEARCH_CHECKPOINT.txt'
    entry='\n2026-11-01 PVR自身2022→2023唯一连续路径完成待独审：continuation-2023-readiness/RESULTS_2023.txt及READINESS_2023_FOR_INDEPENDENT_AUDIT.json。Jan3close27d1...f0cd接余年，279全新Jan4意图/603589400待卖继承，报告两处错文已留errata，账不改。SC2023只读；收益/DD SC−.5984/21.1481→PVR−7.3358/20.1454，平均曝险38.92→47.77，末财富663330.80→662557.91；原1m累计−33.6669→−33.7442，2022少亏优势47685.49被年度差−48458.38消耗。末均全平；PVR累计realized−343546.85+分红应收6104.76=累计−337442.09。新易probe100近保护实卖+1983.13、中际仍未参；上海真实试探/扩张/退出/再入+47822.08。9095市场母体/3638stock-attempt全漏斗、任一role立足/未获资/censor及旧probe等待保存。484日桥/2956fill/5split/4季度identity/10704cache/旧2022+Jan3字节prefix exact；加载108.76s、总307.67s。无SC/2022/Jan3重跑，无新变体/强窗latest尾部/压力/实盘。\n'
    text=cp.read_text()
    if 'PVR自身2022→2023唯一连续路径完成待独审' not in text:cp.write_text(text+entry)
    files=[p for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'scores' not in p.relative_to(O).parts and p.name!='CONTINUATION_2023_ARTIFACT_SHA256.json']
    save('CONTINUATION_2023_ARTIFACT_SHA256.json',dict(scope='ONE completed2023 continuation and readiness lineage;scores covered by frozen manifests',files={str(p.relative_to(O)):sha(p) for p in sorted(files)}))
    print('PVR2023_PUBLISHED_AUDIT_READY',len(files),'artifacts','terminaldifference',end,flush=True)
if __name__=='__main__':main()
