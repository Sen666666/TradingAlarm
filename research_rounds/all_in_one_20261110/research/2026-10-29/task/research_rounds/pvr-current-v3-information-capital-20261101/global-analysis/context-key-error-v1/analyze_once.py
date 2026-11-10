"""Global diagnostic only. Rank freeze precedes label access; no account imports."""
from pathlib import Path
from datetime import datetime,timezone
import ast,textwrap,json,gzip,hashlib,collections,time,math,traceback
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent;OLD=W/'opportunity-quality-ranking-20261031'
ROOTS={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair','2025_26':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
LO={'2022':'2022-01-01','2025_26':'2025-07-01'}
SRC={};LABELS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def stream(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def parquet(n,f):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');f.to_parquet(t,index=False);t.replace(p)
def k(r):return r['sid'],r['day'],r['receipt']
def old_function(name,env):
 path=OLD/'label_and_summarize.py';s=path.read_text();SRC[str(path)]=sha(path);n=next(x for x in ast.walk(ast.parse(s)) if isinstance(x,ast.FunctionDef) and x.name==name);s=textwrap.dedent('\n'.join(s.splitlines()[n.lineno-1:n.end_lineno]))+'\n';exec(compile(s,str(path),'exec'),env);(O/f'original_{name}_function.py').write_text(s);return env[name]

def assign(rows,metric):
 out={};by=collections.defaultdict(list)
 for r in rows:by[r['day']].append(r)
 for day,rs in sorted(by.items()):
  ordered=sorted(rs,key=lambda r:(-r['H1'] if metric=='H1' else -r['PVR'],r['sid']))
  for q,indices in enumerate(np.array_split(np.arange(len(ordered)),5),1):
   for i in indices:out[k(ordered[int(i)])]=(int(i)+1,q)
 return out

def prepare_ranks():
 mother={};common={};gate=[];discordance={};coverage={}
 for win in ROOTS:
  dn=read(OLD/win/'DENOMINATORS.json');path=OLD/win/'CANDIDATES.jsonl.gz';assert sha(path)==dn['candidate_file_SHA256']
  fpath=P/win/'FEATURES.parquet';SRC[str(fpath)]=sha(fpath);f=pd.read_parquet(fpath);ff={(r.symbol,str(r.date.date()),r.receipt):r for r in f.itertuples()};rs=[]
  for raw in stream(path):
   # Market fields only. Actual-funding flags remain outside ranks.
   r={z:raw[z] for z in ['sid','day','receipt','sector','industry_attempt','industry_stage','attempt_inherited','first_stock_attempt_in_window','first_complete_attempt','H1','original_global_rank','quintile']};z=ff[k(r)];r.update(PVR=float(np.round(z.pvr_raw,12)) if np.isfinite(z.pvr_raw) else None,age=float(z.age) if np.isfinite(z.age) else None,runup=float(z.runup) if np.isfinite(z.runup) else None,scale=float(z.scale) if np.isfinite(z.scale) else None,I_start=z.i_start,I_inherited=bool(z.i_start and z.i_start<LO[win]),window=win)
   r['common_ready']=r['PVR'] is not None and np.isfinite(r['H1']);rs.append(r)
  baseline=assign(rs,'H1');assert all(baseline[k(r)][1]==r['quintile'] for r in rs),'old H1 group identity'
  ready=[r for r in rs if r['common_ready']];hh=assign(ready,'H1');pp=assign(ready,'PVR')
  for r in ready:r.update(rank_H1=hh[k(r)][0],Q_H1=hh[k(r)][1],rank_PVR=pp[k(r)][0],Q_PVR=pp[k(r)][1])
  for cut in (['2022-06-30','2022-09-30'] if win=='2022' else ['2025-12-31','2026-03-31']):
   sub=[r for r in ready if r['day']<=cut]
   assert assign(sub,'H1')=={k(r):hh[k(r)] for r in sub};assert assign(sub,'PVR')=={k(r):pp[k(r)] for r in sub}
  ds=[];by=collections.defaultdict(list)
  for r in ready:by[r['day']].append(r)
  for day,zs in sorted(by.items()):
   a=np.array([z['rank_H1'] for z in zs],float);b=np.array([z['rank_PVR'] for z in zs],float);n=len(zs);hq={z['sid'] for z in zs if z['Q_H1']==1};pq={z['sid'] for z in zs if z['Q_PVR']==1};tr=collections.Counter(z['PVR'] for z in zs);trans=collections.Counter(f"{z['Q_H1']}->{z['Q_PVR']}" for z in zs)
   ds.append(dict(day=day,N=n,spearman_ordinal=float(np.corrcoef(a,b)[0,1]) if n>1 else None,normalized_rank_displacement=float(np.abs(a-b).mean()/(n-1)) if n>1 else None,Q1_overlap=len(hq&pq),Q1_size=len(hq),Q1_overlap_fraction=len(hq&pq)/len(hq),PVR_only=len(pq-hq),H1_only=len(hq-pq),PVR_tied_events=sum(v for v in tr.values() if v>1),transition=dict(trans)))
  mother[win]=rs;common[win]=ready;parquet(f'{win}/MOTHER_READINESS.parquet',pd.DataFrame(rs));parquet(f'{win}/COMMON_RANKS.parquet',pd.DataFrame(ready));save(f'{win}/DISCORDANCE.json',ds)
  coverage[win]=dict(full_mother=len(rs),common_support=len(ready),PVR_NA=len(rs)-len(ready),H1_whole_mother_identity=True,inherited_I_common=sum(r['I_inherited'] for r in ready),inherited_industry_attempt_common=sum(r['attempt_inherited'] for r in ready),age_unknown_retained=sum(r['age'] is None for r in ready),candidate_dates=len(by),dates_N_under5=sum(x['N']<5 for x in ds),Q1_exclusive_events_each=sum(x['PVR_only'] for x in ds),Q1_disagreement_dates=sum(x['PVR_only']>0 for x in ds),mean_date_Q1_overlap=float(np.mean([x['Q1_overlap_fraction'] for x in ds])),mean_date_spearman=float(np.mean([x['spearman_ordinal'] for x in ds if x['spearman_ordinal'] is not None])),mean_date_rank_displacement=float(np.mean([x['normalized_rank_displacement'] for x in ds if x['normalized_rank_displacement'] is not None])))
  gate.append(dict(window=win,old_H1_groups_exact=True,H1_PVR_identical_common_keys=True,four_rank_prefixes_exact=True,no_age_anchor_exclusion=True))
 # Genuine tie convention: a constant PVR is code order, not H1 identity.
 fixture=[dict(sid='B',day='2022-01-05',receipt='b',H1=90,PVR=50),dict(sid='A',day='2022-01-05',receipt='a',H1=10,PVR=50)]
 assert assign(fixture,'H1')[k(fixture[0])][0]==1 and assign(fixture,'PVR')[k(fixture[1])][0]==1
 save('RANK_GATE.json',dict(passed=True,checks=gate,constant_PVR_tie_is_code_order=True,labels_not_yet_accessed=True))
 save('RANK_COVERAGE.json',coverage)
 save('GLOBAL_RANK_FREEZE.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),contract_sha256=sha(O/'GLOBAL_CONTRACT.txt'),code_sha256=sha(Path(__file__)),ranks_sha256={win:sha(O/win/'COMMON_RANKS.parquet') for win in ROOTS},before_new_label_value_access=True,source_SHA256=SRC))
 print('GLOBAL_RANKS_FROZEN',coverage,flush=True)
 return mother,common

def days_pair(a,b,days):
 dd=sorted(set(a['daily'])&set(b['daily'])&set(days));delta=[a['daily'][d]['mean_pct']-b['daily'][d]['mean_pct'] for d in dd]
 return dict(common_dates=len(dd),left_date_equal_mean_pct=float(np.mean([a['daily'][d]['mean_pct'] for d in dd])) if dd else None,right_date_equal_mean_pct=float(np.mean([b['daily'][d]['mean_pct'] for d in dd])) if dd else None,mean_same_day_difference_pct=float(np.mean(delta)) if dd else None,median_same_day_difference_pct=float(np.median(delta)) if dd else None,days_left_mean_higher_fraction=float(np.mean(np.array(delta)>0)) if dd else None)
def compact(s):return {k:v for k,v in s.items() if k!='daily'}

def weighted_cdf(win,rs,h,days,metric,q):
 pts=[];D=len(days)
 if not D:return []
 by=collections.defaultdict(list)
 for r in rs:
  z=LABELS[win,*k(r)][str(h)]
  if r['day'] in days and z['valid']:by[r['day']].append(z)
 for field in ['return_pct','MAE_pct','MFE_pct']:
  a=[]
  for day,zs in by.items():
   for z in zs:a.append((z[field],1/(D*len(zs))))
  a.sort();total=0.
  for value,weight in a:total+=weight;pts.append(dict(ranking=metric,quintile=q,field=field,value=value,cumulative_weight=min(1.,total)))
 return pts

def tail_capture(win,rows,selected,h,days):
 by=collections.defaultdict(list);sel={k(r) for r in selected};alltail=selectedtail=0;shares=[];endnegative=0;stocks=set();attempts=set()
 for r in rows:
  if r['day'] in days:by[r['day']].append(r)
 for d,rs in by.items():
  tails=[r for r in rs if LABELS[win,*k(r)][str(h)]['valid'] and LABELS[win,*k(r)][str(h)]['right_tail_MFE30']];chosen=[r for r in tails if k(r) in sel];alltail+=len(tails);selectedtail+=len(chosen)
  if tails:shares.append(len(chosen)/len(tails))
  for r in chosen:
   stocks.add(r['sid']);attempts.add((r['sid'],r['industry_attempt']));endnegative+=LABELS[win,*k(r)][str(h)]['return_pct']<0
 return dict(mother_tail_events=alltail,selected_tail_events=selectedtail,event_tail_capture=selectedtail/alltail if alltail else None,date_equal_capture_on_tail_dates=float(np.mean(shares)) if shares else None,tail_dates=len(shares),tail_stocks=len(stocks),tail_stock_attempts=len(attempts),selected_MFE30_but_negative_endpoint=endnegative)

def concentration(win,rows,h,days,delta):
 by=collections.defaultdict(list)
 for r in rows:
  if r['day'] in days:by[r['day']].append(r)
 stock=collections.defaultdict(float);date={};D=len(days)
 for d,rs in by.items():
  hh=[r for r in rs if r['Q_H1']==1 and LABELS[win,*k(r)][str(h)]['valid']];pp=[r for r in rs if r['Q_PVR']==1 and LABELS[win,*k(r)][str(h)]['valid']];x=0.
  for sign,zs in [(-1,hh),(1,pp)]:
   for r in zs:
    v=sign*LABELS[win,*k(r)][str(h)]['return_pct']/len(zs)/D;stock[r['sid']]+=v;x+=v
  date[d]=x
 assert delta is None or abs(sum(stock.values())-delta)<1e-9,'price-mean difference decomposition'
 def top(items):
  p=sorted([(k,v) for k,v in items.items() if v>0],key=lambda x:-x[1]);n=sorted([(k,v) for k,v in items.items() if v<0],key=lambda x:x[1]);pos=sum(v for k,v in p);neg=sum(v for k,v in n)
  return dict(positive_sum=pos,negative_sum=neg,net=sum(items.values()),top5_positive=p[:5],top5_negative=n[:5],top5_positive_share=sum(v for k,v in p[:5])/pos if pos else None,top5_negative_share=sum(v for k,v in n[:5])/neg if neg else None)
 return dict(unit='algebraic percentage-point contribution to date-equal endpoint price mean; not money/PnL',stocks=top(stock),dates=top(date))

def load_context(win,rs):
 # Original funding and contribution facts only; called after ranks are frozen.
 raw=list(stream(OLD/win/'CANDIDATES.jsonl.gz'));actual={k(r):r['B_diag'] for r in raw};keys={k(r) for r in rs};ops={}
 for r in stream(ROOTS[win]/'opportunities.jsonl.gz'):
  kk=r['sid'],r['day'],r['CP1_id']
  if kk in keys:ops[kk]=r
 ds={r['at'][:10]:r['on'] for r in stream(ROOTS[win]/'daily.jsonl.gz')};dates=list(ds);nxt=dict(zip(dates,dates[1:]));fm=collections.defaultdict(list)
 for r in stream(ROOTS[win]/'funding.jsonl.gz'):fm[r['sid'],r['at'][:10]].append(r)
 ctx={}
 for r in rs:
  kk=k(r);op=ops[kk];nd=nxt.get(r['day']);oo=[x for x in fm[r['sid'],nd] if '09:30:00' in x['at']] if nd else [];mm=[x for x in oo if x['role']=='mobile'];core=any(x['role']=='core' and x['result']=='reserved' for x in oo);close=[x for x in fm[r['sid'],r['day']] if x['role']=='mobile' and '15:10:00' in x['at']];assert len(mm)<=1
  if not ds[r['day']]:stage='ACT_paused'
  elif op['barriers']:stage='authorization_barrier:'+','.join(op['barriers'])
  elif close:stage='authorization_size:'+close[0]['result']
  elif not nd:stage='right_boundary'
  elif core and not mm:stage='core_reserved_suppresses_mobile'
  elif mm:stage='opening:'+mm[0]['result']
  else:stage='unknown'
  ctx[kk]=dict(ACT_paused=not ds[r['day']],held=op['held'],core_role='core' in op['roles'],core_reserved=core,mobile_reserved=bool(mm and mm[0]['result']=='reserved'),stage=stage,**actual[kk])
 entries=read(W/'stage-progress-R-diagnostic-20261031'/win/'B_diag/ENTRIES.json');contrib=collections.defaultdict(list)
 for x in entries:contrib[x['sid'],x['signal_day'],x['canonical_stock_receipt']].append(x)
 return ctx,contrib

def composition(win,rs,ctx,contrib):
 def summarize(zs):
  ca=collections.Counter(ctx[k(r)]['stage'] for r in zs);industry=collections.Counter(r['sector'] for r in zs);stage=collections.Counter(r['industry_stage'] for r in zs);age=[r['age'] for r in zs if r['age'] is not None];progress=[r['runup'] for r in zs if r['runup'] is not None];es=[x for r in zs for x in contrib.get(k(r),[])];net=[(bool(x['closed']),float(x['net_contribution'])) for x in es]
  return dict(events=len(zs),stocks=len({r['sid'] for r in zs}),dates=len({r['day'] for r in zs}),ACT_paused=sum(ctx[k(r)]['ACT_paused'] for r in zs),held=sum(ctx[k(r)]['held'] for r in zs),core_role=sum(ctx[k(r)]['core_role'] for r in zs),industry_stage=dict(stage),industry_counts=dict(industry),I_inherited=sum(r['I_inherited'] for r in zs),industry_attempt_inherited=sum(r['attempt_inherited'] for r in zs),age_known=len(age),age_unknown=len(zs)-len(age),age_median=float(np.median(age)) if age else None,progress_known=len(progress),progress_median=float(np.median(progress)) if progress else None,mobile_reserved=sum(ctx[k(r)]['mobile_reserved'] for r in zs),actual_confirmed_fill_receipts=sum(ctx[k(r)]['selected'] for r in zs),actual_probe_fill_receipts=sum(ctx[k(r)]['probe_mobile_funded'] for r in zs),same_stock_core_fill=sum(ctx[k(r)]['same_stock_core_funded'] for r in zs),raw_funnel=dict(ca),actual_original_confirmed_layers=dict(layers=len(es),buy_cash=sum(float(x['actual_buy_cash']) for x in es),closed_positive=sum(v for c,v in net if c and v>0),closed_negative=sum(v for c,v in net if c and v<0),open_contribution=sum(v for c,v in net if not c),not_alternative_policy_profit=True))
 out={m:{str(q):summarize([r for r in rs if r['Q_'+m]==q]) for q in range(1,6)} for m in ['H1','PVR']}
 out['Q1_sets']={name:summarize([r for r in rs if predicate(r)]) for name,predicate in [('intersection',lambda r:r['Q_H1']==r['Q_PVR']==1),('H1_only',lambda r:r['Q_H1']==1 and r['Q_PVR']!=1),('PVR_only',lambda r:r['Q_PVR']==1 and r['Q_H1']!=1)]}
 out['rank_direction']={name:summarize([r for r in rs if np.sign(r['rank_PVR']-r['rank_H1'])==sign]) for name,sign in [('promoted',-1),('unchanged',0),('demoted',1)]}
 # No new state restoration. Check only original prior-order presence/order inversion.
 lookup={(r['sid'],r['day']):r for r in rs};counts=collections.Counter();events=[]
 for e in read(P/win/'POTENTIAL_COMPETITION.json'):
  r=lookup.get((e['sid'],e['day']))
  if r is None:continue
  prior=e['earlier_actual_NEW_reservations'];scored=[];external=[]
  for x in prior:
   z=lookup.get((x['sid'],e['day']))
   if z:scored.append((x,z))
   else:external.append(x)
  inversion=[dict(sid=x['sid'],pool=x['pool'],same_industry=x['sector']==r['sector'],rank_H1=z['rank_H1'],rank_PVR=z['rank_PVR']) for x,z in scored if r['rank_PVR']<z['rank_PVR']]
  counts['resource_rejected_common_receipts']+=1;counts['with_scored_prior_NEW']+=bool(scored);counts['with_external_unscored_prior_NEW']+=bool(external);counts['with_PVR_order_inversion_background']+=bool(inversion);counts['with_cross_industry_inversion_background']+=any(not x['same_industry'] for x in inversion)
  if inversion:events.append(dict(sid=r['sid'],day=r['day'],receipt=r['receipt'],rank_H1=r['rank_H1'],rank_PVR=r['rank_PVR'],raw_reason=e['raw_reason'],earlier_orders_inverted=inversion,exact_swappability_proven=False))
 save(win+'/ORDER_INVERSION_CONTEXT.json',events);out['ordering_context']=dict(counts=dict(counts),validated_one_order_substitutions=0,warning='potential inversions in scored market-qualifiedCP1 cohort only; external core-only unscored; no executable capital/PnL claim')
 return out

def conditional(win):
 path=P/win/'PAIRS_PRE_OUTCOMES.parquet';SRC[str(path)]=sha(path);pairs=pd.read_parquet(path);f=pd.read_parquet(P/win/'FEATURES.parquet');keys={(r.symbol,str(r.date.date())):(r.symbol,str(r.date.date()),r.receipt) for r in f.itertuples()};result={};records=[]
 for h in [21,63]:
  good=[]
  for p in pairs.itertuples():
   hkey=keys[p.h1_symbol,p.date];pkey=keys[p.pvr_choice_symbol,p.date];a=LABELS[win,*hkey][str(h)];b=LABELS[win,*pkey][str(h)];ok=a['valid'] and b['valid'];r=dict(pair_id=p.pair_id,day=p.date,kind=p.pair_kind,horizon=h,H1_sid=hkey[0],PVR_sid=pkey[0],valid=ok,delta_return_pct=b['return_pct']-a['return_pct'] if ok else None,H1_return_pct=a['return_pct'] if ok else None,PVR_return_pct=b['return_pct'] if ok else None,delta_MFE_pct=b['MFE_pct']-a['MFE_pct'] if ok else None,H1_MFE30=a['right_tail_MFE30'] if ok else None,PVR_MFE30=b['right_tail_MFE30'] if ok else None);records.append(r)
   if ok:good.append(r)
  def agg(zs):
   by=collections.defaultdict(list)
   for r in zs:by[r['day']].append(r['delta_return_pct'])
   return dict(pairs=len(zs),dates=len(by),pair_equal_delta=float(np.mean([r['delta_return_pct'] for r in zs])) if zs else None,date_equal_delta=float(np.mean([np.mean(v) for v in by.values()])) if by else None,H1_mean=float(np.mean([r['H1_return_pct'] for r in zs])) if zs else None,PVR_mean=float(np.mean([r['PVR_return_pct'] for r in zs])) if zs else None,H1_tail_frequency=float(np.mean([r['H1_MFE30'] for r in zs])) if zs else None,PVR_tail_frequency=float(np.mean([r['PVR_MFE30'] for r in zs])) if zs else None)
  result[str(h)]=dict(all_registered=agg(good),conflicts=agg([r for r in good if r['kind']=='conflict']),unavailable_pairs=len(pairs)-len(good))
 parquet(win+'/CONDITIONAL_PAIR_LABELS.parquet',pd.DataFrame(records));return result

def main():
 begun=time.monotonic();fr=read(O/'GLOBAL_CONTRACT_FREEZE.json');assert sha(O/'GLOBAL_CONTRACT.txt')==fr['contract_sha256']
 for n,h in fr['protected_conditional'].items():assert sha(P/n)==h
 save('RUN_SOURCE_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),code_sha256=sha(Path(__file__)),contract_sha256=fr['contract_sha256'],before_rank_and_label_analysis=True,economic_paths=0))
 mother,common=prepare_ranks()
 # Only now may frozen label values enter statistics.
 for win in ROOTS:
  for x in stream(OLD/win/'PRICE_LABELS.jsonl.gz'):LABELS[win,*k(x)]=x['labels']
 env=dict(np=np,pd=pd,collections=collections,labels=LABELS);stats=old_function('stats',env);paired=old_function('paired',env)
 allsummary=[];mains={};contexts={};cond={}
 for win,rs in common.items():
  ctx,contrib=load_context(win,rs);contexts[win]=composition(win,rs,ctx,contrib);save(win+'/COMPOSITION_AND_FUNNEL.json',contexts[win])
  labelled=[]
  for r in rs:
   for h in [21,63]:labelled.append(dict(**r,horizon=h,**LABELS[win,*k(r)][str(h)]))
  parquet(win+'/LABEL_EVENTS_USED.parquet',pd.DataFrame(labelled))
  for variant,predicate in [('all_events',lambda r:True),('first_stock_attempt_within_window',lambda r:r['first_stock_attempt_in_window']),('attempt_started_in_window_first',lambda r:r['first_complete_attempt'])]:
   vv=[r for r in rs if predicate(r)]
   for h in [21,63]:
    group={m:{str(q):stats(win,[r for r in vv if r['Q_'+m]==q],h) for q in range(1,6)} for m in ['H1','PVR']};ds=set.intersection(*(set(s['daily']) for m in group.values() for s in m.values()));qdiff={q:days_pair(group['PVR'][q],group['H1'][q],ds) for q in ['1','2','3','4','5']}
    qq={name:stats(win,[r for r in vv if predicate_set(r)],h) for name,predicate_set in [('intersection',lambda r:r['Q_H1']==r['Q_PVR']==1),('H1_only',lambda r:r['Q_H1']==1 and r['Q_PVR']!=1),('PVR_only',lambda r:r['Q_PVR']==1 and r['Q_H1']!=1)]}
    exclusive=days_pair(qq['PVR_only'],qq['H1_only'],ds);curve={m:{q:dict(dates=len(ds),date_equal_mean=float(np.mean([s['daily'][d]['mean_pct'] for d in ds])) if ds else None,date_equal_positive_fraction=float(np.mean([s['daily'][d]['positive_fraction'] for d in ds])) if ds else None,date_equal_MFE30_frequency=float(np.mean([s['daily'][d]['right_tail_fraction'] for d in ds])) if ds else None,all_group_days_original_stats=compact(s)) for q,s in group[m].items()} for m in group}
    tails={m:tail_capture(win,vv,[r for r in vv if r['Q_'+m]==1],h,ds) for m in group};cdf=[]
    for m in group:
     for q in range(1,6):cdf+=weighted_cdf(win,[r for r in vv if r['Q_'+m]==q],h,ds,m,q)
    parquet(f'{win}/{variant}/CDF_{h}.parquet',pd.DataFrame(cdf))
    out=dict(window=win,variant=variant,horizon=h,events=len(vv),all_five_common_dates=len(ds),common_days=sorted(ds),five_band_curves=curve,PVR_minus_H1_by_band=qdiff,original_single_band_common_day_top=paired(group['PVR']['1'],group['H1']['1']),exclusive_sets={name:compact(s) for name,s in qq.items()},PVR_only_minus_H1_only=exclusive,Q1_minus_Q5={m:paired(group[m]['1'],group[m]['5']) for m in group},top_tail_capture=tails)
    if variant=='all_events':out['top_delta_concentration']=concentration(win,vv,h,ds,qdiff['1']['mean_same_day_difference_pct']);mains[win,str(h)]=out
    save(f'{win}/{variant}/SUMMARY_{h}.json',out);allsummary.append(out)
    if variant=='all_events':print('GLOBAL_MAIN',win,h,'days',len(ds),'H1/PVR',[curve[m]['1']['date_equal_mean'] for m in ['H1','PVR']],'delta',qdiff['1']['mean_same_day_difference_pct'],'exclusive',exclusive['mean_same_day_difference_pct'],'tail',[tails[m]['date_equal_capture_on_tail_dates'] for m in ['H1','PVR']],flush=True)
  cond[win]=conditional(win);save(win+'/CONDITIONAL_SEPARATE.json',cond[win]);print('CONDITIONAL',win,cond[win],flush=True)
 # Predeclared primary-direction decision; no year/horizon fitting.
 directions={win:dict(Q1_21=mains[win,'21']['PVR_minus_H1_by_band']['1']['mean_same_day_difference_pct'],exclusive_21=mains[win,'21']['PVR_only_minus_H1_only']['mean_same_day_difference_pct'],Q1_63=mains[win,'63']['PVR_minus_H1_by_band']['1']['mean_same_day_difference_pct'],exclusive_63=mains[win,'63']['PVR_only_minus_H1_only']['mean_same_day_difference_pct']) for win in ROOTS}
 supports=all(v['Q1_21'] is not None and v['Q1_21']>0 and v['exclusive_21'] is not None and v['exclusive_21']>0 for v in directions.values());secondary=all(v['Q1_63'] is not None and v['Q1_63']>=0 and v['exclusive_63'] is not None and v['exclusive_63']>=0 for v in directions.values())
 recommendation='candidate_for_ONE_native_order_only_trial_review' if supports and secondary else 'STOP_current_unconditional_global_PVR_priority_candidate'
 save('DECISION.json',dict(recommendation=recommendation,primary_two_window_support=supports,secondary_direction_support=secondary,directions=directions,not_a_year_switch=True,conditional_cannot_rescue_global=True,policy_or_live_promotion=False,economic_paths=0))
 for n,h in fr['protected_conditional'].items():assert sha(P/n)==h
 save('SUMMARY_ALL.json',allsummary);save('SOURCE_SHA256.json',SRC);save('COMPLETION.json',dict(passed=True,seconds=time.monotonic()-begun,rank_freeze_before_label_access=True,protected_conditional_exact=True,new_account_paths=0,new_model_coefficients=0,new_state_restorations=0,paired_outcomes_calculated_once=True,source_code_sha256=sha(Path(__file__))))
 print('DONE_GLOBAL_DIAGNOSTIC',round(time.monotonic()-begun,2),recommendation,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),traceback=traceback.format_exc(),economic_paths=0));raise
