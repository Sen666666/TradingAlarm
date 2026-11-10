"""One fixed rank-change description. Saved logs/cache only, no finance import."""
from pathlib import Path
from collections import defaultdict
import json,gzip,hashlib,math,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=W/'g-s-C-month-continuation-20261102';FACT=P/'market-permission-price-only-20261101/industry-evidence-ranking-readonly-v1'
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
LABEL=W/'opportunity-quality-ranking-20261031';READS={};CASES={'2022Jan':('2022','2022-01-04','2022-01-28'),'2025Jul':('2025_26','2025-07-01','2025-07-31')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);h=sha(p);assert not expected or h==expected,(p,'hash');assert str(p) not in READS or READS[str(p)]==h;READS[str(p)]=h;return p
def read(p,expected=None):return json.loads(bind(p,expected).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load_parts(root,m,name):
 refs=[m['files'].get(name),m.get('extensions',{}).get(name),m.get('month_extension',{}).get(name)];out=[]
 for ref in refs:
  if ref:
   p=bind(root/ref['path'],ref['sha256']);out.append(pd.read_parquet(p) if p.suffix=='.parquet' else json.loads(p.read_text()))
 return out
def mean(x):
 z=[float(v) for v in x if v is not None and pd.notna(v)];return float(np.mean(z)) if z else None
def rank_order(scores,sectors):return sorted(sectors,key=lambda s:(-round(float(scores[s]),12),s))
def corr(a,b):
 x=pd.Series(a).rank(method='average');y=pd.Series(b).rank(method='average')
 return float(np.corrcoef(x,y)[0,1]) if len(x)>1 and x.nunique()>1 and y.nunique()>1 else None
def main():
 started=time.monotonic();protocol=dict(windows=CASES,lookback=21,improvement='rank_at_previous21_valid_original_H1_market_observation minus current_rank; higher improves; source change or missing makes UNKNOWN',rank_A='original cached H1 descending rounded12, sector ID tie',rank_B='rank improvement descending, sector ID tie; no composite or TopK',row_weight='one industry per decision day; stock label means formed inside industry/day, then industry/day and date equal summaries separately',universe_M1='fresh canonical CP1 and original retained stock_Q true; unallocated kept',universe_M2='same M1 stock actually present in original C10 requested projection trace, including Q=0; F1/ACT/obligation stage distinct from capital allocation',holdings='all originally occupied industries shown even without fresh; no exit inference',future_industry_21_63='UNKNOWN: existing frozen industry evaluation windows omit Jan2022 and Jul2025; no new industry future label computed',future_stock_proxy='reuse existing 21/63 legacy-Q-reference canonical stock price labels when key matches, report absent label coverage',existing_tail='original stock close MFE>=30%, no new threshold',no_account_events=True,no_signal_recompute=True,no_window_search=True)
 save('PROTOCOL.json',protocol)
 sourcehash=read(FACT/'SOURCE_SHA256.json');bind(H1,sourcehash[str(H1)]);z=np.load(H1,allow_pickle=False);dates=pd.DatetimeIndex(z['dates']);syms=list(map(str,z['symbols']));sectors=sorted(s for s in syms if s.startswith('URFI'));assert len(sectors)==90;cols=[syms.index(s) for s in sectors]
 scores=z['score'][:,cols];prices=z['close'][:,cols];segments=z['segment'][:,cols];nref=z['nref'][:,cols]
 names=read(P/'C-2022-month-native-baseline-20261102/analysis/INDUSTRY_NAMES.json')['mapping'];assert set(names)==set(sectors)
 hrows={};ranks={};warmgate=[]
 for case,(win,start,end) in CASES.items():
  ix=np.where((dates>=start)&(dates<=end))[0];warm=np.arange(ix[0]-21,ix[-1]+1);assert np.isfinite(scores[warm]).all() and np.isfinite(prices[warm]).all() and (prices[warm]>0).all() and (nref[warm]==90).all()
  rank={}
  for t in warm:
   order=rank_order(dict(zip(sectors,scores[t])),sectors);rank[t]={s:j+1 for j,s in enumerate(order)}
  for t in ix:
   assert (segments[t-21:t+1]==segments[t]).all(),'source change: retain UNKNOWN rather than splice'
   for j,s in enumerate(sectors):hrows[case,str(dates[t].date()),s]=dict(case=case,day=str(dates[t].date()),sector=s,industry=names[s],H1_score=float(scores[t,j]),H1_rank90=rank[t][s],H1_nref=int(nref[t,j]),prior21_day=str(dates[t-21].date()),prior21_rank90=rank[t-21][s],rank_improvement21=rank[t-21][s]-rank[t][s],industry_close=float(prices[t,j]),industry_absolute_price_change21_pct=(float(prices[t,j])/float(prices[t-21,j])-1)*100,industry_future21=None,industry_future63=None,industry_future_label_status='UNKNOWN_existing_export_does_not_cover_month',source_row=int(t),prior_source_row=int(t-21))
  warmgate.append(dict(case=case,days=len(ix),rows=len(ix)*90,missing=0,reference90=True,prior_anchor=str(dates[ix[0]-21].date())))
  # Physical prefix arrays at fixed first/middle/last month dates; no future cells.
  tests=[]
  for t in [int(ix[0]),int(ix[len(ix)//2]),int(ix[-1])]:
   cut=scores[:t+1].copy();order=rank_order(dict(zip(sectors,cut[t])),sectors);prev=rank_order(dict(zip(sectors,cut[t-21])),sectors)
   assert all(order.index(s)+1==rank[t][s] and prev.index(s)+1==rank[t-21][s] for s in sectors)
   tests.append(str(dates[t].date()))
  ranks[case]=dict(days=[str(dates[t].date()) for t in ix],physical_prefix_dates=tests)
 save('H1_INPUT_GATE.json',warmgate)
 july_index=read(OLD/'july_end_analysis/ARTIFACT_SHA256.json');jp=OLD/'runs/2025_26-C10/2025-07-31-CLOSE.json';july=read(jp,july_index[str(jp.relative_to(OLD))]);jan=read(O/'JAN_C10_SAVED_LOGS.json');janproof=read(O/'JAN_EXTRACTION_CHECKS.json');assert janproof['passed'] and sha(O/'JAN_C10_SAVED_LOGS.json')==janproof['output_sha256']
 stockrows=[];allrows=[];readiness=[];actual_layers={}
 actual_layers['2022Jan']=read(P/'C-2022-month-difference-readonly-20261102/ALL_LAYERS.json')['C10']
 actual_layers['2025Jul']=read(OLD/'july_end_analysis/ALL_LAYERS.json')['2025_26-C10']
 for case,(win,start,end) in CASES.items():
  logs=jan if case=='2022Jan' else july;root=OLD/'inputs'/win;m=read(root/'MANIFEST.json');meta=read(root/'metadata.json',m['files']['metadata']['sha256']);receipts={}
  for rr in load_parts(root,m,'receipts'):
   for r in rr:
    if r['receipt_id'] in receipts:assert receipts[r['receipt_id']]==r
    receipts[r['receipt_id']]=r
  maps={v['at'][:10]:v for v in logs['mapping']};results={v['at'][:10]:v for v in logs['results'] if 'projection' in v};assert sorted(maps)==ranks[case]['days'] and sorted(results)==ranks[case]['days']
  events={e['at'][:10]:e for e in logs['events'] if e['phase']=='CLOSE'}
  if case=='2022Jan':
   sp=read(P/'C-2022-month-native-baseline-20261102/analysis/C10_JAN05_VERIFIED_REPORT_POINT.json');assert sp['passed'];events['2022-01-05']=dict(bridge=sp['balance'])
   raw=pd.concat(load_parts(root,m,'raw'),ignore_index=True);raw=raw.sort_values(['sid','day']).drop_duplicates(['sid','day'],keep='last');rawby={s:g.set_index('day').close for s,g in raw.groupby('sid')}
  july_daily={d['day']:d for d in read(OLD/'july_end_analysis/DAILY.json')['2025_26-C10']} if case=='2025Jul' else None
  for day in ranks[case]['days']:
   mp=maps[day];res=results[day]['projection'];traces={v['sid']:v for v in res['trace']};counts={s:defaultdict(int) for s in sectors};eligible={s:[] for s in sectors};requested={s:[] for s in sectors}
   for mm in mp['stocks']:
    sid=mm['sid'];sec=meta[sid]['sector'];rid=mm['CP1_id'];fresh=rid is not None
    if fresh:assert rid in receipts and receipts[rid]['confirmed_day']==day and receipts[rid]['canonical_series']==sid
    q=mm['stock_Q'];fq=fresh and q is True and mm['preliminary'] is True
    if fresh:counts[sec]['fresh']+=1;counts[sec]['Q_pass' if q is True else 'Q_unknown' if q is None else 'Q_false']+=1
    if fq:
     sr=dict(case=case,day=day,sid=sid,name=meta[sid]['name'],sector=sec,receipt=rid,C_requested=sid in traces,C_Q=traces[sid].get('q') if sid in traces else None,C_trace_bounds=traces[sid].get('blockers_or_necessary_bounds') if sid in traces else None)
     stockrows.append(sr);eligible[sec].append(sr)
     if sid in traces:requested[sec].append(sr)
   assert set(traces)<=set(z['sid'] for rs in eligible.values() for z in rs),'C requests must preserve canonical fresh/Q'
   cap=defaultdict(float)
   if july_daily:
    for v in july_daily[day]['industries']:cap[v['sector']]=float(v['capital'])
    nav=float(july_daily[day]['NAV'])
   else:
    bal=events[day]['bridge'];nav=float(bal['nav'])
    for sid,q in bal['quantities'].items():
     if q:
      pp=rawby[sid].loc[:day];assert len(pp) and np.isfinite(pp.iloc[-1]);cap[meta[sid]['sector']]+=int(q)*float(pp.iloc[-1])
    assert abs(sum(cap.values())-float(bal['inventory']))<1e-6
   H=res['C_rank_binding']['industry_H1']
   for sec,v in H.items():assert abs(float(v)-hrows[case,day,sec]['H1_score'])<1e-11
   actual=defaultdict(float);actualC=defaultdict(float)
   for l in actual_layers[case]:
    if l['signal_at'][:10]==day:
     contr=float(l['net'] if case=='2022Jan' else l['total_contribution']);actual[l['sector']]+=contr
     if l['role']=='mobile' and l['pool']=='confirmed':actualC[l['sector']]+=contr
   today=[]
   for sec in sectors:
    r=dict(hrows[case,day,sec],fresh_count=counts[sec]['fresh'],fresh_Q_pass=len(eligible[sec]),fresh_Q_false=counts[sec]['Q_false'],fresh_Q_unknown=counts[sec]['Q_unknown'],C_requested_count=len(requested[sec]),C_positive_plan_count=sum((z['C_Q'] or 0)>0 for z in requested[sec]),occupied_capital_C10=cap[sec],occupied_weight_C10=cap[sec]/nav,actual_C10_entry_contribution_to_month_end=actual[sec],actual_C10_confirmed_mobile_entry_contribution=actualC[sec])
    today.append(r)
   for family,col in [('M1','fresh_Q_pass'),('M2','C_requested_count')]:
    subset=[r for r in today if r[col]>0];A=sorted(subset,key=lambda r:r['H1_rank90']);B=sorted(subset,key=lambda r:(-r['rank_improvement21'],r['sector']));ar={r['sector']:i+1 for i,r in enumerate(A)};br={r['sector']:i+1 for i,r in enumerate(B)}
    for r in today:
     sec=r['sector'];r[family+'_A_rank']=ar.get(sec);r[family+'_B_rank']=br.get(sec);r[family+'_rank_group']='B_promoted' if sec in ar and br[sec]<ar[sec] else 'A_promoted' if sec in ar and ar[sec]<br[sec] else 'same' if sec in ar else 'outside'
   allrows.extend(today)
  part=[r for r in allrows if r['case']==case];ss=[r for r in stockrows if r['case']==case]
  readiness.append(dict(case=case,decisions=len(ranks[case]['days']),all_industry_days=len(part),fresh_stock_events=sum(r['fresh_count'] for r in part),fresh_Q_stock_events=len(ss),fresh_Q_industry_days=sum(r['fresh_Q_pass']>0 for r in part),C_requested_stock_events=sum(r['C_requested_count'] for r in part),C_requested_industry_days=sum(r['C_requested_count']>0 for r in part),occupied_industry_days=sum(r['occupied_capital_C10']>0 for r in part),C_positive_industry_days=sum(r['C_positive_plan_count']>0 for r in part)))
 save('RANKS_BEFORE_LABELS.json',allrows);ranksha=sha(O/'RANKS_BEFORE_LABELS.json');save('READINESS_FIRST.json',dict(H1=warmgate,opportunity=readiness,industry_future_labels='UNKNOWN',rank_before_labels_sha256=ranksha))
 print('READY',json.dumps(readiness),flush=True)
 # Existing labels are read only after complete rank/denominator table is saved.
 labelindex=read(LABEL/'FINAL_EVIDENCE.json')['SHA256'];labelmap={}
 for case,(win,start,end) in CASES.items():
  p=bind(LABEL/win/'PRICE_LABELS.jsonl.gz',labelindex[win+'/PRICE_LABELS.jsonl.gz'])
  with gzip.open(p,'rt') as f:
   for line in f:
    z=json.loads(line)
    if start<=z['day']<=end:labelmap[case,z['sid'],z['day'],z['receipt']]=z['labels']
 for sr in stockrows:sr['existing_stock_labels']=labelmap.get((sr['case'],sr['sid'],sr['day'],sr['receipt']));sr['label_source_domain']='legacy_Q_reference_stock_prices_subset; not industry future price'
 bykey=defaultdict(list)
 for sr in stockrows:bykey[sr['case'],sr['day'],sr['sector']].append(sr)
 for r in allrows:
  ss=bykey[r['case'],r['day'],r['sector']]
  for family in ['M1','M2']:
   cs=ss if family=='M1' else [s for s in ss if s['C_requested']]
   for h in ['21','63']:
    ls=[s['existing_stock_labels'][h] for s in cs if s['existing_stock_labels'] and s['existing_stock_labels'][h]['valid']]
    r[f'{family}_{h}_label_n']=len(ls);r[f'{family}_{h}_label_missing_n']=len(cs)-len(ls)
    for dest,src in [('return','return_pct'),('MAE','MAE_pct'),('MFE','MFE_pct'),('tail_share','right_tail_MFE30')]:r[f'{family}_{h}_{dest}']=mean([l[src] for l in ls])
 save('ALL_INDUSTRY_DAYS.json',allrows);save('ALL_FRESH_Q_STOCK_EVENTS.json',stockrows)
 stats=[];daycorr=[];concentration=[];loo=[]
 for case in CASES:
  for family,col in [('M1','fresh_Q_pass'),('M2','C_requested_count')]:
   rs=[r for r in allrows if r['case']==case and r[col]>0]
   for h in ['21','63']:
    covered=[r for r in rs if r[f'{family}_{h}_label_n']];suffix=f'{family}_{h}_';groups={g:[r for r in rs if r[family+'_rank_group']==g] for g in ['B_promoted','A_promoted','same']}
    for group,gg in dict(all=rs,**groups).items():
     valid=[r for r in gg if r[suffix+'label_n']];days=sorted({r['day'] for r in valid});de=mean([mean([r[suffix+'return'] for r in valid if r['day']==d]) for d in days])
     stats.append(dict(case=case,family=family,horizon=h,group=group,industry_days=len(gg),covered_industry_days=len(valid),fully_labelled_industry_days=sum(r[suffix+'label_missing_n']==0 for r in valid),stock_events=sum(r[col] for r in gg),labelled_stock_events=sum(r[suffix+'label_n'] for r in gg),industry_day_equal_mean_return=mean([r[suffix+'return'] for r in valid]),date_equal_mean_return=de,industry_day_mean_MAE=mean([r[suffix+'MAE'] for r in valid]),industry_day_mean_MFE=mean([r[suffix+'MFE'] for r in valid]),industry_day_mean_tail_share=mean([r[suffix+'tail_share'] for r in valid]),past21_absolute_industry_price_change_mean=mean([r['industry_absolute_price_change21_pct'] for r in gg]),past21_nonpositive_count=sum(r['industry_absolute_price_change21_pct']<=0 for r in gg)))
    for day in ranks[case]['days']:
     zz=[r for r in covered if r['day']==day];a=corr([-r['H1_rank90'] for r in zz],[r[suffix+'return'] for r in zz]);b=corr([r['rank_improvement21'] for r in zz],[r[suffix+'return'] for r in zz])
     daycorr.append(dict(case=case,family=family,horizon=h,day=day,covered_industries=len(zz),A_spearman=a,B_spearman=b,B_minus_A=b-a if a is not None and b is not None else None))
    if family=='M2':
     for group in ['B_promoted','A_promoted']:
      gg=[r for r in covered if r[family+'_rank_group']==group];pos=defaultdict(float)
      for r in gg:pos[r['sector']]+=max(0,r[suffix+'return'])
      den=sum(pos.values());best=max(pos,key=pos.get) if pos and den else None
      concentration.append(dict(case=case,horizon=h,group=group,positive_proxy_sum=den,largest_industry=names[best] if best else None,largest_positive_proxy_share=pos[best]/den if best else None,all_industry_positive_proxy=dict(pos)))
     for sec in sorted({r['sector'] for r in covered}):
      rem=[r for r in covered if r['sector']!=sec];v={g:mean([r[suffix+'return'] for r in rem if r[family+'_rank_group']==g]) for g in ['B_promoted','A_promoted']}
      loo.append(dict(case=case,horizon=h,omitted_industry=names[sec],B_promoted_minus_A_promoted=v['B_promoted']-v['A_promoted'] if all(x is not None for x in v.values()) else None))
 assert sha(O/'RANKS_BEFORE_LABELS.json')==ranksha
 save('PROXY_GROUP_STATS.json',stats);save('DAILY_RANK_CORRELATIONS.json',daycorr);save('PROXY_CONCENTRATION.json',concentration);save('ALL_INDUSTRY_LEAVE_ONE_OUT.json',loo)
 focussecs=['URFI881268','URFI881140','URFI881271','URFI881129'];save('FIXED_WINNER_AND_FAILURE_CONTROLS.json',[r for r in allrows if r['sector'] in focussecs])
 focusids={'300199.SZ','002373.SZ','001267.SZ'};save('NAMED_STOCK_CONTROLS.json',dict(opportunities=[s for s in stockrows if s['sid'] in focusids],actual_original_C10_layers={case:[l for l in ls if l['sid'] in focusids] for case,ls in actual_layers.items()}))
 save('PREFIX_CAUSAL_CHECKS.json',dict(passed=True,cutoffs=ranks,rank_table_unchanged_after_labels=True,lookback_fixed=21,future_industry_labels_computed=0))
 assert all(sha(p)==v for p,v in READS.items());save('READ_INPUTS.json',READS);save('CHECKS.json',dict(passed=True,account_events=0,signal_recomputations=0,new_future_labels=0,full90_reference=True,rows=len(allrows),industry_day_unique=len({(r['case'],r['day'],r['sector']) for r in allrows})==len(allrows),account_population='original C10 only, C20/R0 not loaded',seconds=time.monotonic()-started))
 print('COMPLETE',len(allrows),len(stockrows),flush=True)
if __name__=='__main__':main()
