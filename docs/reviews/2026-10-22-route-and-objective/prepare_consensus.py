from pathlib import Path
import hashlib
import json
import difflib

ROOT = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
OUT = Path('/Users/bytedance/Documents/ChatGPT/money/docs/reviews/2026-10-22-consensus-v3-4')
OUT.mkdir(exist_ok=False)
changes = {}

def read(p):
    return (ROOT / p).read_text()

def put(p, s):
    old = read(p)
    assert old != s, p
    for part, data in [('prior', old), ('staged', s)]:
        q = OUT / part / p
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(data)
    changes[p] = {'before': hashlib.sha256(old.encode()).hexdigest(), 'after': hashlib.sha256(s.encode()).hexdigest()}

def replace_once(s, a, b):
    assert s.count(a) == 1, (a[:100], s.count(a))
    return s.replace(a, b, 1)

decision = ('**2026-10-22用户决定：80%保留为大行情愿景和观察项，不再作为每轮研究的通过、晋升或继续搜索门槛。** '
            '20%仍为回撤研究目标，30%仍只是尾部分类界线；低胜率、正常右侧回吐和少量普通净损耗可接受。'
            '固定主要账户与主要对照，先评价机制、收益结构和成本后经济取舍；局部小池相对中间方案改善不能重置整个研究的停止计数。'
            '保持旧九资产停止，继续历史全池板块→个股研究，先核实数据、再作有限对照和主动图检。')

p = 'docs/RESEARCH_CONSENSUS.md'
s = read(p)
s = replace_once(s, '版本：2026-10-21 v3.3。依据：用户本日明确要求历史全池板块—个股两级选股，并新增公司市值及港股通限制；此前未撤销的量价、账户、执行和授权约定保留。',
                 '版本：2026-10-22 v3.4。依据：用户采纳路线复评，明确80%保留为大行情愿景、取消逐轮硬门槛，并要求同步评价与停止条件、继续历史全池两级选股；此前未撤销的量价、范围、风险和执行约定保留。\n\n' + decision)
s = replace_once(s, '- 既有“大行情中整个账户超过80%、最大回撤研究目标20%”保留。80%不是每年要求，也不是单笔要求；20%不是已保证的硬上限。沿用此前用户约定：收益与回撤冲突时优先大行情收益，同时完整报告回撤及取舍，不隐含扩大风险。',
                 '- **大行情整个账户80%仅保留为情景愿景与观察项，不再作为每轮机制通过、策略晋升或继续研究的必要条件。** 未达到80%不自动触发新模型、资金规则或更多试验；达到80%也不证明有效。不是每年要求、单笔要求或必须保住的浮盈。最大回撤20%继续是研究目标和风险偏好参照，不是已保证硬上限，也不是触线强平规则；收益与风险的取舍须显式报告，不为追愿景隐含扩大风险。')
