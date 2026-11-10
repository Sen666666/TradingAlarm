from audit import *
def main():
 out=[];diff=[];events=[]
 for c in STARTS:
  root=O/c;cs=pd.read_csv(root/'analysis/campaigns.csv')
  for aid,g in cs.groupby('account'):
   for sid,gg in g.groupby('symbol'):out.append(dict(cohort=c,account=aid,symbol=sid,name=gg.iloc[0]['name'],net=float(gg.net_pnl.sum()),cycles=len(gg)))
   a=read(root/'accounts-v2'/f'{aid}.json')
   for r in a['audit_log']:
    if r['kind']=='fast_support_exit':events.append(dict(cohort=c,account=aid,**r))
  for sc in ['base','delay1']+(['cost2'] if c=='S0' else []):
   sf=cs[cs.account==f'SF__S0_{sc}'].groupby('symbol').net_pnl.sum()
   for ref in ['ACT','S','F']:
    rr=cs[cs.account==f'{ref}__S0_{sc}'].groupby('symbol').net_pnl.sum();delta=sf.subtract(rr,fill_value=0)
    for sid,n in delta.items():diff.append(dict(cohort=c,scenario=sc,reference=ref,symbol=sid,delta=float(n),sf_net=float(sf.get(sid,0)),ref_net=float(rr.get(sid,0))))
 pd.DataFrame(out).to_csv(O/'stock-contributions.csv',index=False);pd.DataFrame(diff).to_csv(O/'paired-stock-differences.csv',index=False);pd.DataFrame(events).to_csv(O/'fast-exits.csv',index=False)
 summary=pd.read_csv(O/'summary.csv')
 for c in STARTS:
  for sc in ['base','delay1']+(['cost2'] if c=='S0' else []):
   for ref in ['ACT','S','F']:
    d=sum(r['delta'] for r in diff if r['cohort']==c and r['scenario']==sc and r['reference']==ref);ss=summary[(summary.cohort==c)&(summary.scenario==sc)].set_index('policy');assert abs(d-(ss.loc['SF','net_profit']-ss.loc[ref,'net_profit']))<.01
 save(O/'attribution-verification.json',{'passed':True,'paired_stock_sums':21})
if __name__=='__main__':main()
