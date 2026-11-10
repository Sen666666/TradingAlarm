"""Actual first entries versus same-day global sector target ranking."""
from common_abcd import *
import pandas as pd
from analyze_abcd import account_path

def main():
 z=np.load(HERE/'prepared/dual-board.npz');dates=pd.DatetimeIndex(z['dates']);ids=[str(s) for s in z['symbols']];index={s:j for j,s in enumerate(ids)};sectors=[s for s in ids if s.startswith('URFI')];long=z['long'];rank=z['rank'];gate=z['gate'];up=np.zeros((len(dates),len(sectors)),bool);meta=read(OLD/'inputs-v2/metadata.json');prepared=read(OLD/'prepared-v2/manifest.json')
 rec={r['series_id']:r for r in prepared['series']}
 for k,s in enumerate(sectors):
  f=pd.read_parquet(OLD/'prepared-v2'/rec[s]['files']['states']['path'],columns=['target','ready']);q=f.reindex(dates).ffill();up[:,k]=q.ready.eq(1)&q.target.eq(1)
 matrices={}
 for dual in [False,True]:
  matrix=np.full((len(dates),len(sectors)),np.nan)
  for t in range(len(dates)):
   eligible=[s for k,s in enumerate(sectors) if up[t,k] and math.isfinite((rank if dual else long)[t,index[s]]) and (not dual or gate[t,index[s]]==1)]
   eligible.sort(key=lambda s:(-round(float((rank if dual else long)[t,index[s]]),12),s));rr={s:k+1 for k,s in enumerate(eligible)}
   for k,s in enumerate(sectors):matrix[t,k]=rr.get(s,np.nan)
  matrices[dual]=matrix
 sector_index={s:k for k,s in enumerate(sectors)};campaigns=pd.read_csv(HERE/'analysis/campaigns.csv');rows=[]
 for mode in 'ABCD':
  aid=mode+'__S0_base';obj=read(account_path(aid));res={r['order_id']:r['decision_at'][:10] for r in obj['audit_log'] if r['kind']=='reserve'};first={}
  for r in obj['audit_log']:
   if r['kind']=='fill' and r['receipt']['side']=='buy':first.setdefault((r['receipt']['security_id'],r['receipt']['at']),res[r['order_id']])
  for _,c in campaigns[campaigns.account.eq(aid)].iterrows():
   day=first[c.symbol,c.entry_at];t=dates.get_loc(day);sector=meta[c.symbol]['sector_id'];r=matrices[mode in ['B','D']][t,sector_index[sector]]
   rows.append(dict(account=aid,scheme=mode,symbol=c.symbol,name=c['name'],decision_day=day,entry_at=c.entry_at,sector=sector,industry=c.industry,global_comparable_sector_rank=float(r) if math.isfinite(r) else None,sector_outside_global_top3=bool(r>3) if math.isfinite(r) else None,net_pnl=c.net_pnl,closed=c.closed))
 pd.DataFrame(rows).to_csv(HERE/'diagnostics/actual-entry-sector-ranks.csv',index=False);write(HERE/'diagnostics/actual-entry-sector-ranks.json',rows)
 f=pd.DataFrame(rows);s=f.groupby('scheme').agg(first_campaign_entries=('symbol','size'),outside_global_top3=('sector_outside_global_top3','sum'),median_global_sector_rank=('global_comparable_sector_rank','median')).reset_index();s.to_csv(HERE/'diagnostics/entry-rank-alignment-summary.csv',index=False);print(s.to_string(index=False),flush=True)
if __name__=='__main__':main()
