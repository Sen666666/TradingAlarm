from common import *
import gzip

def main():
 out=HERE/'cash-attribution';out.mkdir(exist_ok=False);meta=read(OLD/'inputs-v2/metadata.json');curves=pd.read_csv(ABCD/'analysis/curves.csv');curves=curves[curves.account.eq('A__S0_base')&curves.date.between(START,END)].copy();dates=pd.DatetimeIndex(curves.date);rows=[];gates={}
 for file in (HERE/'sector-states').glob('*.parquet'):
  f=pd.read_parquet(file);v=f.ix_target.where(f.ready).reindex(dates,method='ffill');gates[file.stem]=v
  for d,x in zip(dates,v):rows.append(dict(date=str(d.date()),sector=file.stem,sector_IX=x))
 gs=pd.DataFrame(rows);c=pd.read_csv(ABCD/'analysis/daily-stock-contributions.csv');c=c[c.account.eq('A__S0_base')&c.date.between(START,END)].copy();c['sector']=c.symbol.map(lambda s:meta[s]['sector_id']);c=c.merge(gs,on=['date','sector'],how='left');c['cold_value']=c.market_value.where(c.sector_IX.eq(0),0);c['unknown_value']=c.market_value.where(c.sector_IX.isna(),0);s=c.groupby('date')[['market_value','cold_value','unknown_value']].sum().reset_index().merge(curves[['date','nav']],on='date');s['exposure']=s.market_value/s.nav;s['cold_exposure']=s.cold_value/s.nav;s.to_csv(out/'daily-exposure.csv',index=False)
 obj=read(ABCD/'technical/A-controls/A__S0_base.json');res={r['order_id']:r['decision_at'][:10] for r in obj['audit_log'] if r['kind']=='reserve'};entries={}
 for r in obj['audit_log']:
  if r['kind']=='fill' and r['receipt']['side']=='buy':entries.setdefault((r['receipt']['security_id'],r['receipt']['at']),res[r['order_id']])
 cams=pd.read_csv(ABCD/'analysis/campaigns.csv');cams=cams[cams.account.eq('A__S0_base')&cams.entry_at.str[:10].between(START,END)];er=[]
 for _,r in cams.iterrows():
  day=entries[r.symbol,r.entry_at];v=gates[meta[r.symbol]['sector_id']];i=v.index.searchsorted(pd.Timestamp(day),side='right')-1;val=float(v.iloc[i]) if i>=0 else None;er.append(dict(symbol=r.symbol,name=r['name'],industry=r.industry,decision=day,sector_IX=val,closed_in_window=bool(r.closed and r.exit_at[:10]<=END),net_return=r.net_return,net_pnl=r.net_pnl))
 e=pd.DataFrame(er);e.to_csv(out/'actual-entry-sector-state.csv',index=False);groups=e[e.closed_in_window].groupby('sector_IX').agg(campaigns=('symbol','size'),mean_return=('net_return','mean'),net_pnl=('net_pnl','sum')).reset_index();groups.to_csv(out/'entry-groups.csv',index=False)
 result=dict(mean_old_account_exposure=float(s.exposure.mean()),mean_exposure_while_sector_IX_off=float(s.cold_exposure.mean()),fraction_inventory_value_while_sector_off=float(s.cold_value.sum()/s.market_value.sum()),days_with_cold_sector_holdings=int(s.cold_value.gt(0).sum()),days=len(s),actual_new_entries=len(e),entries_while_sector_off=int(e.sector_IX.eq(0).sum()),closed_groups=groups.to_dict('records'))
 write(out/'summary.json',result);print(result,flush=True)
if __name__=='__main__':main()
