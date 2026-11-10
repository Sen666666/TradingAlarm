"""Finite, offline normalization of saved THS corporate-action terms.

Cash remains in its named currency. Source dates are not fabricated announcement,
payment or delivery dates. Parsed terms alone never admit an account or signal.
"""
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
import argparse
import collections
import importlib.util
import json
import re

import history_batch as hb

ROOT = Path(__file__).resolve().parents[3]
LEGACY_CASH = ROOT / 'research_rounds/pv-retained-impact-20261020/results/code/hk_cash_annotations.py'
A_PARSER = hb.DEFAULT_RESEARCH / 'stock_actions.py'
NUMBER = r'(?:0|[1-9]\d*)(?:\.\d+)?'


@lru_cache(maxsize=4)
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def decimal_text(value):
    return format(Decimal(value).normalize(), 'f')


def source_date(row):
    """Keep a valid source date even when the action terms are unsupported."""
    dt = datetime.strptime(str(row['1']), '%Y%m%d').date()
    prefix = re.match(r'^(\d{4}-\d{2}-\d{2})', row['471'])
    if not prefix or date.fromisoformat(prefix[1]) != dt:
        raise ValueError('source date mismatch')
    return dt


def cash_token(token):
    """Map only exact THS per-share units to the prior audited cash helper."""
    value, currency = None, None
    m = re.fullmatch(r'每股(?:派|普通股)?(' + NUMBER + r')(港元|港仙|美元|美仙)', token)
    if m:
        value = Decimal(m[1]) / (100 if m[2].endswith('仙') else 1)
        currency = '港元' if m[2].startswith('港') else '美元'
    else:
        m = re.fullmatch(r'每股港币(?:(' + NUMBER + r')元)?(?:(' + NUMBER + r')角)?(?:(' + NUMBER + r')仙)?', token)
        if m and any(x is not None for x in m.groups()):
            value = Decimal(m[1] or 0) + Decimal(m[2] or 0)/10 + Decimal(m[3] or 0)/100
            currency = '港元'
    if value is None:
        return None
    # Reuse established currency/component conventions; alternatives are not
    # added to cash and ADS units are never treated as extra local-share cash.
    helper = load_module(LEGACY_CASH, 'existing_hk_cash_annotations')
    component = helper.parse_cash('每股股息' + decimal_text(value) + currency)[0]
    return {'kind': 'cash', 'currency': component['currency'], 'amount_per_source_share': decimal_text(component['amount']),
            'entitlement_basis': 'one source share on the stated event date; no record-date entitlement inferred', 'raw_token': token}


def share_token(token):
    patterns = [r'每(' + NUMBER + r')股拆分为(' + NUMBER + r')股',
                r'(' + NUMBER + r')股拆(' + NUMBER + r')股',
                r'每(' + NUMBER + r')股已发行及未发行普通股分拆为(' + NUMBER + r')股新股份']
    kind, old, new = 'split', None, None
    for pattern in patterns:
        m = re.fullmatch(pattern, token)
        if m: old, new = Decimal(m[1]), Decimal(m[2]); break
    if old is None:
        m = re.fullmatch(r'每(' + NUMBER + r')股每股面值(' + NUMBER + r')港元之已发行及未发行现有股份将合并成(' + NUMBER + r')股', token)
        if m: kind, old, new = 'consolidation', Decimal(m[1]), Decimal(m[3])
    if old is None:
        m = re.fullmatch(r'每股送(' + NUMBER + r')红股', token)
        if m: kind, old, new = 'bonus', Decimal(1), Decimal(1)+Decimal(m[1])
    if old is None or old <= 0 or new <= 0:
        return None
    ratio = Fraction(new) / Fraction(old)
    return {'kind': kind, 'old_shares': decimal_text(old), 'new_shares': decimal_text(new),
            'ratio_numerator': ratio.numerator, 'ratio_denominator': ratio.denominator,
            'split_ratio': decimal_text(new/old), 'raw_token': token}


def unsupported_kind(text):
    if any(x in text for x in ('认购', '供股', '获供')):
        return 'subscription_terms_unmodeled'
    if any(x in text for x in ('获发', '分派', '可选择收取现金')):
        return 'in_kind_or_election_unmodeled'
    if '拆细股份' in text:
        return 'cash_share_basis_after_split_unverified'
    if any(x in text for x in ('拆', '合并', '红股')):
        return 'share_terms_unmodeled'
    return 'unsupported_cash_or_other_terms'


