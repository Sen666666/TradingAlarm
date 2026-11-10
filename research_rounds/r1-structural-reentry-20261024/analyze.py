from pathlib import Path
import json,math
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';O=R/'results/v0';s=pd.read_csv(O/'comparison.csv');t=pd.read_csv(O/'R1-trades-with-provenance.csv');aggregate=[];pairs=[];factors=[]
for (role,sc),z in s.groupby(['role','scenario'],sort=False):
 bases={p:z[z.policy==p].set_index('case') for p in ['E0','R','E2','HOLD']}
 for p,g in z.groupby('policy',sort=False):
  a=g.set_index('case');r=bases['R'];e=bases['E0'];aggregate.append(dict(role=role,scenario=sc,policy=p,cases=len(g),case_mean_return=float(a.net_return.mean()),case_mean_drawdown=float(a.max_drawdown.mean()),case_mean_capital_exposure=float(a.mean_capital_exposure.mean()),case_mean_held_fraction=float(a.exposure_fraction.mean()),trades=int(a.trades.sum()),natural_trades=int(a.natural_trades.sum()),terminal_trades=int(a.terminal_trades.sum()),pooled_win_rate=float(a.wins.sum()/a.trades.sum()),tail_pnl_case_mean=float(a.tail_pnl.mean()),ordinary_pnl_case_mean=float(a.ordinary_pnl.mean()),higher_return_than_R=int((a.net_return>r.net_return+1e-10).sum()),lower_drawdown_than_R=int((a.max_drawdown<r.max_drawdown-1e-10).sum()),both_than_R=int(((a.net_return>r.net_return+1e-10)&(a.max_drawdown<r.max_drawdown-1e-10)).sum()),higher_return_than_E0=int((a.net_return>e.net_return+1e-10).sum()),both_than_E0=int(((a.net_return>e.net_return+1e-10)&(a.max_drawdown<e.max_drawdown-1e-10)).sum())))
for (case,sc),z in s.groupby(['case','scenario'],sort=False):
 a=z.set_index('policy');rr=t[(t.case==case)&(t.scenario==sc)];extra=rr[rr.qualification=='higher_trough_reentry'];common=rr[rr.qualification!='higher_trough_reentry'];old=pd.read_csv(P/'results/v0/accounts'/f'{case}__R__{sc}/trades.csv')
 same=len(common)==len(old) and common.entry_date.tolist()==old.entry_date.tolist() and common.exit_date.tolist()==old.exit_date.tolist()
 if same:
  same=np.allclose(common.net_return,old.net_return,rtol=0,atol=1e-13) and np.allclose(common.entry_price,old.entry_price,rtol=0,atol=1e-13) and np.allclose(common.exit_price,old.exit_price,rtol=0,atol=1e-13)
 factor=float(np.prod(1+extra.net_return));identity_error=abs((1+a.loc['R','net_return'])*factor-(1+a.loc['R1','net_return'])) if same else None
 if same:assert identity_error<1e-11
 factors.append(dict(case=case,scenario=sc,common_R_trades_unchanged=bool(same),recovery_trades=len(extra),recovery_wins=int(extra.net_return.gt(0).sum()),recovery_compound_factor=factor,net_return_R=float(a.loc['R','net_return']),net_return_R1=float(a.loc['R1','net_return']),factor_identity_error=identity_error))
 pairs.append(dict(case=case,role=a.role.iloc[0],scenario=sc,return_delta_vs_R=float(a.loc['R1','net_return']-a.loc['R','net_return']),drawdown_delta_vs_R=float(a.loc['R1','max_drawdown']-a.loc['R','max_drawdown']),return_delta_vs_E0=float(a.loc['R1','net_return']-a.loc['E0','net_return']),drawdown_delta_vs_E0=float(a.loc['R1','max_drawdown']-a.loc['E0','max_drawdown'])))
pd.DataFrame(aggregate).to_csv(O/'descriptive-summary.csv',index=False);pd.DataFrame(pairs).to_csv(O/'paired-deltas.csv',index=False);pd.DataFrame(factors).to_csv(O/'recovery-factor-decomposition.csv',index=False)
# Trace the studied 2024-25 E0 cycle without restarting a new account.
g=t[(t.case=='continuous_USHJ518880')&(t.scenario=='base')&(t.entry_date>='2024-08-20')&(t.entry_date<='2025-10-23')];gold_cycle=dict(entry='2024-08-20',original_E0_exit='2025-10-23',R1_trades=len(g),R1_recoveries=int(g.qualification.eq('higher_trough_reentry').sum()),compounded_return=float(np.prod(1+g.net_return)-1),max_single_trade_return=float(g.net_return.max()),note='descriptive chain within previously identified E0 cycle; no account reset, no future label used as signal')
g.to_csv(O/'gold-2024-25-cycle-trades.csv',index=False);(O/'gold-cycle.json').write_text(json.dumps(gold_cycle,ensure_ascii=False,indent=2))
# Are the higher-support checks independently selective on real wait events?
rejects=[]
for c in json.loads((R/'cases.json').read_text()):
 state=pd.read_parquet(R/'prepared'/c['id']/'R1.parquet')
 for dt,row in state[state.recovery_rejection.ne('')].iterrows():rejects.append(dict(case=c['id'],recognized=str(dt.date()),exit_signal=row.recovery_exit_signal,pivot_date=row.confirmed_pivot_date,pivot=row.confirmed_pivot_price,anchor=row.recovery_anchor_floor,reason=row.recovery_rejection))
pd.DataFrame(rejects).to_csv(O/'rejected-recovery-events.csv',index=False)
result=dict(common_R_factors_exact_cases=int(pd.DataFrame(factors).common_R_trades_unchanged.sum()),total_cases=54,gold_studied_cycle=gold_cycle,base_recovery_trades=int(t[(t.scenario=='base')&t.qualification.eq('higher_trough_reentry')].shape[0]),base_recovery_wins=int(t[(t.scenario=='base')&t.qualification.eq('higher_trough_reentry')].net_return.gt(0).sum()),higher_support_only_rejections=sum(x['reason']=='trough_not_higher_than_exit_support' for x in rejects),no_parameter_changes=True)
(O/'mechanism.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2));print(pd.DataFrame(aggregate).query("scenario=='base'").round(4).to_string(index=False))
