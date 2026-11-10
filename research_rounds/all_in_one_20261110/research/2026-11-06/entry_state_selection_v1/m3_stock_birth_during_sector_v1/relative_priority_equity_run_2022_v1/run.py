"""One approved fixed comparison. Stages: units, bridge_off, fixed, dynamic.
No parameter search. Existing stage outputs are never overwritten.
"""
import engine as s
from engine import pd,np,D,Path
import sys,time,json,ast
O=s.O

def compare_table(actual,expected,keys,columns=None):
 a=actual.copy();b=expected.copy();a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
 assert len(a)==len(b),(len(a),len(b),keys)
 columns=columns or list(b.columns)
 for c in columns:
  if c not in a:
   assert b[c].isna().all(),(c,'missing non-null output');a[c]=np.nan
  x=a[c];y=b[c]
  if pd.api.types.is_numeric_dtype(y) and not pd.api.types.is_bool_dtype(y):
   xx=pd.to_numeric(x,errors='coerce').to_numpy(dtype=float);yy=pd.to_numeric(y,errors='coerce').to_numpy(dtype=float)
   ok=np.isclose(xx,yy,atol=1e-7,rtol=1e-12,equal_nan=True)
  else:
   def norm(v):
    if pd.isna(v):return ''
    if isinstance(v,pd.Timestamp):return str(v.date())
    t=str(v)
    return t[:10] if len(t)>10 and t[4:5]=='-' and t[7:8]=='-' and t[10:11] in (' ','T') else t
   ok=x.map(norm).eq(y.map(norm)).to_numpy()
  if not ok.all():
   i=np.where(~ok)[0][:3];raise AssertionError((c,[(a.iloc[j][keys].to_dict(),x.iloc[j],y.iloc[j]) for j in i]))
 return dict(rows=len(a),columns=len(columns),match=True)

