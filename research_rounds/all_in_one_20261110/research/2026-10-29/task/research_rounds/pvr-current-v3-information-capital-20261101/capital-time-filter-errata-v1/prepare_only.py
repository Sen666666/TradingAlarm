"""Pre-outcome readiness and blind matching. No ledger/model/account imports.

Original PVR score and original matcher are extracted verbatim as AST functions.
No forward return/MAE/MFE values are accessed or joined in this program.
"""
from pathlib import Path
from datetime import datetime,timezone
import ast,json,gzip,hashlib,collections,time,math,sys,statistics,traceback
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
OLD=W/'opportunity-quality-ranking-20261031';U=W/'universe-cp1-inputs-20261031'
WINDOWS={'2022':('2022-01-01','2022-12-30'),'2025_26':('2025-07-01','2026-06-30')}
ROOTS={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair','2025_26':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
INPUT={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):INPUT[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 INPUT[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def function(path,name,env):
 s=Path(path).read_text();INPUT[str(path)]=sha(path);n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 text='\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])+'\n';exec(compile(text,str(path),'exec'),env)
 return env[name],text
freeze=read(O/'CONTRACT_FREEZE.json');assert sha(O/'CONTRACT.txt')==freeze['contract_sha256']
assert freeze['version']=='v1.2' and not freeze['new_paired_outcomes_read']
score,scoretext=function(R/'pvr-act-comparison-20261027/code/experiment.py','score',dict(np=np,pd=pd))
digest=lambda x:hashlib.sha256(x.encode()).hexdigest()
match,matchtext=function(R/'pvr-incremental-order-20261029/code/study.py','match',dict(pd=pd,collections=collections,digest=digest))
env=dict(pd=pd,np=np)
_,_=function(R/'pv-participation-response-20261020/code/data_utils.py','boolean_column',env)
eligible,_=function(R/'pv-participation-response-20261020/code/data_utils.py','eligible_prices',env)
(O/'original_score_function.py').write_text(scoretext);(O/'original_match_function.py').write_text(matchtext)
SM={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};META=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
def tests():
 out=[]
 def check(name,ok):assert ok,name;out.append(name)
 ix=pd.date_range('2020-01-01',periods=220);f=pd.DataFrame(dict(close=100.,amount=1000.,segment_id=0),index=ix)
 z=score(f);check('85th close first ready',z.score.iloc[:84].isna().all() and z.score.iloc[84]==50)
 ff=f.copy();ff.loc[ix[90],'amount']=np.nan;zz=score(ff);check('NA resets and is not neutral50',pd.isna(zz.score.iloc[90]) and zz.score.iloc[91:175].isna().all() and zz.score.iloc[175]==50)
 ff=f.copy();ff.loc[ix[90]:,'segment_id']=1;zz=score(ff);check('source reset full warm',zz.score.iloc[90:174].isna().all() and zz.score.iloc[174]==50)
 ff=f.copy();ff.loc[ix[100],'amount']=1e12;zz=score(ff);check('amount without price creates no signed evidence',zz.score.dropna().eq(50).all())
 ff=f.copy();ff.close=100*np.exp(np.arange(len(f))*.001);zz=score(ff);gg=ff.copy();gg.amount*=100;pd.testing.assert_series_equal(zz.score,score(gg).score,check_exact=True);check('common amount unit scaling cancels',True)
 a=dict(date=pd.Timestamp('2022-01-05'),symbol='A',sector='S',h1=50.,age=0,runup=0.,scale=.1,pvr=20.,pvr_raw=20.,grade=2,e0_epoch='A0',i_epoch='AI',anchor='2022-01-05',feature_ready=True,known_id='A')
 b=dict(a,symbol='B',h1=51.,age=5,runup=.1,pvr=30.,pvr_raw=30.,e0_epoch='B0',i_epoch='BI',known_id='B')
 q=pd.DataFrame([a,b]);p,_=match(q);check('all three inherited boundaries inclusive',len(p)==1)
 for field,value in [('h1',51.00001),('age',6),('runup',.100001)]:
  qq=q.copy();qq.loc[1,field]=value;pp,_=match(qq);check('reject outside '+field,len(pp)==0)
 qq=q.copy();qq['pvr']=0.;pp,_=match(qq);check('PVR-neutral IDs invariant',list(p.pair_id)==list(pp.pair_id))
 qq=pd.concat([q,q.assign(date=pd.Timestamp('2022-01-06'))]);pp,_=match(qq);check('E0 episode no replacement across dates',len(pp)==1)
 qq=q.copy();qq.loc[1,'feature_ready']=False;pp,_=match(qq);check('unknown feature not imputed',len(pp)==0)
 save('FORMULA_MATCH_UNIT_GATE.json',dict(passed=True,checks=out,count=len(out),scope='original function input/NA/reset and unchanged matching semantics; no new coefficient tests',new_accounts=0,new_forward_labels=0))

def population():
 data={};points=collections.defaultdict(set);qdays={};opmaps={};dn={}
 for win in WINDOWS:
  d=read(OLD/win/'DENOMINATORS.json');p=OLD/win/'CANDIDATES.jsonl.gz';assert sha(p)==d['candidate_file_SHA256'];rs=[]
  for x in rows(p):
   # Explicitly discard all original funding/outcome flags before pairing.
   z={k:x[k] for k in ['sid','day','receipt','sector','industry_attempt','industry_stage','H1','original_global_rank']};z['window']=win;rs.append(z);points[z['sid']].add(z['day'])
  assert len(rs)==d['candidates'];data[win]=rs;dn[win]={k:d[k] for k in ['all_original_fresh_receipts','exclusion_counts','candidates','unique_stocks','candidate_dates']}
  qs=collections.defaultdict(list);om={};allfresh=0
  for x in rows(ROOTS[win]/'opportunities.jsonl.gz'):
   if x['core_Q'] is True:qs[x['sid']].append(x['day'])
   if x['CP1_id']:
    allfresh+=1;om[x['sid'],x['day'],x['CP1_id']]={k:x[k] for k in ['roles','barriers','held','core_Q','mobile_Q','rank']}
  assert allfresh==d['all_original_fresh_receipts'];qdays[win]=qs;opmaps[win]=om
 save('MOTHER_DENOMINATORS.json',dn)
 return data,points,qdays,opmaps

def load_signal(sid):
 rec=SM[sid];p=Path(next(x for x in rec['source_sha256'] if x.endswith('/signal.parquet')));assert sha(p)==rec['source_sha256'][str(p)];INPUT[str(p)]=sha(p)
 return pd.read_parquet(p).loc[:'2026-06-30'],p

def cache_score(sid,days):
 p=O/'pvr-cache'/f'{sid}.parquet';m=O/'pvr-cache'/f'{sid}.json'
 src=Path(next(x for x in SM[sid]['source_sha256'] if x.endswith('/signal.parquet')));expected=SM[sid]['source_sha256'][str(src)]
 if p.exists() and m.exists():
  r=read(m)
  if r['source_sha256']==expected and r['function_sha256']==digest(scoretext) and r['requested_days']==sorted(days) and sha(p)==r['output_sha256']:
   INPUT[str(src)]=expected;return pd.read_parquet(p),r,True
 f,src=load_signal(sid);z=score(f);idx=pd.DatetimeIndex(sorted(days));keep=z.reindex(idx);keep.index.name='day';p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');keep.to_parquet(t);t.replace(p)
 r=dict(symbol=sid,source=str(src),source_sha256=sha(src),function_sha256=digest(scoretext),full_warm_start=str(f.index.min().date()),feature_cutoff='2026-06-30',full_input_rows=len(f),requested_days=sorted(days),known=int(keep.score.notna().sum()),unknown=int(keep.score.isna().sum()),output_sha256=sha(p));save(m.relative_to(O),r)
 return keep,r,False

def epoch_maps(f,sid):
 result={}
 for field,key in [('e0_target','e0'),('i_target','i')]:
  active=f[field].fillna(False).astype(bool);start=active & (~active.shift(fill_value=False)|f.segment_id.ne(f.segment_id.shift()));starts=pd.Series(None,index=f.index,dtype=object)
  for t in f.index[start]:starts.loc[t]=str(t.date())
  day=starts.groupby(f.segment_id).ffill().where(active,None);result[key]=day
 return result
def describe(rs,fields=('h1','age','runup','scale','pvr')):
 out={}
 for key in fields:
  a=[float(x[key]) for x in rs if x.get(key) is not None and np.isfinite(x[key])]
  out[key]=dict(known=len(a),unknown=len(rs)-len(a),min=min(a) if a else None,median=statistics.median(a) if a else None,max=max(a) if a else None)
 return out

def main():
 begun=time.monotonic();tests();data,points,qdays,opmaps=population();ids=sorted(points)
 pilot_start=time.monotonic();pilot=[]
 for sid in ids[:10]:
  st=time.monotonic();z,r,reused=cache_score(sid,points[sid]);pilot.append(dict(sid=sid,seconds=time.monotonic()-st,reused=reused,known=r['known']))
  if len(pilot)<=3:
   f,src=load_signal(sid);cut='2025-12-31';small=score(f.loc[:cut]);full=score(f);pd.testing.assert_frame_equal(small,full.loc[:cut],check_exact=True,check_freq=False)
 estimate=sum(x['seconds'] for x in pilot)/len(pilot)*len(ids)*1.3
 save('CACHE_PILOT.json',dict(stocks_in_mother_union=len(ids),pilot=pilot,pilot_wall_seconds=time.monotonic()-pilot_start,estimated_total_cache_seconds=estimate,physical_prefix_checks=3,prior_407_score_files=407,prior_filenames_not_assumed_compatible=True,incremental_scope='only mother stocks; original score, full warm, no financial engine'))
 print('PILOT',len(ids),'estimated cache seconds',round(estimate,2),flush=True)
 if estimate>180:
  save('READINESS.json',dict(status='cache estimate exceeds bounded180s preparation; pilot saved, no blind bulk',estimate_seconds=estimate,new_paired_outcomes_read=False));return
 features={win:[] for win in WINDOWS};by=collections.defaultdict(list)
 for win,rs in data.items():
  for x in rs:by[x['sid']].append((win,x))
 deadline=time.monotonic()+180;cache=[]
 for k,sid in enumerate(ids,1):
  if time.monotonic()>deadline:
   save('READINESS.json',dict(status='partial reusable original score cache; bounded deadline',completed=len(cache),stocks=len(ids),new_paired_outcomes_read=False));return
  z,receipt,reused=cache_score(sid,points[sid]);cache.append(receipt)
  fp=Path(SM[sid]['refs']['facts']);assert sha(fp)==SM[sid]['output_sha256'][str(fp)];INPUT[str(fp)]=sha(fp);f=pd.read_parquet(fp,columns=['close','segment_id','i_target','e0_target'])
  # Same eligible price mask used by native FrozenMarket; never drop price rows merely for missing volume.
  raw,src=load_signal(sid);ef=eligible(raw);common=f.loc[:'2026-06-30'];assert common.index.equals(ef.index),(sid,'cached/native price observation clock mismatch')
  ep=epoch_maps(f,sid);pos={str(t.date()):i for i,t in enumerate(f.index)};anchors={}
  for win,(lo,hi) in WINDOWS.items():
   aa={}
   for d in qdays[win].get(sid,[]):
    t=pd.Timestamp(d)
    if t not in f.index:continue
    start=ep['i'].loc[t]
    if start and start>=lo:aa.setdefault(start,d)
   anchors[win]=aa
  for win,x in by[sid]:
   day=x['day'];t=pd.Timestamp(day);r=f.loc[t];i_start=ep['i'].loc[t];e_start=ep['e0'].loc[t];a=anchors[win].get(i_start);p=z.loc[t];why=[]
   if not a:why.append('I_epoch_inherited_anchor_history_unknown' if i_start and i_start<WINDOWS[win][0] else 'no_original_core_Q_anchor_yet')
   if not np.isfinite(p.score) or not np.isfinite(p.scale) or p.scale<=0:why.append('PVR_or_scale_unready')
   if not i_start or not e_start:why.append('epoch_unknown')
   if not np.isfinite(x['H1']):why.append('H1_unknown')
   sg=int(r.segment_id);e0=f'{sid}|source={sg}|visible_E0_start={e_start}' if e_start else None
   known=f'{sid}|source={sg}|I-visible-start={i_start}|E0={e0}|anchor={a}|decision={day}'
   out=dict(window=win,date=pd.Timestamp(day),symbol=sid,receipt=x['receipt'],sector=x['sector'],industry_attempt=x['industry_attempt'],industry_stage=x['industry_stage'],h1=float(np.round(x['H1'],12)),original_global_rank=x['original_global_rank'],i_epoch=f'{sid}|source={sg}|I-visible-start={i_start}',i_start=i_start,e0_epoch=e0,anchor=a,age=pos[day]-pos[a] if a else np.nan,runup=math.log(float(r['close'])/float(f.loc[pd.Timestamp(a),'close'])) if a else np.nan,scale=float(p.scale),pvr=float(np.round(p.score,12)),pvr_raw=float(p.score),grade=None,known_id=known,feature_ready=not why,unknown_reasons=why)
   features[win].append(out)
  if k%250==0:print('CACHE',k,'/',len(ids),round(time.monotonic()-begun,2),flush=True)
 save('CACHE_MANIFEST.json',dict(stocks=len(cache),entries=cache,formula_function_sha256=digest(scoretext),original_price_clock_all_exact=True,seconds=time.monotonic()-begun))
 result={};matchids={};statuses={};allpairs={}
 for win,rs in features.items():
  frame=pd.DataFrame(rs).sort_values(['date','symbol']).reset_index(drop=True);d=O/win;d.mkdir(exist_ok=True);frame.to_parquet(d/'FEATURES.parquet',index=False)
  p,status=match(frame);neutral=frame.copy();neutral['pvr']=0.;pn,_=match(neutral);assert list(p.pair_id)==list(pn.pair_id)
  prefixes=[]
  cuts=['2022-06-30','2022-09-30'] if win=='2022' else ['2025-12-31','2026-03-31']
  for cut in cuts:
   ps,_=match(frame[frame.date<=pd.Timestamp(cut)]);full=p[p.date<=cut].reset_index(drop=True);assert list(ps.pair_id)==list(full.pair_id);prefixes.append(dict(cut=cut,pairs=len(ps)))
  p.to_parquet(d/'PAIRS_PRE_OUTCOMES.parquet',index=False);status.to_parquet(d/'UNMATCHED_STATUS.parquet',index=False)
  ready=frame[frame.feature_ready];matched=set(status.loc[status.reason=='matched_today','known_id']);mr=[r for r in rs if r['known_id'] in matched];ur=[r for r in rs if r['known_id'] not in matched]
  result[win]=dict(mother_events=len(rs),ready_events=len(ready),feature_unknown_counts=dict(collections.Counter(q for r in rs for q in r['unknown_reasons'])),pairs=len(p),pair_dates=p.date.nunique(),pair_stocks=len(set(p.h1_symbol)|set(p.other_symbol)),pair_industries=p.sector.nunique(),kinds=dict(collections.Counter(p.pair_kind)),status=dict(collections.Counter(status.reason)),matched_distributions=describe(mr),unmatched_distributions=describe(ur),prefix_checks=prefixes,PVR_neutral_pair_IDs_exact=True)
  matchids[win]=list(p.pair_id);statuses[win]=status;allpairs[win]=p
 save('PAIR_ID_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),contract_sha256=sha(O/'CONTRACT.txt'),pair_ids=matchids,before_any_new_pair_label_join=True,feature_outcome_columns=[],new_account_paths=0))
 save('COVERAGE_PRE_OUTCOMES.json',clean(result));print('PAIR_COVERAGE',json.dumps({w:{k:v for k,v in r.items() if k not in ['matched_distributions','unmatched_distributions']} for w,r in result.items()},ensure_ascii=False,default=str),flush=True)
 # Read existing label availability metadata ONLY; never access return/MAE/MFE/tail values.
 labelready={}
 for win in WINDOWS:
  ks={(r['sid'],r['day'],r['receipt']) for r in data[win]};got=set();cnt=collections.Counter();end=collections.defaultdict(list)
  for x in rows(OLD/win/'PRICE_LABELS.jsonl.gz'):
   key=x['sid'],x['day'],x['receipt'];assert key in ks;got.add(key)
   for h in ['21','63']:
    y=x['labels'][h];cnt[h+':'+('valid' if y['valid'] else y['reason'])]+=1
    if y['valid']:end[h].append(y['end_day'])
  assert got==ks;labelready[win]=dict(exact_candidate_identity=True,events=len(ks),availability=dict(cnt),latest_endpoint={h:max(ds) for h,ds in end.items()},outcome_value_fields_accessed=False)
 save('LABEL_REUSE_READINESS.json',labelready)
 # Funding data are joined only AFTER blind pair-ID freeze. Counts are potential context, never substitution proof.
 capital={}
 for win,rs in data.items():
  daily=list(rows(ROOTS[win]/'daily.jsonl.gz'));cal=[x['at'][:10] for x in daily];nextday=dict(zip(cal,cal[1:]));on={x['at'][:10]:x['on'] for x in daily};fund=list(rows(ROOTS[win]/'funding.jsonl.gz'));fm=collections.defaultdict(list);before={};prev=collections.defaultdict(list)
  for x in fund:
   at=x['at'];d=at[:10];fm[x['sid'],d].append(x)
   if '09:30:00' in at:
    before[id(x)]=list(prev[d])
    if x['result']=='reserved':prev[d].append(dict(sid=x['sid'],sector=META[x['sid']]['sector_id'],role=x['role'],pool=x.get('pool'),shares=x.get('shares')))
  counts=collections.Counter();detail=[]
  for r in rs:
   key=r['sid'],r['day'],r['receipt'];op=opmaps[win][key];n=nextday.get(r['day']);oo=fm[r['sid'],n] if n else [];close=fm[r['sid'],r['day']];mobile=[x for x in oo if x['role']=='mobile'];core_reserved=any(x['role']=='core' and x['result']=='reserved' for x in oo)
   counts['ACT_paused' if not on[r['day']] else 'ACT_on']+=1;counts['already_held' if op['held'] else 'not_held']+=1;counts['core_role_same_stock' if 'core' in op['roles'] else 'no_core_role_same_stock']+=1
   if core_reserved and not mobile:counts['core_reserved_suppressed_mobile']+=1
   for b in op['barriers']:counts['asof_barrier:'+b]+=1
   for x in mobile:
    counts['mobile_result:'+x['result']]+=1
    if any(k in x['result'] for k in ['pool_capital','probe_risk','sector_risk','sector_capital','cash','confirmed_unfunded']):
     earlier=before.get(id(x),[]);cross=[z for z in earlier if z['sector']!=r['sector']];same=[z for z in earlier if z['sector']==r['sector']]
     counts['resource_rejection_receipts']+=1;counts['resource_rejection_with_earlier_NEW_order']+=bool(earlier);counts['resource_rejection_with_cross_industry_NEW_order']+=bool(cross);counts['resource_rejection_with_same_industry_NEW_order']+=bool(same)
     detail.append(dict(sid=r['sid'],day=r['day'],receipt=r['receipt'],opening=n,raw_reason=x['result'],earlier_actual_NEW_reservations=earlier,only_potential_competition_not_substitution_proof=True))
  capital[win]=dict(events=len(rs),flags_and_raw_reasons=dict(counts),classification_nonexclusive=True,validated_fixed_state_one_order_substitutions=0,exact_state_scope='three existing SC target projections only, strong window; none in2022; not a full restored Account',unknown='most opens lack frozen pre-route full resources/fees/pending/stock ownership; original daily+funding are enough for raw reason/prior new-order presence, not causal replacement')
  save(win+'/POTENTIAL_COMPETITION.json',detail)
 save('CAPITAL_CHAIN_READINESS.json',capital)
 save('INPUT_SHA256.json',INPUT)
 save('READINESS.json',dict(ready_for_contract_coverage_review=True,active_contract=freeze['version'],new_paired_outcomes_read=False,new_pair_label_joins=0,new_account_paths=0,new_execution_paths=0,prepared_original_score_stocks=len(ids),paired_counts={w:r['pairs'] for w,r in result.items()},capital_actionability_proven=False,seconds=time.monotonic()-begun))
 print('DONE_PRE_OUTCOMES',round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
