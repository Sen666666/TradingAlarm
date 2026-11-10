"""Six frozen replacement cases: saved bookkeeping + price labels only.
No Account/Runner restore, no signal recomputation, no financial events.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import date
import sys,json,gzip,copy,hashlib,traceback,time,math
import pandas as pd,numpy as np
import importlib.util
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'_shared'));import research_output_io as IO
sys.path.insert(0,str(R/'g-s-historical-native-prefix-20261101'));from policy import ExitLock
DESIGN=R/'replacement-quality-design-v1-20261102'
COVER=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/pre-sell-quote-coverage-readonly-20261102')
JAN=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-difference-readonly-20261102')
PRICE_AUDIT=R/'opportunity-quality-ranking-20261031/PRICE_SOURCE_AUDIT.json'
Z=D(0)
USED_SOURCES={}
FILTER_PATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py')
spec=importlib.util.spec_from_file_location('six_case_original_price_filter',FILTER_PATH);FILTER=importlib.util.module_from_spec(spec);spec.loader.exec_module(FILTER)
def read(p):
 p=Path(p)
 actual=p if p.exists() else Path(str(p)+'.gz')
 if not actual.resolve().is_relative_to(O.resolve()):USED_SOURCES[str(actual.resolve())]=sha(actual)
 return json.loads(p.read_text()) if p.exists() else json.loads(gzip.open(str(p)+'.gz','rt').read())
def save(p,x):IO.write_json(p,json.loads(json.dumps(x,default=str,ensure_ascii=False)))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x):return x is not None and bool(pd.notna(x)) and math.isfinite(float(x))
def scalar(x):return x.item() if isinstance(x,np.generic) else x
def clean(r):
 out={}
 for k,v in r.items():
  v=scalar(v)
  out[k]=None if v is None or (isinstance(v,float) and not math.isfinite(v)) else v
 return out
def source_path(p):return p if p.exists() else Path(str(p)+'.gz')

def table(root,key,dates=None):
 m=read(root/'MANIFEST.json');rs=[]
 for group in ['files','extensions','month_extension','continuation_extension']:
  if key not in m.get(group,{}):continue
  rec=m[group][key];p=root/rec['path'];assert sha(p)==rec['sha256'];USED_SOURCES[str(p.resolve())]=rec['sha256'];z=pd.read_parquet(p)
  if dates is not None:z=z[z.day.isin(dates)]
  rs.append(z)
 return pd.concat(rs,ignore_index=True).drop_duplicates(['sid','day'],keep='last')

def oldrisk(a,layer,q,at,mark,floor):
 # Same eligible lock order as original Policy.consume_exit, no fill callback.
 left=q;risk=Z;used=[]
 for e in a['policy']['locks'].values():
  duty=a['exit_duties'].get(e['eid'],{})
  if e['lot']!=layer or not e['remaining'] or duty.get('funding_suspended') or duty.get('earliest_at','9999')>at:continue
  n=min(left,e['remaining']);v=copy.deepcopy(e)
  for k in ['q0','e0','ratio']:v[k]=None if v[k] is None else D(v[k])
  risk+=ExitLock(**v).charge(D(str(mark)),D(str(floor)))*D(n)/e['remaining'];left-=n;used.append(e['eid'])
  if not left:break
 if left:return None,used,'UNKNOWN exact eligible lock allocation'
 return float(risk),used,None

def prices(sid,idx,cache):
 if sid not in cache:
  r=idx[sid];p=Path(r['path']);assert sha(p)==r['SHA256'];USED_SOURCES[str(p.resolve())]=r['SHA256']
  cache[sid]=pd.read_parquet(p).sort_index()
 return cache[sid]

def label(f,start,endpoint,market_days):
 startpd=pd.Timestamp(start);end=pd.Timestamp(endpoint)
 if startpd not in f.index or end not in f.index:return dict(valid=False,reason='missing_start_or_fixed_endpoint')
 z=f.loc[startpd:end]
 # All-day validity belongs only to hindsight labeling, never ASOF evidence.
 eligible=FILTER.eligible_prices(z);flags=z.index.isin(eligible.index)
 if not bool(flags[0]) or not bool(flags[-1]):return dict(valid=False,reason='invalid_start_or_fixed_endpoint')
 if not finite(z.iloc[0].raw_open) or z.iloc[0].raw_open<=0:return dict(valid=False,reason='no_open_anchor')
 if z.segment_id.nunique(dropna=False)!=1:return dict(valid=False,reason='source_segment_break')
 f0=float(z.iloc[0].adjustment_factor);p0=float(z.iloc[0].raw_open)
 good=z[flags & z.raw_close.notna() & z.adjustment_factor.notna()]
 # Relative factor ratio is future-only label information. No future price or
 # factor is used in the saved decision evidence/protective-line calculation.
 path=good.raw_close.astype(float)*good.adjustment_factor.astype(float)/f0/p0-1
 missing_inside=int((~flags).sum())
 missing_days=sorted(set(d for d in market_days if start<=d<=endpoint)-{str(d.date()) for d in good.index})
 return dict(valid=True,start_day=start,end_day=endpoint,anchor_raw_open=p0,return_pct=float(path.iloc[-1]*100),
  close_MAE_pct=float(min(0.,path.min())*100),close_MFE_pct=float(max(0.,path.max())*100),
  observed_close_count=len(path),invalid_present_rows=missing_inside,missing_market_sessions=missing_days,
  path_pct_by_day={str(d.date()):float(v*100) for d,v in path.items()},forward_factor_ratio_used_only_for_labels=True)

def weighted(rows,h,field,weight):
 good=[z for z in rows if z['labels'][str(h)].get('valid') and z[weight]>0]
 total=sum(z[weight] for z in rows if z[weight]>0);covered=sum(z[weight] for z in good)
 return dict(value=sum(z[weight]*z['labels'][str(h)][field] for z in good)/covered if covered else None,
  covered_weight=covered,total_weight=total,coverage_fraction=covered/total if total else None,stocks=len(good),
  no_silent_NA_complete_comparison=bool(total and abs(covered-total)<1e-6))

def basket_path(rows,h,weight):
 selected=[r for r in rows if r[weight]>0];total=sum(r[weight] for r in selected)
 if not selected or any(not r['labels'][str(h)].get('valid') or r['labels'][str(h)].get('missing_market_sessions') for r in selected):
  return dict(valid=False,reason='incomplete_fixed_common_path',weight=weight)
 dates=set(selected[0]['labels'][str(h)]['path_pct_by_day'])
 if any(set(r['labels'][str(h)]['path_pct_by_day'])!=dates for r in selected):return dict(valid=False,reason='different_calendar_dates',weight=weight)
 path={d:sum(r[weight]*r['labels'][str(h)]['path_pct_by_day'][d] for r in selected)/total for d in sorted(dates)}
 return dict(valid=True,weight=weight,return_pct=path[max(path)],close_MAE_pct=min(0.,min(path.values())),close_MFE_pct=max(0.,max(path.values())),
  path_pct_by_day=path,static_initial_weights=True,not_a_policy_portfolio_or_executable_PNL=True)

def main():
 t=time.monotonic();design=read(DESIGN/'SAMPLE_BINDING.json');assert sha(DESIGN/'DESIGN.txt')=='c5bb793367faaf969a9f176c4f7a08ac453a2c2a94a24ecfdb45a3cab536d2f9'
 assert sha(DESIGN/'SAMPLE_BINDING.json')=='4ad5b278150ba8c67b730073038e1cbffbe8973570bb39509d6f766ff1fe8213'
 # Freeze before opening any forward price values. Near-zero is one original
 # A-share quote quantum per share, descriptive only; never average R ratios.
 freeze=dict(design_sha256=sha(DESIGN/'DESIGN.txt'),sample_sha256=sha(DESIGN/'SAMPLE_BINDING.json'),code_sha256=sha(__file__),horizons=[5,21],primary=21,
  fixed_market_session_endpoints=True,risk_near_zero_per_raw_share_yuan='0.01',risk_ratios_not_pooled=True,financial_events=0,new_indicators=0,before_new_forward_price_read=True)
 if not (O/'PRE_LABEL_FREEZE.json').exists():save(O/'PRE_LABEL_FREEZE.json',freeze)
 else:
  original=read(O/'PRE_LABEL_FREEZE.json');assert all(original[k]==freeze[k] for k in ['design_sha256','sample_sha256','horizons','primary','risk_near_zero_per_raw_share_yuan'])
  save(O/'CORRECTED_ANALYSIS_BINDING.json',dict(original_freeze_sha256=sha(O/'PRE_LABEL_FREEZE.json'),corrected_code_sha256=sha(__file__),analysis_errata_sha256=sha(O/'ANALYSIS_ERRATA.json'),not_an_outcome_blinded_new_hypothesis=True,horizons_and_cases_unchanged=True))
 batches=read(COVER/'BATCHES.json');pidx={r['sid']:r for r in read(PRICE_AUDIT)};cache={};allrows=[];summaries=[];sources={str(COVER/'BATCHES.json'):sha(COVER/'BATCHES.json')}
 fullmanifest=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/manifest.json')
 for rec in read(fullmanifest)['series']:
  if rec['series_id'] not in pidx:pidx[rec['series_id']]=dict(path=str(fullmanifest.parent/rec['files']['signal']['path']),SHA256=rec['files']['signal']['sha256'])
 sources[str(fullmanifest)]=sha(fullmanifest)
 roots={'2025':R/'g-s-C-AugSep-continuation-readiness-20261102/inputs','2022':R/'g-s-C-month-continuation-20261102/inputs/2022'}
 dates={k:{c['signal_close'][:10] for c in design['cases'] if c['signal_close'][:4]==k} for k in roots}
 tables={y:{k:table(root,k,dates[y]) for k in ['facts','cp','pvr','h1']} for y,root in roots.items()}
 starts={k:{c['common_start'][:10] for c in design['cases'] if c['signal_close'][:4]==k} for k in roots}
 open_factors={y:table(root,'facts',starts[y]).set_index(['sid','day'])['factor'] for y,root in roots.items()}
 rules=read(roots['2025']/'rules.json');market_days=sorted({d[:10] for d in rules['calendars']['A']})
 meta=read(roots['2025']/'metadata.json');secnames={r['sector']:r['name'] for r in read(R/'g-s-C-month-continuation-20261102/july_end_analysis/MARKET_SECTORS.json')}
 jan=read(JAN/'2022-C10-EXTRACT.json');aug_layers={a:{r['layer']:r for r in read(R/'g-s-C-August-continuation-v1-20261102/analysis'/(a+'-LAYERS.json'))} for a in ['C10','C20']}
 for case in design['cases']:
  arm=case['arm'];day=case['signal_close'][:10];start=case['common_start'][:10];y=day[:4]
  if y=='2025':
   batch=next(b for b in batches if b['certificate']==case['certificate'] and b['cell']==arm)
   path=(R/'g-s-C-August-continuation-v1-20261102/runs'/arm/(day+'-CLOSE.json')) if day[5:7]=='08' else (R/'g-s-C-month-continuation-20261102/runs/2025_26-C10'/(day+'-CLOSE.json'))
  else:
   cert=jan['certificates'][case['certificate']];jt={z['receipt_id']:z for z in jan['account']['trades']}
   buys=copy.deepcopy(case['full_receiver_buys'])
   for f in buys:
    oid=next(k for k,s in jan['account']['supports'].items() if s.get('C_certificate')==case['certificate'] and s['original_intent']['sid']==f['security_id'])
    lids=[int(lid) for lid,z in jan['account']['capital_meta'].items() if z.get('order')==oid];assert len(lids)==1;f['layer']=lids[0]
   batch=dict(Q=cert['Q'],D=cert['D'],source_fills=[dict(f,parts=jt[f['receipt_id']]['parts']) for f in case['full_source_sales']],same_certificate_C_buys=buys)
   path=R/'g-s-C-month-continuation-20261102/runs/2022-C10'/(day+'-CLOSE.json')
  sources[str(source_path(path))]=sha(source_path(path));state=read(path);a=state['account'];layers={z['id']:z for z in a['layers']}
  result=next(r['projection'] for r in reversed(state['results']) if r['certificate']['certificate_id']==case['certificate'])
  rank=result['C_rank_binding']['stock_priority'];pending={i['sid']:i for i in state['pending']};ff={}
  for k,f in tables[y].items():ff[k]=f[f.day==day].set_index('sid')
  sectors=sorted(a['policy']['scopes']);hh=ff['h1'];sector_scores={s:float(hh.loc[s,'score']) for s in sectors if s in hh.index and s!='G' and finite(hh.loc[s,'score'])}
  horder=sorted(sector_scores,key=lambda s:(-round(sector_scores[s],12),s));hrank={s:i+1 for i,s in enumerate(horder)}
  sale_by={};buy_by={}
  for f in batch['source_fills']:sale_by.setdefault(f['security_id'],[]).append(f)
  for f in batch['same_certificate_C_buys']:buy_by.setdefault(f['security_id'],[]).append(f)
  case_rows=[]
  for side,domain in [('D',batch['D']),('Q',{s:q for s,q in batch['Q'].items() if q})]:
   for sid,approved in domain.items():
    fills=(sale_by if side=='D' else buy_by).get(sid,[]);q=sum(f['shares'] for f in fills);gross=sum(float(f['gross_cny']) for f in fills);fees=sum(float(f['fees_cny']) for f in fills)
    facts=clean(ff['facts'].loc[sid].to_dict()) if sid in ff['facts'].index else {};cp=clean(ff['cp'].loc[sid].to_dict()) if sid in ff['cp'].index else {}
    sec=meta[sid]['sector'];scope=a['policy']['scopes'].get(sec,{});context=scope.get('context');proofs=[v for v in a['policy']['proof_history'] if v['scope']==sec and v.get('context')==context and v['kind']=='price_advance' and v['confirmed']<=a['policy']['cursor']]
    signal=dict(name=meta[sid]['name'],sector=sec,sector_name=secnames.get(sec),sector_H1=sector_scores.get(sec),sector_H1_rank90=hrank.get(sec),sector_rank_denominator=len(horder),F1=scope,last_context_price_advance=str(date.fromordinal(max(v['confirmed'] for v in proofs))) if proofs else None,
      stock_H1=float(hh.loc[sid,'score']) if sid in hh.index and finite(hh.loc[sid,'score']) else None,
      PVR=float(ff['pvr'].loc[sid,'score']) if sid in ff['pvr'].index and finite(ff['pvr'].loc[sid,'score']) else None,
      original_key=rank.get(sid,{}).get('original_key'),C_key=rank.get(sid,{}).get('C_key'),
      I_target=facts.get('i_target'),E0_target=facts.get('e0_target'),G1_grade=facts.get('g_grade'),G1_ready=facts.get('g_ready'),G1_fresh_up=facts.get('g_fresh_up'),G1_acute_down=facts.get('g_acute_down'),
      CP1_phase=cp.get('phase'),CP1_reset_reason=cp.get('reset_reason'),CP1_delta_frontier=cp.get('delta_frontier'),CP1_market_receipt=cp.get('receipt'),
      CP1_frontier=cp.get('frontier'),asof=case['signal_close'],fresh_is_execution_not_hold_strength=True)
    f=prices(sid,pidx,cache);labs={str(h):label(f,start,case['label_end_'+str(h)],market_days) for h in [5,21]};p0=float(f.loc[pd.Timestamp(start),'raw_open'])
    # Original HistoricalMarket.refresh reads only this original factor field
    # at OPEN. It is not the buy-day CLOSE I/G1/CP1 or a terminal layer line.
    factor_open=D(str(open_factors[y].loc[(sid,start)])) if (sid,start) in open_factors[y].index and finite(open_factors[y].loc[(sid,start)]) else D(a['market_factors'][sid])
    units=[];risk=Z;knownrisk=True;actual=bool(q);actual_out=[]
    if side=='D':
     parts=[(fill,part) for fill in fills for part in fill.get('parts',[])];use_qty=q
     assert not q or parts,'actual sold quantity missing exact native layer parts'
     for fill,part in parts:
      lid=part['layer'];z=layers[lid];floor=(D(a['facts_floors'][sid]) if z['kind']=='core' else D(z['floor']))/factor_open
      rr,lockids,err=oldrisk(a,lid,part['shares'],fill['at'],p0,float(floor))
      knownrisk &= rr is not None
      if rr is not None:risk+=D(str(rr))
      cm=a['capital_meta'][str(lid)];unrealized_before=float((D(str(p0))-D(cm['unit_cost']))*part['shares'])
      units.append(dict(layer=lid,shares=part['shares'],role=cm['role'],pool=cm['pool'],purpose=cm['purpose'],opened=z['opened'],floor_raw=str(floor),native_lock_risk=rr,lock_ids=lockids,unknown=err,price_gain_before_sell_after_buyfees=unrealized_before))
      if y=='2025':
       tr=next(r for r in batch['source_sell_parts'] if r['receipt']==fill['receipt_id'] and r['layer']==lid);actual_out.append(tr)
      else:
       cost=D(cm['unit_cost'])*part['shares'];actual_out.append(dict(layer=lid,shares=part['shares'],realized_trade_PNL=str(D(part['net_cash'])-cost),fee_cny=str(part['fee_cny']),at=fill['at']))
    else:
     i=pending.get(sid);floor=max(D(i['I_floor']),D(i['cp_floor']))/factor_open if i else None
     for fill in fills:
      # Use saved actual entry floor, not later ratchets or retrospective CP1.
      assert floor is not None,'missing original authorization floor'
      fl=floor;rr=D(fill['shares'])*max(Z,D(str(fill['gross_cny']))/fill['shares']-fl);risk+=rr
      use='G' if state['active']['receipt_bindings'][sid]['market_context']==a['policy']['scopes'].get('G',{}).get('context') else 'S'
      units.append(dict(layer=fill.get('layer'),shares=fill['shares'],role='mobile',pool='confirmed',purpose=use,floor_raw=str(fl),native_entry_risk=str(rr),mapping_later_layer_floor_not_used=fill.get('floor'),source_original_intent=True,open_factor=str(factor_open)))
      if y=='2025':actual_out.append(next(z for z in batch['C_receiver_actual_layer_outcomes_through_Aug29'] if z['layer']==fill['layer']))
      else:
       oid=next(k for k,s in jan['account']['supports'].items() if s.get('C_certificate')==case['certificate'] and s['original_intent']['sid']==sid);lids=[lid for lid,m in jan['account']['capital_meta'].items() if m.get('order')==oid]
       for lid in lids:
        zz=next(z for z in jan['account']['layers'] if z['id']==int(lid));actual_out.append(dict(layer=int(lid),closed=zz.get('closed'),net_layer_cash=zz['cash'],booked_dividend=zz['dividend'],qty=zz['qty'],total_closed_contribution=str(D(zz['cash'])+D(zz['dividend'])) if not zz['qty'] else None))
     use_qty=q
     if not fills:units.append(dict(shares=0,role='mobile',pool='confirmed',floor_raw=str(floor) if floor is not None else None,actual_entry_risk=None,not_filled=True))
    ratio=float(risk)/(use_qty*p0) if knownrisk and use_qty and risk>0 else None
    near=bool(use_qty and knownrisk and risk/D(use_qty)<=D('.01'))
    for h,z in labs.items():
     z['price_change_per_fixed_nominal_risk']=((z['return_pct']/100)/ratio if z.get('valid') and ratio and not near else None)
     z['risk_ratio_not_a_trade_size_or_PNL']=True
    # Corporate-action annotations only. They do not modify saved signals.
    invrec=INV[sid];events=read(invrec['refs']['actions'])['events'] if invrec['refs'].get('actions') else []
    events=[e for e in events if start<=e['effective_date']<=case['label_end_21']]
    row=dict(case=case['certificate'],arm=arm,signal_close=case['signal_close'],start=start,side=side,sid=sid,signal=signal,
      approved_qty=approved,actual_qty=q,actual_gross=gross,actual_fee=fees,actual_filled=actual,actual_equal_weight=1 if actual else 0,
      all_Q_or_D_equal_weight=1,actual_units=units,fixed_native_risk=str(risk) if knownrisk and use_qty else None,
      fixed_risk_fraction=ratio,zero_risk=bool(use_qty and knownrisk and risk==0),near_zero_per_share_one_fen=near,
      risk_unknown=not knownrisk,labels=labs,actual_account_outcomes=actual_out,corporate_actions_in_label_window=events,
      funding_arrow_not_per_dollar=True,not_executable_counterfactual=True)
    case_rows.append(row);allrows.append(row)
  summary=dict(certificate=case['certificate'],arm=arm,signal_close=case['signal_close'],start=start,representative_old=case['representative_old'],representative_new=case['representative_new'],source_D=len(batch['D']),target_Q=sum(q>0 for q in batch['Q'].values()),actual_source_stocks=len(sale_by),actual_receiver_stocks=len(buy_by),labels={},static_basket_paths={})
  for h in [5,21]:
   by={side:[z for z in case_rows if z['side']==side] for side in ['D','Q']}
   summary['labels'][str(h)]={side:{w:{field:weighted(by[side],h,field,w) for field in ['return_pct','close_MAE_pct','close_MFE_pct']} for w in ['actual_gross','actual_equal_weight','all_Q_or_D_equal_weight']} for side in by}
   summary['static_basket_paths'][str(h)]={side:{w:basket_path(by[side],h,w) for w in ['actual_gross','actual_equal_weight','all_Q_or_D_equal_weight']} for side in by}
  save(O/'cases'/(arm+'-'+day+'.json'),dict(summary=summary,original_Q=batch['Q'],original_D=batch['D'],rows=case_rows))
  summaries.append(summary);print('CASE_DONE',arm,day,len(case_rows),'5/21labels',flush=True)
 save(O/'ALL_ROWS.json',allrows);save(O/'SUMMARY.json',summaries)
 save(O/'CHECKS.json',dict(financial_events=0,new_indicators=0,price_archives=len(cache),label_rows=len(allrows),all_D_and_positive_Q_preserved=True,
  all_actual_holdings_and_source_files_unchanged=all(sha(p)==h for p,h in {**sources,**USED_SOURCES}.items()),source_sha256={**sources,**USED_SOURCES,str(FILTER_PATH):sha(FILTER_PATH)},
  price_source_sha256={sid:pidx[sid]['SHA256'] for sid in cache},elapsed_seconds=time.monotonic()-t,
  all_price_horizons_frozen=True,risk_ratio_aggregate_statistics=False,
  invalid_labels=[dict(case=r['case'],side=r['side'],sid=r['sid'],h=h,reason=z['reason']) for r in allrows for h,z in r['labels'].items() if not z.get('valid')]))

INV={r['symbol']:r for r in read(Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json'))}
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
