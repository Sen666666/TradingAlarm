"""Independent saved-ledger audit. Standard library only. Never imports strategy."""
import ast,csv,json,hashlib,math,sys
from pathlib import Path
from collections import defaultdict,Counter
D=Path(__file__).resolve().parent.parent; R=D.parent; B=R/'independent_channel_joint_economic_v1'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p): return list(csv.DictReader(p.open()))
def day(x): return str(x)[:10]
def key(x): return (x['sid'],day(x['day']))
def request(x): return (x['sid'],x['request_id'])
def groups(xs,k):
 d=defaultdict(list)
 for x in xs:d[k(x)].append(x)
 return d
def rank(x):
 known=str(x.get('PVR_known')).lower()=='true'
 try: score=float(x.get('PVR_score')); finite=math.isfinite(score)
 except (TypeError,ValueError): score=0;finite=False
 return (0,-score,x['sid']) if known and finite else (1,0,x['sid'])
def main(w):
 n=D/('gate_'+w);o=B/('economic_'+w)
 assert (n/'COMPLETE_SAVED_SNAPSHOT.json').exists(),'NOT_READY'
 seal=read(n/'OUTPUT_SEAL.json')
 assert sha(n/'OUTPUT_SEAL.json')==read(n/'COMPLETE_SAVED_SNAPSHOT.json')['output_seal_sha256']
 assert all(sha(n/k)==v for k,v in seal.items())
 g=read(n/'ENTRY_GATE_AUDIT.json');of=read(n/'OFFER_AUDIT.json');oldof=read(o/'OFFER_AUDIT.json')
 dec=rows(n/'joint/DECISIONS.csv'); olddec=rows(o/'joint/DECISIONS.csv')
 rounds=rows(n/'joint/ROUNDS.csv');oldrounds=rows(o/'joint/ROUNDS.csv')
 ab=read(n/'AB_DECISION_AUDIT.json');oldab=read(o/'AB_DECISION_AUDIT.json')
 issues=[];checks={}
 def ck(label,bad):
  checks[label]=dict(failures=len(bad),examples=bad[:12])
  if bad:issues.append(label)
 gm={key(x):x for x in g}; ofs=groups(of,key); dm=groups(dec,key)
 ck('unique_gate_sid_day',[str(k) for k,v in groups(g,key).items() if len(v)!=1])
 ck('deny_has_only_natural_application',[x for x in g if x['gate_status']!='ALLOW' and any(y['owner_lane']=='PRICE' and y['result']!='APPLICATION' for y in ofs[key(x)])])
 ck('deny_not_in_queue',[x for x in g if x['gate_status']!='ALLOW' and any(y['owner_lane']=='PRICE' for y in dm[key(x)])])
 ck('all_price_queue_has_allow',[x for x in dec if x['owner_lane']=='PRICE' and gm.get(key(x),{}).get('gate_status')!='ALLOW'])
 ck('gate_signal_close_initial_only',[x for x in g if x.get('clock')!='SIGNAL_CLOSE' or x.get('new_initial_only') is not True])
 ck('gate_excludes_state_blocked_and_ab_suppressed',[x for x in g if any(y['result'].startswith('BLOCKED_') or y['result']=='SUPPRESSED_BY_AB_VALID_CLOSE' for y in ofs[key(x)])])
 finals=[x for x in of if x['result'] in ['SELECTED_PENDING','PASS_NOT_TOP2']]
 fq=groups(finals,lambda x:(day(x['day']),x['sector']))
 rankbad=[];selbad=[];dk={(key(x),x['owner_lane']):x for x in dec}
 for q,rs in fq.items():
  for i,x in enumerate(sorted(rs,key=rank),1):
   z=dk.get((key(x),x['owner_lane']))
   if x['rank']!=i or z is None or int(float(z['joint_feasible_rank']))!=i:rankbad.append(dict(queue=q,expected=i,offer=x,decision=z))
   if (x['result']=='SELECTED_PENDING')!=(i<=2) or z is None or (z['selected']=='True')!=(i<=2):selbad.append(dict(queue=q,expected=i,offer=x))
 ck('independent_sector_pvr_ranking',rankbad);ck('independent_top_two_selected',selbad)
 ck('one_option_per_sid_day',[str(k) for k,v in groups(dec,key).items() if len(v)!=1])
 ck('offer_decision_bijection',[str((k,l)) for (k,l) in dk if sum(key(x)==k and x['owner_lane']==l for x in ofs[k] if x['result'] in ['SELECTED_PENDING','PASS_NOT_TOP2'])!=1])
 legal=[x for x in ab if x['decision_before_joint']=='PASS_TO_JOINT_QUEUE']
 ck('legal_ab_always_retained_as_same_stock_option',[x for x in legal if not any(y['owner_lane']=='AB' and y['event_id']==x['event_id'] for y in dm[key(x)])])
 ck('unknown_pvr_only_price',[x for x in dec if rank(x)[0] and x['owner_lane']!='PRICE'])
 apps=[x for x in of if x['result']=='APPLICATION']
 oldapps=[x for x in oldof if x['result']=='APPLICATION']
 ck('applications_exact_old_fixed_candidate_domain',[] if apps==oldapps else [dict(old_count=len(oldapps),new_count=len(apps),old_only=len(set(map(request,oldapps))-set(map(request,apps))),new_only=len(set(map(request,apps))-set(map(request,oldapps))))])
 ck('new_signal_dates_within_window',[x for x in rounds if not ('2022-01-01'<=x['signal_day']<='2022-12-31' if w=='2022' else '2024-09-01'<=x['signal_day']<='2024-12-31')])
 ck('no_action_after_horizon',[x for x in rows(n/'joint/ACTIONS.csv') if x['day']>'2026-06-30'])
 odm={(x['sid'],x['event_id']):x for x in olddec}
 sizing=['close_check','close_q','close_fee','close_plan_risk','close_floor_raw','prior20_capacity']
 ck('shared_price_queue_old_sizing_exact',[dict(key=(x['sid'],x['event_id']),fields=[f for f in sizing if x.get(f)!=odm[(x['sid'],x['event_id'])].get(f)]) for x in dec if x['owner_lane']=='PRICE' and (x['sid'],x['event_id']) in odm and any(x.get(f)!=odm[(x['sid'],x['event_id'])].get(f) for f in sizing)])
 # Independent lifecycle comparison, excluding only round IDs.
 rr={ (x['sid'],x['event_id']):x for x in rounds};orr={(x['sid'],x['event_id']):x for x in oldrounds}
 acts=groups(rows(n/'joint/ACTIONS.csv'),lambda x:x['round_id']);oacts=groups(rows(o/'joint/ACTIONS.csv'),lambda x:x['round_id'])
 claims=groups(read(n/'joint/CLAIMS.json'),lambda x:x['owner_round_id']);oclaims=groups(read(o/'joint/CLAIMS.json'),lambda x:x['owner_round_id'])
 claimfields=['sid','economic_event_id','evidence_version','record_date','inventory_snapshot_day','snapshot_kind','state','record_q','core_record_q','exitpending','amount','core_amount','recognized','settled','ex_date','pay_date','d_cash']
 def proj(a,fields=None):return [{k:v for k,v in x.items() if (k in fields if fields else k not in ['round_id','arm'])} for x in a]
 retained={};diff=[]
 for lane in ['AB','PRICE']:
  common=[k for k in rr.keys()&orr.keys() if rr[k]['owner_lane']==orr[k]['owner_lane']==lane]
  for k in common:
   a,b=orr[k],rr[k]; kinds=[]
   if proj(oacts[a['round_id']])!=proj(acts[b['round_id']]):kinds.append('actions')
   if proj(oclaims[a['round_id']],claimfields)!=proj(claims[b['round_id']],claimfields):kinds.append('claims')
   if any(a.get(f)!=b.get(f) for f in ['status','exit_day','exit_price','exit_reason']):kinds.append('exit')
   if kinds:diff.append(dict(lane=lane,sid=k[0],event_id=k[1],kinds=kinds))
  retained[lane]=dict(shared_rounds=len(common),changed=[x for x in diff if x['lane']==lane],old_only=sum(x['owner_lane']==lane and k not in rr for k,x in orr.items()),new_only=sum(x['owner_lane']==lane and k not in orr for k,x in rr.items()))
 # Dynamic AB effects must not be hidden by retained-exact result.
 oa={x['event_id']:x for x in oldab};abchanges=[]
 for x in ab:
  a=oa.get(x['event_id'],{})
  f=[z for z in ['stock_state_before','decision_before_joint','original_ab_queue_rank','original_ab_feasible_rank'] if x.get(z)!=a.get(z)]
  if f:abchanges.append(dict(event_id=x['event_id'],sid=x['sid'],day=x['day'],fields=f,old={z:a.get(z) for z in f},new={z:x.get(z) for z in f}))
 oldselected={request(x):x for x in oldof if x['result']=='SELECTED_PENDING'};newselected={request(x):x for x in of if x['result']=='SELECTED_PENDING'}
 displacement=[]
 for k in oldselected.keys()^newselected.keys():
  x=newselected.get(k,oldselected.get(k));gg=gm.get(key(x),{});natural=[y for y in ofs[key(x)] if y['owner_lane']==x['owner_lane'] and y['request_id']==x['request_id']]
  displacement.append(dict(sid=k[0],request_id=k[1],lane=x['owner_lane'],day=x['day'],old_selected=k in oldselected,new_selected=k in newselected,gate_status=gg.get('gate_status'),new_natural_results=[z['result'] for z in natural]))
 out=dict(window=w,source='READ_ONLY_SAVED_JSON_CSV_ONLY_NO_CONSUMER_IMPORT_OR_RUN',output_seal_sha256=sha(n/'OUTPUT_SEAL.json'),checks=checks,check_failure_labels=issues,counts=dict(gate_reads=len(g),gate_status=dict(Counter(x['gate_status'] for x in g)),applications=len(apps),queue_rows=len(dec),sector_queues=len(fq),rounds=len(rounds)),retained_lifecycle=retained,dynamic_ab_state_change_count=len(abchanges),dynamic_ab_state_changes=abchanges,selection_changes=displacement,limitations=['PVR ranking and selected sets independently rebuilt from natural final offers; sizing only crosschecked for shared old/new PRICE options, not independently economically rerun.','Candidate application domain checked exactly against original Joint baseline. Full parquet fixed domain delegated to separate domain auditor.','Retained lifecycle exactness does not imply all AB selections unaffected; changed AB events and dynamic state changes explicitly listed.','Existing continuation no-gate property checked structurally by parent/source review; no consumer replay.'])
 outp=D/'independent_post_run_audit'/('queue_paths_'+w+'.json')
 with outp.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2)
 print(json.dumps(dict(path=str(outp),failures=issues,counts=out['counts'],retained={k:{z:v for z,v in x.items() if z!='changed'}|dict(changed=len(x['changed'])) for k,x in retained.items()},ab_state_changes=len(abchanges),selection_changes=dict(Counter(x['lane']+('_new' if x['new_selected'] else '_lost') for x in displacement))),ensure_ascii=False))
if __name__=='__main__':main(sys.argv[1])
