import pathlib,json,hashlib,warnings,pandas as pd,numpy as np
warnings.filterwarnings('ignore',category=FutureWarning)
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'m3_strict_s_fixed_case_map_v1';O.mkdir(exist_ok=True)
H={r['sid']:r for r in json.load(open(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'))}
master=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv')
M=pd.read_csv(master,dtype=str).drop_duplicates('symbol').set_index('symbol')
C=pd.read_csv(R/'major_trends_2025_2026_review_v1/industry_specific_cycles/SIX_INDEPENDENT_CYCLES.csv').query("sid.str.startswith('URFI')",engine='python')
draw={'URFI881121':'2025-04-07','URFI881270':'2025-04-08','URFI881172':'2025-04-07','URFI881129':'2025-04-08','URFI881169':'2025-05-15'}
rows=[];selection=[];hashes={str(master):hashlib.sha256(master.read_bytes()).hexdigest()}
def load(st):
 r=H[st];p=next(p for p in r['source_identity'] if p.endswith('/signal.parquet'))
 sha=hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();assert sha==r['source_identity'][p];hashes[p]=sha
 return pd.read_parquet(p)
for c in C.to_dict('records'):
 sec=c['sid'];sector=load(sec);ds=sector.loc[:'2024-05-31'].index[-63:];assert str(ds[-1].date())=='2024-05-31'
 pool=sorted(s for s in M[M.industry_index_symbol==sec].index if s in H)
 allowed=[]
 for st in pool:
  q=load(st).reindex(ds);valid=q.observed_bar.fillna(False)&q.price_eligible.fillna(False)&~q.source_invalid.fillna(True)&~q.synthetic_event_bar.fillna(True)&q.close.gt(0)
  ok=bool(valid.all())
  selection.append({'sector':sec,'symbol':st,'name':M.loc[st,'name'],'known63_before_research':ok,'known_days':int(valid.sum()),'required_days':63})
  if ok:allowed.append(st)
 a=allowed[0];b=allowed[(len(allowed)-1)//2]
 picks=[(a,'a_first_code','2024-09-26','924后启动初期，检验三日状态与原生新票，不预设应买'),
 (b,'b_lower_median_code',c['first_close_reclaim_date'],'既有地图重返前高切片，检验是否仍有原生新票，不补票'),
 (a,'a_first_code',draw[sec],'既有地图春季深回撤末端切片，检验假/失效状态；低点为后视标签'),
 (b,'b_lower_median_code','2026-07-22' if sec=='URFI881169' else '2026-03-26','既有地图主要回撤后恢复切片，检验正常重入；当日不知道后来结局')]
 for st,role,day,reason in picks:
  assert pd.Timestamp(day) in sector.index
  rows.append({'case_id':'CASE'+str(len(rows)+1).zfill(2),'sector':sec,'industry':c['name'],'symbol':st,'name':M.loc[st,'name'],'signal_close_date':day,'selection_role':role,'eligible_pre63_n':len(allowed),'code_rank':1 if role.startswith('a') else (len(allowed)-1)//2+1,'reason':reason,'anchor_source':'frozen independent sector cycle map','retrospective_case_timing':True,'allowed_feature_clock':'<=signal CLOSE; next observed OPEN execution only','future_returns_used_for_stock_selection':False,'membership':'2026-10-22 fixed current roster intersect1709 NON-PIT','B0_B1_result_used_for_selection':False,'new_account_status':'NOT_RUN','new_fund_funnel_status':'UNAVAILABLE until new shared account'})
D=pd.DataFrame(rows);S=pd.DataFrame(selection);assert len(D)==20 and D.symbol.nunique()==10
D.to_csv(O/'FIXED_20_CASES.csv',index=False);S.to_csv(O/'PRE_RESEARCH_SELECTION_246.csv',index=False)
json.dump(hashes,open(O/'SOURCE_HASHES.json','w'),ensure_ascii=False,indent=2)
protocol={'research_start':'2024-06-01','research_end':'2026-10-22','frozen_before_reading_B1':True,'n_cases':20,'n_stocks':10,'selection':'first and lower-median code among fixed research sector members with all 63 common industry sessions observed/valid through2024-05-31; no future performance selection','coverage':'five sectors only; illustrative mechanism cases, not random/population performance sample','case_dates':'existing hindsight map anchors; not entry permit or features','B0':'as defined by owner: original M3 A/B common-known birth, I/PVR and industry top2','B1':'only add same-birth-ticket independent original E0-NR1 both-way-confirmation scale1.5 up-active; never wait/reissue; owner implementing','known_gaps':['current frozen M3 matrices end2026-06-30; gold2026-07-22 deliberately outside','no new B0/B1 shared account or cash funnel yet','current membership and adjusted prices NON-PIT'],'old_account_diagnostic_only':'2024 autumn cohort can be traced separately, never substitute as new B0/B1 execution'}
json.dump(protocol,open(O/'PROTOCOL.json','w'),ensure_ascii=False,indent=2)
print(D[['case_id','industry','symbol','name','signal_close_date','selection_role']].to_string(index=False))
