from common_abcd import *
import pandas as pd
from analyze_abcd import account_path

def main():
 f=pd.read_csv(HERE/'analysis/campaigns.csv');rows=[];causes=[]
 for mode in 'ABCD':
  aid=mode+'__S0_base';obj=read(account_path(aid));rot={(e['at'],sid) for e in obj['audit_log'] if e['kind']=='portfolio_rotation_request' for sid in e['outgoing_stocks']};requests={e['event_id']:(e['at'],e['sid']) for e in obj['audit_log'] if e['kind']=='exit_request'};exitcause={}
  for e in obj['audit_log']:
   if e['kind']=='fill' and e['receipt']['side']=='sell':exitcause[e['receipt']['security_id'],e['receipt']['at']]='portfolio_rotation' if requests[e['order_id']] in rot else 'original_IX'
  g=f[f.account.eq(aid)&f.closed].copy();g['exit_cause']=[exitcause[s,t] for s,t in zip(g.symbol,g.exit_at)]
  rows.append(dict(scheme=mode,closed=len(g),mean_closed_return=g.net_return.mean(),median_closed_return=g.net_return.median(),mean_profitable_return=g.loc[g.net_pnl>0,'net_return'].mean(),mean_losing_return=g.loc[g.net_pnl<0,'net_return'].mean(),profit_factor=g.loc[g.net_pnl>0,'net_pnl'].sum()/-g.loc[g.net_pnl<0,'net_pnl'].sum(),closed_tail_count=int(g.tail_closed.sum()),unweighted_selected_closed_sample_only=True))
  for cause,c in g.groupby('exit_cause'):causes.append(dict(scheme=mode,exit_cause=cause,closed=len(c),win_rate=(c.net_pnl>0).mean(),mean_closed_return=c.net_return.mean(),net_pnl=c.net_pnl.sum(),tail_count=int(c.tail_closed.sum())))
 pd.DataFrame(rows).to_csv(HERE/'diagnostics/closed-cycle-quality.csv',index=False);write(HERE/'diagnostics/closed-cycle-quality.json',rows);pd.DataFrame(causes).to_csv(HERE/'diagnostics/closed-cycle-exit-causes.csv',index=False);write(HERE/'diagnostics/closed-cycle-exit-causes.json',causes);print(pd.DataFrame(rows).to_string(index=False),flush=True)
if __name__=='__main__':main()
