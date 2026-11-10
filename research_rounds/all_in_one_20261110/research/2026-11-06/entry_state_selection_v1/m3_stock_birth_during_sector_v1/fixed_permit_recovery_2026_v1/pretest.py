"""No recovery economics: native-exact bridge-off replay and source gate unit tests."""
import engine as s
from engine import pd,np,D,Path,copy
O=s.O

def equal(a,b):
 if pd.isna(a) and pd.isna(b):return True
 if isinstance(a,(pd.Timestamp,np.datetime64)) or isinstance(b,(pd.Timestamp,np.datetime64)):
  try:return pd.Timestamp(a)==pd.Timestamp(b)
  except:return False
 if isinstance(a,(float,int,np.number)) and isinstance(b,(float,int,np.number)):return bool(np.isclose(a,b,atol=1e-7,rtol=1e-12))
 return a==b
s.reset()
for rid in s.permits:s.run_fixed(rid)
new=pd.DataFrame(s.rounds).set_index('round_id');old=s.original.set_index('round_id');errors=[];checked=0
for rid,r in old.iterrows():
 for k,v in r.items():
  checked+=1
  if not equal(v,new.loc[rid].get(k,np.nan)):errors.append(dict(round_id=rid,field=k,old=str(v),new=str(new.loc[rid].get(k))))
a=pd.read_csv(s.E/'lifecycle_v1/ACTIONS.csv',float_precision='round_trip');a=a[a.round_id.isin(s.permits)].reset_index(drop=True)
b=pd.DataFrame(s.actions);assert len(a)==len(b)
for rid in s.permits:
 aa=a[a.round_id.eq(rid)].reset_index(drop=True);bb=b[b.round_id.eq(rid)].reset_index(drop=True)
 for i,r in aa.iterrows():
  for k,v in r.items():
   checked+=1
   if not equal(v,bb.loc[i].get(k,np.nan)):errors.append(dict(round_id=rid,action=i,field=k,old=str(v),new=str(bb.loc[i].get(k))))
s.save(O/'BRIDGE_OFF_QA.json',dict(rounds=len(new),actions=len(b),fields_compared=checked,differences=errors,pass_=not errors))
assert not errors,errors[:10]
if not (O/'bridge_off').exists():s.dump(O/'bridge_off')
print('BRIDGE_OFF_PASS',len(new),len(b),checked,flush=True)
s.prepare_sources();s.SOURCE_BRIDGE=True
checks=[]
def test(name,v):
 assert v,name
 checks.append(name)
for r in s.CANDIDATES:
 sid=r['sid'];d=pd.Timestamp(r['transition_day']);prevday=pd.Timestamp(r['previous_day']);s.load(sid)
 z=s.raw[sid].get(d).to_dict();p=s.raw[sid].get(prevday).to_dict();origin=s.lineage(p)
 def gate(z_=z,p_=p,sid_=sid,d_=d,origin_=origin,pd_=prevday):return s.source_transition_ok(sid_,d_,origin_,z_,p_,pd_)
 test(sid+':valid',gate())
 test(sid+':wrong_sid',not gate(sid_='000000.SZ'));test(sid+':wrong_day',not gate(d_=d+pd.Timedelta(days=1)))
 for c in ['source_path','source_kind','segment_id','adjustment_factor','volume_factor']:
  zz=dict(z);zz[c]=str(z[c])+'_bad' if isinstance(z[c],str) else z[c]+1
  test(sid+':changed_'+c,not gate(z_=zz))
 for c in ['adjustment_factor','volume_factor','raw_open']:
  for v in [np.nan,np.inf,-1.,0.]:
   zz=dict(z);zz[c]=v;test(sid+':invalid_'+c+':'+str(v),not gate(z_=zz))
 for c in ['raw_close','raw_high','raw_low','raw_volume','amount','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']:
  zz=dict(z);zz[c]=np.nan;test(sid+':open_ignores_current_'+c,gate(z_=zz))
 aa,bb=s.OVERLAP[(sid,d)]
 test(sid+':no_overlap',not s.validate_overlap(aa.iloc[0:0],bb,d,prevday))
 test(sid+':duplicate',not s.validate_overlap(pd.concat([aa,aa.iloc[-1:]]),bb,d,prevday))
 test(sid+':missing_previous',not s.validate_overlap(aa.loc[aa.index<prevday],bb,d,prevday))
 for val in [np.nan,np.inf,999999.]:
  bad=bb.copy();bad.loc[prevday,'close']=val;test(sid+':overlap_bad_'+str(val),not s.validate_overlap(aa,bad,d,prevday))
 future=pd.DataFrame(np.nan,index=[d],columns=bb.columns)
 test(sid+':ignore_future_overlap',s.validate_overlap(aa,pd.concat([bb,future]),d,prevday))
# Native CLOSE flags retain fail-closed behavior for unknown boolean values.
for col in ['observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']:
 zz=dict(z);zz[col]=None;test('unknown_close_bool:'+col,not s.flags(zz))
# Unadmitted known local action stays blocked; this test never runs a cash-enabled round.
s.BRIDGE=True
for sid in {r['sid'] for r in s.CANDIDATES}:
 for e in s.local_actions(sid)['events']:
  if str(e['effective_date']).startswith('2026'):test('unadmitted:'+sid+':'+e['effective_date'],s.unadmitted_action_at(sid,pd.Timestamp(e['effective_date'])))
s.save(O/'SOURCE_GATE_QA.json',dict(pass_=True,checks=checks,count=len(checks),economic_recovery_runs=0))
s.save(O/'DEFINITION_DERIVATION.json',s.definition_hashes)
print('SOURCE_GATE_PASS',len(checks))
