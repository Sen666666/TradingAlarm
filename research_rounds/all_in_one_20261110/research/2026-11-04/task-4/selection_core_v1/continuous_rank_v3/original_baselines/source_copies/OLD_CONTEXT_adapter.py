"""Single frozen Q3 experiment; original L0 ledger, policy and sizing."""
from pathlib import Path
import sys,importlib.util,json,hashlib,time,collections,copy,inspect,gzip
from datetime import datetime,time as dt
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
C=load('mainline_frozen_L0',W/'lr1-cp1-add-preflight-20261031/adapter.py')
BP,LR,N,E,R,D=C.BP,C.LR,C.N,C.E,C.R,C.D
save,read,sha=C.save,C.read,C.sha
IC=W/'native-I-cache-interface-20261031';P=ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared'
F=W/'market-mainline-measurement-20261031/FEATURE_MATRIX_90.parquet'
START='2025-07-01';END='2025-09-30'

# This is the only planning change. It is checked against the original body.
needle="early=a.name!='D1' and not held and event[sid] and a.core_epoch.get(sid)!=epoch"
assert C.src.count(needle)==1
source=C.src.replace(needle,needle+" and (not getattr(self,'gate_enabled',False) or sid in self.shortlists[a.rank_policy])")
env=dict(BP.__dict__);exec(source.strip(),env);rank_planning=env['planning']
original_planning=C.plan_original_add

def sector_facts(sid,end=END):
 m=load('mainline_native_I_inputs',IC/'cache.py') if 'mainline_native_I_inputs' not in sys.modules else sys.modules['mainline_native_I_inputs']
 rec=m.RECORDS[sid];paths={k:m.OLD/rec['files'][k]['path'] for k in ['signal','events','states']}
 for k,p in paths.items():assert sha(p)==rec['files'][k]['sha256']
 sig=pd.read_parquet(paths['signal']).loc[:end];f=m.eligible_prices(sig);ev=pd.read_parquet(paths['events']).reindex(f.index);st=pd.read_parquet(paths['states']).reindex(f.index)
 e=f[['segment_id','open','high','low','close','volume']].copy();e['valid_price_observation']=True;e['price_observation']=e.groupby('segment_id',sort=False).cumcount();e['event']=ev.event;e['confirmed_pivot_price']=ev.confirmed_pivot_price;e['ready']=st.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
 v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0));e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
 for c in ['volume_ratio','high_effort','declined']:e[c]=st[c]
 e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
 base,_=m.e0_policy(e);assert not base.pending.fillna(0).any()
 out=f[['close','segment_id']].copy();out['e0_ready']=st.ready;out['e0_target']=base.target;out['e0_floor']=base.floor;out['factor']=sig.adjustment_factor.reindex(out.index);out['raw_close']=sig.raw_close.reindex(out.index)
 return out

