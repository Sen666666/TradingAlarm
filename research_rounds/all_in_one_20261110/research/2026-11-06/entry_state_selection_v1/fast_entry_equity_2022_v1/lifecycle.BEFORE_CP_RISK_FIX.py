"""Frozen small-entry research adapter. Never connects an account or order router."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,sys,json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1'
BASE=E/'relative_priority_equity_run_2022_v1'
spec=importlib.util.spec_from_file_location('immutable_net80_base_engine',BASE/'engine.py')
s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
original_record=s.record;original_before_held=s.before_held;original_held_open=s.held_open;original_held_close=s.held_close
original_entry_open=s.entry_open;original_checkclose=s.checkclose
original_reset=s.reset
source_hashes={str(BASE/'engine.py'):s.sha(BASE/'engine.py'),str(E/'relative_priority_v1/simulate.py'):s.sha(E/'relative_priority_v1/simulate.py')}
role_cache={};role_attempts=[];consumptions=[];core_consumed=set();cp_consumed=set();cpmap={};active_arm=None
ADAPTER_ON=False

def save(p,x):s.save(p,x)
def reset(adapter=False):
 global role_cache,role_attempts,consumptions,core_consumed,cp_consumed,ADAPTER_ON
 original_reset(True);role_cache={};role_attempts=[];consumptions=[];core_consumed=set();cp_consumed=set();ADAPTER_ON=adapter

def close_role(r,role,floor):
 key=(r['sid'],pd.Timestamp(r['day']),role,str(floor))
 if key not in role_cache:
  q=dict(r,i_floor=floor);s.closecache.pop((r['sid'],pd.Timestamp(r['day'])),None)
  role_cache[key]=dict(original_checkclose(q))
 return role_cache[key].copy()

def role_options(r,arm,*,ignore_consumption=False):
 opts=[];sid=r['sid'];ep=r.get('i_epoch');ab=s.true(r.get('AB_I_qualified')) and pd.notna(r.get('AB_event_id'))
 fast=s.true(r.get('event_Q')) and s.true(r.get('epoch_lineage_known')) and pd.notna(ep) and (ignore_consumption or (arm,sid,str(ep)) not in core_consumed)
 cpfresh=s.true(r.get('cp_fresh')) and s.true(r.get('cp_trace_known')) and pd.notna(r.get('cp_id'))
 mobile=cpfresh and s.true(r.get('continuing_Q')) and (ignore_consumption or (arm,str(r['cp_id'])) not in cp_consumed)
 if ab or fast:opts.append(dict(role='I_CORE',floor=r['i_floor'],sources=('AB' if ab else '')+('+' if ab and fast else '')+('FAST_CORE' if fast else '')))
 if mobile:opts.append(dict(role='MOBILE_CP',floor=max(float(r['i_floor']),float(r['cp_candidate'])),sources='EMPTY_FRESH_CP'))
 return opts

def prepare(r,arm):
 opts=role_options(r,arm);checks=[];known_failure=False
 for op in opts:
  ck=close_role(r,op['role'],op['floor']);checks.append(dict(op,**ck))
  if 'UNKNOWN' in ck['close_check']:return [],checks,'CLOSE_'+ck['close_check']
  if ck['close_check']=='PASS':
   # Preserve any other passing role for next-OPEN known-failure fallback.
   passing=[dict(op,check=ck)]
   for later in opts[len(checks):]:
    lc=close_role(r,later['role'],later['floor']);checks.append(dict(later,**lc))
    if lc['close_check']=='PASS':passing.append(dict(later,check=lc))
   return passing,checks,'PASS'
  known_failure=True
 return [],checks,'NO_ELIGIBLE_ROLE' if not opts else 'CLOSE_ALL_ROLES_KNOWN_REJECT'

def record(st,status,d=None,**extra):
 original_record(st,status,d,**extra)
 if ADAPTER_ON:
  rr=s.rounds[-1]
  for k in ['source_mask','AB_event_id','AB_event_type','i_epoch','entry_role','initial_exit_day','initial_exit_price','initial_exit_reason','cp_id','entry_source','signal_cp_id']:
   rr[k]=st.get(k)
  rr['initial_layer_semantics']='first filled lot, I or CP role; standalone dated fees and its actual exit/claims'
  rr['role_options']=json.dumps([{k:o.get(k) for k in ['role','floor','sources']} for o in st.get('role_options',[])],ensure_ascii=False)

def consume(st,role,d,cpid=None):
 arm,sid=st['arm'],st['sid']
 if role=='I_CORE':
  ep=st.get('i_epoch')
  if pd.notna(ep):
   key=(arm,sid,str(ep));core_consumed.add(key)
   consumptions.append(dict(arm=arm,sid=sid,round_id=st['round_id'],day=d,kind='CORE_EPOCH',identity=str(ep),positive_fill=True))
 else:
  assert cpid is not None and pd.notna(cpid)
  key=(arm,str(cpid));assert key not in cp_consumed,(key,'receipt reused')
  cp_consumed.add(key);consumptions.append(dict(arm=arm,sid=sid,round_id=st['round_id'],day=d,kind=role,identity=str(cpid),positive_fill=True))

def before_held(states,sid,st,d):
 old=st.get('fac');ok=original_before_held(states,sid,st,d)
 if ok and st.get('initialfloor') is not None and old!=st['fac']:
  before=st['initialfloor'];st['initialfloor']=before*old/st['fac']
  s.bridges[-1]['protections']['initialfloor']=dict(before=before,after=st['initialfloor'])
 return ok

def entry_open(states,sid,st,d):
 if not ADAPTER_ON:return original_entry_open(states,sid,st,d)
 s.CURRENT_PHASE='OPEN';z=s.raw[sid].get(d,{});prev=s.raw[sid].get(st['signal_day'],{})
 if not s.finite(z.get('raw_open')) or z['raw_open']<=0:return s.freeze_unknown(states,sid,st,'MISSING_NEXT_OPEN_UNKNOWN',d)
 if s.lineage(z)!=s.lineage(prev):return s.freeze_unknown(states,sid,st,'SOURCE_CHANGED_AT_ENTRY_UNKNOWN',d)
 if s.pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])
 if not s.finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return s.freeze_unknown(states,sid,st,'FACTOR_AT_ENTRY_UNKNOWN',d)
 op=D(str(z['raw_open']));px=op*(1+s.SLIP);fail=[]
 for option in st['role_options']:
  role=option['role'];fl=D(str(option['floor']))/D(str(prev['adjustment_factor']))
  if op<=fl:
   fail.append('NEXT_OPEN_BELOW_PROTECTION_NOFILL');role_attempts.append(dict(arm=st['arm'],round_id=st['round_id'],sid=sid,day=d,role=role,result=fail[-1],floor=float(fl)));continue
  try:q,bf,risk,_,_=s.size(sid,d,px,fl,s.INIT,s.RISK,st['prior20_capacity'])
  except (s.RuleUnavailable,KeyError,ValueError):
   role_attempts.append(dict(arm=st['arm'],round_id=st['round_id'],sid=sid,day=d,role=role,result='DATED_RULE_AT_ENTRY_UNKNOWN'));return s.freeze_unknown(states,sid,st,'DATED_RULE_AT_ENTRY_UNKNOWN',d)
  if not q:
   fail.append('MINIMUM_LOT_NOT_FUNDED_NOFILL');role_attempts.append(dict(arm=st['arm'],round_id=st['round_id'],sid=sid,day=d,role=role,result=fail[-1],floor=float(fl)));continue
  st.update(state='HELD',entry_status='CONDITIONAL_OPEN_PROXY',entry_role=role,entry_source=option['sources'],entry_day=d,entry_price=float(px),entry_open=float(op),entry_q=q,entry_fee=float(bf),entry_risk=float(risk),entry_gross=float(D(q)*px),entry_floor_raw=float(fl),cash=-D(q)*px-bf,spent=D(q)*px+bf,fees=bf,core=q,add=0,addfloor=None,added=False,added_q=0,addpending=None,exitpending=None,addexitpending=False,origin=s.lineage(z),factor=float(z['adjustment_factor']),fac=D(str(z['adjustment_factor'])),initial_fee=bf,add_attempts=0,add_profit_floor_rejects=0,add_size_rejects=0,negative_CP_blocked=0,CP_unknown_days=0,post_birth_window_adds=0,profitable_close_days=0,first_profitable_close=None,first_fresh_CP=None,industry_first_not_true=None,max_inventory_reference_fraction=float(D(q)*px/s.NAV),initialfloor=fl if role=='MOBILE_CP' else None,initialexitpending=False,addpending_cp_id=None)
  s.act(st,d,'buy_core',q,px,bf,'AB_OR_FAST_I_INITIAL' if role=='I_CORE' else 'EMPTY_CP_INITIAL',signal_day=str(st['signal_day'].date()),economic_role=role,cp_id=st.get('cp_id') if role=='MOBILE_CP' else None)
  consume(st,role,d,st.get('cp_id'));role_attempts.append(dict(arm=st['arm'],round_id=st['round_id'],sid=sid,day=d,role=role,result='CONDITIONAL_POSITIVE_FILL',q=q,fee=float(bf),risk=float(risk),floor=float(fl)))
  return
 status='NEXT_OPEN_BELOW_PROTECTION_NOFILL' if fail and all(x=='NEXT_OPEN_BELOW_PROTECTION_NOFILL' for x in fail) else 'MINIMUM_LOT_NOT_FUNDED_NOFILL'
 record(st,status,d);states.pop(sid)

def held_open(states,sid,st,d,prevd):
 if not ADAPTER_ON:return original_held_open(states,sid,st,d,prevd)
 s.CURRENT_PHASE='OPEN'
 if not before_held(states,sid,st,d):return
 z=s.raw[sid].get(d,{})
 # Original native function performs identical raw/lineage/factor/rule validation.
 if st.get('entry_role')=='MOBILE_CP' and st.get('initialexitpending') and not st['exitpending']:
  if not s.finite(z.get('raw_open')) or z['raw_open']<=0:return s.freeze_unknown(states,sid,st,'MISSING_OPEN_PATH_UNKNOWN',d)
  if s.lineage(z)!=st['origin']:return s.freeze_unknown(states,sid,st,'SOURCE_CHANGE_PATH_UNKNOWN',d)
  if not s.finite(z.get('adjustment_factor')) or not np.isclose(z['adjustment_factor'],st['factor'],rtol=1e-11):return s.freeze_unknown(states,sid,st,'FACTOR_PATH_UNKNOWN',d)
  try:_,fs,pa=s.getmeta(sid,d)
  except (s.RuleUnavailable,KeyError,ValueError):return s.freeze_unknown(states,sid,st,'DATED_RULE_PATH_UNKNOWN',d)
  assert d>st['entry_day']
  sp=D(str(z['raw_open']))*(1-s.SLIP);q=st['core']
  if q:
   sf=s.fee(q,sp,fs,'sell',pa);st['cash']+=D(q)*sp-sf;st['fees']+=sf;s.act(st,d,'sell_initial',q,sp,sf,'CP_INITIAL_FLOOR',economic_role='MOBILE_CP')
   st.update(core=0,initialexitpending=False,initial_exit_day=d,initial_exit_price=float(sp),initial_exit_reason='CP_INITIAL_FLOOR')
  if not st['add']:
   st['addpending']=None;record(st,'COMPLETE_CONDITIONAL_STOCK_ROUND',d,exit_price=float(sp),exit_reason='CP_INITIAL_FLOOR');states.pop(sid);return
 pre_core=st['core'];pre_add=st['add'];prior_actions=len(s.actions);pending_id=st.get('addpending_cp_id')
 s.native_held_open(states,sid,st,d,prevd)
 new=s.actions[prior_actions:]
 for a in new:
  if a['side']=='buy_add':
   assert pending_id is not None;consume(st,'PROFITABLE_CP_ADD',d,pending_id);a['cp_id']=pending_id;a['economic_role']='MOBILE_CP_ADD'
  if a['side']=='sell_all' and pre_core:
   st.update(initial_exit_day=d,initial_exit_price=a['price'],initial_exit_reason=a['reason'])
   if '_output_index' in st:s.rounds[st['_output_index']].update(initial_exit_day=d,initial_exit_price=a['price'],initial_exit_reason=a['reason'])
 # CP initial could be sold earlier while an add persists; final add stop ends root.
 if states.get(sid,{}).get('state')=='HELD' and st['core']+st['add']==0:
  sells=[a for a in new if a['side'].startswith('sell')]
  assert sells;record(st,'COMPLETE_CONDITIONAL_STOCK_ROUND',d,exit_price=sells[-1]['price'],exit_reason=sells[-1]['reason']);states.pop(sid)

def cp_receipt(sid,d):
 q=cpmap.get((sid,pd.Timestamp(d)))
 return q if q is not None and q.get('known',True) else None

def held_close(states,sid,st,d):
 if not ADAPTER_ON:return original_held_close(states,sid,st,d)
 s.CURRENT_PHASE='CLOSE'
 if st.get('entry_role')!='MOBILE_CP':
  original_held_close(states,sid,st,d)
 else:
  z=s.raw[sid].get(d,{});fr=s.facts[sid].get(d,{});cr=s.cp[sid].get(d,{})
  if not s.flags(z) or not s.finite(z.get('raw_close')) or z['raw_close']<=0:return s.freeze_unknown(states,sid,st,'INVALID_CLOSE_PATH_UNKNOWN',d)
  if not (s.true(fr.get('i_target')) or s.false(fr.get('i_target'))):return s.freeze_unknown(states,sid,st,'I_STATE_PATH_UNKNOWN',d)
  cl=D(str(z['raw_close']));net=s.mark(st,cl*(1-s.SLIP),d)
  st.update(last_known_mark_day=d,last_raw_close=float(cl),last_mark_net=float(net),last_mark_fraction=float(net/st['spent']))
  st['max_inventory_reference_fraction']=max(st['max_inventory_reference_fraction'],float(D(st['core']+st['add'])*cl/s.NAV));st['profitable_close_days']+=int(net>0)
  if net>0 and st['first_profitable_close'] is None:st['first_profitable_close']=d
  sector=s.sector[st['sector']].get(d,-1)
  if sector!=1 and st['industry_first_not_true'] is None:st['industry_first_not_true']=d
  if s.false(fr['i_target']):st['exitpending']='I_STRUCTURE_EXIT';st['addpending']=None;return
  if not s.finite(fr.get('i_floor')) or fr['i_floor']<=0:return s.freeze_unknown(states,sid,st,'I_FLOOR_PATH_UNKNOWN',d)
  if not (s.true(cr.get('receipt')) or s.false(cr.get('receipt'))):return s.freeze_unknown(states,sid,st,'CP_STATE_PATH_UNKNOWN',d)
  fresh=s.true(cr['receipt'])
  if fresh and (not s.finite(cr.get('candidate')) or cr['candidate']<=0):return s.freeze_unknown(states,sid,st,'CP_CANDIDATE_PATH_UNKNOWN',d)
  if st['core'] and cl<=st['initialfloor']:st['initialexitpending']=True
  if st['add'] and cl<=st['addfloor']:st['addexitpending']=True
  if st['core'] and not st['initialexitpending']:
   st['initialfloor']=max(st['initialfloor'],D(str(fr['i_floor']))/st['fac'])
   if fresh:st['initialfloor']=max(st['initialfloor'],D(str(cr['candidate']))/st['fac'])
  if st['add'] and not st['addexitpending']:
   st['addfloor']=max(st['addfloor'],D(str(fr['i_floor']))/st['fac'])
   if fresh:st['addfloor']=max(st['addfloor'],D(str(cr['candidate']))/st['fac'])
  if fresh and st['first_fresh_CP'] is None:st['first_fresh_CP']=d
  if fresh and net<=0:st['negative_CP_blocked']+=1
  if fresh and not st['added'] and net>0 and sector==1 and st['exitpending'] is None and not st['initialexitpending']:
   st['addpending']=max(D(str(fr['i_floor'])),D(str(cr['candidate'])))/st['fac']
 if states.get(sid,{}).get('state')=='HELD' and st.get('addpending') is not None:
  cr=cp_receipt(sid,d)
  if cr is None:
   st['addpending']=None;return s.freeze_unknown(states,sid,st,'CP_RECEIPT_IDENTITY_UNKNOWN',d)
  if (st['arm'],str(cr['cp_id'])) in cp_consumed:st['addpending']=None
  else:st['addpending_cp_id']=str(cr['cp_id'])

def install():
 s.record=record;s.before_held=before_held;s.entry_open=entry_open;s.held_open=held_open;s.held_close=held_close

def load_inputs():
 global cpmap
 p=O/'CANONICAL_CP_2022_2026.parquet';t=pd.read_parquet(p)
 idcol='cp_id' if 'cp_id' in t else 'receipt_id';sidcol='sid' if 'sid' in t else 'canonical_series';daycol='day' if 'day' in t else 'confirmed_day'
 for r in t.to_dict('records'):
  unknown=r.get('trace_unknown',[]);known=(not len(unknown)) if isinstance(unknown,(list,tuple,np.ndarray)) else unknown in (None,'','[]')
  cpmap[(r[sidcol],pd.Timestamp(r[daycol]))]=dict(cp_id=r[idcol],known=known)
 frame=pd.read_parquet(O/'ENTRY_CANDIDATES_2022.parquet');frame['day']=pd.to_datetime(frame.day)
 assert not frame.duplicated(['sid','day']).any()
 for p in [O/'ENTRY_CANDIDATES_2022.parquet',O/'ALL_MARKET_INPUTS_2022.parquet',O/'CANONICAL_CP_2022_2026.parquet',Path(__file__),O/'PROTOCOL_DRAFT.md']:s.hashes[str(p)]=s.sha(p)
 return frame

def run_new(frame,stop=s.END):
 arm='AB_FAST_SMALL';states={};seq={};groups={d:g for d,g in frame.groupby('day',sort=True)}
 for k,d in enumerate(s.cal):
  if d<pd.Timestamp('2022-01-01') or d>stop:continue
  prevd=s.cal[k-1] if k else None;s.accrue_day(arm,d)
  for sid in list(states):
   st=states[sid]
   if st['state']=='BUY_PENDING':entry_open(states,sid,st,d)
   elif st['state']=='HELD':held_open(states,sid,st,d,prevd)
  for sid in list(states):
   st=states[sid]
   if st['state']=='HELD':held_close(states,sid,st,d)
  s.register(states,arm,d)
  if d in groups:
   for industry,g in groups[d].groupby('sector',sort=True):
    slots=0;queue_rank=0
    for r in g.sort_values(['PVR_score','sid'],ascending=[False,True],na_position='last',kind='stable').to_dict('records'):
     ab=r.get('AB_event_id')
     r.update(window='2022',event_id=str(ab) if pd.notna(ab) else '2022|FAST|'+str(d.date())+'|'+r['sid'],event_type=str(r.get('AB_event_type')) if pd.notna(ab) else 'FAST_ROLE_INVITATION',I_qualified=True)
     r['source_mask']='|'.join([name for name,yes in [('AB',pd.notna(ab)),('FAST_CORE',s.true(r.get('event_Q'))),('FRESH_CP',s.true(r.get('cp_fresh')) and s.true(r.get('continuing_Q')))] if yes])
     sid=r['sid'];dec={key:r.get(key) for key in ['event_id','window','day','sid','name','industry','sector','event_type','PVR_score','I_qualified','PVR_known','source_mask','AB_event_id','AB_event_type','event_Q','continuing_Q','cp_id','i_epoch','epoch_lineage_known']}
     dec.update(arm=arm,selected=False,queue_rank=np.nan,stock_state_before=states.get(sid,{}).get('state','FLAT'))
     if sid in states:
      dec.update(decision='BLOCKED_'+states[sid]['state'],blocking_round_id=states[sid]['round_id']);s.decisions.append(dec);continue
     if not s.true(r.get('PVR_known')) or not s.finite(r.get('PVR_score')):dec['decision']='PVR_UNKNOWN';s.decisions.append(dec);continue
     passing,checks,reason=prepare(r,arm);dec['role_checks']=json.dumps(checks,default=str,ensure_ascii=False)
     if not passing:dec['decision']=reason;s.decisions.append(dec);continue
     queue_rank+=1;dec['queue_rank']=queue_rank;ck=passing[0]['check'];dec.update(ck)
     if slots>=2:dec['decision']='PASS_NOT_TOP2';s.decisions.append(dec);continue
     slots+=1;seq[sid]=seq.get(sid,0)+1;rid=f'2022|{arm}|{sid}|{seq[sid]}'
     r['role_options']=passing;r['signal_cp_id']=r.get('cp_id');r['i_floor_original']=r['i_floor'];r['i_floor']=passing[0]['floor']
     st=s.new_state(r,arm,rid,ck);states[sid]=st
     dec.update(decision='SELECTED_PENDING',selected=True,selected_rank=slots,round_id=rid,preferred_role=passing[0]['role']);s.decisions.append(dec)
  s.pay_day(arm,d)
  if k%250==0:print('FAST_DAY',str(d.date()),len(states),len(s.rounds),flush=True)
 for sid,st in states.items():
  if st['state']=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30' if stop==s.END else 'PREFIX_CENSORED',stop)
  elif st['state']=='BUY_PENDING':record(st,'BUY_PENDING_CENSORED_AT_DATA_END',stop)
  s.blocks.append(dict(window='2022',arm=arm,sid=sid,final_state=st['state'],round_id=st['round_id']))
 s.finalize()

install()
