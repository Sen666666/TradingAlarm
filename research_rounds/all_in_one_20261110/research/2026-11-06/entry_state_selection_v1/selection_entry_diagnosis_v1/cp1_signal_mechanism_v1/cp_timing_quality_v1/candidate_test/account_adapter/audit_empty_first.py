from pathlib import Path
import json,gzip,hashlib,time
import pandas as pd,numpy as np
from ce_adapter import CELookup
from empty_first_rank import rank_empty_first_stock_slots
O=Path(__file__).resolve().parent;P=O.parent
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1/run_1200000/pair')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
start=time.monotonic();loader=CELookup();sources={str(p):sha(p) for p in [R/'PVR.json.gz',R/'E31.json.gz',R/'daily.jsonl.gz',O/'empty_first_rank.py',Path(__file__)]}
# No PnL, wins, exits or forward labels are read/used. Only original daily holdings and pending roles/ranks.
held={}
for line in gzip.open(R/'daily.jsonl.gz','rt'):
    d=json.loads(line);held[(d['account'],d['at'][:10])]=set(d['positions'])
rows=[];details=[];replay_exact=True
for account in ['PVR','E31']:
    a=json.load(gzip.open(R/(account+'.json.gz'),'rt'))
    for d in a['decisions']:
        day=d['at'][:10];by={}
        for i in d['intents']:by.setdefault(i['sid'],[]).append(i)
        if not by:continue
        positions=held[(account,day)];frame=[]
        for sid,intents in by.items():
            r=intents[0];roles={i['role'] for i in intents};assert all(i['rank']==r['rank'] for i in intents)
            frame.append(dict(sid=sid,rank=r['rank'],was_empty=sid not in positions,has_core_intent='core' in roles,has_mobile_intent='mobile' in roles,PVR_score=r.get('PVR_score'),PVR_ready=bool(r.get('PVR_ready',False)),priority_rank=r.get('priority_rank'),source_account=account))
        frame=pd.DataFrame(frame);ranked,audit=rank_empty_first_stock_slots(frame,day,loader);audit.update(account=account,year=int(day[:4]));rows.append(audit)
        # Independent baseline-slot replay uses original keys; compare final account-scope order.
        original=frame.sort_values(['rank','sid']).reset_index(drop=True);ranked_by=ranked.set_index('sid');movable=[sid for sid in original.sid if bool(ranked_by.at[sid,'CE_movable_stock_slot'])]
        ordered=sorted(movable,key=lambda sid:(-round(float(ranked_by.at[sid,'CE']),12),-round(float(original.set_index('sid').at[sid,'PVR_score']),12),float(original.set_index('sid').at[sid,'rank']),sid));it=iter(ordered)
        expected=[next(it) if sid in set(movable) else sid for sid in original.sid];assert ranked.sid.tolist()==expected
        assert all(ranked_by.at[sid,'ce_stock_rank']==original.set_index('sid').at[sid,'rank'] for sid in original.sid if sid not in set(movable))
        z=ranked[['sid','rank','ce_stock_rank','was_empty','has_core_intent','has_mobile_intent','CE_known','CE_movable_stock_slot','CE_status']].copy();z['account']=account;z['day']=day;details.append(z)
    print('EMPTY_FIRST_ACCOUNT',account,flush=True)
q=pd.DataFrame(rows);q.to_csv(O/'EMPTY_FIRST_QUEUE_SCOPE_AUDIT.csv',index=False);detail=pd.concat(details,ignore_index=True);detail.to_parquet(O/'EMPTY_FIRST_ORIGINAL_PENDING_SCOPE.parquet',index=False)
counts=[c for c in q if c not in ['scope','signal_day','account','year','all_fixed_slots_exact','original_fields_unchanged','all_stock_groups_retained','K_applied']]
annual=q.groupby(['account','year'])[counts].sum().reset_index();annual.to_csv(O/'EMPTY_FIRST_SCOPE_BY_YEAR.csv',index=False);overall=q.groupby('account')[counts].sum().reset_index();overall.to_csv(O/'EMPTY_FIRST_SCOPE_OVERALL.csv',index=False)
# Boundary matrix includes parent-requested all-unknown object dtype and empty frames.
fixture=pd.DataFrame([dict(sid=s,rank=r,was_empty=e,has_mobile_intent=m,has_core_intent=c,PVR_score=p,PVR_ready=ready,priority_rank=r+100,budget=12345.) for s,r,e,m,c,p,ready in [('600056.SH',10,True,True,True,88.,True),('601607.SH',20,True,False,True,80.,True),('001232.SZ',40,True,False,True,None,False),('600606.SH',70,True,True,False,np.nan,True),('300182.SZ',90,False,True,False,78.,True),('600299.SH',99,True,False,True,54.,True)]])
before=fixture.copy(deep=True);out,aa=rank_empty_first_stock_slots(fixture,'2022-03-03',loader)
assert out.set_index('sid').at['600299.SH','ce_stock_rank']==10
assert out.set_index('sid').at['600056.SH','ce_stock_rank']==99
assert out[out.sid.isin(['001232.SZ','600606.SH','300182.SZ'])].ce_stock_rank.eq(out[out.sid.isin(['001232.SZ','600606.SH','300182.SZ'])]['rank']).all()
pd.testing.assert_frame_equal(before,fixture,check_exact=True)
for unknown in [None,np.nan]:
    unknowns=fixture.copy();unknowns['PVR_score']=pd.Series([unknown]*len(unknowns),dtype=object);u,ua=rank_empty_first_stock_slots(unknowns,'2022-03-03',loader);assert u.ce_stock_rank.eq(u['rank']).all() and ua['movable_stock_groups']==0