def prepare():
 t=time.monotonic();(O/'industry-facts').mkdir(exist_ok=False)
 ids=read(IC/'FREEZE.json')['stocks'];records={r['series_id']:r for r in read(P/'manifest.json')['series']};gids=sorted(k for k in records if k.startswith('URFI'));assert len(ids)==1709 and len(gids)==90
 for sid in gids:sector_facts(sid).to_parquet(O/'industry-facts'/f'{sid}.parquet')
 print('INDUSTRY_Q90',round(time.monotonic()-t,3),flush=True)
 # Invoke the existing exact project market-clock constructor, not a new model.
 sys.path.insert(0,str(ROOT));from TradingAlarm.desk.refresh import compute_recovery
 old=RR/'a-share-selection-e0-20261024/prepared-v2';rec={r['series_id']:r for r in read(old/'manifest.json')['series']};meta=read(RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');signals={};absent=[]
 for sid in ids:
  q=old/rec[sid]['files']['signal']['path'];assert sha(q)==rec[sid]['files']['signal']['sha256']
  f=pd.read_parquet(q,columns=['close','amount','price_eligible','observed_bar','synthetic_event_bar','segment_id']).loc[:END]
  valid=f.price_eligible&f.observed_bar&~f.synthetic_event_bar
  if not valid.any():absent.append(sid)
  else:signals[sid]=f
 roster=pd.DataFrame([dict(symbol=s,sector_id=meta[s]['sector_id']) for s in ids if s in signals])
 z=compute_recovery(signals,roster);z['fast_on']=z.breadth.gt(.6);z.to_csv(O/'recovery.csv')
 # Physical feature clock prefix: no signal beyond the boundary is passed.
 pre='2025-08-15';subset={s:f.loc[:pre] for s,f in signals.items() if (f.loc[:pre].price_eligible&f.loc[:pre].observed_bar&~f.loc[:pre].synthetic_event_bar).any()};rp=roster[roster.symbol.isin(subset)];small=compute_recovery(subset,rp)
 for c in small.columns:np.testing.assert_allclose(small[c].astype(float),z.loc[small.index,c].astype(float),rtol=0,atol=0,equal_nan=True)
 save(O/'PREPARED.json',dict(passed=True,seconds=time.monotonic()-t,stocks=ids,industries=gids,absent_market_history=absent,market_domain='fixed1709 stocks, 90 mutually-exclusive industries; actual formula uses industry-grouped stock inputs',market_formula=str(ROOT/'TradingAlarm/desk/refresh.py')+':compute_recovery',unchanged_min_stock_breadth=5,unchanged_min_sector_breadth=8,physical_market_prefix=pre,market_rows=len(z),market_breakouts_Q3=int(z.loc[START:END,'breakout'].sum()),industry_policy='original e0_policy with decline_candidate=False',no_accounts=True))
 print('PREP_COMPLETE',round(time.monotonic()-t,3),flush=True)

def context(cut=None,ids=None):
 b=BP.C.load_bundle(BP.C.OLD/'inputs-v2/input-manifest.json');allids=read(IC/'FREEZE.json')['stocks'];keep=set(ids or allids);b.lines=tuple(l for l in b.lines if l.security_id in keep);assert {l.security_id for l in b.lines}==keep
 sectors={l.sector_id for l in b.lines};b.series={s:v for s,v in b.series.items() if s in keep|sectors};b.sector_series={s:v for s,v in b.sector_series.items() if s in sectors};records={r['series_id']:r for r in read(P/'manifest.json')['series']};frames={}
 for sid,item in b.series.items():
  item.record=records[sid];path=(O/'industry-facts' if sid.startswith('URFI') else IC/'facts')/f'{sid}.parquet';f=pd.read_parquet(path).loc[:cut or END];frames[sid]=f
  item.states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 h=np.load(P/'h1.npz');dates=pd.DatetimeIndex(h['dates']);mask=dates<=pd.Timestamp(cut or END);b._h1_cache=(dates[mask],{str(s):j for j,s in enumerate(h['symbols'])},h['score'][mask].copy())
 rules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');m=E.FastMarket(b,rules,[],read(BP.C.OLD/'inputs-v2/economic-protocol.json'))
 if cut:
  for sid,f in m.raw.items():
   m.raw[sid]=f.loc[:cut].copy();n=len(m.raw[sid]);a=m.arr[sid];m.arr[sid]={k:(v[v<n] if k in ['good','positive'] else v[:n] if isinstance(v,np.ndarray) else v) for k,v in a.items()}
  m.actions={s:[e for e in es if e['effective_date']<=cut] for s,es in m.actions.items()}
 facts=E.Facts.__new__(E.Facts);facts.b=b;facts.market=m;facts.f=frames;facts.cache={};facts.day=None;facts.structure_lookup={}
 rawrow=facts.row;cache={};at0=[None]
 def row(sid,at):
  if at0[0]!=at:cache.clear();at0[0]=at
  if sid not in cache:cache[sid]=rawrow(sid,at)
  return cache[sid]
 facts.row=row
 return b,m,facts

class Pilot(C.Pilot):
 def __init__(self,cut=None,policies=('H1','ATT'),shared=None):
  self.bundle,self.market,self.facts=shared or context(cut);self.accounts={};self.b0=N.B0Controller();self.applied_actions=set();self.actions_by_date={};self.daily=[];self.risk=[];self.sector='ALL1709';self.prep=IC;self.core=P;self.row_cache_checks=0;self.gate_enabled=True
  for key in policies:
   a=C.Account(key,self.market,self.facts,False,1,0);a.rank_policy=key;self.accounts[key]=a
  for sid,es in self.market.actions.items():
   for n,e in enumerate(es):self.actions_by_date.setdefault(e['effective_date'],[]).append((sid,n,e))
  empty=pd.DataFrame(index=pd.DatetimeIndex([]));self.cp={s:empty for s in self.market.lines};self.pv={s:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for s in self.market.lines}
  self.last_epoch={};self.epoch=collections.Counter();self.global_watch={};self.shortlists={};self.selection_rows=[];self.funnel=[];self.day_checks=[]
  self.matrix=pd.read_parquet(F);self.matrix=self.matrix[(self.matrix.day>=START)&(self.matrix.day<=str(cut or END))];self.matrix_days={d:g.set_index('sector') for d,g in self.matrix.groupby('day',sort=False)}
  self.line_sector={l.security_id:l.sector_id for l in self.bundle.lines};self.line_order={l.security_id:n for n,l in enumerate(self.bundle.lines)}
 def make_lists(self,at):
  day=str(at.date());g=self.matrix_days[day];raw=[];price=[];unknown=[]
  for sid in self.market.lines:
   f=self.facts.f[sid];today=pd.Timestamp(day)
   if today not in f.index:continue
   r=f.loc[today]
   if not bool(r.i_buy) or not bool(r.i_target):continue
   raw.append(sid);q=g.loc[self.line_sector[sid]]
   if not bool(q.price_qualified):continue
   if not np.isfinite(q.H1_original) or not np.isfinite(q.attention_ratio):unknown.append(sid);continue
   price.append(sid)
  b=(len(price)+1)//2;self.shortlists={}
  for key,column in [('H1','H1_original'),('ATT','attention_ratio')]:
   ordered=sorted(price,key=lambda s:(-float(g.loc[self.line_sector[s],column]),self.line_sector[s],self.line_order[s],s));chosen=ordered[:b];assert len(chosen)==b and len(set(chosen))==b
   self.shortlists[key]=set(chosen)
   self.selection_rows.append(dict(day=day,policy=key,raw_I_count=len(raw),P_score_known_count=len(price),P_rank_unknown_count=len(unknown),B=b,candidates=price,selected=chosen,unknown=unknown,attention_at_or_below1_selected=sum(float(g.loc[self.line_sector[s],'attention_ratio'])<=1 for s in chosen)))
 def planning(self,at):
  self.make_lists(at);before={k:len(a.decisions) for k,a in self.accounts.items()};C.plan_original_add=rank_planning
  super().planning(at)
  clock,stocks,sectors=self.facts.packet(at,'I');ss={s.sector_id:s for s in sectors};sd={s.security_id:s for s in stocks}
  for key,a in self.accounts.items():
   assert len(a.decisions)==before[key]+1
   for i in a.pending:assert i['kind']=='core' and i['sid'] in self.shortlists[key]
   counts=collections.Counter();reasons=collections.Counter()
   for sid in self.shortlists[key]:
    q=BP.A.eligibility(sd[sid],ss,clock,'S0');counts['Q_pass' if q.q is True else 'Q_unknown' if q.q is None else 'Q_fail']+=1
    if q.q is not True:reasons.update(q.reasons);continue
    if not a.risk_state['on']:counts['ACT_paused']+=1
    elif sid in a.exits:counts['exit_pending']+=1
    elif sid in a.buys:counts['buy_pending']+=1
    elif a.quantity(sid):counts['already_held']+=1
    elif a.core_epoch.get(sid)==self.global_watch.get(sid):counts['epoch_lock']+=1
    elif any(i['sid']==sid for i in a.pending):counts['intent_after_sizing']+=1
    else:counts['size_or_floor_reject']+=1
   self.funnel.append(dict(day=str(at.date()),policy=key,selected=len(self.shortlists[key]),counts=dict(counts),Q_reasons=dict(reasons)))
 def run(self,end=END,begin=START,max_seconds=None):
  t=time.monotonic();start=N.iso(begin+'T15:10:00+08:00');finish=N.iso(end+'T15:10:00+08:00');cutoffs={x for x in self.market.cutoffs if start<=x<=finish};opens={x for x in self.market.sessions['A'] if start<=x<=finish};acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,N.TZ) for d in self.actions_by_date};events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish});assert finish in cutoffs
  E.risk_policy.RECOVERY=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True).loc[:end if self.facts.f[next(iter(self.market.lines))].index.max()<=pd.Timestamp(end) else END]
  for at in events:
   if max_seconds and time.monotonic()-t>max_seconds:raise TimeoutError('frozen120s economic budget; partial state retained by caller')
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for a in self.accounts.values():self.opening(a,at)
   if at in cutoffs:
    self.planning(at)
    if len(self.daily)%20==0:print('CLOSE',str(at.date()),'rows',len(self.daily),'seconds',round(time.monotonic()-t,3),flush=True)
  self.run_seconds=time.monotonic()-t;return self
 def dump(self,out):
  C.dump(self,out);out=Path(out)
  with gzip.open(out/'selection.jsonl.gz','wt') as f:
   for row in self.selection_rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  save(out/'FUNNEL.json',self.funnel);save(out/'RUN_TIME.json',dict(seconds=self.run_seconds,new_economic_paths=len(self.accounts)))

if __name__=='__main__':prepare()
