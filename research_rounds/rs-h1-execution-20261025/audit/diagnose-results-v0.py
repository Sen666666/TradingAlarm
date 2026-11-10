"""Post-result descriptive contribution attribution; no alternative accounts."""
from pathlib import Path
import collections
import numpy as np,pandas as pd
from build_inputs import HERE,read,write,now
OLD=HERE.parent/'a-share-selection-e0-20261024'
def main():
 out=HERE/'diagnosis';out.mkdir(exist_ok=False)
 z=np.load(HERE/'h1/matrix.npz');days=pd.DatetimeIndex(z['dates']);cols={s:j for j,s in enumerate(z['symbols'])};h=z['h'];score=z['score'];close=z['close']
 oldprofile={(x['account'],x['symbol'],x['first_fill_at'][:10]):x for x in read(OLD/'entry-quality-v2/profiles.json')}
 newprofile={(x['account'],x['symbol'],x['first_fill']):x for x in read(HERE/'audit/filled-order-ranks.json')};rows=[]
 for root,label,profile in [(OLD,'old',oldprofile),(HERE,'new',newprofile)]:
  for c in read(root/'analysis-v2/campaigns.json'):
   if c['account'].startswith('B0'):continue
   p=profile[(c['account'],c['symbol'],c['entry_at'][:10])];date=p['decision_date'];t=days.get_loc(date);j=cols[c['symbol']];horizon=int(h[t,j]);q=close[t,j];start=close[t-horizon,j] if horizon else np.nan
   rows.append(dict(version=label,account=c['account'],symbol=c['symbol'],name=c['name'],industry=c['industry'],entry_at=c['entry_at'],exit_at=c['exit_at'],h=horizon,history_group='h<252' if horizon<252 else 'h=252',score=float(score[t,j]) if np.isfinite(score[t,j]) else None,decision_date=date,net_pnl=float(c['net_pnl']),buy_gross=float(c['buy_gross']),closed=c['closed'],net_return=c['net_return'],source_origin_to_entry_move=float(q/start-1) if np.isfinite(q) and np.isfinite(start) else None,tail_closed=c['tail_closed']))
 f=pd.DataFrame(rows);f.to_csv(out/'history-attribution-campaigns.csv',index=False,encoding='utf-8-sig');summary=[]
 for (version,aid,g),part in f.groupby(['version','account','history_group']):
  cl=part.loc[part.closed];summary.append(dict(version=version,account=aid,history_group=g,campaigns=len(part),unique_stocks=part.symbol.nunique(),net_contribution=float(part.net_pnl.sum()),gross_buys=float(part.buy_gross.sum()),closed_campaigns=len(cl),closed_win_rate=float((cl.net_pnl>0).mean()) if len(cl) else None,closed_tail_pnl=float(cl.loc[cl.tail_closed,'net_pnl'].sum()),ordinary_closed_pnl=float(cl.loc[~cl.tail_closed,'net_pnl'].sum()),median_source_to_entry_move=float(part.source_origin_to_entry_move.median()) if part.source_origin_to_entry_move.notna().any() else None))
 write(out/'history-attribution.json',summary);pd.DataFrame(summary).to_csv(out/'history-attribution.csv',index=False,encoding='utf-8-sig')
 delta=read(HERE/'comparison/actual-stocks-comparison.json');base=[x for x in delta if x['account'].endswith('_base')]
 write(out/'largest-stock-contribution-changes.json',dict(lost=sorted(base,key=lambda x:x['net_contribution_change'])[:24],gained=sorted(base,key=lambda x:-x['net_contribution_change'])[:24]))
 first=read(HERE/'misses-v2/first-opportunity-snapshots.json');ann=[x for x in read(HERE/'comparison/winner-comparison.json') if x['account'].endswith('_base') and x['window_type']=='annual' and x['current_cap_disposition']=='selected' and not x['new_participated']]
 sn={(x['account'],x['key']):x for x in first};examples=[]
 for x in sorted(ann,key=lambda x:-x['price_return']):
  if x['new_reason'] in ['selection_rejected:total_slots_full','selection_rejected:not_top_ranked_sector','selection_rejected:sector_slots_full','selection_rejected:sector_issuer_slots_full']:
   snap=sn.get((x['account'],x['key']));examples.append(dict(**x,first_actionable_snapshot=snap))
  if len(examples)>=32:break
 write(out/'missed-winner-snapshots.json',examples)
 write(out/'summary.json',dict(recorded_at=now(),campaigns_described=len(rows),no_new_accounts=True,notes=['Contribution buckets are descriptive actual allocations, not a counterfactual profit effect of changing RS history or expiry separately.','h is source-age capped252 on the market calendar, not an asserted true IPO age.','Old persistent intents are classified by their original decision day, not eventual fill day.','No trading rule was changed after these results.']))
 print({'history_summary': [x for x in summary if x['account'].endswith('_base')]},flush=True)
if __name__=='__main__':main()
