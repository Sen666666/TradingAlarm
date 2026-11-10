"""Posterior adapter for already computed engines. Never imports/runs a consumer.

Missing evidence is a diagnostic blocker, never a zero or coverage assertion.
Callbacks below must be read-only. No report result is passed to selection.
"""
from collections import Counter, defaultdict
from decimal import Decimal as D
import math
import re
import json
import hashlib
import ast
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
from reporting import (records, build_report, normalize_native_actions,
                       normalize_native_claims)

CLOSED = 'COMPLETE_CONDITIONAL_STOCK_ROUND'
KNOWN_NO_ENTRY = {'NEXT_OPEN_BELOW_PROTECTION_NOFILL','MINIMUM_LOT_NOT_FUNDED_NOFILL',
                  'PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT','PRECHECK_Q0_NO_SUBMIT'}


def read_sealed_baseline(directory, original_permits, *, evidence_engine=None):
    """Read existing baseline tables only; never obtain permits from selections.

    Evidence engine, when supplied, is already loaded and only its source/dated
    fee readers are borrowed. No engine import, reset, run or finalize occurs.
    """
    directory = Path(directory)
    def csv(name):
        frame = pd.read_csv(directory / (name+'.csv'),float_precision='round_trip',low_memory=False)
        return frame.astype(object).where(pd.notna(frame),None).to_dict('records')
    rounds = [r for r in csv('ROUNDS') if r['arm']=='A_UNION_B']
    ids = {r['round_id'] for r in rounds}
    actions = [r for r in csv('ACTIONS') if r['round_id'] in ids]
    claims = [c for c in json.loads((directory/'CLAIMS.json').read_text()) if c['owner_round_id'] in ids]
    archives = {r['round_id']:dict(owner_lane='AB',cash=r.get('cash_after_payouts'),
        receivable=r.get('receivable_after_payouts'),last_known_mark_day=r.get('last_known_mark_day'),
        last_raw_close=r.get('last_raw_close')) for r in rounds}
    snapshot = SimpleNamespace(rounds=rounds,actions=actions,claims=claims,archives=archives,
        ev=original_permits,END=pd.Timestamp('2026-06-30'),raw={})
    if evidence_engine is not None:
        for name in ('raw','manifest','getmeta','fee','local_actions','read','sha','EVENT_AT','END'):
            if hasattr(evidence_engine,name):
                setattr(snapshot,name,getattr(evidence_engine,name))
    return snapshot


def _rows(value):
    return records(list(value.values()) if isinstance(value, dict) else value)


def _group(rows, field):
    out=defaultdict(list)
    for r in rows:out[r.get(field)].append(r)
    return out


def _permits(value):
    # Preserve all original columns and missingness without JSON NaN coercion.
    def cell(x):
        if isinstance(x, float) and not math.isfinite(x):
            return {'__native_nonfinite__': repr(x)}
        if x is pd.NA or x is pd.NaT:
            return {'__native_missing__': type(x).__name__}
        return x
    return [{k: cell(v) for k,v in r.items()} for r in records(value)]


def _day(x):
    return None if x is None or pd.isna(x) else pd.Timestamp(x)


def _raw(s, sid, day):
    return getattr(s, 'raw', {}).get(sid, {}).get(pd.Timestamp(day), {})


def posterior_price_reader(s):
    """Native DayFrame omits H/L. Read frozen signal parquet without s.load."""
    cache = {}
    def read(sid, day):
        row = _raw(s, sid, day)
        if 'raw_high' in row and 'raw_low' in row:
            return row
        if sid not in cache:
            cache[sid] = None
            manifest = getattr(s, 'manifest', {}).get(sid, {})
            paths = [(p,h) for p,h in manifest.get('source_sha256', {}).items() if p.endswith('/signal.parquet')]
            if len(paths) == 1:
                p, h = paths[0]
                try:
                    if s.sha(p) == h:
                        cache[sid] = pd.read_parquet(p)
                except (OSError, ValueError, KeyError):
                    pass
        frame = cache[sid]
        if frame is not None and pd.Timestamp(day) in frame.index:
            return dict(frame.loc[pd.Timestamp(day)].to_dict(),_posterior_source_verified=True)
        return row
    return read


def _fee(s, sid, day, q, price, side):
    _, schedule, params = s.getmeta(sid, pd.Timestamp(day))
    return float(s.fee(int(q), D(str(price)), schedule, side, params))


