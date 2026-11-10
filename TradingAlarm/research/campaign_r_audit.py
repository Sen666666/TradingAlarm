"""Risk-normalize frozen campaigns, including open inventory; never refit signals."""
import json
import math
import argparse
import numpy as np
import pandas as pd
from hk_extension import load_extended
from campaign_engine import features
from trend_tail_audit import SOURCE, OUT


def economics(rows, denominator):
    values = pd.Series([r['pnl'] / r[denominator] for r in rows], dtype=float)
    wins, losses = values[values > 0], values[values < 0]
    tail = values.nlargest(max(1, math.ceil(len(values) * .1)))
    return dict(count=len(values), mean_R=float(values.mean()) if len(values) else None,
                mean_win_R=float(wins.mean()) if len(wins) else None, mean_loss_R=float(losses.mean()) if len(losses) else None,
                payoff=float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else None,
                sum_R=float(values.sum()), top10_R=float(tail.sum()),
                remainder_R=float(values.drop(tail.index).sum()))


def main(source=SOURCE, out=OUT, assets_override=None):
    assets = assets_override if assets_override is not None else load_extended()[0]
    fs = {name: features(a) for name, a in assets.items()}
    results, details = [], []
    for metric in json.loads((source / 'results.json').read_text()):
        case = metric['case']
        states = json.loads((source / f'{case}-campaigns.json').read_text())
        orders = json.loads((source / f'{case}-orders.json').read_text())
        path = pd.read_csv(source / f'{case}-path.csv')
        last = path.iloc[-1]
        rows = []
        campaigns = [(s, False) for s in states['closed']]
        campaigns += [(dict(s, symbol=n), True) for n, s in states['open'].items()]
        for s, is_open in campaigns:
            buys = [o for o in orders if o['campaign_id'] == s['id'] and o['units'] > 0]
            assert buys[0]['type'] == 'entry'
            risks = []
            for o in buys:
                f = fs[o['symbol']]
                atr = float(f.loc[:o['signal_date']].iloc[-1].atr)
                factor = float(f.loc[o['date'], 'factor'])
                if o['type']=='complete':
                    adjusted=o['raw_open']*factor+float(f.loc[o['date'],'cash_adjustment'])
                    risks.append(o['units']*(adjusted-o['stop'])/factor*o['fx'])
                else:
                    risks.append(o['units'] * 4 * atr / factor * o['fx'])
            assert np.isclose(s['entry_atr'], fs[s['symbol']].loc[:buys[0]['signal_date']].iloc[-1].atr)
            assert all(r > 0 for r in risks)
            if 'committed_risk' in s:
                assert np.isclose(sum(risks),s['committed_risk'])
                assert sum(risks)<=s['completion_budget']+1e-6
            mark = float(last['w_' + s['symbol']] * last.nav * 1_000_000) if is_open else 0.
            pnl = mark + s['sell_cash'] + s['dividend_claims'] - s['buy_cash']
            if not is_open:
                assert np.isclose(pnl, s['pnl'])
            rows.append(dict(case=case, id=s['id'], symbol=s['symbol'], open=is_open,
                             pnl=pnl, initial_R_cash=risks[0], layer_R_cash=sum(risks),
                             initial_share_of_layer_risk=risks[0]/sum(risks),
                             layers=len(buys), terminal_inventory_value=mark))
        closed = [r for r in rows if not r['open']]
        closed_pnl = sum(r['pnl'] for r in closed)
        open_pnl = sum(r['pnl'] for r in rows if r['open'])
        account_pnl = float((last.nav - 1) * 1_000_000)
        result = dict(case=case, closed_initial=economics(closed, 'initial_R_cash'),
                      all_initial=economics(rows, 'initial_R_cash'),
                      all_layer=economics(rows, 'layer_R_cash'), closed_pnl=closed_pnl,
                      open_marked_pnl=open_pnl, account_pnl=account_pnl,
                      min_initial_share_of_layer_risk=min((r['initial_share_of_layer_risk'] for r in rows), default=None),
                      reconciliation_residual=account_pnl-closed_pnl-open_pnl,
                      terminal_date=str(last.date))
        if 'security_claim_value' in path:
            claim_value=float(last.security_claim_value+last.claim_dividend_receivable+last.claim_dividend_cash_paid)
            result['separate_security_claim_value_and_income']=claim_value
            result['residual_after_security_claims']=result['reconciliation_residual']-claim_value
            result['campaign_payoff_caveat']='Parent campaigns exclude retained recipient-share claims and their dividends; account includes these separately. Parent closed status does not mean all related economic exposure ended.'
        results.append(result)
        details.extend(rows)
    out.mkdir(exist_ok=True)
    (out / 'risk-normalized.json').write_text(json.dumps(dict(
        definitions={
            'initial_R_cash': 'First entry shares * four signal-date ATR / fill-date split factor * fill FX; excludes fees, not guaranteed maximum loss.',
            'layer_R_cash': 'Sum of analogous entry/add risk budgets; completion buys instead use actual fill-to-original-stop distance with fill FX/factor. Not simultaneous account risk.',
            'open': 'Terminal market value plus proceeds and dividend claims minus purchases; unrealized and censored.',
            'R_sum': 'Descriptive sum of campaign risk multiples, not account return.',
            'initial_R_caveat': 'Small partial initial entries followed by much larger adds can dominate initial-R means. Inspect initial_share_of_layer_risk; do not interpret as fixed-risk trade expectancy.',
            'residual': 'Account PnL minus campaign PnL; ex-date versus payment-date FX and dividend FX fees are not allocated in original campaign records.',
            'tail': 'Ex-post highest 10% R campaigns, diagnostic only; no new strategy selection.'},
        results=results, campaigns=details), indent=2))
    for r in results:
        print(r['case'], json.dumps({k:v for k,v in r.items() if k!='case'}))


if __name__ == '__main__':
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    main(args.source, args.out)