anchor = '## C08 因果性与证据保留'
section = '''### 当前阶段的评价与停止约束（2026-10-22）

1. 分开评价机制真实性、稀疏大赢家与普通损耗的结构、相对简单对照的经济价值、冻结后的新增证据。工程通过和收益形态符合理念均不能替代经济优势；一个可信的否定结果也可以结束阶段。
2. 事前指定完整主要账户、主要对照、固定时期和成本/延迟压力。本轮主账户S0，主要基础对照T0；T1−T0解释板块资格，S0−T1解释两级分配，S0−T0评价整体政策。不得看完结果换对照、换池、换日期或按不同市场拼政策。
3. 普通损耗、尾部金额及参与、未结估值、现金与暴露共同报告。低回撤若主要来自少投钱，只能说明风险取舍；不按现金比例线性外推收益。普通净损耗预算须在经济协议冻结前有经济理由，不能由已见最佳结果倒推。30%—40%胜率是可接受形态，不是调参奖励。
4. 本轮首阶段只准入预定10账户及必要技术验证。首轮结束必须作“支持／否定／证据不足”裁决；未达80%不构成继续理由。后续分仓、等待、退出和仓位清单不自动执行。只有主要对照或共同行为证据支持一个非重复、当时可实现的问题，才另行冻结一个有限追加轮，写明配置上限、损失/改善预期及否证条件。
5. 局部子池或较弱中间对照的改善可以记为发现，不得重置整个主线无进展计数或自动延长预算。连续三个不同问题无主要进展是最迟停止复查边界，不是必须跑满三轮；首轮已否定且无新证据时即停止该扩展。不以新目录、换agent、换评价数字重置停止状态。
6. 保留已有数据准备边界：首批最多24证券线路、每字段最多两批明确来源验证，验证后每扩展批最多100线路。不用无限工程代替研究；缺失资格不能填成否或用当前快照回填，部分覆盖不得称全池通过。真实资料足以支持的图检和技术验收可并行，但不越过经济账户的数据准入。

'''
s = replace_once(s, anchor, section + anchor)
s += '\n| 2026-10-22 | v3.4 | 用户采纳路线复评：80%降为大行情愿景与观察项，取消逐轮硬门槛；固定主要账户/对照、分层评价、首轮有限10账户及条件式追加，局部发现不重置总研究计数。保留20%风险目标、量价与尾部初衷、历史全池两级选择和旧小池停止。 |\n'
put(p, s)

p = 'docs/NEXT_RESEARCH_TASKS.md'
old = read(p)
history = old[old.index('## 旧九资产阶段记录'):]
current = '''# 下一阶段 AI agent 执行计划

''' + decision + '''

遵守[共识v3.4](RESEARCH_CONSENSUS.md)，具体范围与交易设计见[全池方案](SECTOR_STOCK_STRATEGY_PLAN_2026_10_21.md)，入口为[研究轮](../research_rounds/sector-stock-20261021/README.md)。历史全部沪深北A股、当时南向港股通股票，新买/加仓公司总市值>100亿元；ETF仅作参照。算法冻结，一个候选，机制修订0次。首版3板块×2公司、90%初始预算只是研究默认，不是固定6只股票。

## 当前证据与下一动作

**D1已实际完成，不能因旧入口未同步而重跑。** 见[本地盘点](../research_rounds/sector-stock-20261021/coverage/LOCAL_INVENTORY.md)：本地5,517条原价线路、239条退市历史复用已核对。D2第1批已保存公开18次GET及6次原生请求；这不表示历史市值、南向资格和同源行业成员已通过。现有三份更码公告与后续链接应先离线解析，剩余请求按已有批次预算接续，不重新开启计数。

1. **下一动作：复核D2已有原始响应并形成字段/身份裁决。** 核对更码公告、股本历史的日期/精度、南向初始名单与变更、行业成员的真实来源。不得把源表自带或程序赋值的“无前视”标签当成证据；保存已知、未知和否定三种结果。
2. 按实际缺口冻结剩余第1批及必要第2批验证。单字段最多两批、首批最多24证券线路；本人已授权THS节点只作必要增量查询，公开资料补证。当前快照、HTTP成功、少数成功证券均不等于全池历史资格齐备。
3. 链路通过后每批最多100线路增量扩展，复用已有行情。交付逐日全体名册、确定合格/不合格/未知、历史市值、南向资格与同源成员覆盖。关键缺口未闭合时只能作真实范围内的轨迹/技术验证，不能冒充全池经济验证。
4. 固定行业—个股正反例，先原始量价解释，再叠加冻结状态；包括板块先起、个股先起、行业弱而个股独涨、共同假突破、长期赢家及身份/权息变化。适配动态排名、双重资格和共享槽位，检查前缀因果；适配股票与南向人民币交收并独立核账。
5. 覆盖、执行与图检通过后，冻结并完成首轮10账户：T0/T1/S0各基础、双成本、额外延迟，加同池被动B0。完整保存候选漏斗、交易、普通/尾部/未结、现金暴露、未成交和主观得失。

## 首轮问题、评价与停止

**唯一首轮问题：同一冻结个股算法下，板块信息是否改善大赢家实际参与和累计试错的经济取舍？** 主账户S0、主要对照T0固定；T1−T0测板块资格，S0−T1测两级分配政策包。B0和理论同池指数是辅助参照，不能因整手造成被动高现金就宣称选股有效。

- 先证明数据、时序和账户可信，再分别评价收益结构及经济增量。主要账户、固定时期和三执行情景全部报告，明确收益/回撤/尾部/普通损耗/现金的取舍；不能只报最佳行，不要求每个子组都盈利。
- 首个账户前还须冻结实际数据与代码身份、费用假设、普通累计损耗预算及经济理由、主要比较的判读规则。若主要价值在成本或延迟情景反向，应裁为取舍或证据不足，不能自动晋升。小数值改善不自动当成稳健优势。
- 首轮结束必须作支持/否定/证据不足裁决。没有共同新证据时即停止该扩展，不因80%未到而自动进入分仓、等待、退出、仓位四轮。
- 有主要对照或共同机制证据时，才追加一个独立冻结的有限问题；先写配置上限、预期改善及可接受代价、否证条件，再运行。局部子池击败中间方案不重置全项目停止计数。连续三轮不同问题无主要进展是最迟停止边界，不是自动授权跑满三轮。
- 旧九资产轮保持停止，不调R16，不反复改旧池资金政策。80%仅愿景；20%仍为风险研究目标，30%不是止盈，不为保住浮盈改退出。所有已见历史仍为开发检验，前瞻从实际冻结后开始。

用户授权覆盖研究及必要数据查询，无需逐阶段重复确认；不自动实盘、不发远端、不重新全量补数。遇到确切数据不可得要保存有限调查结论，继续独立可做部分；不将目标缩成容易通过的小池。

'''
put(p, current + history)

