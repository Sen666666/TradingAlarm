from collect import *
if __name__=='__main__':
 periods=pd.read_csv(O/'periods.csv');out=[];worst=[];sent=[]
 for label,root in PATHS:
  c=pd.read_csv(root/'analysis/campaigns.csv');c=c[c.account=='I__S0_base'].copy();new=c[c.entry_at.str[:10]>='2026-07-01'];h2=periods[(periods.version==label)&(periods.account=='I__S0_base')&(periods.period=='2026H2')].iloc[0]
  out.append(dict(version=label,h2_pnl=h2.pnl,new_campaigns=len(new),new_campaign_pnl=float(new.net_pnl.sum()),new_campaign_losses=int((new.net_pnl<0).sum()),carried_h2_pnl=float(h2.pnl-new.net_pnl.sum()),h2_exposure=h2.mean_exposure))
  x=pd.read_csv(root/'analysis/contributions.csv');x=x[(x.account=='I__S0_base')&(x.date>='2026-07-01')];group=x.groupby('symbol').net_contribution.sum().sort_values()
  for sid,v in group.head(10).items():worst.append(dict(version=label,symbol=sid,h2_contribution=v))
  for sid in ['688498.SH','300308.SZ','300502.SZ','688256.SH','001309.SZ','688195.SH']:
   q=c[c.symbol==sid];sent.append(dict(version=label,symbol=sid,net_pnl=float(q.net_pnl.sum()),campaigns=len(q),first_entry=q.entry_at.min() if len(q) else '',last_exit=q.exit_at.dropna().max() if len(q.exit_at.dropna()) else ''))
 pd.DataFrame(out).to_csv(O/'h2-attribution.csv',index=False);pd.DataFrame(worst).to_csv(O/'h2-worst-stocks.csv',index=False);pd.DataFrame(sent).to_csv(O/'winner-participation.csv',index=False);print(pd.DataFrame(out).to_string(index=False))