def financial_coverage(s, rd, claims):
    """Original held-interval convention, with explicit source completeness checks.

    Both original windows exclude entry day, include closed/censored endpoint,
    and exclude UNKNOWN endpoint. Absence of a source is never no-action proof.
    """
    reasons = []
    ent = _day(rd.get('entry_day'))
    end = _day(rd.get('exit_day') if rd['status'] == CLOSED else rd.get('status_day'))
    inclusive = rd['status'] == CLOSED or 'CENSORED' in rd['status']
    if ent is None:
        return dict(financial_covered=False, reason='NO_CONFIRMED_HOLDING')
    if end is None:
        return dict(financial_covered=False, reason='MISSING_INTERVAL_END')
    try:
        ac = s.local_actions(rd['sid'])
    except (AttributeError, KeyError, OSError, ValueError):
        return dict(financial_covered=False, reason='RIGHTS_SOURCE_UNAVAILABLE')
    reasons.extend(ac.get('_source_issues', []))
    reasons.extend(ac.get('_source_coverage_issues', []))
    if ac.get('raw_response_empty'):
        reasons.append('ACTION_RAW_RESPONSE_EMPTY')
    if str(rd['window']) != '2022' and ac.get('_source_integrity_ok') is not True:
        reasons.append('ACTION_SOURCE_INTEGRITY_UNKNOWN')
    evidence = ac.get('coverage_evidence', [])
    if not evidence:
        reasons.append('NO_RIGHTS_SOURCE')
    unresolved = list(ac.get('unresolved', []))
    sources = []
    for e in evidence:
        try:
            source = s.read(e['path'])
            ok = s.sha(e['path']) == e['sha256']
            sources.append(dict(e, hash_ok=ok, records=len(source.get('records', []))))
            if not ok:
                reasons.append('RIGHTS_HASH_MISMATCH')
            if not source.get('records'):
                reasons.append('RIGHTS_EMPTY')
            unresolved.extend(source.get('unparsed', []))
        except (AttributeError, KeyError, OSError, ValueError):
            reasons.append('RIGHTS_EVIDENCE_UNREADABLE')
    def inside(day):
        return day is not None and ent < day and (day <= end if inclusive else day < end)
    for u in unresolved:
        row = u.get('row', u) if isinstance(u, dict) else {}
        value = row.get('1') or row.get('effective_date') or row.get('date')
        if value is None:
            m = re.search(r'\d{4}-\d{2}-\d{2}', str(u))
            value = m.group() if m else None
        try:
            day = _day(value) if value is None or '-' in str(value) else pd.to_datetime(str(value), format='%Y%m%d')
        except (ValueError, TypeError):
            day = None
        if day is None:
            reasons.append('UNPARSED_UNDATED')
        elif inside(day):
            reasons.append('UNPARSED_IN_HELD_INTERVAL')
    held = []
    for event in ac.get('events', []):
        day = _day(event['effective_date'])
        if not inside(day):
            continue
        held.append(event)
        approved = s.EVENT_AT.get((rd['sid'], day))
        owned = [c for c in claims if approved and c.get('economic_event_id') == approved['economic_event_id'] and c.get('recognized') is True]
        if not approved or not approved.get('entitlement_verified', False) or not owned:
            reasons.append('UNVERIFIED_HELD_ACTION:' + str(event['effective_date']))
        if approved and (approved.get('event_type') != 'PURE_CASH' or float(approved.get('split_ratio', 1)) != 1):
            reasons.append('UNADMITTED_QUANTITY_ACTION')
    return dict(financial_covered=not reasons,
                reason=';'.join(sorted(set(reasons))) if reasons else ('VERIFIED_ACTIONS_SCENARIO' if held else 'LOCAL_NO_ACTION_EVIDENCE'),
                interval_start=str(ent.date()), interval_end=str(end.date()),
                end_inclusive=inclusive, rights_sources=sources)


def read_precommitted_diagnostics(window):
    """Frozen market facts and original winner names, never new economics."""
    directory=Path(__file__).resolve().parent.parent/'independent_channel_full1709_preflight_v1/overlap'
    expected=json.loads((directory/'OUTPUT_HASHES.json').read_text())
    expected.update(json.loads((directory/'SUPPLEMENT_OUTPUT_HASHES.json').read_text())['supplement_files'])
    output=[]
    for name in ('WINNER_FULL_HOLD_FIXED_COHORT.csv','RECEIPT_CONDITIONAL_OVERLAP.parquet'):
        path=directory/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected[name]:
            raise ValueError('frozen diagnostic source changed: '+name)
        frame=pd.read_csv(path) if name.endswith('.csv') else pd.read_parquet(path)
        output.append(frame[frame.window.astype(str).eq(str(window))].copy())
    return tuple(output)


