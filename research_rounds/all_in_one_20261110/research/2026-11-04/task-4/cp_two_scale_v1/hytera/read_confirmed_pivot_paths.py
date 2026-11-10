"""Saved E0 pivot paths, revealed only at confirmation; no CP/G/account model."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={}
def bind(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.isoformat()
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')
def main():
 bind(__file__)
 sid='002583.SZ';lo='2024-09-23';hi='2024-11-27'
 rec=next(r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')if r['symbol']==sid)
 ep=next(p for p in rec['source_sha256']if p.endswith('/events.parquet'))
 p=bind(ep);assert H[str(p)]==rec['source_sha256'][str(p)];events=pd.read_parquet(p).loc[:hi]
 fs={}
 for key in ['CP1_input','CP1','facts']:
  p=bind(rec['refs'][key]);assert H[str(p)]==rec['output_sha256'][str(p)];fs[key]=pd.read_parquet(p).loc[:hi]
 f=fs['CP1_input'];cp=fs['CP1'];facts=fs['facts'];assert f.index.equals(cp.index)
 days=list(f.index);index={d:i for i,d in enumerate(days)};C=[float(x)for x in f.close];segments=list(f.segment_id)
 def describe(anchor,t):
  if anchor is None:return None
  j=anchor['pivot_index'];i=index[t];assert j<=i
  assert all(segments[k]==anchor['source_segment']for k in range(j,i+1))
  L=math.fsum(abs(math.log(C[k]/C[k-1]))for k in range(j+1,i+1));A=math.log(C[i]/anchor['pivot_price_a_saved']);mx=max(C[j:i+1]);DD=math.log(mx/C[i])
  return dict(A=A,L=L,ER=A/L if L>0 else None,DD=DD,
   observations_after_pivot=i-j,known_peak_C_a=mx,path_start_exclusive=anchor['pivot_day'],path_end_inclusive=str(t.date()),
   anchor={k:v for k,v in anchor.items()if k!='pivot_index'},
   pivot_a_div_current_factor=float(anchor['pivot_price_a_saved']/float(facts.loc[t].factor)),
   current_factor=float(facts.loc[t].factor),
   disclosed_only_from_confirm_at=True)
 anchors={'short_low':None,'long_high':None};lastseg=None;rows=[];archive=[]
 for day,r in f.iterrows():
  d=str(day.date());seg=int(r.segment_id);ev=events.loc[day]if day in events.index else None
  if lastseg is not None and seg!=lastseg:anchors={'short_low':None,'long_high':None}
  update=None
  if ev is not None and ev.event in[1,-1]and not pd.isna(ev.confirmed_pivot_price):
   kind='short_low'if int(ev.event)==1 else'long_high';pdte=pd.Timestamp(ev.confirmed_pivot_date);j=index[pdte];price=float(ev.confirmed_pivot_price)
   assert int(ev.segment_id)==seg==int(f.loc[pdte].segment_id)
   assert math.isclose(C[j],price,rel_tol=1e-12,abs_tol=1e-12)
   z=cp.loc[day,'z'];z=None if pd.isna(z)else float(z)
   old=anchors[kind];old_path=describe(old,day)
   new=dict(kind=kind,event_sign=int(ev.event),pivot_day=str(pdte.date()),confirm_day=d,
    confirm_at_native_protocol=d+' 15:10:00+08:00',confirmation_clock_is_vendor_timestamp=False,
    pivot_price_a_saved=price,pivot_raw_close_at_pivot_saved=float(facts.loc[pdte].raw_close),
    sigma_CP_z_at_confirm=z,sigma_is_copied_not_reestimated=True,source_segment=seg,pivot_index=j,
    source_id={'symbol':sid,'source_segment':seg,'events_path':str(Path(ep).resolve()),'events_sha256':H[str(Path(ep).resolve())],'event_row':d,'provider_event_ID':'NOT_SAVED','identity_kind':'LOCAL_SOURCE_ROW_PROVENANCE_NOT_PROVIDER_ID'})
   anchors[kind]=new;update=kind
   if lo<=d<=hi:
    archive.append(dict(replacement_confirm_at=d+' 15:10:00+08:00',kind=kind,
     previous_anchor={k:v for k,v in old.items()if k!='pivot_index'}if old else None,
     previous_anchor_path_ending_at_replacement_before_switch=old_path,
     newly_confirmed_anchor={k:v for k,v in new.items()if k!='pivot_index'},
     newly_confirmed_anchor_path_at_disclosure=describe(new,day),
     lower_high_replacement=bool(kind=='long_high'and old and price<old['pivot_price_a_saved']),
     no_original_receipt_or_down_reset_used_as_anchor=True))
  if lo<=d<=hi:
   a=describe(anchors['short_low'],day);b=describe(anchors['long_high'],day);fa=facts.loc[day]
   rows.append(dict(sid=sid,date=d,known_at_native_protocol=d+' 15:10:00+08:00',continuous_close=float(r.close),raw_close=float(fa.raw_close),factor=float(fa.factor),source_segment=seg,
    original_E0_target=int(fa.e0_target),original_I_target=int(fa.i_target),
    original_E0_event=int(ev.event)if ev is not None and not pd.isna(ev.event)else None,
    anchor_changed_today=update,short=a,long=b,original_CP_receipt=bool(cp.loc[day,'receipt']),
    original_CP_reset_reason=None if pd.isna(cp.loc[day,'reset_reason'])else str(cp.loc[day,'reset_reason']),
    anchor_rule='Only newly confirmed E0 +1 low/-1 high updates; old CP receipt/down/SEEK and I off do not wash these same-source anchors.',
    no_new_G_or_trading_state=True))
  lastseg=seg
 assert len(rows)==43
 save('ALL43_CONFIRMED_E0_TWO_SCALE_PATHS.json',rows)
 flat=[]
 for r in rows:
  q={k:v for k,v in r.items()if k not in['short','long']}
  for label,key in [('s','short'),('l','long')]:
   v=r[key]
   for name in ['A','L','ER','DD','observations_after_pivot','pivot_a_div_current_factor']:
    q[name+'_'+label]=v[name]if v else None
   for name in ['pivot_day','confirm_day','confirm_at_native_protocol','pivot_price_a_saved','pivot_raw_close_at_pivot_saved','sigma_CP_z_at_confirm','source_segment']:
    q[label+'_'+name]=v['anchor'][name]if v else None
   q['sigma_'+label]=v['anchor']['sigma_CP_z_at_confirm']if v else None
   q['sourceID_'+label]=json.dumps(v['anchor']['source_id'],ensure_ascii=False,separators=(',',':'))if v else None
  flat.append(q)
 with(OUT/'ALL43_CONFIRMED_E0_TWO_SCALE_PATHS.csv').open('w',newline='')as g:
  w=csv.DictWriter(g,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 save('KEY_2024_09_24_10_18.json',[r for r in rows if r['date']in['2024-09-24','2024-10-18']])
 save('ANCHOR_REPLACEMENT_ARCHIVE.json',archive)
 save('SOURCE_SHA256.json',H)
 save('SCOPE.json',dict(symbol=sid,window=[lo,hi],observations=43,raw_event_columns=list(events.columns),
  unavailable_provider_eventID=True,anchor_is_original_confirmed_close_pivot=True,
  historical_path_use='Pivot->confirmation historical prices are all known at confirmation; anchor/path not disclosed on earlier pivot dates. No future confirmed pivot backfill.',
  raw_mapping='Saved pivot a/current factor is current raw units; pivot-day original rawclose is separately preserved.',
  sigmas='Copy oldCP z on respective pivot confirmation dates; no new volatility estimate.',
  new_accounts=0,new_backtests=0,new_G_states=0,new_thresholds=0,new_returns=0,new_CP_receipt_models=0))
if __name__=='__main__':main()
