"""Read-only extraction of saved original funding records. No strategy imports/runs."""
from pathlib import Path
import csv, gzip, hashlib, json

O = Path(__file__).resolve().parent
Q = O.parents[1]
BASE = Q / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
DOS = Q / 'current_strategy_source_dossier_v1/yingxin_chain'
SID = '000620.SZ'
SECTOR = 'URFI881153'
IDS = [68, 69, 75, 78, 113, 122]
sources = {}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p, lines=False):
    p = Path(p)
    sources[str(p.resolve())] = sha(p)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f:
        return [json.loads(line) for line in f] if lines else json.load(f)

def save(name, obj):
    (O / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def ref(p, where):
    return dict(path=str(Path(p).resolve()), index=where, index_base=0)

book = read(BASE / 'B.json.gz')
daily = read(BASE / 'daily.jsonl.gz', True)
funding = read(BASE / 'funding.jsonl.gz', True)
industry = read(BASE / 'industry.jsonl.gz', True)
old = read(DOS / 'ORIGINAL_SIX_LAYER_CHAIN.json')
chains = read(Q / 'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json')
ci, chain = next((i, c) for i, c in enumerate(chains) if c['campaign']['sid'] == SID)
observations = {x['day']: (i, x) for i, x in enumerate(chain['observations'])}
rows = []
objects = []
for e in old:
    lid, fi, t = e['layer'], e['original_frozen_intent'], e['actual_buy']
    assert lid in IDS
    jfi, jf = next((i, x) for i, x in enumerate(book['journal']) if x.get('kind') == 'real_buy_fill' and x.get('layer') == lid)
    jri, jr = next((i, x) for i, x in enumerate(book['journal']) if x.get('kind') == 'real_reserve' and x.get('budget_order') == jf['budget_order'])
    bo = book['budget']['orders'][jf['budget_order']]
    fni, fn = next((i, x) for i, x in enumerate(funding) if x.get('account') == 'B' and x.get('sid') == SID and x.get('at') == t['at'] and x.get('role') == fi['role'] and x.get('result') == 'reserved')
    di, de = next((i, x) for i, x in enumerate(book['decisions']) if x['at'] == t['signal_at'])
    ii, intent = next((i, x) for i, x in enumerate(de['intents']) if x.get('sid') == SID and x['role'] == fi['role'])
    dyi, dy = next((i, x) for i, x in enumerate(daily) if x['at'] == t['signal_at'] and x['account'] == 'B')
    ti, trade = next((i, x) for i, x in enumerate(book['trades']) if x.get('side') == 'buy' and x.get('layer') == lid)
    auri, au = next((i, x) for i, x in enumerate(book['audit']) if x == e['original_actual_reserve'])
    aufi, af = next((i, x) for i, x in enumerate(book['audit']) if x == e['original_fill_audit'])
    fin_candidates = [(i, x) for i, x in enumerate(industry) if x.get('account') == 'B' and x['sector'] == SECTOR and x['day'] <= t['signal_at'][:10]]
    fini, fin = fin_candidates[-1]
    assert intent == fi and trade == t and jr['pool'] == jf['pool'] == fn['pool']
    assert au['target_shares'] == t['shares'] == fn['shares'] == jr['shares']
    assert bo['attempt'] == jf['attempt'] and fin['attempt'] == bo['attempt'] and fin['episode'] == bo['episode']
    row = dict(layer=lid, signal_at=t['signal_at'], actual_OPEN=t['at'], role=fi['role'], pool_at_reserve_and_fill=jf['pool'],
        signal_NAV=de['nav'], signal_available=dy['available'], signal_shared_loss=dy['shared_loss'],
        OPEN_before_this_reserve_available_prior_audited_bridge=e['original_OPEN_before_reserve_available_cash'],
        frozen_gross_budget=fi['budget'], frozen_risk_budget=fi.get('risk_budget'), frozen_cap=fi['cap'], reserved_target=au['target_shares'], actual_qty=t['shares'],
        raw_OPEN=t['raw_open'], fill_price=t['price'], buy_fee=t['fees_cny'], floor_adjusted=t['floor'], floor_raw=e['actual_initial_floor_raw'],
        actual_intent_CP_id=fi.get('CP1_id'), market_CP_id=None if e['signal_CP_canonical_receipt'] is None else e['signal_CP_canonical_receipt']['receipt_id'],
        budget_episode=bo['episode'], budget_attempt=bo['attempt'], latest_financial_event_day=fin['day'], latest_event_financial_level=fin['financial_level'], latest_event_result=fin['result'],
        direct_reserve_financial_level='NOT_RECORDED', direct_reserve_financial_status='NOT_RECORDED',
        signal_market_stage=e['signal_industry_stage'], signal_market_attempt=e['signal_industry_attempt'], signal_market_authorization=e['signal_industry_auth'])
    rows.append(row)
    objects.append(dict(summary=row, original_signal_opportunity=e['original_signal_opportunity'], original_frozen_intent=intent,
        original_signal_market_industry=e['signal_industry_state'], original_market_CP_cache=e['signal_CP_cache'], original_market_CP_canonical=e['signal_CP_canonical_receipt'],
        latest_prior_original_industry_financial_event=fin, original_funding_result=fn, original_reserve_journal=jr, original_fill_journal=jf,
        original_actual_reserve_audit=au, original_actual_fill_audit=af, original_buy_trade=trade,
        serialized_budget_order_at_final_dump=bo,
        final_dump_warning='qty/status are final stored order fields, not the original reserve snapshot; use reserve/fill journals for at-time qty and pool.',
        original_signal_daily_funding_fields={k: dy.get(k) for k in ['at','nav','available','order_reserved','pool_probe','pool_confirmed','shared_loss','on']},
        prior_audited_cash_bridge_origin=dict(path=str((DOS/'ORIGINAL_SIX_LAYER_CHAIN.json').resolve()), layer=lid, field='original_OPEN_before_reserve_available_cash', note='Reused existing read-only audit-cash bridge; not a field directly logged on reserve. Not recalculated here.'),
        raw_source_references=dict(decision=ref(BASE/'B.json.gz', f'decisions[{di}].intents[{ii}]'), trade=ref(BASE/'B.json.gz',f'trades[{ti}]'),
            reserve_audit=ref(BASE/'B.json.gz',f'audit[{auri}]'), fill_audit=ref(BASE/'B.json.gz',f'audit[{aufi}]'), reserve_journal=ref(BASE/'B.json.gz',f'journal[{jri}]'), fill_journal=ref(BASE/'B.json.gz',f'journal[{jfi}]'),
            budget_order=ref(BASE/'B.json.gz',f'budget.orders[{jf["budget_order"]!r}]'), daily=ref(BASE/'daily.jsonl.gz',dyi), funding=ref(BASE/'funding.jsonl.gz',fni), financial_event=ref(BASE/'industry.jsonl.gz',fini)),
        missing=['No at-reserve sector level/active/status snapshot in reserve/fill/funding rows.', 'No saved per-pool searched q values or winning/losing route constraint vector for successful orders.', 'No timestamped sector/episode loss bucket at each funding slot; final budget.losses is not backfilled.']))

assert [r['layer'] for r in rows] == IDS
assert len({r['budget_episode'] for r in rows}) == len({r['budget_attempt'] for r in rows}) == 1
save('SIX_FUNDING_ORIGINAL_FIELDS.json', objects)
with (O/'SIX_FUNDING_TABLE.csv').open('w') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

timeline = []
for di, d in enumerate(book['decisions']):
    day = d['at'][:10]
    if not '2022-01-07' <= day <= '2022-01-25': continue
    intents = [dict(original_intent_index=i, fields=x) for i, x in enumerate(d['intents']) if x.get('sid') == SID]
    dyi, dy = next((i, x) for i, x in enumerate(daily) if x['at'] == d['at'] and x['account'] == 'B')
    obs = observations.get(day)
    timeline.append(dict(day=day, CLOSE_at=d['at'], decision_index=di, daily_index=dyi, original_intents=intents,
        original_CLOSE_fields={k:dy.get(k) for k in ['nav','available','order_reserved','shared_loss','pool_probe','pool_confirmed','on','pending_sells']},
        same_stock_original_CLOSE_layers=[x for x in dy['layers'] if x['sid']==SID],
        original_chain_industry=None if obs is None else obs[1]['industry'],
        original_chain_index=None if obs is None else f'[{ci}].observations[{obs[0]}]',
        note='Jan07 signal is included only to identify Jan10 morning rejects; Jan10 morning is not Jan10 CLOSE funding.'))
save('ORIGINAL_CLOSE_TIMELINE.json', timeline)
related_funding=[dict(source_index=i, original=x) for i,x in enumerate(funding) if x.get('account')=='B' and x.get('sid')==SID and '2022-01-10'<=x.get('at','')[:10]<='2022-01-26']
save('ALL_RECORDED_FUNDING_AND_REJECTIONS.json',related_funding)
events=[dict(source_index=i, original=x) for i,x in enumerate(industry) if x.get('account')=='B' and x['sector']==SECTOR and '2022-01-01'<=x['day']<='2022-01-26']
save('INDUSTRY_FINANCIAL_CHANGE_EVENTS.json',events)
loss_focus=dict(daily_records=[x for x in timeline if x['day'] in ['2022-01-19','2022-01-20','2022-01-21']],
    actual_sell_journal=[dict(source_index=i,original=x) for i,x in enumerate(book['journal']) if x.get('sid')==SID and x.get('kind')=='real_sell_fill' and x.get('at','')[:10]=='2022-01-20'],
    original_loss_field_scope='daily.shared_loss is whole-account cumulative shared-loss, not Yingxin-only and not the change solely caused by its sale. No new sums/differences calculated.',
    per_sector_per_episode_at_time_loss='NOT_RECORDED_IN_SELECTED_DAILY_JOURNAL_FUNDING_SNAPSHOTS',
    final_budget_losses_not_used=True)
save('LOSS_MEMORY_ORIGINAL_FIELDS.json',loss_focus)

codes={
 'planning_and_opening':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),
 'route_before_No60_transform':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/route_without_account_check.py'),
 'No60_transform_and_adapter':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py'),
 'No60_native_adapter':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py'),
 'budget_model_before_No60_transform':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py'),
 'previous_effective_route_text':DOS/'NO60_ACTIVE_ROUTE_SOURCE.txt'}
