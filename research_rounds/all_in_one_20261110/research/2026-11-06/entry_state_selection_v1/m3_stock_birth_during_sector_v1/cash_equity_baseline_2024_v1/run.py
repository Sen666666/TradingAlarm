"""Stages are gated. Units/cases/native regression precede independent economic authorization."""
import engine as s
from engine import pd,np,D,Path
import ast,sys,json,time
O=s.O
old_driver=s.E/'relative_priority_equity_run_2022_v1/run.py';txt=old_driver.read_text()
node=next(n for n in ast.parse(txt).body if isinstance(n,ast.FunctionDef) and n.name=='compare_table');exec(compile(ast.get_source_segment(txt,node),str(old_driver)+':compare_only','exec'),globals())
def units():
 node=next(n for n in ast.parse(txt).body if isinstance(n,ast.FunctionDef) and n.name=='units');code=ast.get_source_segment(txt,node)
 code=code[:code.index(" dest=O/'units'")]+" return results\n"
 code=code.replace('def units():','def inherited_units():').replace("other=dict(st,core=70,add=30,round_id='r3')","other=dict(st,core=70,add=30,round_id='r3',arm='OTHER_ARM')")
 exec(compile(code,str(old_driver)+':units_only','exec'),globals());results=inherited_units()
 assert s.WINDOW=='2024_924' and s.START==pd.Timestamp('2024-09-01') and s.BIRTH_END==pd.Timestamp('2024-12-31') and len(s.EVENTS)==165
 assert all(x['origin']=='2024_REVIEWED_165_SCENARIO' for x in s.EVENTS)
 assert len({x['economic_event_id'] for x in s.EVENTS})==165 and sum(bool(x['components']) for x in s.EVENTS)==1
 results['window_and_finite165_asserted']=True
 e=next(x for x in s.EVENTS if x['sid']=='301031.SZ');cur=s.raw[e['sid']].get(e['ex_date']);prev=s.raw[e['sid']].get(e['previous_day']);assert s.coordinate_matches(e,cur,prev);assert not s.coordinate_matches(dict(e,d_source=e['d_cash']),cur,prev)
 results['precision_cash_never_substitutes_source_factor']=True
 # Unadmitted known actions fail closed even if the observed factor happens to be unchanged.
 saved=(s.local_actions,s.freeze_unknown,s.raw.get('GUARD.SZ'));events=[];sid='GUARD.SZ';d=pd.Timestamp('2024-10-10');prev=d-pd.Timedelta(days=1)
 s.local_actions=lambda x:{'events':[{'effective_date':str(d.date()),'split_ratio':'1.4','cash_per_old_share':'0'}]}
 s.freeze_unknown=lambda states,sid,st,reason,day:events.append(reason)
 z=dict(raw_open=10,raw_close=10,adjustment_factor=1,source_kind='x',source_path='y',segment_id='z');s.raw[sid]=s.DayFrame(pd.DataFrame([z,z],index=[prev,d]));st=dict(sid=sid,origin=('x','y','z'),signal_day=prev)
 assert not s.before_held({sid:st},sid,st,d) and events[-1]=='UNADMITTED_ACTION_PATH_UNKNOWN'
 s.native_entry_open({sid:st},sid,st,d);assert events[-1]=='UNADMITTED_ACTION_AT_ENTRY_UNKNOWN'
 s.raw[sid].frame.loc[d,'raw_open']=np.nan;assert not s.before_held({sid:st},sid,st,d) and events[-1]=='MISSING_OPEN_PATH_UNKNOWN'
 s.BRIDGE=False;assert not s.unadmitted_action_at(sid,d);s.BRIDGE=True
 s.local_actions,s.freeze_unknown,oldraw=saved
 if oldraw is None:s.raw.pop(sid)
 else:s.raw[sid]=oldraw
 results['unadmitted_event_guard_and_missing_open_priority']=True;results['bridge_off_disables_guard']=True
 dest=O/'units';dest.mkdir(exist_ok=False);results.update(engine_sha256=s.sha(O/'engine.py'),driver_sha256=s.sha(Path(__file__)));s.save(dest/'QA.json',results)
 s.save(O/'ECONOMIC_EVENTS.json',s.EVENTS);s.save(O/'EVENT_REGISTRY.json',[{k:e[k] for k in ['economic_event_id','sid','local_action_ordinal','aliases','components']} for e in s.EVENTS]);print('UNITS_PASS',flush=True)
