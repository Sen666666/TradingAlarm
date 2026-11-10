"""Input/partial-only audit of resource continuation, zero paths or markets."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,json,time
R=Path(__file__).resolve().parent;I=R.parent;P=I/'labels_new';S=P/'remaining_shards';W=I.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
t0=time.monotonic();plan=read(S/'REMAINING_SHARD_PLAN.json');timing=read(P/'FULL_LABEL_TIMING.json');oldgate=read(R/'FULL_SINGLE_ASSET_LABEL_ADMISSION.json')
for p,s in plan['source_sha256'].items():assert sha(p)==s,(p,'continuation source drift')
for p,s in timing['source_sha256'].items():assert sha(p)==s,(p,'prior full source drift')
assert plan['source_sha256'][str((P/'native_single_asset.py').resolve())]==oldgate['final_helper_sha256']=='c9d7632bb6f6103979d91a676b8a7efbed9f2a7c69bc3dfaa6c635be1c1b87bd'
whole={x['key']:x for x in rows(I/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz')if x['is_first_sector_reject_in_original_source_I_epoch']};assert len(whole)==8335
prior=list(rows(P/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz'));done={x['key']for x in prior};assert len(done)==len(prior)==3879 and done<=set(whole)
assert Counter(x['status']for x in prior)==Counter(timing['statuses'])==Counter({'closed':3871,'entry_nonfill':8});assert all(x['window']=='long'for x in prior)
assert timing['timed_out']and timing['failure']is None and timing['counts']['label_attempts']==3880 and timing['counts']['single_asset_shadow_paths']==3879 and timing['incomplete_path_key']not in done
seen=set();sids=set();sums=[]
for z in plan['shards']:
 p=Path(z['event_file']);assert sha(p)==z['event_file_sha256'];rs=list(rows(p));ks={r['key']for r in rs};ss={r['sid']for r in rs};assert len(ks)==len(rs)==z['events']==1114 and len(ss)==z['SIDs'];assert not(ks&done)and not(ks&seen)and not(ss&sids)
 assert ks==set(z['keys'])and ss==set(z['sids']);assert dict(Counter(r['window']for r in rs))==z['windows']
 assert z['input_only_scheduling_weight']==len(rs)+40*len(ss)
 assert all(r==whole[r['key']]for r in rs),'event contents changed by sharding'
 seen|=ks;sids|=ss;sums.append({k:z[k]for k in ['shard','events','SIDs','windows','input_only_scheduling_weight']})
assert seen==set(whole)-done and len(seen)==4456 and done|seen==set(whole)and timing['incomplete_path_key']in seen
# Rebuild input-only greedy assignment independently; no numeric outcome field is accessed.
by=defaultdict(list)
for k in set(whole)-done:by[whole[k]['sid']].append(k)
loads=[0]*4;assigned=[set()for _ in range(4)];event_count=[0]*4
for sid,ks in sorted(by.items(),key=lambda p:(-len(p[1]),p[0])):
 j=min(range(4),key=lambda n:(loads[n],event_count[n],n));assigned[j].add(sid);loads[j]+=40+len(ks);event_count[j]+=len(ks)
for z in plan['shards']:assert assigned[z['shard']]==set(z['sids'])
res={'passed':True,'scope':'Resource-only partition/identity audit. New runner/card budget admission still separate; no new single-asset or portfolio path constructed.','original_first_events':8335,'prior_completed_rows_immutable':3879,'prior_completed_windows':{'long':3879},'prior_statuses':dict(Counter(x['status']for x in prior)),'remaining_events':4456,'remaining_by_window':dict(Counter(whole[k]['window']for k in seen)),'shards':sums,'all_remaining_records_equal_original_mother':True,'disjoint_remaining_SID_sets':True,'input_only_schedule_independently_reconstructed':True,'old_completed_never_replayed':True,'initial_incomplete_key_has_no_completed_row_and_is_remaining':True,'native_helper_and_original15_dependency_hashes_unchanged':True,'original_compute_seconds':timing['seconds'],'proposed_additional_budget':{'processes':4,'per_process_seconds':90,'aggregate_process_seconds':360,'automatic_extension':False,'needs_final_runner_card_source_gate':True},'root_explicit_resource_revision':'One extra resource-only continuation after observed initial throughput; same mother/q_min/fees/exit/CA and frozen ACT, no result-conditioned rule or schedule.','reviewer_new_single_asset_paths':0,'reviewer_new_mark_or_state_builds':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),S/'REMAINING_SHARD_PLAN.json',P/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz',P/'FULL_LABEL_TIMING.json',P/'prepare_remaining_shards.py',P/'native_single_asset.py']},'seconds':time.monotonic()-t0}
(R/'REMAINING_SHARD_IDENTITY_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k!='source_sha256'},indent=2))
