"""Metadata source-boundary slices of the original full-H1 output, not new windows."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 before=sha(O/'DAILY_STATES.parquet');d=pd.read_parquet(O/'DAILY_STATES.parquet');h=d[d.window.eq('2026H1')].copy()
 h['source_period']=np.where(h.day.le('2026-05-15'),'2026_01_01_TO_05_15','2026_05_18_TO_06_30')
 rows=[]
 for (period,sid),g in h.groupby(['source_period','sid']):
  rows.append(dict(source_period=period,sid=sid,days=len(g),price_known=int(g.valid.sum()),amount_known=int(g.amount_valid.sum()),births=int(g.born.sum()),birth_confirmed=int((g.born&g.phase.eq('CONFIRMED')).sum()),birth_probe=int((g.born&g.phase.eq('PROBE')).sum()),birth_amount_unknown=int((g.born&g.phase.eq('PROBE_AMOUNT_UNKNOWN')).sum()),receipts=int(g.receipt.sum()),root_unknown=int(g.root_unknown.sum()),root_unknown_valid_price=int((g.root_unknown&g.valid).sum()),price_failures=int(g.failed.sum()),active_days=int(g.active.sum())))
 c=pd.DataFrame(rows);c.to_csv(O/'SOURCE_BOUNDARY_2026_STOCK_COVERAGE.csv',index=False)
 s=c.groupby('source_period').agg(stocks=('sid','size'),price_known_stocks=('price_known',lambda v:int((v>0).sum())),days_per_stock=('days','first'),stock_days=('days','sum'),price_known=('price_known','sum'),amount_known=('amount_known','sum'),births=('births','sum'),birth_confirmed=('birth_confirmed','sum'),birth_probe=('birth_probe','sum'),birth_amount_unknown=('birth_amount_unknown','sum'),receipts=('receipts','sum'),root_unknown=('root_unknown','sum'),root_unknown_valid_price=('root_unknown_valid_price','sum'),price_failures=('price_failures','sum'),active_days=('active_days','sum')).reset_index();s.to_csv(O/'SOURCE_BOUNDARY_2026_SUMMARY.csv',index=False)
 a=h[h.day.eq('2026-05-15')].set_index('sid');b=h[h.day.eq('2026-05-18')].set_index('sid');assert a.index.equals(b.index)
 z=pd.DataFrame(index=a.index);z['valid_before']=a.valid;z['valid_after']=b.valid;z['both_price_known']=a.valid&b.valid
 for field in ['source_kind','source_path','segment_id','identity','adjustment_factor']:
  z[field+'_before']=a[field];z[field+'_after']=b[field]
 for field in ['source_kind','source_path','segment_id','identity']:
  z[field+'_changed']=pd.Series(pd.NA,index=z.index,dtype='boolean');known=z.both_price_known;z.loc[known,field+'_changed']=a.loc[known,field].ne(b.loc[known,field])
 z['factor_continuous']=pd.Series(pd.NA,index=z.index,dtype='boolean');z.loc[z.both_price_known,'factor_continuous']=np.isclose(a.loc[z.both_price_known,'adjustment_factor'],b.loc[z.both_price_known,'adjustment_factor'],rtol=1e-11)
 z['root_active_before']=a.active;z['root_day_before']=a.root_day;z['root_unknown_after']=b.root_unknown;z['root_day_after']=b.root_day;z.reset_index().to_csv(O/'SOURCE_BOUNDARY_20260518_IDENTITY.csv',index=False)
 data=dict(both_price_known=int(z.both_price_known.sum()),source_kind_changed=int(z.source_kind_changed.fillna(False).sum()),source_path_changed=int(z.source_path_changed.fillna(False).sum()),segment_id_changed=int(z.segment_id_changed.fillna(False).sum()),full_identity_changed=int(z.identity_changed.fillna(False).sum()),factor_continuous_among_both_known=int(z.factor_continuous.fillna(False).sum()),root_unknown_after=int(z.root_unknown_after.sum()),price_known_root_unknown_after=int((z.root_unknown_after&z.valid_after).sum()),changed_identity_with_continuous_factor=int((z.identity_changed.fillna(False)&z.factor_continuous.fillna(False)).sum()),no_market_recompute=True,original_full_H1_retained=True,not_trend_regime_labels=True,identity_definition='source_kind|source_path|segment_id; factor continuity never overrides source quarantine',input_sha256=before)
 assert before==sha(O/'DAILY_STATES.parquet');assert int(s.receipts.sum())==int(h.receipt.sum());assert int(s.births.sum())==int(h.born.sum());assert int(s.root_unknown.sum())==int(h.root_unknown.sum())
 (O/'SOURCE_BOUNDARY_2026_QA.json').write_text(json.dumps(data,indent=2));print(s.to_string(index=False));print(json.dumps(data))
if __name__=='__main__':main()
