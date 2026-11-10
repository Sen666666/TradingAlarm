"""Explain sizing effects using independently reconciled saved HK episodes.

Ex-post cash blending is diagnostic only, never a selected trading allocation.
"""
import json
from collections import defaultdict
import pandas as pd
from build_stock_features import ROOT


def main():
    base=ROOT/'results/trend-workbench-initial-protection'
    out=ROOT/'results/trend-workbench-risk-sizing'
    rows=json.loads((out/'results.json').read_text());reports=[]
    components=['local_price_pnl','security_fx_pnl','paid_dividends','unpaid_dividends','dividend_fees','trade_fees']
    for r in rows:
        case=r['case'];control=pd.read_parquet(base/f'{case}-path.parquet');candidate=pd.read_parquet(out/f'{case}-path.parquet')
        pd.testing.assert_index_equal(control.index,candidate.index)
        # Invest constant fraction of initial capital in the complete baseline
        # account, leaving the rest in zero-return cash. Ex-post match the
        # average absolute tradable inventory value, not NAV weight/volatility.
        before=(control.filter(like='w_').sum(axis=1)*control.nav).mean()
        after=(candidate.filter(like='w_').sum(axis=1)*candidate.nav).mean()
        fraction=float(after/before)
        overlay=1+fraction*(control.nav-1)
        dd=overlay/overlay.cummax().clip(lower=1)-1
        report=dict(case=case,expost_baseline_fraction=fraction,
                    cash_blend_return=float(overlay.iloc[-1]-1),cash_blend_mdd=float(dd.min()),
                    candidate_return=r['total_return'],candidate_mdd=r['max_drawdown'],
                    candidate_minus_blend_return=float(candidate.nav.iloc[-1]-overlay.iloc[-1]))
        if r['group']=='hk7':
            old=json.loads((base/f'{case}-episodes.json').read_text());new=json.loads((out/f'{case}-episodes.json').read_text())
            by_symbol=defaultdict(lambda:dict(control=0.,candidate=0.));delta=defaultdict(float)
            for sign,label,episodes in [(-1,'control',old),(1,'candidate',new)]:
                for e in episodes:
                    by_symbol[e['symbol']][label]+=e['pnl']
                    for key in components:delta[key]+=sign*e[key]
            expected=(candidate.nav.iloc[-1]-control.nav.iloc[-1])*1e6
            assert abs(sum(x['candidate']-x['control'] for x in by_symbol.values())-expected)<1e-6
            assert abs(sum(v*(-1 if k.endswith('fees') else 1) for k,v in delta.items())-expected)<1e-6
            report.update(pnl_difference_cny=float(expected),components=dict(delta),symbols=[dict(symbol=s,**v,difference=v['candidate']-v['control']) for s,v in sorted(by_symbol.items())],
                          matched_episode_dates=len({(e['symbol'],e['entry_date'],e['exit_date']) for e in old}&{(e['symbol'],e['entry_date'],e['exit_date']) for e in new}),control_episodes=len(old),candidate_episodes=len(new))
        reports.append(report)
    (out/'sizing-attribution.json').write_text(json.dumps(dict(reports=reports,
        meaning='Cash blend fraction uses full-sample average absolute tradable inventory, hence hindsight mechanism diagnostic only. Not implementable selection, not exact matched volatility, and excludes claim value from exposure matching. HK PNL components include remaining marked claims; fee deltas must be subtracted.'),indent=2)+'\n')
    for r in reports:
        if r['case'].endswith('base'):print(json.dumps(r,indent=2))


if __name__=='__main__':main()