for p in codes.values(): sources[str(p.resolve())]=sha(p)
save('SOURCE_MANIFEST.json',dict(source_sha256=sources,code_paths={k:str(v.resolve()) for k,v in codes.items()},script_sha256=sha(__file__),
    scope='Only saved original book/daily/chain extraction and static source reading.',new_accounts=0,new_models=0,new_backtests=0,new_counterfactuals=0,strategy_imports=0))

fmt=lambda v:'缺失' if v is None else f'{float(v):,.2f}'
lines=['# 盈新六次获资：原账字段与状态记忆','',
'范围：000620.SZ，Jan10—Jan25信号/成交；附Jan7→Jan10及Jan25→Jan26边界。只读既有原账、daily和已封证据，0模型、0账户、0回测、0新反事实。索引均从0起。','',
'|层|信号→实际OPEN|role / 实际pool|原cap→reserve/filled|信号NAV / available|原gross预算 / CORE risk预算|初始raw保护线|',
'|---|---|---|---:|---:|---:|---:|']
for r in rows:
    lines.append(f'|{r["layer"]}|{r["signal_at"][:10]}→{r["actual_OPEN"][:10]}|{r["role"]} / {r["pool_at_reserve_and_fill"]}|{r["frozen_cap"]}→{r["reserved_target"]}/{r["actual_qty"]}|{fmt(r["signal_NAV"])} / {fmt(r["signal_available"])}|{fmt(r["frozen_gross_budget"])} / {fmt(r["frozen_risk_budget"])}|{r["floor_raw"]}|')
