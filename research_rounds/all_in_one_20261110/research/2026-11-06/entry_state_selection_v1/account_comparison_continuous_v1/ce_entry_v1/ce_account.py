"""One stock-rank-only CE intervention after original PVR planning.

No account is initialized or replayed on import. Immutable CE inputs stay in
module globals and are never serialized in the account checkpoint.
"""
from pathlib import Path
from collections import Counter
from types import MappingProxyType
import hashlib, importlib, json, math, pickle, sys
import pandas as pd

HERE = Path(__file__).resolve().parent
O = HERE.parent
CE_DIR = O.parent / 'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_timing_quality_v1/candidate_test/account_adapter'
sys.path.insert(0, str(O / 'inputs'))
import continuous_inputs as C
A, N, J = C.A, C.N, C.J
SUFFIX = ':CE_ALL_EMPTY_STOCK_SLOTS_V1'
# Final external API identity is pinned before handoff. No fallback API is used.
RANK_MODULE = 'empty_first_rank'
RANK_FUNCTION = 'rank_empty_first_stock_slots'
RANK_MANIFEST = 'EMPTY_FIRST_MANIFEST.json'
FINAL_MANIFEST_SHA256 = '7bc25d5e2fe74a50adde848979adf06860cdff8b3f58576caff0c186000699dd'
FINAL_RANK_SOURCE_SHA256 = '5f8e9462c9f2e1302ed0c4a47775eadcaa3dcffeb50abc59e3a6091ddffa0c9e'
CE_LOOKUP = None
CE_RANKER = None
CE_IDENTITY = None
CE_SOURCE_FREEZE = None
FRAME_COLUMNS = ['sid', 'rank', 'was_empty', 'has_mobile_intent', 'has_core_intent', 'PVR_score', 'PVR_ready']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def json_scalar(value):
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def configure_inputs():
    """Load verified, immutable full-pool fresh-CP CE, never an old account."""
    global CE_LOOKUP, CE_RANKER, CE_IDENTITY, CE_SOURCE_FREEZE
    if CE_LOOKUP is not None:
        verify_input_identity()
        return dict(CE_IDENTITY), dict(CE_SOURCE_FREEZE)
    assert sha(CE_DIR / RANK_MANIFEST) == FINAL_MANIFEST_SHA256, 'Final scope manifest changed'
    assert sha(CE_DIR / (RANK_MODULE + '.py')) == FINAL_RANK_SOURCE_SHA256, 'Final rank API changed'
    sys.path.insert(0, str(CE_DIR))
    module = importlib.import_module(RANK_MODULE)
    manifest = read(CE_DIR / RANK_MANIFEST)
    expected = dict(manifest['runtime_sha256'])
    assert manifest['status'] == 'READY_ALL_EMPTY_FIRST_ENTRY_SCOPE'
    expected.update(manifest['audit_sha256_by_file'])
    handoff = read(CE_DIR / 'EMPTY_FIRST_HANDOFF_HASHES.json')
    for name, digest in expected.items():
        assert handoff[name] == digest, ('Conflicting CE audit identity', name)
    expected.update(handoff)
    # The new, wider API needs its own sealed manifest, never the old narrow one.
    for name, digest in expected.items():
        assert sha(CE_DIR / name) == digest, ('CE handoff source drift', name)
    required = ['ce_adapter.py', RANK_MODULE + '.py', 'ADAPTER_MANIFEST.json',
                'ALL_NATIVE_CP_RECEIPT_CE.parquet', 'STOCK_COVERAGE.csv',
                'ADAPTER_AUDIT.json', 'PREFIX_CHECKS.csv', 'BUILD_FREEZE.json',
                'CACHE_SOURCE_HASHES.csv', 'EMPTY_FIRST_HANDOFF_HASHES.json', RANK_MANIFEST]
    sources = {str(CE_DIR / name): sha(CE_DIR / name) for name in required}
    sources.update({str(CE_DIR / name): digest for name, digest in expected.items()})
    build = read(CE_DIR / 'BUILD_FREEZE.json')
    for path, digest in build['input_sha256'].items():
        assert sha(path) == digest, ('CE formula/input identity drift', path)
        sources[path] = digest
    audit = read(CE_DIR / 'ADAPTER_AUDIT.json')
    assert audit['fixed_pool_symbols'] == 1709
    assert audit['source_complete_symbols'] == 1687 and audit['source_unavailable_symbols'] == 22
    assert audit['native_receipt_rows'] == 232520 and audit['full_prefix_checks'] == 5061
    assert audit['additional_receipt_keys_outside_original_candidate_domain'] == 177668
    assert audit['all_state_columns_prefix_exact'] and audit['source_hashes_unchanged']
    assert audit['no_account_state_dependency'] and audit['no_top_K_or_truncation']
    lookup = module.load_empty_first_inputs(directory=CE_DIR)
    identity = dict(policy=SUFFIX[1:], ranking_module=RANK_MODULE,
                    ranking_function=RANK_FUNCTION, handoff_manifest_sha256=sha(CE_DIR / RANK_MANIFEST),
                    score_manifest_sha256=sha(CE_DIR / 'ADAPTER_MANIFEST.json'),
                    score_table_sha256=sha(CE_DIR / 'ALL_NATIVE_CP_RECEIPT_CE.parquet'),
                    formula_sha256=build['formula_sha256'],
                    prefix_audit_sha256=sha(CE_DIR / 'PREFIX_CHECKS.csv'),
                    fixed_pool_symbols=1709, complete_symbols=1687, unavailable_symbols=22,
                    native_receipt_rows=232520, all_prefix_checks=5061,
                    scope='ALL_SIGNAL_CLOSE_EMPTY_STOCK_GROUPS_WITH_CURRENT_FRESH_CE_AND_KNOWN_PVR',
                    unknown_policy='EXACT_ORIGINAL_STOCK_SLOT', no_old_receipt_carry=True,
                    no_top_K=True, no_account_state_in_lookup=True)
    CE_LOOKUP, CE_RANKER = lookup, getattr(module, RANK_FUNCTION)
    CE_IDENTITY, CE_SOURCE_FREEZE = MappingProxyType(identity), MappingProxyType(sources)
    return dict(CE_IDENTITY), dict(CE_SOURCE_FREEZE)