def cases():
 assert (O/'units/QA.json').exists();dest=O/'cases';dest.mkdir(exist_ok=False)
 old=pd.read_csv(s.E/'relative_priority_v1/baseline/ROUNDS.csv',low_memory=False);old=old[old.window.eq(s.WINDOW)]
 acts=pd.read_csv(s.E/'relative_priority_v1/baseline/ACTIONS.csv',low_memory=False)
 cases=['002847.SZ','688208.SH','301031.SZ','002352.SZ','600663.SH'];checks=[]
 for sid in cases:
  rr=old[old.sid.eq(sid)].sort_values('signal_day').iloc[0];r=s.ev[s.ev.event_id.eq(rr.event_id)].iloc[0].to_dict();s.reset(True);out=s.run_fixed(rr.round_id,r)
  e=s.EVENT_BY_ID[s.REGRESSION_EVENT_MAP[rr.round_id]];ex=e['ex_date'];rec=e['record_date'];a=pd.DataFrame(s.actions);b=acts[acts.round_id.eq(rr.round_id)]
  prefix=compare_table(a[pd.to_datetime(a.day)<ex] if len(a) else a,b[pd.to_datetime(b.day)<ex],['day','side'],['day','side','q','price','fee','reason']) if len(b) else {'rows':0,'match':True}
  assert all(x['economic_event_id']==e['economic_event_id'] for x in s.claims.values());cl=list(s.claims.values());reg=[x for x in s.registrations if x['economic_event_id']==e['economic_event_id']]
  if pd.isna(rr.entry_day):assert not cl and reg[0]['record_q']==0 and any(x['kind']=='PENDING_COORDINATE_Q0' for x in s.bridges)
  else:
   q=sum(int(x['q'])*(1 if str(x['side']).startswith('buy') else -1) for x in b.to_dict('records') if pd.Timestamp(x['day'])<=rec)
   assert len(cl)==1 and cl[0]['record_q']==q and cl[0]['amount']==D(q)*e['d_cash']*s.NET and cl[0]['owner_round_id']==rr.round_id and cl[0]['recognized'] and cl[0]['settled']
  s.dump(dest/sid);checks.append(dict(sid=sid,round_id=rr.round_id,prefix=prefix,record_q=reg[0]['record_q'],claim_count=len(cl),net80_amount=str(cl[0]['amount']) if cl else '0',final_status=out['status'],notice_cash_source_separation=True))
 s.save(dest/'QA.json',dict(cases=checks,engine_sha256=s.sha(O/'engine.py'),driver_sha256=s.sha(Path(__file__)),scope='Five bounded original permits, only their first admitted event, no selection or strategy comparison'))
 print('CASES_PASS',checks,flush=True)
def bridge_off():
 assert (O/'cases/QA.json').exists();s.reset(False);s.run_window('A_UNION_B');checks={}
 for name,arr in [('ROUNDS',s.rounds),('ACTIONS',s.actions),('DECISIONS',s.decisions),('RANKING_AUDIT',s.ranking_audit),('END_STATES',s.blocks)]:
  b=pd.read_csv(s.E/'relative_priority_v1/baseline'/(name+'.csv'),low_memory=False);b=b[b.window.eq(s.WINDOW)];a=pd.DataFrame(arr)
  keys=['round_id','day','side'] if name=='ACTIONS' else ['round_id'] if name in ('ROUNDS','END_STATES') else ['event_id']
  checks[name]=compare_table(a,b,keys)
 assert not s.claims and not s.bridges;s.dump(O/'bridge_off');checks.update(engine_sha256=s.sha(O/'engine.py'),driver_sha256=s.sha(Path(__file__)),unchanged_selection_parameters=True)
 s.save(O/'bridge_off/QA.json',checks);print('BRIDGE_OFF_PASS',checks,flush=True)
def economic():
 audit=s.read(O/'PRE_ECONOMIC_AUDIT.json');assert audit['economic_baseline_permitted'] is True and audit['engine_sha256']==s.sha(O/'engine.py') and audit['driver_sha256']==s.sha(Path(__file__))
 assert all((O/p).exists() for p in ['units/QA.json','cases/QA.json','bridge_off/QA.json'])
 assert not (O/'ECONOMIC_RUN_ONCE.json').exists() and not (O/'economic').exists()
 s.save(O/'ECONOMIC_RUN_ONCE.json',dict(version='2024_AB_165_NET80_V1',started=str(pd.Timestamp.now(tz='UTC')),engine_sha256=s.sha(O/'engine.py'),driver_sha256=s.sha(Path(__file__)),audit_sha256=s.sha(O/'PRE_ECONOMIC_AUDIT.json'),protocol_sha256=s.sha(O/'PROTOCOL.md'),arms=['A_UNION_B'],admitted_events=165,subsequent393_unadmitted=True,not_shared_account=True))
 s.reset(True);s.run_window('A_UNION_B');z=pd.DataFrame(s.rounds);a=pd.DataFrame(s.actions);d=pd.DataFrame(s.decisions)
 assert d.groupby(['day','sector']).selected.sum().le(2).all() and not z.round_id.duplicated().any() and set(z.round_id)==set(d.loc[d.selected,'round_id'])
 assert a[a.side.eq('buy_add')].prior_round_net.gt(0).all() and a[a.side.eq('buy_add')].groupby('round_id').size().le(1).all()
 assert all(x['economic_event_id'] in s.EVENT_BY_ID for x in s.claims.values())
 s.dump(O/'economic');s.save(O/'economic/QA.json',dict(max2=True,one_outcome=True,one_profitable_add=True,only165_events=True,arm='A_UNION_B',status_counts=z.status.value_counts().to_dict()))
 print('ECONOMIC_DONE',len(z),z.status.value_counts().to_dict(),flush=True)
if __name__=='__main__':
 assert sys.argv[1] in ['units','cases','bridge_off','economic'];globals()[sys.argv[1]]()
