"""Associate an externally frozen structural table with saved audited accounts.
No market state calculation, new price source, capital or account construction.
"""
from pathlib import Path
from decimal import Decimal as D
import json, gzip, hashlib

H = Path(__file__).resolve().parent
T = H.parents[2]
R = T / 'risk_constraints'
A = T / 'ar6_native_feasibility/market_recovery_three_state/structural_walk_v1'
Z = D(0)


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str) + '\n')


def main():
    paths = dict(structure=A / 'DAILY.json', windows=A / 'WINDOWS.json', protocol=H / 'PROTOCOL.txt',
        money2=R / 'absolute_loss_2022_2023/NO60_2022_2023_DAILY.json',
        moneyS=R / 'absolute_loss_2022_2023/NO60_STRONG_DAILY.json',
        sector2=R / 'absolute_loss_2022_2023/NO60_2022_2023_SECTOR_DAILY.json',
        sectorS=R / 'absolute_loss_2022_2023/NO60_STRONG_SECTOR_DAILY.json',
        qty22=R / 'pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json',
        qty23=R / 'no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json',
        qtyS=R / 'pvr_pool_results_2025_26/PVR_NO_CONFIRMED60_DAILY.json',
        book2=T / 'pvr_pool_feasibility/continuation2023/run-2023/pair/B.json.gz',
        bookS=T / 'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz',
        tails=R / 'ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json',
        source=H / 'associate_saved_money.py')
    hashes = {str(p): sha(p) for p in paths.values()}
    save(H / 'INPUT_FREEZE.json', dict(before_association=True, source_sha256=hashes,
        scope='external structural table + old audited account day/sector quantities only; no price/state/risk/NAV simulation'))
    structural = read(paths['structure'])
    money = {'two_year': read(paths['money2']), 'strong': read(paths['moneyS'])}
    sectors = {'two_year': read(paths['sector2']), 'strong': read(paths['sectorS'])}
    quantities = {'two_year': read(paths['qty22']) + read(paths['qty23']), 'strong': read(paths['qtyS'])}
    tails = read(paths['tails'])['members']['strong']
    tail_by_sid = {}
    for r in tails: tail_by_sid.setdefault(r['sid'], r)
    clocks = {}
    for window, key in [('two_year', 'book2'), ('strong', 'bookS')]:
        with gzip.open(paths[key], 'rt') as f: book = json.load(f)
        assert all(str(r['at'])[11:19] == '09:30:00' for r in book['trades'])
        splits = [r for r in book['audit'] if r['kind'] == 'split']
        assert all(str(r['at'])[11:19] < '09:30:00' for r in splits)
        clocks[window] = dict(actual_trades=len(book['trades']), all_trade_times='09:30:00+08:00',
            saved_split_events=len(splits), split_clock_before_OPEN=True,
            next_OPEN_quantity_basis='next CLOSE saved quantities after original09:30fills; all actual fills atOPEN and all split quantity changes beforeOPEN. This is not an OPEN market-value mark.')
    selections = []
    summaries = []
    definitions = [('L01', '2022-01-04', '2022-04-26', 'two_year', 1),
                   ('L03', '2022-07-05', '2022-10-31', 'two_year', 1),
                   ('AI_2023Q2', '2023-04-01', '2023-06-30', 'two_year', 1),
                   ('STRONG', '2025-07-01', '2026-06-30', 'strong', 2)]
    for label, lo, hi, window, count in definitions:
        rs = [r for r in structural if lo <= r['day'] <= hi]
        exits = [r for r in rs if r['event'] == 'support_break_D']
        summaries.append(dict(window=label, start=lo, end=hi, structural_closes=len(rs),
            requested_D_days=sum(r['requested_state'] == 'D' for r in rs), requested_C_days=sum(r['requested_state'] == 'C' for r in rs),
            requested_P_days=sum(r['requested_state'] == 'P' for r in rs), explicit_D_transitions=len(exits),
            selected_D_days=[r['day'] for r in exits[:count]], initialized_before_window=True))
        for r in exits[:count]: selections.append((label, lo, hi, window, r))
    footprints = []
    for label, lo, hi, window, structural_row in selections:
        day = structural_row['day'];md = money[window];lookup = {r['day']: r for r in md}
        daily = lookup[day];nextrow = next(r for r in md if r['day'] > day)
        nextday = nextrow['day'];qty = {str(r['at'])[:10]: r for r in quantities[window]}
        q0, q1 = qty[day], qty[nextday]
        future = [r for r in md if day < r['day'] <= hi]
        total = sum((D(r['wealth_change']) for r in future), Z)
        assert total == D(lookup[hi]['NAV_end']) - D(daily['NAV_end'])
        sector_at = [r for r in sectors[window] if r['day'] == day]
        assert sum((D(r['market_value']) for r in sector_at), Z) == D(daily['market_value'])
        sector_future = {}
        for r in sectors[window]:
            if day < r['day'] <= hi:
                key = r['sector'];x = sector_future.setdefault(key, dict(sector=key, industry=r['industry'], following_wealth_change=Z, actual_buy_cash=Z, actual_fees=Z))
                x['following_wealth_change'] += D(r['wealth_change']);x['actual_buy_cash'] += D(r['actual_buy_cash']);x['actual_fees'] += D(r['actual_fees'])
        assert sum((r['following_wealth_change'] for r in sector_future.values()), Z) == total
        for r in sector_at:
            x = sector_future.setdefault(r['sector'], dict(sector=r['sector'], industry=r['industry'], following_wealth_change=Z, actual_buy_cash=Z, actual_fees=Z))
            x.update(asof_D_marked_inventory=r['market_value'], asof_D_held_cost=r['held_cost_basis'],
                asof_D_unrealized_trade_net=D(r['market_value']) - D(r['held_cost_basis']))
        held_tail = [dict(sid=sid, name=tag['name'], industry=tag['industry'], sector=tag['sector'],
            old_actual_qty_at_D=q0['positions'].get(sid, 0), old_actual_qty_after_next_OPEN=q1['positions'].get(sid, 0),
            identity_scope='Frozen original94tail SID label only, not matched order/episode or asof profit.')
            for sid, tag in tail_by_sid.items() if q0['positions'].get(sid, 0) > 0]
        examples = [dict(sid=sid, old_actual_qty_at_D=q0['positions'].get(sid, 0), old_actual_qty_after_next_OPEN=q1['positions'].get(sid, 0))
                    for sid in ['920808.BJ', '603083.SH', '601595.SH']]
        footprints.append(dict(label=label, day=day, structural_request=structural_row, next_original_OPEN_day=nextday,
            original_at_D=dict(NAV=daily['NAV_end'], inventory=daily['market_value'], exposure_pct=daily['exposure_pct'],
                held_stocks=len(q0['positions']), unrealized_trade_net=D(daily['market_value']) - D(daily['held_cost_basis']),
                ACT_after_CLOSE=daily['ACT_after_CLOSE'], pending_original_exit_intents=len(q0['pending_sells'])),
            original_after_next_OPEN=dict(held_stocks=len(q1['positions']), saved_quantities=q1['positions'],
                quantity_clock_note=clocks[window]['next_OPEN_quantity_basis'], next_CLOSE_inventory=nextrow['market_value'],
                next_CLOSE_NAV=nextrow['NAV_end'], next_CLOSE_exposure_pct=nextrow['exposure_pct']),
            original_following=dict(through=hi, wealth_change=total, actual_buy_cash=sum((D(r['actual_buy_cash']) for r in future), Z),
                actual_sell_net=sum((D(r['actual_sell_net']) for r in future), Z), actual_fees=sum((D(r['actual_fees']) for r in future), Z),
                warning='Entire old-account path including later new orders, dividends and inventories. Not PnL of the D-day basket or avoidable/mis-harm PnL.'),
            frozen_old_winner_stock_labels_actually_held=held_tail, fixed_local_counterexample_quantities=examples,
            original_sector_context=sorted(sector_future.values(), key=lambda r: r['sector']),
            no_new_exit_order_or_NAV=True))
    save(H / 'STRUCTURAL_WINDOW_COVERAGE.json', summaries)
    save(H / 'ORIGINAL_QUANTITY_CLOCK_PROOF.json', clocks)
    save(H / 'FOOTPRINTS.json', footprints)
    assert all(sha(p) == h for p, h in hashes.items())
    save(H / 'COMPLETED.json', dict(status='SAVED_ACCOUNT_ASSOCIATION_ONLY', footprints=len(footprints),
        source_post_exact=True, original_sector_to_account_forward_bridges_exact=True,
        original_asof_sector_inventory_bridges_exact=True, new_models=0, new_accounts=0,
        structural_table_sha256=sha(paths['structure']), input_freeze_sha256=sha(H / 'INPUT_FREEZE.json')))
    print('SAVED_MACRO_FOOTPRINTS_READY', len(footprints))


if __name__ == '__main__': main()
