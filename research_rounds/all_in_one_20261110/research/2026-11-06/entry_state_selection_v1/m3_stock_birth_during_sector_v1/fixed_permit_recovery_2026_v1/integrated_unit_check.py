"""Synthetic bridge/cash state-machine causality, never real-permit economics."""
import engine as s
from engine import pd,np,D,copy
s.prepare_sources();r=s.CANDIDATES[0];sid=r['sid'];day=pd.Timestamp(r['transition_day']);prevday=pd.Timestamp(r['previous_day']);s.load(sid)
z=s.raw[sid].get(day).to_dict();p=s.raw[sid].get(prevday).to_dict();origin=s.lineage(p);checks=[]
def test(n,v):assert v,n;checks.append(n)
s.reset(True,True)
def gate(**kw):return s.source_transition_ok(kw.get('sid',sid),kw.get('d',day),kw.get('origin',origin),kw.get('z',z),kw.get('p',p),kw.get('prevday',prevday))
test('old_origin_mismatch',not gate(origin=('wrong',origin[1],origin[2])))
pp=dict(p,source_path='wrong');test('previous_lineage_mismatch',not gate(p=pp));test('previous_day_mismatch',not gate(prevday=prevday-pd.Timedelta(days=1)))
s.SOURCE_SEALED=False;test('unsealed_source',not gate());s.SOURCE_SEALED=True
cache=s.OVERLAP.pop((sid,day));test('missing_overlap_cache',not gate());s.OVERLAP[(sid,day)]=cache
test('non_datetime_overlap',not s.validate_overlap(pd.DataFrame(),pd.DataFrame(),day,prevday))
# Reuse real frozen transition coordinates but an explicitly synthetic position.
def state():return dict(sid=sid,arm='A_UNION_B',round_id='SYNTHETIC_ONLY',state='HELD',origin=origin,factor=r['factor'],fac=D(str(r['factor'])),core=100,add=20,addfloor=D(50),addpending=D(55),exitpending=None,addexitpending=False,cash=D(-12000),receivable=D(0),dividend_total=D(0),dividend_paid=D(0))
oldlocal=s.local_actions;s.local_actions=lambda sid:dict(events=[],_source_integrity_ok=True)
st=state();before=copy.deepcopy(st);states={sid:st};test('source_transition_succeeds',s.before_held(states,sid,st,day));test('success_only_origin_changes',{k:v for k,v in st.items() if k!='origin'}=={k:v for k,v in before.items() if k!='origin'} and st['origin']==s.lineage(z))
# Failure itself must not mutate any position coordinate, even though native OPEN will stop later.
st=state();st['origin']=('wrong',origin[1],origin[2]);before=copy.deepcopy(st);s.before_held({sid:st},sid,st,day);test('failed_transition_no_mutation',st==before)
# Native source/factor blockers tested directly with captured freeze, without round output.
oldfreeze=s.freeze_unknown;fail=[]
s.freeze_unknown=lambda states,sid,st,status,d:fail.append(status)
st=state();st['origin']=s.lineage(z);nextday=day+pd.Timedelta(days=1);baseframe=s.raw[sid].frame
bad=dict(z,source_path='not_whitelisted');s.raw[sid]=s.DayFrame(pd.DataFrame([z,bad],index=[day,nextday]));s.held_open({sid:st},sid,st,nextday,day);test('later_nonwhite_source_blocked',fail[-1]=='SOURCE_CHANGE_PATH_UNKNOWN')
bad=dict(z,adjustment_factor=z['adjustment_factor']*1.01);s.raw[sid]=s.DayFrame(pd.DataFrame([z,bad],index=[day,nextday]));s.held_open({sid:st},sid,st,nextday,day);test('later_unknown_factor_blocked',fail[-1]=='FACTOR_PATH_UNKNOWN')
bad=dict(z,volume_factor=z['volume_factor']*1.01);s.raw[sid]=s.DayFrame(pd.DataFrame([z,bad],index=[day,nextday]));s.held_open({sid:st},sid,st,nextday,day);test('later_volume_factor_blocked',fail[-1]=='VOLUME_FACTOR_PATH_UNKNOWN')
s.freeze_unknown=oldfreeze;s.raw[sid]=s.DayFrame(baseframe)
# Source migration -> record close -> ex open claim -> exit -> later pay close.
dates=pd.DatetimeIndex(['2026-05-15','2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22'])
rec=day;ex=dates[2];pay=dates[4];fo=D(str(r['factor']));pc=D(str(z['raw_close']));ds=D('.1');fn=fo*pc/(pc-ds)
e=dict(sid=sid,economic_event_id='SYNTHETIC_CASH',evidence_version='UNIT',record_date=rec,coordinate_snapshot_day=rec,ex_date=ex,pay_date=pay,previous_day=rec,announcement_date=prevday,d_source=ds,d_cash=D('.2'),factor_old=fo,factor_new=fn,entitlement_verified=True)
frame=pd.DataFrame([p,z,*[dict(z,adjustment_factor=float(fn)) for _ in range(4)]],index=dates)
future_event=dict(e,economic_event_id='FUTURE_UNIT',announcement_date=dates[-1],record_date=dates[-1],coordinate_snapshot_day=dates[-1],ex_date=dates[-1]+pd.Timedelta(days=3),pay_date=dates[-1]+pd.Timedelta(days=3),previous_day=dates[-1])
def simulate(cut,mode):
 s.reset(True,True);s.cal=dates if mode!='truncate' else dates[dates<=cut]
 f=frame.copy();fx=pd.DataFrame({'i_target':True,'i_floor':50.},index=dates);cpx=pd.DataFrame({'receipt':False,'candidate':55.},index=dates);caps={d:1000. for d in dates};sec={d:1 for d in dates};events=[copy.deepcopy(e),copy.deepcopy(future_event)]
 if mode=='truncate':
  f=f.loc[:cut].copy();fx=fx.loc[:cut].copy();cpx=cpx.loc[:cut].copy();caps={d:v for d,v in caps.items() if d<=cut};sec={d:v for d,v in sec.items() if d<=cut};events=[x for x in events if x['announcement_date']<=cut]
 if mode=='perturb':
  for df in [f,fx,cpx]:
   for col in df.select_dtypes(include=['number']).columns:df.loc[df.index>cut,col]=df.loc[df.index>cut,col]*9
  caps={d:(v if d<=cut else -100) for d,v in caps.items()};sec={d:(v if d<=cut else -1) for d,v in sec.items()}
  for x in events:
   if x['announcement_date']>cut:x['d_cash']=D(999)
 s.raw[sid]=s.DayFrame(f);s.facts[sid]=s.DayFrame(fx);s.cp[sid]=s.DayFrame(cpx);s.capacity[sid]=caps;s.sector={'UNIT':sec};s.install_events(events)
 s.local_actions=lambda sid:dict(events=[dict(effective_date=str(ex.date()))],_source_integrity_ok=True)
 st=state();states={sid:st};s.archives[st['round_id']]=st;trace=[]
 for d in dates:
  if d<day or d>cut:continue
  s.CURRENT_PHASE='OPEN';s.accrue_day('A_UNION_B',d)
  if states:
   assert s.before_held(states,sid,st,d)
   if d==ex:st['core']=0;st['add']=0;states.clear() # synthetic exit after accrued claim
  s.CURRENT_PHASE='CLOSE';s.register(states,'A_UNION_B',d);s.pay_day('A_UNION_B',d)
  trace.append(dict(day=d,cash=st['cash'],receivable=st['receivable'],origin=st['origin'],factor=st['fac']))
 # available_from is metadata for the next known calendar session, not a pre-cutoff cash effect.
 ledger=copy.deepcopy(s.claim_ledger)
 for x in ledger:x.pop('available_from',None)
 return dict(trace=trace,bridges=copy.deepcopy(s.bridges),claims=copy.deepcopy(list(s.claims.values())),ledger=ledger,register=copy.deepcopy(s.registrations))
for cut in dates[1:5]:
 base=simulate(cut,'full')
 for mode in ['truncate','perturb']:
  out=simulate(cut,mode);test('integrated_prefix:'+str(cut.date())+':'+mode,s.json.dumps(base,default=str,sort_keys=True)==s.json.dumps(out,default=str,sort_keys=True))
 test('source_bridge_exists:'+str(cut.date()),base['bridges'][0]['kind']=='EXACT_SOURCE_TRANSITION')
final=simulate(pay,'full');test('exit_then_pay_persists',final['claims'][0]['settled'] and final['claims'][0]['amount']==D('19.2') and final['trace'][-1]['receivable']==0)
s.local_actions=oldlocal;s.save(s.O/'INTEGRATED_UNIT_QA.json',dict(pass_=True,checks=checks,count=len(checks),economic_recovery_runs=0,scope='Synthetic source migration and cash record/ex/pay across exit with physical prefix and future perturbation; no actual permit continuation'))
print('INTEGRATED_UNIT_PASS',len(checks))
