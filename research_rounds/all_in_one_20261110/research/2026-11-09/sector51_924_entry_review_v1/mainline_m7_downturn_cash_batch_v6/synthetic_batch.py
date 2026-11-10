"""No historical execution. Standard cash admission and retained/pending preflight."""
from pathlib import Path
import sys,importlib.util,copy,types,json
P=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('cash_v6_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
D=e.D;dt=e.pd.Timestamp('2024-10-11');record=e.pd.Timestamp('2024-10-10');checks=[]
def ok(name,v=True):
 assert v,name
 checks.append(name)
def fixture(s='600535.SH'):
 dividend=D('.26' if s=='600535.SH' else '.50');fo=D(1);pc=D(10);fn=fo*pc/(pc-dividend)
 ev=dict(sid=s,event_type='PURE_CASH',record_date='2024-10-10',ex_date='2024-10-11',pay_date='2024-10-11',d_source=str(dividend),d_cash=str(dividend),factor_old=str(fo),factor_new=str(fn),economic_event_id_candidate=s+'|SYNTHETIC',notice=dict(pdf_path='synthetic.pdf',pdf_sha256='synthetic_hash'),evidence_hashes={'synthetic.pdf':'synthetic_hash'})
 common=dict(source_kind='synthetic',source_path='synthetic_path',segment_id='0',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 z=e.pd.DataFrame([dict(common,raw_open=10,raw_close=10,adjustment_factor=float(fo)),dict(common,raw_open=float(10-dividend),raw_close=float(10-dividend),adjustment_factor=float(fn))],index=e.pd.DatetimeIndex([record,dt]))
 data=types.SimpleNamespace(end=dt,raw={s:z},actions={s:dict(events=[dict(effective_date='2024-10-11',split_ratio='1',cash_per_old_share=str(dividend))])},events={},admission=[],sid_sector={s:'synthetic'})
 data.z=lambda sid,day:data.raw[sid].loc[day]
 data.action=lambda sid,day:[a for a in data.actions[sid]['events'] if a['effective_date']==e.day(day)]
 return data,ev
for sid in ['600535.SH','600750.SH']:
 data,ev=fixture(sid);seen=[];e.admit_cash(data,ev,lambda p,h:seen.append((p,h)),{(sid,ev['ex_date'],ev['economic_event_id_candidate'])})
 ok('admit_'+sid,(sid,dt) in data.events and len(data.admission)==1 and seen==[('synthetic.pdf','synthetic_hash')])
 x=e.Engine(data);origin=('synthetic','synthetic_path','0');old=D(ev['factor_old'])
 x.tickets={sid:dict(sid=sid,ticket_id='synthetic',ever_seeded=False,status='RETAINED',origin=origin,current_factor=old,original_factor=old,nav0=D(100000),budget=D(2000),original_ifloor=D(1),ifloor=D(1),signal_day='2024-10-08',plan=None,last_verified_day='2024-10-10')}
 x.register_pay(record);before=copy.deepcopy(x.tickets[sid]);pending=[dict(sid=sid,origin=origin,factor=old,ticket_id='synthetic')]
 x.economic_preflight(dt,pending);x.accrue(dt);x.register_pay(dt)
 ok('pending_retained_standard_bridge_'+sid,x.tickets[sid]['current_factor']==D(data.events[(sid,dt)]['factor_new']) and len(pending)==1)
 ok('cash_no_entitlement_for_Q0_'+sid,x.cash==D(1200000) and x.receivable==0 and not x.claims and not x.active and not x.orders)
 ok('ticket_originals_unchanged_'+sid,all(x.tickets[sid][k]==v for k,v in before.items() if k not in ['current_factor','last_verified_day']))
 ok('ordinary_factor_zero_record_log_'+sid,len(x.equity)==1 and x.equity[0]['record_qty']==0 and x.equity[0]['cash_delta']=='0')
def reject(name,mutate):
 data,ev=fixture();mutate(data,ev)
 try:e.admit_cash(data,ev,lambda p,h:None,{(ev['sid'],ev['ex_date'],ev['economic_event_id_candidate'])})
 except (AssertionError,KeyError):ok(name)
 else:raise AssertionError(name)
reject('reject_duplicate',lambda d,v:d.events.update({(v['sid'],dt):v}))
reject('reject_split',lambda d,v:d.actions[v['sid']]['events'][0].update(split_ratio='1.3'))
reject('reject_wrong_cash',lambda d,v:v.update(d_source='9'))
reject('reject_missing_notice',lambda d,v:v.pop('notice'))
reject('reject_wrong_record',lambda d,v:v.update(record_date='2024-10-08'))
reject('reject_pay_before_ex',lambda d,v:v.update(pay_date='2024-10-10'))
reject('reject_wrong_old_factor',lambda d,v:v.update(factor_old='2'))
reject('reject_wrong_new_factor',lambda d,v:v.update(factor_new='2'))
reject('reject_source_change',lambda d,v:d.raw[v['sid']].loc.__setitem__((dt,'source_path'),'changed'))
reject('reject_bad_factor_formula',lambda d,v:d.raw[v['sid']].loc.__setitem__((dt,'adjustment_factor'),5.0))
ok('all_economic_methods_identical',all(e.self_check()['method_identity'].values()))
ok('loop_change_only_checkpoint',e.source.replace(e.new_dates,e.old_dates)==e.old_source)
# Inherit v3 guards exactly; ordinary pending requests do not pass through its split-day exception.
ok('split_guard_unchanged',e.Engine.economic_preflight is e.v5.Engine.economic_preflight and e.Engine.register_pay is e.v5.Engine.register_pay)
# A valid event outside the locked manifest is rejected, even with valid source math.
data,ev=fixture()
try:e.admit_cash(data,ev,lambda p,h:None,set())
except AssertionError:ok('reject_not_in_manifest')
else:raise AssertionError('unlisted event')
reject('reject_non_cash_type',lambda d,v:v.update(event_type='SPLIT_CASH'))
reject('reject_outside_month',lambda d,v:v.update(ex_date='2024-11-01'))
# Optional finalized batch verification runs source admission only, never the strategy loop.
if e.MANIFEST_SHA!='AWAITING_REVIEWED_MANIFEST':
 assert e.sha(e.MANIFEST_PATH)==e.MANIFEST_SHA
 checked_paths={}
 def checked(path,h):
  assert e.sha(Path(path))==h;checked_paths[path]=h
 manifest=e.read(e.MANIFEST_PATH);facts,allowed=e.manifest_records(manifest,checked)
 for ev in facts:
  sid=ev['sid'];ed=e.pd.Timestamp(ev['ex_date']);data=types.SimpleNamespace(end=ed,raw={sid:e.pd.read_parquet(ev['signal_path']).loc[:ed]},actions={sid:e.read(ev['local_action_path'])},events={},admission=[],sid_sector={sid:'facts_only'})
  e.admit_cash(data,ev,checked,allowed);ok('actual_frozen_cash_facts_'+sid+'_'+ev['ex_date'],(sid,ed) in data.events)
 e.save(P/'FACTS_LOADER_QA.json',dict(result='PASS',manifest_sha256=e.MANIFEST_SHA,events=len(facts),source_hashes=checked_paths,history_run=False))
# Actual held ordinary-cash entitlement uses the current200share record, never old614.
ev=next(v for v in facts if v['sid']=='688516.SH' and v['ex_date']=='2024-10-15');sid=ev['sid'];rd=e.pd.Timestamp(ev['record_date']);ed=e.pd.Timestamp(ev['ex_date']);z=e.pd.read_parquet(ev['signal_path']).loc[:ed]
data=types.SimpleNamespace(end=ed,raw={sid:z},actions={sid:e.read(ev['local_action_path'])},events={},admission=[],sid_sector={sid:'facts_only'})
data.z=lambda s,d:data.raw[s].loc[d];data.action=lambda s,d:[a for a in data.actions[s]['events'] if a['effective_date']==e.day(d)]
e.admit_cash(data,ev,checked,allowed)
x=e.Engine(data);a=dict(id='synthetic_200_share_record',sid=sid,lots=[dict(q=200)],origin=e.v5.v4.v3.m7.m3.lineage(z.loc[rd]),factor=D(ev['factor_old']),dividend=D(0))
x.active[sid]=a;x.archive[a['id']]=a;x.register_pay(rd)
ok('actual_688516_record_snapshot_200',x.snapshots[(sid,ev['record_date'])]['q']==200)
x.economic_preflight(ed,[]);x.accrue(ed)
ok('actual_688516_receivable_137_60',x.receivable==D('137.60') and a['dividend']==D('137.60'))
x.register_pay(ed)
ok('actual_688516_same_day_close_payment',x.cash==D('1200137.60') and x.receivable==0 and x.quantity(a)==200)
ok('generic_loader_function_identity',e.admit_cash is e.v5.admit_cash and e.manifest_records is e.v5.manifest_records)
out=dict(result='PASS',total=len(checks),checks=checks,history_run=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'))
e.save(P/'SYNTHETIC_QA.json',out);print(json.dumps(out))
