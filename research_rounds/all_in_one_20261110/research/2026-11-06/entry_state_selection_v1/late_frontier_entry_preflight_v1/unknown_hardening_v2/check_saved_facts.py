"""Strict three-valued safety repair of the ONE frozen gate. Saved facts only.
No trace reconstruction, numeric CP recalculation, new variant, or economics.
"""
from pathlib import Path
from datetime import date
import json,hashlib,math,copy
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;P=O.parent;H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def tri(x):
 # Only original bool and its explicit CSV serialization are recognized.
 # Integers/floats, including 0 and 1, are not implicit truth values.
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,str) and x in ('True','False'):return x=='True'
 return None
def key(x):return x if isinstance(x,str) and x and x not in ('nan','None','<NA>') else None
def day(x):
 if not isinstance(x,str) or len(x)!=10:return None
 try:return date.fromisoformat(x).isoformat()
 except (ValueError,TypeError):return None
def unknown_list(x):
 if isinstance(x,str):
  try:x=json.loads(x)
  except (ValueError,TypeError):return None
 return x if isinstance(x,list) else None

def decide(r,tr):
 auth=key(r.get('native_sector_authorization_id'));a=tr.get(auth) if auth is not None else None
 action=key(r.get('native_sector_action'));usable=tri(r.get('native_sector_authorization_usable'));birth=day(r.get('root_day'));signal=day(r.get('day'));found=tri(r.get('current_authorization_trace_found'))
 condition='UNKNOWN';reason='UNKNOWN_MISSING_STATE'
 if action=='unknown':reason='UNKNOWN_CURRENT_STAGE'
 elif action is not None and usable is None:reason='UNKNOWN_CURRENT_AUTH_USABLE'
 elif action is not None and usable is False:condition='DENY';reason='NO_CURRENT_USABLE_AUTHORIZATION'
 elif action is not None and usable is True:
  if found is not True or a is None:reason='CURRENT_AUTH_ID_NOT_TRACED'
  else:
   traceflags=[tri(a.get(k)) for k in ['formation_source_consistent','positive_original_CP1_receipt','accepted_by_original_stage']]
   rowflags=[tri(r.get(k)) for k in ['current_authorization_accepted','current_authorization_source_consistent','current_authorization_same_native_episode','current_authorization_same_attempt']]
   unknown=unknown_list(a.get('trace_unknown'));confirm=day(a.get('confirmed_day'));reported=day(r.get('current_authorization_confirmed_day'))
   ids=[key(r.get('sector')),key(a.get('canonical_series')),key(a.get('receipt_id')),key(r.get('native_sector_source_identity')),key(a.get('source_identity_at_confirmation')),key(r.get('native_sector_E0_episode')),key(a.get('native_E0_episode_at_confirmation')),key(r.get('native_sector_attempt_id')),key(a.get('native_attempt_id_at_confirmation'))]
   identity_ok=all(v is not None for v in ids) and ids[0]==ids[1] and ids[2]==auth and ids[3]==ids[4] and ids[5]==ids[6] and ids[7]==ids[8]
   evidence_ok=all(v is True for v in traceflags+rowflags) and unknown is not None and len(unknown)==0 and identity_ok and confirm is not None and reported==confirm and signal is not None and confirm<=signal
   if not evidence_ok:reason='AUTH_ID_SOURCE_EPISODE_OR_ACCEPTANCE_UNPROVEN'
   elif birth is None:reason='UNKNOWN_STOCK_ROOT_BIRTH'
   elif confirm>birth:condition='ALLOW';reason='CURRENT_ACCEPTED_POST_BIRTH_AUTHORIZATION'
   else:condition='DENY';reason='CURRENT_AUTH_NOT_STRICTLY_POST_BIRTH'
 # Existing fixed Q/F is not re-admitted by this late-entry gate.
 parent=key(r.get('proxy_parent_before_signal'));born=tri(r.get('born'));receipt=tri(r.get('receipt'));frontier=tri(r.get('new_frontier'))
 if parent=='EXISTING_PROXY_PROBE_PARENT':gate='BYPASS_EXISTING_PROBE_PARENT'
 elif r.get('case_source_status')=='UNKNOWN_MISSING_SOURCE' or born is None or receipt is None or frontier is None:gate='UNKNOWN_STOCK_SIGNAL'
 elif receipt is False or frontier is False:gate='DENY_NO_ORIGINAL_FRESH_RECEIPT'
 elif born is True:gate='KEEP_ORIGINAL_ROOT_BIRTH'
 elif parent=='NO_PROXY_PROBE_PARENT':gate=condition+'_LATE_NO_PARENT'
 else:gate='UNKNOWN_EXECUTION_PARENT'
 return dict(preflight_gate=gate,sector_market_condition=condition,sector_market_reason=reason)

