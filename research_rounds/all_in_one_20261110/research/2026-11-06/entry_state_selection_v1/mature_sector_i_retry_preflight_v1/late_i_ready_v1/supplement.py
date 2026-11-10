from pathlib import Path
import pandas as pd,json,hashlib,numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');hs={}
def read(p,kind='json'):
 hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text()) if kind=='json' else pd.read_csv(p,low_memory=False) if kind=='csv' else pd.read_parquet(p)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
q=read(O/'FIXED7_AB_D_SHADOW_QUEUES.csv','csv');d=q[q.channel.eq('D')];w=d[d.signal_day<'2023'];f=read(R/'fast_q1_signal_mechanism_v1/MERGED_PERMIT_DIAGNOSIS.csv','csv');z=w[['sid','name','signal_day','D_shadow_selected']].merge(f[['sid','signal_day','status','initial_evidence_usable','initial_net','initial_return','entry_role','entry_day','exit_day']],on=['sid','signal_day'],how='left',validate='one_to_one');z['label_scope']='Old FAST conditional lifecycle only, not D account outcome';z.to_csv(O/'WEAK_D_MATCHED_OLD_FAST_CONTROLS.csv',index=False)
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};ids=[]
for row in d.itertuples():
 m=manifest[row.sid];p=Path(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));raw=read(p,'parquet');day=pd.Timestamp(row.signal_day);at=raw.loc[day];identity=[row.sid,str(at.source_kind),str(at.source_path),str(at.segment_id),str(day.date())];sid=hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();ids.append(dict(sid=row.sid,day=row.signal_day,canonical_identity_components=identity,canonical_D_receipt_sha256=sid,local_receipt_key=row.D_receipt_id,source_factor=float(at.adjustment_factor)))
assert len({x['canonical_D_receipt_sha256'] for x in ids})==len(ids);save('D_CANONICAL_RECEIPT_IDENTITIES.json',ids)
c=read(O/'FIXED56_CASES.csv','csv');cp=[]
for row in c.itertuples():
 x=read(Path(manifest[row.sid]['refs']['CP1']),'parquet');r=x.loc[pd.Timestamp(row.day)] if pd.Timestamp(row.day) in x.index else None;cp.append(dict(sid=row.sid,day=row.day,case_scope=row.case_scope,D_raw=row.D_raw,fresh_CP=None if r is None else bool(r.receipt),CP_candidate=None if r is None or not np.isfinite(r.candidate) else float(r.candidate),warning='CP is observed, never manufactured or replaced by D.'))
pd.DataFrame(cp).to_csv(O/'FIXED56_TRUE_CP_CONTEXT.csv',index=False)
# Signal truth-table only, not a broker/execution simulator.
def gate(sp,s,mp,m,ip,i,pvr=True,same=True):return sp==s==mp==m==1 and ip==0 and i==1 and pvr and same
tests=[('late_ready',dict(sp=1,s=1,mp=1,m=1,ip=0,i=1),True),('continuing_I',dict(sp=1,s=1,mp=1,m=1,ip=1,i=1),False),('previous_I_unknown',dict(sp=1,s=1,mp=1,m=1,ip=-1,i=1),False),('current_I_unknown',dict(sp=1,s=1,mp=1,m=1,ip=0,i=-1),False),('sector_unknown_to_true',dict(sp=-1,s=1,mp=1,m=1,ip=0,i=1),False),('M_unknown_to_true',dict(sp=1,s=1,mp=-1,m=1,ip=0,i=1),False),('B_is_not_D',dict(sp=1,s=1,mp=0,m=1,ip=0,i=1),False),('A_is_not_D',dict(sp=0,s=1,mp=1,m=1,ip=0,i=1),False),('PVR_unknown',dict(sp=1,s=1,mp=1,m=1,ip=0,i=1,pvr=False),False),('changed_segment',dict(sp=1,s=1,mp=1,m=1,ip=0,i=1,same=False),False)]
for name,args,expected in tests:assert gate(**args)==expected
save('SYNTHETIC_UNKNOWN_BOUNDARIES.json',[dict(name=name,args=args,expected=expected,passed=True) for name,args,expected in tests])
# Check pre/post snapshot-only repair did not change economic diagnostic numbers.
old=read(O/'BEFORE_PREFIX_SNAPSHOT_FIX/FIXED7_SUMMARY.csv','csv');now=read(O/'FIXED7_SUMMARY.csv','csv');pd.testing.assert_frame_equal(old,now,check_exact=True)
qa=dict(new_D_raw=len(d),weak17_all_in_saved_FAST_event_Q=bool(w.original_event_Q.eq(True).all()),weak_old_FAST_matches=int(z.status.notna().sum()),weak_matched_net_positive=int((z.initial_net>0).sum()),weak_matched_net_negative=int((z.initial_net<0).sum()),weak_D_selected=int(w.D_shadow_selected.sum()),weak_D_selected_old_FAST_matches=int(z[z.D_shadow_selected].status.notna().sum()),weak_D_selected_matched_losses=int((z[z.D_shadow_selected].initial_net<0).sum()),canonical_receipts_unique=True,truth_table_checks=len(tests),pre_post_fix_summary_exact=True,all_sources_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hs.items()),account_runs=0)
save('SUPPLEMENT_QA.json',qa);save('SUPPLEMENT_SOURCE_HASHES.json',hs);print(json.dumps(qa,ensure_ascii=False,indent=2))
