from pathlib import Path
import ast,hashlib,json
O=Path(__file__).resolve().parent;E=O.parent
base=E/'relative_priority_equity_run_2022_v1/engine.py';src=base.read_text();assert hashlib.sha256(base.read_bytes()).hexdigest()=='77a5d6345a7f35cbfaffedc08320512140adc2cd853fc8fef560de6a1a1a303c'
def replacefun(s,name,new):
 tree=ast.parse(s);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);old=ast.get_source_segment(s,node);assert s.count(old)==1;return s.replace(old,new)
s=src.replace('Frozen 2022 two-consumer NET80 conditional experiment.','Independent 2024 A+B baseline NET80 conditional scenario.')
s=s.replace("END=pd.Timestamp('2026-06-30')","END=pd.Timestamp('2026-06-30');WINDOW='2024_924';START=pd.Timestamp('2024-09-01');BIRTH_END=pd.Timestamp('2024-12-31')")
s=s.replace("ev.window.eq('2022')","ev.window.eq(WINDOW)")
s=s.replace("return ('2022',arm,e['sid'],e['economic_event_id'])","return (WINDOW,arm,e['sid'],e['economic_event_id'])")
s=s.replace("birth_end=pd.Timestamp('2022-12-31')","birth_end=BIRTH_END")
s=s.replace("if d<pd.Timestamp('2022-01-01') or d>stop:continue","if d<START or d>stop:continue")
s=s.replace("rid=f'2022|{arm}|{sid}|{seq[sid]}'","rid=f'{WINDOW}|{arm}|{sid}|{seq[sid]}'")
s=s.replace("dict(window='2022',arm=arm","dict(window=WINDOW,arm=arm")
s=s.replace("def run_window(arm,stop=END):\n states=", "def run_window(arm,stop=END):\n assert arm=='A_UNION_B','Only unchanged A+B baseline authorized'\n states=")
verify='''def verify_admitted_evidence():
 root=E/'cash_dividend_2024_coverage_v1';sp=root/'FINAL_OUTPUT_HASHES.json';seal=read(sp)
 assert read(root/'FINAL_INDEPENDENT_AUDIT.json')['result']=='PASS_COMPANY_FACT_EVIDENCE_ONLY'
 for name,h in seal['file_sha256'].items():
  p=root/name;assert sha(p)==h,(p,'2024 evidence seal mismatch');hashes[str(p)]=h
 for p,h in read(root/'SOURCE_SEAL.json')['sources'].items():assert sha(p)==h,(p,'original source drift');hashes[p]=h
 for p,h in read(root/'ADJUDICATION_SUMMARY.json')['original_source_action_hashes'].items():assert sha(p)==h;hashes[p]=h
 hashes[str(sp)]=sha(sp)
 assert read(root/'ADJUDICATION_SUMMARY.json')['production_admitted']==0
 # Source candidates remain blocked. This separate runtime is a bounded NET80 scenario.
'''
s=replacefun(s,'verify_admitted_evidence',verify.rstrip())
build='''def build_events():
 p=E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json';t=read(p);assert len(t)==165
 rows=[]
 for r in t:
  sid=r['sid'];d=pd.Timestamp(r['ex_date']);a=local_actions(sid);ordinal=r['local_action_ordinal'];term=a['events'][ordinal-1]
  assert term['effective_date']==r['ex_date'] and D(term['split_ratio'])==1 and D(term['cash_per_old_share'])==D(r['d_source'])
  assert not r['coordinate_verified_for_production'] and not r['entitlement_verified_for_production']
  load(sid);f=raw[sid].frame;prev=f[f.index<d].iloc[-1];cur=f.loc[d]
  ds=D(r['d_source']);dc=D(r['d_cash']);fn=D(str(cur.adjustment_factor));fo=D(str(prev.adjustment_factor));pc=D(str(prev.raw_close))
  assert dc>0 and ds>0 and lineage(prev)==lineage(cur)
  assert abs(fo/D(r['factor_old'])-1)<=D('1e-11') and abs(fn/D(r['factor_new'])-1)<=D('1e-11')
  assert abs(fo*pc/(pc-ds)/fn-1)<=D('1e-11') and str(prev.name.date())==r['previous_day']
  rec=pd.Timestamp(r['record_date']);pay=pd.Timestamp(r['pay_date']);assert rec==prev.name and rec<d<=pay and all(x in cal for x in [rec,d,pay])
  assert START<=rec and d<=END
  notice=r['notice'];components=notice['components'] if notice else []
  fields=dict(sid=sid,economic_event_id=r['economic_event_id_candidate'],event_type='PURE_CASH',record_date=rec,coordinate_snapshot_day=rec,ex_date=d,pay_date=pay,d_source=ds,d_cash=dc,d_ref=r['d_ref'],factor_old=fo,factor_new=fn,previous_close=pc,previous_day=prev.name,coordinate_verified=True,entitlement_verified=True,coordinate_scope='FROZEN_SOURCE_TRANSLATION_ONLY',entitlement_scope='OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX',origin='2024_REVIEWED_165_SCENARIO',local_action_ordinal=ordinal,source_path=str(p),aliases=['2024_FACT:'+sid+'|'+r['ex_date']],components=components,unresolved_reason=None,evidence_version=r['evidence_version'],scenario_not_PIT=True)
  rows.append(fields)
 assert len({r['economic_event_id'] for r in rows})==165
 regmap={}
 m=pd.read_csv(E/'relative_priority_equity_rebuild_v1/FIRST_ACTION_ROUND_MAP_2024.csv',dtype=str)
 by={(r['sid'],str(r['ex_date'].date())):r['economic_event_id'] for r in rows}
 for r in m.to_dict('records'):
  key=(r['sid'],r['status_day'])
  if key in by:regmap[r['round_id']]=by[key]
 return rows,regmap
'''
s=replacefun(s,'build_events',build.rstrip())
# Defensive finite-facts gate only when bridge enabled. The bridge-off regression is native-exact.
guard='''def unadmitted_action_at(sid,d):
 if not BRIDGE:return False
 a=local_actions(sid)
 if not a.get('_source_integrity_ok',True):return True
 e=EVENT_AT.get((sid,d))
 return (e is None or not enabled(e)) and any(pd.Timestamp(x['effective_date'])==d for x in a['events'])
'''
s=s.replace('def before_held(states,sid,st,d):',guard+'\ndef before_held(states,sid,st,d):')
old=" e=EVENT_AT.get((sid,d))\n if not e or not enabled(e):return True"
new=""" e=EVENT_AT.get((sid,d))
 if unadmitted_action_at(sid,d):
  z=raw[sid].get(d,{})
  if not finite(z.get('raw_open')) or z['raw_open']<=0:freeze_unknown(states,sid,st,'MISSING_OPEN_PATH_UNKNOWN',d);return False
  if lineage(z)!=st['origin']:freeze_unknown(states,sid,st,'SOURCE_CHANGE_PATH_UNKNOWN',d);return False
  freeze_unknown(states,sid,st,'UNADMITTED_ACTION_PATH_UNKNOWN',d);return False
 if not e or not enabled(e):return True"""
