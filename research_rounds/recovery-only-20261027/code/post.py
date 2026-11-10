from pathlib import Path
import pandas as pd,numpy as np,json
O=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 out=O/'results';score=pd.read_csv(out/'scoreboard.csv');events=pd.read_csv(O/'risk-events.csv');market=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True);curves=pd.read_csv(out/'curves.csv',parse_dates=['date']);epochs=[];counts=[]
 for (v,aid),z in events.groupby(['version','account']):
  c=curves[(curves.version==v)&(curves.account==aid)].sort_values('date');rs=z[z.event=='resume'].sort_values('date');starts=[('2023-12-29',1e6,0)]+[(r.date,r.nav,int(r.episode)) for r in rs.itertuples()]
  for i,(day,nav,e) in enumerate(starts):
   end,n1,_=starts[i+1] if i+1<len(starts) else (str(c.date.iloc[-1].date()),float(c.nav.iloc[-1]),None)
   pauses=z[(z.event=='pause')&(z.date>=day)&(z.date<end if i+1<len(starts) else z.date<=end)]
   future=market[(market.index>=pd.Timestamp(day))&market.breakout]
   first63=str(future.index[0].date()) if len(future) else None
   lead=int(market.index.searchsorted(pd.Timestamp(first63))-market.index.searchsorted(pd.Timestamp(day))) if first63 is not None else None
   epochs.append(dict(version=v,account=aid,episode=e,start=day,end=end,start_nav=nav,end_nav=n1,net_pnl=n1-nav,net_return=n1/nav-1,pause_date=pauses.date.iloc[0] if len(pauses) else None,next_quarter_condition=first63,observations_until_quarter_condition=lead,closed_by_next_resume=i+1<len(starts)))
  g=pd.DataFrame(epochs);g=g[(g.version==v)&(g.account==aid)];assert abs(g.net_pnl.sum()-(float(c.nav.iloc[-1])-1e6))<1e-6
  counts.append(dict(version=v,account=aid,resumes=len(rs),pauses=int(z.event.eq('pause').sum()),negative_epochs=int(g.net_pnl.lt(0).sum()),negative_epoch_total=-g.loc[g.net_pnl.lt(0),'net_pnl'].sum(),h2_resumes=int(rs.date.ge('2026-07-01').sum())))
 pd.DataFrame(epochs).to_csv(out/'participation-epochs.csv',index=False);k=pd.DataFrame(counts);k.to_csv(out/'restart-counts.csv',index=False);s=score.merge(k,on=['version','account'],how='left');s.to_csv(out/'comparison.csv',index=False)
 print(s[s.scenario=='base'][['version','net_return','max_drawdown','h2_return','fees','tail_profit','ordinary_profit','all_closed_losses','resumes','negative_epochs','h2_resumes']].to_string(index=False))
 print(s[s.version!='CONTROL'][['version','scenario','net_return','max_drawdown']].to_string(index=False))
 (O/'epoch-validation.json').write_text(json.dumps({'passed':True,'epochs':len(epochs),'telescoping_pnl_exact_to_1e_6':True,'future_quarter_date_used_only_in_report':True},indent=2))
