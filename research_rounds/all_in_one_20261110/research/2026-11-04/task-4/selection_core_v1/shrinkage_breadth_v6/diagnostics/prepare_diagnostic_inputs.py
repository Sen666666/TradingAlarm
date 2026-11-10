"""v6 source/interface preparation only. No shrink scores, ranks or labels."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;SEL=O.parents[1];SOURCES={}
def bind(p):
 p=Path(p).resolve();SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 O.mkdir(parents=True,exist_ok=True);bind(__file__)
 src=bind(SEL/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet')
 cols=['date','sector_id_static','industry_static','Nstatic','N_U_t','N_above20_t','N_above20_tminus5','B_now','B_lag5_pairedU','dB5_paired','B_lag5_ownU','dB5_ownU','N_U_previous5','N_U_intersection_previous5','U_joiners1','U_leavers1','U_joiners5','U_leavers5','membership_PIT_verified']
 f=pd.read_parquet(src,columns=cols);assert len(f)==97650 and not f.duplicated(['date','sector_id_static']).any()
 assert f.groupby('date').size().eq(90).all()and f.date.nunique()==1085
 assert f[['N_U_t','N_above20_t','N_above20_tminus5']].notna().all().all()
 assert (f.N_above20_t<=f.N_U_t).all()and(f.N_above20_tminus5<=f.N_U_t).all()
 f.to_parquet(O/'ORIGINAL_INPUT_COUNTS.parquet',index=False)
 warm_src=bind(SEL/'separated_momentum_v4/ranking/WARMUP_BREADTH_2021.parquet');warm=pd.read_parquet(warm_src)
 warm_cols=['date','sector_id_static','industry_static','N_U_t','N_above20_t','N_above20_tminus5','B_now','B_lag5_pairedU','dB5_paired'];assert warm.groupby('date').size().eq(90).all()
 warm[warm_cols].to_parquet(O/'ORIGINAL_WARM_INPUT_COUNTS_2021.parquet',index=False)
 case_src=bind(SEL/'causal_launch_v5/burst_raw/RAW_PATHS_COMPLETE.parquet');case=pd.read_parquet(case_src,columns=['case_id','case_role','event_anchor','relative_session','date','sector_id_static','industry_static'])
 assert len(case)==168 and not case.duplicated(['case_id','date']).any();case.to_csv(O/'FROZEN_V5_CASE_MAPPING_168.csv',index=False)
 dump('PREPARATION_SOURCE_SHA256.json',SOURCES)
 dump('SOURCE_READINESS.json',dict(status='SOURCE_READY_WAITING_V6_FROZEN_CONTRACT',study_rows=len(f),study_sessions=int(f.date.nunique()),sectors_per_session=90,first_date=str(f.date.min()),last_date=str(f.date.max()),paired_industry_u0_and_u1_count_known=True,zero_n_rows=int(f.N_U_t.eq(0).sum()),original_B_known_rows=int(f.B_now.notna().sum()),warm_rows=len(warm),warm_first=str(warm.date.min()),warm_last=str(warm.date.max()),case_rows=len(case),main=int(case.case_role.eq('MAIN').sum()),aux=int(case.case_role.eq('AUXILIARY').sum()),counter=int(case.case_role.eq('COUNTER').sum()),kappa_user_fixed=10,new_shrink_scores=0,new_ranks=0,new_labels=0,new_accounts=0,known_limit='static selected1709/current industry bridge; not PIT historical all-A or full industry'))
 (O/'FORMULA_INTERFACE.txt').write_text('''v6 thin diagnostic interface — preparation only, waiting root freeze
User-fixed kappa=10; no tuning, no new ranking or labels executed.

Inputs at T:
n = original N_U_t
u1 = original N_above20_t
u0 = original N_above20_tminus5 (the same T industry U members observed at T-5)
Original B1=u1/n; original paired B0=u0/n; original paired delta=(u1-u0)/n.
Bm1 = sum industry N_above20_t / sum industry N_U_t at T.
Bm0 = the same aggregate at the preceding fifth CSI session, using that dates own observed U, not todays U backfilled across the market.
Use saved2021 warm counts for the first2022 five-session market lag; do not make initial2022 lag unknown solely because the report starts then.

Frozen candidate algebra to be executed only after root contract:
B1prime=(u1+10*Bm1)/(n+10)
B0prime=(u0+10*Bm0)/(n+10)
DeltaBprime=(u1-u0)/(n+10)+10*(Bm1-Bm0)/(n+10).
Self term = (u1-u0)/(n+10) = n/(n+10)*original paired delta.
Market term = 10*(Bm1-Bm0)/(n+10).
The market coefficient grows when n is smaller. For equal n the market term is the same daily shift; across n it can change cross-sectional order. It cannot be called industry-specific diffusion.

Planned output fields (root freeze governs actual names/ties):
date,sector_id_static,industry_static,n,u1,u0,original_B1,original_pair_B0,original_delta,Bm1,Bm0,market_delta,shrunk_B1,shrunk_pair_B0,shrunk_delta,self_term,market_term,self_weight,market_weight,original_delta_rank,shrunk_delta_rank,rank_change,known flags.
Raw original own-U lag/change and U join/leave counts remain separate diagnostics. Never substitute own-U industry change for paired same-T-industry change.
Rank ties/cutoff/display order await root freeze. No stock/industry order is computed here.
The fixed v5 cases remain168 rows; known risk windows are exploratory counterexamples, not a fresh blind holdout. No case is selected because a shrink result looks favorable.
''')
 outputs={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(O.iterdir())if p.is_file()and p.name!='PREPARATION_OUTPUT_SHA256.json'};dump('PREPARATION_OUTPUT_SHA256.json',outputs)
 print(json.dumps(json.loads((O/'SOURCE_READINESS.json').read_text()),ensure_ascii=False))
if __name__=='__main__':main()
