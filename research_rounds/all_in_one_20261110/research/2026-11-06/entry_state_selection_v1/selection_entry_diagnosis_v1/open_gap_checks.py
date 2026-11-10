from pathlib import Path
import pandas as pd,numpy as np,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
f=pd.read_csv(O/'ALL_FIRST_ENTRIES.csv');rows=[]
for(a,y),g in f.groupby(['account','year']):
 for rule,m in [('gap_gt_one_prior_sigma',np.log1p(g.entry_gap)>g.sigma20_prior),('highPVR_and_weak',g.PVR_gt85&g.weak_market)]:
  unknown=g.sigma20_prior.isna()if rule.startswith('gap')else g.PVR_decision.isna()
  for side,z in [('removed',g[m&~unknown]),('retained',g[~m&~unknown]),('unknown',g[unknown])]:
   c=z[z.closed_in_entry_year]if y==2022 else z[z.closed]
   rows.append(dict(account=a,year=y,rule=rule,side=side,n=len(z),closed_n=len(c),winrate=c.round_pnl.gt(0).mean(),pnl=c.round_pnl.sum(),ret5=z.ret5_forward.mean(),ret20=z.ret20_forward.mean(),big60=int(z.big60_posthoc.sum()),big60_total=int(g.big60_posthoc.sum())))
pd.DataFrame(rows).to_csv(O/'OPEN_GAP_AND_INTERACTION_DIAGNOSTIC.csv',index=False)
z=f[(f.account=='PVR')&(f.year==2022)&f.closed_in_entry_year]
z.groupby(['quarter','weak_market']).agg(n=('sid','size'),winrate=('round_pnl',lambda x:(x>0).mean()),pnl=('round_pnl','sum'),ret5=('ret5_forward','mean'),ret20=('ret20_forward','mean')).to_csv(O/'2022_CLOSED_QUARTER_WEAK_NONWEAK.csv')
daily=pd.read_csv(O/'FIVE_CASES_DAILY.csv');c=pd.read_csv(O/'FIVE_CASES_ENTRY.csv');cm=c.set_index('sid')
daily['within_selected_round']=[cm.at[s,'entry_day']<=d[:10]<=cm.at[s,'closed_day']for s,d in zip(daily.sid,daily.day)]
daily.to_csv(O/'FIVE_CASES_DAILY.csv',index=False)
print(pd.DataFrame(rows).query("account=='PVR'").to_string(index=False))