def normalize_hk_record(symbol, row, price_currency='HKD'):
    result = {'symbol': symbol, 'source_record': row, 'components': [], 'unresolved': [],
              'source_effective_date': None, 'announcement_date': None, 'known_at': None,
              'record_date': None, 'pay_date': None, 'new_share_tradable_date': None,
              'ledger_ready': False, 'event': None}
    try:
        dt = source_date(row)
        result['source_effective_date'] = str(dt)
        text = row['471']
        m = re.fullmatch(r'(\d{4}-\d{2}-\d{2})(?:\$(.*)|\((.*)\))', text)
        if not m or date.fromisoformat(m[1]) != dt:
            raise ValueError('source_date_or_format_mismatch')
        body = m[2] if m[2] is not None else m[3]
    except (KeyError, TypeError, ValueError):
        result['unresolved'] = ['source_date_or_format_mismatch']; return result
    # Complex entitlements must remain intact: commas may be thousands separators.
    if any(x in body for x in ('认购', '供股', '获供', '获发', '分派', '可选择收取现金')):
        result['unresolved'] = [unsupported_kind(body)]; return result
    tokens = [x for x in body.replace('，', ',').split(',') if x]
    if not tokens:
        result['unresolved'] = ['empty_terms']; return result
    for token in tokens:
        component = cash_token(token) or share_token(token)
        if component:
            result['components'].append(component)
        else:
            result['unresolved'].append(unsupported_kind(token))
    cash = collections.defaultdict(Decimal)
    shares = []
    for component in result['components']:
        if component['kind'] == 'cash':
            cash[component['currency']] += Decimal(component['amount_per_source_share'])
        else:
            shares.append(component)
    if any(currency != price_currency for currency in cash):
        result['unresolved'].append('cash_currency_requires_explicit_fx_or_matching_quote_currency')
    if len(shares) > 1:
        result['unresolved'].append('multiple_share_components_require_order_review')
    if shares and cash and shares[0]['kind'] != 'bonus':
        result['unresolved'].append('same_date_cash_split_entitlement_order_unverified')
    result['cash_by_currency'] = {k: decimal_text(v) for k, v in cash.items()}
    result['terms_parsed'] = not any(x not in {'cash_currency_requires_explicit_fx_or_matching_quote_currency'} for x in result['unresolved'])
    if not result['unresolved']:
        result['event'] = {'effective_date': str(dt), 'cash_per_old_share': decimal_text(cash.get(price_currency, Decimal(0))),
                           'split_ratio': shares[0]['split_ratio'] if shares else '1', 'currency': price_currency}
    return result


def normalize_a_record(symbol, row):
    result = {'symbol': symbol, 'source_record': row, 'event': None, 'components': [], 'unresolved': [], 'ledger_ready': False}
    try:
        result['source_effective_date'] = str(source_date(row))
        parsed = load_module(A_PARSER, 'existing_a_stock_actions').parse_ths_rights(symbol, row)
        # Decimal re-read keeps source precision, while the prior parser validates
        # the complete A-share grammar and the mandatory per-ten-share denominator.
        text = row['471']; cash = Decimal(0); shares = Decimal(1)
        for kind, amount, _ in re.findall(r'(转增|送股|送|红利)(\d+(?:\.\d+)?)(股|元)', text):
            if kind == '红利': cash += Decimal(amount)/10
            else: shares += Decimal(amount)/10
        result.update(source_effective_date=parsed['effective_date'], announcement_date=None, known_at=None,
                      record_date=None, pay_date=None, new_share_tradable_date=None, terms_parsed=True,
                      event=dict(effective_date=parsed['effective_date'], cash_per_old_share=decimal_text(cash), split_ratio=decimal_text(shares), currency='CNY'))
    except (KeyError, TypeError, ValueError):
        result['unresolved'] = ['unsupported_a_record_or_date']
    return result