p = 'docs/SECTOR_STOCK_STRATEGY_PLAN_2026_10_21.md'
s = read(p)
s = replace_once(s, '2026-10-21，设计版 v1。依据用户最新纠偏，遵守[研究共识 v3.3](RESEARCH_CONSENSUS.md)。', '2026-10-22，设计版 v2（初版2026-10-21）。依据用户最新纠偏，遵守[研究共识 v3.4](RESEARCH_CONSENSUS.md)。')
s = replace_once(s, '通过开仓、持有、卖出与适度分仓，能否捕捉足够多的大赢家，使整个账户在大行情中超过80%，并争取把最大回撤控制在20%以内？', '通过开仓、持有、卖出与适度分仓，板块信息能否改善大赢家实际参与与累计试错的经济取舍，并相对固定简单对照形成价值？')
s = replace_once(s, '| 行情目标 | 整户大行情收益>80%，最大回撤研究目标20% | 长期研究目标，尚未达到或验证 |', '| 行情愿景与风险 | 整户大行情80%仅作愿景/观察项；最大回撤研究目标20% | 80%不作为逐轮通过/继续门槛，20%不是触线强平，不隐含扩大风险 |')
s = replace_once(s, '首轮复盘完成后，每轮只改变一个问题：', '首轮复盘先按当前执行计划作支持/否定/证据不足裁决。以下仅为可能的问题清单，不是自动执行队列；只有主要对照或共同机制证据支持时，才一次冻结一个追加问题及配置上限：')
s = replace_once(s, '超过80%的一两个窗口不等于完成长期验证，不能只择最好起止。', '80%仅作情景愿景与描述项，不作为每轮晋升或继续条件；超过80%的一两个窗口不等于完成验证，未达到也不自动触发追加试验，不能只择最好起止。')
start = s.index('“可靠进展”须在相同范围')
end = s.index('\n\n## 9.', start)
s = s[:start] + ('“可靠进展”须在事前固定的完整主账户S0和主要对照T0上，结合成本/延迟、固定时期、尾部与普通损耗、现金及暴露体现可解释的经济价值。T1−T0、S0−T1只按事前定义解释机制，不事后换对照。仅某个小池或较弱中间版本改善可记局部发现，不能重置整个项目的停止计数。首轮10账户结束即作支持/否定/证据不足裁决；无共同新证据则停止该扩展，有证据才另冻一个有限追加轮。连续三轮不同问题无主要进展是最迟停止边界，不是必须跑满三轮。缺陷修复、完整负结论与局部发现分开记录，不以80%未到或新目录重置研究。') + s[end:]
s = replace_once(s, '**下一项实际工作是本地历史全池与缓存盘点，随后验证首批历史市值、南向资格和同源行业成员。**', '**D1本地盘点已完成；下一项实际工作是复核D2已保存的第1批响应，形成更码、历史市值、南向资格和行业成员裁决，再在剩余预算内接续验证。**')
put(p, s)

