"""Repair A/B labels only; native Q, epochs, CP identities and sizing are unchanged."""
from pathlib import Path
import pandas as pd,json,hashlib,shutil
O=Path(__file__).resolve().parent;E=O.parent/'m3_stock_birth_during_sector_v1';archive=O/'input_failure_unfiltered_AB';archive.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
names=['prepare_inputs.py','prepare_inputs.log','ALL_MARKET_INPUTS_2022.parquet','ENTRY_CANDIDATES_2022.parquet','STARTUP_MARKET_INPUTS.parquet','CASE_PREFLIGHT.csv','INPUT_SOURCE_HASHES.json','INPUT_OUTPUT_HASHES.json','INPUT_PREFLIGHT_SUMMARY.json']
for n in names:shutil.copy2(O/n,archive/n)
s=(O/'prepare_inputs.py').read_text();needle="ab=pd.read_csv(source(E/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False);assert not ab.duplicated(['sid','day']).any()";assert s.count(needle)==1
s=s.replace(needle,"ab=pd.read_csv(source(E/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False);ab=ab[ab.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy();assert not ab.duplicated(['sid','day']).any()")
(O/'prepare_inputs.py').write_text(s)
a=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'],low_memory=False);a=a[a.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy();assert not a.duplicated(['sid','day']).any()
a=a[['sid','day','event_id','event_type','I_qualified','PVR_known']].rename(columns={'event_id':'AB_event_id','event_type':'AB_event_type','I_qualified':'AB_I_qualified','PVR_known':'AB_PVR_known'})
cols=['AB_event_id','AB_event_type','AB_I_qualified','AB_PVR_known'];stats={}
def repair(df):
 x=df.copy();x['day']=pd.to_datetime(x.day);keep=x.drop(columns=cols);y=keep.merge(a,on=['sid','day'],how='left',validate='many_to_one',sort=False)
 for c in ['AB_I_qualified','AB_PVR_known']:y[c]=y[c].astype('boolean')
 assert len(y)==len(x);pd.testing.assert_frame_equal(keep.reset_index(drop=True),y[keep.columns].reset_index(drop=True),check_exact=True)
 assert y.loc[y.AB_event_id.notna(),'AB_event_type'].isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']).all()
 return y
for n in ['ALL_MARKET_INPUTS_2022.parquet','STARTUP_MARKET_INPUTS.parquet']:
 old=pd.read_parquet(O/n);new=repair(old);stats[n]={'rows':len(new),'old_AB_labels':int(old.AB_event_id.notna().sum()),'new_AB_labels':int(new.AB_event_id.notna().sum()),'non_AB_columns_exact':True};new.to_parquet(O/n,index=False)
 if n.startswith('ALL_'):all22=new
cand=all22[all22.event_Q.fillna(False)|all22.cp_fresh.fillna(False)|all22.AB_event_id.notna()].copy();oldcand=pd.read_parquet(O/'ENTRY_CANDIDATES_2022.parquet');cand.to_parquet(O/'ENTRY_CANDIDATES_2022.parquet',index=False)
case=repair(pd.read_csv(O/'CASE_PREFLIGHT.csv'))
# Explicitly distinguish a theoretical size PASS from a current market-role trigger.
case['role_market_eligible']=[bool((pd.notna(r.AB_event_id) and r.AB_I_qualified==True) or (r.event_Q==True and r.epoch_lineage_known==True)) if r.role=='I' else bool(r.cp_fresh==True and r.continuing_Q==True and r.cp_trace_known==True and pd.notna(r.cp_id)) for r in case.itertuples()]
case.to_csv(O/'CASE_PREFLIGHT.csv',index=False)
summary=json.loads((O/'INPUT_PREFLIGHT_SUMMARY.json').read_text());summary.update(candidate_rows=len(cand),epoch_lineage_unknown_candidates=int((~cand.epoch_lineage_known).sum()),AB_whitelist_repaired=True,original_invalid_candidate_rows=len(oldcand),AB_only_event_types=['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']);save(O/'INPUT_PREFLIGHT_SUMMARY.json',summary)
correction=dict(passed=True,reason='OTHER_UNKNOWN_OR_LEFT was incorrectly labelled as an A/B invitation. Exact A/B whitelist applied before mapping. Independent native Q/CP eligibility is retained.',scope='Labels and candidate selection only; no recomputation of Q, epoch, CP, prices, quantity or economics.',tables=stats,old_candidates=len(oldcand),new_candidates=len(cand),archive=str(archive),no_account_or_lifecycle=True)
save(O/'INPUT_AB_CORRECTION.json',correction)
h=json.loads((O/'INPUT_SOURCE_HASHES.json').read_text());h[str(O/'prepare_inputs.py')]=sha(O/'prepare_inputs.py');h[str(Path(__file__))]=sha(Path(__file__));h[str(archive/'prepare_inputs.py')]=sha(archive/'prepare_inputs.py');save(O/'INPUT_SOURCE_HASHES.json',h)
seal=json.loads((O/'INPUT_OUTPUT_HASHES.json').read_text());seal['INPUT_AB_CORRECTION.json']=sha(O/'INPUT_AB_CORRECTION.json')
for n in seal:seal[n]=sha(O/n)
save(O/'INPUT_OUTPUT_HASHES.json',seal);print(json.dumps(correction,ensure_ascii=False,indent=2))
