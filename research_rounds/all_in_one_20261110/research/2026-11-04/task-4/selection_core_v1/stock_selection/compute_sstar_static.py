"""One frozen three-date Sstar static diagnostic; zero accounts/models/returns."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;sha={};started=time.monotonic()
DATES=['2024-09-24','2026-01-15','2022-01-24']
def bind(p):
 p=Path(p);sha[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def save(name,x):
 x=x.drop(columns=['_fraction'],errors='ignore');x.to_parquet(O/(name+'.parquet'),index=False);x.to_csv(O/(name+'.csv'),index=False)
def sorted_global(x,tie_h=False):
 x=x.copy();x['_fraction']=[Fraction(int(a),int(b)) for a,b in zip(x.Sstar_numerator,x.Sstar_denominator)]
 cols=['_fraction']+(['p_rs5'] if tie_h else [])+['sid'];asc=[False]+([False] if tie_h else [])+[True]
 return x.sort_values(cols,ascending=asc,na_position='last')
bind(P/'FROZEN_STATIC_DIAGNOSTIC.txt')
old=pd.read_parquet(bind(P/'original_candidates/ALL_STATIC_STOCKS_FACTS_H1_PVR.parquet'))
old=old[old.date.isin(DATES)].copy();assert len(old)==5127 and not old.duplicated(['sid','date']).any()
u=pd.read_parquet(bind(P/'industry_selection/U_T_STOCK_ELIGIBILITY.parquet'))
h=pd.read_parquet(bind(P/'industry_selection/HSTAR_STATIC_PANEL.parquet'))
e=pd.read_parquet(bind(O/'E0_THREE_DATE_EVIDENCE.parquet'))
assert len(u)==len(e)==5127 and not u.duplicated(['sid','date']).any()
assert not h.duplicated(['date','sector_id_static']).any()
d=old.merge(u,on=['sid','date'],validate='one_to_one',suffixes=('','_U')).merge(e,on=['sid','date'],validate='one_to_one')
assert d.sector_static.fillna('UNKNOWN').equals(d.sector_id_static.fillna('UNKNOWN'))
assert len(d)==5127
cp_known=d.original_CP1_id.notna()&d.original_CP1_id.astype(str).str.len().gt(0)
d['original_signal_legal_frozen']=d.original_core_Q.eq(True)|(cp_known&d.original_mobile_Q.eq(True))
assert d.original_signal_legal_frozen.equals(d.source_Q_core_or_CP_mobile)
components=[('PVR_cache_score','PVR',4),('RS_stock20','RS_stock20',3),('drawdown20_prior_high','drawdown20',2),('amount_change','amount_change',1)]
known=np.ones(len(d),dtype=bool)
for col,_,_ in components:known&=np.isfinite(pd.to_numeric(d[col],errors='coerce').to_numpy(dtype=float))
known&=d.PVR_known.eq(True).to_numpy(dtype=bool)
d['Sstar_all_four_known']=known
d['Sstar_rankable']=d.qualified_U_t.eq(True)&d.original_signal_legal_frozen&d.Sstar_all_four_known&d.sector_id_static.notna()
d['Sstar_static']=np.nan;d['Sstar_numerator']=np.nan;d['Sstar_denominator']=np.nan;d['percentile_N']=np.nan
for _,tag,_ in components:
 for prefix in ['p_','n_less_','n_equal_','midrank_numerator_']:d[prefix+tag]=np.nan
for (date,sector),g in d[d.Sstar_rankable].groupby(['date','sector_id_static'],sort=True):
 n=len(g);d.loc[g.index,'percentile_N']=n;numerator=np.zeros(n,dtype=np.int64)
 for col,tag,w in components:
  lower=(g[col].rank(method='min')-1).to_numpy(dtype=np.int64)
  equal=(g[col].rank(method='max')-g[col].rank(method='min')+1).to_numpy(dtype=np.int64)
  mid=2*lower+equal
  d.loc[g.index,'n_less_'+tag]=lower;d.loc[g.index,'n_equal_'+tag]=equal;d.loc[g.index,'midrank_numerator_'+tag]=mid;d.loc[g.index,'p_'+tag]=mid/(2*n)
  numerator+=w*mid
 d.loc[g.index,'Sstar_numerator']=numerator;d.loc[g.index,'Sstar_denominator']=20*n;d.loc[g.index,'Sstar_static']=numerator/(20*n)
d['Sstar_exact_fraction']=[str(Fraction(int(a),int(b))) if np.isfinite(a) else None for a,b in zip(d.Sstar_numerator,d.Sstar_denominator)]
d['Sstar_formal_PIT']=np.nan;d['formal_unknown_reason']='historical_pool_and_industry_membership_PIT_not_verified'
d['selection_scope']='2026-10-22_static1709__source_Q_signal_legal__not_order_or_fill_legality'
d['watch_only']=d.one_price_up_T.eq(True)
d['execution_status']='UNKNOWN_NO_LIMIT_SUSPENSION_ORDERBOOK_OR_QUEUE_PROOF'
miss=[]
for r in d.to_dict('records'):
 why=[]
 if not r['original_signal_legal_frozen']:why.append('original_signal_Q_not_legal_or_unknown')
 if not r['qualified_U_t']:why.append('outside_U_t:'+str(r['eligibility_reasons']))
 if not r['PVR_known'] or not np.isfinite(r['PVR_cache_score']):why.append('true_PVR_unknown')
 for c,_,_ in components[1:]:
  if not np.isfinite(r[c]):why.append(c+':unknown')
 if pd.isna(r['sector_id_static']):why.append('static_industry_unknown')
 miss.append(';'.join(why))
d['Sstar_missing_or_exclusion_reasons']=miss
d['Sstar_within_industry_order1']=np.nan;d['Sstar_within_industry_tied_rank1']=np.nan;d['Sstar_global_numeric_inventory_order1']=np.nan
for _,g in d[d.Sstar_rankable].groupby(['date','sector_id_static']):
 z=g.sort_values(['Sstar_numerator','sid'],ascending=[False,True]);d.loc[z.index,'Sstar_within_industry_order1']=np.arange(1,len(z)+1)
 d.loc[g.index,'Sstar_within_industry_tied_rank1']=g.Sstar_numerator.rank(method='min',ascending=False)
tops=[]
for date,g in d[d.Sstar_rankable].groupby('date'):
 z=sorted_global(g);d.loc[z.index,'Sstar_global_numeric_inventory_order1']=np.arange(1,len(z)+1)
 z=z.head(20).copy();z['view']='Sstar_numerical_global_TOP20_NOT_crossindustry_budget_or_execution_priority';tops.append(z)
hd=h[['date','sector_id_static','Hstar_static','rank_Hstar_static','p_rs5']].copy()
d=d.merge(hd,on=['date','sector_id_static'],how='left',validate='many_to_one')
d['MAIN_native_E0_I_valid']=d.fact_e0_target.eq(1)&d.fact_i_target.eq(1)
d['START_original_E0_evidence']=d.START_saved_original_evidence.eq(True)
d['MAIN_industry_top5']=False;d['MAIN_selected']=False;d['MAIN_round']=np.nan;d['MAIN_round_robin_order1']=np.nan
d['START_selected']=False;d['START_order1']=np.nan
mainboards=[];startboards=[]
for date in DATES:
 hg=h[(h.date==date)&h.Hstar_static.notna()].sort_values(['Hstar_static','sector_id_static'],ascending=[False,True]).head(5)
 sectors=hg.sector_id_static.tolist();d.loc[(d.date==date)&d.sector_id_static.isin(sectors),'MAIN_industry_top5']=True
 picks=[]
 for roundnum in [1,2]:
  for sec in sectors:
   g=d[(d.date==date)&(d.sector_id_static==sec)&d.Sstar_rankable&d.MAIN_native_E0_I_valid].sort_values(['Sstar_numerator','sid'],ascending=[False,True])
   if len(g)>=roundnum:
    idx=g.index[roundnum-1];d.loc[idx,['MAIN_selected','MAIN_round','MAIN_round_robin_order1']]=[True,roundnum,len(picks)+1];picks.append(idx)
 if picks:mainboards.append(d.loc[picks].copy())
 sg=d[(d.date==date)&d.Sstar_rankable&d.START_original_E0_evidence]
 # Frozen START tie-break uses industry RS5 percentile, then SID. No Hstar top5 condition.
 sz=sorted_global(sg,tie_h=True).head(10)
 for order,idx in enumerate(sz.index,1):d.loc[idx,['START_selected','START_order1']]=[True,order]
 if len(sz):startboards.append(d.loc[sz.index].copy())
d['MAIN_exclusion_reason']=np.where(~d.Sstar_rankable,'not_Sstar_rankable',np.where(~d.MAIN_native_E0_I_valid,'native_E0_or_I_not_valid',np.where(~d.MAIN_industry_top5,'industry_not_frozen_Hstar_top5',np.where(~d.MAIN_selected,'outside_industry_first_two',''))))
d['START_exclusion_reason']=np.where(~d.Sstar_rankable,'not_Sstar_rankable',np.where(~d.START_original_E0_evidence,'no_verified_original_E0_start_evidence_T',np.where(~d.START_selected,'outside_START_top10','')))
assert len(d)==5127 and d.Sstar_static.notna().equals(d.Sstar_rankable)
assert ((d.loc[d.percentile_N==1,[f'p_{tag}' for _,tag,_ in components]]==.5).all().all())
# Final boards are reselected from final table so all descriptive flags are current.
save('ALL5127_STATIC_DIAGNOSTIC_WITH_REASONS',d.sort_values(['date','sid']))
save('ALL_ORIGINAL_SIGNAL_LEGAL_WITH_SSTAR',d[d.original_signal_legal_frozen].sort_values(['date','sector_id_static','Sstar_within_industry_order1','sid'],na_position='last'))
save('ALL_SSTAR_RANKABLE_WITHIN_INDUSTRY',d[d.Sstar_rankable].sort_values(['date','sector_id_static','Sstar_within_industry_order1']))
save('THREE_DATE_NUMERICAL_TOP20_NOT_ALLOCATION',d[d.Sstar_global_numeric_inventory_order1.le(20)].sort_values(['date','Sstar_global_numeric_inventory_order1']))
save('MAIN_INDUSTRY_TOP5_ROUND_ROBIN',d[d.MAIN_selected].sort_values(['date','MAIN_round_robin_order1']))
save('START_TOP10_ORIGINAL_E0_EVIDENCE',d[d.START_selected].sort_values(['date','START_order1']))
focus=pd.read_csv(bind(P/'original_candidates/EARLY_THREE_FOCAL_JOINED.csv'),usecols=['sid','date'],dtype={'sid':str})
focal=focus.merge(d,on=['sid','date'],validate='one_to_one');save('FOCAL_ORIGINAL_AND_SSTAR',focal.sort_values(['date','sid']))
for legal,name in [(True,'OLD_SOURCE_Q_H1_TOP20_COMPARISON'),(False,'OLD_ALL_STATIC_H1_TOP20_COMPARISON')]:
 selected=[]
 for date,g in d.groupby('date'):
  if legal:g=g[g.original_signal_legal_frozen]
  selected.extend(g.sort_values(['original_H1_rank0','sid']).head(20).index.tolist())
 save(name,d.loc[selected].sort_values(['date','original_H1_rank0']))
selected=d[d.MAIN_selected|d.START_selected].copy();selected['both_channels']=selected.MAIN_selected&selected.START_selected;save('UNIQUE_MAIN_OR_START_DISCOVERY_ONLY',selected.sort_values(['date','sid']))
counts=d.groupby('date').agg(static_pool=('sid','size'),U_t=('qualified_U_t','sum'),source_signal_legal=('original_signal_legal_frozen','sum'),Sstar_known=('Sstar_rankable','sum'),
 MAIN=('MAIN_selected','sum'),START=('START_selected','sum'),watch_only_T=('watch_only','sum'))
counts['source_legal_and_U_t']=d[d.original_signal_legal_frozen].groupby('date').qualified_U_t.sum()
counts['source_legal_U_four_known_missing']=counts.source_legal_and_U_t-counts.Sstar_known
counts['MAIN_START_unique']=selected.groupby('date').size();counts['MAIN_START_both']=selected.groupby('date').both_channels.sum();counts.to_csv(O/'COUNTS_BY_DATE.csv')
summary={'scope':DATES,'rows':len(d),'source_signal_legal':int(d.original_signal_legal_frozen.sum()),'Sstar_rankable':int(d.Sstar_rankable.sum()),
 'formula':'(4 midnum_PVR+3 midnum_RS20+2 midnum_D20+midnum_A21)/(20N)','same_N_all_four_components':True,
 'single_candidate_percentile_all_half':True,'formal_PIT_known':0,'score_or_weight_variants_computed':1,'account_runs':0,'new_CP_or_price_models':0,
 'new_returns_or_labels_computed':0,'seconds':time.monotonic()-started}
(O/'SSTAR_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');bind(__file__);(O/'STATIC_DIAGNOSTIC_INPUT_SHA256.json').write_text(json.dumps(sha,indent=2)+'\n')
print(counts.to_string(),flush=True);print(json.dumps(summary,ensure_ascii=False),flush=True)