def verify_input_identity():
    assert CE_LOOKUP is not None and CE_RANKER is not None
    for path, digest in CE_SOURCE_FREEZE.items():
        assert sha(path) == digest, ('CE immutable runtime input changed', path)


def nonrank_snapshot(intents):
    """Byte snapshot captures rich quote/clock/receipt fields without mutating them."""
    return pickle.dumps([{k: v for k, v in item.items() if k != 'rank'} for item in intents], protocol=5)


def candidate_roles(intents):
    return Counter((item['sid'], item['role']) for item in intents)


def pending_stock_frame(account):
    """Use actual current pending roles and signal-CLOSE quantity, not core_Q."""
    grouped = {}
    for item in sorted(account.pending, key=lambda x: (x['rank'], x['role'] != 'core')):
        sid, role = item['sid'], item['role']
        assert role in ('core', 'mobile'), ('unknown native role', role)
        if sid not in grouped:
            grouped[sid] = dict(sid=sid, rank=item['rank'], was_empty=account.quantity(sid) == 0,
                                has_mobile_intent=False, has_core_intent=False,
                                PVR_score=item['PVR_score'], PVR_ready=bool(item['PVR_ready']))
        row = grouped[sid]
        assert row['rank'] == item['rank'], ('same-stock native rank differs', sid)
        assert row['PVR_ready'] == bool(item['PVR_ready'])
        pvr = item['PVR_score']
        assert (row['PVR_score'] == pvr or
                (pd.isna(row['PVR_score']) and pd.isna(pvr))), ('same-stock PVR differs', sid)
        flag = 'has_' + role + '_intent'
        assert not row[flag], ('duplicate native role', sid, role)
        row[flag] = True
    frame = pd.DataFrame(list(grouped.values()), columns=FRAME_COLUMNS)
    frame['PVR_score'] = pd.to_numeric(frame['PVR_score'], errors='coerce').astype('float64')
    frame = frame.astype({'sid': 'str', 'rank': 'int64', 'was_empty': 'bool',
                          'has_mobile_intent': 'bool', 'has_core_intent': 'bool',
                          'PVR_score': 'float64', 'PVR_ready': 'bool'})
    assert frame['rank'].is_unique
    return frame


