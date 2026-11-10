"""Post-hoc exact-date coverage only. Does not simulate a strategy or recompute returns."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;B=O.parent;E=B.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def pct(a,b):return float(a/b) if b else None
def key(g,day):return list(zip(g.window,g.sid,g[day]))
def cat(parts):return pd.concat(parts,ignore_index=True)
for k in range(8):
 q=json.loads((O/('QA_'+str(k)+'.json')).read_text());assert q['original_M3_exact'] and q['all_sources_unchanged']
ev=cat([pd.read_csv(O/f'RECEIPTS_{k}.csv',parse_dates=['day','arm_day'],float_precision='round_trip') for k in range(8)])
tr=cat([pd.read_csv(O/f'CACHE_TRACE_{k}.csv',parse_dates=['day','arm_day'],float_precision='round_trip') for k in range(8)])
da=cat([pd.read_csv(O/f'DAILY_PATHS_{k}.csv',parse_dates=['day'],float_precision='round_trip') for k in range(8)])
qa=cat([pd.read_csv(O/f'SOURCE_AND_CLOCK_QA_{k}.csv') for k in range(8)])
assert not ev.duplicated(['window','arm','sid','day']).any()
assert not da.duplicated(['window','sid','day']).any()
sourcehash={}
for k in range(8):
 for p,h in json.loads((O/f'SOURCE_HASHES_{k}.json').read_text()).items():
  assert p not in sourcehash or sourcehash[p]==h
  sourcehash[p]=h
assert all(sha(p)==h for p,h in sourcehash.items())
save('SOURCE_HASHES.json',sourcehash)
old=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'],float_precision='round_trip')
old=old[old.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy()
assert set(key(old,'day'))==set(key(da,'day'))
sets={a:set(key(ev[ev.arm.eq(a)],'day')) for a in ['SAME_DAY','CACHED']}
assert sets['SAME_DAY']<=sets['CACHED']
assert set(key(ev[ev.arm.eq('CACHED')&ev.receipt_type.eq('IMMEDIATE')],'day'))==sets['SAME_DAY']
assert ev[ev.receipt_type.eq('DEFERRED')].old_birth_type.eq('B_STOCK_BIRTH_DURING_SECTOR').all()
fixed=pd.read_csv(B/'RECEIPTS.csv',parse_dates=['day','arm_day'])
scope=json.loads((B/'FIXED_SCOPE.json').read_text())
ss={(w,sid) for w,x in scope.items() for sid in x['stocks']}
subset=ev[[(w,s) in ss for w,s in zip(ev.window,ev.sid)]]
fields=['window','arm','sid','day','receipt_type','arm_day','delay']
assert set(map(tuple,fixed[fields].to_numpy()))==set(map(tuple,subset[fields].to_numpy()))
keep=['window','sid','day','mu5','M3_known','M3','sectorS','relative_known','relative_reason','relative_phase','relative_event','I_continuity_epoch','last_up_index','last_down_index']
x=old.merge(da[keep],on=['window','sid','day'],validate='one_to_one')
for a,s in sets.items():x[a+'_covered']=[k in s for k in key(x,'day')]
x['missing_primary']=np.select([~x.relative_known.eq(True),~x.M3_known.eq(True),~x.M3.eq(True),~x.I_qualified.eq(True),x.I_continuity_epoch.isna(),~x.sectorS.eq(1),~x.relative_event.eq(1)],['RELATIVE_UNKNOWN','M3_UNKNOWN','M3_NOT_RIGHT','I_NOT_QUALIFIED','I_CONTINUITY_UNKNOWN','SECTOR_NOT_RIGHT','NO_FRESH_RELATIVE_UP'],default='ELIGIBLE_SAME_DAY')
x.to_csv(O/'EVENT_COVERAGE.csv',index=False)
rows=[]
for (w,et),g in x.groupby(['window','event_type']):
 for scope,gg in [('RAW_A_B',g),('I_QUALIFIED',g[g.I_qualified.eq(True)]),('I_AND_PVR_KNOWN',g[g.I_and_PVR_known.eq(True)])]:
  for a in sets:
   n=int(gg[a+'_covered'].sum());rows.append(dict(window=w,event_type=et,denominator=scope,total=len(gg),candidate_arm=a,covered=n,missed=len(gg)-n,coverage_fraction=pct(n,len(gg)),relative_unknown=int((~gg.relative_known.eq(True)).sum())))
eventsummary=pd.DataFrame(rows);eventsummary.to_csv(O/'EVENT_SUMMARY.csv',index=False)
rnd=pd.read_csv(E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv',parse_dates=['signal_day','entry_day','exit_day'],float_precision='round_trip')
rnd=rnd.merge(x[['window','sid','day','relative_known','relative_reason','missing_primary']].rename(columns={'day':'signal_day'}),on=['window','sid','signal_day'],validate='many_to_one')
assert rnd.round_id.is_unique
assert rnd.core_return.notna().equals(rnd.status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND"))
assert np.isfinite(rnd.loc[rnd.core_return.notna(),["core_net","core_return"]].to_numpy()).all()
for a,s in sets.items():rnd[a+'_covered']=[k in s for k in key(rnd,'signal_day')]
assert set(key(rnd,'signal_day'))<=set(key(x,'day'))
rnd['known_core_label']=np.select([rnd.core_return.gt(0),rnd.core_return.lt(0),rnd.core_return.eq(0)],['WIN','LOSS','FLAT'],default='UNKNOWN_OR_UNCLOSED')
rnd['tail_ge20']=rnd.core_return.ge(.2);rnd['tail_ge50']=rnd.core_return.ge(.5);rnd['tail_top_decile_positive']=False;rnd['top10_positive']=False
tail_thresholds=[]
for (w,a),g in rnd.groupby(['window','arm']):
 pos=g[g.core_return.gt(0)].sort_values(['core_return','round_id'],ascending=[False,True]);n=int(math.ceil(len(pos)/10))
 rnd.loc[pos.head(n).index,'tail_top_decile_positive']=True;rnd.loc[pos.head(10).index,'top10_positive']=True
 tail_thresholds.append(dict(window=w,old_arm=a,positive_rounds=len(pos),tail_count=n,lowest_included_return=pos.head(n).core_return.min() if n else None))
rnd.to_csv(O/'ROUND_COVERAGE.csv',index=False)
rnd.groupby(['window','arm','known_core_label','relative_known','missing_primary','SAME_DAY_covered','CACHED_covered'],dropna=False).size().rename('rounds').reset_index().to_csv(O/'LABEL_CLOCK_BREAKDOWN.csv',index=False)
save('TAIL_THRESHOLDS.json',tail_thresholds)
rows=[];tailrows=[];statusrows=[]
for (w,oldarm),g in rnd.groupby(['window','arm']):
 known=g[g.core_return.notna()]
 for a in sets:
  hit=g[g[a+'_covered']];kh=hit[hit.core_return.notna()]
  win=g.core_return.gt(0);loss=g.core_return.lt(0)
  rows.append(dict(window=w,old_arm=oldarm,candidate_arm=a,original_rounds=len(g),covered_rounds=len(hit),original_known_label_relative_unknown=int((g.core_return.notna()&~g.relative_known.eq(True)).sum()),original_wins_relative_unknown=int((g.core_return.gt(0)&~g.relative_known.eq(True)).sum()),original_entered=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),covered_entered=int(hit.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),original_complete=len(known),covered_complete=len(kh),original_wins=int(win.sum()),covered_wins=int(kh.core_return.gt(0).sum()),original_losses=int(loss.sum()),covered_losses=int(kh.core_return.lt(0).sum()),original_zero=int(g.core_return.eq(0).sum()),covered_zero=int(kh.core_return.eq(0).sum()),original_unknown=int(g.status.str.contains('UNKNOWN').sum()),covered_unknown=int(hit.status.str.contains('UNKNOWN').sum()),original_unclosed_other=int((g.core_return.isna()&~g.status.str.contains('UNKNOWN')).sum()),covered_unclosed_other=int((hit.core_return.isna()&~hit.status.str.contains('UNKNOWN')).sum()),coverage_complete=pct(len(kh),len(known)),win_retention=pct(int(kh.core_return.gt(0).sum()),int(win.sum())),loss_retention=pct(int(kh.core_return.lt(0).sum()),int(loss.sum())),old_label_win_share_all=pct(int(win.sum()),len(known)),old_label_win_share_covered=pct(int(kh.core_return.gt(0).sum()),len(kh)),positive_core_cash_retention=pct(float(kh.loc[kh.core_net.gt(0),'core_net'].sum()),float(g.loc[g.core_net.gt(0),'core_net'].sum())),negative_core_cash_retention=pct(float(kh.loc[kh.core_net.lt(0),'core_net'].sum()),float(g.loc[g.core_net.lt(0),'core_net'].sum()))))
  for name in ['tail_ge20','tail_ge50','tail_top_decile_positive','top10_positive']:
   tail=g[g[name]];ht=tail[tail[a+'_covered']]
   tailrows.append(dict(window=w,old_arm=oldarm,candidate_arm=a,tail_definition=name,total=len(tail),original_relative_unknown=int((~tail.relative_known.eq(True)).sum()),covered=len(ht),missed=len(tail)-len(ht),retention=pct(len(ht),len(tail)),old_core_positive_cash_retention=pct(float(ht.core_net.sum()),float(tail.core_net.sum()))))
  for status,sg in g.groupby('status'):
   statusrows.append(dict(window=w,old_arm=oldarm,candidate_arm=a,status=status,total=len(sg),covered=int(sg[a+'_covered'].sum())))
summary=pd.DataFrame(rows);summary.to_csv(O/'ROUND_SUMMARY.csv',index=False)
tails=pd.DataFrame(tailrows);tails.to_csv(O/'TAIL_SUMMARY.csv',index=False)
pd.DataFrame(statusrows).to_csv(O/'ROUND_STATUS_SUMMARY.csv',index=False)
rnd[rnd.tail_top_decile_positive|rnd.tail_ge50|rnd.top10_positive].to_csv(O/'RIGHT_TAIL_CASES.csv',index=False)
# Describe original A/B labels newly retained only through the frozen cache. Not incremental simulated PnL.
extra=rnd[rnd.CACHED_covered&~rnd.SAME_DAY_covered].copy();extra.to_csv(O/'CACHE_ADDED_OLD_ROUNDS.csv',index=False)
ev.to_csv(O/'ALL_RECEIPTS.csv',index=False)
qa.to_csv(O/'SOURCE_AND_CLOCK_QA.csv',index=False)
ev.groupby(['window','arm','receipt_type','old_birth_type']).size().rename('receipts').reset_index().to_csv(O/'RECEIPT_COUNTS.csv',index=False)
miss=x[~x.CACHED_covered].groupby(['window','event_type','missing_primary']).size().rename('events').reset_index();miss.to_csv(O/'MISSED_EVENT_REASONS.csv',index=False)
ct=tr[tr.arm.eq('CACHED')]
endpending=ct.sort_values('day').groupby(['window','sid']).tail(1)
endpending=endpending[endpending.pending.eq(True)].copy()
endpending.to_csv(O/'CACHE_WINDOW_END_PENDING.csv',index=False)
assert int(ct.action.eq('ARM').sum())==int(ct.action.eq('RECEIPT_DEFERRED').sum())+int(ct.action.str.startswith('CANCEL_').sum())+len(endpending)
save('QA.json',dict(stocks=len(qa),all_A_B_events=len(x),all_source_hashes_matched=len(sourcehash),fixed_case_receipts_exactly_reproduced=True,all_deferred_are_originalB=True,no_duplicate_receipts=True,immediate_branches_identical=True,original_M3_exact=True,I_continuity_inconsistent=int(qa.I_continuity_inconsistent.sum()),actual_arm_count=int(ct.action.eq('ARM').sum()),deferred_count=int(ct.action.eq('RECEIPT_DEFERRED').sum()),cancel_count=int(ct.action.str.startswith('CANCEL_').sum()),birth_window_end_pending=len(endpending),new_trading_simulation=False,new_return_computation=False,NON_PIT=True))
print('EVENT SUMMARY RAW');print(eventsummary[eventsummary.denominator.eq('RAW_A_B')].to_string(index=False))
print('ROUND SUMMARY');print(summary.to_string(index=False))
print('TAIL SUMMARY');print(tails.to_string(index=False))
print('EXTRA OLD LABELS');print(extra.groupby(['window','arm','known_core_label']).size().to_string())
print('DONE')
