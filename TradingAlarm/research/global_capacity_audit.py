"""Reproduce frozen six-asset baseline and count actual entry constraints."""
import json
from collections import Counter
import pandas as pd
from build_stock_features import ROOT
from campaign_engine import run_campaign
from global_combined_transfer import load_all


def main():
    folder=ROOT/'results/global-combined-provisional';trace=[]
    m,path,orders,closed,state=run_campaign(load_all(),start='2007-01-01',pyramid=False,exit_mode='trend',
        ranking='low_atr',base_currency='USD',settlement_scenario=True,max_positions=6,decision_audit=trace)
    frozen=pd.read_parquet(folder/'noadd-base-path.parquet')
    pd.testing.assert_frame_equal(path,frozen)
    assert orders==json.loads((folder/'noadd-base-orders.json').read_text())
    assert dict(closed=closed,open=state)==json.loads((folder/'noadd-base-campaigns.json').read_text())
    sizing=[r for r in trace if r['event']=='sizing'];counts=Counter();binding=Counter()
    for row in sizing:
        counts['attempts']+=1
        counts['zero' if row['units']==0 else ('partial' if row['units']<row['target_units'] else 'full')]+=1
        # Constraints can tie; report all ties, not mutually exclusive causes.
        for field in ('adv_units','exposure_units','risk_units','cash_units'):
            if row[field]<row['target_units'] and row[field]==row['units']:binding[field]+=1
    flat=[r for r in trace if r['event']=='flat_signal']
    dates=set(path.index.strftime('%Y-%m-%d'));signaldays={r['date'] for r in flat if r['breakout']}
    result=dict(exact_baseline_reproduced=True,entry_sizing=dict(counts),binding_constraints=dict(binding),
        binding_note='Counts include tied binding constraints; repeated requests are not independent opportunities.',
        rejected_reasons=dict(Counter(r['reason'] for r in trace if r['event']=='rejected')),
        sessions=len(dates),sessions_with_flat_asset_breakout=len(signaldays),sessions_without_flat_asset_breakout=len(dates-signaldays),
        risk_limited_while_cash_available=sum(r['risk_units']==r['units'] and r['units']<r['target_units'] and r['cash_units']>=r['target_units'] for r in sizing),
        peak_risk_budget_multiple=max(r['planned_risk_before']/r['planned_risk_limit'] for r in sizing),
        note='Current distance to original stop includes accrued winner gains. Exceeding buying risk limit through price drift does not force exit. No counterfactual trade profitability inferred here.')
    limited=[r for r in sizing if r['risk_units']==r['units'] and r['units']<r['target_units'] and r['cash_units']>=r['target_units']]
    fractions=[];initial_used=[];giveback_counts=Counter()
    for r in limited:
        risks=r['shared_stop_risk_by_symbol'];initial=r['original_atr_risk_by_symbol']
        assert abs(sum(risks.values())-r['planned_risk_before'])<1e-6
        excess={s:max(0,v-initial[s]) for s,v in risks.items()}
        fractions.append(sum(excess.values())/sum(risks.values()) if sum(risks.values()) else 0.)
        initial_used.append(sum(min(v,initial[s]) for s,v in risks.items())/r['planned_risk_limit'])
        if excess:giveback_counts[max(excess,key=excess.get)]+=1
    result['limited_attempt_profit_giveback']=dict(mean_fraction_of_current_stop_risk=float(pd.Series(fractions).mean()),
        median_fraction=float(pd.Series(fractions).median()),median_initial_component_fraction_of_budget=float(pd.Series(initial_used).median()),
        largest_contributor_counts=dict(giveback_counts),definition='max(current_open_to_original_stop_risk - original4ATR_share_risk,0); noadd sharedstop only. Descriptive; releasing this budget still leaves real drawdown risk.')
    (folder/'capacity-audit.json').write_text(json.dumps(result,indent=2));pd.DataFrame(trace).to_parquet(folder/'capacity-trace.parquet',index=False)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
