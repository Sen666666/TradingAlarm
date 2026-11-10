"""Decision-known first-entry price/risk grouping; no account/policy engine."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D,getcontext
import json,hashlib,csv
import pandas as pd
import numpy as np
getcontext().prec=60
O=Path(__file__).resolve().parent;E=O.parents[1];T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):
 with (O/n).open('w') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def n(x):return D(str(x))
def agg(rows,mother=None):
 a=dict(fills=len(rows),stocks=len({x['sid'] for x in rows}))
 for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']:a[k]=sum((n(x[k]) for x in rows),Z)
 a.update(positive=sum((max(Z,n(x['net'])) for x in rows),Z),negative=sum((min(Z,n(x['net'])) for x in rows),Z),positive_fills=sum(n(x['net'])>0 for x in rows),negative_fills=sum(n(x['net'])<0 for x in rows),open_layers=sum(bool(x['qty']) for x in rows),tail30_analysis_layers=sum(n(x['net'])/n(x['cost'])>=D('.3') for x in rows))
 if mother:
  a.update(share_of_mother_buycash=a['cost']/mother['cost'] if mother['cost'] else None,share_of_mother_positive=a['positive']/mother['positive'] if mother['positive'] else None,share_of_mother_negative=a['negative']/mother['negative'] if mother['negative'] else None)
 def dist(k):
  v=[float(x[k]) for x in rows if x.get(k) is not None]
  return dict(known=len(v),unknown=len(rows)-len(v),min=None if not v else min(v),q25=None if not v else float(np.quantile(v,.25)),median=None if not v else float(np.quantile(v,.5)),q75=None if not v else float(np.quantile(v,.75)),max=None if not v else max(v))
 a['decision_distributions']={k:dist(k) for k in ['stock_gap_prior63high_pct','industry_gap_prior63high_pct','decision_protection_width_pct','decision_budget_pct_NAV','decision_cap_reference_gross_pct_NAV','decision_cap_nominal_risk_pct_NAV']}
 return a
def main():
 read(O/'PROTOCOL.json')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')};frames={};snaps={}
 def snapshot(sid,day):
  key=(sid,day)
  if key in snaps:return snaps[key]
  if sid not in frames:
   m=im[sid] if sid.startswith('URFI') else sm[sid];p=Path(m['refs']['CP1_input' if sid.startswith('URFI') else 'facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m['output_sha256'][str(p)];SRC[str(p)]=h
   frames[sid]=pd.read_parquet(p,columns=['close','segment_id'])
  f=frames[sid];dt=pd.Timestamp(day);assert f.index.is_unique and f.index.is_monotonic_increasing and dt in f.index;prefix=f.loc[:dt];current=prefix.iloc[-1];prior=prefix.iloc[-64:-1]
  why=None
  if len(prior)!=63:why='insufficient_prior63'
  elif pd.isna(current.segment_id) or not prior.segment_id.eq(current.segment_id).all():why='price_domain_changed_within_prior63'
  elif not np.isfinite(prior.close.to_numpy(float)).all() or not prior.close.gt(0).all():why='invalid_prior_price'
  h=None if why else float(prior.close.max());c=float(current.close)
  s=dict(close=c,prior63high=h,breakout=None if why else c>h,gap_pct=None if why else (c/h-1)*100,unknown=why,source_max_used=day,prior_last=str(prior.index[-1].date()) if len(prior) else None)
  snaps[key]=s;return s
 entries={};allfirst=[]
 for ref in ['2022_2024','strong']:
  rows=read(E/'local_high'/(ref+'_ROWS.json'));gg={x['layer']:x for x in read(T/f'loss_correction/mobile_current_grade_quickcheck_v1/{ref}_ROWS.json')};out=[]
  for e in rows:
   if e['action']!='first_actual_participation':continue
   x=dict(e);day=e['decision_at'][:10];ss=snapshot(e['sid'],day);ii=snapshot(e['sector'],day)
   assert abs(ss['close']-float(e['stock']['close']))<1e-8 and abs(ii['close']-float(e['industry_state']['close']))<1e-8
   refp=n(e['signal_close_raw'])*D('1.0005');floor=n(e['frozen_initial_adjusted_floor'])/n(e['signal_factor']);nav=n(e['decision_NAV']);g=gg[e['layer']];assert (g['sid'],g['decision_at'])==(e['sid'],e['decision_at'])
   x.update(window=ref,stock_prior63=ss,industry_prior63=ii,stock_breakout='unknown' if ss['breakout'] is None else 'above_prior63closehigh' if ss['breakout'] else 'not_above_prior63closehigh',industry_breakout='unknown' if ii['breakout'] is None else 'above_prior63closehigh' if ii['breakout'] else 'not_above_prior63closehigh',stock_gap_prior63high_pct=ss['gap_pct'],industry_gap_prior63high_pct=ii['gap_pct'],decision_protection_width_pct=(refp-floor)/refp*100,decision_budget_pct_NAV=n(e['frozen_intent']['budget'])/nav*100,decision_cap_reference_gross_pct_NAV=D(e['frozen_intent']['cap'])*refp/nav*100,decision_cap_nominal_risk_pct_NAV=D(e['frozen_intent']['cap'])*max(Z,refp-floor)/nav*100,original_MA_class=e['original_inclusive_MA_class'],current_g_grade=g['current_g_grade'],current_g_ready=g['current_g_ready'])
   out.append(x);allfirst.append(x)
  entries[ref]=out
 assert len(entries['2022_2024'])==968 and len(entries['strong'])==671
 # Descriptive equal-observation quartiles. No outcomes enter the cuts.
 cuts={}
 for k in ['decision_protection_width_pct','decision_cap_reference_gross_pct_NAV','decision_budget_pct_NAV']:
  v=[float(x[k]) for x in allfirst if x[k] is not None];q=[float(np.quantile(v,z)) for z in [.25,.5,.75]];cuts[k]=dict(cuts=q,population='all1639 first actual entries pooled, unweighted; descriptive only',cut_ties=[sum(float(x[k])==c for x in allfirst) for c in q])
  for x in allfirst:x[k+'_quartile']='unknown' if x[k] is None else 'Q'+str(1+sum(float(x[k])>c for c in q))
 results={}
 for ref,rows in entries.items():
  scopes={'ALL_FIRST':rows}
  if ref=='2022_2024':scopes.update(two_year_first=[x for x in rows if x['opened'][:10]<='2023-12-29'],post303_first=[x for x in rows if x['opened'][:10]>'2024-10-08'])
  summary={}
  dimensions=['role','pool_at_fill','original_MA_class','ETF_macro','stock_breakout','industry_breakout','decision_protection_width_pct_quartile','decision_cap_reference_gross_pct_NAV_quartile','decision_budget_pct_NAV_quartile']
  jointsets={'role_and_breakouts':['role','stock_breakout','industry_breakout'],'macro_role_breakouts':['ETF_macro','role','stock_breakout','industry_breakout'],'role_and_protection_quartile':['role','decision_protection_width_pct_quartile'],'role_and_planned_size_quartile':['role','decision_cap_reference_gross_pct_NAV_quartile']}
  for name,z in scopes.items():
   mother=agg(z);groups={d:{key:agg([x for x in z if x[d]==key],mother) for key in sorted({x[d] for x in z})} for d in dimensions}
   joints={}
   for label,ds in jointsets.items():
    buckets=defaultdict(list)
    for x in z:buckets[tuple(x[d] for d in ds)].append(x)
    joints[label]=[dict(labels=dict(zip(ds,key)),money=agg(value,mother)) for key,value in sorted(buckets.items())]
   summary[name]=dict(all=mother,groups=groups,joints=joints)
   for d,g in groups.items():assert abs(sum((n(v['net']) for v in g.values()),Z)-mother['net'])<D('1e-18')
  old=read(E/'local_high'/(ref+'_FIXED_TAILS.json'));byid={x['layer']:x for x in rows};controls=[]
  for t in old:
   matched=[byid[x['layer']] for x in t['matched_actual_No60_rows'] if x['layer'] in byid]
   controls.append(dict(original=t['original'],matched_actual_first=matched,unmatched_in_No60=t['unmatched'],note='No match and matched non-first are distinct; original cohort unchanged.'))
  matches=[x for t in controls for x in t['matched_actual_first']]
  summary['fixed_original_tail']=dict(original_members=len(old),all_actual_matches=sum(not t['unmatched'] for t in old),actual_first_matches=len(matches),actual_first_money=agg(matches),first_by_stock_breakout={k:agg([x for x in matches if x['stock_breakout']==k]) for k in sorted({x['stock_breakout'] for x in matches})})
  results[ref]=summary;save(ref+'_FIRST_ROWS.json',rows);save(ref+'_ORIGINAL_FIXED_TAILS.json',controls)
 save('RESULTS.json',results);save('DESCRIPTIVE_QUARTILE_CUTS.json',cuts);save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),unique_stock_or_industry_frames=len(frames),snapshots=len(snaps),new_account_events=0,new_gate_events=0))
 columns=['window','layer','sid','name','role','opened','decision_at','stock_breakout','industry_breakout','stock_gap_prior63high_pct','industry_gap_prior63high_pct','ETF_macro','pool_at_fill','decision_protection_width_pct','decision_budget_pct_NAV','decision_cap_reference_gross_pct_NAV','decision_cap_nominal_risk_pct_NAV','cost','net','strict_realized','open_unrealized','recognized_dividend_AR']
 with (O/'ALL_FIRST_DECISIONS.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(allfirst)
 print('FIRST_PRICE_RISK_COMPLETE',len(allfirst),len(frames),len(snaps),flush=True)
if __name__=='__main__':main()
