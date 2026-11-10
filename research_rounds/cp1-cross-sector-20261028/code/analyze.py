from cp_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
PAIRS=[('ACT','ACP'),('S','SCP'),('SF','SCP'),('SW3F','WCP'),('SAMT','MCP')]
def main():
 out=O/'comparison';out.mkdir(exist_ok=False);summaries=[];pairs=[];matches=[];stocks=[];curves=[];risk_events=[]
 for sector in ['TECH','DRUG']:
  root=O/sector;ss=pd.read_csv(root/'analysis/summary.csv');ss['sector']=sector
  cc=pd.read_csv(root/'analysis/campaigns.csv');st=pd.read_csv(root/'analysis/stocks.csv');st['sector']=sector;stocks.append(st)
  cv=pd.read_csv(root/'analysis/curves.csv');cv['sector']=sector;curves.append(cv)
  daily={}
  for r in rows(root/'accounts-v2/daily.jsonl.gz'):daily.setdefault(r['account'],[]).append(r)
  sessions=sorted({r['at'][:10] for ds in daily.values() for r in ds})
  def duration(a,b):return sum(str(a)[:10]<=d<str(b)[:10] for d in sessions)
  extras=[]
  for _,s in ss.iterrows():
   aid=s.account;ds=daily[aid];obj=read(root/'accounts-v2'/f'{aid}.json');log=obj['audit_log'];campaign=cc[cc.account.eq(aid)]
   lengths=[duration(c.entry_at,c.exit_at if pd.notna(c.exit_at) else END) for _,c in campaign.iterrows()]
   closes=[duration(c.entry_at,c.exit_at) for _,c in campaign[campaign.closed].iterrows()]
   cps=[r for r in log if r['kind']=='cp_checkpoint']
   extra=dict(account=aid,holding_stock_days=sum(sum(int(q)>0 for q in d['positions'].values()) for d in ds),exposure_days=sum(float(d['inventory'])/float(d['nav']) for d in ds),mean_cash_ratio=sum(float(d['available'])/float(d['nav']) for d in ds)/len(ds),mean_elapsed_observations=float(np.mean(lengths)) if lengths else 0,median_closed_observations=float(np.median(closes)) if closes else 0,cp_raise_events=sum(r['raised_by_cp'] for r in cps),cp_trigger_events=sum(r['reason']=='CP' for r in cps),pause_events=sum(r['kind']=='risk_checkpoint' and r['event']=='pause' for r in log),resume_events=sum(r['kind']=='risk_checkpoint' and r['event']=='resume' for r in log))
   extras.append(extra)
   for r in log:
    if r['kind']=='risk_checkpoint' and r['event'] in ['pause','resume']:risk_events.append(dict(sector=sector,account=aid,**r))
  ss=ss.merge(pd.DataFrame(extras),on='account',validate='one_to_one');summaries.append(ss)
  for base,new in PAIRS:
   for stress in ['base','cost2','delay1']:
    b=ss[ss.policy.eq(base)&ss.scenario.eq(stress)].iloc[0];n=ss[ss.policy.eq(new)&ss.scenario.eq(stress)].iloc[0]
    result=dict(sector=sector,baseline=base,candidate=new,scenario=stress)
    for k in ['net_return','max_drawdown','net_profit','tail_profit','ordinary_profit','all_closed_losses','fees','mean_exposure','holding_stock_days','exposure_days','closed','open']:
     result['baseline_'+k]=b[k];result['candidate_'+k]=n[k];result['delta_'+k]=n[k]-b[k]
    bd,nd=daily[b.account],daily[n.account];fields=['nav','inventory','positions','pending_buys','pending_sells'];different=[u['at'][:10] for u,v in zip(bd,nd) if any(u[k]!=v[k] for k in fields)];result['first_economic_difference']=different[0] if different else None
    pairs.append(result)
    bc=cc[cc.account.eq(b.account)];nc=cc[cc.account.eq(n.account)];joint=bc.merge(nc,on=['symbol','entry_at'],suffixes=('_base','_cp'),validate='one_to_one')
    newobj=read(root/'accounts-v2'/f'{n.account}.json')
    for _,c in joint.iterrows():
     be=c.exit_at_base if pd.notna(c.exit_at_base) else END+' 15:10:00+08:00';ne=c.exit_at_cp if pd.notna(c.exit_at_cp) else END+' 15:10:00+08:00'
     onward=[f for f in newobj['fills'] if f['side']=='buy' and pd.Timestamp(ne)<pd.Timestamp(f['at'])<pd.Timestamp(be)]
     matches.append(dict(sector=sector,baseline=base,candidate=new,scenario=stress,symbol=c.symbol,name=c.name_base,entry_at=c.entry_at,baseline_exit=c.exit_at_base,candidate_exit=c.exit_at_cp,baseline_net=float(c.net_pnl_base),candidate_net=float(c.net_pnl_cp),baseline_trade_return=c.net_return_base,candidate_trade_return=c.net_return_cp,baseline_observations=duration(c.entry_at,be),candidate_observations=duration(c.entry_at,ne),actual_buys_in_released_interval=len(onward),actual_symbols_in_interval=';'.join(sorted({f['security_id'] for f in onward}))))
 allsummary=pd.concat(summaries);allstocks=pd.concat(stocks);allcurves=pd.concat(curves)
 for name,df in [('summary',allsummary),('pairs',pd.DataFrame(pairs)),('same-entry-cycles',pd.DataFrame(matches)),('stocks',allstocks),('curves',allcurves),('risk-events',pd.DataFrame(risk_events))]:df.to_csv(out/f'{name}.csv',index=False)
 fig,axes=plt.subplots(2,2,figsize=(17,11))
 colors=dict(ACT='#888888',S='#1756a9',SF='#45a580',SW3F='#be9830',SAMT='#a373ad',ACP='#333333',SCP='#e83a24',WCP='#e99116',MCP='#b82a93')
 for row,sector in enumerate(['TECH','DRUG']):
  for mode in MODES:
   q=allcurves[allcurves.sector.eq(sector)&allcurves.policy.eq(mode)&allcurves.scenario.eq('base')]
   for col,k in enumerate(['nav','drawdown']):axes[row,col].plot(pd.to_datetime(q.date),q[k]/1e6 if k=='nav' else q[k]*100,label=mode,color=colors[mode],linestyle='-' if mode in CPS else '--',linewidth=1.3)
  axes[row,0].set_title(sector+' NAV (CNY million)');axes[row,1].set_title(sector+' drawdown (%)');axes[row,0].legend(ncol=3,fontsize=9);axes[row,1].legend(ncol=3,fontsize=9)
 fig.tight_layout();fig.savefig(out/'curves.png',dpi=120);plt.close(fig)
 print(allsummary[['sector','policy','scenario','net_return','max_drawdown','mean_exposure','tail_profit','all_closed_losses']].to_string(index=False),flush=True)
if __name__=='__main__':main()