empty=pd.DataFrame(columns=list(fixture.columns));e,ea=rank_empty_first_stock_slots(empty,'2022-03-03',loader);assert len(e)==0
zero=fixture.copy();zero.was_empty=False;z,za=rank_empty_first_stock_slots(zero,'2022-03-03',loader);assert z.ce_stock_rank.eq(z['rank']).all()
single=zero.copy();single.loc[single.sid=='600056.SH','was_empty']=True;s,sa=rank_empty_first_stock_slots(single,'2022-03-03',loader);assert s.ce_stock_rank.eq(s['rank']).all() and sa['movable_stock_groups']==1
nofresh=fixture.copy();n,na=rank_empty_first_stock_slots(nofresh,'1900-01-01',loader);assert n.ce_stock_rank.eq(n['rank']).all() and na['movable_stock_groups']==0
restart=CELookup();out2,a2=rank_empty_first_stock_slots(fixture,'2022-03-03',restart);pd.testing.assert_frame_equal(out,out2,check_exact=True);assert aa==a2
for p,h in sources.items():assert sha(p)==h
for p,h in json.loads((O/'ORIGINAL_TEST_FILES_BEFORE.json').read_text()).items():assert sha(p)==h
# Preserve all prior narrow-scope artifacts and source identities.
for name,h in json.loads((O/'FINAL_HANDOFF_HASHES.json').read_text()).items():assert sha(O/name)==h,name
result=dict(status='READY_ALL_EMPTY_FIRST_ENTRY_SCOPE',scope='was_empty AND current fresh CE known AND original PVR ready/finite; CORE/MOBILE role does not restrict membership',queues_audited=len(q),stock_group_observations=len(detail),original_queue_replay_exact=True,all_fixed_slots_exact=True,all_original_fields_unchanged=True,no_K20=True,no_old_receipt_reuse=True,full_object_None_NaN_unknown_PVR_pass=True,zero_row_zero_movable_single_movable_pass=True,CORE_only_fresh_CE_movable_and_no_fresh_CE_fixed=True,restart_exact=True,source_hashes_unchanged=True,old_narrow_scope_artifacts_unchanged=True,old_diagnostic_artifacts_unchanged=True,account_runs=0,seconds=time.monotonic()-start)
dump('EMPTY_FIRST_AUDIT.json',result);dump('EMPTY_FIRST_SOURCE_HASHES.json',sources)
manifest=dict(status='READY_ALL_EMPTY_FIRST_ENTRY_SCOPE',interface='empty_first_rank.rank_empty_first_stock_slots(frame, signal_day, lookup) -> (ranked_frame, audit_dict)',constructor='empty_first_rank.load_empty_first_inputs(directory=None) -> CELookup',scope=result['scope'],supersedes_for_new_account_only='account_rank.rank_stock_slots MOBILE-only scope retained as historical artifact',original_diagnostic_not_equivalent=True,runtime_sha256={n:sha(O/n) for n in ['empty_first_rank.py','ce_adapter.py','ALL_NATIVE_CP_RECEIPT_CE.parquet','STOCK_COVERAGE.csv','ADAPTER_MANIFEST.json']},audit_sha256=sha(O/'EMPTY_FIRST_AUDIT.json'),source_hashes_sha256=sha(O/'EMPTY_FIRST_SOURCE_HASHES.json'),full_pool_audit_sha256=sha(O/'ADAPTER_AUDIT.json'),no_K=True,no_account_state_in_scores=True,account_runs=0)
dump('EMPTY_FIRST_MANIFEST.json',manifest)
print(json.dumps(result,ensure_ascii=False),flush=True);print(overall.to_string(index=False),flush=True);print('MANIFEST_SHA256',sha(O/'EMPTY_FIRST_MANIFEST.json'),flush=True)