lines += ['', '六笔pool由原real_reserve、real_buy_fill和funding reserved三方逐值对齐；不使用期末layer metadata的pool回填。逐笔价格/费用、OPEN该槽位现金的既有审计桥、原CP全文和原索引在SIX_FUNDING_ORIGINAL_FIELDS.json / CSV。现金桥是已封旧审计结果，不是reserve原行中的现金字段，本次没有复算。','',
'六笔预算episode相同：`'+rows[0]['budget_episode']+'`；六笔预算attempt相同：`'+rows[0]['budget_attempt']+'`。上游market attempt另为`'+rows[0]['signal_market_attempt']+'`，不是同一个字段；上游authorization为`'+rows[0]['signal_market_authorization']+'`。','',
'六笔信号时market stage原字段均confirmed；截至各信号日最后一条原金融变更事件均是2022-01-07：result=confirmed、financial_level=1（industry原行61）。这是最后已记录变更，不等于逐reserve现场完整快照。reserve/fill/funding行没有financial_level、active/status、各池试算q和成功获资约束向量，全部标NOT_RECORDED；不以期末budget.sectors补写。','',
'为何68为probe、之后为confirmed：原日志证明结果。有效route源码限定core只有probe候选；mobile且expand、金融level>0并migrate成功才追加confirmed，比较两池可买量、probe同量优先。这解释机制许可，不证明每次confirmed的另一池具体q或哪一道门约束了数量，原日志未存。No60实际route仅对probe保pool_capital，不误引旧confirmed60上限。','',
'Jan10 CLOSE原opportunity roles=[core,mobile]，decision同时保存CORE cap3200/gross预算8804.37与MOBILE cap7200/gross预算19913.762962110280090（CP ca675c13…）。Jan11 OPEN core先reserved 100，J.opening先按rank再core优先，成功后done.add(sid)，同股后续mobile命中continue；没有mobile拒单记录，不能称被拒。CORE本身CP1_id=None，不能把当日市场CP贴成CORE用过的凭证。','',
'原decision在Jan14、17、18、19均没有该股intent；这只表示原保存列表为空，不追加后验失败状态。Jan7 CLOSE的core/mobile请求在Jan10上午均有cash_or_original_reserve,probe_risk拒绝，属于Jan7信号，和Jan10 CLOSE的两请求分开。Jan20 CLOSE mobile cap5900在Jan21 OPEN原记录拒绝cash_or_original_reserve,sector_capital；Jan21 CLOSE是另一个新CP mobile，Jan24 OPEN成交5100。','',
'## 1/19退出请求、1/20卖出、1/21再次申请的已存损耗','',
'|原CLOSE日期|原daily index|全账户shared_loss|该股intent|',
'|---|---:|---:|---|']
for x in loss_focus['daily_records']:
    lines.append(f'|{x["day"]}|{x["daily_index"]}|{x["original_CLOSE_fields"]["shared_loss"]}|{[(z["fields"]["role"],z["fields"]["cap"]) for z in x["original_intents"]]}|')
