from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared');hs={}
def read(p):hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
old=pd.read_csv(O/'OLD8_EXACT_DECISION_STATE.csv');q=pd.read_csv(O/'FIXED7_SHADOW_REQUEST_QUEUES.csv');t=pd.read_csv(O/'OLD8_POINT_TIME_TRACE.csv');weak=pd.read_csv(O/'WEAK_ORIGINAL_EXIT_RETRY_TRACE.csv')
acc=read(M/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json');fills=[]
for x in old.itertuples():
 xs=[v for v in acc['fills'] if v['security_id']==x.sid and v['side']=='buy' and v['at'][:10]==x.old_entry_at[:10]]
 assert xs;fills+=xs
save('OLD8_ORIGINAL_BUY_FILLS.json',fills)
a=read(R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924/AUDIT.json');save('SEP30_ORIGINAL_ALLOCATION_EVENTS.json',[x for x in a if x['day'].startswith('2024-09-30') and x['type'] in ['PROMOTED','ALL_RESERVATIONS_COMPLETE']]);j=read(R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924/EXACT_TRADE_JOURNAL.json');save('SEP30_ORIGINAL_ACTUAL_BUYS.json',[x for x in j if x['day'].startswith('2024-09-30') and x['side'].startswith('buy')])
fixed=read(R/'probe_principal_giveback_ledger_preflight_v1/FIXED_DAY_ACCOUNT_RISK.json');save('ALREADY_AUDITED_RISK_CONTEXT.json',fixed)
# Include primary input rank, not a recomputed alternative rank universe.
npz=P/'h1.npz';hs[str(npz)]=hashlib.sha256(npz.read_bytes()).hexdigest();z=np.load(npz);dates=pd.DatetimeIndex(z['dates']);cols={str(s):i for i,s in enumerate(z['symbols'])};rk=[]
for x in old.itertuples():
 row=dates.get_loc(pd.Timestamp(x.day));rk.append(dict(sid=x.sid,day=x.day,stock_H1_saved_score=float(z['score'][row,cols[x.sid]]),sector_H1_saved_score=float(z['score'][row,cols[x.sector]])))
pd.DataFrame(rk).to_csv(O/'OLD8_SAVED_H1_SCORES.csv',index=False)
# Exact source-event membership test for every old8 trace and original fixed42 point.
E=R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv';hs[str(E)]=hashlib.sha256(E.read_bytes()).hexdigest();e=pd.read_csv(E,low_memory=False);keys={(v.sid,str(v.day)[:10]):('A' if v.event_type=='A_SECTOR_BIRTH' else 'B') for v in e.itertuples() if v.event_type in ['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']};checks=[]
for src,df in [('old8trace',t),('fixed42',pd.read_csv(O/'FIXED42_UNCHANGED_CONTROLS.csv'))]:
 for v in df.itertuples():
  got='' if pd.isna(v.AB_type) else v.AB_type;expected=keys.get((v.sid,v.day),'');assert got==expected,(src,v.sid,v.day,got,expected);checks.append(dict(source=src,sid=v.sid,day=v.day,AB_exact=True))
pd.DataFrame(checks).to_csv(O/'AB_CLOCK_RECONSTRUCTION_PARITY.csv',index=False)
# Reentry controls are mechanical permission, no counterfactual outcome.
w=weak[(weak.C_raw==True)&(weak.current_state=='FLAT')];w.to_csv(O/'WEAK_ACTUAL_EXIT_NEW_C_REQUESTS.csv',index=False)
sel=q[(q.channel=='C')&(q.shadow_top2==True)];s=sel.groupby('signal_day').agg(requests=('sid','size'),planned_buy_fee=('close_fee','sum'),planned_fee_risk=('close_plan_risk','sum'),median_fee_risk=('close_plan_risk','median'));s.to_csv(O/'SHADOW_REQUEST_FEE_RISK.csv')
save('SUPPLEMENT_QA.json',dict(old8_original_buy_fills=len(fills),AB_clock_exact_checks=len(checks),weak_postexit_new_C_requests=len(w),weak_postexit_names=w.sid.nunique(),actual_new_account_runs=0,all_new_cash_PnL_uncomputed=True,source_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hs.items())));save('SUPPLEMENT_SOURCE_HASHES.json',hs)
print('AB parity',len(checks));print(pd.DataFrame(rk).to_string(index=False));print(s.to_string());print('Sep30 buys',[(x['sid'] if 'sid'in x else x['round_id'],x['q']) for x in j if x['day'].startswith('2024-09-30') and x['side'].startswith('buy')])
