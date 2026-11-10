"""Small fixed-permit same-day tax-exempt capitalization pilot, not a general action engine."""
from pathlib import Path
from decimal import Decimal as D
import ast,inspect,importlib.util,json,hashlib,sys,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;E=O.parent;V=E/'cash_dividend_402_scenario_v2';F=E/'share_action_facts_50_v1'
spec=importlib.util.spec_from_file_location('approved_cash_v2',V/'run_scenario.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def yes(x):return str(x).lower() in ['true','1']
shares=[]
def entitlement_known(st,event,day):
 if any(not yes(event[k]) for k in ['capital_premium_explicit','transfer_tax_exempt_explicit','no_bonus','listing_same_ex','record_previous_common_day']):return False
 if D(str(event['bonus_per_old_share']))!=0 or pd.Timestamp(event['listing_date'])!=day:return False
 ratio=D(str(event['transfer_per_old_share']))
 return ratio>0 and all(D(int(st[k]))*ratio==(D(int(st[k]))*ratio).to_integral_value() for k in ['core','add'])
def apply_shares(st,event,day):
 assert entitlement_known(st,event,day) and not st.get('share_event_applied',False)
 before=(st['spent'],st['cash'],st['fees'],st['added'],st['added_q'],st['add_attempts'],st['exitpending'],st['addexitpending'],st['addpending'])
 ratio=D(str(event['transfer_per_old_share']));q0=st['core'];q1=st['add'];n0=int(D(q0)*ratio);n1=int(D(q1)*ratio)
 st['core']+=n0;st['add']+=n1;st['share_event_applied']=True
 assert before==(st['spent'],st['cash'],st['fees'],st['added'],st['added_q'],st['add_attempts'],st['exitpending'],st['addexitpending'],st['addpending'])
 shares.append(dict(round_id=st['round_id'],original_round_id=st['original_round_id'],mode=s.MODE,sid=st['sid'],day=str(day.date()),record_date=event['record_date'],listing_date=event['listing_date'],event='TAX_EXEMPT_PREMIUM_CAPITALIZATION',core_before=q0,add_before=q1,transfer_per_old_share=str(ratio),core_new=n0,add_new=n1,core_after=st['core'],add_after=st['add'],buy_cash_delta=0,fee_delta=0,capital_source_tax_exempt_fact=True))
s.entitlement_known=entitlement_known;s.apply_shares=apply_shares
base=inspect.getsource(s.run_round)
old="cash=D(str(event['public_gross_cash_per_share']))";assert base.count(old)==1;base=base.replace(old,"cash=D(str(event['source_cash']))")
old="pred=D(str(prev['adjustment_factor']))*D(str(prev['raw_close']))/(D(str(prev['raw_close']))-cash)";assert base.count(old)==1;base=base.replace(old,"pred=D(str(prev['adjustment_factor']))*D(str(prev['raw_close']))*D(str(event['source_split']))/(D(str(prev['raw_close']))-cash)")
old="  if event and t==ex and qrec is not None and qrec>0:\n   inc=accrue"
new="  if event and t==ex and qrec is not None and qrec>0 and not entitlement_known(rootst,event,t):\n   freeze_unknown(states,sid,rootst,'SHARE_ENTITLEMENT_UNSUPPORTED_UNKNOWN',t);qrec=None;active=False\n  if event and t==ex and qrec is not None and qrec>0:\n   apply_shares(rootst,event,t)\n   inc=accrue"
assert base.count(old)==1;base=base.replace(old,new)
exec(compile(base,'approved_run_round_with_same_day_capitalization','exec'),s.__dict__)
# New issued odd shares may be liquidated only according to the existing dated quantity rule.
oldsrc=(s.OLD/'simulate.py').read_text();node=next(n for n in ast.parse(oldsrc).body if isinstance(n,ast.FunctionDef) and n.name=='held_open');op=ast.get_source_segment(oldsrc,node)
assert op.count('try:_,fs,pa=getmeta(sid,d)')==1;op=op.replace('try:_,fs,pa=getmeta(sid,d)','try:qr,fs,pa=getmeta(sid,d)')
op=op.replace(" if st['exitpending']:\n  assert", " if st['exitpending']:\n  if st.get('share_event_applied') and qr.sell_floor(st['core']+st['add'],st['core']+st['add'])!=st['core']+st['add']:return freeze_unknown(states,sid,st,'ODD_FULL_EXIT_PATH_UNKNOWN',d)\n  assert")
op=op.replace(" if st['addexitpending'] and st['add']:\n  q=", " if st['addexitpending'] and st['add']:\n  if st.get('share_event_applied') and qr.sell_floor(st['add'],st['core']+st['add'])!=st['add']:return freeze_unknown(states,sid,st,'ODD_ADD_EXIT_PATH_UNKNOWN',d)\n  q=")
exec(compile(op,'original_held_open_with_issued_odd_quantity_guards','exec'),s.__dict__)

def load_target():
 a=pd.read_csv(F/'FIRST_ELIGIBILITY_COVERAGE.csv',dtype={'cash_per_old_share':str,'bonus_per_old_share':str,'transfer_per_old_share':str,'source_cash':str,'source_split':str})
 a=a[a.first_pilot_gate_pass.map(yes)].sort_values(['ex_date','sid']).copy()
 pick=a.head(5).sid.tolist();withadd=a[pd.to_numeric(a.old_add_qty)>0]
 if len(withadd):pick.append(withadd.iloc[0].sid)
 a=a[a.sid.isin(pick)].copy();assert 1<=len(a)<=6
 old=pd.read_csv(E/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv');old=old[(old.status=='FACTOR_PATH_UNKNOWN')&(old.split_ratio!=1)]
 if 'round_id' in a.columns:assert all(r.round_id==old.set_index('sid').loc[r.sid,'round_id'] for r in a.itertuples())
 a=a.drop(columns=[k for k in ['round_id','core_qty','add_qty'] if k in a.columns])
 a=a.merge(old[['sid','round_id','core_qty','add_qty']],on='sid',validate='one_to_one');a['status_day']=a.ex_date;a['public_gross_cash_per_share']=a.cash_per_old_share;a['register_held_qty_in_original_simulation']=a.core_qty+a.add_qty
 return a

def verify():
 z=json.loads((O/'CONTRACT_SEAL.json').read_text());assert all(sha(p)==h for p,h in z['source_hashes'].items()),'source/code drift';s.verify_seal();return z

def prepare():
 assert not (O/'CONTRACT_SEAL.json').exists();a=load_target();a.to_csv(O/'PILOT_TARGETS.csv',index=False)
 ids=a.round_id.tolist();added=a[pd.to_numeric(a.old_add_qty)>0];units=list(dict.fromkeys([ids[0]]+([added.iloc[0].round_id] if len(added) else ids[1:2])))
 paths=list(json.loads((V/'CONTRACT_SEAL.json').read_text())['source_hashes']);paths += [str(Path(__file__)),str(V/'run_scenario.py'),str(V/'FINAL_INDEPENDENT_AUDIT.json'),str(O/'PILOT_TARGETS.csv')]
 paths += [str(p) for p in F.rglob('*') if p.is_file()]
 for sid in a.sid:
  m=s.manifest[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  for p in [sp,m['refs']['facts'],m['refs']['CP1']]:assert sha(p)=={**m['source_sha256'],**m['output_sha256']}[p];paths.append(p)
 save(O/'CONTRACT_SEAL.json',{'created_utc':str(pd.Timestamp.now(tz='UTC')),'fixed_pilot_ids':ids,'unit_ids':units,'control_ids':s.controls,'selection':'First five eligible by ex-date then sid, plus earliest eligible previously held-add case. No later outcome/exit observation used.','scope':'At most six of original50 unresolved share events; same original permits and signal source, no reselection/account/PIT.','eligibility':'Official tax-exempt premium capitalization only, no bonus shares, own core/add new shares strictly integer, unrestricted new shares tradeable ex-day, record previous common day. Later-listing, fractional or unproved tax/source remain UNKNOWN.','coordinate_policy':'Validate old factor by old source cash and source split. Raw protections multiply stored Fold/Fnew; no signal I/CP reconstruction. Official ex-reference parameters remain distinct.','inventory_policy':'At ex pre-OPEN add exact integer issued shares to each arm own record holdings by core/add layer; preserve spent, old costs/fees, added and all exit flags. No trade action for issued shares. All original quantities retained in history.','cash_policy':'Known shareholder gross cash times record quantity times0.8, explicit NET80 not actual investor tax. Same pay-date CLOSE/next OPEN convention as approved cash experiment. Tax-exempt capitalization adds no fictional tax.','lot_policy':'After original raw/source/factor/dated-rule checks and before requested sell, use existing QuantityRule.sell_floor. Full liquidation odd permitted only if rule permits. Invalid partial-add odd order stops UNKNOWN; never round or invent residual policy.','budget_capacity':'INIT24000/SLOT48000/RISK3000 and original raw_volume20mean*1% capacity unchanged. Capacity retains mixed raw-share units across event, not certified economic-unit invariant. No bonus reset of add permission.','validation':'Synthetic entitlement integrality, cost invariance, add permission/exit flags, protections, immediate exits and lot locks; controls and pre-event prefix; independent share/cash/trade ledger; future factor/missing bars fail closed.','modes':['FULL_CORE_PLUS_ADD','CORE_ONLY'],'source_hashes':{p:sha(p) for p in sorted(set(paths))}});print('SEALED',len(a),'pilot permits',len(units),'unit cases',flush=True)

def synthetic():
 event={'capital_premium_explicit':True,'transfer_tax_exempt_explicit':True,'no_bonus':True,'listing_same_ex':True,'record_previous_common_day':True,'bonus_per_old_share':'0','transfer_per_old_share':'.5','listing_date':'2022-01-05','record_date':'2022-01-04'}
 z={'round_id':'SYNTH','original_round_id':'SYNTH','sid':'SYNTH','core':100,'add':100,'spent':D(2000),'cash':D(-2000),'fees':D(10),'added':True,'added_q':100,'add_attempts':1,'exitpending':'I_STRUCTURE_EXIT','addexitpending':True,'addpending':D(8),'fac':D(1),'factor':1,'addfloor':D(7)}
 before=len(shares);s.MODE='SYNTH';d=pd.Timestamp('2022-01-05');assert entitlement_known(z,event,d);apply_shares(z,event,d);assert z['core']==150 and z['add']==150 and z['spent']==2000 and z['added'] and z['add_attempts']==1
 s.rebase(z,D('1.5'));assert z['addfloor']==D(7)/D('1.5') and z['addpending']==D(8)/D('1.5') and z['exitpending']=='I_STRUCTURE_EXIT' and z['addexitpending'];shares.pop();assert len(shares)==before
 bad={**event,'transfer_per_old_share':'.6877934'};assert not entitlement_known({**z,'core':400,'add':0},bad,d)
 bad={**event,'listing_same_ex':False,'listing_date':'2022-01-06'};assert not entitlement_known(z,bad,d)
 bad={**event,'no_bonus':False,'bonus_per_old_share':'.2'};assert not entitlement_known(z,bad,d)
 qr=s.QuantityRule('SYNTH',100,100,100,True,1);assert qr.sell_floor(910,2210)==900 and qr.sell_floor(2210,2210)==2210
 return {'strict_integer_no_floor':True,'delayed_listing_rejected':True,'bonus_tax_scope_rejected':True,'spent_cash_fees_unchanged':True,'original_added_and_exit_flags_preserved':True,'both_raw_protections_rebased':True,'partial_odd_requires_unknown_full_exit_rule_distinct':True}

def synthetic_open_order():
 saved={k:getattr(s,k) for k in ['getmeta','fee','act','record','freeze_unknown','size','mark']};sid='SYNTH_SHARE_OPEN';d=pd.Timestamp('2022-01-05');prev=d-pd.Timedelta(days=1);events=[]
 prior={k:getattr(s,k).get(sid) for k in ['raw','facts','capacity']}
 qr=s.QuantityRule('SYNTH',100,100,100,True,1)
 s.getmeta=lambda *a:(qr,None,D(1));s.fee=lambda *a:D(5)
 s.act=lambda st,day,side,q,px,ff,reason,**kw:events.append({'kind':'trade','side':side,'q':q})
 s.record=lambda st,status,day,**kw:events.append({'kind':'status','status':status})
 def unknown(states,sid,st,status,day):events.append({'kind':'unknown','status':status});states[sid]={'state':'UNKNOWN'}
 s.freeze_unknown=unknown;s.size=lambda *a:(100,D(5),D(50),None,None);s.mark=lambda *a:D(100)
 bar={'raw_open':10,'adjustment_factor':1.5,'source_kind':'x','source_path':'y','segment_id':'z'}
 s.raw[sid]=s.DayFrame(pd.DataFrame([bar],index=[d]));s.facts[sid]=s.DayFrame(pd.DataFrame([{'i_floor':6}],index=[prev]));s.capacity[sid]={prev:100}
 template={'sid':sid,'origin':('x','y','z'),'factor':1.5,'fac':D('1.5'),'share_event_applied':True,'core':150,'add':150,'cash':D(-2000),'fees':D(10),'spent':D(2000),'initial_fee':D(5),'entry_day':prev,'birth_end':pd.Timestamp('2022-12-31'),'exitpending':None,'addexitpending':False,'addpending':None,'added':True,'added_q':100,'add_attempts':1,'add_size_rejects':0,'add_profit_floor_rejects':0,'post_birth_window_adds':0}
 checks={}
 try:
  st={**template,'exitpending':'I_STRUCTURE_EXIT','addexitpending':True};state={sid:st};s.held_open(state,sid,st,d,prev);assert events[-2]=={'kind':'trade','side':'sell_all','q':300} and sid not in state and st['spent']==2000;checks['ex_open_I_exit_precedes_add_exit']=True
  events.clear();st={**template,'addexitpending':True};state={sid:st};s.held_open(state,sid,st,d,prev);assert events==[{'kind':'unknown','status':'ODD_ADD_EXIT_PATH_UNKNOWN'}];checks['invalid_issued_partial_odd_is_unknown_without_trade']=True
  events.clear();st={**template,'add':200,'addexitpending':True};s.held_open({sid:st},sid,st,d,prev);assert events==[{'kind':'trade','side':'sell_add','q':200}] and st['core']==150 and st['add']==0;checks['valid_add_exit_retains_odd_core']=True
  events.clear();st={**template,'core':150,'add':0,'added':False,'added_q':0,'addpending':D(8)/D('1.5')};s.held_open({sid:st},sid,st,d,prev);assert events==[{'kind':'trade','side':'buy_add','q':100}] and st['added'] and st['addfloor']==D(8)/D('1.5');checks['preexisting_rebased_addpending_preserves_original_open_logic']=True
  events.clear();s.raw[sid]=s.DayFrame(pd.DataFrame([{**bar,'raw_open':np.nan}],index=[d]));st={**template,'addexitpending':True};s.held_open({sid:st},sid,st,d,prev);assert events==[{'kind':'unknown','status':'MISSING_OPEN_PATH_UNKNOWN'}];checks['original_missing_open_precedes_new_quantity_guard']=True
 finally:
  for k,v in saved.items():setattr(s,k,v)
  for k,v in prior.items():
   g=getattr(s,k)
   if v is None:g.pop(sid,None)
   else:g[sid]=v
 return checks

def ledger():
 out=[]
 for r in s.rounds:
  aa=[x for x in s.actions if x['round_id']==r['round_id']];ss=[x for x in shares if x['round_id']==r['round_id']];q=0;c=D(0);spent=D(0);fees=D(0);bought={}
  events=[(x['day'],1,i,'TRADE',x) for i,x in enumerate(aa)]+[(x['day'],0,i,'ISSUE',x) for i,x in enumerate(ss)]
  for day,_,_,kind,x in sorted(events,key=lambda t:t[:3]):
   if kind=='ISSUE':assert q==x['core_before']+x['add_before'];q+=x['core_new']+x['add_new'];continue
   n=int(x['q']);p=D(str(x['price']));ff=D(str(x['fee']));buy=x['side'].startswith('buy')
   if buy:q+=n;c-=n*p+ff;spent+=n*p+ff;bought[day]=bought.get(day,0)+n
   else:
    assert n<=q-bought.get(day,0);qr,_,_=s.getmeta(x['sid'],pd.Timestamp(day));assert qr.sell_floor(n,q)==n,(r['round_id'],'invalid sell quantity');q-=n;c+=n*p-ff
   fees+=ff;assert q>=0
  paid=D(str(r['dividend_net80_paid']));rec=D(str(r['receivable_after_known_payouts']));assert abs(float(c+paid)-r['cash_after_known_payouts'])<1e-7 and abs(float(spent)-r['total_buy_cash'])<1e-7 and abs(float(fees)-r['all_fees'])<1e-7
  if r['status']=='SCENARIO_CLOSED_NOT_FACT':assert q==0 and abs(float(c+paid+rec)-r['net_pnl'])<1e-7
  if r['mode']=='CORE_ONLY':assert all(x['side'] in ['buy_core','sell_all'] for x in aa)
  out.append(dict(round_id=r['round_id'],inventory=q,trade_cash=float(c),dividend_paid=float(paid),receivable=float(rec),new_issued_shares=sum(x['core_new']+x['add_new'] for x in ss),reconciled=True))
 return out

def phase(which):
 z=verify();dest=O/which;dest.mkdir(exist_ok=True);assert not (dest/'RUN_ONCE.json').exists()
 if which=='pilot':assert json.loads((O/'UNIT_INDEPENDENT_AUDIT.json').read_text())['pilot_run_permitted'] is True
 a=pd.read_csv(O/'PILOT_TARGETS.csv',dtype={'cash_per_old_share':str,'bonus_per_old_share':str,'transfer_per_old_share':str,'source_cash':str,'source_split':str,'public_gross_cash_per_share':str});pub={r['round_id']:r for r in a.to_dict('records')}
 ids=z['unit_ids']+z['control_ids'] if which=='unit' else z['fixed_pilot_ids'];save(dest/'RUN_ONCE.json',{'contract_sha256':sha(O/'CONTRACT_SEAL.json'),'fixed_permits':ids,'start_utc':str(pd.Timestamp.now(tz='UTC'))})
 tests={'share':synthetic(),'open_order':synthetic_open_order(),'cash_and_fail_closed':s.synthetic_tests()};start=time.monotonic()
 for rid in ids:
  for mode in z['modes']:
   r=s.run_round(rid,mode,pub.get(rid));r['same_day_tax_exempt_capitalization_scenario']=rid in pub
 checks=ledger();verify()
 if which=='unit':
  for rid in z['control_ids']:
   r=next(r for r in s.rounds if r['original_round_id']==rid and r['mode']=='FULL_CORE_PLUS_ADD');old=s.old_by.loc[rid];assert abs(r['net_pnl']-old.net_pnl)<1e-7 and pd.Timestamp(r['exit_day'])==pd.Timestamp(old.exit_day)
 for fn,arr in [('ROUNDS.csv',s.rounds),('ACTIONS.csv',s.actions),('SHARE_LEDGER.csv',shares),('DIVIDEND_LEDGER.csv',s.divs),('DAILY_MARKS.csv',s.marks)]:pd.DataFrame(arr).to_csv(dest/fn,index=False)
 save(dest/'BRIDGES.json',s.bridges);save(dest/'QA.json',{'tests':tests,'ledger':checks,'prefix_checks':s.prefix,'economic_paths':len(s.rounds),'fixed_permits':len(ids),'source_unchanged':True,'seconds':time.monotonic()-start});save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(pd.DataFrame(s.rounds).groupby(['mode','status']).size().to_string());print('DONE',which)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1] in ['unit','pilot']:phase(sys.argv[1])
 else:raise ValueError(sys.argv[1])
