"""Read existing source/book/chain only; no imports of financial engines or replay."""
import gzip
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BOOK = ROOT / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
CHAINS = ROOT / 'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    evidence_path = OUT / 'ORIGINAL_EXECUTION_RISK_EVIDENCE.json'
    evidence = json.loads(evidence_path.read_text())
    source_identity = {}
    for path, expected in evidence['source_sha256'].items():
        actual = sha(Path(path))
        assert actual == expected, path
        source_identity[path] = actual
    book = json.load(gzip.open(BOOK, 'rt'))
    chains = json.loads(CHAINS.read_text())
    silver = next(c for c in chains if c['campaign']['sid'] == '300085.SZ')
    close = next(o for o in silver['observations'] if o['day'] == '2024-10-10')
    assert close['stock']['raw_close'] == 37.76
    assert close['stock']['i_target'] == 1
    assert close['original_pending_sells'] == ['300085.SZ']
    assert not close['original_intents']
    assert all('exit_pending' in x['barriers'] for x in close['original_opportunities'])
    journal = book['journal']
    day = [(n, x) for n, x in enumerate(journal)
           if str(x.get('at', '')).startswith('2024-10-11')]
    sales = [(n, x) for n, x in day if x.get('kind') == 'real_sell_fill'
             and x.get('sid') == '300085.SZ']
    reserves = [(n, x) for n, x in day if x.get('kind') == 'real_reserve']
    buys = [(n, x) for n, x in day if x.get('kind') == 'real_buy_fill']
    assert len(sales) == 1
    sn, sale = sales[0]
    assert sn == 5534 and sale['shares'] == 300 and sale['price'] == '30.194895'
    assert len(reserves) == len(buys) == 10
    assert sn < min(n for n, _ in reserves) < min(n for n, _ in buys)
    assert reserves[0][0] == 5541 and buys[0][0] == 5551
    trades = [(n, t) for n, t in enumerate(book['trades'])
              if t.get('security_id') == '300085.SZ'
              and t.get('side') == 'sell'
              and str(t.get('at', '')).startswith('2024-10-11')]
    assert len(trades) == 1 and trades[0][0] == 3509
    case = next(c for c in evidence['cases'] if c['campaign']['sid'] == '300085.SZ')
    entry = case['entries'][0]
    buy_cash = D(entry['actual_cost'])
    close_mark = D('37.76') * 300
    sold_net = D('30.194895') * 300 - D(sale['fees'])
    already_lost_at_close = buy_cash - close_mark
    remaining_realized_loss = close_mark - sold_net
    assert already_lost_at_close + remaining_realized_loss == -D(entry['actual_net'])
    output = {
        'status': 'PASS_READ_ONLY_ORIGINAL_SOURCE_AND_CASHFLOW_CHECK',
        'scope': '2 original cases; original Oct11 journal order; no replay, no counterfactual',
        'source_sha256': source_identity,
        'book': {'path': str(BOOK), 'sha256': sha(BOOK)},
        'chains': {'path': str(CHAINS), 'sha256': sha(CHAINS)},
        'script': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'silver_original_order': {
            'index_basis': 'zero-based indices into original B.json.gz arrays',
            'sell_trade_index': trades[0][0], 'sell_journal_index': sn,
            'sell': sale, 'first_new_reserve': {'index': reserves[0][0], 'entry': reserves[0][1]},
            'first_new_buy': {'index': buys[0][0], 'entry': buys[0][1]},
            'new_reserve_count': len(reserves), 'new_buy_count': len(buys),
            'all_new_reserves_follow_successful_silver_sell': True,
            'Oct10_pending_same_sid': close['original_pending_sells'],
            'Oct10_same_sid_new_intents': close['original_intents'],
            'Oct10_same_sid_opportunities': close['original_opportunities'],
            'risk_zero_funded_any_actual_new_buy': 'UNPROVEN; this stock sold before all new reservations',
        },
        'silver_actual_cashflow_only': {
            'actual_buy_cash_including_fee': str(buy_cash),
            'Oct10_close_mark_still_in_inventory': str(close_mark),
            'loss_already_present_at_Oct10_CLOSE_including_buy_fee': str(already_lost_at_close),
            'remaining_actual_CLOSE_to_sell_loss_including_sell_fee': str(remaining_realized_loss),
            'actual_total_loss': str(buy_cash - sold_net),
            'not_a_guaranteed_future_loss_bound': True,
            'Oct10_resources_distance_risk_zero_is_not_cash_or_capital_release': True,
        },
        'shared_20000': {
            'initialization': 'joint_v3.py:16 exhausted_policy=record_only',
            'loss_cancel_disabled_branch': 'model_without_account_check.py:90-93',
            'new_request_rejection_disabled_branch': 'model_without_account_check.py:236-238',
            'definition': 'sum across sector/episode of gross negative realized price PnL plus actual fees; price profits do not offset; not net PnL or drawdown',
            'enforces_20000_loss_ceiling': False,
        },
        'new_accounts': 0, 'new_models': 0, 'new_parameter_sets': 0,
        'new_counterfactuals': 0, 'financial_source_modified': False,
    }
    (OUT / 'ORIGINAL_CLOCK_AND_LOSS_AUDIT.json').write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': output['status'], 'journal': sn,
                      'first_reserve': reserves[0][0], 'first_buy': buys[0][0],
                      'already_lost': str(already_lost_at_close),
                      'remaining_actual_loss': str(remaining_realized_loss)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
