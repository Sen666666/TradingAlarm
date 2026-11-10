"""V4 pure signals: original CP formula under V3 hold/P and conditional permissions."""
from pathlib import Path
import importlib.util
import hashlib
import json
import math
import copy
import csv
import pandas as pd
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FREEZE = BASE / 'SIGNAL_FREEZE_V4.md'
V3_PATH = BASE / 'signal_traces_v3/signal_trace.py'
CP_PATH = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if v is None or v is pd.NA: return None
    if isinstance(v, pd.Timestamp): return str(v.date())
    if isinstance(v, np.generic): v = v.item()
    return None if isinstance(v, float) and not math.isfinite(v) else v
def encoded(v): return json.dumps(clean(v), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
def identity(v): return hashlib.sha256(encoded(v).encode()).hexdigest()
def save(p, v): p.write_text(json.dumps(clean(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def selected(sid, day):
    return '2022-01-01' <= day <= '2022-01-31' if sid == '000620.SZ' else ('2024-01-01' <= day <= '2024-01-31' or '2024-09-01' <= day <= '2024-11-27')


class PermissionFSM:
    """Only permission issuance memory. No positions, money, fills or reservations."""
    def __init__(self, version, sid, branch):
        self.version, self.sid, self.branch = version, sid, branch
        self.up = None; self.up_used = False; self.segment = None
        self.observed_days = set(); self.seen_cp = {}; self.issued = 0

    def observe(self, t):
        if t['day'] in self.observed_days: return
        self.observed_days.add(t['day'])
        if t['source_segment'] != self.segment:
            self.segment = t['source_segment']; self.up = None; self.up_used = False
        if t['down_event'] is not None:
            self.up = None; self.up_used = False
        if t['trial_event'] is not None:
            event_id = t['trial_event']['L']['source_event_id']
            self.up = (self.version, self.sid, t['source_segment'], event_id)
            self.up_used = False

    def decide(self, t, cp_key, context):
        if cp_key in self.seen_cp:
            old = self.seen_cp[cp_key]
            return dict(purpose='REPLAY', reason='SAME_CP_NO_SECOND_PERMISSION',
                        intent_id=old['intent_id'], original_purpose=old['purpose'], issued_now=False,
                        up_credit_key=self.up, up_used_before=self.up_used, up_used_after=self.up_used)
        before = self.up_used; purpose = 'BLOCK'; reason = None
        ctx = ('has_position', 'pending_buy', 'pending_exit', 'cancel_ack_pending', 'protection_checks_passed', 'exit_required_today')
        if any(context.get(k) is None for k in ctx): reason = 'UNKNOWN_EXTERNAL_EXECUTION_CONTEXT'
        elif context['exit_required_today']: reason = 'EXIT_REQUIRED_TODAY_PRIORITY'
        elif context['pending_exit']: reason = 'PENDING_EXIT_NOT_ACKED'
        elif context['pending_buy']: reason = 'PENDING_BUY_NOT_ACKED'
        elif context['cancel_ack_pending']: reason = 'CANCEL_ACK_PENDING'
        elif not context['protection_checks_passed']: reason = 'EXIT_OR_PROTECTION_PRIORITY'
        elif t['I_hold'] is not True or not t['price_close_valid']: reason = 'I_HOLD_FALSE_OR_UNKNOWN'
        elif not t['up_after_R'] or self.up is None: reason = 'WAIT_NEW_ORIGINAL_UP'
        elif context['has_position'] and t['I_expand'] is True:
            purpose = 'MATURE_CP_ADD'; reason = 'HELD_MATURE_ONE_CP_ONE_PURPOSE'; self.up_used = True
        elif not self.up_used:
            purpose = 'START_CP_PROBE'; reason = 'NEW_UP_ONCE_PERMISSION'; self.up_used = True
        else: reason = 'UP_PERMISSION_ALREADY_ISSUED_OR_SETTLED'
        issued = purpose != 'BLOCK'
        intent_id = identity((self.version, self.sid, self.branch, cp_key, purpose, self.up)) if issued else None
        result = dict(purpose=purpose, reason=reason, intent_id=intent_id, issued_now=issued,
                      up_credit_key=self.up, up_used_before=before, up_used_after=self.up_used)
        # Expired/rejected CP is cached too: later replay never creates a new permission.
        self.seen_cp[cp_key] = copy.deepcopy(result)
        self.issued += int(issued)
        return result


def build_market(sid, price, events, q, event_sha, v3, cp):
    trace = v3.trace(sid, price, events, event_sha)
    lookup = {r['day']: r for r in trace}
    assert q.index.isin(price.index).all()
    assert np.array_equal(q.close.to_numpy(), price.loc[q.index, 'close'].to_numpy())
    assert np.array_equal(q.amount.to_numpy(), price.loc[q.index, 'amount'].to_numpy())
    assert q.e0_down.equals(events.reindex(q.index).event.eq(-1))
    known_hold = [lookup[str(t.date())]['I_hold'] for t in q.index]
    floor = [lookup[str(t.date())]['P_new'] for t in q.index]
    f = q.copy()
    f['e0_valid'] = pd.Series([v is True for v in known_hold], index=q.index, dtype=bool)
    f['i_target'] = f.e0_valid.astype(int)
    f['i_floor'] = pd.Series(floor, index=q.index, dtype=float)
    assert np.isfinite(f.close).all() and f.close.gt(0).all()
    assert np.isfinite(f.amount).all() and f.amount.gt(0).all()
    result = cp.calculate(f)
    status = {}
    ever_prepared = False
    for row in trace:
        if row['original_event_ready']: ever_prepared = True
        day = row['day']; t = pd.Timestamp(day)
        if t not in q.index: why = 'NO_ORIGINAL_CP_OBSERVATION_UNKNOWN'
        elif row['I_hold'] is None: why = 'I_CURRENT_UNKNOWN' if ever_prepared else 'I_NOT_PREPARED'
        elif not row['price_close_valid']: why = 'PRICE_UNKNOWN'
        else: why = 'KNOWN'
        status[day] = why
    return trace, result, status


def condition_rows(sid, trace, cpstar, status, version):
    fsm = {b: PermissionFSM(version, sid, b) for b in ('HELD', 'FLAT')}
    out = []
    for t in trace:
        for engine in fsm.values(): engine.observe(t)
        stamp = pd.Timestamp(t['day'])
        row_cp = None if stamp not in cpstar.index else clean(cpstar.loc[stamp].to_dict())
        receipt = bool(row_cp and row_cp['receipt'] and status[t['day']] == 'KNOWN')
        cp_key = None if not receipt else (version, sid, t['source_segment'], t['day'])
        branches = {}
        for branch, engine in fsm.items():
            context = dict(has_position=branch == 'HELD', pending_buy=False, pending_exit=False,
                           cancel_ack_pending=False, protection_checks_passed=True,
                           exit_required_today=bool(t['support_exit_events']))
            if receipt:
                decision = engine.decide(t, cp_key, context)
                before = engine.issued
                replay = engine.decide(t, cp_key, context)
                assert replay['purpose'] == 'REPLAY' and engine.issued == before
                assert replay['intent_id'] == decision['intent_id']
                decision['same_CP_replay_checked'] = True
            else:
                decision = dict(purpose='NO_CP_RECEIPT', reason=status[t['day']] if status[t['day']] != 'KNOWN' else 'NO_NEW_CP',
                                intent_id=None, issued_now=False, up_credit_key=engine.up,
                                up_used_before=engine.up_used, up_used_after=engine.up_used)
            if branch == 'FLAT': assert decision['purpose'] != 'MATURE_CP_ADD'
            branches[branch] = dict(external_context_assumption=context,
                context_scope='Fixed hypothetical condition each day, including original layer protection/exit checks assumed passed; no positions or fill transition.', **decision)
        out.append(dict(sid=sid, day=t['day'], V3=t, CP_star=row_cp, CP_input_status=status[t['day']],
                        CP_star_receipt=receipt, CP_star_key=cp_key, branches=branches))
    return out


def logic_checks():
    def row(day, mature=False, up=True):
        return dict(day=day, source_segment='0', down_event=None, trial_event=None,
                    I_hold=True, I_expand=mature, price_close_valid=True, up_after_R=up)
    ctx = dict(has_position=False, pending_buy=False, pending_exit=False, cancel_ack_pending=False, protection_checks_passed=True, exit_required_today=False)
    t = row('D1', True); t['trial_event'] = {'L': {'source_event_id': 'up1'}}
    h = PermissionFSM('logic', 'sid', 'HELD'); h.observe(t)
    assert h.decide(t, ('c1',), dict(ctx, has_position=True))['purpose'] == 'MATURE_CP_ADD'
    assert h.up_used and h.decide(row('D2'), ('c2',), dict(ctx, has_position=True))['purpose'] == 'BLOCK'
    f = PermissionFSM('logic', 'sid', 'FLAT'); f.observe(t)
    assert f.decide(t, ('c1',), ctx)['purpose'] == 'START_CP_PROBE'
    assert f.decide(t, ('c1',), ctx)['purpose'] == 'REPLAY'
    assert f.issued == 1
    # There is deliberately no fill callback/refund; zero fill cannot return issuance credit.
    assert f.decide(row('D2', True), ('c2',), ctx)['purpose'] == 'BLOCK'
    t2 = row('D3'); t2['trial_event'] = {'L': {'source_event_id': 'up2'}}; f.observe(t2)
    assert f.decide(t2, ('c3',), dict(ctx, pending_exit=True))['reason'] == 'PENDING_EXIT_NOT_ACKED'
    assert f.decide(t2, ('c3',), ctx)['purpose'] == 'REPLAY'
    assert f.decide(t2, ('c4',), ctx)['purpose'] == 'START_CP_PROBE'
    down = row('D4', False, False); down['down_event'] = {'kind': 'down'}; f.observe(down)
    assert f.up is None and f.decide(down, ('c5',), ctx)['purpose'] == 'BLOCK'
    t3 = row('D5', True); t3['trial_event'] = {'L': {'source_event_id': 'up3'}}; f.observe(t3)
    assert f.decide(t3, ('c6',), dict(ctx, exit_required_today=True))['reason'] == 'EXIT_REQUIRED_TODAY_PRIORITY'
    assert not f.up_used
    # Mature without an issued permission does not settle the credit.
    assert f.decide(row('D6'), ('c7',), ctx)['purpose'] == 'START_CP_PROBE'
    return dict(same_CP_replay=True, held_up_mature_CP_unique_ADD_and_probe_settlement=True,
                flat_mature_only_once_probe=True, zero_fill_no_refund=True,
                old_pending_exit_blocks_new_up=True, blocked_CP_cannot_be_replayed_later=True,
                price_lost_R_after_mature_no_probe_regrant=True, down_closes_up_credit=True,
                same_CLOSE_old_P_exit_blocks_even_with_new_up=True,
                mature_without_permission_does_not_burn_probe_credit=True,
                layer_floor_contract='NOT_EXECUTED: CP reset changes market formation only; actual old floor first / max update and pending ACK require layer book. Paper contract only.')


def main():
    output = HERE / 'v4_two_stock'
    output.mkdir(exist_ok=False)
    sources = {str(p): sha(p) for p in (FREEZE, V3_PATH, CP_PATH, SM, Path(__file__))}
    version = 'CPSTAR_V4:' + identity(dict(freeze=sources[str(FREEZE)], v3=sources[str(V3_PATH)], cp=sources[str(CP_PATH)]))[:20]
    v3 = module('v4_frozen_v3', V3_PATH); cp = module('v4_original_cp_kernel', CP_PATH)
    specs = {r['symbol']: r for r in json.loads(SM.read_text())}
    prep = BASE / 'cp_authorization_v4_inputs'
    old_daily_path = prep / 'DAILY_ORIGINAL_CP_INPUTS.json'; sources[str(old_daily_path)] = sha(old_daily_path)
    old = {(r['sid'], r['day']): r for r in json.loads(old_daily_path.read_text())}
    all_rows = []; prefix_checks = []; full_counts = []
    for sid, end in [('000620.SZ', '2022-01-31'), ('002583.SZ', '2024-11-27')]:
        meta = specs[sid]
        pp = Path(next(p for p in meta['source_sha256'] if p.endswith('/signal.parquet')))
        ep = Path(next(p for p in meta['source_sha256'] if p.endswith('/events.parquet')))
        qp = Path(meta['refs']['CP1_input'])
        for p in (pp, ep): assert sha(p) == meta['source_sha256'][str(p)]
        for p in (pp, ep, qp): sources[str(p)] = sha(p)
        price = pd.read_parquet(pp).loc[:end]; events = pd.read_parquet(ep).loc[:end]
        q = pd.read_parquet(qp).loc[:end]
        trace, cpstar, status = build_market(sid, price, events, q, sources[str(ep)], v3, cp)
        full = condition_rows(sid, trace, cpstar, status, version)
        display = [r for r in full if selected(sid, r['day'])]
        for r in display:
            original = old[(sid, r['day'])]
            r['old_CP'] = original['original_CP']; r['old_canonical_receipt'] = original['canonical_receipt']
            r['original_requests_annotations_only'] = original['original_requests']
            r['original_position_annotations_only'] = original['original_position_condition_only']
            r['original_position_snapshot_status'] = original['original_position_snapshot_status']
        all_rows.extend(display)
        full_counts.append(dict(sid=sid, original_price_rows=len(price), original_CP_observation_rows=len(q),
                                excluded_original_q_dates=[str(t.date()) for t in price.index.difference(q.index)],
                                fullprefix_conditional_FSM=True, display_rows=len(display)))
        save(output / (sid.replace('.', '_') + '_DAILY.json'), display)
        key_days = {'000620.SZ': ['2022-01-07', '2022-01-20', '2022-01-21', '2022-01-24', '2022-01-25'],
                    '002583.SZ': ['2024-09-20', '2024-09-30', '2024-10-11', '2024-11-20']}[sid]
        print(encoded(dict(sid=sid, key_days=[dict(day=r['day'], C=r['V3']['C'], I_hold=r['V3']['I_hold'], I_expand=r['V3']['I_expand'],
              receipt=r['CP_star_receipt'], candidate=None if r['CP_star'] is None else r['CP_star']['candidate'],
              HELD=r['branches']['HELD']['purpose'], FLAT=r['branches']['FLAT']['purpose']) for r in display if r['day'] in key_days])), flush=True)
        for cut in (('2022-01-14', '2022-01-28') if sid == '000620.SZ' else ('2024-01-31', '2024-11-26')):
            shorter_trace, shorter_cp, shorter_status = build_market(sid, price.loc[:cut], events.loc[:cut], q.loc[:cut], sources[str(ep)], v3, cp)
            assert encoded(shorter_trace) == encoded([r for r in trace if r['day'] <= cut])
            assert shorter_cp.equals(cpstar.loc[:cut])
            shorter_auth = condition_rows(sid, shorter_trace, shorter_cp, shorter_status, version)
            assert encoded([r['branches'] for r in shorter_auth]) == encoded([r['branches'] for r in full if r['day'] <= cut])
            prefix_checks.append(dict(sid=sid, cutoff=cut, V3_CPstar_and_conditional_permissions_exact=True))
    assert len(all_rows) == 97
    save(output / 'ALL_DAILY.json', all_rows)
    union = [r for r in all_rows if r['CP_star_receipt'] or r['old_CP']['receipt'] or r['original_requests_annotations_only']]
    save(output / 'FULL_RECEIPT_AND_ORIGINAL_INTENT_UNION.json', union)
    compare = []
    for r in all_rows:
        a = r['CP_star']; b = r['old_CP']
        cols = ['ready', 'receipt', 'candidate', 'phase', 'reset_reason', 'anchor', 'frontier', 'scale', 'credit', 'delta_frontier', 'displacement', 'next_anchor', 'next_scale', 'next_credit', 'next_phase']
        differences = [k for k in cols if (None if a is None else a[k]) != b[k]]
        compare.append(dict(sid=r['sid'], day=r['day'], old_receipt=b['receipt'], new_receipt=r['CP_star_receipt'], different_fields=differences))
    save(output / 'CPSTAR_VS_OLD_DAILY_DIFF.json', compare)
    flat = [dict(sid=r['sid'], day=r['day'], C=r['V3']['C'], raw_C=r['V3']['raw_C'], E0=r['V3']['original_E0_event'], I_hold=r['V3']['I_hold'],
                 I_expand=r['V3']['I_expand'], P=r['V3']['P_new'], old_receipt=r['old_CP']['receipt'], CP_star_receipt=r['CP_star_receipt'],
                 CP_star_candidate=None if r['CP_star'] is None else r['CP_star']['candidate'], CP_star_key=r['CP_star_key'],
                 old_CP_id=None if r['old_canonical_receipt'] is None else r['old_canonical_receipt']['receipt_id'],
                 HELD=r['branches']['HELD']['purpose'], FLAT=r['branches']['FLAT']['purpose'],
                 original_roles=[x['original_role'] for x in r['original_requests_annotations_only']],
                 original_actual_layer_ids=[n for x in r['original_requests_annotations_only'] for n in x['original_actual_layer_ids']]) for r in union]
    with (output / 'RECEIPT_AND_INTENT_TABLE.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0])); writer.writeheader()
        writer.writerows({k: encoded(v) if isinstance(v, (list, tuple, dict)) else v for k, v in row.items()} for row in flat)
    save(output / 'PREFIX_CHECKS.json', prefix_checks)
    save(output / 'MINIMAL_PERMISSION_CHECKS.json', logic_checks())
    save(output / 'RUN_RECEIPT.json', dict(status='V4_PURE_SIGNAL_COMPLETE', version=version, source_sha256=sources,
        full_prefix=full_counts, display_rows=len(all_rows), union_rows=len(union), prefix_checks=len(prefix_checks),
        old_receipt_rows=sum(r['old_CP']['receipt'] for r in all_rows), new_receipt_rows=sum(r['CP_star_receipt'] for r in all_rows),
        original_CP_recalculated_under_V3_hold_P=True, new_E0_events=0, new_accounts=0, new_orders=0, new_quantities=0, new_cash_paths=0, new_returns=0))
    save(output / 'OUTPUT_SHA256.json', {str(p): sha(p) for p in output.iterdir() if p.is_file() and p.name != 'OUTPUT_SHA256.json'})


if __name__ == '__main__': main()