def main():
 src(__file__);src(P/'CONTRACT.md');src(P/'INDEPENDENT_AUDIT_V1_UNKNOWN_BOUNDARY.json')
 t=pd.read_csv(src(P/'ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv'),low_memory=False);tr={r['receipt_id']:r for r in t.to_dict('records')};inputs={}
 comparison=[]
 for label,name in [('MARKET','MARKET_RECEIPT_PREFLIGHT.csv'),('REGISTERED','REGISTERED_ENTRY_PREFLIGHT.csv')]:
  df=pd.read_csv(src(P/name),low_memory=False);df['day']=df['signal_day'] if label=='REGISTERED' else df.day
  z=pd.DataFrame([decide(r,tr) for r in df.to_dict('records')]);checks={k:int(df[k].ne(z[k]).sum()) for k in z};assert not any(checks.values()),(label,checks)
  result=df[[c for c in ['year','sid','day','round_id','root_key'] if c in df]].copy()
  for col in z:result[col]=z[col]
  result.to_csv(O/(label+'_STRICT_LABELS.csv'),index=False,mode='x');comparison.append(dict(dataset=label,rows=len(df),differences=checks,exact=True));inputs[label]=df
 # Synthetics directly perturb each Boolean input and each required identity/date.
 b=next(r for r in inputs['MARKET'].to_dict('records') if r['preflight_gate']=='ALLOW_LATE_NO_PARENT');results=[]
 def test(name,r,expected=None,trace=tr,forbid_allow=False):
  out=decide(r,trace)
  if expected is not None:assert out['preflight_gate']==expected,(name,out)
  if forbid_allow:assert out['preflight_gate'] not in ['ALLOW_LATE_NO_PARENT','KEEP_ORIGINAL_ROOT_BIRTH'],(name,out)
  results.append(dict(case=name,**out,passed=True))
 bad=[('none',None),('nan',np.nan),('pdNA',pd.NA),('int0',0),('int1',1),('string_garbage','garbage')]
 boolfields=['native_sector_authorization_usable','born','receipt','new_frontier','current_authorization_trace_found','current_authorization_accepted','current_authorization_source_consistent','current_authorization_same_native_episode','current_authorization_same_attempt']
 for field in boolfields:
  for name,value in bad:
   r=copy.copy(b);r[field]=value;test(field+'_'+name,r,forbid_allow=True)
 # Explicit false strings may never behave as true; born=False is normal late logic.
 for field in boolfields:
  r=copy.copy(b);r[field]='False';test(field+'_CSV_False',r,forbid_allow=field!='born')
 for field in ['native_sector_authorization_usable','current_authorization_trace_found','current_authorization_accepted','current_authorization_source_consistent','current_authorization_same_native_episode','current_authorization_same_attempt','receipt','new_frontier']:
  for v in [True,np.bool_(True),'True']:
   r=copy.copy(b);r[field]=v;test(field+'_explicit_true_'+type(v).__name__,r,expected='ALLOW_LATE_NO_PARENT')
 for field in ['native_sector_authorization_id','native_sector_E0_episode','native_sector_attempt_id','native_sector_source_identity','current_authorization_confirmed_day','root_day','day','sector']:
  for name,value in bad[:3]:
   r=copy.copy(b);r[field]=value;test(field+'_missing_'+name,r,forbid_allow=True)
 for field in ['formation_source_consistent','positive_original_CP1_receipt','accepted_by_original_stage']:
  for name,value in bad+[('CSV_False','False')]:
   trace=dict(tr);a=copy.copy(tr[b['native_sector_authorization_id']]);a[field]=value;trace[b['native_sector_authorization_id']]=a;test('trace_'+field+'_'+name,copy.copy(b),trace=trace,forbid_allow=True)
 for value in ['False',None,np.nan,pd.NA,'["missing_source"]']:
  trace=dict(tr);a=copy.copy(tr[b['native_sector_authorization_id']]);a['trace_unknown']=value;trace[b['native_sector_authorization_id']]=a;test('trace_unknown_'+str(value),copy.copy(b),trace=trace,forbid_allow=True)
 r=copy.copy(b);r['native_sector_authorization_usable']=False;test('known_false_usable',r,expected='DENY_LATE_NO_PARENT')
 r=copy.copy(b);r['proxy_parent_before_signal']='UNKNOWN_NO_ECONOMIC_WINDOW';test('unknown_parent_not_no_parent',r,expected='UNKNOWN_EXECUTION_PARENT')
 r=copy.copy(b);r.update(proxy_parent_before_signal='EXISTING_PROXY_PROBE_PARENT',native_sector_authorization_usable=pd.NA,born=pd.NA,receipt=pd.NA,new_frontier=pd.NA);test('existing_parent_bypass_no_new_QF_gate',r,expected='BYPASS_EXISTING_PROBE_PARENT')
 # Normalize final fixed cases using saved signal evidence and provide no-parent-only condition separately.
 c=pd.read_csv(src(P/'FIXED_CASE_PREFLIGHT_FINAL.csv'),low_memory=False);prior=pd.read_csv(src(P/'FIXED_CASE_PREFLIGHT.csv'),low_memory=False);cols=[x for x in prior if x not in c and (x.startswith('current_authorization_') or x=='native_sector_source_identity' or x=='new_frontier')];c=c.merge(prior[['sid','day']+cols],on=['sid','day'],how='left',validate='one_to_one')
 fixed=pd.read_csv(src(P.parent/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv'))
 for d in ['2025-12-15','2025-12-17']:
  fr=fixed[fixed.sid.eq('300666.SZ')&fixed.day.eq(d)].iloc[0];ix=c.index[c.sid.eq('300666.SZ')&c.day.eq(d)][0];c.loc[ix,'new_frontier']=fr.new_frontier
 final=[]
 for r in c.to_dict('records'):
  out=decide(r,tr);hyp=copy.copy(r);hyp['proxy_parent_before_signal']='NO_PROXY_PROBE_PARENT';r.update(out);r['hypothetical_no_parent_signal_condition']=decide(hyp,tr)['preflight_gate'];final.append(r)
 pd.DataFrame(final).to_csv(O/'FIXED_CASE_PREFLIGHT_FINAL_STRICT.csv',index=False,mode='x')
 pd.DataFrame(results).to_csv(O/'SYNTHETIC_UNKNOWN_TESTS.csv',index=False,mode='x');dump('KNOWN_LABEL_EQUIVALENCE.json',comparison)
 assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in H.items())
 dump('SOURCE_HASHES.json',H);dump('QA.json',dict(status='PASS_STRICT_TRISTATE_KNOWN_LABELS_EXACT',known_label_checks=comparison,synthetic_tests=len(results),synthetic_passes=len(results),economic_runs=0,numeric_CP_recomputations=0,trace_reconstructions=0,formula_changes=0,source_changes=0,boolean_contract='Python bool / numpy.bool_ or explicit original CSV True / False only. None, NaN, pd.NA, numeric 0/1 and all other strings are UNKNOWN.',original_v1_preserved=True,not_an_execution_consumer=True))
 (O/'READOUT.md').write_text('# UNKNOWN执行安全补件\n\nv1已知样本计数正确，但bool(NaN)可能把缺失usable当True。原失败版与独审证据均保留。本补件只把唯一公式的输入解释改为严格三态：Python bool、numpy.bool_、原CSV字面True/False；None/NaN/pd.NA、数值0/1和其他字符串不当作布尔。\n\n37456市场票及3621登记票的preflight_gate/sector_market_condition/sector_market_reason逐行完全一致；所有合成缺失字段测试通过。已有parent不读取新门，未知parent不等于无parent。没有新公式、新参数、trace/CP/经济重跑。本补件只是事实预检解释器，不是执行消费者或上线认证。最终安全标签以本目录MARKET_STRICT_LABELS.csv、REGISTERED_STRICT_LABELS.csv和FIXED_CASE_PREFLIGHT_FINAL_STRICT.csv为准。\n')
 dump('OUTPUT_HASHES.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
 print('HARDENING_DONE',comparison,'synthetic',len(results))
if __name__=='__main__':main()
