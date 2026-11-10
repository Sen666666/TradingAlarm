"""Descriptive coverage on baseline base-scenario winners, never used as inputs."""
from cp_common import *
def main():
 out=[];windows=[]
 for sector in ['TECH','DRUG']:
  root=O/sector;c=pd.read_csv(root/'analysis/campaigns.csv');daily=rows(root/'accounts-v2/daily.jsonl.gz');dm={}
  for r in daily:dm.setdefault(r['account'],{})[r['at'][:10]]=r
  for base,new in [('ACT','ACP'),('S','SCP'),('SF','SCP'),('SW3F','WCP'),('SAMT','MCP')]:
   old=c[c.account.eq(base+'__S0_base') & c.closed & c.tail_closed];symbols=set(old.symbol);possible=set()
   for _,w in old.iterrows():
    possible.update((w.symbol,d) for d in dm[base+'__S0_base'] if w.entry_at[:10]<=d<w.exit_at[:10])
   for mode in [base,new]:
    for scenario in ['base','cost2','delay1']:
     aid=mode+'__S0_'+scenario;d=dm[aid];held={(sid,day) for sid,day in possible if int(d.get(day,{}).get('positions',{}).get(sid,0))>0}
     q=c[c.account.eq(aid)];negclosed=-q.loc[q.closed & q.net_pnl.lt(0),'net_pnl'].sum();negativeall=-q.loc[q.net_pnl.lt(0),'net_pnl'].sum()
     out.append(dict(sector=sector,reference=base,policy=mode,scenario=scenario,reference_tail_cycles=len(old),reference_tail_stocks=len(symbols),possible_stock_days=len(possible),held_stock_days=len(held),coverage=len(held)/len(possible) if possible else None,fixed_symbols_all_period_net=q.loc[q.symbol.isin(symbols),'net_pnl'].sum(),all_closed_trial_loss=negclosed,all_negative_including_open_marks=negativeall))
     for sid in symbols:
      p={(s,day) for s,day in possible if s==sid};h={(s,day) for s,day in held if s==sid};windows.append(dict(sector=sector,reference=base,policy=mode,scenario=scenario,symbol=sid,possible=len(p),held=len(h)))
 pd.DataFrame(out).to_csv(O/'comparison/fixed-winner-coverage.csv',index=False);pd.DataFrame(windows).to_csv(O/'comparison/fixed-winner-stocks.csv',index=False)
 save(O/'comparison/fixed-winner-definition.json',dict(description='每对旧策略正常组已平仓净收益率>=30%的固定窗口；entry收盘含、exit开盘不含，股票日去重。仅事后描述参照，不是信号或完整市场赢家名单。',positions='实际收盘持股数>0；不按持仓权重加权。',all_losses='负周期净亏已包括实际费用，不能再把全部费用重复扣一次。开放周期负数单列计入全部负数含期末标记。'))
if __name__=='__main__':main()