lines += ['',
'Jan19 CLOSE原pending_sells含000620.SZ；Jan20 09:30 journal[230]真实卖出69/75/78共16200股，价2.948525、费用61.5561795135000。Jan21 CLOSE又有fresh_CP1_mobile原intent。上表shared_loss是全账户累计原字段，不能把日间增量归给盈新一股，也不能当作该行业或该attempt损耗。所选原daily/journal/funding没有同股/行业/attempt当时累计loss快照；期末budget.losses不回填。','',
'Jan25 09:30先成交122（来自Jan24 CLOSE）；Jan25 CLOSE行业市场controller才发生confirmed→observe、action=end_attempt、reason=mobile_line、authorization撤销，原industry金融变更行412为invalidated（level字段仍1）。同一个Jan25 CLOSE原规划仍保存一笔mobile cap4200；Jan26 OPEN原funding以industry_invalidated拒绝。不能把Jan25晚间失效倒填至Jan25早上，亦不能把level仍1理解为active仍真。','',
'## 源码与原记录入口','',
'- joint_v3.py:195–212：行业market记录驱动预算observe，且只在result不为unchanged时写金融变更事件。',
'- joint_v3.py:241–259：原roles、barriers、CORE/MOBILE intent、frozen cap；:259保存daily.shared_loss与pool总量。',
'- joint_v3.py:302–324：先退出/结算，再按rank与core优先，done/pending阻止同股第二reserve，之后调用fill。',
'- route_without_account_check.py:3–10、24–29 + component.py:17–34：真实No60路由来源、pool候选及最大合法量选择；NO60_ACTIVE_ROUTE_SOURCE.txt是已封有效文本。',
'- model_without_account_check.py:73–90、210–262：loss桶的sector+original episode键、shared_loss求和、request；record_only不把损耗记忆清零。这里只解释源码，不生成历史桶快照。','',
'逐笔原对象及索引：SIX_FUNDING_ORIGINAL_FIELDS.json；完整原请求/边界：ORIGINAL_CLOSE_TIMELINE.json与ALL_RECORDED_FUNDING_AND_REJECTIONS.json；原金融变更：INDUSTRY_FINANCIAL_CHANGE_EVENTS.json；1/19—21：LOSS_MEMORY_ORIGINAL_FIELDS.json。SOURCE_MANIFEST.json绑定输入与源码sha。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(status='PASS_READ_ONLY_SAVED_RECORD_EXTRACTION',layers=IDS,matched_reserve_funding_fill=6,
    identical_budget_episode=True,identical_budget_attempt=True,market_and_budget_attempt_differ=True,
    direct_at_reserve_level_status='NOT_RECORDED',per_pool_search_quantity='NOT_RECORDED',per_sector_episode_loss_snapshots='NOT_RECORDED',
    cash_bridge_reused_not_recomputed=True,new_accounts=0,new_models=0,new_backtests=0,new_counterfactuals=0,strategy_imports=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print(json.dumps(dict(status='PASS',six_layers=IDS,output=str(O),readout_sha256=sha(O/'READOUT.md')),ensure_ascii=False))
