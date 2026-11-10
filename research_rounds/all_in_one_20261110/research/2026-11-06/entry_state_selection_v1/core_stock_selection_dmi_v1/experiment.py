"""Single frozen CORE opportunity comparison. No account engine imported or run."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,json,gzip,hashlib,time,importlib.util,warnings
from pathlib import Path
from collections import Counter
import numpy as np,pandas as pd
warnings.filterwarnings('ignore',category=FutureWarning)
O=Path(__file__).resolve().parent;R=O.parent
P=R/'account_comparison_continuous_v1/run_1200000/pair'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
DMI=R/'dmi_boundary_migration_v1'
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
RAW=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def csv(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
def checkhash(x):
 for p,h in x.items():assert sha(p)==h,('source changed',p)
def prior_module():
 sp=importlib.util.spec_from_file_location('frozen_dmi_core_reuse',DMI/'experiment.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def protocol():
 assert not (O/'PROTOCOL.json').exists()
 x=dict(status='FROZEN_BEFORE_NEW_CORE_FEATURES_RANKS_AND_OUTCOMES_NOT_OOS',source='Existing DMI14 continuous boundary-migration formula and .25 influence budget, not selected by CORE results.',domain='Original PVR-account CORE pending only, independently from decisions and opportunities; original empty, core_Q True, no barriers, cap>0, no size_reject, original industry E0/attempt/stage active. Not MOBILE registry. Reconcile all 879 actual CORE first fills. Fixed future-selected1709, static sectors, original-account-conditioned states.',original_semantics='Unique-stock rank shared by CORE/MOBILE; opening CORE first, successful reserve prevents same-stock MOBILE, failed CORE may fall back. CORE needs native i_buy and unchanged S0 qualification; MOBILE fresh CP can bypass i_buy. CORE no CP requirement. CORE original I exit remains distinct from MOBILE CP protection.',formula=read(DMI/'PROTOCOL.json'),ranking='Three arms PVR/CLOSE/DMI. Original CORE-domain global K=min(20,N) establishes each (sector,has_actual_mobile_pending) quota. Only common-known stocks can exchange slots within that same date/sector/role group. UNKNOWN exact original slot; descending rounded12 score then original priority_rank and sid. No gate or threshold. CORE role and dual fallback opportunity held equal. This conditional CORE top20 is not the complete native mixed queue and not funded buys.',evaluation='Seal scores/picks before future labels. Exact existing native next common OPEN to common close labels 5/20/60, all selected in all3 arms complete for whole-day inclusion. Day equal means plus event counts, gross and40bp price-positive only. Existing fixed native epoch first legal CORE opportunity complete60 MFE>=30%,terminal>=20%, capture by first+5 common sessions. Every year,2022,924 Sep24-Oct31,2026Q1 and Jan15-30. Denominators/UNKNOWN explicit. 60-session block descriptive paired intervals; no statistical-selection claim.',rounds='Original full0-to0 net rounds from frozen ALL_FIRST_ENTRIES.csv only. CORE entry attribution, including subsequent MOBILE layers, not isolated CORE-layer PnL. Entry-year and signal-clock groups; terminal closed and separately entry-year closed. Not a new-strategy win rate; no35% claim.',constraints='No account rerun, no parameter search, no original model changes. Inputs immutable. Only this new output directory written.',created_utc=pd.Timestamp.now(tz='UTC').isoformat())
 dump('PROTOCOL.json',x)

def domain():
 assert (O/'PROTOCOL.json').exists() and not (O/'DOMAIN.parquet').exists()
 started=time.monotonic();src={str(p):sha(p) for p in [P/'PVR.json.gz',P/'opportunities.jsonl.gz',P/'daily.jsonl.gz',P/'rank-policy.jsonl.gz',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',DMI/'experiment.py',DMI/'PROTOCOL.json',O/'PROTOCOL.json',Path(__file__)]}
 x=json.load(gzip.open(P/'PVR.json.gz','rt'));pending={}
 for dec in x['decisions']:
  mobile={i['sid'] for i in dec['intents'] if i['role']=='mobile'}
  for i in dec['intents']:
   if i['role']=='core':pending[(dec['at'][:10],i['sid'])]=dict(i,day=dec['at'][:10],has_mobile=i['sid'] in mobile)
 sector={}
 for r in read(U/'INDUSTRY_MANIFEST.json'):
  path=r['refs']['state'];src[path]=sha(path);f=pd.read_parquet(path)
  for q in f[(f.day>='2022-01-01')&(f.day<='2026-05-15')].to_dict('records'):sector[(r['series'],q['day'])]=q
 held={}
 for line in gzip.open(P/'daily.jsonl.gz','rt'):
  z=json.loads(line)
  if z['account']=='PVR':held[z['at'][:10]]=set(z['positions'])
 rows=[]
 for line in gzip.open(P/'opportunities.jsonl.gz','rt'):
  z=json.loads(line);key=(z['day'],z['sid'])
  if z['account']!='PVR' or key not in pending:continue
  i=pending[key];assert not z['held'] and z['sid'] not in held[z['day']] and z['core_Q'] is True and 'core' in z['roles'] and not z['barriers'] and not i['size_reject'] and i['cap']>0
  s=sector[(z['sector'],z['day'])]
  rows.append(dict(sid=z['sid'],day=z['day'],sector=z['sector'],has_mobile=i['has_mobile'],cp_fresh=z['CP1_id'] is not None,core_Q=z['core_Q'],industry_active=bool(s['E0_valid'] and pd.notna(s['attempt_id']) and s['stage']>0),industry_stage=s['stage'],industry_attempt=str(s['attempt_id']),original_PVR=i['PVR_score'],original_priority_rank=i['priority_rank'],original_H1_rank=i['original_H1_rank'],epoch=str(i['epoch']),cap=i['cap'],budget=i['budget'],floor=i['floor']))
 c=pd.DataFrame(rows);assert len(c)==len(pending)==126994 and not c.duplicated(['sid','day']).any()
 legal=c[c.industry_active].reset_index(drop=True);assert len(legal)==106618
 sm={z['symbol']:z for z in read(U/'STOCK_MANIFEST.json')}
 for sid,ii in legal.groupby('sid').groups.items():
  path=sm[sid]['refs']['facts'];src[path]=sha(path);ff=pd.read_parquet(path);ff['I_on_first_observed']=ff.i_target.eq(1)&~ff.i_target.groupby(ff.segment_id).shift().eq(1);f=ff.reindex(pd.DatetimeIndex(legal.loc[ii,'day']))
  for k,v in [('e0_ready',1),('i_target',1),('g_ready',True),('i_buy',True)]:assert f[k].eq(v).all(),(sid,k)
  legal.loc[ii,'I_on_first_observed']=f.I_on_first_observed.to_numpy()
  cp=pd.read_parquet(sm[sid]['refs']['CP1'],columns=['receipt']).reindex(f.index);assert np.array_equal(cp.receipt.to_numpy(bool),legal.loc[ii,'cp_fresh'].to_numpy(bool))
  src[sm[sid]['refs']['CP1']]=sha(sm[sid]['refs']['CP1'])
 # Independent native unique-stock priority receipt, not a rebuilt PVR sort.
 rank_seen=set()
 for line in gzip.open(P/'rank-policy.jsonl.gz','rt'):
  z=json.loads(line);key=(z['day'],z['sid'])
  if z['account']=='PVR' and key in pending:
   i=pending[key];assert 'core' in z['roles'] and z['priority_rank']==i['priority_rank'] and z['original_H1_rank']==i['original_H1_rank'];assert (z['PVR'] is None and i['PVR_score'] is None) or z['PVR']==i['PVR_score'];rank_seen.add(key)
 assert len(rank_seen)==len(pending)
 first=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv',usecols=['account','sid','signal_day','first_kind']);core=first[first.account.eq('PVR')&first.first_kind.eq('core')]
 assert len(core)==len(core.merge(legal,left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one'))==879
 c.to_parquet(O/'ALL_CORE_PENDING.parquet',index=False);legal.to_parquet(O/'DOMAIN.parquet',index=False)
 counts=legal.assign(year=legal.day.str[:4]).groupby('year').agg(rows=('sid','size'),dates=('day','nunique'),stocks=('sid','nunique'),dual_role=('has_mobile','sum'),fresh_CP=('cp_fresh','sum'),PVR_known=('original_PVR','count')).reset_index();csv('DOMAIN_ANNUAL.csv',counts)
 dump('DOMAIN_AUDIT.json',dict(raw_core_pending=len(c),industry_inactive=int((~c.industry_active).sum()),legal_core_rows=len(legal),days=legal.day.nunique(),stocks=legal.sid.nunique(),dual_role=int(legal.has_mobile.sum()),core_only=int((~legal.has_mobile).sum()),fresh_CP=int(legal.cp_fresh.sum()),PVR_known=int(legal.original_PVR.notna().sum()),all879_actual_core_firsts_covered=True,actual_original_empty_and_CORE_Q_and_pending_and_source_facts_exact=True,original_unique_rank_receipt_exact=True,accounts=0,seconds=time.monotonic()-started))
 checkhash(src);dump('INPUT_HASHES.json',src);print('DOMAIN',read(O/'DOMAIN_AUDIT.json'),flush=True)

def features():
 assert not (O/'RANK_SEAL.json').exists();start=time.monotonic();src=read(O/'INPUT_HASHES.json');checkhash(src)
 c=pd.read_parquet(O/'DOMAIN.parquet');m=prior_module();parts=[];aud=[];prefix=0
 old=pd.read_parquet(DMI/'FEATURES.parquet',columns=['sid','day','d','dclose']);err=[]
 for no,(sid,g) in enumerate(c.groupby('sid')):
  p,path=m.source(sid);src[path]=sha(path);z=m.calc(p,m.cal);v=z.reindex(pd.DatetimeIndex(g.day))[['d','dclose','plus_di','minus_di','adx','age']].reset_index(drop=True);v['sid']=sid;v['day']=g.day.to_numpy();parts.append(v)
  if no%80==0:
   day=g.day.iloc[len(g)//2];cc=m.cal[m.cal<=day];pd.testing.assert_frame_equal(m.calc(p.loc[:day],cc),z.loc[cc],check_exact=True);prefix+=1
  ok=p.price_eligible.fillna(False)&p.observed_bar.fillna(False)&p.is_observed_bar.fillna(False)&~p.source_invalid.fillna(True)&~p.synthetic_event_bar.fillna(True)
  assert not p.loc[ok].groupby('segment_id')[['source_kind','source_path']].nunique(dropna=False).gt(1).any().any()
  aud.append(dict(sid=sid,source=path,rows=len(g),known=int(v.d.notna().sum())))
  if (no+1)%300==0:print('FEATURES',no+1,round(time.monotonic()-start,2),flush=True)
 c=c.merge(pd.concat(parts),on=['sid','day'],validate='one_to_one');j=c.merge(old,on=['sid','day'],suffixes=('','_old'),validate='one_to_one')
 for k in ['d','dclose']:
  assert np.array_equal(j[k].isna(),j[k+'_old'].isna());assert (j[k]-j[k+'_old']).abs().max()<1e-12
 c['row']=np.arange(len(c));c['calendar_t']=[m.cal.get_loc(pd.Timestamp(d)) for d in c.day];c['DMI']=m.fuse(c.original_PVR,c.d);c['CLOSE']=m.fuse(c.original_PVR,c.dclose);c['common_known']=c[['DMI','CLOSE','original_PVR']].notna().all(axis=1)
 picks=[];moves=[];queues=[]
 for day,g in c.groupby('day'):
  base=g.sort_values(['original_priority_rank','sid']);K=min(20,len(base));ks=base.head(K).groupby(['sector','has_mobile']).size().to_dict();bi=set(base.head(K).index)
  for method in ['PVR','CLOSE','DMI']:
   chosen=[]
   for key,gs in base.groupby(['sector','has_mobile'],sort=False):
    k=int(ks.get(key,0));order=list(gs.index)
    if method!='PVR':
     good=gs.common_known;ready=gs[good].assign(score12=gs.loc[good,method].round(12)).sort_values(['score12','original_priority_rank','sid'],ascending=[False,True,True]);it=iter(ready.index);order=[next(it) if good.loc[idx] else idx for idx in gs.index]
     assert all(order[pos]==idx for pos,idx in enumerate(gs.index) if not good.loc[idx]) and set(order)==set(gs.index)
    chosen.extend(order[:k]);moves.extend(dict(row=int(idx),method=method,group_rank=n+1,selected=n<k) for n,idx in enumerate(order))
   assert len(chosen)==K and c.loc[chosen].groupby(['sector','has_mobile']).size().to_dict()==ks
   picks.extend(dict(row=int(idx),day=day,method=method) for idx in chosen);queues.append(dict(day=day,method=method,N=len(g),K=K,known=int(g.common_known.sum()),changed=len(set(chosen)-bi)))
 c.to_parquet(O/'FEATURES.parquet',index=False);pd.DataFrame(picks).to_parquet(O/'SEALED_PICKS.parquet',index=False);pd.DataFrame(moves).to_parquet(O/'RANK_MOVES.parquet',index=False);csv('QUEUE_AUDIT.csv',queues);csv('SOURCE_AUDIT.csv',aud)
 qa=dict(rows=len(c),common_known=int(c.common_known.sum()),unknown_fixed=int((~c.common_known).sum()),old_MOBILE_feature_overlap=len(j),old_feature_exact=True,prefix_exact=prefix,same_day_sector_role_K=True,UNKNOWN_exact_slots=True,new_accounts=0,original_models=0)
 dump('QA.json',qa);checkhash(src);dump('INPUT_HASHES.json',src);seal={n:sha(O/n) for n in ['PROTOCOL.json','experiment.py','DOMAIN.parquet','FEATURES.parquet','SEALED_PICKS.parquet','RANK_MOVES.parquet']};dump('RANK_SEAL.json',dict(hashes=seal,future_labels_read=False,slots=len(picks)//3,qa=qa,seconds=time.monotonic()-start));print('SEALED',read(O/'RANK_SEAL.json'),flush=True)

def periods():return [('ALL',None,None)]+[(str(y),f'{y}-01-01',f'{y}-12-31') for y in range(2022,2027)]+[('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31'),('2026Jan15_30','2026-01-15','2026-01-30')]
def per(x,a,b,col='day'):return x if a is None else x[x[col].between(a,b)]
def evaluate():
 assert not (O/'EVALUATION_STARTED.json').exists();seal=read(O/'RANK_SEAL.json');assert all(sha(O/n)==h for n,h in seal['hashes'].items());dump('EVALUATION_STARTED.json',dict(at=pd.Timestamp.now(tz='UTC').isoformat(),single_attempt=True))
 start=time.monotonic();c=pd.read_parquet(O/'FEATURES.parquet');sel=pd.read_parquet(O/'SEALED_PICKS.parquet');m=prior_module();hh=np.load(H,allow_pickle=False);allcal=pd.DatetimeIndex(hh['dates']);use=(allcal>='2022-01-01')&(allcal<='2026-05-15');cal=allcal[use];close=pd.DataFrame(hh['close'][use],index=cal,columns=list(hh['symbols']));rawm={z['series_id']:z for z in read(RAW)['series']};sm={z['symbol']:z for z in read(U/'STOCK_MANIFEST.json')};labs=[];src=read(O/'INPUT_HASHES.json');src[str(H)]=sha(H);src[str(RAW)]=sha(RAW)
 for no,(sid,g) in enumerate(c.groupby('sid')):
  f=pd.read_parquet(sm[sid]['refs']['facts']).reindex(cal);path=rawm[sid]['raw']['path'];src[path]=sha(path);raw=pd.read_parquet(path);raw.index=pd.to_datetime(raw.trade_date);raw=raw.reindex(cal);op=raw.open.to_numpy(float)*f.factor.to_numpy(float);C=close[sid].to_numpy(float);fc=f.close.to_numpy(float);same=np.isfinite(C)&np.isfinite(fc);assert np.max(np.abs(C[same]-fc[same]))<1e-7;valid=np.isfinite(C)&(C>0)
  for r in g.itertuples():
   t=cal.get_loc(pd.Timestamp(r.day));en=t+1;openknown=bool(en<len(cal) and np.isfinite(op[en]) and op[en]>0);q=dict(row=r.row,sid=sid,day=r.day,open_known=openknown)
   for n in [5,20,60]:
    end=t+n;ok=bool(openknown and end<len(cal) and valid[en:end+1].all());q['complete'+str(n)]=ok;q['ret'+str(n)]=float(C[end]/op[en]-1) if ok else np.nan;q['mfe'+str(n)]=max(0,float(C[en:end+1].max()/op[en]-1)) if ok else np.nan;q['mae'+str(n)]=min(0,float(C[en:end+1].min()/op[en]-1)) if ok else np.nan
   q['big60']=bool(q['complete60'] and q['mfe60']>=.3 and q['ret60']>=.2);labs.append(q)
  if (no+1)%400==0:print('LABELS',no+1,round(time.monotonic()-start,1),flush=True)
 lab=pd.DataFrame(labs);old=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet');j=lab.merge(old,on=['sid','day'],suffixes=('','_old'),validate='one_to_one')
 for n in [5,20,60]:
  assert np.array_equal(j['complete'+str(n)],j['complete'+str(n)+'_old'])
  for k in ['ret','mfe','mae']:assert (j[k+str(n)]-j[k+str(n)+'_old']).abs().max()<1e-12
 lab.to_parquet(O/'FIXED_NATIVE_LABELS.parquet',index=False);c=c.merge(lab,on=['row','sid','day'],validate='one_to_one');s=sel.merge(c,on=['row','day'],validate='many_to_one');results=[];diff=[];coverage=[]
 for n in [5,20,60]:
  good=s.groupby('day')['complete'+str(n)].all();whole=s[s.day.isin(good[good].index)]
  for period,a,b in periods():
   full=per(s,a,b);sub=per(whole,a,b);coverage.append(dict(period=period,H=n,all_days=full.day.nunique(),all_slots=len(full)//3,common_days=sub.day.nunique(),common_slots=len(sub)//3,excluded_days=full.day.nunique()-sub.day.nunique()))
   if not len(sub):continue
   means=sub.groupby(['day','method'])['ret'+str(n)].mean().unstack('method')
   for method,g in sub.groupby('method'):
    results.append(dict(period=period,H=n,method=method,N=len(g),days=g.day.nunique(),mean_day=g.groupby('day')['ret'+str(n)].mean().mean(),mean_event=g['ret'+str(n)].mean(),mae_day=g.groupby('day')['mae'+str(n)].mean().mean(),mfe_day=g.groupby('day')['mfe'+str(n)].mean().mean(),positive=(g['ret'+str(n)]>0).mean(),positive_40bp=(g['ret'+str(n)]>.004).mean()))
   for x,y in [('DMI','PVR'),('CLOSE','PVR'),('DMI','CLOSE')]:diff.append(dict(period=period,H=n,comparison=x+'-'+y,**m.blockstat(means[x]-means[y])))
 csv('RESULTS.csv',results);csv('PAIRED_BLOCKS.csv',diff);csv('LABEL_COVERAGE.csv',coverage)
 mem={method:set(g.row) for method,g in sel.groupby('method')};roots=[]
 for (sid,epoch),g in c.groupby(['sid','epoch'],dropna=False):
  g=g.sort_values('calendar_t');r=g.iloc[0];early=set(g.loc[g.calendar_t.le(r.calendar_t+5),'row']);roots.append(dict(sid=sid,epoch=epoch,day=r.day,complete60=bool(r.complete60),big60=bool(r.big60),**{method:bool(early&rows) for method,rows in mem.items()}))
 roots=pd.DataFrame(roots);csv('ROOTS.csv',roots);rs=[]
 for period,a,b in periods():
  g=per(roots,a,b);big=g[g.big60]
  for method in mem:rs.append(dict(period=period,method=method,roots=len(g),complete=int(g.complete60.sum()),big=len(big),caught=int(big[method].sum()),lost_vs_PVR=int((big.PVR&~big[method]).sum()),added_vs_PVR=int((~big.PVR&big[method]).sum())))
 csv('ROOT_COVERAGE.csv',rs)
 # Original-account net rounds. No substitution or counterfactual round outcome.
 ac=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');ac=ac[ac.account.eq('PVR')].copy();ac['is_core']=ac.first_kind.eq('core');core=ac[ac.is_core].merge(c[['sid','day','row','cp_fresh','I_on_first_observed']],left_on=['sid','signal_day'],right_on=['sid','day'],suffixes=('_old',''),validate='one_to_one');assert len(core)==879
 core['signal_clock']=np.where(core.cp_fresh,'CORE_with_fresh_CP','CORE_without_fresh_CP');core['I_clock']=np.where(core.I_on_first_observed.eq(True),'first_observed_I_on','later_I_buy')
 csv('ORIGINAL_CORE_ROUNDS.csv',core)
 def metric(g,closed_column='closed'):
  z=g[g[closed_column]];v=z.round_pnl;return dict(firsts=len(g),closed=len(z),unclosed=len(g)-len(z),wins=int(v.gt(0).sum()),losses=int(v.lt(0).sum()),flat=int(v.eq(0).sum()),win_rate=float(v.gt(0).mean()) if len(z) else None,net_sum=float(v.sum()),gross_winner_sum=float(v[v>0].sum()),gross_loser_sum=float(v[v<0].sum()),complete60=int(g.complete60.sum()) if 'complete60' in g else None,big60=int(g.big60_posthoc.sum()) if 'big60_posthoc' in g else None)
 rr=[]
 for period,a,b in periods():
  g=per(core,a,b,'entry_day');full=per(ac,a,b,'entry_day')
  for view,col in [('terminal_closed','closed'),('closed_in_entry_year','closed_in_entry_year')]:
   rr.append(dict(period=period,dimension='CORE_ALL',value='ALL',view=view,**metric(g,col)))
   rr.append(dict(period=period,dimension='ALL_ROLES',value='ALL',view=view,**metric(full,col)))
   for key in ['signal_clock','I_clock']:
    for val,z in g.groupby(key):rr.append(dict(period=period,dimension=key,value=val,view=view,**metric(z,col)))
 csv('ORIGINAL_ROUND_SUMMARY.csv',rr)
 ar=[]
 for period,a,b in periods():
  g=per(core,a,b,'entry_day');base=g[g.row.isin(mem['PVR'])]
  for method,ss in mem.items():
   for label,z in [('original_fills_selected',g[g.row.isin(ss)]),('removed_original_PVR_fills',base[~base.row.isin(ss)])]:ar.append(dict(period=period,method=method,scope=label,**metric(z),NOT_COUNTERFACTUAL=True))
 csv('ORIGINAL_ROUND_ASSOCIATION.csv',ar)
 # Fixed names chosen earlier, not chosen by this result.
 namedkeys=pd.DataFrame(m.cases,columns=['sid','day']);named=namedkeys.merge(c,on=['sid','day'],how='left');named=named.merge(pd.read_parquet(O/'RANK_MOVES.parquet'),on='row',how='left');csv('FIXED_CASES.csv',named)
 checkhash(src);assert all(sha(O/n)==h for n,h in seal['hashes'].items());dump('EVALUATION_INPUT_HASHES.json',src);dump('COMPLETION.json',dict(completed=True,single_comparison=True,accounts=0,parameter_searches=0,original_models_rerun=0,new_CORE_domain_rows=len(c),same_day_sector_role_K=True,source_hashes_unchanged=True,rank_seal_unchanged=True,old_label_overlap_exact=len(j),new_net_round_win_rate_computed=False,seconds=time.monotonic()-start));print('RESULTS',pd.DataFrame(results).query('H in [20,60]').to_csv(index=False),flush=True);print('ROOTS',pd.DataFrame(rs).to_csv(index=False),flush=True);print('ROUNDS',pd.DataFrame(rr).query('dimension=="CORE_ALL" or (dimension=="ALL_ROLES" and period=="ALL")').to_csv(index=False),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
