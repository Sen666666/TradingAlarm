from pathlib import Path
import gzip,json,hashlib,time
import pandas as pd,numpy as np
from ce_adapter import CELookup
from account_rank import rank_stock_slots
O=Path(__file__).resolve().parent;P=O.parent
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1/run_1200000/pair')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
start=time.monotonic();loader=CELookup();old=pd.read_parquet(P/'CANDIDATE_CE.parquet');keys=set(zip(old.account,old.day,old.sid));source={str(p):sha(p) for p in [R/'PVR.json.gz',R/'E31.json.gz',O/'account_rank.py',Path(__file__),P/'CANDIDATE_CE.parquet']};rows=[];queueaudits=[]
for account in ['PVR','E31']:
    a=json.load(gzip.open(R/(account+'.json.gz'),'rt'))
    for decision in a['decisions']:
        day=decision['at'][:10];by={}
        for intent in decision['intents']:by.setdefault(intent['sid'],[]).append(intent)
        frame=[]
        for sid,intents in by.items():
            roles={i['role'] for i in intents};mobile=next((i for i in intents if i['role']=='mobile'),None)
            if (account,day,sid) in keys:
                assert mobile is not None
                rows.append(dict(account=account,day=day,sid=sid,has_actual_CORE_intent='core' in roles,has_actual_MOBILE_intent=True,actual_role_set='|'.join(sorted(roles)),year=int(day[:4])))
            i=intents[0];assert all(q['rank']==i['rank'] for q in intents)
            frame.append(dict(sid=sid,rank=float(i['rank']),was_empty=(account,day,sid) in keys,has_mobile_intent='mobile' in roles,has_core_intent='core' in roles,PVR_score=float(i['PVR_score']) if i.get('PVR_score') is not None else np.nan,PVR_ready=bool(i.get('PVR_ready',False)),priority_rank=i.get('priority_rank'),source_account=account))
        if frame:
            q=pd.DataFrame(frame);out,audit=rank_stock_slots(q,day,loader);audit['account']=account;queueaudits.append(audit)
            # Every original CORE stock rank is exact even when native ranks have gaps.
            core=out[out.has_core_intent];assert core.ce_stock_rank.eq(core['rank']).all()
            assert out.ce_stock_rank.nunique()==len(out)
    print('SCOPE_ACCOUNT',account,flush=True)
roles=pd.DataFrame(rows);assert len(roles)==103766 and not roles.duplicated(['account','day','sid']).any()
joined=old.merge(roles,on=['account','day','sid','year'],validate='one_to_one');joined['account_scope_movable']=~joined.has_actual_CORE_intent & joined.CE_known & np.isfinite(joined.original_PVR)
joined[['account','day','sid','year','core_Q','has_actual_CORE_intent','actual_role_set','CE_known','original_PVR','account_scope_movable']].to_parquet(O/'ORIGINAL_CANDIDATE_ACTUAL_ROLE_SCOPE.parquet',index=False)
summary=joined.groupby(['account','year']).agg(original_legal_MOBILE_candidates=('sid','size'),core_qualification_true=('core_Q','sum'),actual_CORE_MOBILE_stock_groups=('has_actual_CORE_intent','sum'),MOBILE_only_stock_groups=('has_actual_CORE_intent',lambda x:int((~x).sum())),account_scope_movable=('account_scope_movable','sum')).reset_index();summary.to_csv(O/'ACTUAL_CORE_INTERSECTION_BY_YEAR.csv',index=False)
pd.DataFrame(queueaudits).to_csv(O/'ORIGINAL_PENDING_SLOT_INTERFACE_AUDIT.csv',index=False)
# Strict example: rank gaps, actual CORE group, held group and unknown source all stay fixed.
fixture=pd.DataFrame([dict(sid=s,rank=r,was_empty=e,has_mobile_intent=m,has_core_intent=c,PVR_score=p,PVR_ready=True) for s,r,e,m,c,p in [('600056.SH',10,True,True,False,88.),('601607.SH',20,True,True,True,80.),('001232.SZ',40,True,True,False,79.),('600606.SH',90,False,True,False,78.),('600299.SH',99,True,True,False,54.)]])
f,audit=rank_stock_slots(fixture,'2022-03-03',loader);assert f.sid.tolist()==['600299.SH','601607.SH','001232.SZ','600606.SH','600056.SH'];assert f.ce_stock_rank.tolist()==[10,20,40,90,99]
# Restart is a new immutable loader, not account-state recovery.
loader2=CELookup();f2,a2=rank_stock_slots(fixture,'2022-03-03',loader2);pd.testing.assert_frame_equal(f,f2,check_exact=True);assert audit==a2
for p,h in source.items():assert sha(p)==h
for p,h in json.loads((O/'ORIGINAL_TEST_FILES_BEFORE.json').read_text()).items():assert sha(p)==h
out=dict(status='ACCOUNT_SCOPE_INTERFACE_READY',actual_pending_role_extraction=True,core_Q_never_used_as_actual_intent=True,original_candidate_rows=len(joined),actual_CORE_MOBILE_intersection=int(joined.has_actual_CORE_intent.sum()),MOBILE_only_candidates=int((~joined.has_actual_CORE_intent).sum()),movable_with_finite_PVR_CE=int(joined.account_scope_movable.sum()),all_original_pending_queues_tested=len(queueaudits),all_CORE_stock_slots_unchanged=True,all_original_fields_preserved=True,unknown_slots_preserved=True,no_K20=True,restart_exact=True,all_original_test_artifacts_unchanged=True,source_hashes_unchanged=True,seconds=time.monotonic()-start,important='Original pending audit used old legal empty candidate membership solely to verify this historical scope. Runtime account_rank requires actual counterfactual was_empty and pending roles; it does not load original account history.')
dump('ACCOUNT_SCOPE_AUDIT.json',out);dump('ACCOUNT_SCOPE_INPUT_SHA256.json',source);print(json.dumps(out,ensure_ascii=False));print(summary.to_string(index=False))
