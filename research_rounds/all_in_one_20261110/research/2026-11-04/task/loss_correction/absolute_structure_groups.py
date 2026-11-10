"""Join actual fills to frozen original structure/evidence identities.
Pure saved-cache grouping. No signals, permissions or account events generated.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,gzip,time
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import absolute_retries as R
P,O,W,Z=R.P,R.O,R.W,R.Z;SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def n(x):return D(str(x))
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,D):return str(x)
 if x is None:return None
 try:
  if pd.isna(x):return None
 except (TypeError,ValueError):pass
 return x.item() if hasattr(x,'item') else x
def parquet(p,expected,columns=None):
 assert sha(p)==expected;SRC[str(p)]=sha(p);return pd.read_parquet(p,columns=columns)
def epochs(f,sid,key):
 on=f[key].fillna(False).astype(bool);seg=f.segment_id;start=on & (~on.shift(fill_value=False)|seg.ne(seg.shift()))
 tags=pd.Series(None,index=f.index,dtype=object)
 for dt in f.index[start]:tags.loc[dt]=sid+'|'+str(int(seg.loc[dt]))+'|'+str(dt.date())
 return tags.groupby(seg).ffill().where(on,None)
def grouped(entries,key):
 g=defaultdict(list)
 for l in entries:g[str(l[key])].append(l)
 out=[]
 for k,ll in g.items():
  cycles={x['stock_campaign_number'] for x in ll};out.append(dict(key=k,layer_ids=[x['layer'] for x in ll],stock_campaigns=len(cycles),actual_CP1_ids=len({x['receipt'] for x in ll if x['receipt']}),actions=dict(Counter(x['action'] for x in ll)),**R.agg(ll)))
 return sorted(out,key=lambda x:x['net'])
def main():
 started=time.monotonic();sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 manifests={y:{x['sid']:x for x in read(W/path)} for y,path in [('2022','2022-normal-reference-20261031/inputs/MANIFEST.json'),('2023','recovery-2023-readiness-20261101/inputs/MANIFEST.json')]}
 cases=read(O/'FIXED_FOUR_CASES.json')['cases'];caseids={x['sid'] for x in cases};fig,axes=plt.subplots(4,2,figsize=(22,17),layout='constrained');caseout={};industry={};allsummary={}
 roots={'2022_2023':P.parent/'pvr_pool_feasibility/continuation2023/run-2023','strong':P.parent/'pvr_pool_feasibility/runs/2025_26'}
 for scope,root in roots.items():
  prefix='PVR_NO60-'+scope;entries=read(O/(prefix+'-ENTRIES.json'));export=P/'no60_behavior_v1/continuation2023' if scope=='2022_2023' else P/'pvr_no60_2025_26';cc=read(export/'PVR_NO60-CAMPAIGNS.json');cm={lid:c['campaign_number'] for c in cc for lid in c['layer_ids']};lo,end=('2022-01-01','2023-12-29') if scope=='2022_2023' else ('2025-07-01','2026-06-30')
  b=R.gz(root/'pair/B.json.gz');daily=R.rows(root/'pair/daily.jsonl.gz');buys={t['layer']:t for t in b['trades'] if t['side']=='buy'};joined=[]
  for sid in sorted({x['sid'] for x in entries}):
   m=sm[sid];fp=m['refs']['facts'];f=parquet(fp,m['output_sha256'][fp]).loc[:end];cp=m['refs']['CP1'];cz=parquet(cp,m['output_sha256'][cp],['receipt','candidate','phase','reset_reason','delta_frontier','m','v']).loc[:end];ee=epochs(f,sid,'e0_target');ie=epochs(f,sid,'i_target');own=sorted([x for x in entries if x['sid']==sid],key=lambda x:x['opened']);receipts={}
   for year in {x['signal_day'][:4] for x in own if x['receipt']}:
    if year in manifests:
     r=manifests[year][sid];rp=r['output_path'];assert sha(rp)==r['output_sha256']
    else:rp=m['refs']['receipts'];assert sha(rp)==m['output_sha256'][rp]
    for r in read(rp):receipts[r['receipt_id']]=r
   sec=own[0]['sector']
   if sec not in industry:
    mm=im[sec];sp=mm['refs']['state'];industry[sec]=parquet(sp,mm['output_sha256'][sp]).set_index('day')
   memo=defaultdict(list);memo_i=defaultdict(list);memo_cp=defaultdict(list);memo_fin=defaultdict(list);memo_market=defaultdict(list)
   for l in own:
    d=l['signal_day'];dt=pd.Timestamp(d);r=f.loc[dt];c=cz.loc[dt];st=industry[sec].loc[d];t=buys[l['layer']];e0=ee.loc[dt];i0=ie.loc[dt];trace=receipts[l['receipt']] if l['receipt'] else None
    if trace:assert trace['canonical_series']==sid and trace['confirmed_day']==d and bool(c.receipt) and not trace['trace_unknown']
    cp_e0=trace['original_E0_episode_id'] if trace else None;financial=sid+'|'+str(l['attempt']);market=sid+'|'+str(st.attempt_id);prior_cp=memo_cp.get(cp_e0,[]) if cp_e0 else [];prior_i=memo_i.get(i0,[]) if i0 else []
    x=dict(l,stock_campaign_number=cm[l['layer']],source_segment=int(r.segment_id),cached_E0_epoch=e0,cached_I_epoch=i0,CP1_original_E0_episode=cp_e0,financial_stock_industry_attempt=financial,canonical_stock_industry_attempt=market,financial_E0_joint=financial+'|'+str(e0),canonical_E0_joint=market+'|'+str(e0),signal_continuous_close=n(r.close),signal_raw_close=n(r.raw_close),signal_I_valid=clean(r.i_target),signal_E0_valid=clean(r.e0_target),signal_I_floor=clean(r.i_floor),signal_E0_floor=clean(r.e0_floor),CP1_candidate=clean(c.candidate) if bool(c.receipt) else None,CP1_phase=clean(c.phase),CP1_reset_reason=clean(c.reset_reason),CP1_delta_frontier=clean(c.delta_frontier),CP1_m=clean(c.m),CP1_v=clean(c.v),canonical_receipt=trace,original_initial_adjusted_floor=t['floor'],actual_fill_price=t['price'],entry_known_factor=n(f.loc[pd.Timestamp(t['at'][:10]),'factor']),reentry_same_cached_E0=bool(l['action']=='fresh_reentry_after_actual_flat' and e0 is not None and memo.get(e0)),reentry_same_cached_I=bool(l['action']=='fresh_reentry_after_actual_flat' and i0 is not None and prior_i),reentry_same_financial_industry_attempt=bool(l['action']=='fresh_reentry_after_actual_flat' and memo_fin.get(financial)),reentry_same_canonical_industry_attempt=bool(l['action']=='fresh_reentry_after_actual_flat' and memo_market.get(market)),repeat_mobile_same_CP1_E0=bool(trace and prior_cp),prior_actual_layers_same_I=[z['layer'] for z in prior_i])
    if prior_cp:
     first=prior_cp[0];x['price_above_first_actual_signal_same_CP1_E0']=n(r.close)>n(first['signal_continuous_close']);x['CP1_candidate_above_first_actual_signal_same_CP1_E0']=n(c.candidate)>n(first['CP1_candidate']);x['I_floor_above_first_actual_signal_same_CP1_E0']=n(r.i_floor)>n(first['signal_I_floor'])
    else:
     for k in ['price_above_first_actual_signal_same_CP1_E0','CP1_candidate_above_first_actual_signal_same_CP1_E0','I_floor_above_first_actual_signal_same_CP1_E0']:x[k]=None
    joined.append(x)
    if e0 is not None:memo[e0].append(x)
    if i0 is not None:memo_i[i0].append(x)
    if cp_e0:memo_cp[cp_e0].append(x)
    memo_fin[financial].append(x);memo_market[market].append(x)
   if sid in caseids:
    ci=next(k for k,z in enumerate(cases) if z['sid']==sid)
    if cases[ci]['scope']==scope:
     ff=f.loc[lo:end];zz=cz.reindex(ff.index);xx=np.arange(len(ff));ix={str(t.date()):j for j,t in enumerate(ff.index)}
     for a in axes[ci]:a.plot(xx,ff.close,lw=1,color='#384957');ticks=np.arange(0,len(ff),60);a.set_xticks(ticks,[str(ff.index[j].date()) for j in ticks],fontsize=7,rotation=10);a.grid(alpha=.15)
     axes[ci,0].plot(xx,ff.i_floor.where(ff.i_target.astype(bool)),color='#399176',lw=1,label='cached I');axes[ci,0].plot(xx,ff.e0_floor.where(ff.e0_target.astype(bool)),color='#8a75ac',lw=.7,label='cached E0');re=zz.receipt.fillna(False).astype(bool);axes[ci,0].scatter(xx[re],zz.candidate[re],s=10,color='#bc7a31',label='cached fresh CP1');axes[ci,0].set_title(sid+' saved states',fontsize=10);axes[ci,0].legend(fontsize=7)
     ownjoin=[x for x in joined if x['sid']==sid];floorpaths=[]
     for l in ownjoin:
      dd=l['opened'][:10];axes[ci,1].scatter(ix[dd],float(n(l['actual_fill_price'])*l['entry_known_factor']),marker='^',color='#c74c43',s=25);fp=[]
      for d in daily:
       z=next((z for z in d['layers'] if z['id']==l['layer']),None)
       if z:fp.append(dict(day=d['at'][:10],floor=z['last_core_line'] if z['role']=='core' else z['floor'],role=z['role'],quantity=z['qty']))
      if fp:axes[ci,1].plot([ix[z['day']] for z in fp],[float(z['floor']) for z in fp],lw=.6,color='#3e829d' if l['role']=='mobile' else '#8a75ac')
      floorpaths.append(dict(layer=l['layer'],actual_after_CLOSE_path=fp))
     for t in b['trades']:
      if t['security_id']==sid and t['side']=='sell':dd=t['at'][:10];axes[ci,1].scatter(ix[dd],float(n(t['price'])*n(f.loc[pd.Timestamp(dd),'factor'])),marker='v',color='#2f8a65',s=25)
     axes[ci,1].set_title(sid+' actual buys/sells + after-CLOSE live floors',fontsize=10);caseout[sid]=dict(scope=scope,joined_entries=ownjoin,actual_campaigns=[c for c in cc if c['sid']==sid],floorpaths=floorpaths,source_states=clean(ff.join(zz.add_prefix('CP1_')).reset_index().to_dict('records')))
  assert len(joined)==len(entries) and sum((n(x['net']) for x in joined),Z)==sum((n(x['net']) for x in entries),Z)
  dims={}
  for key in ['cached_E0_epoch','cached_I_epoch','financial_stock_industry_attempt','canonical_stock_industry_attempt','financial_E0_joint','canonical_E0_joint']:
   gg=grouped(joined,key);save(prefix+'-'+key+'-GROUPS.json',gg);repeated=[g for g in gg if g['stock_campaigns']>=2];dims[key]=dict(groups=len(gg),groups_multiple_flatcycles=len(repeated),repeated_groups_negative=sum(g['net']<0 for g in repeated),repeated_group_layers=sum(g['layers'] for g in repeated),repeated_group_buy_cash=sum((g['buy_cash'] for g in repeated),Z),repeated_group_net=sum((g['net'] for g in repeated),Z))
  cohorts={}
  for key in ['reentry_same_cached_E0','reentry_same_cached_I','reentry_same_financial_industry_attempt','reentry_same_canonical_industry_attempt']:
   cohorts[key]=R.agg([x for x in joined if x[key]])
  repeat=[x for x in joined if x['repeat_mobile_same_CP1_E0']];progress={}
  for p in [False,True]:
   for c in [False,True]:progress[f'price_above_first={p}|CP1_candidate_above_first={c}']=R.agg([x for x in repeat if x['price_above_first_actual_signal_same_CP1_E0']==p and x['CP1_candidate_above_first_actual_signal_same_CP1_E0']==c])
  unknown={k:sum(x[k] is None for x in joined) for k in ['cached_E0_epoch','cached_I_epoch','CP1_original_E0_episode']};allsummary[scope]=dict(dimensions=dims,reentry_same_structure_cohorts=cohorts,repeat_mobile_price_protection_progress=progress,missing_id_counts=unknown,independent_CP1_ids=len({x['receipt'] for x in joined if x['receipt']}),actual_mobile_layers=sum(bool(x['receipt']) for x in joined),scope='Grouping original cached states/receipt identities only; CP1 original_E0_episode uses original CP1 input e0_valid==cached i_target, distinct from raw facts e0_target; not recomputing numeric models or real-time gates')
  save(prefix+'-JOINED_ENTRIES.json',joined)
 save('STRUCTURE_POPULATION_SUMMARY.json',allsummary);save('FOUR_SAVED_PATHS.json',caseout);fig.savefig(O/'FOUR_SAVED_STATE_AND_ACTUAL_PATHS.png',dpi=130);plt.close(fig);SRC.update(R.SRC);save('SOURCE_BINDING-PHASE2.json',dict(sources=SRC,script_sha256=sha(__file__),seconds=time.monotonic()-started,new_account_events=0,numeric_signal_recomputations=0,field_identity_warning='CP1 original_E0_episode is not silently merged with raw E0 target episode'))
 print(json.dumps(clean(allsummary),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
