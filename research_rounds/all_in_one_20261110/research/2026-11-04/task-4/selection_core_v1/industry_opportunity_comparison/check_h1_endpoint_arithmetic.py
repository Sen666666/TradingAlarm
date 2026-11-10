"""Ten preselected H1 formulas from saved npz scalars, not a new H1 export/reference rank."""
from pathlib import Path
import numpy as np,pandas as pd,json,hashlib
O=Path(__file__).resolve().parent;P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');z=np.load(P);dates=pd.DatetimeIndex(z['dates']);sy=z['symbols'].astype(str);col={s:j for j,s in enumerate(sy)}
C=z['close'];SEG=z['segment'];H=z['h'];R=z['raw'];S=z['score'];N=z['nref'];OB=z['obs_count']
cases=[('2024-09-24','URFI881129','通信设备'),('2024-09-24','URFI881272','软件开发'),('2024-09-24','002583.SZ','海能达'),('2024-09-24','300085.SZ','银之杰'),('2026-01-15','URFI881121','半导体'),('2026-01-15','300666.SZ','江丰电子'),('2026-01-15','301611.SZ','珂玛科技'),('2026-01-15','603061.SH','金海通'),('2022-01-24','URFI881153','房地产'),('2022-01-24','000620.SZ','盈新发展')]
rows=[];terms=[]
for d,s,name in cases:
 t=int(dates.get_indexer([d])[0]);j=col[s];h=int(H[t,j]);lags=np.minimum(np.arange(5)*63,h);ep=[]
 for k,b in enumerate(lags):
  q=t-int(b);ep.append({'endpoint':k,'lag_common_sessions':int(b),'date':str(dates[q].date()),'close':float(C[q,j]),'source_segment':float(SEG[q,j])})
 term=[];summed=0.
 for k,w in enumerate([.4,.2,.2,.2],1):
  ret=ep[k-1]['close']/ep[k]['close']-1.;v=w*ret if lags[k-1]!=lags[k] else 0.;summed+=v
  tr={'date':d,'symbol':s,'name':name,'h':h,'term':k,'weight':w,'near_date':ep[k-1]['date'],'far_date':ep[k]['date'],'near_lag':int(lags[k-1]),'far_lag':int(lags[k]),'near_close':ep[k-1]['close'],'far_close':ep[k]['close'],'simple_return':ret,'weighted_term':v};term.append(tr);terms.append(tr)
 rounded=float(np.round(summed,12));cached=float(R[t,j]);rows.append({'date':d,'symbol':s,'name':name,'h':h,'observation_count':int(OB[t,j]),'endpoints':ep,'four_terms':term,'sum_unrounded':summed,'numpy_round12':rounded,'cached_raw':cached,'round12_exact_cache_raw':rounded==cached,'difference_after_round12':rounded-cached,'cached_Nref':int(N[t,j]),'cached_H1_percentile_score':float(S[t,j]),'score_reference_recomputed':False,'reference_warning':'Cached raw values from different own-h cohorts must not be mixed to reconstruct this percentile. A recomputation would require same h across the whole stock or industry reference group.','source':str(P)})
assert all(r['round12_exact_cache_raw'] for r in rows)
(O/'H1_TEN_FOCAL_ENDPOINT_ARITHMETIC.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n');pd.DataFrame(terms).to_csv(O/'H1_TEN_FOCAL_FOUR_TERMS.csv',index=False)
flat=[]
for r in rows:
 f={k:v for k,v in r.items() if k not in ['endpoints','four_terms']}
 for e in r['endpoints']:
  for k in ['date','close','source_segment','lag_common_sessions']:f['endpoint'+str(e['endpoint'])+'_'+k]=e[k]
 for n,tr in enumerate(r['four_terms'],1):f['return'+str(n)]=tr['simple_return'];f['weighted_term'+str(n)]=tr['weighted_term']
 flat.append(f)
pd.DataFrame(flat).to_csv(O/'H1_TEN_FOCAL_ENDPOINT_ARITHMETIC.csv',index=False)
(O/'H1_ENDPOINT_SOURCE_SHA256.json').write_text(json.dumps({str(P):hashlib.sha256(P.read_bytes()).hexdigest(),str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
print(pd.DataFrame([{k:r[k] for k in ['date','name','h','sum_unrounded','numpy_round12','cached_raw','cached_Nref','cached_H1_percentile_score','round12_exact_cache_raw']} for r in rows]).to_string(index=False))
