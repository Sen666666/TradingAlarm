from audit import *

def main():
 out=[];stock=[]
 for c in STARTS:
  root=O/c;cs=pd.read_csv(root/'analysis/campaigns.csv');ds=rows(root/'accounts-v2/daily.jsonl.gz');by={a:[r for r in ds if r['account']==a] for a in cs.account.unique()}
  for scenario in ['base','delay1']+(['cost2'] if c=='S0' else []):
   tails=cs[(cs.account==f'A6__S0_{scenario}')&cs.tail_closed]
   for mode in MODES:
    aid=f'{mode}__S0_{scenario}';rr=by.get(aid,[]);held=eligible=0
    for _,win in tails.iterrows():
     for r in rr:
      if win.entry_at[:10]<=r['at'][:10]<=win.exit_at[:10]:
       eligible+=1;held+=win.symbol in r['positions']
    cc=cs[cs.account==aid];out.append(dict(cohort=c,account=aid,ACT_tail_windows=len(tails),ACT_tail_window_stock_days=eligible,held_in_ACT_tail_windows=held,all_losses=float(-cc.loc[cc.net_pnl<0,'net_pnl'].sum()),all_fees=float((cc.buy_fees+cc.sell_fees).sum())))
    for symbol,group in cc.groupby('symbol'):
     stock.append(dict(cohort=c,account=aid,symbol=symbol,name=group.iloc[0]['name'],net=float(group.net_pnl.sum()),cycles=len(group)))
 pd.DataFrame(out).to_csv(O/'winner-participation.csv',index=False);pd.DataFrame(stock).to_csv(O/'stock-contributions.csv',index=False)
if __name__=='__main__':main()
