from pathlib import Path
import json
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;O=R/'results/v0';s=pd.read_csv(O/'summary.csv');pairs=[];agg=[]
for (role,scenario),z in s.groupby(['role','scenario'],sort=False):
 baseline=z[z.policy=='E0'].set_index('case');sen=z[z.policy=='E2'].set_index('case')
 for p,a in z.groupby('policy',sort=False):
  x=a.set_index('case');ret=x.net_return-baseline.net_return;dd=x.max_drawdown-baseline.max_drawdown
  agg.append(dict(role=role,scenario=scenario,policy=p,cases=len(a),case_mean_return=x.net_return.mean(),case_mean_drawdown=x.max_drawdown.mean(),median_return=x.net_return.median(),exposure_fraction=x.exposure_fraction.mean(),trades=int(x.trades.sum()),natural_trades=int(x.natural_trades.sum()),terminal_trades=int(x.terminal_trades.sum()),pooled_win_rate=float(x.wins.sum()/x.trades.sum()) if x.trades.sum() else None,tail_pnl_case_mean=x.tail_pnl.mean(),ordinary_pnl_case_mean=x.ordinary_pnl.mean(),higher_return_than_E0=int((ret>1e-9).sum()),lower_drawdown_than_E0=int((dd<-1e-9).sum()),both_than_E0=int(((ret>1e-9)&(dd<-1e-9)).sum()),both_than_E2=int(((x.net_return>sen.net_return+1e-9)&(x.max_drawdown<sen.max_drawdown-1e-9)).sum())))
  for case in x.index:pairs.append(dict(case=case,role=role,scenario=scenario,policy=p,return_delta_E0=float(ret[case]),drawdown_delta_E0=float(dd[case])))
pd.DataFrame(agg).to_csv(O/'descriptive-comparison.csv',index=False);pd.DataFrame(pairs).to_csv(O/'paired-deltas.csv',index=False)
# RC supplementary attempts: match legs by entry observation, not by hindsight profit.
attempts=[]
for case in s.case.unique():
 r=pd.read_csv(O/'accounts'/f'{case}__R__base/trades.csv');rc=pd.read_csv(O/'accounts'/f'{case}__RC__base/trades.csv')
 for row in rc[~rc.entry_date.isin(r.entry_date)].to_dict('records'):attempts.append(dict(case=case,**row))
pd.DataFrame(attempts).to_csv(O/'RC-additional-entry-legs.csv',index=False)
# Previous M was only a diagnostic; the new R does not read M or actual E0 fills.
old=R.parent/'market-regimes-exit-20261024/results/v0/accounts/semi_ytd26__M__E2__base'
r=pd.read_csv(O/'accounts/semi_ytd26__R__base/trades.csv');m=pd.read_csv(old/'trades.csv')
for col in ['entry_date','exit_date','entry_price','exit_price','net_return']:
 if col.endswith('date'):assert r[col].tolist()==m[col].tolist()
 else:np.testing.assert_allclose(r[col],m[col],rtol=0,atol=1e-14)
(O/'mechanism.json').write_text(json.dumps({'R_is_causal_shadow_state_not_matched_future_fills':True,'ytd_R_recovers_previous_M_result_without_actual_trade_inputs':True,'R_RC_additional_ytd_trades':3,'R_RC_additional_ytd_returns':[-.056972927844571,.031284148684134,-.058408958101452],'note':'use RC-additional-entry-legs.csv as exact evidence; extra trades change subsequent capital. No summing unweighted trade returns.'},ensure_ascii=False,indent=2))
# Exact fields from the actual records replace rounded narrative values.
me=json.loads((O/'mechanism.json').read_text());me['R_RC_additional_ytd_returns']=[x['net_return'] for x in attempts if x['case']=='semi_ytd26'];(O/'mechanism.json').write_text(json.dumps(me,ensure_ascii=False,indent=2))
print(pd.DataFrame(agg).query("scenario=='base'")[['role','policy','case_mean_return','case_mean_drawdown','exposure_fraction','trades','pooled_win_rate','both_than_E0']].round(4).to_string(index=False))