p = 'research_rounds/sector-stock-20261021/protocol.proposed.json'
d = json.loads(read(p));d['schema_version'] = 2;d['amended_date'] = '2026-10-22'
d['authority'] += ' User decision 2026-10-22: 80% is a large-market aspiration only, never a per-round pass or continuation gate; fix primary comparisons and finite stopping.'
ev = d['evaluation']
ev.pop('account_large_market_return_target')
ev['account_large_market_return_aspiration'] = 0.8
ev['aspiration_is_pass_or_continue_gate'] = False
ev['primary_account'] = 'S0'
ev['primary_comparator'] = 'T0'
ev['fixed_mechanism_contrasts'] = ['T1_minus_T0', 'S0_minus_T1', 'S0_minus_T0']
ev['assessment_layers'] = ['causal_mechanism', 'tail_and_ordinary_structure', 'net_economic_value_vs_fixed_controls', 'post_freeze_new_evidence']
ev['first_stage_accounts_limit'] = 10
ev['first_stage_disposition_required'] = ['supported', 'rejected', 'insufficient_evidence']
ev['followup_requires_new_common_evidence_and_separate_finite_freeze'] = True
ev['subpool_or_weaker_intermediate_progress_resets_project_stop_counter'] = False
ev['no_progress_three_is_latest_stop_not_minimum_rounds'] = True
ev['ordinary_loss_budget_and_rationale_before_account_freeze'] = None
d['freeze_requirements_remaining'].append('primary_comparison_interpretation_and_economic_ordinary_loss_budget_frozen_before_accounts')
put(p, json.dumps(d,ensure_ascii=False,indent=2)+'\n')

p = 'research_rounds/sector-stock-20261021/README.md';s=read(p)
s=s.replace('[共识v3.3]', '[共识v3.4]')
s=replace_once(s,'- 目标仍为大行情整个账户>80%、最大回撤研究目标20%；方案完成不代表目标验证。','- 80%保留为大行情愿景和观察项，不作为逐轮硬门槛；20%仍为回撤研究目标。主账户S0与主要对照T0固定，方案完成不代表经济优势。')
s=replace_once(s,'| D1，当前 |','| D1，已完成 |')
s=replace_once(s,'| D2 |','| D2，当前 |')
s=replace_once(s,'D1/D2完成后，可并行处理已可靠资料的S1/E1', 'D1盘点见[已保存报告](coverage/LOCAL_INVENTORY.md)；D2第1批已有18次公开GET及6次原生请求，应接续而非重跑。D1/D2完成后，可并行处理已可靠资料的S1/E1')
s=replace_once(s,'后续分仓、等待、退出、仓位研究按一轮一个问题推进，不自动全开。连续三轮不同机制无可靠进展后复查本轮真实全池失败，停止条件不能被“新目录”绕过。', '首轮10账户后必须作支持/否定/证据不足裁决；无共同新证据即停止该扩展，不因80%未到继续。后续分仓、等待、退出、仓位仅为条件式清单，一次另冻一个有限问题；局部子池击败中间方案不重置项目计数。连续三个不同问题无主要进展是最迟停止边界，不要求跑满，不被新目录或换agent绕过。')
s=replace_once(s,'2026-10-21启动设计。', '2026-10-21启动设计，2026-10-22按用户决定更新评价和停止条件。')
put(p,s)

