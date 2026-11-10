"""Read-only provider/admission probes on saved raw samples; NO account loop."""
from pathlib import Path
from datetime import datetime, time
import hashlib
import importlib.util
import json
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
CODE = ROOT / 'code'
sys.path.insert(0, str(CODE))
import current_pool_bridge as bridge
import pandas as pd
import sector_stock_admission as admission
from current_fixed_pool import PoolLine
from sector_account import FXQuote, dec
from market_rules import sellable_at
from action_normalize import normalize_a_record, normalize_hk_record

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
snap = OUT / 'code-at-read'
snap.mkdir(exist_ok=False)
for name in ['history_runner.py', 'sector_account.py', 'market_rules.py', 'current_pool_bridge.py']:
    shutil.copyfile(CODE / name, snap / name)
spec = importlib.util.spec_from_file_location('reviewed_history_runner', snap / 'history_runner.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FrozenMarket = mod.FrozenMarket


def at(d, h=17, minute=0):
    return datetime.combine(pd.Timestamp(d).date(), time(h, minute), bridge.TZ)


def version(**extra):
    return dict({'from': '2013-01-01', 'to': None, 'source_id': 'isolated-provider-probe-only',
                 'basis': 'explicit_research_proxy', 'proxy_id': 'probe'}, **extra)


def base_market(lines):
    m = object.__new__(FrozenMarket)
    m.lines = {x.security_id: x for x in lines}
    m.protocol = {'approved_proxy_ids': ['probe'], 'fx_max_age_days': 7}
    m.rules = {}
    m.fx, m._fx_times, m._fx_cache = {}, {}, {}
    m.notices, m._notice_keys = [], {}
    return m


result = dict(account_runs=0, synthetic_account_runs=0, algorithm_runs=0, network_requests=0,
              note='Provider functions and pure admission only; no HistoryRunner/SectorAccount instantiated. Probe declarations are not production manifests or market evidence.')
inventory = []
for market in ('a', 'hk'):
    for p in sorted((ROOT / 'downloads' / f'{market}-pilot-01' / 'history').glob('*.json')):
        obj = json.loads(p.read_text()); rows = obj['bars']
        rp = ROOT / 'downloads' / f'{market}-pilot-01' / 'rights' / p.stem / 'attempt-001' / 'decoded.json'
        rights = json.loads(rp.read_text())
        dates = {r['date'] for r in rows}
        in_window = []
        for x in rights:
            s = str(x['1']); d = s[:4] + '-' + s[4:6] + '-' + s[6:]
            if rows[0]['date'] <= d <= rows[-1]['date']:
                in_window.append(d)
        inventory.append(dict(symbol=p.stem, rows=len(rows), start=rows[0]['date'], end=rows[-1]['date'],
            source=obj.get('source'), history_sha256=sha(p), rights_sha256=sha(rp), rights_in_bar_window=len(in_window),
            rights_dates_missing_from_bars=[d for d in in_window if d not in dates],
            missing_volume_rows=sum(r['volume'] is None for r in rows)))
result['real_sample_inventory'] = inventory

# Actual source conventions: A per ten vs HK per one, without trusting payment dates.
ar = json.loads((ROOT / 'downloads/a-pilot-01/rights/USHA600000/attempt-001/decoded.json').read_text())
a = normalize_a_record('USHA600000', next(r for r in ar if r['1'] == 20260716))
hr = json.loads((ROOT / 'downloads/hk-pilot-01/rights/UHKMHK0001/attempt-001/decoded.json').read_text())
h = normalize_hk_record('UHKMHK0001', next(r for r in hr if r['1'] == 20130524), 'HKD')
result['real_unit_contracts'] = {'A': a, 'HK': h}
assert a['event']['cash_per_old_share'] == '0.42'
assert h['event']['cash_per_old_share'] == '2.63'

# F1: actual A pilot identities, separate declared venue fee rows, broad A route wins.
lines = [PoolLine(s, 'A', None, None, None, True) for s in ('USHA600000', 'USZA000001', 'USTM920000')]
m = base_market(lines)
def fee_row(id, rate):
    return version(schedule={'schedule_id': id, 'components': [{'name': 'handling', 'rate': rate, 'basis': 'fill'}]})
m.rules = {'fee_versions': {'A': [fee_row('SH_SZ-current-handling', '0.0000341')],
                          'BSE': [fee_row('BJ-current-handling', '0.000125')]}}
actual = {s: {'schedule_id': m.fees(s, at('2026-10-22')).schedule_id,
              'handling_at_100k': str(sum(m.fees(s, at('2026-10-22')).incremental('buy', dec(100000), {}, {}, 1).values()))}
          for s in m.lines}
assert actual['USTM920000']['handling_at_100k'] == '3.4100000'
result['F1_market_fee_collapse'] = dict(actual=actual, expected_BJ_handling_at_100k='12.5',
    rate_evidence='../audit-fees/fees.json', fixture_meaning='Separate BSE row is unreachable via current PoolLine.market-only lookup; no fee policy frozen here.')

# F2: preserve the existing HK gate and separately probe the declared tail boundary.
sid = 'UHKMHK0001'
p = ROOT / 'downloads/hk-pilot-01/history' / (sid + '.json')
obj = json.loads(p.read_text())
record = dict(series_id=sid, kind='stock', currency='HKD', status='ready', source_start=obj['bars'][0]['date'],
    volume_unit='shares', price_adjustment='raw', close_available_time='16:10:00',
    raw={'path': str(p), 'sha256': sha(p)}, unavailable_from='2015-05-27')
actions_path = ROOT / 'audit-hk/actions-pilot-v1' / (sid + '.json')
record['adjustment'] = {'method': 'total_return', 'actions': {'path': str(actions_path), 'sha256': sha(actions_path)}}
try:
    bridge.read_actions(record, ROOT)
    raise AssertionError('Existing needs_review HK actions must be rejected')
except ValueError as exc:
    existing_gate = str(exc)
frame = bridge.read_raw(p, record)
frame['valid_price'] = frame.index.isin(bridge.eligible_prices(frame).index)
m = base_market([PoolLine(sid, 'H', None, None, None, True, True)])
m.raw = {sid: frame}
m.bundle = SimpleNamespace(series={sid: SimpleNamespace(record=record)})
m.sessions = {'H': tuple(at(d, 9, 30) for d in frame.index)}
m.fx = {'HKD': [FXQuote(dec('0.8'), at('2015-05-26'), 'isolated-FX-probe-not-historical-claim')]}
m._fx_times = {'HKD': [at('2015-05-26')]}
m.rules = dict(fee_versions={'H': [fee_row('probe-zero', '0')]},
    quantity_versions={sid: [version(rule=dict(rule_id='probe-lot',buy_minimum=100,buy_step=100,sell_step=100,allow_full_exit_odd=True,fill_step=1))]},
    availability_versions={sid: [version(buy_allowed=True, sell_allowed=True)]},
    venue_versions={sid: [version(venue='HKEX_MAIN')]})
m.protocol.update(participation_rate='0.01', daily_execution={'H': dict(price_limit_policy='no_price_limits',reject_flat_day=True,slippage_bps='0',stress_slippage=True)}, sellable_lag_sessions={'H': 0}, settlement_lag_sessions={'H': 2})
window = m.window(sid, at('2015-05-27',9,30), 'sell', 1)
mark = m.latest_mark(sid, at('2015-05-27'))
assert window is not None and window.sell_allowed is True
assert mark.raw_price == dec('118.2')
# Placeholder state only exercises bridge boundary dispatch, not algorithm quality.
states = pd.DataFrame({'ready': [True], 'target': [True], 'rs': [0.5]}, index=pd.DatetimeIndex(['2015-05-26']))
b = object.__new__(bridge.Bundle); b.series = {sid: bridge.SeriesData(record, states=states)}
clock = admission.Clock(at('2015-05-27'), at('2015-05-28',9,30), pd.Timestamp('2015-05-27').date())
assert b._last(sid, clock) == (None, None, None)
f = lambda value: admission.Fact(value, clock.decision_at, clock.decision_at, source_id='probe')
security = admission.Security(sid, f('issuer'), f('sector'), f(None), f(True), f(20e9), f(None))
held = admission.Occupancy(sid, 'issuer', 'sector', clock.decision_at, has_position=True)
decision = admission.decide(clock=clock, variant='T0', securities=[security], sectors=[admission.Sector('sector',f(True))], occupied=[held])
assert not decision.exit_requests
result['F2_unavailable_stock_boundary'] = dict(existing_full_HK_gate=existing_gate,
    real_event=next(r for r in hr if r['1'] == 20150527), previous_close=str(frame.loc['2015-05-26','close']),
    declared_unavailable_from=record['unavailable_from'], bridge_state_after_boundary=None,
    provider_sell_window_allowed=window.sell_allowed, provider_sell_raw_open=str(window.raw_open),
    provider_mark_after_boundary=str(mark.raw_price), pure_admission_exit_requests=list(decision.exit_requests),
    limitation='No production prefix approval, true trend assertion, held-account simulation or gate bypass. Demonstrates provider boundary not enforced if a partial prefix is later admitted.')

# F3: runner bypasses market_rules' already available one-session-per-date guard.
m.sessions = {'A': [at('2026-10-21',9,30), at('2026-10-21',13), at('2026-10-22',9,30)]}
actual_lag = m.lag('A', at('2026-10-21',9,30), 1)
assert actual_lag.date() == pd.Timestamp('2026-10-21').date()
try:
    sellable_at(at('2026-10-21',9,30), m.sessions['A'], 1)
    raise AssertionError('Existing session validator must reject duplicate local date')
except ValueError as exc:
    proper_rejection = str(exc)
result['F3_session_clock_validation'] = dict(runner_lag1=str(actual_lag), correct_existing_adapter_rejection=proper_rejection,
    limitation='Malformed multi-open calendar acceptance, not evidence current production calendar contains this error.')
result['reviewed_code_sha256'] = {p.name: sha(p) for p in snap.iterdir()}
result['current_code_matches_read_snapshot'] = {p.name: sha(CODE / p.name) == sha(p) for p in snap.iterdir()}
with (OUT / 'findings.json').open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(dict(real_symbols=len(inventory), confirmed_provider_findings=3, account_runs=0, current_code_matches_snapshot=result['current_code_matches_read_snapshot']), ensure_ascii=False))