def normalize_actions(series_id, records, currency, origin, last, source_id, market=None, source_symbol=None):
    """Bridge-compatible candidates; human/source-coverage review still required."""
    origin, last = date.fromisoformat(origin), date.fromisoformat(last)
    if origin > last: raise ValueError('origin after last')
    source_symbol = source_symbol or series_id
    if market is None:
        if source_symbol.startswith(('UHKM', 'UHKG')) or re.fullmatch(r'HK\d+', source_symbol) or source_symbol.endswith('.HK'):
            market = 'HK'
        elif source_symbol.startswith(('USHA', 'USZA', 'USHT', 'USTM')) or re.fullmatch(r'\d{6}\.(?:SH|SZ|BJ)', source_symbol):
            market = 'A'
        else:
            raise ValueError('explicit market A/HK or recognized source_symbol required')
    if market not in {'A', 'HK'}: raise ValueError('market must be A or HK')
    details, ignored, unresolved, events = [], [], [], []
    if not records:
        unresolved.append({'source_id': source_id, 'effective_date': None,
                           'reasons': ['empty_rights_response_does_not_certify_no_events'], 'raw': None})
    bydate = collections.Counter(str(r.get('1')) for r in records)
    for index, row in enumerate(records):
        parsed = normalize_hk_record(source_symbol, row, currency) if market == 'HK' else normalize_a_record(source_symbol, row)
        event_source = source_id + '#record-' + str(index)
        parsed.update(source_id=event_source)
        dt = parsed.get('source_effective_date')
        if bydate[str(row.get('1'))] > 1:
            parsed['unresolved'].append('multiple_same_date_source_rows_require_explicit_aggregation'); parsed['event'] = None
        if dt and date.fromisoformat(dt) < origin:
            parsed['scope'] = 'ignored_before_signal_origin'; ignored.append(parsed)
        elif dt and date.fromisoformat(dt) > last:
            parsed['scope'] = 'outside_signal_window_after_last'; ignored.append(parsed)
        else:
            parsed['scope'] = 'production_window'; details.append(parsed)
            if dt and date.fromisoformat(dt) == origin:
                parsed['unresolved'].append('origin_date_action_requires_explicit_prior_or_origin_policy')
                parsed['event'] = None
            if parsed['unresolved']:
                unresolved.append({'source_id': event_source, 'effective_date': dt, 'reasons': parsed['unresolved'], 'raw': row})
            elif parsed['event']:
                events.append(dict(parsed['event'], source_id=event_source))
    return {'series_id': series_id, 'source_symbol': source_symbol, 'market': market, 'currency': currency, 'status': 'needs_review',
            'coverage_evidence': {'source_id': source_id, 'observed_records': len(records), 'origin': str(origin), 'last': str(last),
                                  'meaning': 'Saved THS id211 response inspected; source completeness and dates not independently certified'},
            'events': sorted(events, key=lambda x: x['effective_date']), 'unresolved': unresolved,
            'production_details': details, 'ignored_outside_window': ignored,
            'ledger_ready': False, 'announcement_date': None, 'known_at': None,
            'pay_date': None, 'new_share_tradable_date': None,
            'limitations': ['Candidate source terms only; needs_review must be cleared explicitly before a signal bridge.',
                            'No tax, FX, payment, deliverability, odd-lot, subscription or in-kind valuation assumptions.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', default='2013-01-01')
    parser.add_argument('--currency', default='HKD')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources, totals, reports = [], collections.Counter(), []
    for rights in sorted(args.batch.glob('rights/*/attempt-*/decoded.json')):
        symbol = rights.parent.parent.name
        if not symbol.startswith(('UHKM', 'UHKG')): continue
        history = hb.read_json(args.batch / 'history' / (symbol + '.json'))
        dates = sorted(b['date'] for b in history['bars'] if b['date'] >= args.start)
        if not dates: continue
        raw = rights.read_bytes(); records = json.loads(raw)
        response = rights.with_name('response.bin'); receipt = hb.read_json(rights.with_name('receipt.json'))
        if hb.digest(response.read_bytes()) != receipt['sha256']: raise ValueError('raw response hash mismatch')
        source_id = str(rights.resolve()) + '@sha256:' + hb.digest(raw)
        normalized = normalize_actions(symbol, records, args.currency, dates[0], dates[-1], source_id)
        hb.immutable(args.output / (symbol + '.json'), hb.encoded(normalized))
        totals['raw_records'] += len(records); totals['candidate_events_in_window'] += len(normalized['events'])
        totals['unresolved_records_in_window'] += len(normalized['unresolved']); totals['ignored_outside_window'] += len(normalized['ignored_outside_window'])
        reports.append({'symbol': symbol, 'origin': dates[0], 'last': dates[-1], 'raw_records': len(records),
                        'candidate_events': len(normalized['events']), 'unresolved_records': len(normalized['unresolved']),
                        'unresolved_reasons': dict(collections.Counter(reason for x in normalized['unresolved'] for reason in x['reasons']))})
        for path in [rights, response, rights.with_name('request.json'), rights.with_name('receipt.json')]:
            sources.append({'path': str(path.resolve()), 'sha256': hb.digest(path.read_bytes()), 'bytes': path.stat().st_size})
    hb.immutable(args.output / 'summary.json', hb.encoded({'created_at': hb.now(), 'totals': dict(totals), 'symbols': reports,
                  'network_requests': 0, 'account_runs': 0, 'algorithm_changes': 0, 'payment_or_delivery_proxy_decisions': 0}))
    sources += [{'path': str(p.resolve()), 'sha256': hb.digest(p.read_bytes()), 'bytes': p.stat().st_size} for p in [Path(__file__), LEGACY_CASH, A_PARSER]]
    hb.immutable(args.output / 'source-code-manifest.json', hb.encoded(sources))
    print(json.dumps({'symbols': len(reports), 'totals': dict(totals), 'network_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
