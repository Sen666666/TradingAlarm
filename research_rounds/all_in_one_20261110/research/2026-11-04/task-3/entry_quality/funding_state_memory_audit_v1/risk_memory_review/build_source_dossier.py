"""Read source text only. No strategy imports, model calls or account runs."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

O = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Q = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
ROOT = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC = {
    'A': Q/'pvr_pool_feasibility/native_adapter.py',
    'P': Q/'pvr_pool_feasibility/component.py',
    'BASE': W/'account-risk-ablation-20261031/adapter.py',
    'MODEL_TEMPLATE': W/'account-risk-ablation-20261031/model_without_account_check.py',
    'ROUTE_TEMPLATE': W/'account-risk-ablation-20261031/route_without_account_check.py',
    'V': W/'case-stage-ledger-20261031/budget_v3/model.py',
    'J': W/'case-stage-ledger-20261031/v3/joint_v3.py',
    'L': W/'case-stage-ledger-20261031/v3/launch_v3.py',
    'N': W/'pvr-slot1-native-readiness-20261101/native_rank.py',
    'LR': ROOT/'lot-risk-allocation-20261029/code/study.py',
    'ACT': ROOT/'actual-risk-recovery-20261027/code/risk_policy.py',
    'ENTRY': O.parents[1]/'trend_exit_controls_v1/run_account.py',
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


text = {k: p.read_text() for k, p in SRC.items()}
literal = {}
for node in ast.parse(text['P']).body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        k = getattr(node.targets[0], 'id', '')
        if k in {'MG', 'PG', 'PN', 'RG', 'RN'}:
            literal[k] = ast.literal_eval(node.value)
model = text['MODEL_TEMPLATE'].replace(literal['MG'], '').replace(literal['PG'], literal['PN'])
route = text['ROUTE_TEMPLATE'].replace(literal['RG'], literal['RN'])
account_gate = "        if ar+risk > .03*budget_nav + 1e-9: failures.append('account_risk')\n"
assert text['V'].replace(account_gate, '') == text['MODEL_TEMPLATE']
for k, v in [('EFFECTIVE_NO60_MODEL', model), ('EFFECTIVE_NO60_ROUTE', route)]:
    p = O/(k+'.txt')
    p.write_text(v)
    SRC[k] = p
    text[k] = v
(O/'ACCOUNT_RISK_MODEL_TEXT_DIFF.txt').write_text(''.join(difflib.unified_diff(
    text['V'].splitlines(True), text['MODEL_TEMPLATE'].splitlines(True),
    fromfile=str(SRC['V']), tofile=str(SRC['MODEL_TEMPLATE']))))

sections = [
    ('A', 11, 40, '当前No60预算/route真正覆盖；未重建预算对象'),
    ('BASE', 5, 19, 'NoAccountBudget继承J.Budget；当前B账户由原构造建立'),
    ('J', 15, 31, '实际初始化20000/record_only；其余方法沿V继承'),
    ('J', 166, 175, 'B账户expand=True与单一sector_by_sid映射'),
    ('V', 239, 255, '对照：原全账户3%保护距离门，当前已被删'),
    ('MODEL_TEMPLATE', 236, 256, 'account-check移除后的request模板；损耗拒绝仍需非record_only'),
    ('P', 17, 34, '当前再移除confirmed60的三处字符串改写；本审未exec或compile'),
    ('EFFECTIVE_NO60_ROUTE', 1, 29, '静态还原的当前route全文；原模板经P替换，仅去confirmed60'),
    ('LR', 16, 31, 'CORE单笔保护风险及整手最大量函数'),
    ('LR', 42, 66, 'CORE信号.25%风险和OPEN复核'),
    ('J', 243, 259, 'MOBILE原2%gross与CORE resize、真实pending/daily输出'),
    ('V', 62, 104, '继承生效：losses初始化、累计损耗、record_only与新episode'),
    ('V', 106, 125, '继承生效：资源仅pool/sector分组相加；凭证epoch/attempt范围'),
    ('J', 36, 63, 'sync只同步真实余股、旧线、已知mark、现金与应收；不清损耗'),
    ('J', 104, 135, '实际native买卖回调loss：买费、毛负损益、卖费'),
    ('J', 177, 212, '行业初始化/observe调用：新episode、失败或行业CP推进'),
    ('V', 127, 160, '行业失败之后的凭证/时间推进要求；同观察失败优先'),
    ('V', 166, 186, 'invalidate保failed_bar；取消确认前保留余量'),
    ('EFFECTIVE_NO60_MODEL', 188, 205, '静态当前migrate：无60%检查，不更改现金/NAV/风险/损耗'),
    ('J', 213, 240, 'CLOSE更新current_nav，ACT独立step及ACT/I持仓退出'),
    ('J', 243, 251, 'ACT_paused、exit/buy pending等新仓障碍'),
    ('J', 302, 324, 'OPEN最终资助使用route；没有给current_nav重赋值'),
    ('ACT', 8, 29, 'ACT20 episode暂停/flat恢复独立于预算losses'),
    ('L', 59, 81, 'checkpoint保整个account字段/budget；restore直接还原'),
    ('N', 122, 136, 'rank wrapper校验/季度复制，不重置预算'),
    ('A', 42, 51, 'No60 restore只校验身份后调用原restore'),
    ('L', 98, 108, '月末checkpoint；不是年度/预算重置'),
    ('J', 325, 332, '最终原账输出losses与consumed'),
    ('ENTRY', 14, 26, 'BASELINE选A.Runner，fresh1m，无年度重置')
]
doc = [
    '# 当前No60：风险门与损耗/失败记忆源码原文',
    '',
    '只读取源文本、AST字面字符串和文件SHA；不导入策略、不调用模型、不执行组件中的exec/compile、无新测试/账户/回测。',
    '',
    '**方法归属：** A只把request换成P.MOD.Contract.request，migrate换成P.MOD.Contract.migrate；loss/resources/start/observe/valid等实际沿J.Budget→V.Contract继承。J.Budget.industry在B.expand=True时委托V。MODEL_TEMPLATE的其它fill/sell辅助方法没有作为当前ledger成交回调使用，实际回调见J104–135。',
    '',
    '**派生文本行号：** EFFECTIVE_NO60_*是本目录对P原字符串替换的只读静态还原；不能把它们的行号冒充原磁盘文件行号。原模板与P行号同时保留。',
]
index = []
for key, lo, hi, title in sections:
    p = SRC[key]
    lines = text[key].splitlines()
    assert 1 <= lo <= hi <= len(lines), (key, lo, hi)
    doc.extend(['', '## '+title, '', f'来源：[{p.name}:{lo}]({p}:{lo})；原文范围{lo}–{hi}。', '', '```python'])
    doc.extend(f'{i:4d} {lines[i-1]}' for i in range(lo, hi+1))
    doc.extend(['```'])
    index.append(dict(alias=key, path=str(p), first_line=lo, last_line=hi, sha256=sha(p), title=title))
(O/'EVIDENCE.md').write_text('\n'.join(doc)+'\n')
memory_fields = {
    'losses': 'V.__init__ creates {}; V.loss updates by sector/original episode. No clear/reset in scoped active path except new budget initialization or restoring saved state.',
    'shared_loss': 'sum(losses.values()), no independent mutable scalar reset.',
    'episode_loss': 'No field named episode_loss in the scoped current Budget/No60/J/ACT sources; industry-episode amount is losses[(sector, episode)].',
    'failed_bar': 'V.invalidate increases max; V.start carries old value; industry requires newer evidence.',
    'consumed_and_stock_requests': 'Account-wide sets preserved across sector start/invalidate; fresh original CP/request identities still required.',
    'ACT_episode': 'Separate risk_state epoch: resume sets peak=nav and increments episode; no budget loss reset in that source.'
}
result = {
    'status': 'PASS_STATIC_CURRENT_NO60_RISK_MEMORY_SOURCE_REVIEW',
    'remaining_blocks': [],
    'scope': 'Current original No60 BASELINE source only; no v2/v3 proposed new unit-risk contracts, no economic rerun.',
    'model_template_equals_original_minus_single_account3_line': True,
    'confirmed60_removal': ['migrate capital guard', 'request confirmed pool capital guard', 'route confirmed pool capital guard'],
    'source_sha256': {str(p): sha(p) for p in SRC.values()},
    'excerpt_index': index,
    'memory_field_semantics': memory_fields,
    'dual_NAV_clock': {
        'pool_sector': 'route nav = b.nav - pending_fees - current_buy_fee; b.nav uses OPEN sync known native marks and receivable equity, not forced all-stock finalOPEN marks.',
        'stock_cash_retention': 'a.current_nav is assigned at prior CLOSE J222; OPEN does not reassign it. Stock10% and cash10% retention use this signal NAV.'
    },
    'correlation_scope': 'resources filters by pool/sector then sums reference distance. No explicit covariance, cross-sector correlation coefficient, beta or common-gap stress term in these active budget/route functions. Shared cash/probe resources/ACT couple accounts economically but are not correlation modeling.',
    'future_interface_note_only': 'route.allowed prechecks, then request must return reserved; future request gates require synchronized route precheck. Risk unit changes need consistent existing resources and new-request/route risk; no changes made.',
    'no_current_episode_loss_identifier': all('episode_loss' not in text[k] for k in ['A','P','BASE','MODEL_TEMPLATE','ROUTE_TEMPLATE','V','J','L','N','ACT']),
    'new_strategy_imports': 0, 'new_model_calls': 0, 'new_tests': 0, 'new_accounts': 0, 'new_backtests': 0, 'new_strategy_edits': 0,
    'limits': ['Static source/alias attribution only, not fresh runtime instrumentation.', 'No original account data, losses or risk amounts recomputed.', 'Does not infer realized loss bounds, efficacy or historical coverage from formulas.']
}
(O/'SOURCE_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'source_files': len(SRC), 'excerpts': len(index), 'episode_loss_present': not result['no_current_episode_loss_identifier']}, ensure_ascii=False))
