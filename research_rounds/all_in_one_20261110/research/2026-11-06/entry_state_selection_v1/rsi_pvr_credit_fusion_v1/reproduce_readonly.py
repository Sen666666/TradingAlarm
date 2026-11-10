import pandas as pd,numpy as np,json,hashlib
from pathlib import Path
B=Path('selection_entry_diagnosis_v1'); O=B/'cp1_signal_mechanism_v1/soft_cp1_quality_v1/candidate_test'; M=B/'mobile_candidate_response_v1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
spec=dict(formula='q=U/(U+D)=Q/100; E=atanh((PVR-50)/50)/2; Ef=E-(1-q)*max(E,0); fused=50+50*tanh(2*Ef)',domain='PVR account original legal EMPTY fresh MOBILE only',K='min(20,N) same day; original unknown PVR/Q fixed slot',rank='fused rounded12 desc; original_PVR rounded12 desc; original_priority_rank; sid',clock='All signal inputs known after signal close. Evaluation original next common open. No new E0/I/CP, no account, no parameter scan.',annual='2022..2026 separate, common all-picks-mature dates; primary20 secondary5; roots unchanged',actual_rounds='original first_kind add, full original terminal outcome by 2026-05-15; unknown closed not loss; information association only')
print('FREEZE',json.dumps(spec,ensure_ascii=False),flush=True)
source={str(p):sha(p) for p in [O/'CANDIDATE_Q.parquet',M/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',M/'FIXED_NATIVE_PRICE_LABELS.parquet',B/'ALL_FIRST_ENTRIES.csv']}
c=pd.read_parquet(O/'CANDIDATE_Q.parquet');c=c[c.account.eq('PVR')].copy().reset_index(drop=True)
known=np.isfinite(c.original_PVR)&np.isfinite(c.Q)&c.original_PVR.gt(0)&c.original_PVR.lt(100)&c.Q.between(0,100)
c['fused']=np.nan
E=np.arctanh((c.loc[known,'original_PVR']-50)/50)/2;q=c.loc[known,'Q']/100
c.loc[known,'fused']=50+50*np.tanh(2*(E-(1-q)*np.maximum(E,0)))
assert np.all(c.loc[known,'fused']<=c.loc[known,'original_PVR']+1e-12)
assert np.all(c.loc[known & c.original_PVR.gt(50),'fused']>=50)
picks=[];moves=[];counts=[];poison_checks=0
def ranking(g):
 base=g.sort_values(['original_priority_rank','sid']).index.tolist()
 pos=[j for j,i in enumerate(base) if np.isfinite(c.at[i,'fused'])]
 knownids=[base[j] for j in pos]
 ids=sorted(knownids,key=lambda i:(-round(float(c.at[i,'fused']),12),-round(float(c.at[i,'original_PVR']),12),float(c.at[i,'original_priority_rank']),c.at[i,'sid']))
 alt=base.copy()
 for j,i in zip(pos,ids):alt[j]=i
 return base,alt
for day,g in c.groupby('day',sort=True):
 base,alt=ranking(g);k=min(20,len(g));bp={i:j+1 for j,i in enumerate(base)};ap={i:j+1 for j,i in enumerate(alt)}
 for kind,ids in [('PVR',base[:k]),('FUSED',alt[:k])]:
  z=c.loc[ids].copy();z['method']=kind;z['selected_rank']=range(1,k+1);picks.append(z)
 for i in base:
  moves.append(dict(day=day,sid=c.at[i,'sid'],year=c.at[i,'year'],epoch=c.at[i,'epoch'],Q=c.at[i,'Q'],PVR=c.at[i,'original_PVR'],fused=c.at[i,'fused'],base_rank=bp[i],fused_rank=ap[i],N=len(g),K=k,base_selected=bp[i]<=k,fused_selected=ap[i]<=k))
 counts.append(dict(day=day,year=g.year.iloc[0],N=len(g),K=k,added=len(set(alt[:k])-set(base[:k])),unknown=int(g.fused.isna().sum())))
 assert all(base[j]==alt[j] for j in range(len(base)) if not np.isfinite(c.at[base[j],'fused']))
 poison=g.copy();poison['ret20']=999999;poison['round_pnl']=-999999
 assert ranking(poison)==(base,alt);poison_checks+=1
sel=pd.concat(picks,ignore_index=True);mv=pd.DataFrame(moves);cnt=pd.DataFrame(counts)
rank_seal=hashlib.sha256(sel[['day','method','selected_rank','sid','CP1_id']].to_csv(index=False).encode()).hexdigest()
print('RANK_SEALED_BEFORE_LABELS',rank_seal,'candidate_rows',len(c),'selections',len(sel),'unknown',int(c.fused.isna().sum()),'poison_checks',poison_checks,flush=True)
old=pd.read_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet');old=old[old.account.eq('PVR')&old.strategy.eq('ORIGINAL_PVR')]
cols=['day','selected_rank','sid','CP1_id']
pd.testing.assert_frame_equal(sel[sel.method.eq('PVR')][cols].sort_values(cols[:2]).reset_index(drop=True),old[cols].sort_values(cols[:2]).reset_index(drop=True),check_dtype=False)
lab=pd.read_parquet(M/'FIXED_NATIVE_PRICE_LABELS.parquet')
s=sel.merge(lab,on=['day','sid'],validate='many_to_one');allc=c.merge(lab,on=['day','sid'],validate='many_to_one')
rows=[]
for H in [5,20]:
 for day,g in s.groupby('day'):
  groups={k:x for k,x in g.groupby('method')}
  b=groups['PVR'];f=groups['FUSED'];assert len(b)==len(f)
  if b['complete'+str(H)].all() and f['complete'+str(H)].all():
   rows.append(dict(day=day,year=int(b.year.iloc[0]),H=H,K=len(b),base_ret=b['ret'+str(H)].mean(),fused_ret=f['ret'+str(H)].mean(),dret=f['ret'+str(H)].mean()-b['ret'+str(H)].mean(),base_mae=b['mae'+str(H)].mean(),fused_mae=f['mae'+str(H)].mean(),dmae=f['mae'+str(H)].mean()-b['mae'+str(H)].mean()))
pair=pd.DataFrame(rows)
ann=pair.groupby(['year','H']).agg(days=('day','size'),events=('K','sum'),base_ret=('base_ret','mean'),fused_ret=('fused_ret','mean'),delta_ret=('dret','mean'),base_mae=('base_mae','mean'),fused_mae=('fused_mae','mean'),delta_mae=('dmae','mean')).reset_index()
print('ANNUAL_PAIRED',ann.to_json(orient='records'),flush=True)
print('REPLACEMENTS',cnt.groupby('year').agg(days=('day','size'),changed_days=('added',lambda x:int(x.gt(0).sum())),slots=('K','sum'),replacements=('added','sum'),unknown=('unknown','sum')).to_json(orient='index'),flush=True)
sets={k:set(zip(g.day,g.sid,g.epoch)) for k,g in sel.groupby('method')};roots=[]
for (sid,ep),g in allc.groupby(['sid','epoch'],sort=True,dropna=False):
 g=g.sort_values('t');b=g.iloc[0];early=g[g.t.le(b.t+5)]
 row=dict(sid=sid,epoch=ep,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc))
 for name,ss in sets.items():row[name]=any((r.day,sid,ep) in ss for r in early.itertuples())
 roots.append(row)
rt=pd.DataFrame(roots)
oldrt=pd.read_csv(M/'ROOT_EPISODE_COVERAGE.csv',keep_default_na=False);oldrt=oldrt[oldrt.account.eq('PVR')]
rr=rt.merge(oldrt[['sid','epoch','birth_day','ORIGINAL_PVR_early_capture']],on=['sid','epoch'],validate='one_to_one',suffixes=('','_old'))
assert len(rr)==len(rt)==len(oldrt) and rr.birth_day.eq(rr.birth_day_old).all() and rr.PVR.eq(rr.ORIGINAL_PVR_early_capture).all()
rrout=[]
for y,g in rt.groupby('year'):
 b=g[g.big60]
 rrout.append(dict(year=int(y),roots=len(g),complete60=int(g.complete60.sum()),big=len(b),base=int(b.PVR.sum()),fused=int(b.FUSED.sum()),lost=int((b.PVR&~b.FUSED).sum()),added=int((~b.PVR&b.FUSED).sum())))
print('ROOTS',json.dumps(rrout),flush=True)
for name,mask in [('924',pair.day.between('2024-09-24','2024-10-31')),('2026Q1',pair.day.between('2026-01-01','2026-03-31'))]:
 z=pair[mask]
 print('PERIOD',name,z.groupby('H').agg(days=('day','size'),base_ret=('base_ret','mean'),fused_ret=('fused_ret','mean'),delta_ret=('dret','mean'),delta_mae=('dmae','mean')).to_json(orient='index'),flush=True)
f=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');f=f[f.account.eq('PVR')&f.first_kind.eq('add')].copy()
a=f.merge(mv,left_on=['signal_day','sid'],right_on=['day','sid'],suffixes=('','_queue'),how='left',validate='one_to_one')
assert a.N.notna().all();assert np.nanmax(np.abs(a.PVR_decision-a.PVR))<1e-10
def auc(g,col):
 z=g[[col,'round_pnl']].dropna();win=z.round_pnl.gt(0);nw=int(win.sum());nl=int((~win).sum())
 return float((z[col].rank(method='average')[win].sum()-nw*(nw+1)/2)/(nw*nl)) if nw and nl else None
actual=[]
for y,g in a.groupby('year'):
 z=g[g.closed];knownz=z[z.fused.notna()]
 removed=z[z.base_selected&~z.fused_selected];added=z[~z.base_selected&z.fused_selected]
 actual.append(dict(year=int(y),births=len(g),closed=len(z),still_open=int((~g.closed).sum()),known_closed=len(knownz),wins=int(z.round_pnl.gt(0).sum()),PVR_auc=auc(knownz,'PVR'),fused_auc=auc(knownz,'fused'),removed_original_rounds=len(removed),removed_wins=int(removed.round_pnl.gt(0).sum()),removed_original_net=float(removed.round_pnl.sum()),added_observed_original_rounds=len(added),added_observed_wins=int(added.round_pnl.gt(0).sum()),added_observed_net=float(added.round_pnl.sum())))
print('ACTUAL_FIRST_MOBILE_ROUNDS',json.dumps(actual),flush=True)
casekeys=[('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('688582.SH','2024-07-29'),('000506.SZ','2024-10-15'),('600606.SH','2022-03-22'),('600056.SH','2022-03-30'),('601607.SH','2022-03-24'),('000620.SZ','2022-01-11'),('002911.SZ','2022-07-25'),('002317.SZ','2022-10-14')]
case=mv.set_index(['sid','day']).reindex(pd.MultiIndex.from_tuples(casekeys,names=['sid','day'])).reset_index()
case=case.merge(f[['sid','signal_day','round_pnl']],left_on=['sid','day'],right_on=['sid','signal_day'],how='left')
print('FIXED_CASES',case[['sid','day','Q','PVR','fused','base_rank','fused_rank','N','K','base_selected','fused_selected','round_pnl']].to_json(orient='records'),flush=True)
for name,mask in [('924_actual',a.signal_day.between('2024-09-19','2024-10-31')),('2026_winners',a.year.eq(2026)&a.closed)]:
 z=a[mask].sort_values('round_pnl',ascending=False).head(5)
 print('CASE_GROUP',name,z[['sid','signal_day','round_pnl','Q','PVR','fused','base_rank','fused_rank','N','K','base_selected','fused_selected']].to_json(orient='records'),flush=True)
# 2022 year-end closure kept separate from full-to-source terminal labels.
z=a[a.year.eq(2022)&a.closed_in_entry_year];print('2022_YEAR_END',len(z),int(z.round_pnl.gt(0).sum()),'vs full source',len(a[a.year.eq(2022)&a.closed]),flush=True)
assert source=={p:sha(Path(p)) for p in source}
print('SOURCE_HASHES_UNCHANGED',json.dumps(source),flush=True)