def industry_delay_diagnostics(receipts, calendar, window):
    groups=defaultdict(list)
    for r in records(receipts):
        if str(r.get('window',window))==str(window):
            groups[(r['sid'],str(r.get('identity')),str(r['root_day']))].append(r)
    out=[]
    cal=pd.DatetimeIndex(calendar)
    for (sid,identity,root),rs in groups.items():
        rs.sort(key=lambda r:str(r['day']))
        def gate(r):
            vals=[r.get('old_'+k,r.get(k)) for k in ('sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up')]
            if any(x is None or pd.isna(x) for x in vals):return 'UNKNOWN'
            return 'PASS' if all(bool(x) for x in vals) else 'FALSE'
        first=next((r for r in rs if gate(r)=='PASS'),None)
        born=next((r for r in rs if r.get('born') is True),None)
        birth=_day(root)
        left=born is None
        delay=int(((cal>birth)&(cal<=_day(first['day']))).sum()) if first and len(cal) and not left else None
        out.append(dict(sid=sid,window=str(window),identity=identity,root_day=root,
            left_truncated=left,birth_gate=gate(born) if born else 'UNKNOWN_LEFT_TRUNCATED',
            first_observed_receipt=str(rs[0]['day']),first_industry_pass=str(first['day']) if first else None,
            industry_delay_sessions=delay,known_session_calendar=bool(len(cal)),
            observed_failed_receipts=sum(gate(r)=='FALSE' for r in rs),unknown_receipts=sum(gate(r)=='UNKNOWN' for r in rs),
            interpretation='Industry facts only; not slot, target, fill or economic benefit'))
    return out


def round_risk_holding(s, adapted):
    out=[]
    cal=pd.DatetimeIndex(getattr(s,'cal',[]))
    actions_by_round=_group(adapted['actions'],'round_id')
    cash_by_round={c['round_id']:c['cash_plus_receivable'] for c in adapted['closed_cash_checks']}
    for r in adapted['rounds']:
        rid=r['round_id'];st=getattr(s,'archives',{}).get(rid,{})
        unknown='UNKNOWN' in r['status']
        start=_day(r.get('entry_day'))
        end=_day(r.get('last_known_mark_day')) if unknown else _day(r.get('exit_day') if r['status']==CLOSED else r.get('status_day'))
        sessions=int(((cal>=start)&(cal<=end)).sum()) if len(cal) and start is not None and end is not None else None
        net=cash_by_round.get(rid)
        acts=actions_by_round[rid]
        lots=defaultdict(list);sell_losses=[]
        for a in acts:
            ls=lots[a['role']]
            if a['side']=='BUY':ls.append([a['q'],a['q']*a['price']+a['fee']]);continue
            rem=a['q'];cost=0
            while rem>1e-9:
                q,c=ls[0];take=min(rem,q);allocated=c*take/q
                cost+=allocated;rem-=take
                if take==q:ls.pop(0)
                else:ls[0]=[q-take,c-allocated]
            sell_losses.append(a['q']*a['price']-a['fee']-cost)
        gap=None;floor=None
        if r['owner_lane']=='PRICE' and st.get('price_s') is not None and st.get('fac') is not None and r.get('exit_price') is not None:
            floor=float(st['price_s'])/float(st['fac'])
            gap=float(r['exit_price'])-floor*(1-.0005)
        out.append(dict(sid=r['sid'],window=r['window'],arm=r['arm'],lane=r['owner_lane'],round_id=rid,
            holding_sessions=sessions,holding_scope='KNOWN_PREFIX_ONLY' if unknown else 'ENTRY_THROUGH_ENDPOINT_INCLUSIVE',
            full_closed_net=net,net_loss_above_3000=net < -3000 if net is not None else None,
            realized_sell_losses=sell_losses,single_role_sell_loss_above_3000=any(x < -3000 for x in sell_losses),
            exit_signal_floor_raw=floor,proxy_exit_minus_protected_slipped_price=gap,
            gap_status='KNOWN_PRICE_SIGNAL_S_PROJECTED' if gap is not None else 'UNKNOWN_NO_FROZEN_EXIT_PROTECTION',
            distinction='Net loss over budget is not proof that a price gap caused the entire loss'))
    return out


