"""Parent-fixed continuous rank study; prepare first, execute after root freeze.

No portfolio, allocation, old hard gates, new price features or forward labels.
"""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent;WORK=ROOT.parents[1]
PANEL=WORK/'selection_core_v1/industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
PRIOR_H1_SOURCES=WORK/'selection_core_v1/original_candidates/SOURCE_SHA256.json'
RAW=['rs_ind20','rs_ind5','B_now','dB5_paired']
PERCENTILES=['p_r20','p_r5','p_breadth','p_delta_b5']
READ_COLUMNS=['date','sector_id_static','industry_static',*RAW,'Nstatic','N_U_t','N25valid','Nobserved','membership_PIT_verified']
SNAPSHOTS=['2024-09-24','2026-01-15','2022-01-24'];SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p).resolve();h=sha(p)
 if expected is not None:assert h==expected,(str(p),'source SHA changed')
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if isinstance(v,Fraction):return str(v)
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not np.isfinite(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def inputs():
 bind(__file__);f=pd.read_parquet(bind(PANEL),columns=READ_COLUMNS)
 assert len(f)==97650 and not f.duplicated(['date','sector_id_static']).any()
 assert f.groupby('date').size().eq(90).all()
 expected=read(PRIOR_H1_SOURCES)[str(H1)];bind(H1,expected)
 with np.load(H1)as z:
  dates=pd.DatetimeIndex(z['dates']);symbols=z['symbols'].astype(str);scores=z['score'].copy()
 assert dates.is_unique and len(symbols)==len(set(symbols))
 assert scores.shape==(len(dates),len(symbols))
 date_map={str(d.date()):i for i,d in enumerate(dates)};sector_map={s:i for i,s in enumerate(symbols)}
 days=sorted(f.date.unique());sectors=sorted(f.sector_id_static.unique())
 missing_days=[d for d in days if d not in date_map];missing_sectors=[s for s in sectors if s not in sector_map]
 assert not missing_days and not missing_sectors,(missing_days,missing_sectors)
 known=np.isfinite(scores[np.ix_([date_map[d]for d in days],[sector_map[s]for s in sectors])]).sum(axis=1)
 readiness=dict(status='PREPARED_NOT_EXECUTED',panel_rows=len(f),sessions=len(days),industry_count=len(sectors),
  raw_missing={c:int(f[c].isna().sum())for c in RAW},H1_path=str(H1),H1_SHA256=SOURCES[str(H1.resolve())],H1_shape=list(scores.shape),
  H1_missing_dates=missing_days,H1_missing_sectors=missing_sectors,H1_finite90_same_day_min=int(known.min()),H1_finite90_same_day_max=int(known.max()),
  all_dates_exact_no_asof=True,new_scores_or_rankings_computed=0,new_accounts=0,new_forward_labels=0,
  D_status='Not defined; not computed or included in these scores.')
 return f,scores,date_map,sector_map,readiness

def prepare():
 _,_,_,_,status=inputs();save('SOURCE_READINESS.json',status);save('PREPARED_SOURCE_SHA256.json',SOURCES)
 schema=dict(status='DRAFT_PENDING_ROOT_FROZEN_DESIGN',keys=['date','sector_id_static'],input_raw=RAW,input_read_columns=READ_COLUMNS,
  percentile_fields=dict(zip(RAW,PERCENTILES)),scores={'A_score':'.4*p_r20+.2*p_r5+.2*p_breadth+.2*p_delta_b5','START_score':'.5*p_r5+.5*p_delta_b5'},
  selection={'CONT_selected':'Exact first5 complete A scores, descending exact score then sector_id_static','START_selected':'Exact first3 complete START scores, descending exact score then sector_id_static','UNION_selected':'De-duplicated OR; no extra R20/B/pRS5 gates'},
  H1_baseline='Exact source same-day cache, descending cache numeric score then sector_id_static, select actual UNION N(t). This is a diagnostic comparator, not an original account-selected industry set.',
  missing='Each percentile uses only that field known industry rows; A requires four known, START requires two known. No insertion of unknown at the bottom.',
  tie='Score arithmetic uses exact Fraction midpercentiles; sid deterministically cuts at5/3 without expanding tied groups; preserve mathematical tie counts and boundary split.',
  sources_immutable=True,do_not_use_old_hard_gate_columns=True,formal_PIT_fields_unknown=True,
  planned_outputs=['DAILY_RANKINGS.parquet','DAILY_RANKINGS.csv','DAILY_CARDINALITY.csv','SNAPSHOTS_ALL90.csv','SNAPSHOT_SELECTION_LISTS.json','FOCAL_RANKS_3D.csv'],
  no_accounts=True,no_allocations=True,no_70_30=True,D_not_defined=True)
 save('SCHEMA_PREPARED.json',schema)
 print(json.dumps(status,ensure_ascii=False),flush=True)

def assign_exact_queue(g,prefix,values,k):
 known=[i for i,v in values.items()if v is not None];ordered=sorted(known,key=lambda i:(-values[i],g.at[i,'sector_id_static']))
 counts={v:sum(values[i]==v for i in known)for v in set(values[i]for i in known)}
 g[prefix+'_order']=pd.Series(pd.NA,index=g.index,dtype='Int64');g[prefix+'_selected']=pd.Series(pd.NA,index=g.index,dtype='boolean')
 g[prefix+'_score_tie_count']=pd.Series(pd.NA,index=g.index,dtype='Int64');g[prefix+'_mathematical_rank_min']=pd.Series(pd.NA,index=g.index,dtype='Int64')
 g[prefix+'_cutoff_tie']=False
 cutoff=values[ordered[min(k,len(ordered))-1]]if ordered else None
 for rank,i in enumerate(ordered,1):
  v=values[i];g.at[i,prefix+'_order']=rank;g.at[i,prefix+'_selected']=rank<=k;g.at[i,prefix+'_score_tie_count']=counts[v]
  g.at[i,prefix+'_mathematical_rank_min']=1+sum(values[j]>v for j in known)
  g.at[i,prefix+'_cutoff_tie']=v==cutoff
 g[prefix+'_complete_count']=len(known);g[prefix+'_K_requested']=k
 g[prefix+'_cutoff_tie_total']=counts[cutoff]if cutoff is not None else 0
 g[prefix+'_cutoff_tie_selected']=sum(values[i]==cutoff for i in ordered[:k])if cutoff is not None else 0
 return ordered[:k]

def execute(freeze_file):
 begun=time.monotonic();freeze_file=Path(freeze_file)
 assert freeze_file.is_file(),'Parent freeze file required before any score computation'
 bind(freeze_file);f,h1,dm,sm,_=inputs();parts=[];cards=[]
 for day,g in f.groupby('date',sort=True):
  g=g.copy().reset_index(drop=True);fractions={}
  for raw,p in zip(RAW,PERCENTILES):
   known=g[raw].notna();n=int(known.sum());g[p]=np.nan;g[p+'_reference_N']=n
   vals={i:None for i in g.index}
   if n:
    units=2*g.loc[known,raw].rank(method='average')-1;assert units.mod(1).eq(0).all()
    for i,u in units.items():vals[i]=Fraction(int(u),2*n);g.at[i,p]=float(vals[i])
   fractions[p]=vals
  av={};sv={}
  for i in g.index:
   ps=[fractions[p][i]for p in PERCENTILES]
   av[i]=(2*ps[0]+ps[1]+ps[2]+ps[3])/5 if all(p is not None for p in ps)else None
   sv[i]=(ps[1]+ps[3])/2 if ps[1]is not None and ps[3]is not None else None
  g['A_score']=[float(av[i])if av[i]is not None else np.nan for i in g.index]
  g['START_score']=[float(sv[i])if sv[i]is not None else np.nan for i in g.index]
  g['A_score_exact']=[str(av[i])if av[i]is not None else None for i in g.index]
  g['START_score_exact']=[str(sv[i])if sv[i]is not None else None for i in g.index]
  ac=assign_exact_queue(g,'CONT',av,5);sc=assign_exact_queue(g,'START',sv,3)
  g['UNION_selected']=g.CONT_selected|g.START_selected;N=int(g.UNION_selected.eq(True).sum());g['N_union']=N
  if len([v for v in av.values()if v is not None])>=5 and len([v for v in sv.values()if v is not None])>=3:assert 5<=N<=8
  scores={i:float(h1[dm[day],sm[g.at[i,'sector_id_static']]])for i in g.index}
  horder=sorted([i for i,v in scores.items()if np.isfinite(v)],key=lambda i:(-scores[i],g.at[i,'sector_id_static']))
  g['H1_cache_same_date_score']=[scores[i]for i in g.index];g['H1_cache_exact_date']=day
  g['H1_order']=pd.Series(pd.NA,index=g.index,dtype='Int64');g['H1_matchedN_selected']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  for rank,i in enumerate(horder,1):g.at[i,'H1_order']=rank;g.at[i,'H1_matchedN_selected']=rank<=N
  g['H1_known_industries']=len(horder);g['H1_matchedN_complete']=len(horder)>=N
  if len(horder)>=N:assert int(g.H1_matchedN_selected.eq(True).sum())==N
  g['formal_PIT_CONT']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['formal_PIT_START']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['formal_PIT_UNION']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  g['qualification_hard_thresholds_removed']=True;g['H1_is_diagnostic_comparator_not_original_selection']=True
  cards.append(dict(date=day,CONT_selected=len(ac),START_selected=len(sc),overlap=len(set(ac)&set(sc)),N_union=N,
   H1_matchedN_selected=int(g.H1_matchedN_selected.eq(True).sum()),H1_same_date_known=len(horder),A_known=sum(v is not None for v in av.values()),START_score_known=sum(v is not None for v in sv.values())))
  parts.append(g)
 table=pd.concat(parts,ignore_index=True).sort_values(['date','sector_id_static']).reset_index(drop=True)
 assert len(table)==97650 and not table.duplicated(['date','sector_id_static']).any()
 table.to_parquet(O/'DAILY_RANKINGS.parquet',index=False);table.to_csv(O/'DAILY_RANKINGS.csv',index=False)
 pd.DataFrame(cards).to_csv(O/'DAILY_CARDINALITY.csv',index=False)
 snaps=table.loc[table.date.isin(SNAPSHOTS)];snaps.to_csv(O/'SNAPSHOTS_ALL90.csv',index=False);snaps.to_parquet(O/'SNAPSHOTS_ALL90.parquet',index=False)
 lists={}
 for day,g in snaps.groupby('date'):
  def queue(flag,order):return g.loc[g[flag].eq(True)].sort_values(order)[['sector_id_static','industry_static',order]].to_dict('records')
  lists[day]=dict(CONT=queue('CONT_selected','CONT_order'),START=queue('START_selected','START_order'),
   UNION=g.loc[g.UNION_selected.eq(True),['sector_id_static','industry_static','CONT_selected','START_selected']].to_dict('records'),
   H1_matchedN=queue('H1_matchedN_selected','H1_order'),N_union=int(g.N_union.iloc[0]))
 save('SNAPSHOT_SELECTION_LISTS.json',lists)
 focal=snaps.loc[snaps.industry_static.isin(['软件开发','通信设备','通信服务','房地产','半导体','电子化学品'])]
 focal.to_csv(O/'FOCAL_RANKS_3D.csv',index=False);save('FOCAL_RANKS_3D.json',focal.to_dict('records'))
 save('SUMMARY.json',dict(complete=True,rows=len(table),sessions=len(cards),industries=90,
  union_cardinality_counts=pd.DataFrame(cards).N_union.value_counts().sort_index().to_dict(),
  all_H1_comparisons_exact_same_day_sameN=all(c['H1_matchedN_selected']==c['N_union']for c in cards),
  all_formal_PIT_unknown=True,no_accounts=True,no_70_30_or_allocation=True,no_future_labels=True,
  no_old_R20_B60_pR5hard_gates=True,D_computed=False,seconds=time.monotonic()-begun))
 save('EXECUTED_SOURCE_SHA256.json',SOURCES)
 paths=[p for p in O.iterdir()if p.is_file()and p.name not in ['OUTPUT_SHA256.json','rank_daily.log']]
 save('OUTPUT_SHA256.json',{str(p.resolve()):sha(p)for p in paths})
 print(json.dumps(clean(dict(complete=True,sessions=len(cards),snapshots=lists)),ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--freeze-file')
 a=p.parse_args();assert a.prepare!=a.execute,'Choose exactly one mode'
 if a.prepare:prepare()
 else:
  assert a.freeze_file,'Explicit root freeze file path required';execute(a.freeze_file)