p='AGENTS.md';s=read(p)
s=replace_once(s,'- 用户目标是大行情中**整个账户**超过 80%，最大回撤研究目标 20%；不是年年 80%，不是单笔涨幅 80%。尚未实现或验证。','- 用户2026-10-22决定：**80%仅保留为大行情整户愿景/观察项，不作为每轮通过、晋升或继续搜索门槛**；20%仍为回撤研究目标，不隐含扩大风险。固定S0主账户和T0主要对照，T1作机制拆解；局部小池/中间对照改善不重置项目停止计数。首轮10账户后裁决，无共同新证据即停止该扩展，有证据才另冻一个有限追加问题。旧九资产保持停止。')
s=s.replace('当前为全池两级选股方案完成，下一步本地名册/缓存盘点及历史市值、南向资格、同源行业成员验证；', '当前D1全池本地名册/缓存盘点已完成，D2第1批已有原始取证，先核查并接续历史市值、南向资格、同源行业成员验证；')
put(p,s)

status = ('\n\n' + decision + '\n\nD1本地盘点已有产物，D2第1批已有18次公开GET及6次原生请求；先复核已有响应和字段语义，再接续剩余预算，不重跑盘点或重置批次。新全池经济账户0，历史资格/行业/执行仍须通过。详见[当前计划](NEXT_RESEARCH_TASKS.md)。\n')
for p in ['docs/HANDOFF.md','docs/RESEARCH.md','docs/REPRODUCIBILITY.md','docs/DATA_SOURCES.md']:
 s=read(p);first,rest=s.split('\n',1)
 if p=='docs/HANDOFF.md':
  first='# 当前交接状态（2026-10-22）'
  rest=rest.replace('**唯一下一动作：本地历史证券名册与缓存盘点，随后首批历史市值/南向资格/同源行业成员取证。**', '**此段为2026-10-21旧入口，D1现已完成；当前动作以上方2026-10-22更新和执行计划为准。**')
 put(p,first+status+'\n## 2026-10-21及此前记录（当前动作以上方更新为准）\n'+rest)

p='README.md';s=read(p);first,rest=s.split('\n',1)
top='\n\n'+decision+'\n\n当前D1本地盘点已完成，D2第1批已有取证；先核查并接续历史市值、南向资格和同源行业成员，保持新全池账户0。见[共识v3.4](docs/RESEARCH_CONSENSUS.md)、[当前交接](docs/HANDOFF.md)、[执行计划](docs/NEXT_RESEARCH_TASKS.md)。\n\n## 2026-10-21及此前记录（当前动作以上方更新为准）\n'
put(p,first+top+rest)

p='TradingAlarm/research/TREND_RESEARCH_FOCUS.md';s=read(p);first,rest=s.split('\n',1)
put(p,first+'\n\n'+decision+'\n\nD1本地盘点已完成，D2已有第1批响应，先核实再有限补证。当前动作与判读标准以[共识v3.4](../../docs/RESEARCH_CONSENSUS.md)和[执行计划](../../docs/NEXT_RESEARCH_TASKS.md)为准。\n\n## 2026-10-21及此前记录\n'+rest)

(OUT/'manifest.json').write_text(json.dumps({'date':'2026-10-22','user_authorized':True,'formal_repository':str(ROOT),'files':changes},ensure_ascii=False,indent=2)+'\n')
diff=''
for p in changes:
 diff+=''.join(difflib.unified_diff((OUT/'prior'/p).read_text().splitlines(True),(OUT/'staged'/p).read_text().splitlines(True),fromfile=p+' before',tofile=p+' after'))
(OUT/'changes.diff').write_text(diff)
print(json.dumps({'staged_files':len(changes),'directory':str(OUT),'diff_lines':len(diff.splitlines())},ensure_ascii=False))