def identity_funnel(joint, adapted, offers, ab_permits):
    s=getattr(joint,'s',joint)
    ab_audit=records(getattr(joint,'ab_decision_audit',[]))
    price=records(getattr(joint,'price_audit',[]))
    rdmap={r['round_id']:r for r in adapted['rounds']}
    for rid,book in getattr(joint,'books',{}).items():
        for parent in getattr(book,'parents',{}).values():
            target=parent.target;receipt=str(target.signal_receipt_id)
            if not any(p.get('receipt_id')==receipt for p in price):
                price.append(dict(round_id=rid,sid=rdmap.get(rid,{}).get('sid'),
                    receipt_id=receipt,day=target.decision_open,role=target.role.value,
                    event='BOOK_TARGET_IDENTITY',target_Q=target.target_Q,
                    filled_F=parent.filled_F,parent_id=target.parent_id))
    price_by_request=defaultdict(list)
    price_no_receipt_by_round=defaultdict(list)
    for p in price:
        if p.get('receipt_id'):price_by_request['PRICE|'+str(p['receipt_id'])].append(p)
        else:price_no_receipt_by_round[p.get('round_id')].append(p)
    ab_by_event=_group(ab_audit,'event_id')
    round_by_event=_group(adapted['rounds'],'event_id')
    round_by_id={r['round_id']:r for r in adapted['rounds']}
    action_by_round=_group(adapted['actions'],'round_id')
    requests={}
    for o in offers:
        request=o.get('request_id') or (o.get('event_id') if o.get('owner_lane')=='AB' else 'PRICE|'+str(o.get('receipt_id')))
        identity=(o.get('owner_lane'),str(request),str(o.get('sid')),str(o.get('day')))
        requests.setdefault(identity,[]).append(o)
    for p in ab_permits:
        identity=('AB',str(p['event_id']),str(p['sid']),str(p.get('day')))
        requests.setdefault(identity,[])
    for p in price:
        if not p.get('receipt_id'):
            continue
        request='PRICE|'+str(p['receipt_id'])
        try:
            receipt=ast.literal_eval(str(p['receipt_id']))
            signal_day=str(pd.Timestamp(receipt[-1]))
        except (ValueError,TypeError,SyntaxError):
            signal_day='UNKNOWN'
        matching=any(k[0]=='PRICE' and k[1]==request for k in requests)
        if not matching:
            requests[('PRICE',request,str(p.get('sid')),signal_day)]=[]
    out=[]
    for (lane,request,sid,day),oo in requests.items():
        receipt_rounds={p.get('round_id') for p in price_by_request[request]}
        rds=list(round_by_event[request])
        rds.extend(round_by_id[rid] for rid in receipt_rounds if rid in round_by_id and round_by_id[rid] not in rds)
        rds=[r for r in rds if r['owner_lane']==lane]
        ridset={r['round_id'] for r in rds}
        pr=list(price_by_request[request])
        for r in rds:
            if r.get('event_id')==request:pr.extend(price_no_receipt_by_round[r['round_id']])
        aa=ab_by_event[request]
        actions=[a for rid in ridset for a in action_by_round[rid]]
        if lane=='PRICE':
            actions=[a for a in actions if any(str(a['day'])[:10]==str(p.get('day'))[:10] and a['role']==p.get('role') for p in pr)]
        books={str(k):dict(responsibility=v.responsibility(),events=list(v.events)) for k,v in getattr(joint,'books',{}).items() if k in ridset}
        out.append(dict(lane=lane,request_id=request,sid=sid,signal_day=day,
            source='ORIGINAL_RAW_AB_PERMIT' if lane=='AB' else 'PRICE_MARKET_RECEIPT',
            offers=oo,original_ab_decisions=aa,price_execution_events=pr,
            rounds=rds,normalized_actions=actions,execution_books=books,
            slot_granted=any(o['result']=='SELECTED_PENDING' for o in oo),
            execution_roles=sorted({p['role'] for p in pr if p.get('role')}),
            consumes_initial_slot=any(o['result']=='SELECTED_PENDING' for o in oo),
            add_consumes_initial_slot=False,
            filled=bool(actions),unresolved=any('UNKNOWN' in r['status'] or 'PENDING' in r['status'] for r in rds),
            receipt_identity_status='REQUEST_EXACT' if lane=='AB' or any(o.get('request_id') for o in oo) else 'LEGACY_ALIAS_ONLY',
            phase_semantics='Observed order: application, own-state block, AB precedence, industry, size, rank, next OPEN; early blocked industry is untested, not false'))
    return out