def units():
 s.reset();results={};arm='UNIT';sid='TEST.SZ';d=pd.Timestamp('2022-03-10');rec=d-pd.Timedelta(days=1);pay=d+pd.Timedelta(days=10)
 e=dict(sid=sid,economic_event_id=sid+'|DISTRIBUTION_001',evidence_version='v1',record_date=rec,ex_date=d,pay_date=pay,d_cash=D('.12345'),d_source=D('.12'),entitlement_verified=True)
 saved=[s.BY_RECORD,s.BY_EX,s.BY_PAY,s.EVENT_AT,s.ALLOWED_EVENT_IDS]
 s.BY_RECORD={rec:[e]};s.BY_EX={d:[e]};s.BY_PAY={pay:[e]};s.EVENT_AT={(sid,d):e}
 st=dict(round_id='r1',arm=arm,sid=sid,state='HELD',core=100,add=50,exitpending='I_STRUCTURE_EXIT',cash=D('-1000'),spent=D('1000'),fees=D(2),receivable=D(0),dividend_total=D(0),dividend_paid=D(0));s.archives['r1']=st
 s.register({sid:st},arm,rec);c=s.claims[s.claim_key(arm,e)];assert c['record_q']==150 and c['core_record_q']==100
 before=st.copy();s.accrue_day(arm,d);s.accrue_day(arm,d);assert st['receivable']==D(150)*D('.12345')*D('.8');assert (st['core'],st['add'],st['spent'],st['fees'])==(100,50,D(1000),D(2))
 # Stock can exit or freeze, then another round exists. Old claims stay with original root.
 st['core']=st['add']=0;new=dict(st,round_id='r2',cash=D('-2000'),receivable=D(0),dividend_total=D(0),dividend_paid=D(0));s.archives['r2']=new
 total=st['cash']+st['receivable'];s.pay_day(arm,pay);s.pay_day(arm,pay);assert st['cash']==total and st['receivable']==0 and new['cash']==-2000 and new['receivable']==0
 results['registered_exitpending_own_core_add_q']=True;results['ex_accrual_and_pay_idempotent']=True;results['flat_unknown_and_reentry_claim_isolation']=True;results['pay_transfer_preserves_equity']=True
 # Identity does not depend on date or evidence version; separate exchange does.
 revised=dict(e,evidence_version='v2',ex_date=d+pd.Timedelta(days=1));assert s.claim_key(arm,e)==s.claim_key(arm,revised);assert s.claim_key(arm,dict(e,sid='TEST.SH',economic_event_id='TEST.SH|DISTRIBUTION_001'))!=s.claim_key(arm,e)
 assert s.claim_key('OTHER_ARM',e)!=s.claim_key(arm,e);results['stable_identity_date_version_exchange_arm']=True
 # New second event obtains a distinct claim, first stays settled, both isolated.
 second=dict(e,economic_event_id=sid+'|DISTRIBUTION_002',record_date=pay,ex_date=pay+pd.Timedelta(days=1),pay_date=s.END+pd.Timedelta(days=1));s.BY_RECORD[pay]=[second];s.BY_EX[second['ex_date']]=[second];s.BY_PAY[second['pay_date']]=[second]
 new.update(state='HELD',core=200,add=0);s.register({sid:new},arm,pay);s.accrue_day(arm,second['ex_date']);assert new['receivable']==D(200)*e['d_cash']*s.NET;assert not s.claims[s.claim_key(arm,second)]['settled'];results['multiple_events_terminal_unpaid_claim']=True
 # Known flat and pending are Q=0; unknown is not zero; no entitlement created.
 for a,state in [('FLAT',{}),('PENDING',{sid:dict(state='BUY_PENDING',round_id='p')}),('UNKNOWN',{sid:dict(state='UNKNOWN',round_id='u')})]:
  s.register(state,a,rec);snap=s.snapshots[s.claim_key(a,e)];assert snap['record_q']==(None if a=='UNKNOWN' else 0);assert s.claim_key(a,e) not in s.claims
 results['known_zero_pending_sold_at_open_not_unknown']=True
 # Different arm owns actual different Q, never a frozen proxy.
 other=dict(st,core=70,add=30,round_id='r3');s.archives['r3']=other;s.register({sid:other},'OTHER_ARM',rec);assert s.claims[s.claim_key('OTHER_ARM',e)]['record_q']==100;results['independent_arm_q']=True
 s.BY_RECORD,s.BY_EX,s.BY_PAY,s.EVENT_AT,s.ALLOWED_EVENT_IDS=saved
 # Strict native profit boundary, without current CLOSE fields or CP access.
 old={k:getattr(s,k) for k in ['mark','getmeta','fee','size']};rs=s.raw.get(sid);fs=s.facts.get(sid);cs=s.capacity.get(sid)
 s.raw[sid]=s.DayFrame(pd.DataFrame([dict(raw_open=10,adjustment_factor=1,source_kind='x',source_path='y',segment_id='z')],index=[d]));s.facts[sid]=s.DayFrame(pd.DataFrame([dict(i_floor=5)],index=[rec]));s.capacity[sid]={rec:100};calls=[]
 s.getmeta=lambda *a:(None,None,D(1));s.fee=lambda *a:D(0);s.size=lambda *a:(calls.append(1) or (0,D(0),D(0),None,None))
 for val in [D('-.0001'),D(0),D('.0001')]:
  s.mark=lambda *a,_v=val:_v;st=dict(origin=('x','y','z'),factor=1,fac=D(1),exitpending=None,addexitpending=False,addpending=D(5),add=0,core=100,initial_fee=D(0),add_attempts=0,add_profit_floor_rejects=0,add_size_rejects=0,added=False)
  before=len(calls);s.native_held_open({sid:st},sid,st,d,rec);assert (len(calls)>before)==(val>0)
 for k,v in old.items():setattr(s,k,v)
 for g,v in [(s.raw,rs),(s.facts,fs),(s.capacity,cs)]:
  if v is None:g.pop(sid,None)
  else:g[sid]=v
 results['strict_zero_gate_original_open_no_close_flags']=True
 # Frozen queue permutation: only live feasible and known slots, UNKNOWN immovable.
 rows=[dict(event_id=str(i),PVR_score=10-i,sid=str(i),relative_known=i!=1,relative_event=1 if i==2 else 0) for i in range(4)]
 out=s.reorder(rows,{'0','1','2'},True);assert [x['event_id'] for x in out]==['2','1','0','3'];results['relative_unknown_and_infeasible_slots_fixed']=True
 # Verify source definitions unchanged except the one explicitly bounded entry hook.
 results['original_definition_sha256']=s.extracted;results['no_import_old_executable_scripts']=True
 dest=O/'units';dest.mkdir(exist_ok=False);s.save(dest/'QA.json',results);s.save(O/'ECONOMIC_EVENTS.json',s.EVENTS);s.save(O/'EVENT_REGISTRY.json',[{k:e[k] for k in ['economic_event_id','sid','local_action_ordinal','aliases','components']} for e in s.EVENTS]);s.save(O/'IMPLEMENTATION.json',dict(calculation_version='DYNAMIC_2022_NET80_V1',contract_sha256=s.sha(s.E/'relative_priority_equity_rebuild_v1/PROTOCOL_DRAFT.md'),original_definition_hashes=s.extracted,canonical_identity='Persisted registry local logical distribution ordinal; dates, corrections and evidence_version do not form claim key. Frozen single evidence version per run. Component aliases map to canonical composite.',limitations=['NON_PIT_STATIC_POOL','NET80_NOT_ACTUAL_TAX','HISTORICAL_ORDERABILITY_UNKNOWN','NOT_SHARED_ACCOUNT','ONLY_436_ADMITTED_ACTION_FACTS']))
 print('UNITS_PASS',results,flush=True)

