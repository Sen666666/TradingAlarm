"""Validate and publish the saved read-only causal joins; no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
import json, hashlib, collections, datetime

O=Path(__file__).resolve().parent
W=O.parent
Y=W/'recovery-2023-readiness-20261101'
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
    p=O/name; t=p.with_suffix(p.suffix+'.tmp')
    t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'); t.replace(p)
def text(name,x):
    p=O/name; t=p.with_suffix(p.suffix+'.tmp'); t.write_text(x); t.replace(p)

subjects=read(O/'CONTROL_SELECTION.json')
sids={'300308.SZ','300502.SZ'}|{x['sid'] for x in subjects if x['sid']}
manifest={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
expected={}
for sid in sorted(sids): expected.update(manifest[sid]['output_sha256'])
for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json'):
    expected.update(x['output_sha256'])
source_checks=[dict(path=p,expected=h,actual=sha(p)) for p,h in sorted(expected.items())]
assert all(x['expected']==x['actual'] for x in source_checks)
checks=[]
for policy in ['Bdiag','C1']:
    ops=read(O/policy/'OPPORTUNITIES_NAMED.json')
    assert len(ops)==159
    for sid,ni,nc in [('300308.SZ',56,24),('300502.SZ',52,27)]:
        a=[x for x in ops if x['sid']==sid]
        c=[x for x in a if x['role']=='core']; m=[x for x in a if x['role']=='mobile']
        assert len(c)==ni and len(m)==nc
        assert len({x['canonical_receipt'] for x in m})==nc
        assert all(not x['canonical_receipt'] for x in c)
        for x in a:
            assert all(str(t['signal_at'])[:10]==x['signal_day'] for t in x['actual_fills'])
            assert all(str(t['decision_at'])[:10]==x['signal_day'] for t in x['actual_routes'])
            for f in x['funding_records']:
                assert (str(f['at'])[:10]==x['signal_day'] and '15:10:00' in f['at']) or (str(f['at'])[:10]==x['native_next_session'] and '09:30:00' in f['at'])
        checks.append(dict(policy=policy,sid=sid,core_signal_days=ni,canonical_CP1_receipts=nc,
            Q_and_role_offered_core=sum(x['valid_entry_signal_before_ACT_resources'] for x in c),
            Q_and_role_offered_mobile=sum(x['valid_entry_signal_before_ACT_resources'] for x in m),passed=True))
    snaps=read(O/policy/'OWNERS_SNAPSHOTS.json')
    assert all(all(abs(v)<1e-6 for v in x['component_gaps'].values()) for x in snaps)
    assert all(x['reconstruction_exact'] or x['unknown'] for x in snaps)
lineage=read(O/'LINEAGE_VERIFICATION.json'); assert lineage['passed']
assert all(x['passed'] and not x['mismatches'] for x in lineage['named_route_checks'].values())
ex=read(O/'APRIL_EXIT_SUMMARY.json')
assert ex['trigger_day']=='2023-04-27' and D(ex['trigger_close'])==63
assert len(ex['actual_sells'])==1 and ex['actual_sells'][0]['shares']==300
assert ex['actual_sells'][0]['at'].startswith('2023-04-28 09:30')
assert ex['all_later_fresh_CP1_receipts']==11 and not ex['core_opportunities_during_CP1_gap']
assert read(O/'SUMMARY_COMPLETION.json')['new_accounts']==0
save('VERIFICATION.json',dict(passed=True,named=checks,immutable_manifest_files_checked=len(source_checks),
    market_financial_attempts_checked=166,exact_owner_decompositions=164,unknown_owner_decompositions=2,
    all_166_aggregate_component_checks_within_1e_6=True,
    two_unknowns='C1 2023-05-31 core 300502 and mobile 300308: per-layer fractional split allocation not asserted',
    new_accounts=0,new_strategy_calls=0,new_indicators=0,relaxed_constraint_PnL_run=False,
    funding_clock_join='signal-day close planning; native next-session open execution; never same-day preceding open',
    source_hash_checks=source_checks))

eps=read(O/'EPISODES_NAMED.json')
lines=['保存的全年机会段；连续指连续已记录机会，非连续自然日。价格统一原复权close，2022-12-30=100；不是PnL。',
       '每段仍保留逐canonical receipt/信号日及实际路由于JSON。原rank从0开始，是当日全输入H1队列位置，不是仅合法信号的名次。',
       'policy | stock | role | first..last signal | count | action | stage | original reason | adjusted-index first..last (peak)']
for x in sorted(eps,key=lambda x:(x['policy'],x['sid'],x['role'],x['first_signal'])):
    p=x['price_progress']; lines.append(f"{x['policy']} | {x['sid']} | {x['role']} | {x['first_signal']}..{x['last_signal']} | {x['distinct_opportunities']} | {x['classification']} | {x['industry_stage']} | {x['first_block_or_admission']} | {p['first_adjusted_index']:.2f}..{p['last_adjusted_index']:.2f} (peak {p['highest_adjusted_index']:.2f}@{p['highest_day']})")
text('OPPORTUNITY_EPISODES.txt','\n'.join(lines)+'\n')

report='''2023 中际／新易：已有两账的全年因果行为复盘（只读；无新账户回放）

结论：不是没有反复出现机会。早期主要是同批H1优先预留消耗probe风险；上涨后又有原core整手floor-risk不可行、行业attempt退回及行业总占用共同约束。资源中确有已获资的有效赢家，不能据事后两只最强股缺席就推断应卖掉存量或取消所有限制。

分母与时点
每臂159条原机会：中际56个原I日＋24张canonical CP1，新易52＋27；core日键与CP1 ID分开，平行角色不能相加成可同时成交机会。原Q且角色可提供、尚未审ACT/资金的core/mobile分别：Bdiag中际52/22、新易51/27；C1中际52/22、新易45/27。Q本已含原行业E0/H1资格，不能叫未门控raw信号。
中际1/3首次I/Q/CP1，被ACT暂停；1/19信号→1/20才首次实际core路由；2/1才首次“行业confirmed且个股Q通过CP1”。新易1/3已有I/Q，1/20首CP1，1/30首次实际core和随后mobile尝试，2/6首市场confirmed CP1。这些事件不可用旧first_proven_block字段混称。
全年按原因/attempt/stage/action合为161个严格机会段；每张原I／CP1、原队列rank、市场与财务attempt映射、Q/ACT、最小量、各路由与实际预留/成交均在OPPORTUNITIES_NAMED与EPISODES_NAMED。没有信号的日期不记为被拒订单。原core成功“预留”即跳mobile，不等待是否实际成交。

紧凑因果矩阵
1）两股早期：中际1/19原H1=14.8826、0起rank1294。1/20开盘两账无旧持仓，先到的真实买单预留已占probe风险B 3325.32/C 3979.65元，最低100股2897.45元仍只被probe_risk挡。主要预留百亚／鸣志／铖昌，原H1约99.41／99.48／99.90，比候选当时强；B三者风险合3175.57，C合3655.43元。不能按后来中际涨幅判当日次序错误。新易1/20信号→1/30，一手2594.30元也被probe风险挡；已有持仓风险B2576/C4130.72，其中百亚、鸣志等仍占用。
2）确认后仍有机会：中际2/1至3/2六张CP1、新易2/6至2/28五张，行业confirmed/expanded时反复被probe风险及部分池资本挡；首次2/2中际confirmed迁池未准仅有raw confirmed_unfunded，不能强归独占C1 cap。完整双路最小单位拒因及各占用前10已保存，联合拒因不拆成独占。
3）涨起来后的core：原100股minimum_unit_exceeds_risk_or_nominal_cap中，中际B22/C26次、新易B15/C8次都能严格证明：一手保护线距离的风险（未计费下界）已超过原0.25%决策NAV预算，且一手毛额未超过股10%。例如中际3/23 B一手5002.50元、floor-risk至少1741.13元>1656.59元预算。不是通称mobile 2%买不起；这只证明原core sizing不能下，不表示移除此项就能越过其它约束。
4）新易C1真正参与：4/7 mobile初入200股、4/10追加100股，共含费20496.85元；实际日终峰值3.0132%在4/20。两层都属confirmed mobile；账里kind=add不代表第一次之前已有core。Bdiag全年度没有新易成交；两账中际都没有成交。
5）新易退出／无信号段：4/18最后抬升的mobile线折原价71.165454，4/26收71.20仍在线上；4/27收63触发原保护，个股I仍有效。4/28下一合法代理窗口实卖300股@65.007480，闭合含费-1020.64元，无未平。4/28卖出后至5/17没有新CP1，也无fresh I核心机会。原CP1已在4/26 E0_down重置、4/27降低anchor，并非被旧高点锁死；5/17收61.46，不能直接称这段等待漏掉持续上涨。
6）新易后续确有重入但被挡：5/18、5/29两张CP1先被行业attempt失效挡；5/31新行业probe→6/1实际重入最低一手，同时被probe风险／行业资本／行业风险三项挡。C1行业占用40926元／risk9306元，全部是剑桥两层mobile：各300股、mark68.21、原保护52.70、成本24.69234与43.531755；个股I有效、浮盈为正，原H1=99.9662，比新易99.4932略高。这些层属于旧attempt，风险是实际浮盈回吐风险，不是免费额度。当前行业probe 2%约16339.51、行业risk1%约8169.76，同时global probe risk4448.67>约4084.88；没有单一容量放开即可进的证据。B同日行业占用75031/risk17061，也来自盈利有效剑桥层。
7）完整后续分母：C1退出后11张CP1，5/18、5/29 industry_invalidated；5/31、6/16各probe+sector capital+sector risk；6/20再含pool capital；6/30 pool+probe+sector capital；11/7、11/10仅probe risk；11/17 pool+probe；11/30、12/7 pool+probe+sector capital。全部无再成交。B late-2023主要ACT暂停，不能拿C1仍尝试的机会推成相同账户路径。

同年对照，避免只盯两个后验赢家
按固定行业内最大闭合贡献（排除两股）选：B剑桥2/27先小mobile，全年新买25546.77元、峰10.806%(6/15)、闭合+28806.42；B计算机曙光数创4/14首买、峰8.627%(5/4)、闭合+25527.31。C剑桥3/15首买、峰5.456%(6/20)、闭合+9168.35；C计算机没有aggregate closed净正股票，不另挑浮盈股冒正对照。说明原系统确已分配给另一条真实通信赢家。
按真实probe-origin最差闭合股票／expanded mobile最差闭合子群确定负对照：B福瑞医科-1589.70、峰1.806%，秦港-7087.46、峰4.832%（5/8–11三层快速扩张）；C奥飞probe-origin子群-2069.89（全股-2129.34），常山expanded子群-2582.00，但全股闭合+7354.09、未平-130.54，不能把坏追加子群当整股坏名单。逐层投入→request→实卖路径已保存，probe-origin可后来迁池，不冒称永远小仓。

全年价格前三行业，精确资金参与（事后评价，不回填名单；权重包含被动上涨）
行业                   B首次买／峰权重／闭合净       C首次买／峰权重／闭合净／未平
计算机设备 +47.35%       2/20／10.437%／+19471.91      3/13／5.613%／-8771.72／+1964.94
消费电子   +43.73%       3/27／6.315%／-4224.85       3/31／1.995%／-912.87／+624.63
通信设备   +43.64%       2/10／10.806%／+25802.42      3/15／7.253%／+6279.90／0

可证伪机制假说，尚未实施
H1 同批串行预留＋probe全局风险造成晚排机会缺席：预测早期被挡机会的空间主要在同开盘前序预留、未必旧仓；本例1/20支持。反证／负对照是H1高位预留后来既有赢家也有鸣志亏损；必须在所有当日候选同口径检验，不能预定中际优先。任何改进必须保留总风险与原子预留，不能把瞬时空间相加为可实现收益。
H2 上涨中原I core远保护与整手风险预算不兼容，使后续只能依赖mobile路由：本批全部上述core sizing拒绝支持其可执行性缺口，但不能解释早期mobile被池风险挡，也不能证明更大core正确。负对照福瑞小试失败与秦港扩张失败要求保留风险限制；不是自动取整、改floor或提高0.25%的授权。
H3 保护退出后，个股新推进与行业attempt／存量行业总占用脱节，可能阻断纠错参与：本例5/18后支持“有fresh信号但行业／资源拒绝”；反证是原CP1已正确重置，4/28–5/17无新推进不能算拒绝。已有剑桥有效盈利且H1更高是强负对照，不能据旧attempt编号就回收它。该假说若只在事后两赢家存在、或其它同类机会本来也差，即应否定其通用改进价值。

核验与停止边界
166条实际路由前资源快照由原库存＋已发生拆股/卖出＋前序真实预留逐笔复算，无Account/Contract/策略调用，无本地放宽约束PnL。164条逐层可精确核同；C1 5/31两条涉及拆股分数尾差归层，aggregate各科目虽均同仍保留unknown，不用猜补。6823个市场attempt映射到财务ID，166条level/attempt核同0错。当前已读缓存哈希与原manifest逐份核同；实际cash只引用原账授权视图，不冒称第二套独立现金模型。
core成功预留而非fill会跳过mobile；原rank从0开始、覆盖全输入，不是当日合法订单名次。minimum preview仅原规则可行性，不是反事实交易。只读加载/聚合约6.48+26.31秒，未重放任何账户；首次owner JSON遇inactive attempt的NaN序列化失败，保留raw与failure，仅unknown→null后重导，不吞掉风险差。
仍是已消费、当前snapshot非PIT及日线OHLCV执行／权息时点代理下的行为证据；不能认证实盘。没有新门、白名单、卖赢家、旧receipt复活、收益回测或latest准备。
'''
text('READOUT.txt',report)
frozen=[]
for policy in ['Bdiag','C1']:
    for n in ['B.json.gz','daily.jsonl.gz','capacity-checks.jsonl.gz','opportunities.jsonl.gz','funding.jsonl.gz']:
        p=Y/'runs'/policy/'pair'/n; frozen.append(dict(path=str(p),sha256=sha(p)))
for p in [Y/'continuation_2023.py',Y/'run_continuation.py',W/'case-stage-ledger-20261031/v3/joint_v3.py']:
    frozen.append(dict(path=str(p),sha256=sha(p)))
save('SOURCE_MANIFEST.json',dict(original_ledgers_and_algorithms=frozen,
    manifests=[dict(path=str(p),sha256=sha(p)) for p in [W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json']],
    read_only_source_mode=True,source_files_changed=0))
save('FINAL_STATUS.json',dict(status='complete_readonly',new_account_replays=0,new_strategy_rules=0,
    named_rows=318,named_distinct_canonical_receipts_per_arm=51,core_signal_days_per_arm=108,
    named_opportunity_episodes=161,owner_snapshots=166,owner_exact=164,owner_unknown=2,
    no_relaxed_PnL=True,no_latest_restart=True,
    deliverables=['READOUT.txt','OPPORTUNITY_EPISODES.txt','VERIFICATION.json','SOURCE_MANIFEST.json',
                  'Bdiag/OPPORTUNITIES_NAMED.json','C1/OPPORTUNITIES_NAMED.json','XINYISHENG_EXIT_REENTRY.json','CONTROLS_FUNDED_PATHS.json']))
hashes={str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name not in ['ARTIFACT_SHA256.json'] and 'failure' not in p.parts}
save('ARTIFACT_SHA256.json',hashes)
print('READONLY_COMPLETE',len(checks),'cohorts',len(source_checks),'immutable cache files',len(eps),'episodes',len(report),'readout chars')