def apply_ce_priority(account, day, lookup, ranker):
    """Only change execution rank; preserve original PVR logs and every other field."""
    decision = account.decisions[-1]
    assert str(decision['at'])[:10] == day
    pending_before = nonrank_snapshot(account.pending)
    decisions_before = nonrank_snapshot(decision['intents'])
    roles_before = candidate_roles(account.pending)
    assert roles_before == candidate_roles(decision['intents'])
    object_order = [id(i) for i in account.pending]
    frame = pending_stock_frame(account)
    quantities = {sid: account.quantity(sid) for sid in frame.sid}
    ranked, audit = ranker(frame, day, lookup)
    assert len(ranked) == len(frame) and not ranked.sid.duplicated().any()
    pd.testing.assert_frame_equal(ranked[FRAME_COLUMNS].sort_values('sid').reset_index(drop=True),
                                  frame.sort_values('sid').reset_index(drop=True), check_exact=True)
    assert sorted(ranked.ce_stock_rank) == sorted(frame['rank'])
    keys = {}
    rows = []
    old_slot_values = {rank: rank for rank in frame['rank'].tolist()}
    for row in ranked.to_dict('records'):
        sid = row['sid']
        pvr_finite = bool(row['PVR_ready']) and math.isfinite(float(row['PVR_score']))
        ce_finite = bool(row['CE_known']) and math.isfinite(float(row['CE']))
        movable = bool(row['was_empty']) and pvr_finite and ce_finite
        assert bool(row['CE_movable_stock_slot']) == movable, ('wrong CE scope', sid)
        if not movable:
            assert row['ce_stock_rank'] == row['rank'], ('fixed stock slot moved', sid)
        keys[sid] = old_slot_values[row['ce_stock_rank']]
        reason = ('held_at_signal_close' if not row['was_empty'] else
                  'original_PVR_unknown_or_not_ready' if not pvr_finite else
                  'no_current_fresh_CE:' + row['CE_status'] if not ce_finite else
                  'eligible_empty_stock_slot')
        roles = [role for role in ('core', 'mobile') if row['has_' + role + '_intent']]
        rows.append(dict(account=account.label, signal_day=day,
                         **{k: json_scalar(v) for k, v in row.items()}, roles=roles,
                         original_rank=json_scalar(row['rank']), new_rank=keys[sid],
                         quantity_at_signal_close=int(quantities[sid]), eligibility_reason=reason,
                         rank_changed=keys[sid] != row['rank']))
    for item in account.pending + decision['intents']:
        item['rank'] = keys[item['sid']]
    assert nonrank_snapshot(account.pending) == pending_before, 'Non-rank pending field changed'
    assert nonrank_snapshot(decision['intents']) == decisions_before, 'Non-rank decision field changed'
    assert candidate_roles(account.pending) == roles_before == candidate_roles(decision['intents'])
    assert [id(i) for i in account.pending] == object_order, 'Intent list order changed'
    for item in account.pending + decision['intents']:
        assert item['rank'] == keys[item['sid']], ('stock/decision rank mismatch', item['sid'])
    assert quantities == {sid: account.quantity(sid) for sid in frame.sid}, 'Position changed during ranking'
    # No changed role order: native opening will still sort (rank, role != core).
    role_groups = {sid: [] for sid in keys}
    for item in sorted(account.pending, key=lambda x: (x['rank'], x['role'] != 'core')):
        role_groups[item['sid']].append(item['role'])
    for actual in role_groups.values():
        assert actual == sorted(actual, key=lambda role: role != 'core')
    audit = dict(audit, account=account.label, native_pending_intents=len(account.pending),
                 unchanged_candidate_role_multiset=True, unchanged_all_nonrank_intent_fields=True,
                 original_priority_rank_and_PVR_preserved=True, unchanged_pending_list_order=True,
                 was_empty_measured_at='AFTER_NATIVE_PLANNING_SIGNAL_CLOSE',
                 ranking_calls_at_OPEN=0,
                 pending_nonrank_sha256=hashlib.sha256(pending_before).hexdigest(),
                 decisions_nonrank_sha256=hashlib.sha256(decisions_before).hexdigest())
    return rows, audit


class CERunner(A.Runner):
    route = A.Runner.route
    opening = J.Runner.opening

    def planning(self, at):
        assert self.market.phase == 'CLOSE' and self.market.phase_at == at
        N.Runner.planning(self, at)
        for account in self.accounts.values():
            rows, audit = apply_ce_priority(account, str(at.date()), CE_LOOKUP, CE_RANKER)
            self.ce_stock_rank_audit.extend(rows)
            self.ce_day_audit.append(audit)

    def assert_native_wiring(self):
        assert self.integration_policy == A.POLICY + ':' + self.rank_mode + SUFFIX
        assert self.rank_mode == 'PVR_SLOT1'
        assert self.rank_scores_manifest_sha256 == N.SCORES.manifest_sha256
        assert self.planning.__func__ is CERunner.planning
        assert self.route.__func__ is A.Runner.route
        assert self.opening.__func__ is J.Runner.opening
        assert self.ce_input_identity == dict(CE_IDENTITY)
        assert self.ce_source_freeze == dict(CE_SOURCE_FREEZE)
        assert 'CE_LOOKUP' not in self.__dict__ and 'ce_lookup' not in self.__dict__
        for account in self.accounts.values():
            assert type(account) is J.Account and type(account.budget) is A.NoConfirmed60Budget
            assert account.budget.request.__func__ is A.P.MOD.Contract.request
            assert account.budget.migrate.__func__ is A.NoConfirmed60Budget.migrate
            for name in ('reserve_quantity', 'fill_buy', 'fill_exit', 'cancel_buy', 'split', 'sync', 'assert_budget_view', 'expire_day_buys'):
                assert getattr(account, name).__func__ is getattr(J.Account, name)

    def restore(self, path):
        verify_input_identity()
        payload = pickle.loads(Path(path).read_bytes())
        assert payload['runner']['ce_input_identity'] == dict(CE_IDENTITY), 'Checkpoint CE identity differs'
        assert payload['runner']['ce_source_freeze'] == dict(CE_SOURCE_FREEZE), 'Checkpoint CE source freeze differs'
        result = A.Runner.restore(self, path)
        self.assert_native_wiring()
        return result


def install(runner):
    """Install only after the unmodified original constructor/bootstrap passes."""
    assert CE_LOOKUP is not None and CE_RANKER is not None, 'Configure frozen CE inputs first'
    runner.assert_native_wiring()
    runner.__class__ = CERunner
    runner.integration_policy += SUFFIX
    runner.ce_input_identity = dict(CE_IDENTITY)
    runner.ce_source_freeze = dict(CE_SOURCE_FREEZE)
    runner.ce_stock_rank_audit = []
    runner.ce_day_audit = []
    runner.assert_native_wiring()
