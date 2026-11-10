"""Bounded saved-account/price attribution only. No strategy state or account."""
from pathlib import Path
from decimal import Decimal as D
import hashlib
import json
import pandas as pd

H = Path(__file__).resolve().parent
T = H.parent.parent
P = T / 'pvr_pool_feasibility/market_phase_2022_2023'
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
M = W / 'mainline-absolute-Q4-20261031/recovery.csv'
Z = D(0)


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str) + '\n')


def main():
    files = [P / p for p in ['HS300_ALL_LEGS.json', 'DAILY_ALIGNED.json', 'ALL_PERIODS.json', 'ALL_PHASE_STOCK_WEALTH.json', 'PHASE_STOCK_WEALTH_BRIDGES.json', 'PHASE_SECTOR_CONTRIBUTIONS.json']]
    files += [M, H / 'analyze_saved.py', W / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json']
    dpaths = [T / 'risk_constraints/pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json', T / 'risk_constraints/no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json']
    strong_path = T / 'risk_constraints/absolute_loss_2022_2023/NO60_STRONG_DAILY.json'
    files += dpaths + [strong_path]
    save(H / 'INPUT_FREEZE.json', dict(scope='fixed old L01-L05 account/price/risk and fixed3 winner context; no D/P/C state, parameter sweep, model or account', source_sha256={str(p): sha(p) for p in files}))
    daily = read(P / 'DAILY_ALIGNED.json')['NO60']
    legs = read(P / 'HS300_ALL_LEGS.json')
    periods = {r['period']: r for r in read(P / 'ALL_PERIODS.json') if r['policy'] == 'NO60' and r['period'].startswith('L0')}
    cohorts = {r['leg']: r for r in read(P / 'PHASE_STOCK_WEALTH_BRIDGES.json') if r['policy'] == 'NO60'}
    market = pd.read_csv(M, index_col=0, parse_dates=True)
    snapshots = {str(r['at'])[:10]: r for p in dpaths for r in read(p)}
    assert len(snapshots) == 484
    stocks = read(P / 'ALL_PHASE_STOCK_WEALTH.json')['NO60']
    phases = []
    for leg in legs:
        rows = [r for r in daily if leg['first_analysis_day'] <= r['day'] <= leg['last_analysis_day']]
        r = periods[leg['id']]
        left = market.loc[:leg['left']].iloc[-1]
        right = market.loc[:leg['right']].iloc[-1]
        phases.append(dict(phase=leg['id'], start=r['start'], end=r['end'], days=len(rows),
                           account_wealth_change=r['net_PnL'], account_return_pct=r['return_pct'], HS300_return_pct=r['HS300_return_pct'],
                           synthetic_M_return_pct=(float(right.market) / float(left.market) - 1) * 100,
                           synthetic_M_is_not_traded=True,
                           mean_lag_exposure_pct=r['mean_lag_exposure_pct'], initial_inventory=rows[0]['inventory_begin'],
                           final_inventory=rows[-1]['inventory_end'], actual_buy_cash=r['actual_buy_cash'], actual_fees=r['actual_fees'],
                           mean_nominal_risk_pct=sum((D(x['nominal_risk_pct']) for x in rows), Z) / len(rows),
                           max_nominal_risk_pct=max(D(x['nominal_risk_pct']) for x in rows),
                           ACT_paused_OPEN_days=r['ACT_paused_OPEN_days'], ACT_active_OPEN_days=r['ACT_active_OPEN_days'],
                           stock_cohort_wealth=cohorts[leg['id']]['cohorts']))
    save(H / 'PHASE_MONEY_RISK.json', phases)
    selected_days = ['2022-04-19', '2022-04-20', '2022-04-21', '2022-06-17', '2022-06-20', '2022-07-04', '2022-07-05', '2022-10-31', '2023-01-30', '2023-04-28', '2023-06-30', '2023-07-20', '2023-07-21']
    save(H / 'ACT_CLOCK_SNAPSHOTS.json', [dict(**next(r for r in daily if r['day'] == day), synthetic_M=float(market.loc[day, 'market']), synthetic_B=float(market.loc[day, 'breadth'])) for day in selected_days])
    cap = []
    for label, rows in [('2022_2023', daily), ('STRONG_2025_26', read(strong_path))]:
        held = [r for r in rows if D(r['market_value']) > 0]
        over = [r for r in held if D(r['nominal_risk_pct']) > D('4.5')]
        cap.append(dict(window=label, all_closes=len(rows), held_closes=len(held), closes_nominal_risk_above_proposed_4_5_pct=len(over),
                        mean_nominal_risk_pct=sum((D(r['nominal_risk_pct']) for r in rows), Z) / len(rows),
                        original_actual_buy_cash_on_those_closes=sum((D(r['actual_buy_cash']) for r in over), Z),
                        original_total_actual_buy_cash=sum((D(r['actual_buy_cash']) for r in rows), Z),
                        interpretation='Association with old CLOSE state, not new-order reject counts, avoidable loss or hypothetical NAV.'))
    save(H / 'PROPOSED_CAP_OLD_STATE_OVERLAP.json', cap)
    winners = []
    # Prespecified explanatory representatives: L05 computer/communications/local
    # movie rally. Their realized whole-leg records are not input to a gate.
    for sid in ['920808.BJ', '603083.SH', '601595.SH']:
        native = next(r for r in stocks if r['leg'] == 'L05' and r['sid'] == sid)
        held = [r for day, r in sorted(snapshots.items()) if day >= '2023-01-31' and r['positions'].get(sid, 0) > 0]
        winners.append(dict(**native, first_L05_held_close=str(held[0]['at']), last_held_close=str(held[-1]['at']),
                            warning='Whole fixed-leg observed profit, not profit lost under defensive liquidation; stocks were selected as explicit known counterexamples.'))
    save(H / 'LOCAL_WINNER_COUNTEREXAMPLES.json', winners)
    # Reuse original factor conversion of effective core/mobile protection lines.
    manifest = {r['symbol']: r for r in read(W / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    facts_cache = {}
    def facts(sid):
        if sid not in facts_cache:
            p = Path(manifest[sid]['refs']['facts']);facts_cache[sid] = pd.read_parquet(p);files.append(p)
        return facts_cache[sid]
    examples = []
    for day in ['2022-07-04', '2023-04-14', '2023-05-04', '2023-07-20']:
        r = snapshots[day];groups = {}
        for lot in r['layers']:
            sid = lot['sid'];q = D(lot['qty']);f = facts(sid)
            if pd.Timestamp(day) not in f.index: continue
            z = f.loc[day];factor = D(str(z.factor));mark = D(str(z.raw_close));line = lot['last_core_line'] if lot['role'] == 'core' else lot['floor']
            x = groups.setdefault(sid, dict(sid=sid, quantity=Z, market_value=Z, line_risk=Z, lot_lines=[]))
            x['quantity'] += q;x['market_value'] += q * mark
            if line is not None:
                raw_line = D(str(line)) / factor;x['line_risk'] += q * max(Z, mark - raw_line)
                x['lot_lines'].append(dict(layer=lot['id'], role=lot['role'], qty=q, raw_close=mark, signal_effective_line=line, current_factor=factor, raw_equivalent_line=raw_line, distance_pct=(mark - raw_line) / mark * 100))
        chosen = sorted(groups.values(), key=lambda x: x['market_value'], reverse=True)[:3] if day == '2022-07-04' else [groups[s] for s in ['920808.BJ', '603083.SH', '601595.SH'] if s in groups]
        examples.append(dict(day=day, account_NAV=r['nav'], actual_inventory=r['inventory'], actual_nominal_risk=D(str(r['pool_probe'][1])) + D(str(r['pool_confirmed'][1])),
                             chosen=chosen, selection='L03 start top3 actual held market value; otherwise the fixed3 local rally counterexamples',
                             limits='Known exact source dates only; raw-equivalent lines are current adjustment-coordinate conversions, not guaranteed executable stop fills or market-S translation.'))
    save(H / 'ACTUAL_ASSET_PROTECTION_EXAMPLES.json', examples)
    # Mathematical capital permissions only, no return projection.
    save(H / 'UNIT_ARITHMETIC.json', dict(planned_NAV=1200000, units=[dict(n=n, gross_permission_fraction=min(D('.1') * n, D('.9')), nominal_risk_permission_fraction=D('.005') * n,
        gross_yuan_at_planned_NAV=D(1200000) * min(D('.1') * n, D('.9')), nominal_risk_yuan_at_planned_NAV=D(1200000) * D('.005') * n) for n in range(1, 10)],
        one_R_option_only=dict(not_executed=True, extra_price_advance_to_n9='8 * R_init', examples_entry_R_fraction_to_extra_M_advance_pct={'.02': 16, '.05': 40, '.10': 80}, caution='Conditional arithmetic until C/other rule overrides; these R widths are illustrative, not fitted values or a second tested state machine.'),
        admissible_stock_quantity='min(original target/native risk/sector/pool/lot/cash limits, macro gross+pending room, macro actual-line nominal-risk room); no synthetic-M-to-stock-loss equality'))
    save(H / 'SOURCE_MANIFEST.json', {str(p): sha(p) for p in files})
    print('SAVED_REGIME_RISK_ATTRIBUTION_READY', len(phases), len(examples), len(files))


if __name__ == '__main__': main()
