"""One observational test of the externally fixed F OR same-signal-or-later CP gate.
No strategy engine import/run, no portfolio allocation, no alternative thresholds."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,csv,hashlib,math,copy
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=ROOT/'mainline_seed_entry_diagnostic_v1';B=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630'
Z=D(0);END='2025-01-20';hashes={}
def rd(p):
 h=hashlib.sha256(p.read_bytes()).hexdigest();hashes[str(p)]=h;return json.loads(p.read_text())
def save(n,x):
 (O/('GATE_'+n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/('GATE_'+n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def dec(x):return D(str(x))
def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except:return False
def tri(x):
 if pd.isna(x):return -1
 return 1 if x in (True,1) else 0 if x in (False,0) else -1
def OR(a,b):return 1 if 1 in [a,b] else -1 if -1 in [a,b] else 0
def lin(r):
 vals=[r.get(c) for c in ['source_kind','source_path','segment_id']]
 return None if any(pd.isna(v) or str(v)=='' for v in vals) else tuple(str(v) for v in vals)
def valid(r):return all(tri(r.get(c))==1 for c in ['observed_bar','price_eligible','volume_eligible']) and tri(r.get('source_invalid'))==0 and tri(r.get('synthetic_event_bar'))==0
def row(frame,dt):return frame.loc[dt] if dt in frame.index else pd.Series(dtype=object)
def receipt_tri(x):return int(x) if isinstance(x,(bool,np.bool_)) else -1
def bump(st,key,condition=True):
 if condition:st['audit'][key]=st['audit'].get(key,0)+1
MODEL_PATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
MODEL_SHA256=hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
assert MODEL_SHA256=='85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf'
hashes[str(MODEL_PATH)]=MODEL_SHA256
CONTRACT=ROOT/'mainline_structural_maturity_design_v1/DESIGN.md'
assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest()=='79ebeb73457914656eb70e4ecb59a58008e57d7cb92dd1296dd86d3577efbe12'
hashes[str(CONTRACT)]=hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
source_hashes=rd(B/'SOURCE_HASHES.json')
allrows=rd(O/'FILLED_SEED_CLASSIFICATION.json');rows=[r for r in allrows if r['phase']=='MATURE']
orders=rd(B/'ORDERS.json');seed={x['round_id']:x for x in orders if x['side']=='BUY_SEED'}
sec={(x['day'],x['sector51']):x for x in rd(B/'SECTOR_DAILY.json')}
days=sorted({x[0] for x in sec});di={d:i for i,d in enumerate(days)}
manifest_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
manifest={x['symbol']:x for x in rd(manifest_path)}
admission={(x['sid'],x['ex_date']):x for x in rd(B/'EVENT_ADMISSION.json')}
# Purely local hash-bound approved adapters, never their URL fields.
adapter=defaultdict(list)
def walk(x):
 if isinstance(x,list):
  for a in x:walk(a)
 elif isinstance(x,dict):
  if all(k in x for k in ['sid','ex_date','factor_old','factor_new']):adapter[(x['sid'],x['ex_date'])].append(x)
  for k,v in x.items():
   if isinstance(v,(dict,list)):walk(v)
for p,h in source_hashes.items():
 if p.endswith('.json') and any(t in Path(p).name for t in ['EVENT_ADAPTER_CANDIDATES','EXTRA_REVIEWED_EQUITY_EVENTS','ADDITIONAL_REVIEWED_EVENTS','REVIEWED_CASH_EVENTS','EXACT_CASH_BATCH_MANIFEST']):
  pp=Path(p);assert hashlib.sha256(pp.read_bytes()).hexdigest()==h;walk(rd(pp))
ids=sorted({r['sid'] for r in rows});frames={};facts={};cps={};actions={}
def parquet(p,expected=None,columns=None):
 pp=Path(p);h=hashlib.sha256(pp.read_bytes()).hexdigest();hashes[str(pp)]=h
 if expected:assert h==expected,('SOURCE_DRIFT',p)
 return pd.read_parquet(pp,columns=columns)
Q=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
kp=Q/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet';rp=kp.with_name('RIGHT3.parquet');pp=Q/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'
known=parquet(kp,source_hashes[str(kp)],ids);right=parquet(rp,source_hashes[str(rp)],ids)
ps=parquet(pp,source_hashes[str(pp)],['sid','day','state']);ps=ps[ps.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=known.index,columns=ids);known &= ps.ge(0)
for sid in ids:
 m=manifest[sid];hs={**m['source_sha256'],**m['output_sha256']}
 p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 frames[sid]=parquet(p,hs[p]).loc[:END];facts[sid]=parquet(m['refs']['facts'],hs[m['refs']['facts']]).loc[:END];cps[sid]=parquet(m['refs']['CP1'],hs[m['refs']['CP1']]).loc[:END]
 ap=next(p for p in source_hashes if p.endswith('/inputs-v1/actions/'+sid+'.json'))
 assert hashlib.sha256(Path(ap).read_bytes()).hexdigest()==source_hashes[ap]
 actions[sid]={x['effective_date']:x for x in rd(Path(ap))['events']}
def stock(sid,dt):
 if dt not in known.index or sid not in known.columns or tri(known.at[dt,sid])!=1:return -1
 return tri(right.at[dt,sid])
def make_state(r):
 z=row(frames[r['sid']],pd.Timestamp(r['signal_day']));factor=z.get('adjustment_factor')
 return dict(sid=r['sid'],signal_day=r['signal_day'],origin=lin(z),factor=dec(factor) if finite(factor) and factor>0 else None,ifloor=None,slot=None,cp_update_unknown=False,cancelled=None,blocked=None,unknown=None,log=[],bridges=[],audit={})
def event(st,ds,phase,typ,**kw):st['log'].append(dict(day=ds,phase=phase,event=typ,**kw))
def preflight(st,ds):
 st['unknown']=None
 if st.get('preflight_day')==ds:return True
 sid=st['sid'];dt=pd.Timestamp(ds);z=row(frames[sid],dt);origin=lin(z)
 if origin is None or st['origin'] is None:st['unknown']='SOURCE_UNKNOWN';return False
 if origin!=st['origin']:st['cancelled']='SOURCE_CHANGED';st['slot']=None;st['cp_update_unknown']=False;event(st,ds,'PREFLIGHT','CANCEL_SOURCE_CHANGED');return False
 factor=z.get('adjustment_factor')
 if not finite(factor) or factor<=0 or st['factor'] is None:st['unknown']='FACTOR_UNKNOWN';return False
 new=dec(factor)
 if ds>st['signal_day'] and (abs(new/st['factor']-1)>D('1e-11') or ds in actions[sid]):
  pair=(sid,ds)
  if pair not in admission:st['blocked']='UNADMITTED_EQUITY_OR_FACTOR';return False
  a=adapter.get(pair,[])
  matches=[x for x in a if abs(st['factor']/dec(x['factor_old'])-1)<=D('1e-11') and abs(new/dec(x['factor_new'])-1)<=D('1e-11')]
  if not matches:st['blocked']='ADMITTED_BRIDGE_EXACT_PAIR_NOT_RECONSTRUCTED';return False
  st['bridges'].append(dict(day=ds,factor_old=str(st['factor']),factor_new=str(new),admitted=True,CP_floor_not_rescaled=True))
 st['factor']=new;st['preflight_day']=ds;return True
def cp_check_price(st,ds,field,phase):
 z=row(frames[st['sid']],pd.Timestamp(ds));cp=st['slot'];price=z.get(field);factor=z.get('adjustment_factor');origin=lin(z)
 if cp is None or cp['invalid']:return
 if not valid(z) or not finite(price) or price<=0 or not finite(factor) or factor<=0 or origin is None:
  cp['history_unknown']=True;event(st,ds,phase,'CP_HISTORY_UNKNOWN',cp_id=cp['id']);return
 if origin!=tuple(cp['origin']):cp['invalid']=True;event(st,ds,phase,'CP_SOURCE_INVALID',cp_id=cp['id']);return
 px=dec(price)*dec(factor)
 if px<=dec(cp['floor']):cp['invalid']=True;event(st,ds,phase,'CP_PRICE_BREACHED',cp_id=cp['id'],price=str(px),floor=cp['floor'])
def cp_state(st):
 cp=st['slot']
 return -1 if st['cp_update_unknown'] else 0 if cp is None or cp['invalid'] else -1 if cp['history_unknown'] else 1
def failed_preflight(st):return dict(base='CANCEL' if st['cancelled'] else 'BLOCKED' if st['blocked'] else 'UNKNOWN',reason=st['cancelled'] or st['blocked'] or st['unknown'])
def at_open(st,ds):
 if st['cancelled'] or st['blocked']:return failed_preflight(st)
 z=row(frames[st['sid']],pd.Timestamp(ds));price=z.get('raw_open');factor=z.get('adjustment_factor')
 bump(st,'OPEN_visits');bump(st,'OPEN_raw_row_missing',z.empty);bump(st,'OPEN_source_unknown',lin(z) is None);bump(st,'OPEN_factor_unknown',not finite(factor) or factor<=0);bump(st,'OPEN_quote_unknown',not valid(z) or not finite(price) or price<=0)
 ok=preflight(st,ds)
 cp_check_price(st,ds,'raw_open','OPEN')
 if not ok:return failed_preflight(st)
 if not valid(z) or not finite(price) or price<=0:return dict(base='UNKNOWN',reason='OPEN_PRICE_UNKNOWN')
 px=dec(price)*dec(factor)
 if st['ifloor'] is not None and px<=st['ifloor']:
  st['cancelled']='OPEN_BELOW_I_PROTECTION';st['slot']=None;st['cp_update_unknown']=False;event(st,ds,'OPEN','CANCEL_I_PROTECTION');return dict(base='CANCEL',reason=st['cancelled'])
 return dict(base='PASS',CP_state=cp_state(st),adjusted_open=str(px))
def at_close(st,ds,sector):
 sid=st['sid'];dt=pd.Timestamp(ds);z=row(frames[sid],dt);f=row(facts[sid],dt);c=row(cps[sid],dt);s=sec.get((ds,sector),dict(state=-1,M=-1,F=-1,S=-1,E=None))
 if st['cancelled'] or st['blocked']:return failed_preflight(st)
 it=tri(f.get('i_target'));ss=stock(sid,dt);stsec=s['state'];iline=f.get('i_floor');current_floor_valid=finite(iline) and iline>0
 rt=receipt_tri(c.get('receipt'));price=z.get('raw_close');factor=z.get('adjustment_factor')
 bump(st,'CLOSE_visits');bump(st,'CLOSE_raw_row_missing',z.empty);bump(st,'CLOSE_facts_row_missing',f.empty);bump(st,'CLOSE_CP_row_missing',c.empty);bump(st,'CLOSE_source_unknown',lin(z) is None);bump(st,'CLOSE_factor_unknown',not finite(factor) or factor<=0);bump(st,'CLOSE_receipt_unknown',rt<0);bump(st,'CLOSE_I_true_floor_invalid',it==1 and not current_floor_valid);bump(st,'CLOSE_original_state_unknown',-1 in [it,ss,stsec])
 # Original known false always cancels, even alongside quote/source/receipt unknown.
 why='I_FALSE' if it==0 else 'SECTOR_FALSE' if stsec==0 else 'STOCK_FALSE' if ss==0 else None
 if why:
  st['cancelled']=why;st['slot']=None;st['cp_update_unknown']=False;event(st,ds,'CLOSE','CANCEL_'+why);return dict(base='CANCEL',reason=why,stock_state=ss,sector_state=stsec,I_state=it,M=s['M'],F=s['F'])
 ok=preflight(st,ds)
 # Invalidate prior slot before processing this CLOSE receipt. Unknown price history sticks.
 cp_check_price(st,ds,'raw_close','CLOSE')
 if not ok:
  if not st['cancelled'] and not st['blocked']:
   st['cp_update_unknown']=True;event(st,ds,'CLOSE','CP_UPDATE_HISTORY_UNKNOWN',reason=st['unknown'])
  return dict(**failed_preflight(st),CP_state=cp_state(st),F=s['F'],S=s['S'],M=s['M'],gate=OR(s['F'],cp_state(st)),stock_state=ss,sector_state=stsec,I_state=it)
 if it==1 and current_floor_valid:st['ifloor']=max(st['ifloor'] or Z,dec(iline))
 px=dec(price)*dec(factor) if finite(price) and price>0 else None
 if px is not None and st['ifloor'] is not None and valid(z) and px<=st['ifloor']:
  st['cancelled']='I_PROTECTION_BREACHED';st['slot']=None;st['cp_update_unknown']=False;event(st,ds,'CLOSE','CANCEL_I_PROTECTION_BREACHED');return dict(base='CANCEL',reason=st['cancelled'],stock_state=ss,sector_state=stsec,I_state=it,M=s['M'],F=s['F'])
 valid_scale=bool(valid(z) and px is not None and finite(f.get('close')) and f.get('close')>0 and abs(px/dec(f.get('close'))-1)<=D('1e-10') and lin(z)==st['origin'])
 bump(st,'CLOSE_quote_or_scale_unknown',not valid_scale)
 receipt_known=rt>=0;candidate=c.get('candidate')
 if rt==1 and (not finite(candidate) or candidate<=0 or not valid_scale):receipt_known=False;bump(st,'CLOSE_true_receipt_invalid_candidate_or_scale')
 if not receipt_known:
  st['cp_update_unknown']=True;event(st,ds,'CLOSE','CP_UPDATE_HISTORY_UNKNOWN',reason='RECEIPT_OR_CANDIDATE_UNKNOWN')
 if rt==1 and receipt_known:
  fl=dec(candidate);identity=hashlib.sha256(json.dumps(['ENTRY_CP',sid,ds,str(fl),st['origin'],MODEL_SHA256]).encode()).hexdigest()[:24]
  if px>fl:
   old=st['slot'];st['slot']=dict(id=identity,receipt_day=ds,floor=str(fl),origin=st['origin'],model_sha256=MODEL_SHA256,invalid=False,history_unknown=False);st['cp_update_unknown']=False
   event(st,ds,'CLOSE','CREATE_OR_REPLACE',cp_id=identity,floor=str(fl),superseded=old['id'] if old else None)
  else:event(st,ds,'CLOSE','RECEIPT_ALREADY_BREACHED_KEEP_PRIOR_SLOT',cp_id=identity,floor=str(fl),price=str(px))
 cp=st['slot'];cpstate=cp_state(st)
 base='UNKNOWN' if it==-1 or ss==-1 or stsec==-1 or not valid_scale or not current_floor_valid or st['ifloor'] is None else 'PASS'
 G=OR(s['F'],cpstate)
 return dict(base=base,CP_state=cpstate,F=s['F'],S=s['S'],M=s['M'],gate=G,stock_state=ss,sector_state=stsec,I_state=it,I_floor=str(st['ifloor']) if st['ifloor'] is not None else None,adjusted_close=str(px) if px is not None else None,receipt_today=rt,receipt_today_known=receipt_known,CP_receipt_day=cp['receipt_day'] if cp else None,CP_floor=cp['floor'] if cp else None,CP_id=cp['id'] if cp else None,CP_invalid=cp['invalid'] if cp else None,CP_history_unknown=cp['history_unknown'] if cp else None,CP_update_history_unknown=st['cp_update_unknown'])
def trace_to_plan(r):
 st=make_state(r);out=None
 for ds in [d for d in days if r['signal_day']<=d<=r['plan_day']]:
  if ds>r['signal_day']:
   op=at_open(st,ds)
   if op['base'] in ['CANCEL','BLOCKED']:out=op;break
  out=at_close(st,ds,r['sector51'])
  if out['base'] in ['CANCEL','BLOCKED']:break
 return st,out
results=[];life=[];states={}
for r in rows:
 st,out=trace_to_plan(r);states[r['round_id']]=(copy.deepcopy(st),copy.deepcopy(out))
 status='BLOCKED_SOURCE_BRIDGE' if out['base']=='BLOCKED' else 'CANCEL_ORIGINAL_REQUEST' if out['base']=='CANCEL' else 'UNKNOWN_BASE' if out['base']=='UNKNOWN' else 'PASS' if out['gate']==1 else 'UNKNOWN_GATE' if out['gate']==-1 else 'STRUCTURE_WAIT'
 gatevia='F_AND_CP' if out.get('F')==out.get('CP_state')==1 else 'F' if out.get('F')==1 else 'CP' if out.get('CP_state')==1 else None
 frozenF=out.get('F');openst=copy.deepcopy(st);op=at_open(openst,r['seed_day']) if status=='PASS' else None
 openpass=None
 if op:openpass=op['base']=='PASS' and OR(frozenF,op.get('CP_state',-1))==1
 result=dict(**r,gate_status=status,gate_via=gatevia,CP_observation=out,CP_receipt_day=out.get('CP_receipt_day'),CP_floor=out.get('CP_floor'),CP_state=out.get('CP_state'),actual_next_OPEN_gate_pass=openpass,actual_next_OPEN_check=op,shadow_CP_consumed=False,bridges=st['bridges'],input_audit_signal_to_plan=st['audit'],input_audit_actual_next_OPEN=dict(Counter(openst['audit'])-Counter(st['audit'])) if op else {})
 results.append(result);life.append(dict(round_id=r['round_id'],sid=r['sid'],signal_day=r['signal_day'],plan_day=r['plan_day'],events=st['log'],input_audit_signal_to_plan=st['audit'],input_audit_actual_next_OPEN=dict(Counter(openst['audit'])-Counter(st['audit'])) if op else {}))
def sm(rs):
 return dict(rounds=len(rs),net=sum((D(r['net']) for r in rs),Z),gross_gains=sum((max(Z,D(r['net'])) for r in rs),Z),gross_losses=-sum((min(Z,D(r['net'])) for r in rs),Z),seed_cost=sum((D(r['seed_cost']) for r in rs),Z),top_winners=[{k:r[k] for k in ['round_id','name','sector51','plan_day','seed_day','net','CP_receipt_day','CP_floor','gate_status','gate_via']} for r in sorted(rs,key=lambda r:D(r['net']),reverse=True)[:6]])
summary=[]
for label,rs in [('ALL_MATURE',results),('LATE_MATURE',[r for r in results if r['seed_day']>'2024-11-06']),('OPEN_0924',[r for r in results if r['seed_day']=='2024-09-24']),('OPEN_0925',[r for r in results if r['seed_day']=='2024-09-25']),('PV_OPEN_1024',[r for r in results if r['seed_day']=='2024-10-24' and r['sector51']=='光伏风电设备'])]:
 for status in sorted({r['gate_status'] for r in results}):
  for state in ['ALL','CLOSED','OPEN']:
   a=[r for r in rs if r['gate_status']==status and (state=='ALL' or (not r['final_qty'])==(state=='CLOSED'))]
   summary.append(dict(cohort=label,status=status,state=state,**sm(a)))
sectorrows=[]
for s in sorted({r['sector51'] for r in results}):
 for status in sorted({r['gate_status'] for r in results}):
  a=[r for r in results if r['sector51']==s and r['seed_day']>'2024-11-06' and r['gate_status']==status]
  for state in ['ALL','CLOSED','OPEN']:
   b=[r for r in a if state=='ALL' or (not r['final_qty'])==(state=='CLOSED')]
   sectorrows.append(dict(sector51=s,status=status,state=state,**sm(b)))
qa=dict(formula='MATURE new SEED only: tri_or(original F, valid unbroken shadow CP with receipt_day >= original signal_day)',formula_not_changed=True,rows=len(results),counts=dict(Counter(r['gate_status'] for r in results)),CP_states=dict(Counter(str(r['CP_state']) for r in results)),close_PASS_OPEN_failed=sum(r['gate_status']=='PASS' and r['actual_next_OPEN_gate_pass'] is False for r in results),same_day_signal_CP_pass=sum(r['gate_status']=='PASS' and r['gate_via'] in ['CP','F_AND_CP'] and r['CP_receipt_day']==r['signal_day'] for r in results),bridge_checks=sum(len(r['bridges']) for r in results),original_false_cancellations=sum(r['gate_status']=='CANCEL_ORIGINAL_REQUEST' for r in results),all_local_only=True,no_engine_or_portfolio_run=True)
for n,x in [('ACTUAL_ENTRY_ROWS',results),('CP_LIFECYCLE',life),('SUMMARY',summary),('SECTOR_SUMMARY',sectorrows),('QA',qa),('SOURCE_HASHES',hashes)]:save(n,x)
save('INPUT_COVERAGE',dict(ticket_days=sum(r['input_audit_signal_to_plan'].get('CLOSE_visits',0) for r in results),audit=dict(sum((Counter(r['input_audit_signal_to_plan']) for r in results),Counter())),model_sha256=MODEL_SHA256,definition='Per-ticket signal CLOSE through plan CLOSE, with every intervening OPEN. Duplicate sid/day across different tickets count separately. Zero omitted issue keys mean zero occurrences.'))
print(json.dumps(dict(qa=qa,summary=[x for x in summary if x['state']=='ALL']),ensure_ascii=False,default=str))
