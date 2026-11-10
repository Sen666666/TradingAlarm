"""V3 down-reset recovery pure signal trace. Consume saved E0 events; no E0/CP/account run."""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
FREEZE=O.parent/'SIGNAL_FREEZE_V3.md'
NUMERIC=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py')
UNIT_ROUNDOFF=np.finfo(np.float64).eps/2
ROUNDING_STEPS=4
GAMMA4=ROUNDING_STEPS*UNIT_ROUNDOFF/(1-ROUNDING_STEPS*UNIT_ROUNDOFF)
def compare(a,b):
 a,b=float(a),float(b)
 if not (math.isfinite(a) and math.isfinite(b) and a>=0 and b>=0):raise ValueError('finite nonnegative magnitudes required')
 if abs(a-b)<=GAMMA4*max(a,b):return 0
 return 1 if a>b else -1
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def encoded(x):return json.dumps(clean(x),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def save(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def finite(v):return v is not None and pd.notna(v) and math.isfinite(float(v))
def segid(v):return None if not finite(v) else str(int(v)) if float(v).is_integer() else str(v)
def tri_or(a,b):return True if a is True or b is True else None if a is None or b is None else False
def higher_point(old,new):return new if old is None or compare(new['price_adjusted'],old['price_adjusted'])>0 else old

def pivot(sid,segment,day,obs,event,row,source_sha):
 value=row.get('confirmed_pivot_price');occur=row.get('confirmed_pivot_date')
 if not finite(value) or float(value)<=0 or occur is None or pd.isna(occur):return None
 occur=str(occur)[:10];assert occur<=day
 p=dict(price_adjusted=float(value),pivot_day=occur,confirmed_at=day,confirmed_observation=obs,source_segment=segment,event=event)
 p['source_event_id']=hashlib.sha256(encoded(dict(sid=sid,source_sha=source_sha,**p)).encode()).hexdigest()
 p['id_semantics']='Local stable reference to original source row; no E0 event recomputed.'
 return p

def trace(sid,price,events,event_sha):
 active=False;generation=0;P=None;P_point=None;R=None;cycle=0;up_after_R=False;B_base=False;B_triplet=None;B_reason='NO_RECOVERY_CYCLE'
 Hs=[];Ls=[];segment=None;obs=-1;close_obs=-1;memory='OFF';last_expand=None;rows=[];start_at=None
 for t,pr in price.iterrows():
  day=str(t.date());seg=segid(pr.get('segment_id'));changed=seg!=segment
  before=dict(active=active,generation=generation,P=P,mode_memory=memory,R=R,recovery_cycle=cycle,up_after_R=up_after_R,last_I_expand=last_expand)
  exits=[];archive=None;launch=None;trial=None;confirmation=None;revocation=None;down=None;P_update=None
  if changed:
   if active or R is not None:archive=dict(kind='source_incomparable_archive',at=day,generation=generation,old_segment=segment,old_P=P,old_R=R,old_recovery_cycle=cycle,actual_price_exit_not_claimed=True)
   active=False;P=None;P_point=None;R=None;up_after_R=False;B_base=False;B_triplet=None;B_reason='NEW_SOURCE_UNKNOWN';Hs=[];Ls=[];obs=-1;close_obs=-1;memory='OFF';last_expand=None;segment=seg;start_at=None
  C=float(pr['close']) if finite(pr.get('close')) else None
  price_valid=C is not None and C>0 and bool(pr.get('price_eligible',False)) and bool(pr.get('observed_bar',False)) and not bool(pr.get('synthetic_event_bar',True)) and not bool(pr.get('source_invalid',True)) and seg is not None
  volume_valid=finite(pr.get('volume')) and float(pr['volume'])>0 and bool(pr.get('volume_eligible',False))
  if price_valid:close_obs+=1
  if price_valid and volume_valid:obs+=1
  er=None if t not in events.index else events.loc[t].to_dict()
  ev=None if er is None or not finite(er.get('event')) or float(er['event']) not in [-1.,0.,1.] else int(er['event'])
  event_ready=er is not None and segid(er.get('segment_id'))==seg and finite(er.get('leg_direction'))
  P_old=P
  # Old support is checked with known comparable close, independently of volume.
  if active and price_valid and compare(C,P)<=0:
   exits.append(dict(kind='support_exit',at=day,generation=generation,P_old=P,P_origin=P_point,C=C,recovery_cycle_preserved=cycle,R_preserved=R))
   active=False;P=None;P_point=None;B_base=False;B_triplet=None;B_reason='HOLD_GENERATION_EXIT';memory='OFF';start_at=None
  prior_Hs=list(Hs);prior_Ls=list(Ls)
  newp=pivot(sid,seg,day,obs,ev,er,event_sha) if price_valid and volume_valid and event_ready and ev in [-1,1] else None
  if newp is not None:(Ls if ev==1 else Hs).append(newp)
  # Every published negative event resets recovery, regardless of HH/LH or holding.
  if newp is not None and ev==-1:
   cycle+=1;R=newp;up_after_R=False;B_base=False;B_triplet=None;B_reason='RESET_BY_LATEST_DOWN'
   down=dict(kind='down_reset',at=day,recovery_cycle=cycle,R=R,C=C,previous_expand=before['last_I_expand'],old_recovery_cycle=before['recovery_cycle'],old_R=before['R'])
   revocation=dict(kind='down_event_retracts_maturity',at=day,recovery_cycle=cycle,previous_expand=before['last_I_expand'])
   if active:memory='HOLD_ONLY'
  if newp is not None and ev==1:
   up_after_R=True
   if not active:
    active=True;generation+=1;P=newp['price_adjusted'];P_point=newp;start_at=day
    launch=dict(kind='new_holding_generation',at=day,generation=generation,L_launch=newp,recovery_cycle=cycle,R_preserved=R)
   elif compare(newp['price_adjusted'],P)>0:
    P_update=dict(kind='raise_P',old=P,new=newp['price_adjusted'],source=newp);P=newp['price_adjusted'];P_point=newp
   memory='START';trial=dict(kind='positive_event_trial',at=day,generation=generation,recovery_cycle=cycle,L=newp)
   L1=prior_Ls[-1] if prior_Ls else None
   middle=[] if L1 is None else [h for h in prior_Hs if L1['confirmed_at']<h['confirmed_at']<day]
   H12=middle[0] if len(middle)==1 else None
   B_triplet=dict(L1=L1,H12=H12,L2=newp,intervening_confirmed_H_count=len(middle))
   if L1 is None or H12 is None or R is None:B_base=None;B_reason='UNKNOWN_PAIR_OR_RECOVERY_REF'
   else:
    ordered=L1['pivot_day']<H12['pivot_day']<newp['pivot_day'] and H12['confirmed_at']<day
    B_base=bool(ordered and compare(newp['price_adjusted'],L1['price_adjusted'])>0 and newp['confirmed_at']>R['confirmed_at']);B_reason='VALID_POST_DOWN_HL_PAIR' if B_base else 'NON_HL_OR_UNORDERED_OR_NOT_POST_DOWN'
  above_before_up=bool(price_valid and R is not None and R['confirmed_at']<day and not up_after_R and compare(C,R['price_adjusted'])>0)
  if not price_valid:A_active=None;B_active=None;current_hold=None;reason='UNKNOWN_CURRENT_CLOSE'
  elif not active:
   A_active=False if event_ready else None;B_active=False if event_ready else None;current_hold=False if event_ready else None;reason='NO_ACTIVE_HOLDING_GENERATION'
  elif not up_after_R:
   A_active=False if event_ready else None;B_active=False if event_ready else None;current_hold=True;reason='WAIT_NEW_ORIGINAL_UP_AFTER_DOWN'
  else:
   current_hold=True;reason='POST_DOWN_UP_PUBLISHED'
   A_active=None if R is None or R['confirmed_at']>=day else compare(C,R['price_adjusted'])>0
   B_active=None if B_base is None else False if B_base is False else compare(C,B_triplet['H12']['price_adjusted'])>0
  expand=tri_or(A_active,B_active)
  mode='UNKNOWN' if expand is None else 'OFF' if not active else 'CONFIRMED' if expand else 'START' if up_after_R else 'HOLD_ONLY'
  if active and expand is not None:
   if memory!='CONFIRMED' and mode=='CONFIRMED':confirmation=dict(kind='recovered_maturity',at=day,generation=generation,recovery_cycle=cycle,via_A=A_active is True,via_B=B_active is True)
   if memory=='CONFIRMED' and mode!='CONFIRMED' and revocation is None:revocation=dict(kind='price_lost_recovery_reference',at=day,generation=generation,recovery_cycle=cycle)
   memory=mode
  row=dict(sid=sid,day=day,source_segment=seg,source_segment_changed=changed,price_close_valid=price_valid,volume_valid=bool(volume_valid),valid_E0_observation_index=obs,effective_CLOSE_observation_index=close_obs,original_event_ready=bool(event_ready),original_E0_event=ev,C=C,raw_C=pr.get('raw_close'),
   generation=generation,active_generation=active,mode=mode,mode_memory=memory,I_hold=current_hold,I_expand=expand,A_active=A_active,B_active=B_active,A_reason=reason,B_base=B_base,B_reason=B_reason,
   P_old=P_old,P_new=P,P_source=P_point,start_at=start_at,recovery_cycle=cycle,R=R,up_after_R=up_after_R,PRICE_ABOVE_R_BEFORE_UP=above_before_up,
   L1=None if B_triplet is None else B_triplet['L1'],H12=None if B_triplet is None else B_triplet['H12'],L2=None if B_triplet is None else B_triplet['L2'],latest_two_H=Hs[-2:],latest_two_L=Ls[-2:],new_confirmed_pivot=newp,
   support_exit_events=exits,source_archive_event=archive,launch_event=launch,trial_event=trial,down_event=down,confirm_event=confirmation,revoke_event=revocation,downgrade_events=[] if revocation is None else [revocation],P_update_event=P_update,before_CLOSE=before,
   E0_RMS_sigma='NOT_PERSISTED_NOT_RECOMPUTED; consumes original published pivots only')
  rows.append(clean(row));last_expand=expand
 return rows

def run(output,sids=None,prefix=False):
 output.mkdir(parents=True,exist_ok=False);index=json.loads((O.parent/'path_inputs/INPUT_INDEX.json').read_text());mp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={r['symbol']:r for r in json.loads(mp.read_text())}
 selected=[r for r in index if sids is None or r['sid'] in sids];allrows=[];checks=[];sources={str(FREEZE):sha(FREEZE),str(NUMERIC):sha(NUMERIC),str(Path(__file__)):sha(Path(__file__)),str(mp):sha(mp)}
 for spec in selected:
  sid=spec['sid'];m=sm[sid];sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));ep=Path(next(p for p in m['source_sha256'] if p.endswith('/events.parquet')))
  for p in [sp,ep]:assert sha(p)==m['source_sha256'][str(p)];sources[str(p)]=sha(p)
  price=pd.read_parquet(sp).loc[:spec['target_end']];events=pd.read_parquet(ep).loc[:spec['target_end']];full=trace(sid,price,events,sources[str(ep)])
  display=copy.deepcopy([r for r in full if spec['target_start']<=r['day']<=spec['target_end']])
  if prefix:
   for cut in [display[len(display)//2]['day'],display[-2]['day']]:
    shorter=trace(sid,price.loc[:cut],events.loc[:cut],sources[str(ep)])
    assert encoded(shorter)==encoded([r for r in full if r['day']<=cut]);checks.append(dict(sid=sid,cutoff=cut,full_source_first_day=str(price.index[0].date()),prefix_exact=True))
  for key,label,cols in [('facts','native',['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','g_fresh_up','g_acute_down']),('CP1','CP',['ready','receipt','candidate','scale','next_scale','s','z'])]:
   p=Path(m['refs'][key]);assert sha(p)==m['output_sha256'][str(p)];sources[str(p)]=sha(p);f=pd.read_parquet(p)
   for r in display:
    t=pd.Timestamp(r['day']);r['original_'+label+'_comparison_only']=None if t not in f.index else clean({c:f.loc[t,c] for c in cols})
  allrows.extend(display);save(output/(sid.replace('.','_')+'_TRACE.json'),display)
  print(encoded(dict(sid=sid,source_first_day=str(price.index[0].date()),display_rows=len(display),transitions=[dict(day=r['day'],mode=r['mode'],C=r['C'],P=r['P_new'],R=None if r['R'] is None else r['R']['price_adjusted'],A=r['A_active'],B=r['B_active']) for r in display if r['launch_event'] or r['confirm_event'] or r['support_exit_events'] or r['downgrade_events'] or r['down_event'] or r['trial_event']][-25:])),flush=True)
 save(output/'ALL_DAILY_TRACES.json',allrows);trans=[r for r in allrows if r['launch_event'] or r['confirm_event'] or r['support_exit_events'] or r['downgrade_events'] or r['down_event'] or r['trial_event']]
 save(output/'TRANSITIONS.json',trans);save(output/'PREFIX_CHECKS.json',checks)
 flat=[{k:(encoded(v) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in allrows]
 with (output/'DAILY_TRACES.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 save(output/'RUN_RECEIPT.json',dict(status='V3_PURE_SIGNAL_COMPLETE',source_sha256=sources,stocks=len(selected),rows=len(allrows),prefix_checks=len(checks),new_E0_events=0,new_CP_events=0,new_accounts=0,new_orders=0,new_cash_paths=0,new_returns=0))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--sids',nargs='*');p.add_argument('--prefix-check',action='store_true');a=p.parse_args();run(a.output,a.sids,a.prefix_check)
