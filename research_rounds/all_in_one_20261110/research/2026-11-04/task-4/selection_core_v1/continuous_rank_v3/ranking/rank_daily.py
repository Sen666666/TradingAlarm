"""Parent-fixed continuous rank study; prepare first, execute after root freeze.

No portfolio, allocation, old hard gates, new price features or forward labels.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import argparse,hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent;WORK=ROOT.parents[1]
PANEL=WORK/'selection_core_v1/industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
PRIOR_H1_SOURCES=WORK/'selection_core_v1/original_candidates/SOURCE_SHA256.json'
RAW=['rs_ind20','rs_ind5','B_now','dB5_paired','share_change_diagnostic']
PERCENTILES=['p_r20','p_r5','p_breadth','p_delta_b5','p_share_change']
READ_COLUMNS=['date','sector_id_static','industry_static',*RAW,'Nstatic','N_U_t','N25valid','Nobserved','membership_PIT_verified']
SNAPSHOTS=['2024-09-24','2026-01-15','2022-01-24'];SOURCES={}
FROZEN_EXPECTED='cf6feda161b897c5fe54b6012a135f7bec7f2991f89162b655b877625d178fcc'
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
  D_status='Parent frozen exploratory D=.5*p_share_change+.5*p_delta_b5; no score computed by prepare.')
 return f,scores,date_map,sector_map,readiness

def prepare():
 _,_,_,_,status=inputs();save('SOURCE_READINESS.json',status);save('PREPARED_SOURCE_SHA256.json',SOURCES)
 schema=dict(status='DRAFT_PENDING_ROOT_FROZEN_DESIGN',keys=['date','sector_id_static'],input_raw=RAW,input_read_columns=READ_COLUMNS,
  percentile_fields=dict(zip(RAW,PERCENTILES)),scores={'A_score':'.4*p_r20+.2*p_r5+.2*p_breadth+.2*p_delta_b5','E_score':'.5*p_r5+.5*p_delta_b5','D_score':'.5*p_share_change+.5*p_delta_b5'},
  selection={'native_A_selected':'Exact first5 complete native A','native_E_selected':'Exact first3 complete native E','native_UNION_selected':'De-duplicated native OR',
   'C_t_member':'A/E/D/original same-day H1 all known; no future label condition',
   'common_A_selected':'Within C_t first5 A','common_E_selected':'Within C_t first3 E','common_UNION_selected':'Deduplicated common A/E, defines N_common_union',
   'common_H1_selected':'Within same C_t exact cache top N_common_union','common_D_selected':'Within same C_t top N_common_union exploratory D'},
  H1_baseline='Exact source same-day cache, descending cache numeric score then sector_id_static, select common UNION N(t) within same C_t. Diagnostic comparator, not original account-selected industries.',
  missing='Each percentile uses only that field known industry rows; A requires four known, START requires two known. No insertion of unknown at the bottom.',
  tie='Score arithmetic uses exact Fraction midpercentiles; sid deterministically cuts at5/3 without expanding tied groups; preserve mathematical tie counts and boundary split.',
  sources_immutable=True,do_not_use_old_hard_gate_columns=True,formal_PIT_fields_unknown=True,
  planned_outputs=['DAILY_RANKINGS.parquet','DAILY_RANKINGS.csv','DAILY_CARDINALITY.csv','SNAPSHOTS_ALL90.csv','SNAPSHOT_SELECTION_LISTS.json','FOCAL_RANKS_3D.csv'],
  no_accounts=True,no_allocations=True,no_70_30=True,D_exploratory_new_not_legacy=True)
 save('SCHEMA_PREPARED.json',schema)
 print(json.dumps(status,ensure_ascii=False),flush=True)

def assign_exact_queue(g,prefix,values,k):
 known=[i for i,v in values.items()if v is not None];ordered=sorted(known,key=lambda i:(-values[i],g.at[i,'sector_id_static']))
 counts=Counter(values[i]for i in known);first_rank={};orders={}
 for rank,i in enumerate(ordered,1):
  orders[i]=rank;first_rank.setdefault(values[i],rank)
 g[prefix+'_order']=pd.Series([orders.get(i,pd.NA)for i in g.index],index=g.index,dtype='Int64')
 g[prefix+'_score_tie_count']=pd.Series([counts[values[i]]if i in orders else pd.NA for i in g.index],index=g.index,dtype='Int64')
 g[prefix+'_mathematical_rank_min']=pd.Series([first_rank[values[i]]if i in orders else pd.NA for i in g.index],index=g.index,dtype='Int64')
 g[prefix+'_complete_count']=len(known)
 if k is None:return ordered
 cutoff=values[ordered[min(k,len(ordered))-1]]if ordered and k>0 else None
 g[prefix+'_selected']=pd.Series([orders[i]<=k if i in orders else pd.NA for i in g.index],index=g.index,dtype='boolean')
 g[prefix+'_cutoff_tie']=[values[i]==cutoff if i in orders and cutoff is not None else False for i in g.index]
 g[prefix+'_K_requested']=k;g[prefix+'_cutoff_tie_total']=counts[cutoff]if cutoff is not None else 0
 g[prefix+'_cutoff_tie_selected']=sum(values[i]==cutoff for i in ordered[:k])if cutoff is not None else 0
 return ordered[:k]

def execute(freeze_file):
 begun=time.monotonic();freeze_file=Path(freeze_file)
 assert freeze_file.is_file(),'Parent freeze file required before any score computation'
 bind(freeze_file,FROZEN_EXPECTED);f,h1,dm,sm,_=inputs();parts=[];cards=[];differences=[]
 for day,g in f.groupby('date',sort=True):
  g=g.copy().reset_index(drop=True);fractions={}
  for raw,p in zip(RAW,PERCENTILES):
   known=g[raw].notna();n=int(known.sum());g[p]=np.nan;g[p+'_reference_N']=n
   vals={i:None for i in g.index}
   if n:
    units=2*g.loc[known,raw].rank(method='average')-1;assert units.mod(1).eq(0).all()
    for i,u in units.items():vals[i]=Fraction(int(u),2*n);g.at[i,p]=float(vals[i])
   fractions[p]=vals
  av={};ev={};dv={}
  for i in g.index:
   ps=[fractions[p][i]for p in PERCENTILES]
   av[i]=(2*ps[0]+ps[1]+ps[2]+ps[3])/5 if all(p is not None for p in ps[:4])else None
   ev[i]=(ps[1]+ps[3])/2 if ps[1]is not None and ps[3]is not None else None
   dv[i]=(ps[4]+ps[3])/2 if ps[4]is not None and ps[3]is not None else None
  for name,values in [('A',av),('E',ev),('D',dv)]:
   g[name+'_score']=[float(values[i])if values[i]is not None else np.nan for i in g.index]
   g[name+'_score_exact']=[str(values[i])if values[i]is not None else None for i in g.index]
   g[name+'_known']=[values[i]is not None for i in g.index]
  hv={i:float(h1[dm[day],sm[g.at[i,'sector_id_static']]])for i in g.index}
  hv={i:v if np.isfinite(v)else None for i,v in hv.items()}
  g['H1_cache_same_date_score']=[hv[i]if hv[i]is not None else np.nan for i in g.index]
  g['H1_cache_exact_date']=day;g['H1_known']=[hv[i]is not None for i in g.index]
  an=assign_exact_queue(g,'native_A',av,5);en=assign_exact_queue(g,'native_E',ev,3)
  assign_exact_queue(g,'native_D',dv,None);assign_exact_queue(g,'native_H1',hv,None)
  g['native_UNION_selected']=g.native_A_selected|g.native_E_selected
  native_set=set(g.index[g.native_UNION_selected.eq(True)]);Nnative=len(native_set)
  C={i:av[i]is not None and ev[i]is not None and dv[i]is not None and hv[i]is not None for i in g.index}
  g['C_t_member']=[C[i]for i in g.index];NC=sum(C.values());g['N_C']=NC
  commonA={i:v if C[i]else None for i,v in av.items()};commonE={i:v if C[i]else None for i,v in ev.items()}
  commonD={i:v if C[i]else None for i,v in dv.items()};commonH={i:v if C[i]else None for i,v in hv.items()}
  ac=assign_exact_queue(g,'common_A',commonA,5);ec=assign_exact_queue(g,'common_E',commonE,3)
  g['common_UNION_selected']=g.common_A_selected|g.common_E_selected
  common_set=set(g.index[g.common_UNION_selected.eq(True)]);N=len(common_set)
  dc=assign_exact_queue(g,'common_D',commonD,N);hc=assign_exact_queue(g,'common_H1',commonH,N)
  g['N_native_union']=Nnative;g['N_common_union']=N
  g['common_comparison_available']=NC>0;g['common_UNION_known']=g.common_UNION_selected.notna()
  g['native_UNION_known']=g.native_UNION_selected.notna()
  assert len(dc)==len(hc)==N
  if NC>=5:assert 5<=N<=8
  outside=~g.C_t_member
  for field in ['common_A_selected','common_E_selected','common_UNION_selected','common_D_selected','common_H1_selected']:
   assert g.loc[outside,field].isna().all(),('Outside C_t was marked unselected',field)
  def tag(a,b):
   if pd.isna(a)or pd.isna(b):return 'UNKNOWN'
   return 'BOTH'if a and b else'A_ONLY'if a else'E_ONLY'if b else'NONE'
  g['native_channel_label']=[tag(a,b)for a,b in zip(g.native_A_selected,g.native_E_selected)]
  g['common_channel_label']=[tag(a,b)for a,b in zip(g.common_A_selected,g.common_E_selected)]
  g['C_missing_inputs']=['|'.join(k for k,v in [('A',av[i]),('E',ev[i]),('D',dv[i]),('H1',hv[i])]if v is None)for i in g.index]
  for i in sorted(native_set^common_set):
   differences.append(dict(date=day,sector_id_static=g.at[i,'sector_id_static'],industry_static=g.at[i,'industry_static'],
    native_selected=i in native_set,common_selected=i in common_set,C_t_member=C[i],
    reason='not_in_C:'+g.at[i,'C_missing_inputs']if not C[i]else'promotion_after_restricting_to_C'))
  g['formal_PIT_CONT']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['formal_PIT_START']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['formal_PIT_UNION']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  g['formal_PIT_D']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  g['qualification_hard_thresholds_removed']=True;g['H1_is_diagnostic_comparator_not_original_selection']=True
  g['D_exploratory_new_not_legacy']=True
  cards.append(dict(date=day,N_C=NC,native_A_selected=len(an),native_E_selected=len(en),N_native_union=Nnative,
   common_A_selected=len(ac),common_E_selected=len(ec),common_overlap=len(set(ac)&set(ec)),N_common_union=N,
   common_H1_selected=len(hc),common_D_selected=len(dc),H1_same_date_known=sum(v is not None for v in hv.values()),
   A_known=sum(v is not None for v in av.values()),E_known=sum(v is not None for v in ev.values()),D_known=sum(v is not None for v in dv.values()),
   native_common_symmetric_difference=len(native_set^common_set)))
  if day in SNAPSHOTS:
   early=dict(date=day,N_C=NC,N_native_union=Nnative,N_common_union=N,
    native_A=g.loc[an,'industry_static'].tolist(),native_E=g.loc[en,'industry_static'].tolist(),
    common_A=g.loc[ac,'industry_static'].tolist(),common_E=g.loc[ec,'industry_static'].tolist(),
    common_UNION=g.loc[sorted(common_set),'industry_static'].tolist(),
    H1_sameN=g.loc[hc,'industry_static'].tolist(),D_sameN=g.loc[dc,'industry_static'].tolist(),
    focal=g.loc[g.industry_static.isin(['软件开发','房地产','通信设备','半导体','电子化学品']),
       ['industry_static','A_score','E_score','D_score','native_A_order','native_E_order','common_A_order','common_E_order','common_UNION_selected','common_H1_selected','common_D_selected','C_missing_inputs']].to_dict('records'))
   save('EARLY_'+day+'.json',early);print(json.dumps(clean(early),ensure_ascii=False),flush=True)
  parts.append(g)
 table=pd.concat(parts,ignore_index=True).sort_values(['date','sector_id_static']).reset_index(drop=True)
 assert len(table)==97650 and not table.duplicated(['date','sector_id_static']).any()
 table.to_parquet(O/'DAILY_RANKINGS.parquet',index=False);table.to_csv(O/'DAILY_RANKINGS.csv',index=False)
 pd.DataFrame(cards).to_csv(O/'DAILY_CARDINALITY.csv',index=False)
 snaps=table.loc[table.date.isin(SNAPSHOTS)];snaps.to_csv(O/'SNAPSHOTS_ALL90.csv',index=False);snaps.to_parquet(O/'SNAPSHOTS_ALL90.parquet',index=False)
 lists={}
 for day,g in snaps.groupby('date'):
  def queue(flag,order):return g.loc[g[flag].eq(True)].sort_values(order)[['sector_id_static','industry_static',order]].to_dict('records')
  lists[day]=dict(native_A=queue('native_A_selected','native_A_order'),native_E=queue('native_E_selected','native_E_order'),
   native_UNION=g.loc[g.native_UNION_selected.eq(True),['sector_id_static','industry_static','native_channel_label']].to_dict('records'),
   common_A=queue('common_A_selected','common_A_order'),common_E=queue('common_E_selected','common_E_order'),
   common_UNION=g.loc[g.common_UNION_selected.eq(True),['sector_id_static','industry_static','common_channel_label']].to_dict('records'),
   H1_sameN_in_C=queue('common_H1_selected','common_H1_order'),D_sameN_in_C=queue('common_D_selected','common_D_order'),
   N_C=int(g.N_C.iloc[0]),N_native_union=int(g.N_native_union.iloc[0]),N_common_union=int(g.N_common_union.iloc[0]))
 save('SNAPSHOT_SELECTION_LISTS.json',lists)
 focal=snaps.loc[snaps.industry_static.isin(['软件开发','通信设备','通信服务','房地产','半导体','电子化学品'])]
 focal.to_csv(O/'FOCAL_RANKS_3D.csv',index=False);save('FOCAL_RANKS_3D.json',focal.to_dict('records'))
 diffcols=['date','sector_id_static','industry_static','native_selected','common_selected','C_t_member','reason']
 pd.DataFrame(differences,columns=diffcols).to_csv(O/'NATIVE_COMMON_DIFFERENCES.csv',index=False)
 save('SUMMARY.json',dict(complete=True,rows=len(table),sessions=len(cards),industries=90,
  common_union_cardinality_counts=pd.DataFrame(cards).N_common_union.value_counts().sort_index().to_dict(),
  native_union_cardinality_counts=pd.DataFrame(cards).N_native_union.value_counts().sort_index().to_dict(),
  N_C_counts=pd.DataFrame(cards).N_C.value_counts().sort_index().to_dict(),native_common_difference_rows=len(differences),
  all_H1_D_comparisons_exact_same_day_sameC_sameN=all(c['common_H1_selected']==c['common_D_selected']==c['N_common_union']for c in cards),
  all_formal_PIT_unknown=True,no_accounts=True,no_70_30_or_allocation=True,no_future_labels=True,
  no_old_R20_B60_pR5hard_gates=True,D_computed=True,D_exploratory_not_legacy=True,seconds=time.monotonic()-begun))
 schema=read(O/'SCHEMA_PREPARED.json');schema.update(status='EXECUTED_FROZEN',frozen_design_SHA256=FROZEN_EXPECTED,
  main_strategy_flags=['common_UNION_selected','common_H1_selected','common_D_selected'],
  native_strategy_flags=['native_A_selected','native_E_selected','native_UNION_selected'],
  common_queue_flags=['common_A_selected','common_E_selected'],C_t_field='C_t_member',N_C_field='N_C',N_t_field='N_common_union',
  outside_C_common_flags='NA; not unselected/False',exact_score_fields=['A_score_exact','E_score_exact','D_score_exact'],
  native_rank_only_fields=['native_D_order','native_H1_order'],source_H1_score='H1_cache_same_date_score')
 save('SCHEMA.json',schema)
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
