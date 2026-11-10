"""Endpoint-only raw/adjusted sensitivity at saved CPs/signals, no new models."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
cache={};source={}
def get(sid):
 if sid not in cache:
  p=Path(manifest[sid]['refs']['facts']);source[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  assert source[str(p)]==manifest[sid]['output_sha256'][str(p)]
  cache[sid]=pd.read_parquet(p)
 return cache[sid]
def val(f,d,k):
 d=pd.Timestamp(d)
 if d not in f.index or pd.isna(f.at[d,k]):return None
 return float(f.at[d,k])
def augment(r):
 f=get(r['sid']);d=r['day'];ft=val(f,d,'factor');rawt=val(f,d,'raw_close')
 z={'sid':r['sid'],'name':r['name'],'day':d,'CP_receipt_id':r.get('CP_canonical_receipt_id'),'factor_t':ft,'raw_close_t':rawt}
 for n in [5,20,60]:
  b=r[f'base_day_{n}'];fb=val(f,b,'factor');rb=val(f,b,'raw_close')
  rawret=math.log(rawt/rb) if rawt is not None and rb is not None and min(rawt,rb)>0 else None
  ir=r[f'industry_logreturn_{n}'];adj=r[f'stock_logreturn_{n}']
  rawrs=rawret-ir if rawret is not None and ir is not None else None
  adjustment=math.log(ft/fb) if ft is not None and fb is not None and min(ft,fb)>0 else None
  delta=adj-rawret if adj is not None and rawret is not None else None
  residual=delta-adjustment if delta is not None and adjustment is not None else None
  assert residual is None or abs(residual)<1e-12,(r['sid'],d,n,residual)
  ar=r[f'RS_stock_{n}']
  z.update({f'base_day_{n}':b,f'factor_base_{n}':fb,f'raw_close_base_{n}':rb,f'raw_stock_logreturn_{n}':rawret,
    f'adjusted_stock_logreturn_{n}':adj,f'industry_logreturn_{n}':ir,f'RS_raw_vs_industry_{n}':rawrs,f'RS_adjusted_vs_industry_{n}':ar,
    f'adjustment_logfactor_{n}':adjustment,f'adjusted_minus_raw_return_{n}':delta,f'identity_residual_{n}':residual,
    f'factor_changed_exact_{n}':ft!=fb if ft is not None and fb is not None else None,
    f'RS_sign_changed_{n}':((ar>0)-(ar<0) != (rawrs>0)-(rawrs<0)) if ar is not None and rawrs is not None else None})
 return z
cp=[augment(r) for r in read(O/'ALL_CANONICAL_CP_H1_RS.json')]
signals=[]
for r in read(O/'ALL25_ORIGINAL_SIGNAL_RS.json'):
 z=augment(r['RS_at_original_signal']);z.update(layer=r['layer'],role=r['role']);signals.append(z)
def save(name,rs):
 dump(O/(name+'.json'),rs)
 with (O/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rs for k in r)));w.writeheader();w.writerows(rs)
save('ALL1220_CP_RAW_ADJUSTED_SENSITIVITY',cp);save('ALL25_SIGNAL_RAW_ADJUSTED_SENSITIVITY',signals)
summary={}
for label,rs in [('canonical_CP1220',cp),('original_signals25',signals)]:
 summary[label]={}
 for n in [5,20,60]:
  av=[r for r in rs if r[f'RS_raw_vs_industry_{n}'] is not None and r[f'RS_adjusted_vs_industry_{n}'] is not None]
  summary[label][str(n)]={'rows':len(rs),'both_available':len(av),'missing':len(rs)-len(av),
   'factor_changed_exact':sum(r[f'factor_changed_exact_{n}'] is True for r in av),
   'RS_sign_changed':sum(r[f'RS_sign_changed_{n}'] is True for r in av),
   'max_abs_adjustment_logfactor':max((abs(r[f'adjustment_logfactor_{n}']) for r in av),default=None),
   'max_abs_identity_residual':max((abs(r[f'identity_residual_{n}']) for r in av),default=None),
   'changed_sign_rows':[{k:r[k] for k in ['sid','name','day',f'RS_raw_vs_industry_{n}',f'RS_adjusted_vs_industry_{n}',f'adjustment_logfactor_{n}']} for r in av if r[f'RS_sign_changed_{n}']]}
dump(O/'RAW_ADJUSTED_CONVENTION_SUMMARY.json',summary)
source[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();dump(O/'RAW_ADJUSTED_SOURCE_SHA256.json',source)
print(json.dumps(summary,ensure_ascii=False,indent=2))
