"""Expand three existing capital batches with same-time saved evidence.
No account/event/selector call, no new forward price labels or order proposal.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import date
import json,gzip,hashlib,sys,math
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'_shared'));import research_output_io as IO
COV=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/pre-sell-quote-coverage-readonly-20261102')
JAN=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-difference-readonly-20261102')
USED={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);a=p if p.exists() else Path(str(p)+'.gz');USED[str(a.resolve())]=sha(a)
 return json.loads(p.read_text()) if p.exists() else json.loads(gzip.open(str(p)+'.gz','rt').read())
def save(p,x):IO.write_json(p,json.loads(json.dumps(x,ensure_ascii=False,default=str)))
def finite(x):return x is not None and pd.notna(x) and math.isfinite(float(x))
def table(root,k,days):
 m=read(root/'MANIFEST.json');parts=[]
 for g in ['files','extensions','month_extension','continuation_extension']:
  if k not in m.get(g,{}):continue
  r=m[g][k];p=root/r['path'];assert sha(p)==r['sha256'];USED[str(p.resolve())]=r['sha256'];f=pd.read_parquet(p);parts.append(f[f.day.isin(days)])
 return pd.concat(parts,ignore_index=True).drop_duplicates(['sid','day'],keep='last')
def main():
 bs=read(COV/'BATCHES.json');jan=read(JAN/'2022-C10-EXTRACT.json')
 roots={'2025':R/'g-s-C-AugSep-continuation-readiness-20261102/inputs','2022':R/'g-s-C-month-continuation-20261102/inputs/2022'}
 dates={'2025':{'2025-08-07','2025-08-13','2025-08-15'},'2022':{'2022-01-12'}}
 caches={y:{k:table(p,k,dates[y]).set_index(['sid','day']) for k in ['facts','cp','pvr','h1']} for y,p in roots.items()}
 factors={y:table(p,'facts',{'2025-08-08','2025-08-14','2025-08-18'} if y=='2025' else {'2022-01-13'}).set_index(['sid','day'])['factor'] for y,p in roots.items()}
 meta=read(roots['2025']/'metadata.json');names={z['sector']:z['name'] for z in read(R/'g-s-C-month-continuation-20261102/july_end_analysis/MARKET_SECTORS.json')}
 configs=[('C10','2025-08-15','2025-08-18'),('C20','2025-08-07','2025-08-08'),('2022-C10','2022-01-12','2022-01-13')];results=[]
 for arm,day,op in configs:
  y=day[:4]
  if y=='2025':
   b=next(z for z in bs if z['cell']==arm and z['original_plan_at'][:10]==day);p=R/'g-s-C-August-continuation-v1-20261102/runs'/arm/(day+'-CLOSE.json')
  else:
   cid='3c97a50113f10c549cf6b1f61f6c01c91420fdc618d0ba2ad85b8e4254fdd812';c=jan['certificates'][cid];fills=[f for f in jan['fills'] if f['at'][:10]==op];tr={t['receipt_id']:t for t in jan['account']['trades']};b=dict(certificate=cid,Q=c['Q'],D=c['D'],source_fills=[dict(f,parts=tr[f['receipt_id']]['parts']) for f in fills if f['side']=='sell'],same_certificate_C_buys=[f for f in fills if f['side']=='buy' and f['security_id'] in c['Q']]);p=R/'g-s-C-month-continuation-20261102/runs/2022-C10'/(day+'-CLOSE.json')
  state=read(p);a=state['account'];cert=state['active'];assert cert['certificate_id']==b['certificate'];pr=next(z['projection'] for z in state['results'] if z['certificate']['certificate_id']==cert['certificate_id']);rk=pr['C_rank_binding']['stock_priority'];pending={i['sid']:i for i in state['pending']};ls={z['id']:z for z in a['layers']}
  h=caches[y]['h1'].xs(day,level='day');secs=[s for s in a['policy']['scopes'] if s!='G'];sr=sorted(secs,key=lambda s:(-round(float(h.loc[s,'score']),12),s));sector_rank={s:i+1 for i,s in enumerate(sr)}
  rows=[]
  for side,dom in [('D',b['D']),('Q',{s:q for s,q in b['Q'].items() if q})]:
   for sid,approved in dom.items():
    f=caches[y]['facts'].loc[sid,day];cp=caches[y]['cp'].loc[sid,day];sec=meta[sid]['sector'];sc=a['policy']['scopes'][sec];factor=D(a['market_factors'][sid]);mark=D(a['market_marks'][sid]);units=[]
    if side=='D':
     for z in pr['donors']['rows']:
      if z['sid']!=sid:continue
      old=ls[z['layer']];cm=a['capital_meta'][str(z['layer'])];floor=D(old['floor'])/factor;duties=[dict(eid=e['eid'],qty=e['remaining'],reasons=a['exit_duties'][e['eid']]['reasons']) for e in a['policy']['locks'].values() if e['lot']==z['layer'] and e['remaining']]
      units.append(dict(layer=z['layer'],qty=z['q'],total_layer_qty=old['qty'],floor_raw=str(floor),held_since=old['opened'],entry_price=cm['unit_cost'],I_valid=bool(f.i_target==1),price_above_floor=mark>floor,role=cm['role'],pool=cm['pool'],purpose=cm['purpose'],duties=duties))
    else:
     i=pending[sid];floor=max(D(i['I_floor']),D(i['cp_floor']))/factor;units=[dict(qty=approved,floor_raw=str(floor),role='mobile',pool='confirmed',purpose='S' if cert['receipt_bindings'][sid]['market_context']==sc['context'] else 'G')]
    ff=(b['source_fills'] if side=='D' else b['same_certificate_C_buys']);actual=[z for z in ff if z['security_id']==sid];q=sum(z['shares'] for z in actual);gross=sum(D(z['gross_cny']) for z in actual)
    open_factor=D(str(factors[y].loc[sid,op])) if (sid,op) in factors[y].index and finite(factors[y].loc[sid,op]) else factor
    entryline=(max(D(pending[sid]['I_floor']),D(pending[sid]['cp_floor']))/open_factor) if side=='Q' else None
    pv=float(caches[y]['pvr'].loc[(sid,day),'score']);stockh=float(h.loc[sid,'score']);proofs=[v for v in a['policy']['proof_history'] if v['scope']==sec and v.get('context')==sc['context'] and v['kind']=='price_advance' and v['confirmed']<=a['policy']['cursor']]
    row=dict(side=side,sid=sid,name=meta[sid]['name'],industry=names[sec],sector=sec,industry_H1=float(h.loc[sec,'score']),industry_H1_rank=sector_rank[sec],F1=dict(permit=sc['permit'],support=sc['support'],mature=sc['mature'],context=sc['context']),last_industry_advance=str(date.fromordinal(max(v['confirmed'] for v in proofs))) if proofs else None,
      mark_close=str(mark),floor_close=str(floor),line_distance_close_pct=float((mark-floor)/mark*100),PVR=pv,stock_H1=stockh,G1_grade=float(f.g_grade),G1_ready=bool(f.g_ready),G1_warm_original=bool(f.g_ready and f.g_grade>=2),G1_acute_down=bool(f.g_acute_down),I_target=float(f.i_target),E0_target=float(f.e0_target),
      CP1_market_fresh=bool(cp.receipt),CP1_phase=str(cp.phase),CP1_reset_reason=str(cp.reset_reason) if pd.notna(cp.reset_reason) else None,CP1_delta_frontier=float(cp.delta_frontier),original_key=rk[sid]['original_key'],C_key=rk[sid]['C_key'],authorized_qty=approved,actual_qty=q,actual_gross=str(gross),
      actual_price=str(gross/q) if q else None,open_entry_floor=str(entryline) if entryline else None,
      actual_open_line_distance_pct=float((gross/D(q)-entryline)/(gross/D(q))*100) if side=='Q' and q else None,units=units)
    rows.append(row)
  edges=[dict(old=d['sid'],new=n['sid'],new_PVR_stronger=n['PVR']>d['PVR'],new_stock_H1_not_lower=n['stock_H1']>=d['stock_H1'],
    same_scale_PVR_H1_dominance=n['PVR']>=d['PVR'] and n['stock_H1']>=d['stock_H1'] and (n['PVR']>d['PVR'] or n['stock_H1']>d['stock_H1']),old_original_G1_still_warm=d['G1_warm_original'],
    diagnostic_only_not_a_new_funding_permission=True) for d in rows if d['side']=='D' for n in rows if n['side']=='Q']
  results.append(dict(arm=arm,day=day,open_day=op,certificate=cert['certificate_id'],original_Q=cert['Q'],original_D=cert['D'],rows=rows,edge_comparisons=edges,
    original_actual_source_gross=b.get('actual_source_gross'),original_actual_receiver_gross=b.get('actual_C_receiver_gross'),original_actual_receiver_outcomes=b.get('C_receiver_outcomes'),
    planning=dict(available=a['balance']['available'],decision_nav=a['policy']['nd'],actual_resources=a['balance']['resources'],donor_cash_need=pr['donors']['raw_need'],conditional_plan_is_not_cash=True),state_unchanged=True))
  print('BATCH',arm,day,'D/Q',len(b['D']),sum(q>0 for q in b['Q'].values()),flush=True)
 # Original Aug13 values for the same mid layer's evidence clock.
 six=read(R/'replacement-quality-six-batches-v2-20261102/ALL_ROWS.json');mid13=next(r for r in six if r['arm']=='C10' and r['signal_close'][:10]=='2025-08-13' and r['sid']=='300308.SZ')
 audit=read('/tmp/replacement-six-independent-20261102/FINAL_AUDIT.json')['middle_chain']
 save(O/'THREE_BATCHES.json',results);save(O/'MIDDLE_TIMELINE.json',dict(Aug13_entry_evidence=mid13['signal'],entry_units=mid13['actual_units'],Aug15_evidence=next(r for r in results[0]['rows'] if r['sid']=='300308.SZ'),actual_layer_chain=audit,
   original_current_G1_formula_source='/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:18'))
 save(O/'SOURCE_CHECKS.json',dict(financial_events=0,new_price_labels=0,new_indicators=0,no_selector_or_order_call=True,sources_sha256=USED,all_unchanged=all(sha(p)==h for p,h in USED.items()),original_model_source_sha256=sha('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py')))
if __name__=='__main__':main()
