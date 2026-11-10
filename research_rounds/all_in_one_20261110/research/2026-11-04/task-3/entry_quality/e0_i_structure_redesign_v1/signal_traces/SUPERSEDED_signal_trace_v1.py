"""Frozen two-arm signal trace from original E0 source events, never an Account.

The CLI requires an explicit resolved-contract JSON. Source E0/CP/G1 are read,
never recomputed. Exact source prefix precedes each display slice.
"""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import dataclass,field
import argparse,csv,gzip,hashlib,json,math
import pandas as pd

O=Path(__file__).resolve().parent;Q=O.parents[1]
FREEZE=O.parent/'SIGNAL_FREEZE.md'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
ARMS=('U_OR','S_PAIR')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,(pd.Timestamp,D)):return str(v)
 if hasattr(v,'item'):v=v.item()
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def encode(v):return json.dumps(clean(v),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def money(v):return None if v is None or pd.isna(v) else D(str(v))
def save(path,v):path.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

@dataclass
class Arm:
 name:str
 mode:str='OFF'
 generation:int=0
 support:D|None=None
 support_origin:dict|None=None
 start_at:str|None=None
 key_H:D|None=None
 key_H_point:dict|None=None
 key_H_components:list=field(default_factory=list)
 key_H_complete:bool=False
 HL_certificate:dict|None=None
 reclaim_active:bool=False
 reclaim_key:D|None=None
 reclaim_key_point:dict|None=None
 certificate_origin:dict|None=None

 def clear(self):
  self.mode='OFF';self.support=None;self.support_origin=None;self.start_at=None
  self.key_H=None;self.key_H_point=None;self.key_H_components=[];self.key_H_complete=False
  self.HL_certificate=None;self.reclaim_active=False;self.reclaim_key=None;self.reclaim_key_point=None;self.certificate_origin=None

 def freeze_key(self,points,lower_high=False):
  take=points[-2:] if self.name=='S_PAIR' or lower_high else points[-1:]
  self.key_H_components=list(take);self.key_H_complete=bool(take) if self.name=='U_OR' else len(take)==2
  point=max(take,key=lambda p:D(p['value_adjusted'])) if self.key_H_complete else None
  self.key_H_point=point;self.key_H=None if point is None else D(point['value_adjusted'])

 def snapshot(self):
  return dict(mode=self.mode,generation=self.generation,support=self.support,support_origin=self.support_origin,start_at=self.start_at,key_H=self.key_H,key_H_point=self.key_H_point,key_H_components=self.key_H_components,key_H_complete=self.key_H_complete,
   fresh_HL_certificate=self.HL_certificate is not None,HL_certificate=self.HL_certificate,reclaim_active=self.reclaim_active,reclaim_key_H=self.reclaim_key,certificate_origin=self.certificate_origin)

def point_from_source(sid,segment,day,event,er,source_hash):
 value=money(er.get('confirmed_pivot_price'));pivot=er.get('confirmed_pivot_date')
 if value is None or value<=0 or pivot is None or pd.isna(pivot):return None
 occurrence=str(pivot)[:10];assert occurrence<=day
 identity=dict(sid=sid,segment=segment,confirmed_at=day,event=event,pivot_occurrence_day=occurrence,value_adjusted=str(value),source_events_sha256=source_hash)
 return dict(value_adjusted=str(value),pivot_occurrence_day=occurrence,confirmed_at=day,segment=segment,event=event,event_id=hashlib.sha256(encode(identity).encode()).hexdigest(),event_id_basis='Local stable source-row identity; not a newly generated E0 event.',source_events_sha256=source_hash)

def trace(sid,price,events,source_hash,resolution):
 """Causal loop over one original full source prefix, with no future lookup."""
 required=['OFF_LH_DOES_NOT_LAUNCH','LAUNCH_SAME_PLUS_CAN_GRANT_ADJACENT_HL','S_PAIR_RECLAIM_ALONE_DOES_NOT_RECONFIRM','CONFIRM_EVENT_ONLY_ON_PROMOTION']
 assert all(resolution.get(k) is True for k in required),'Execution awaits matching explicit root resolution of card ambiguities'
 arms={a:Arm(a) for a in ARMS};Hs=[];Ls=[];segment=None;out=[];published=[]
 for t,pr in price.iterrows():
  day=str(t.date());er=None if t not in events.index else events.loc[t].to_dict();seg=pr.get('segment_id');seg=None if pd.isna(seg) else str(seg)
  changed=seg!=segment
  if changed:
   for a in arms.values():a.clear()
   Hs=[];Ls=[];segment=seg
  c=money(pr.get('close'));v=money(pr.get('volume'))
  observed=bool(pr.get('observed_bar',False)) and not bool(pr.get('synthetic_event_bar',True))
  valid=(c is not None and c>0 and v is not None and v>0 and observed and bool(pr.get('price_eligible',False)) and not bool(pr.get('source_invalid',True)) and seg is not None)
  raw_event=None if er is None else er.get('event');known_event=raw_event is not None and pd.notna(raw_event) and float(raw_event) in [-1.,0.,1.]
  event=None if not known_event else int(raw_event)
  before={k:a.snapshot() for k,a in arms.items()};signals={k:dict(exit_events=[],launch_event=None,confirm_event=None,downgrade_events=[],reclaim_event=None,no_progress_event=None) for k in ARMS}
  # 1. Only the support already known before this CLOSE is tested.
  if valid:
   for k,a in arms.items():
    if a.mode!='OFF' and a.support is not None and c<=a.support:
     signals[k]['exit_events'].append(dict(kind='support_exit',at=day,generation=a.generation,support_old=a.support,C=c,support_origin=a.support_origin))
     a.clear()
  p=point_from_source(sid,seg,day,event,er,source_hash) if valid and event in [-1,1] else None
  source_known=valid and known_event and (event==0 or p is not None)
  prior_Hs=list(Hs);prior_Ls=list(Ls)
  # 2. Publish a pivot only at its original confirmation row.
  if source_known and p is not None:
   (Ls if event==1 else Hs).append(p);published.append(p)
  if source_known:
   for k,a in arms.items():
    s=signals[k]
    # 3. An OFF arm launches only on an original positive event.
    if a.mode=='OFF' and event==1:
     a.generation+=1;a.mode='START';a.support=D(p['value_adjusted']);a.support_origin=p;a.start_at=day;a.freeze_key(prior_Hs)
     s['launch_event']=dict(kind='positive_pivot_launch',at=day,generation=a.generation,pivot=p,key_H=a.key_H,key_H_components=a.key_H_components)
    # 4. Adjacent confirmed lows, rather than a synthetic max-floor low.
    if a.mode!='OFF' and event==1 and prior_Ls:
     previous=prior_Ls[-1];is_HL=D(p['value_adjusted'])>D(previous['value_adjusted'])
     if is_HL:
      a.HL_certificate=dict(generation=a.generation,confirmed_at=day,previous_low=previous,new_low=p)
      if a.support is None or D(p['value_adjusted'])>a.support:a.support=D(p['value_adjusted']);a.support_origin=p
     else:
      s['downgrade_events'].append(dict(kind='non_HL_low',at=day,generation=a.generation,previous_low=previous,new_low=p,old_mode=a.mode))
      a.mode='START';a.HL_certificate=None;a.certificate_origin=None;a.reclaim_active=False;a.reclaim_key=None;a.reclaim_key_point=None
    # 5. An OFF lower-high does not manufacture a START/support.
    if a.mode!='OFF' and event==-1 and prior_Hs:
     previous=prior_Hs[-1];newH=D(p['value_adjusted']);previousH=D(previous['value_adjusted'])
     if newH<previousH:
      s['downgrade_events'].append(dict(kind='lower_high',at=day,generation=a.generation,previous_high=previous,new_high=p,old_mode=a.mode))
      a.mode='START';a.HL_certificate=None;a.certificate_origin=None;a.reclaim_active=False;a.reclaim_key=None;a.reclaim_key_point=None;a.freeze_key(Hs,lower_high=True)
     elif newH==previousH:s['no_progress_event']=dict(kind='equal_high_no_progress',at=day,generation=a.generation,previous_high=previous,new_high=p)
    # 6. Reclaim is a state above an already-published, frozen high.
    if a.mode!='OFF':
     reclaim=bool(a.key_H_complete and a.key_H is not None and a.key_H_point['confirmed_at']<day and c>a.key_H)
     hl=a.HL_certificate is not None
     permit=(hl or reclaim) if k=='U_OR' else (hl and reclaim)
     if a.mode=='START' and permit:
      a.mode='CONFIRMED';basis='HL_AND_RECLAIM' if hl and reclaim else 'HL_ONLY' if hl else 'RECLAIM_ONLY'
      a.certificate_origin=dict(confirmed_at=day,generation=a.generation,basis=basis,HL_certificate=a.HL_certificate,key_H=a.key_H,key_H_point=a.key_H_point)
      s['confirm_event']=dict(kind='promotion',**a.certificate_origin)
     if a.mode=='CONFIRMED' and reclaim:
      if not a.reclaim_active:s['reclaim_event']=dict(kind='first_reclaim_of_current_key',at=day,generation=a.generation,key_H=a.key_H,key_H_point=a.key_H_point)
      a.reclaim_active=True;a.reclaim_key=a.key_H;a.reclaim_key_point=a.key_H_point
    # 7. Reclaim failure retracts only the current certificate, once.
    if a.mode!='OFF' and a.reclaim_active and c<=a.reclaim_key and c>a.support:
     s['downgrade_events'].append(dict(kind='failed_reclaim',at=day,generation=a.generation,C=c,reclaim_key_H=a.reclaim_key,reclaim_key_point=a.reclaim_key_point,old_mode=a.mode))
     a.mode='START';a.HL_certificate=None;a.certificate_origin=None;a.reclaim_active=False;a.reclaim_key=None;a.reclaim_key_point=None
  status='KNOWN' if source_known else 'UNKNOWN_INVALID_PRICE_OR_EVENT'
  row=dict(sid=sid,day=day,source_segment=seg,source_segment_changed=changed,data_status=status,C_adjusted=c,raw_C=pr.get('raw_close'),original_E0_event=event,new_published_pivot=p,latest_two_H=Hs[-2:],latest_two_L=Ls[-2:],E0_sigma_at_ext='NOT_PERSISTED_NOT_RECOMPUTED_NOT_REQUIRED_BY_NEW_STRUCTURE')
  for k,a in arms.items():
   state=a.snapshot();state.update(signals[k]);state['before_CLOSE']=before[k]
   state['I_hold']=None if not source_known else a.mode in ['START','CONFIRMED'];state['I_expand']=None if not source_known else a.mode=='CONFIRMED'
   row[k]=state
  out.append(clean(row))
 return out,clean(published)

def run(contract_path,output):
 resolution=json.loads(contract_path.read_text());output.mkdir(parents=True,exist_ok=False)
 input_index=json.loads((O.parent/'path_inputs/INPUT_INDEX.json').read_text());sm_path=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={r['symbol']:r for r in json.loads(sm_path.read_text())}
 sources={str(FREEZE):sha(FREEZE),str(contract_path):sha(contract_path),str(sm_path):sha(sm_path),str(Path(__file__)):sha(Path(__file__))};allrows=[];pivotlog=[];prefixchecks=[]
 for spec in input_index:
  sid=spec['sid'];m=sm[sid];sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));ep=Path(next(p for p in m['source_sha256'] if p.endswith('/events.parquet')))
  for p in [sp,ep]:assert sha(p)==m['source_sha256'][str(p)];sources[str(p)]=sha(p)
  price=pd.read_parquet(sp).loc[:spec['target_end']];events=pd.read_parquet(ep).loc[:spec['target_end']]
  full,pivots=trace(sid,price,events,sources[str(ep)],resolution)
  display=[r for r in full if spec['target_start']<=r['day']<=spec['target_end']]
  for key,label in [('facts','native'),('CP1','CP')]:
   p=Path(m['refs'][key]);assert sha(p)==m['output_sha256'][str(p)];sources[str(p)]=sha(p);f=pd.read_parquet(p)
   for r in display:
    t=pd.Timestamp(r['day']);rr=None if t not in f.index else f.loc[t]
    cols=['e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','g_fresh_up','g_acute_down'] if label=='native' else ['ready','receipt','candidate','scale','next_scale','s','z']
    r['original_'+label+'_comparison_only']=None if rr is None else clean({c:rr[c] for c in cols})
  # Isolated cut-prefix checks; no future rows are supplied to the shorter run.
  for cut in sorted({display[len(display)//2]['day'],display[-1]['day']}):
   short,_=trace(sid,price.loc[:cut],events.loc[:cut],sources[str(ep)],resolution)
   expected=[r for r in full if r['day']<=cut]
   assert encode(short)==encode(expected),(sid,cut,'prefix dependence')
   prefixchecks.append(dict(sid=sid,cutoff=cut,full_source_first_day=str(price.index[0].date()),rows=len(short),exact_prefix=True))
  allrows.extend(display);pivotlog.extend(pivots);save(output/(sid.replace('.','_')+'_TRACE.json'),display)
 transitions=[]
 for r in allrows:
  for arm in ARMS:
   a=r[arm]
   if a['exit_events'] or a['launch_event'] or a['confirm_event'] or a['downgrade_events'] or a['reclaim_event']:
    transitions.append(dict(sid=r['sid'],day=r['day'],arm=arm,C=r['C_adjusted'],new_pivot=r['new_published_pivot'],latest_H=r['latest_two_H'],latest_L=r['latest_two_L'],state=a))
 save(output/'ALL_DAILY_TRACES.json',allrows);save(output/'TRANSITIONS.json',transitions);save(output/'PUBLISHED_PIVOTS_FULL_PREFIX.json',pivotlog);save(output/'PREFIX_CHECKS.json',prefixchecks)
 flat=[]
 for r in allrows:
  d={k:v for k,v in r.items() if k not in ARMS}
  for arm in ARMS:
   for k,v in r[arm].items():d[arm+'__'+k]=v
  flat.append({k:(encode(v) if isinstance(v,(dict,list)) else v) for k,v in d.items()})
 with (output/'DAILY_TRACES.csv').open('w') as f:
  wr=csv.DictWriter(f,fieldnames=list(flat[0]));wr.writeheader();wr.writerows(flat)
 save(output/'RUN_RECEIPT.json',dict(status='PURE_SIGNAL_TWO_ARM_TRACE_COMPLETE',source_sha256=sources,display_rows=len(allrows),transition_rows=len(transitions),prefix_checks=len(prefixchecks),new_E0_events=0,new_CP_events=0,new_accounts=0,new_orders=0,new_cash_paths=0,new_returns=0,unresolved_contract=False))
 print(encode(dict(output=str(output),display_rows=len(allrows),transitions=len(transitions),prefix_checks=len(prefixchecks))))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.contract,args.output)