def adapt_engine(engine, roster, window, arm, *, baseline=False, coverage_resolver=None,
                 posterior_raw_resolver=None):
    """Accept JointConsumer or an engine-like snapshot with frozen ledger fields."""
    s = getattr(engine, 's', engine)
    window = '2024_924' if str(window) == '2024' else str(window)
    posterior_raw = posterior_raw_resolver or posterior_price_reader(s)
    archives = getattr(s, 'archives', {})
    rounds = []
    for r in _rows(s.rounds):
        r = dict(r)
        if str(r.get('window', window)) != str(window):
            continue
        # A snapshot may contain other original arms. Never merge their ledgers.
        expected_arm = 'A_UNION_B' if baseline else getattr(engine, 'arm', r.get('arm'))
        if r.get('arm') != expected_arm:
            continue
        st = archives.get(r['round_id'], {})
        r.update(window=str(window), arm=arm,
                 owner_lane='AB' if baseline else st.get('owner_lane', r.get('owner_lane', 'AB')))
        rounds.append(r)
    # A current pending/UNKNOWN round may not yet have an output record. Keep
    # its responsibility visible rather than treating absence as a zero stock.
    existing = {r['round_id'] for r in rounds}
    active = getattr(engine, 'states', getattr(s, 'states', {}))
    for st in _rows(active):
        if st.get('round_id') in existing:
            continue
        if not st.get('round_id'):
            raise ValueError('active state missing round identity')
        rounds.append(dict(st, window=str(window), arm=arm,
            owner_lane='AB' if baseline else st.get('owner_lane', 'AB'),
            status='UNKNOWN_UNFINALIZED_' + str(st.get('state', 'RESPONSIBILITY'))))
    ids = {r['round_id'] for r in rounds}
    native = [r for r in _rows(s.actions) if r['round_id'] in ids]
    # Normalize sets explicit arm labels, irrespective of native stored labels.
    native = [dict(r, arm=arm, window=str(window)) for r in native]
    actions = normalize_native_actions(native, rounds)
    claims_native = [r for r in _rows(s.claims) if r['owner_round_id'] in ids]
    claims = normalize_native_claims(claims_native, rounds)
    by_round, claimby = defaultdict(list), defaultdict(list)
    blockers, core, checks, marks, round_cov = [], [], [], [], []
    for a in actions:
        z = posterior_raw(a['sid'], a['day'])
        def equal(fields):
            vals = [z.get('raw_' + f) for f in fields]
            return all(float(v) == float(vals[0]) for v in vals) if all(v is not None and math.isfinite(float(v)) for v in vals) else None
        a['one_price_hl'] = equal(('high', 'low'))
        a['one_price_ohlc'] = equal(('open', 'high', 'low', 'close'))
        by_round[a['round_id']].append(a)
    for c in claims_native:
        claimby[c['owner_round_id']].append(c)
    for rd in rounds:
        rid, sid = rd['round_id'], rd['sid']
        st = archives.get(rid, {})
        k = {f: rd[f] for f in ('sid', 'window', 'arm')}
        k['lane'] = rd['owner_lane']
        known_zero = rd['status'] in KNOWN_NO_ENTRY and not by_round[rid] and not claimby[rid]
        if known_zero:
            st_qty = [st.get(f, 0) for f in ('core','add','receivable')]
            known_zero = all(v is None or float(v)==0 for v in st_qty)
        rd['_confirmed_zero_responsibility'] = known_zero
        cov = dict(financial_covered=True,reason='KNOWN_ZERO_TERMINATED_NO_ENTRY') if known_zero else (coverage_resolver or financial_coverage)(s, rd, claimby[rid])
        round_cov.append(dict(k, round_id=rid, **cov))
        aa = by_round[rid]
        book=getattr(engine,'books',{}).get(rid)
        responsibility=book.responsibility() if book is not None else None
        rd['_unresolved_book']=bool(responsibility and (responsibility.get('unknown') or responsibility.get('live_leaves',0) or responsibility.get('exit_pending') or not responsibility.get('all_orders_reconciled',False)))
        inventory = defaultdict(float)
        for a in aa:
            inventory[a['role']] += a['q'] * (1 if a['side'] == 'BUY' else -1)
        if rd['status'] == CLOSED and aa:
            cash = st.get('cash', rd.get('cash_after_payouts'))
            recv = st.get('receivable', rd.get('receivable_after_payouts'))
            if cash is None or recv is None:
                blockers.append('MISSING_CLOSED_CASH:' + rid)
            else:
                checks.append(dict(k, round_id=rid, cash_plus_receivable=float(cash)+float(recv)))
        if any(q > 0 for q in inventory.values()) and 'UNKNOWN' not in rd['status'] and not rd['_unresolved_book']:
            end = getattr(s, 'END', None)
            z = posterior_raw(sid, end) if end is not None else {}
            try:
                raw = float(z['raw_close'])
                # Terminal source/factor evidence must be explicit; last raw value alone is insufficient.
                verified = st.get('last_known_mark_day') is not None and _day(st['last_known_mark_day']) == _day(end)
                last_close = st.get('last_raw_close',rd.get('last_raw_close'))
                if last_close is not None:
                    verified = verified and math.isclose(float(last_close),raw,rel_tol=1e-12,abs_tol=0)
                if 'adjustment_factor' in z:
                    factor=float(z['adjustment_factor'])
                    verified = verified and math.isfinite(factor) and factor>0
                    if st.get('fac') is not None:
                        verified = verified and math.isclose(float(st['fac']),factor,rel_tol=1e-11)
                if not verified or not math.isfinite(raw) or raw <= 0:
                    raise ValueError('unverified endpoint')
                total = sum(inventory.values())
                fee = _fee(s, sid, end, total, raw*(1-.0005), 'sell')
                for role, q in inventory.items():
                    if q > 0:
                        marks.append(dict(k, round_id=rid, role=role, q=q, verified=True,
                            mark_raw=raw, sell_slippage=.0005, estimated_dated_sell_fee=fee*q/total,
                            terminal_day=str(_day(end).date()), fee_basis='ONE_COMBINED_ROUND_SELL'))
            except (AttributeError, KeyError, ValueError, TypeError):
                blockers.append('UNVERIFIED_TERMINAL_MARK:' + rid)
        probe = [a for a in aa if a['role'] == 'PROBE']
        try:
            buy = sell = fees = 0.0
            for a in probe:
                f = _fee(s, sid, a['day'], a['q'], a['price'], a['side'].lower())
                fees += f
                if a['side'] == 'BUY':
                    buy += a['q']*a['price']+f
                else:
                    sell += a['q']*a['price']-f
            income = sum(float(c['core_amount']) for c in claimby[rid] if c.get('recognized') is True)
            closed = inventory['PROBE'] == 0 and bool(probe) and 'UNKNOWN' not in rd['status']
            terminal = next((m for m in marks if m['round_id'] == rid and m['role']=='PROBE'),None)
            core_open = None
            core_terminal_fee = None
            if terminal:
                q=inventory['PROBE']; price=terminal['mark_raw']*(1-terminal['sell_slippage'])
                core_terminal_fee=_fee(s,sid,terminal['terminal_day'],q,price,'sell')
                core_open=sell-buy+q*price-core_terminal_fee+income
            core.append(dict(k, round_id=rid, status=rd['status'], buy_cash=buy,
                sell_cash=sell, independent_dated_fees=fees, core_registered_net80=income,
                closed_net=sell-buy+income if closed else None,
                open_total_net=core_open,terminal_independent_sell_fee=core_terminal_fee,
                fee_basis='EACH_ACTUAL_CORE_FILL_INDEPENDENT_DATED_FEE'))
        except (AttributeError, KeyError, ValueError, TypeError):
            blockers.append('CORE_DATED_FEE_OR_ENTITLEMENT_MISSING:' + rid)
    states, coverage = [], []
    for sid in roster:
        for lane in ('AB', 'PRICE'):
            rs = [r for r in rounds if str(r['sid']) == str(sid) and r['owner_lane'] == lane]
            k = dict(sid=str(sid), window=str(window), arm=arm, lane=lane)
            statuses = [r['status'] for r in rs]
            if not rs or all(r.get('_confirmed_zero_responsibility') is True for r in rs):
                status = 'NEVER_ENTERED'
            elif any('UNKNOWN' in x or 'PENDING' in x for x in statuses) or any(r.get('_unresolved_book') for r in rs):
                status = 'UNKNOWN'
            elif any('CENSORED' in x for x in statuses):
                status = 'OPEN_CENSORED'
            else:
                status = 'CLOSED'
            last = rs[-1] if rs else {}
            states.append(dict(k, status=status, last_known_day=last.get('last_known_mark_day'),
                last_known_mark=last.get('last_mark_net'), frozen_amount=None,
                frozen_trade_cashflow=last.get('cashflow_to_date'),
                frozen_trade_cashflow_definition='Cumulative trade cashflow, not frozen asset value or remaining cost',
                unknown_order=status == 'UNKNOWN', unknown_inventory=status == 'UNKNOWN'))
            cs = [c for c in round_cov if c['sid'] == sid and c['lane'] == lane]
            coverage.append(dict(k, financial_covered=all(c['financial_covered'] for c in cs) if rs else True,
                reason=';'.join(sorted({c['reason'] for c in cs})) if rs else 'KNOWN_ZERO_NO_RESPONSIBILITY'))
    return dict(actions=actions, claims=claims, states=states, terminal_marks=marks,
                coverage=coverage, core_diagnostics=core, closed_cash_checks=checks,
                rounds=rounds, round_coverage=round_cov, blockers=blockers)


