"""ENTRY_CP knowledge state only. No market model, account, clock, I/O, or history runner."""
from decimal import Decimal as D
import hashlib
import json
import copy
import numpy as np

T, F, U = 1, 0, -1
TOL = D('1e-11')
TERMINAL = ('CANCELLED', 'CONSUMED')


def tri_or(a, b):
    assert a in (T, F, U) and b in (T, F, U)
    return T if T in (a, b) else U if U in (a, b) else F


def positive(value):
    try:
        value = D(str(value))
        return value.is_finite() and value > 0
    except Exception:
        return False


def bool_state(value):
    # NumPy 2 uses the class name 'bool'; use type identity, never its display name.
    # Integer/string sentinels are still not canonical Boolean receipts.
    if isinstance(value, (bool, np.bool_)):
        return T if value else F
    return U


def known_origin(origin):
    return (origin is not None and len(origin) == 3
            and all(v is not None and str(v).strip().lower() not in
                    ('', 'none', 'nan', 'nat', '<na>', 'unknown', 'null') for v in origin))


def ticket_id(request):
    identity = [request['sid'], request['birth_type'], request['signal_day'], tuple(request['origin'])]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]


def structure_ticket(request):
    """Independent entry point: no invented capital caps or fake capital rejection."""
    return dict(ticket_id=ticket_id(request), sid=request['sid'], birth_type=request['birth_type'],
                signal_day=request['signal_day'], nav0=request['nav0'], budget=request['budget'],
                origin=tuple(request['origin']), original_factor=request['factor'],
                current_factor=request['factor'], original_ifloor=request['ifloor'],
                ifloor=request['ifloor'], status='STRUCTURE_WAIT', ever_seeded=False,
                plan=None, first_reject_caps=[], creation_reason='STRUCTURE_GATE',
                last_verified_day=request['plan_day'], event_id=request.get('event_id'))


def new_shadow(request, model_hash, provenance=None):
    assert len(model_hash) == 64 and known_origin(request['origin'])
    identity = structure_ticket(request)
    return dict(identity=identity, model_version=model_hash, provenance=copy.deepcopy(provenance or {}),
                slot=None, unknown_gap=False, unknown_reasons=[], last_open=None, last_close=None,
                current_factor=request['factor'], status='LIVE', last_phase=None)


def event(shadow, date, phase, action, **extra):
    return dict(day=date, phase=phase, event=action, sid=shadow['identity']['sid'],
                ticket_id=shadow['identity']['ticket_id'], original_signal_day=shadow['identity']['signal_day'],
                entry_evidence_id=shadow['slot']['id'] if shadow['slot'] else None, **extra)


def unknown(shadow, date, phase, reason, log):
    shadow['unknown_gap'] = True
    key = (date, phase, reason)
    if key not in shadow['unknown_reasons']:
        shadow['unknown_reasons'].append(key)
        log.append(event(shadow, date, phase, 'UNKNOWN_GAP', reason=reason))
    if shadow['slot']:
        shadow['slot']['unknown_gap'] = True


def state(shadow):
    if shadow['status'] != 'LIVE':
        return F
    if shadow['unknown_gap']:
        return U
    return T if shadow['slot'] and not shadow['slot']['invalid'] else F


def verify_price(shadow, date, phase, raw, factor, origin, source_valid, log):
    """Caller supplies only prices known at this phase and a preflight-verified factor."""
    if shadow['status'] != 'LIVE' or date < shadow['identity']['signal_day']:
        return False
    if not known_origin(origin) or not source_valid or not positive(raw) or not positive(factor):
        unknown(shadow, date, phase, 'PRICE_SOURCE_OR_FACTOR_UNKNOWN', log)
        return False
    if tuple(origin) != shadow['identity']['origin']:
        raise ValueError('KNOWN_SOURCE_CHANGE_REQUIRES_TICKET_CANCELLATION')
    if abs(D(str(factor)) / shadow['current_factor'] - 1) > TOL:
        raise ValueError('FACTOR_MUST_HAVE_PASSED_ORIGINAL_ECONOMIC_PREFLIGHT')
    slot = shadow['slot']
    price = D(str(raw)) * D(str(factor))
    # A CLOSE receipt does not yet exist at that day's OPEN.
    if slot and (date > slot['receipt_day'] or phase == 'CLOSE'):
        slot['last_verified_' + phase.lower()] = date
        if not slot['invalid'] and price <= slot['floor']:
            slot['invalid'] = True
            slot['invalidated_at'] = (date, phase)
            log.append(event(shadow, date, phase, 'INVALIDATED', adjusted_price=str(price), floor=str(slot['floor'])))
    return True


