"""Same-date admission opportunity contrast; evaluation labels never used for selection."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('results/sector-admission-outcomes')
def label(close,date,h):
 i=close.index.get_indexer([date])[0]
 if i<0 or i+h>=len(close):return None
 path=close.iloc[i+1:i+h+1]/close.iloc[i]-1
 return dict(label_end=str(close.index[i+h].date()),forward_return=float(path.iloc[-1]),mfe=float(path.max()),mae=float(path.min()))
def main():
 OUT.mkdir(exist_ok=True);source=Path('results/sector-admission-audit/events.csv');events=pd.read_csv(source,parse_dates=['date']);root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());records={r['symbol']:r for r in manifest['records']};rows=[];missing=[];hashes={}
 (OUT/'protocol.json').write_text(json.dumps({'horizons':[21,63],'comparison':'selected vs slot_constraints_or_ranking, both pass proxy gate','pairing':['same date','same date and proxy group'],'weights':'equal mean per side per date (or date/group), then equal dates; report all years separately','labels':'Adjusted signal close at signal date to h-th subsequent observed positive-volume close, cutoff2026Oct16','limits':['Not next-open fills or account returns; no trading costs or liquidity.','Allocation constraints depend on previous portfolio history; matched dates do not identify causal ranking effects.','Selected survivor sample and repeated development history.','End-of-sample immature labels excluded, counts reported; 2026 horizon coverage differs.','Proxy groups are correlation associations, not true historical industry constituents.']},indent=2))
 for symbol,g in events.groupby('symbol'):
  rec=records[symbol];p=root/f"{rec['ths_symbol']}-signal.parquet";sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==rec['signal_sha256'];hashes[str(p)]=sha
  f=pd.read_parquet(p);c=f.loc[f.observed_bar&f.volume.gt(0)&(f.index<=pd.Timestamp('2026-10-16')),'signal_close']
  for e in g.to_dict('records'):
   for h in [21,63]:
    x=label(c,e['date'],h)
    if x is None:missing.append(dict(date=str(e['date'].date()),symbol=symbol,horizon=h,reason=e['reason']));continue
    rows.append(dict(**e,horizon=h,**x))
 d=pd.DataFrame(rows);d['tail30']=d.forward_return.ge(.3);d['tail80']=d.forward_return.ge(.8);d['loss30']=d.forward_return.le(-.3);d.to_parquet(OUT/'labels.parquet',index=False);pd.DataFrame(missing).to_csv(OUT/'excluded.csv',index=False)
 allsummary=d.groupby(['year','horizon','reason']).agg(n=('symbol','size'),mean=('forward_return','mean'),median=('forward_return','median'),tail30=('tail30','mean'),tail80=('tail80','mean'),loss30=('loss30','mean')).reset_index();allsummary.to_csv(OUT/'unpaired-summary.csv',index=False)
 pairs=[];chosen=d[d.reason.isin(['selected','slot_constraints_or_ranking'])]
 for mode,keys in [('date',['year','horizon','date']),('date_group',['year','horizon','date','group'])]:
  a=chosen.groupby(keys+['reason']).agg(n=('symbol','size'),mean=('forward_return','mean'),tail30=('tail30','mean'),tail80=('tail80','mean'),loss30=('loss30','mean')).reset_index()
  p=a.pivot(index=keys,columns='reason',values=['mean','tail30','tail80','loss30']).dropna()
  if p.empty:continue
  paired=pd.DataFrame({m:p[m]['selected']-p[m]['slot_constraints_or_ranking'] for m in ['mean','tail30','tail80','loss30']}).reset_index()
  paired.to_csv(OUT/f'{mode}-pairs.csv',index=False)
  # Give each date equal weight even if multiple proxy groups have pairs.
  date=paired.groupby(['year','horizon','date'])[['mean','tail30','tail80','loss30']].mean().reset_index()
  for (y,h),g in date.groupby(['year','horizon']):
   pairs.append(dict(mode=mode,year=int(y),horizon=int(h),dates=len(g),**{m+'_selected_minus_rejected':float(g[m].mean()) for m in ['mean','tail30','tail80','loss30']}))
 pd.DataFrame(pairs).to_csv(OUT/'paired-summary.csv',index=False)
 assert len(rows)+len(missing)==2*len(events)
 report={'status':'development_diagnostic','events':len(events),'labels':len(rows),'excluded':len(missing),'input_hash_checks':len(hashes),'input_hashes':hashes,'event_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'paired':pairs};(OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(pd.DataFrame(pairs).to_string(index=False));print('labels/excluded',len(rows),len(missing))
if __name__=='__main__':main()