def build_comparison(baseline, joint, roster, window, *, winners=None, market_receipts=None,
                     expected_roster_size=1709, expected_winner_count=None,
                     coverage_resolver=None, posterior_raw_resolver=None):
    """Two already computed FULL arms, one window. No strategy evaluation occurs."""
    window = '2024_924' if str(window) == '2024' else str(window)
    if winners is None or market_receipts is None:
        frozen_winners,frozen_receipts=read_precommitted_diagnostics(window)
        if winners is None:winners=frozen_winners
        if market_receipts is None:market_receipts=frozen_receipts
    expected_winner_count = (44 if window=='2022' else 64) if expected_winner_count is None else expected_winner_count
    b = adapt_engine(baseline, roster, window, 'baseline', baseline=True, coverage_resolver=coverage_resolver, posterior_raw_resolver=posterior_raw_resolver)
    j = adapt_engine(joint, roster, window, 'joint', coverage_resolver=coverage_resolver, posterior_raw_resolver=posterior_raw_resolver)
    bs, js = getattr(baseline, 's', baseline), getattr(joint, 's', joint)
    permits_b, permits_j = _permits(bs.ev), _permits(js.ev)
    offers = records(getattr(joint, 'offer_audit', []))
    counts = Counter((r.get('owner_lane'), r.get('PVR_known') is True, r['result']) for r in offers)
    # JointConsumer emits PRICE APPLICATION only. AB applications are the full
    # raw original permits, never the selected subset or an invented zero.
    for p in permits_j:
        known=p.get('PVR_known') is True
        counts['AB',known,'APPLICATION']+=1
    stages = sorted({k[2] for k in counts} | {'APPLICATION','SELECTED_PENDING','PASS_NOT_TOP2',
        'INDUSTRY_UNKNOWN','INDUSTRY_FALSE','BLOCKED_HELD','BLOCKED_BUY_PENDING','BLOCKED_UNKNOWN',
        'SUPPRESSED_BY_AB_VALID_CLOSE','AB_ORIGINAL_CLOSE_INELIGIBLE'})
    funnel = [dict(lane=lane,pvr_group='KNOWN' if known else 'UNKNOWN',stage=stage,
                  count=counts[lane,known,stage])
              for lane in ('AB','PRICE') for known in (True,False) for stage in stages]
    changes = []
    b_by_event=_group(b['rounds'],'event_id');j_by_event=_group(j['rounds'],'event_id')
    j_by_id={r['round_id']:r for r in j['rounds']}
    offers_by_event=_group([o for o in offers if o.get('owner_lane')=='AB'],'event_id')
    offers_by_queue=defaultdict(list)
    for o in offers:offers_by_queue[str(o.get('day')),o.get('sector')].append(o)
    for event in permits_b:
        eid = event['event_id']
        br = b_by_event[eid]
        jr = [r for r in j_by_event[eid] if r['owner_lane'] == 'AB']
        audit = offers_by_event[eid]
        result = 'SAME_EVENT_RETAINED' if br and jr else 'JOINT_ONLY_AB_STATE_CHAIN' if jr else 'NOT_SELECTED_BOTH'
        if br and not jr:
            result = 'AB_STATE_CHAIN_LOSS'
            for a in audit:
                owner = j_by_id.get(a.get('blocking_round_id'), {})
                if owner.get('owner_lane') == 'PRICE':
                    result = 'PRICE_SAME_STOCK_' + a['result']
                elif a['result'] == 'PASS_NOT_TOP2':
                    price_slots = [x for x in offers_by_queue[str(a.get('day')),a.get('sector')] if x.get('owner_lane') == 'PRICE' and x['result'] == 'SELECTED_PENDING']
                    result = 'PRICE_INDUSTRY_SLOT_DISPLACEMENT' if price_slots else 'AB_STATE_CHAIN_RANK_LOSS'
        changes.append(dict(event_id=eid, sid=event['sid'], day=str(event.get('day')), result=result,
                            baseline_round_ids=[r['round_id'] for r in br], joint_round_ids=[r['round_id'] for r in jr], audit=audit,
                            competing_queue=offers_by_queue[str(event.get('day')),event.get('sector')]))
    args = {name: b[name]+j[name] for name in ('actions','claims','states','terminal_marks','coverage','core_diagnostics','closed_cash_checks')}
    report = build_report(roster, [str(window)], ['baseline','joint'], ['AB','PRICE'],
        expected_roster_size=expected_roster_size, reference_permits=permits_b,
        candidate_permits=permits_j, ab_changes=changes, pvr_diagnostics=funnel, **args)
    path_checks = []
    for c in changes:
        if c['result'] != 'SAME_EVENT_RETAINED':
            continue
        def canonical(source, rids, table):
            rows = []
            for x in source[table]:
                if x['round_id'] not in rids:
                    continue
                # round/arm identities differ by design; sequence is global FIFO
                # ordinal, not an economic field. All other ledger fields remain.
                row = {k:v for k,v in x.items() if k not in {'round_id','arm','sequence','claim_id'}}
                rows.append(json.dumps(_permits([row])[0],sort_keys=True,default=str,allow_nan=False))
            return Counter(rows)
        exact_actions = canonical(b,c['baseline_round_ids'],'actions') == canonical(j,c['joint_round_ids'],'actions')
        exact_claims = canonical(b,c['baseline_round_ids'],'claims') == canonical(j,c['joint_round_ids'],'claims')
        br = [r for r in b['rounds'] if r['round_id'] in c['baseline_round_ids']]
        jr = [r for r in j['rounds'] if r['round_id'] in c['joint_round_ids']]
        exits = lambda rs: [(r['status'],str(r.get('exit_day')),r.get('exit_price'),r.get('exit_reason')) for r in rs]
        path_checks.append(dict(event_id=c['event_id'], actions_exact=exact_actions,
            claims_exact=exact_claims, exit_exact=exits(br)==exits(jr)))
    winner_rows = []
    for w in records(winners):
        w=dict(w)
        owner=next((r for r in b['rounds'] if r['round_id']==w.get('round_id')),None)
        if not w.get('event_id') and owner:w['event_id']=owner.get('event_id')
        change = next((c for c in changes if c['event_id'] == w.get('event_id')), None)
        same_sid = [r for r in j['rounds'] if r['sid'] == w['sid']]
        status = change['result'] if change and change['result'] != 'NOT_SELECTED_BOTH' else 'UNKNOWN' if any('UNKNOWN' in r['status'] for r in same_sid) else 'DIFFERENT_TIME_SAME_STOCK_HELD' if any(a['sid'] == w['sid'] for a in j['actions']) else 'NOT_PARTICIPATING'
        winner_rows.append(dict(w, named_coverage_status=status, event_diagnostic=change))
    # Round-level posterior one-price dependence, including buy/add/sell. Do
    # not rerun selection when excluding these rounds descriptively.
    dependence = []
    for source in (b,j):
        for rd in source['rounds']:
            aa = [a for a in source['actions'] if a['round_id'] == rd['round_id']]
            pnl = next((c['cash_plus_receivable'] for c in source['closed_cash_checks'] if c['round_id'] == rd['round_id']),None)
            dependence.append(dict(round_id=rd['round_id'], arm=rd['arm'], lane=rd['owner_lane'],
                sid=rd['sid'], window=rd['window'], status=rd['status'], conditional_closed_net=pnl,
                any_hl=any(a['one_price_hl'] is True for a in aa),
                any_ohlc=any(a['one_price_ohlc'] is True for a in aa),
                annotation_missing=any(a['one_price_ohlc'] is None for a in aa),
                action_roles=[dict(side=a['side'],role=a['role'],day=a['day'],hl=a['one_price_hl'],ohlc=a['one_price_ohlc']) for a in aa]))
    dependency_summary=[]
    for arm in ('baseline','joint'):
        rows=[r for r in dependence if r['arm']==arm and r['conditional_closed_net'] is not None]
        total=sum(r['conditional_closed_net'] for r in rows)
        positive=sum(max(0,r['conditional_closed_net']) for r in rows)
        dep=[r for r in rows if r['any_ohlc']]
        amount=sum(r['conditional_closed_net'] for r in dep)
        dependency_summary.append(dict(arm=arm,closed_round_count=len(rows),dependent_round_count=len(dep),
            dependent_net=amount,total_net=total,net_share=amount/total if total else None,
            positive_tail_share=sum(max(0,r['conditional_closed_net']) for r in dep)/positive if positive else None,
            descriptive_excluding_dependent_net=sum(r['conditional_closed_net'] for r in rows if not r['any_ohlc'] and not r['annotation_missing']),
            excluded_unannotated_round_count=sum(r['annotation_missing'] for r in rows),rerun=False))
    report.update(round_coverage=b['round_coverage']+j['round_coverage'],
        retained_ab_path_exact=path_checks,one_price_round_dependencies=dependence,
        one_price_dependency_summary=dependency_summary,
        named_original_winners=winner_rows, offer_audit=offers,
        price_precheck_audit=records(getattr(joint, 'price_audit', [])),
        execution_books={str(k): v.responsibility() for k,v in getattr(joint,'books',{}).items()},
        normalized_actions=args['actions'], normalized_claims=args['claims'],
        terminal_marks=args['terminal_marks'], adapter_states=args['states'],
        adapter_blockers=b['blockers']+j['blockers'])
    if len(winner_rows) != expected_winner_count or any(not w.get('event_id') for w in winner_rows):
        report['adapter_blockers'].append('ORIGINAL_WINNER_COHORT_WINDOW_NOT_COMPLETE')
    if not report['permit_exact_verified']:
        report['adapter_blockers'].append('ORIGINAL_AB_PERMITS_NOT_EXACT')
    if any(not all(c[k] for k in ('actions_exact','claims_exact','exit_exact')) for c in path_checks):
        report['adapter_blockers'].append('RETAINED_AB_PATH_MISMATCH_REQUIRES_REVIEW')
    if any(a['one_price_ohlc'] is None for a in args['actions']):
        report['adapter_blockers'].append('POSTERIOR_OHLC_ANNOTATIONS_MISSING')
    report['first_ab_divergence'] = next(iter(sorted((c for c in changes if c['result'] not in {'SAME_EVENT_RETAINED','NOT_SELECTED_BOTH'}),key=lambda c:c['day'])),None)
    report['industry_delay_diagnostics']=industry_delay_diagnostics(market_receipts,getattr(js,'cal',getattr(bs,'cal',[])),window)
    report['round_risk_holding_diagnostics']=round_risk_holding(bs,b)+round_risk_holding(js,j)
    report['request_execution_identity_join']=identity_funnel(joint,j,offers,permits_j)
    report['original_ab_decision_audit']=records(getattr(joint,'ab_decision_audit',[]))
    report['not_yet_wired_diagnostics'] = []
    report['diagnostic_unknown_fields'] = dict(
        holding_session_rounds=sum(r['holding_sessions'] is None for r in report['round_risk_holding_diagnostics']),
        exit_protection_gap_rounds=sum(r['gap_status'].startswith('UNKNOWN') for r in report['round_risk_holding_diagnostics']),
        industry_delay_roots=sum(r['industry_delay_sessions'] is None for r in report['industry_delay_diagnostics']))
    report['limitations'].extend([
        'Joint AB minus baseline AB is the net impact of competition and holding-path changes, including new, delayed and lost AB events; it is not all direct displacement.',
        'Original winner/loss labels and industry-delay observations are posterior attribution only, never permissions.',
        'Amounts are conditional per-stock money, not returns on a real 1.2m account.',
        'Two FULL arms cannot separately establish causal superiority of the channel, volume state or PVR ranking.',
        'AB APPLICATION counts full raw original permits; early state-blocked requests have untested industry qualification, not industry failure.'])
    report['comparison_release_ready'] = False
    return report
