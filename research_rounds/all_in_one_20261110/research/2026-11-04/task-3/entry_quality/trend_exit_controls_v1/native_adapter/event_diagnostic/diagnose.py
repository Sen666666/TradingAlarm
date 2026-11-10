"""Original-path first known early-tool breaks, strictly before first request.

No candidate accounts, pending replay, indicator model, or hypothetical PnL.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import gzip,hashlib,json,sys,time

O=Path(__file__).resolve().parent
R=O.parents[1]
E=R/'execution_review'
Q=R.parent/'entry_exit_scale/holding_exit'
T=R.parent/'local_high'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
sys.path.insert(0,str(R));from indicator_provider import IndicatorProvider
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def money(rr):
 v=[D(x['original_net']) for x in rr]
 return dict(layers=len(rr),cost=str(sum((D(x['original_cost']) for x in rr),D(0))),net=str(sum(v,D(0))),positive=str(sum((x for x in v if x>0),D(0))),negative=str(sum((x for x in v if x<0),D(0))),positive_layers=sum(x>0 for x in v),negative_layers=sum(x<0 for x in v))
def grouped(rr):
 touched=[x for x in rr if x['first_known_break'] is not None];allm=money(rr);tm=money(touched)
 return dict(original_mother=allm,touched_original_contribution=tm,
  positive_contribution_touched_share=None if D(allm['positive'])==0 else str(D(tm['positive'])/D(allm['positive'])),
  negative_contribution_touched_share=None if D(allm['negative'])==0 else str(D(tm['negative'])/D(allm['negative'])),
  row_status=dict(Counter(x['status'] for x in rr)),unknown_before_first_break_layers=sum(bool(x['unknown_before_first_known_break_count']) for x in touched))

t0=time.monotonic();provider=IndicatorProvider();tools=('EMA20','EMA60','BOLL20_MID','BOLL20_LOWER')
manifest=read(R/'indicators/MANIFEST.json');assert sha(R/'indicators/MANIFEST.json')==provider.manifest_sha256
SRC[str(Path(manifest['data_file']))]=sha(manifest['data_file']);assert SRC[str(Path(manifest['data_file']))]==manifest['data_sha256']
SRC[str(R/'indicator_provider.py')]=sha(R/'indicator_provider.py')
freeze=read(R/'STATE_MACHINE_FREEZE.json');assert freeze['conflict_priority'][-1].startswith('additional indicator')
review_sources=read(E/'NO_SOFT_GRACE_SOURCE_SHA256.json')
ALL={};SUMMARY={};TAILS={};VALID={}
roots={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':B/'pvr_pool_feasibility/runs/2025_26/pair'}
for ref,pair in roots.items():
 mother=read(Q/(ref+'_LAYERS.json'));mm={x['layer']:x for x in mother};expected=2265 if ref=='2022_2024' else 1171;assert len(mm)==expected
 ds=read(pair/'daily.jsonl.gz',gz=True,lines=True);book=read(pair/'B.json.gz',gz=True)
 for file in (pair/'daily.jsonl.gz',pair/'B.json.gz'):assert SRC[str(file)]==review_sources[str(file)]
 ioff=read(E/(ref+'_ALL_HELD_IOFF_CLOSES.json'));off={(x['layer'],x['at']) for x in ioff};assert len(off)==len(ioff)
 firstrequest={};raw_requests=defaultdict(list)
 for a in book['audit']:
  if a['kind']=='pilot_layer_exit':
   for lid in a['layers']:
    firstrequest[lid]=min(firstrequest.get(lid,a['at']),a['at']);raw_requests[lid].append(a)
 for h in mother:
  earliest=min((x['at'] for x in h['original_exit_request_events']),default=None)
  assert earliest==firstrequest.get(h['layer'])
 cutoffnotes=[]
 cancel_audit=[a for a in book['audit'] if 'cancel' in a['kind'].lower() or 'exit_release' in a['kind'].lower()]
 # No assumptions about absence of a cancellation: never reopen after first
 # saved layer request even if later original observations still exist.
 rows={(h['layer'],tool):dict(window=ref,layer=h['layer'],sid=h['sid'],name=h['name'],role=h['role'],action=h['action'],opened_at=h['opened'],decision_at=h['decision_at'],original_actual_exit_class=h['actual_exit_class'],original_terminal_state=h['terminal_equity_state'],original_cost=h['cost'],original_net=h['net'],original_strict_realized=h['strict_realized'],original_open_unrealized=h['open_unrealized'],tool=tool,first_original_specific_layer_request_at=firstrequest.get(h['layer']),status='NO_KNOWN_PRE_REQUEST_BREAK',first_known_break=None,eligible_original_held_CLOSEs=0,provider_unknown_count=0,provider_unknown_reason_counts={},provider_unknown_days=[],unknown_before_first_known_break_count=0,observations_at_or_after_first_request_excluded=0,ACT_off_observations_excluded=0,I_off_observations_excluded=0,all_original_held_CLOSEs=0) for h in mother for tool in tools}
 observed=Counter();off_seen=set();dayindex={x['at'][:10]:i for i,x in enumerate(ds)};unique_unknown=Counter()
 for d in ds:
  at=d['at']
  for x in d['layers']:
   lid=x['id'];h=mm[lid];observed[lid]+=1;assert x['sid']==h['sid'] and int(x['qty'])>0 and at>=h['opened']
   isoff=(lid,at) in off
   if isoff:off_seen.add((lid,at))
   for tool in tools:
    z=rows[lid,tool];z['all_original_held_CLOSEs']+=1
    cutoff=z['first_original_specific_layer_request_at']
    # Strict exclusion includes the original request CLOSE itself: I/ACT/CP
    # already has responsibility at that bar, even though no actual fill yet.
    if cutoff is not None and at>=cutoff:
     z['observations_at_or_after_first_request_excluded']+=1;continue
    if not d['on']:
     z['ACT_off_observations_excluded']+=1;continue
    if isoff:
     z['I_off_observations_excluded']+=1;continue
    z['eligible_original_held_CLOSEs']+=1
    q=provider.at(h['sid'],at,tool)
    assert q['day']==at[:10] and q['status'] in ('READY','UNKNOWN')
    if q['status']=='UNKNOWN':
     z['provider_unknown_count']+=1;reason=q['unknown_reason'];z['provider_unknown_reason_counts'][reason]=z['provider_unknown_reason_counts'].get(reason,0)+1;z['provider_unknown_days'].append(at)
     unique_unknown[(h['sid'],at,tool,reason)]+=1;continue
    assert q['source_max_day']<=at[:10]
    if q['causal_close']<q['line'] and z['first_known_break'] is None:
     z['unknown_before_first_known_break_count']=z['provider_unknown_count']
     z['first_known_break']=dict(at=at,day=at[:10],causal_close=q['causal_close'],indicator_line=q['line'],source_segment=q['source_segment'],source_max_day=q['source_max_day'],price_domain='original causal adjusted signal price within this source segment; not raw executable quote',original_ACT_on=True,original_I_target=True,original_layer_exit_not_yet_requested=True,
      original_native_market_CLOSE_steps_before_first_request=None if cutoff is None else dayindex[cutoff[:10]]-dayindex[at[:10]],original_held_CLOSE_number=observed[lid],unknown_observations_preceding_this_known_break=z['provider_unknown_count'])
 for (lid,tool),z in rows.items():
  assert z['all_original_held_CLOSEs']==mm[lid]['held_close_observations']
  if z['first_known_break'] is not None:
   z['status']='FIRST_KNOWN_BREAK_WITH_EARLIER_UNKNOWN' if z['unknown_before_first_known_break_count'] else 'FIRST_KNOWN_PRE_REQUEST_BREAK'
   assert z['first_original_specific_layer_request_at'] is None or z['first_known_break']['at']<z['first_original_specific_layer_request_at']
  elif z['provider_unknown_count']:
   z['status']='NO_KNOWN_BREAK_WITH_UNKNOWN_INPUT'
  elif not z['eligible_original_held_CLOSEs']:
   z['status']='NO_PRE_REQUEST_ELIGIBLE_CLOSE'
 assert off_seen==off and sum(observed.values())==(36213 if ref=='2022_2024' else 21000)
 rr=list(rows.values());ALL[ref]=rr;save(ref+'_FIRST_KNOWN_TOOL_BREAK_ROWS.json',rr)
 scopes={'all':rr}
 if ref=='2022_2024':
  scopes['weak2022_2023']=[x for x in rr if x['opened_at'][:10]<'2024-01-01']
  scopes['post303']=[x for x in rr if '2024-10-09'<=x['opened_at'][:10]<='2024-12-31'];assert len(scopes['post303'])==303*4
  scopes['2024_all']=[x for x in rr if x['opened_at'][:10]>='2024-01-01']
 for scope,scope_rows in scopes.items():
  for tool in tools:
   base=[x for x in scope_rows if x['tool']==tool]
   actions=sorted({x['action'] for x in base});exits=sorted({x['original_actual_exit_class'] for x in base})
   SUMMARY[ref+'|'+scope+'|'+tool]=dict(all=grouped(base),by_action={a:grouped([x for x in base if x['action']==a]) for a in actions},by_final_actual_exit={e:grouped([x for x in base if x['original_actual_exit_class']==e]) for e in exits},complete_action_exit_cells=[dict(action=a,final_actual_exit=e,**grouped([x for x in base if x['action']==a and x['original_actual_exit_class']==e])) for a in actions for e in exits])
 tails=read(T/(ref+'_FIXED_TAILS.json'));assert len(tails)==(83 if ref=='2022_2024' else 94)
 controls=[]
 for tr in tails:
  old=tr['original'];matched=tr['matched_actual_No60_rows'];members=[]
  for m in matched:
   h=mm[m['layer']]
   for k in ('sid','decision_at','role','opened','budget_order'):assert h[k]==m[k],('No60 exact original intent match',k)
   members.append(dict(actual_No60_layer=m['layer'],actual_No60_original_contribution=h['net'],by_tool={tool:rows[m['layer'],tool] for tool in tools}))
  controls.append(dict(original_fixed_tail=old,original_fixed_tail_contribution=old['net'],No60_match_status='EXACT_MATCHED_ORIGINAL_INTENT' if members else 'NO_MATCH_IN_NO60_ACTUAL_MOTHER',matched_No60=members,unknown_if_unmatched='Original PVR tail has no exact No60 participation; not classified untouched, not joined by cross-arm layer ID.' if not members else None))
 TAILS[ref]=controls
 save(ref+'_FULL_FIXED_TAIL_CONTROLS.json',controls)
 tail_summary={}
 for tool in tools:
  matched=[x for x in controls if x['matched_No60']];touched=[x for x in matched if any(m['by_tool'][tool]['first_known_break'] is not None for m in x['matched_No60'])]
  actualids=sorted({m['actual_No60_layer'] for x in matched for m in x['matched_No60']});touchids=sorted({m['actual_No60_layer'] for x in touched for m in x['matched_No60'] if m['by_tool'][tool]['first_known_break'] is not None})
  tail_summary[tool]=dict(all_original_tail_members=len(controls),matched_original_tail_members=len(matched),unmatched_unknown_original_tail_members=len(controls)-len(matched),touched_original_tail_members=len(touched),original_fixed_tail_contribution_total=str(sum((D(x['original_fixed_tail_contribution']) for x in controls),D(0))),original_fixed_tail_contribution_of_matched=str(sum((D(x['original_fixed_tail_contribution']) for x in matched),D(0))),original_fixed_tail_contribution_of_touched=str(sum((D(x['original_fixed_tail_contribution']) for x in touched),D(0))),No60_matched_original_money=money([rows[lid,tool] for lid in actualids]),No60_touched_original_money=money([rows[lid,tool] for lid in touchids]),interpretation='Original PVR tail contributions and No60 actual contributions are separate; event overlap is potential exposure only, not foregone gain or saved loss.')
 save(ref+'_FIXED_TAIL_SUMMARY.json',tail_summary)
 VALID[ref]=dict(original_entries=len(mother),rows=len(rr),tools=4,original_held_layer_CLOSEs=sum(observed.values()),full_held_Ioff_index_reused=len(off),all_original_Ioff_rows_seen=True,all_mother_held_counts_exact=True,strict_before_first_specific_layer_request=True,same_request_day_CP_ACT_I_excluded=True,observed_explicit_cancellation_kind_records=len(cancel_audit),cancellation_semantics='After first request always excluded; no inferred cancellation/reopening. Absence of explicit cancel kinds is not proof no native pending changes.',unique_unknown_observations=[dict(sid=k[0],at=k[1],tool=k[2],reason=k[3],layer_memberships=v) for k,v in unique_unknown.items()],fixed_tail_members=len(controls),fixed_tail_matched=sum(bool(x['matched_No60']) for x in controls))
save('SUMMARY.json',SUMMARY)
save('VALIDATION.json',dict(passed=True,refs=VALID,provider_manifest_sha256=provider.manifest_sha256,new_accounts=0,new_native_events=0,new_indicators=0,financial_output='Original saved full-lifecycle layer money only; no static alternative PnL, no implied saved loss or winner loss.',elapsed_seconds=time.monotonic()-t0))
save('PROTOCOL.json',dict(mother='All original No60 2265 three-year +1171 strong actual layers, all57213 actual held CLOSE snapshots. No winner/loser selection of tool points.',event='Each tool first READY current causal-close strictly below frozen tool line on actual held original path, while ACT on, original I on, strictly before earliest original layer-specific request. Equality no break; UNKNOWN retained.',priority='ACT>I>original mobile old-floor CP>tool. Conservative earliest-layer-request cutoff never reopens, even if a later cancel might exist. No pending replay.',first_known='Earlier unknown remains explicit; reported first known is not asserted true first if missing earlier tool values.',groups='Full original signed-money denominators by period/action/final actual exit and full fixed83/94 old tail list, with exact No60 intent matches only.',limits=['This keeps the original account path after hypothetical tool exit and cannot include endogenous allocation, ACT, fees or legal execution changes.','Touching an original losing layer does not quantify avoidable loss; touching an original winner does not quantify foregone gain.','Unmatched original PVR tails remain unknown in No60 mother, never called untouched.']))
SRC[str(__file__)]=sha(__file__);save('SOURCE_SHA256.json',SRC)
print('DONE',sum(v['original_entries'] for v in VALID.values()),sum(v['original_held_layer_CLOSEs'] for v in VALID.values()),'seconds',round(time.monotonic()-t0,2))
for key,value in SUMMARY.items():
 if '|weak2022_2023|' in key or '|post303|' in key or key.startswith('strong|all|'):print(key,json.dumps(value['all'],ensure_ascii=False))