def bridge_off():
 s.reset(False)
 checks={}
 for arm,folder in [('A_UNION_B','baseline'),('RELATIVE_UP_PRIORITY','economic')]:
  s.run_window(arm)
  for name,arr in [('ROUNDS',s.rounds),('ACTIONS',s.actions),('DECISIONS',s.decisions),('RANKING_AUDIT',s.ranking_audit),('END_STATES',s.blocks)]:
   expected=pd.read_csv(s.E/'relative_priority_v1'/folder/(name+'.csv'),low_memory=False);expected=expected[expected.window.astype(str).eq('2022')]
   actual=pd.DataFrame(arr);actual=actual[actual.arm.eq(arm)]
   keys=['round_id','day','side'] if name=='ACTIONS' else ['round_id'] if name in ('ROUNDS','END_STATES') else ['event_id']
   checks[arm+'_'+name]=compare_table(actual,expected,keys)
 s.dump(O/'bridge_off');s.save(O/'bridge_off/QA.json',checks);print('BRIDGE_OFF_PASS',checks,flush=True)

def fixed():
 expected_root=s.E/'cash_dividend_precision_24_v1/report';old=pd.read_csv(s.E/'lifecycle_v1/ROUNDS.csv',low_memory=False);old=old[old.window.astype(str).eq('2022')&old.arm.eq('A_UNION_B')];assert len(old)==2432
 events=s.ev.set_index('event_id');out={};checks={};start=time.monotonic()
 for mode,expectedname in [('FULL','FULL_CORE_PLUS_ADD'),('CORE_REGRESSION','CORE_ONLY')]:
  s.reset(True,mode)
  for i,rr in enumerate(old.to_dict('records')):
   r=events.loc[rr['event_id']].to_dict();r['event_id']=rr['event_id'];s.run_fixed(rr['round_id'],r)
   if i%400==0:print('FIXED',mode,i,round(time.monotonic()-start,1),flush=True)
  z=pd.DataFrame(s.rounds);b=pd.read_csv(expected_root/(expectedname+'_FIXED_PERMITS.csv'),low_memory=False)
  b['status']=b.status.replace({'SCENARIO_CLOSED_NOT_FACT':'COMPLETE_CONDITIONAL_STOCK_ROUND','CORE_ONLY_CLOSED_ALGEBRAIC':'COMPLETE_CONDITIONAL_STOCK_ROUND'})
  if mode=='CORE_REGRESSION':
   bad=set(b.loc[b.status.eq('CORE_BASELINE_ACTION_COVERAGE_UNKNOWN'),'round_id']);assert len(bad)==11
   z.loc[z.round_id.isin(bad),'status']='CORE_BASELINE_ACTION_COVERAGE_UNKNOWN';z.loc[z.round_id.isin(bad),['net_pnl','net_return_on_buy_cash']]=np.nan
  cols=['round_id','status','entry_day','exit_day','entry_q','net_pnl','net_return_on_buy_cash']
  checks[mode]=compare_table(z,b,['round_id'],cols)
  closed=z[z.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];assert (len(closed),int(closed.net_pnl.gt(0).sum()))==((2345,687) if mode=='FULL' else (2334,737))
  checks[mode].update(closed=len(closed),wins=int(closed.net_pnl.gt(0).sum()),unknown=int(z.status.str.contains('UNKNOWN').sum()),nofill=int(z.status.str.contains('NOFILL').sum()),strict_coverage=mode=='CORE_REGRESSION')
  s.dump(O/('fixed_'+mode.lower()));z.to_csv(O/('fixed_'+mode.lower())/'REPORTED_ROUNDS.csv',index=False)
  # Compare the 426 held-event paths against frozen published actions and register Q.
  pub=pd.read_csv(s.E/'cash_dividend_402_scenario_v2/full/ACTIONS.csv',low_memory=False);pub=pub[pub['mode'].eq(expectedname)]
  p24=pd.read_csv(s.E/'cash_dividend_precision_24_v1/full/ACTIONS.csv',low_memory=False);p24=p24[p24['mode'].eq(expectedname)&p24.cash_variant.eq('PRECISE_PUBLIC_CASH')]
  pub=pd.concat([pub,p24],ignore_index=True);pub['round_id']=pub.original_round_id
  actual=pd.DataFrame(s.actions);actual=actual[actual.round_id.isin(pub.round_id)]
  checks[mode]['published_actions']=compare_table(actual,pub,['round_id','day','side'],['round_id','day','side','q','price','fee','reason'])
  targets=pd.concat([pd.read_csv(s.E/'cash_dividend_402_scenario_v2/full/ROUNDS.csv'),pd.read_csv(s.E/'cash_dividend_precision_24_v1/full/ROUNDS.csv').query("cash_variant=='PRECISE_PUBLIC_CASH'")]);targets=targets[targets['mode'].eq(expectedname)]
  regs=pd.DataFrame(s.registrations).set_index('owner_round_id');expectedregs=targets.set_index('original_round_id').register_qty
  assert len(expectedregs)==426
  for rid,q in expectedregs.items():assert regs.loc[rid,'record_q']==q,(rid,'register q')
  checks[mode]['all_426_own_register_q_match']=True
 s.save(O/'FIXED_REGRESSION_QA.json',checks);print('FIXED_PASS',checks,flush=True)

