"""Original decision-price context, no holding/financial engine or new policy."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D,getcontext
import json,hashlib,csv
import numpy as np
import pandas as pd
getcontext().prec=60
O=Path(__file__).resolve().parent;E=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def n(x):return D(str(x))
def agg(z,mother=None):
 a=dict(layers=len(z),stocks=len({x['sid'] for x in z}))
 for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']:a[k]=sum((n(x[k]) for x in z),Z)
 a.update(positive_net=sum((max(Z,n(x['net'])) for x in z),Z),negative_net=sum((min(Z,n(x['net'])) for x in z),Z),negative_layers=sum(n(x['net'])<0 for x in z),positive_layers=sum(n(x['net'])>0 for x in z),open_layers=sum(bool(x['qty']) for x in z))
 if mother:a.update(negative_money_share=a['negative_net']/mother['negative_net'] if mother['negative_net'] else None,positive_money_share=a['positive_net']/mother['positive_net'] if mother['positive_net'] else None,buycash_share=a['cost']/mother['cost'] if mother['cost'] else None)
 a['context_distributions']={}
 for k in ['width_pct','gap_prior20close_pct','gap_prior20high_pct','r5_pct','r20_pct','decision_budget_pct_NAV','decision_cap_nominal_risk_pct_NAV']:
  v=[float(x[k]) for x in z if x.get(k) is not None]
  a['context_distributions'][k]=dict(known=len(v),unknown=len(z)-len(v),quantiles=None if not v else np.quantile(v,[0,.1,.25,.5,.75,.9,1]).tolist())
 return a
def groups(z,cols,mother):
 buckets=defaultdict(list)
 for x in z:buckets[tuple(x[c] for c in cols)].append(x)
 return [dict(labels=dict(zip(cols,key)),money=agg(value,mother)) for key,value in sorted(buckets.items(),key=lambda kv:str(kv[0]))]
def main():
 read(O/'PROTOCOL.json');sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};frames={};raw={};snap={}
 def context(sid,day):
  key=(sid,day)
  if key in snap:return snap[key]
  if sid not in frames:
   m=sm[sid];p=Path(m['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m['output_sha256'][str(p)];SRC[str(p)]=h
   frames[sid]=pd.read_parquet(p,columns=['close','segment_id','factor','raw_close','i_floor','i_target']);rp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert hashlib.sha256(rp.read_bytes()).hexdigest()==m['source_sha256'][str(rp)];SRC[str(rp)]=m['source_sha256'][str(rp)]
   raw[sid]=pd.read_parquet(rp,columns=['close','high','segment_id','price_eligible','source_invalid','observed_bar','synthetic_event_bar'])
  f=frames[sid];dt=pd.Timestamp(day);assert dt in f.index and f.index.is_unique and f.index.is_monotonic_increasing;p=f.loc[:dt];cur=p.iloc[-1];seg=cur.segment_id
  result=dict(decision_close=float(cur.close),decision_factor=n(cur.factor),decision_raw_close=n(cur.raw_close),decision_I_floor=None if pd.isna(cur.i_floor) else float(cur.i_floor),source_segment=float(seg),r5_pct=None,r20_pct=None,gap_prior20close_pct=None,gap_prior20high_pct=None,prior20close=None,prior20high=None,r5_span_calendar_days=None,r20_span_calendar_days=None,unknown=[])
  for k,horizon in [('r5_pct',5),('r20_pct',20)]:
   w=p.iloc[-(horizon+1):]
   if len(w)!=horizon+1:result['unknown'].append(k+':insufficient_history')
   elif pd.isna(seg) or not w.segment_id.eq(seg).all() or not np.isfinite(w.close.to_numpy(float)).all() or not w.close.gt(0).all():result['unknown'].append(k+':incomparable_or_invalid_history')
   else:result[k]=(float(cur.close/w.iloc[0].close)-1)*100;result['r5_span_calendar_days' if horizon==5 else 'r20_span_calendar_days']=(dt-w.index[0]).days
  prior=p.iloc[-21:-1]
  if len(prior)==20 and prior.segment_id.eq(seg).all() and np.isfinite(prior.close.to_numpy(float)).all() and prior.close.gt(0).all():
   ch=float(prior.close.max());result.update(prior20close=ch,gap_prior20close_pct=(float(cur.close)/ch-1)*100)
   rf=raw[sid];rr=rf.reindex(prior.index)
   good=rr.close.notna()&rr.high.notna()&rr.segment_id.eq(seg)&rr.price_eligible.eq(True)&rr.source_invalid.eq(False)&rr.observed_bar.eq(True)&rr.synthetic_event_bar.eq(False)&np.isfinite(rr.high)&rr.high.ge(rr.close-1e-10)&rr.high.gt(0)
   if good.all() and np.allclose(rr.close.to_numpy(float),prior.close.to_numpy(float),rtol=1e-10,atol=1e-10):
    hh=float(rr.high.max());result.update(prior20high=hh,gap_prior20high_pct=(float(cur.close)/hh-1)*100)
   else:result['unknown'].append('prior20_OHLC_high:bad_or_missing_exact_geometry')
  else:result['unknown'].append('prior20close:insufficient_or_incomparable')
  snap[key]=result;return result
 rows={};allrows=[]
 for ref in ['2022_2024','strong']:
  source=read(E/'local_high'/(ref+'_ROWS.json'));out=[]
  for e in source:
   c=context(e['sid'],e['decision_at'][:10]);assert abs(c['decision_close']-float(e['stock']['close']))<1e-8
   assert n(e['frozen_initial_adjusted_floor'])==n(e['frozen_intent']['floor']);refp=c['decision_raw_close']*D('1.0005');floor=n(e['frozen_intent']['floor'])/c['decision_factor'];nav=n(e['decision_NAV'])
   x=dict(e,window=ref,**{k:v for k,v in c.items() if k not in ['unknown']},context_unknown=c['unknown'],decision_reference_price=refp,decision_original_floor_raw=floor,width_pct=(refp-floor)/refp*100,decision_budget_pct_NAV=n(e['frozen_intent']['budget'])/nav*100,decision_cap_nominal_risk_pct_NAV=D(e['frozen_intent']['cap'])*max(Z,refp-floor)/nav*100)
   x['break20close']='unknown' if x['gap_prior20close_pct'] is None else 'above_prior20close' if x['gap_prior20close_pct']>0 else 'at_prior20close' if x['gap_prior20close_pct']==0 else 'below_prior20close'
   x['r5_sign']='unknown' if x['r5_pct'] is None else 'positive' if x['r5_pct']>0 else 'negative' if x['r5_pct']<0 else 'zero'
   x['r20_sign']='unknown' if x['r20_pct'] is None else 'positive' if x['r20_pct']>0 else 'negative' if x['r20_pct']<0 else 'zero'
   out.append(x);allrows.append(x)
  rows[ref]=out
 assert len(allrows)==3436
 cuts={}
 for k in ['width_pct','gap_prior20close_pct','r5_pct','r20_pct']:
  v=[float(x[k]) for x in allrows if x[k] is not None];q=np.quantile(v,[.25,.5,.75]).tolist();cuts[k]=dict(cuts=q,known=len(v),unknown=len(allrows)-len(v),ties=[sum(float(x[k])==a for x in allrows if x[k] is not None) for a in q],scope='pooled3436 original layers, equal observation; descriptive not policy')
  for x in allrows:x[k+'_q']='unknown' if x[k] is None else 'Q'+str(1+sum(float(x[k])>a for a in q))
 results={}
 for ref,rr in rows.items():
  scopes={'ALL':rr}
  if ref=='2022_2024':scopes.update(two_year=[x for x in rr if x['opened'][:10]<='2023-12-29'],post303=[x for x in rr if x['opened'][:10]>'2024-10-08'],post924_new320=[x for x in rr if '2024-09-24'<=x['opened'][:10]])
  output={}
  for name,z in scopes.items():
   mother=agg(z);item=dict(all=mother,by_action=groups(z,['action'],mother),by_role=groups(z,['role'],mother),natural=groups(z,['action','role','break20close','r5_sign','r20_sign'],mother),pairs={})
   for pair,cols in {'width_r5':['width_pct_q','r5_pct_q'],'width_r20':['width_pct_q','r20_pct_q'],'break20_r20':['break20close','r20_pct_q']}.items():item['pairs'][pair]=groups(z,['action','role']+cols,mother)
   output[name]=item
  controls=read(E/'local_high'/(ref+'_FIXED_TAILS.json'));byid={x['layer']:x for x in rr};matched=[byid[x['layer']] for t in controls for x in t['matched_actual_No60_rows']]
  output['fixed_original_tail']=dict(original_members=len(controls),exact_matched_members=sum(not t['unmatched'] for t in controls),unmatched_members=sum(t['unmatched'] for t in controls),actual_matched_money=agg(matched),all_controls=[dict(original=t['original'],matched_actual_layers=[x['layer'] for x in t['matched_actual_No60_rows']],unmatched=t['unmatched']) for t in controls],pairs=groups(matched,['action','role','width_pct_q','r5_pct_q'],agg(matched)))
  results[ref]=output;save(ref+'_ROWS.json',rr)
 save('RESULTS.json',results);save('DESCRIPTIVE_CUTS.json',cuts)
 cols=['window','layer','sid','name','role','action','decision_at','opened','closed','width_pct','decision_original_floor_raw','gap_prior20close_pct','gap_prior20high_pct','r5_pct','r20_pct','r5_span_calendar_days','r20_span_calendar_days','decision_budget_pct_NAV','decision_cap_nominal_risk_pct_NAV','cost','net','strict_realized','open_unrealized','recognized_dividend_AR']
 with (O/'ALL_DECISION_CONTEXT.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(allrows)
 save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),unique_price_frames=len(frames),unique_decision_snapshots=len(snap),new_accounts=0,new_models=0,context_unknown_counts=dict(__import__('collections').Counter(y for x in allrows for y in x['context_unknown']))))
 print('ENTRY_EXIT_CONTEXT_COMPLETE',len(allrows),len(frames),len(snap),flush=True)
if __name__=='__main__':main()