def observe_open(shadow, date, *, raw, factor, origin, source_valid=True, log):
    if shadow['status'] != 'LIVE' or date <= shadow['identity']['signal_day']:
        return state(shadow)
    if shadow['last_open'] == date:
        return state(shadow)
    verify_price(shadow, date, 'OPEN', raw, factor, origin, source_valid, log)
    shadow['last_open'] = date
    return state(shadow)


def observe_close(shadow, date, *, raw_open, raw_close, factor, origin, receipt,
                  candidate=None, source_valid=True, log):
    if shadow['status'] != 'LIVE' or date < shadow['identity']['signal_day']:
        return state(shadow)
    if shadow['last_close'] == date:
        return state(shadow)
    if date > shadow['identity']['signal_day'] and shadow['last_open'] != date:
        observe_open(shadow, date, raw=raw_open, factor=factor, origin=origin, source_valid=source_valid, log=log)
    good = verify_price(shadow, date, 'CLOSE', raw_close, factor, origin, source_valid, log)
    receipt_state = bool_state(receipt)
    if receipt_state == U:
        unknown(shadow, date, 'CLOSE', 'RECEIPT_STREAM_UNKNOWN', log)
    elif receipt_state == T:
        if not positive(candidate):
            unknown(shadow, date, 'CLOSE', 'RECEIPT_CANDIDATE_INVALID', log)
        elif good:
            floor = D(str(candidate))
            identity = ['ENTRY_CP', shadow['identity']['sid'], shadow['identity']['origin'],
                        date, str(floor), shadow['model_version']]
            evidence_id = 'ENTRY_CP:' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            if D(str(raw_close)) * D(str(factor)) <= floor:
                log.append(event(shadow, date, 'CLOSE', 'RECEIPT_ALREADY_BREACHED', rejected_evidence_id=evidence_id, candidate=str(floor)))
            else:
                old = shadow['slot']
                if old:
                    old['superseded_by'] = evidence_id
                    log.append(event(shadow, date, 'CLOSE', 'SUPERSEDED', old_slot=copy.deepcopy(old), replacement=evidence_id))
                shadow['slot'] = dict(id=evidence_id, receipt_day=date, floor=floor,
                                      origin=shadow['identity']['origin'], model_version=shadow['model_version'],
                                      observed_at='CLOSE', last_verified_open=None, last_verified_close=date,
                                      invalid=False, unknown_gap=False, superseded_by=None,
                                      provenance=copy.deepcopy(shadow['provenance']))
                shadow['unknown_gap'] = False
                shadow['unknown_reasons'] = []
                log.append(event(shadow, date, 'CLOSE', 'CREATED', candidate=str(floor)))
    # Explicit False (including ready=False/receipt=False) leaves both slot and gaps intact.
    shadow['last_close'] = date
    return state(shadow)


def finish(shadow, date, status, reason, log):
    assert status in TERMINAL
    if shadow['status'] == status:
        return
    log.append(event(shadow, date, 'LIFECYCLE', status, reason=reason, final_slot=copy.deepcopy(shadow['slot'])))
    shadow['status'] = status
    shadow['slot'] = None


def gate(phase, kind, m, e, active_event, identity_match, fast, cp):
    if kind != 'SEED' or phase in ('EVENT', 'RESIDUAL'):
        return T
    if phase != 'MATURE':
        return U
    assert m == T and positive(e) and active_event and identity_match, 'INCONSISTENT_MATURE_DOMAIN'
    return tri_or(fast, cp)