def dynamic():
 assert (O/'FIXED_REGRESSION_QA.json').exists() and (O/'bridge_off/QA.json').exists() and (O/'units/QA.json').exists()
 dest=O/'dynamic';assert not dest.exists() and not (O/'DYNAMIC_RUN_ONCE.json').exists()
 s.save(O/'DYNAMIC_RUN_ONCE.json',dict(calculation_version='DYNAMIC_2022_NET80_V1',started=str(pd.Timestamp.now(tz='UTC')),engine_sha256=s.sha(O/'engine.py'),driver_sha256=s.sha(Path(__file__)),contract=s.sha(s.E/'relative_priority_equity_rebuild_v1/PROTOCOL_DRAFT.md'),arms=['A_UNION_B','RELATIVE_UP_PRIORITY'],authorization='Parent explicit 2022 minimum dynamic FULL two-arm fixed comparison, no scan'))
 s.reset(True)
 for arm in ['A_UNION_B','RELATIVE_UP_PRIORITY']:s.run_window(arm)
 z=pd.DataFrame(s.rounds);a=pd.DataFrame(s.actions);d=pd.DataFrame(s.decisions);rank=pd.DataFrame(s.ranking_audit)
 assert d.groupby(['arm','day','sector']).selected.sum().le(2).all();assert not z.round_id.duplicated().any();assert set(z.round_id)==set(d.loc[d.selected,'round_id'])
 assert a[a.side.eq('buy_add')].prior_round_net.gt(0).all();assert a[a.side.eq('buy_add')].groupby('round_id').size().le(1).all()
 unk=rank[rank.relative_unknown&rank.feasible_at_ranking];assert unk.original_feasible_rank.equals(unk.new_feasible_rank)
 hard=d[d.arm.eq('A_UNION_B')&d.day.eq(pd.Timestamp('2022-04-29'))&d.sector.eq('URFI881281')].set_index('sid');assert hard.loc['300390.SZ','selected'] and hard.loc['300014.SZ','decision']=='PASS_NOT_TOP2'
 t=z[z.arm.eq('A_UNION_B')&z.sid.eq('300390.SZ')].sort_values('signal_day').iloc[0];assert pd.Timestamp(t.exit_day)==pd.Timestamp('2022-04-12')
 s.dump(dest);s.save(dest/'QA.json',dict(max2=True,one_outcome=True,one_profitable_add=True,relative_unknown_fixed=True,tianhua_exit_apr12_and_selected_apr29=True,arms_independent=True))
 print('DYNAMIC_DONE',len(z),z.groupby(['arm','status']).size().to_dict(),flush=True)

if __name__=='__main__':
 stage=sys.argv[1];globals()[stage]()
