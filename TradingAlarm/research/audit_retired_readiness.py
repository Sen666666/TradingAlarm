"""Audit checkpointed raw histories; never equate structural validity with readiness."""
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/stock-data-audit'


def inspect_history(payload, master):
    errors = []
    frame = pd.DataFrame(payload.get('rows', []))
    required = {'date', 'code', 'open', 'high', 'low', 'close', 'volume',
                'amount', 'tradestatus', 'isST', 'adjustflag'}
    if frame.empty or not required.issubset(frame.columns):
        return {'structurally_valid': False, 'errors': ['empty_or_missing_fields'], 'rows': len(frame)}
    dates = pd.to_datetime(frame.date, errors='coerce')
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        errors.append('invalid_duplicate_or_unsorted_dates')
    if (dates < pd.Timestamp(max(master['ipoDate'], '2010-01-01'))).any() or (dates > pd.Timestamp(master['outDate'])).any():
        errors.append('dates_outside_requested_lifetime')
    # BaoStock pagination may silently stop at a full 2,000-row page after a
    # transport failure. A long tail gap requires review, not assumed completion.
    tail_gap = (pd.Timestamp(master['outDate']) - dates.max()).days
    if len(frame) % 2000 == 0 and tail_gap > 30:
        errors.append('suspected_incomplete_pagination')
    if payload.get('symbol') != master['symbol'] or not frame.code.eq(master['code']).all():
        errors.append('symbol_mismatch')
    for field, allowed in [('tradestatus', {'0', '1'}), ('isST', {'0', '1'}), ('adjustflag', {'3'})]:
        if not set(frame[field].astype(str)).issubset(allowed):
            errors.append('invalid_' + field)
    num = frame[['open', 'high', 'low', 'close', 'volume', 'amount']].apply(pd.to_numeric, errors='coerce')
    trading = frame.tradestatus.eq('1')
    valid_prices = (num[['open', 'high', 'low', 'close']] > 0).all(axis=1)
    valid_prices &= num.high.ge(num[['open', 'close', 'low']].max(axis=1)) & num.low.le(num[['open', 'close']].min(axis=1))
    valid_prices &= np.isfinite(num[['open', 'high', 'low', 'close']]).all(axis=1)
    if (trading & ~valid_prices).any():
        errors.append('invalid_trading_ohlc')
    if (num[['volume', 'amount']] < 0).any().any():
        errors.append('negative_activity')
    active = trading & num.volume.gt(0) & valid_prices
    if not np.isfinite(num.loc[trading, ['volume', 'amount']]).all().all():
        errors.append('nonfinite_trading_activity')
    vwap = num.amount.div(num.volume.replace(0, np.nan))
    bad_vwap = active & ~(vwap.ge(num.low * .98) & vwap.le(num.high * 1.02))
    if bad_vwap.any():
        errors.append('vwap_outside_bar_requires_review')
    return {
        'structurally_valid': not errors, 'errors': errors, 'rows': len(frame),
        'first_date': str(frame.date.iloc[0]), 'last_date': str(frame.date.iloc[-1]),
        'tail_gap_calendar_days': int(tail_gap),
        'last_positive_volume_date': str(frame.loc[active, 'date'].iloc[-1]) if active.any() else None,
        'suspended_rows': int((~trading).sum()), 'st_rows': int(frame.isST.eq('1').sum()),
        'positive_volume_rows': int(active.sum()), 'vwap_review_rows': int(bad_vwap.sum()),
        'execution_ready': False,
        'remaining_gates': ['corporate_actions', 'dated_price_limits', 'terminal_event_and_proceeds', 'calendar_completeness'],
    }


def main():
    master = pd.read_csv(OUT / 'missing-retired-symbols.csv', dtype=str)
    selected = master[pd.to_datetime(master.outDate) >= pd.Timestamp('2015-01-01')].sort_values('symbol')
    records = []
    for row in selected.to_dict('records'):
        file = ROOT / 'data/retired-pilot' / (row['symbol'] + '.json')
        result = {'symbol': row['symbol'], 'downloaded': file.exists()}
        if file.exists():
            try:
                result.update(inspect_history(json.loads(file.read_text()), row))
            except (ValueError, KeyError, TypeError) as exc:
                result.update(structurally_valid=False, errors=[type(exc).__name__])
        records.append(result)
    report = {
        'as_of': datetime.now().astimezone().isoformat(), 'selected': len(records),
        'downloaded': sum(x['downloaded'] for x in records),
        'structurally_valid': sum(x.get('structurally_valid', False) for x in records),
        'raw_rows': sum(x.get('rows', 0) for x in records), 'execution_ready': 0,
        'scope': 'Provider-known missing SH/SZ retirees since 2015; not a complete exchange universe.',
        'units': {'volume': 'shares', 'amount': 'CNY'},
        'warning': 'Nontrading rows never fill. Missing dates require calendar audit. Delisting is not automatic zero value or an executable sale.',
        'records': records,
    }
    (OUT / 'retired-readiness.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