assert s.count(old)==1;s=s.replace(old,new)
old="segment=segment.replace(needle,\" if pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])\\n\"+needle)"
new="segment=segment.replace(needle,\" if unadmitted_action_at(sid,d):return freeze_unknown(states,sid,st,'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN',d)\\n if pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])\\n\"+needle)"
assert s.count(old)==1;s=s.replace(old,new)
# Arm/window independent owner is checked at registration; economic event id is unchanged across rounds.
s=s.replace("if q is not None and q>0 and e['entitlement_verified']:\n   claims[key]=", "if q is not None and q>0 and e['entitlement_verified']:\n   assert st['sid']==e['sid'] and st['arm']==arm and st['round_id'] in archives\n   claims[key]=")

local='''def local_actions(sid):
 if sid in actions_sources:return actions_sources[sid]
 p=AS/'inputs-v1/actions'/(sid+'.json');issues=[];coverage=[]
 empty=dict(series_id=sid,currency='CNY',events=[],coverage_evidence=[],unresolved=[],raw_response_empty=True)
 if not p.exists():a=empty;issues.append('ACTION_FILE_MISSING')
 else:
  hashes[str(p)]=sha(p)
  try:a=read(p)
  except Exception:a=empty;issues.append('ACTION_JSON_INVALID')
  if not isinstance(a,dict):a=empty;issues.append('ACTION_SCHEMA_INVALID')
  if a.get('series_id')!=sid:issues.append('ACTION_SECURITY_IDENTITY_MISMATCH')
  if a.get('currency')!='CNY':issues.append('ACTION_CURRENCY_MISMATCH')
  if not isinstance(a.get('events'),list):issues.append('ACTION_EVENTS_SCHEMA');a=dict(a,events=[])
  seen=set()
  for x in a['events']:
   try:
    date=pd.Timestamp(x['effective_date']);assert str(date.date())==x['effective_date'];assert x['effective_date'] not in seen;seen.add(x['effective_date']);assert D(str(x['split_ratio']))>0 and D(str(x['cash_per_old_share']))>=0
   except Exception:issues.append('ACTION_EVENT_SCHEMA_INVALID')
  evidence=a.get('coverage_evidence')
  if not isinstance(evidence,list):issues.append('COVERAGE_SCHEMA_INVALID');evidence=[];a=dict(a,coverage_evidence=[])
  if not evidence:coverage.append('NO_RIGHTS_SOURCE')
  for e in evidence:
   try:
    ep=Path(e['path']);assert ep.exists();assert sha(ep)==e['sha256'];hashes[str(ep)]=sha(ep);raw=read(ep);assert isinstance(raw.get('records'),list)
    if not raw['records']:coverage.append('RIGHTS_EMPTY')
   except Exception:issues.append('RIGHTS_EVIDENCE_MISSING_INVALID_OR_HASH_MISMATCH')
 if a.get('raw_response_empty'):coverage.append('ACTION_RAW_RESPONSE_EMPTY')
 a=dict(a,_source_integrity_ok=not issues,_source_issues=sorted(set(issues)),_source_coverage_status='COVERAGE_UNKNOWN' if issues or coverage else 'LOCAL_SOURCE_PRESENT_NOT_PIT',_source_coverage_issues=sorted(set(coverage)))
 actions_sources[sid]=a;return a
'''
s=replacefun(s,'local_actions',local.rstrip())
s=s.replace("ordinal=r['local_action_ordinal'];term=a['events'][ordinal-1]", "ordinal=r['local_action_ordinal'];assert a['_source_integrity_ok'];term=a['events'][ordinal-1]")
s=s.replace("if st['state']=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30' if stop==END else 'PREFIX_CENSORED',stop)", "if st['state']=='HELD':record(st,'OPEN_CENSORED_AT_2026_06_30' if stop==END else 'PREFIX_CENSORED',stop,exit_pending_at_end=bool(st['exitpending']),add_pending_at_end=st['addpending'] is not None)")

ast.parse(s);(O/'engine.py').write_text(s)
oldfunc={n.name:ast.get_source_segment(src,n) for n in ast.parse(src).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))};newfunc={n.name:ast.get_source_segment(s,n) for n in ast.parse(s).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
changed=[k for k in oldfunc if oldfunc[k]!=newfunc[k]]
assert set(changed)=={'verify_admitted_evidence','build_events','claim_key','register','before_held','new_state','run_window','local_actions'},changed
(O/'ENGINE_DERIVATION.json').write_text(json.dumps({'base_engine':str(base),'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(s.encode()).hexdigest(),'changed_definitions':changed,'added_definitions':['unadmitted_action_at'],'unchanged_definitions':[k for k in oldfunc if k not in changed],'native_entry_patch':'one existing approved pending hook plus finite-unadmitted-action guard after native raw/lineage checks','economic_runs':0},indent=2)+'\n')
print('ENGINE_GENERATED',changed)
