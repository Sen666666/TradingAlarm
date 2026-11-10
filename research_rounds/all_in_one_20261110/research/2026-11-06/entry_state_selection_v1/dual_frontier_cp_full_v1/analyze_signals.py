"""Frozen descriptive comparison. No account simulation, ranking change, or parameter search."""
from pathlib import Path
import sys,json,gzip,time,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
P=R/'account_comparison_continuous_v1/run_1200000/pair'
D=R/'selection_entry_diagnosis_v1';L=D/'mobile_candidate_response_v1'
sys.path.insert(0,str(O));import replay_signals as r
START='2022-01-01';END='2026-05-15';start=time.monotonic()
calendar=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')['dates'])
calendar=calendar[calendar<=END];dates=[str(x.date()) for x in calendar];cpos={d:i for i,d in enumerate(dates)}
manifest={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())}
meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/metadata.json').read_text())
freeze=dict(status='ANALYSIS_DEFINITION_FROZEN_BEFORE_LABELS',membership='Signal unions and native I roots from sealed full-prefix replay. Original PVR-conditioned pre-size qualifier: held is False; mobile_Q is True; none of ACT_paused/exit_pending/buy_pending; industry E0_valid, nonnull attempt, stage>0. No use of original roles or event/core-only barrier reasons. No new pending/cap/fill assumed.',
oldlegal='Original 53121 PVR actual pending cap>0 legal intentions; only same-day retained/lost measured. Additions only in pre-size domain.',
root='Native I-active episodes, known birth only if prior observed row in same source inactive. Segment-start active is unknown birth. Birth<2022 separate. Deduplicate sid+segment+I_root. All known 2022+ roots included, even neither version receipts.',
labels='Fixed common anchor root birth; next COMMON trading-day adjusted OPEN, then 5/20/60 closing prices including entry day. Require all common sessions observed and price-eligible, one source segment and no synthetic/source-invalid. Only prices through cutoff. big60=MFE close>=.30 and terminal close>=.20; mature roots only. Never use each version first receipt as label anchor.',
capture='For fixed big60 root, same-root receipt within first5/20/60 common-calendar intervals AFTER and INCLUDING birth; lag 0..h-1. Report raw signal capture and pre-size qualification separately. This is opportunity timing, not actual selection/fills.',
timing='Within native I root: common same-day receipts synchronize versions; within blocks separated by those, pair unmatched old/new in chronological order; no tolerance search and no claim paired are same evidence. Report new-old common trading-day lag, native-observation lag, and calendar days.',
originalrounds='Only original PVR first_kind=add actual first MOBILE campaigns. Uniform closed as of 2026-05-15. Same-day new receipt retained/lost and same-root earlier new receipt annotation. Round net PnL is ORIGINAL history, not hypothetical strategy PnL; CORE not removed. Zero outcomes included in closed denominator.',
limits=['fixed future1709 pool and fixed sector metadata non-PIT','old-account held/ACT/pending depend on original strategy','full endpoint2026 is May15 not full year','no brokerage accounts, no account backtest, no parameter scan','no same-K ranking or funded queue recomputation'])
r.save('ANALYSIS_FREEZE.json',freeze)
ev=pd.read_parquet(O/'EVENTS.parquet');roots=pd.read_parquet(O/'I_ROOTS.parquet')
ev=ev.merge(roots[['sid','I_root','segment','unknown_birth','birth_before_2022']],on=['sid','I_root','segment'],validate='many_to_one')
ev['sector']=ev.sid.map(lambda s:meta.get(s,{}).get('sector_id'));ev['name']=ev.sid.map(lambda s:meta.get(s,{}).get('name'))
ev['event_type']=np.select([ev.old_receipt&ev.new_receipt,ev.old_receipt&~ev.new_receipt],['both','old_only'],default='new_only')
assert not ev.duplicated(['sid','day']).any()
# Original-account-conditioned daily qualification from FULL opportunity log, including old no-CP dates.
industry={}
for x in json.loads((U/'INDUSTRY_MANIFEST.json').read_text()):
 st=pd.read_parquet(x['refs']['state'])
 for q in st[(st.day>=START)&(st.day<=END)].itertuples():
  industry[(x['series'],q.day)]=bool(q.E0_valid and pd.notna(q.attempt_id) and q.stage>0)
keys=set(zip(ev.sid,ev.day));qrows=[];n=0;seen=0
hard={'ACT_paused','exit_pending','buy_pending'}
for line in gzip.open(P/'opportunities.jsonl.gz','rt'):
 d=json.loads(line)
 if d['account']!='PVR':continue
 n+=1
 if (d['sid'],d['day'])not in keys:continue
 seen+=1;bar=d['barriers'];assert isinstance(d['held'],bool) and isinstance(bar,list)
 active=industry[(d['sector'],d['day'])]
 eligible=d['held'] is False and d['mobile_Q'] is True and not hard.intersection(bar) and active
 qrows.append(dict(sid=d['sid'],day=d['day'],original_held=d['held'],original_mobile_Q=d['mobile_Q'],hard_barrier=bool(hard.intersection(bar)),industry_active=active,prequalified=eligible,old_CP_id=d['CP1_id'],old_rank=d['rank'],old_roles=','.join(d['roles']),old_barriers=','.join(bar)))
qd=pd.DataFrame(qrows);assert not qd.duplicated(['sid','day']).any()
ev=ev.merge(qd,on=['sid','day'],how='left',validate='one_to_one')
ev['opportunity_observed']=ev.prequalified.notna();ev['prequalified']=ev.prequalified.fillna(False).astype(bool)
legal=pd.read_parquet(L/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');legal=legal[legal.account=='PVR'].copy()
lx=legal.merge(ev[['sid','day','old_receipt','new_receipt','prequalified','I_root','segment','qok']],on=['sid','day'],how='left',validate='one_to_one')
assert len(lx)==53121 and lx.old_receipt.eq(True).all() and lx.prequalified.eq(True).all()
lx.to_parquet(O/'ORIGINAL_LEGAL_COMPARISON.parquet',index=False)
ev['original_legal']=pd.MultiIndex.from_frame(ev[['sid','day']]).isin(pd.MultiIndex.from_frame(legal[['sid','day']]))
ev.to_parquet(O/'EVENTS_QUALIFIED.parquet',index=False)
print('QUALIFIED',len(ev),int(ev.prequalified.sum()),'seconds',time.monotonic()-start,flush=True)
# Same-day event counts, keeping UNKNOWN separately.
counts=[]
def addcounts(domain,df,period):
 counts.append(dict(domain=domain,period=period,union=len(df),stocks=df.sid.nunique(),old=int(df.old_receipt.sum()),new=int(df.new_receipt.sum()),both=int((df.old_receipt&df.new_receipt).sum()),old_only=int((df.old_receipt&~df.new_receipt).sum()),new_only=int((~df.old_receipt&df.new_receipt).sum()),old_only_q_unknown=int((df.old_receipt&~df.new_receipt&~df.qok).sum())))
for name,df in [('full_I_signal',ev),('PVR_conditioned_presize',ev[ev.prequalified]),('original_legal',ev[ev.original_legal])]:
 addcounts(name,df,'ALL')
 for y,g in df.groupby('year'):addcounts(name,g,str(y))
 for lab,a,b in [('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]:
  addcounts(name,df[df.day.between(a,b)],lab)
  addcounts(name,df[df.day.between(a,b)&df.sector.eq('URFI881121')],lab+'_semiconductor')
pd.DataFrame(counts).to_csv(O/'EVENT_COUNTS.csv',index=False)
# Descriptive paired dates using full-signal common receipts as true synchronization boundaries.
pairs=[]
for sid,sg in ev.groupby('sid',sort=False):
 states=pd.read_parquet(O/'states'/(sid+'.parquet'));opos={x:i for i,x in enumerate(states.day)}
 for (root,seg),g in sg.groupby(['I_root','segment'],sort=False):
  g=g.sort_values('day');os=[];ns=[];block=0
  def flush():
   for i in range(max(len(os),len(ns))):
    a=os[i] if i<len(os) else None;b=ns[i] if i<len(ns) else None
    pairs.append(dict(sid=sid,I_root=root,segment=int(seg),block=block,old_day=a,new_day=b,kind='paired_unmatched' if a and b else 'unpaired_old' if a else 'unpaired_new',trading_lag=(cpos[b]-cpos[a])if a and b else np.nan,observation_lag=(opos[b]-opos[a])if a and b else np.nan,calendar_lag=(pd.Timestamp(b)-pd.Timestamp(a)).days if a and b else np.nan))
  for q in g.itertuples():
   if q.old_receipt and q.new_receipt:
    flush();os=[];ns=[];pairs.append(dict(sid=sid,I_root=root,segment=int(seg),block=block,old_day=q.day,new_day=q.day,kind='same_day',trading_lag=0,observation_lag=0,calendar_lag=0));block+=1
   elif q.old_receipt:os.append(q.day)
   else:ns.append(q.day)
  flush()
pairs=pd.DataFrame(pairs);pairs.to_parquet(O/'DESCRIPTIVE_EVENT_PAIRS.parquet',index=False)
# Common fixed root-birth labels and first-receipt lags.
rootout=[]
for no,(sid,rr)in enumerate(roots.groupby('sid',sort=False)):
 rec=manifest[sid];sp=next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet'));source=pd.read_parquet(sp).loc[:END]
 src=source.reindex(calendar)
 good=src.observed_bar.eq(True)&src.price_eligible.eq(True)&src.source_invalid.eq(False)&src.synthetic_event_bar.eq(False)
 good &= np.isfinite(src.open)&src.open.gt(0)&np.isfinite(src.close)&src.close.gt(0)
 ss=ev[ev.sid==sid]
 for t in rr.itertuples():
  d=t._asdict();d.pop('Index',None);d['year']=int(t.I_root[:4]);d['sector']=meta.get(sid,{}).get('sector_id');d['name']=meta.get(sid,{}).get('name')
  gg=ss[(ss.I_root==t.I_root)&(ss.segment==t.segment)]
  for arm in ['old','new']:
   for domain,hh in [('signal',gg),('qualified',gg[gg.prequalified])]:
    e=hh[hh[arm+'_receipt']];fd=e.day.min() if len(e) else None
    d[arm+'_'+domain+'_first']=fd
    d[arm+'_'+domain+'_lag']=cpos[fd]-cpos[t.I_root] if fd and t.I_root in cpos else np.nan
    d[arm+'_'+domain+'_count']=len(e)
  allowed=(not t.unknown_birth and not t.birth_before_2022 and t.I_root in cpos)
  for h in [5,20,60]:
   complete=False;ret=mfe=mae=np.nan
   if allowed:
    j=cpos[t.I_root]+1;stop=j+h
    if stop<=len(calendar):
     zz=src.iloc[j:stop];periodgood=good.iloc[j:stop]
     complete=bool(len(zz)==h and periodgood.all() and zz.segment_id.eq(t.segment).all())
     if complete:
      p=float(zz.open.iloc[0]);returns=zz.close.to_numpy()/p-1
      ret=float(returns[-1]);mfe=float(max(0,returns.max()));mae=float(min(0,returns.min()))
   d['complete'+str(h)]=complete;d['ret'+str(h)]=ret;d['mfe'+str(h)]=mfe;d['mae'+str(h)]=mae
  d['big60']=bool(d['complete60'] and d['mfe60']>=.3 and d['ret60']>=.2)
  rootout.append(d)
 if(no+1)%400==0:print('ROOT_LABELS',no+1,flush=True)
rr=pd.DataFrame(rootout);rr.to_parquet(O/'FIXED_I_ROOT_COMPARISON.parquet',index=False)
# Root dedup coverage (each native root once).
rootcounts=[]
for lab,g in [('ALL',rr)]+[(str(y),g)for y,g in rr.groupby('year') if y>=2022]+[('2024_924',rr[rr.I_root.between('2024-09-24','2024-10-31')]),('2026Q1',rr[rr.I_root.between('2026-01-01','2026-03-31')]),('2026Q1_semiconductor',rr[rr.I_root.between('2026-01-01','2026-03-31')&rr.sector.eq('URFI881121')])]:
 for domain in ['signal','qualified']:
  a=g['old_'+domain+'_count'].gt(0);b=g['new_'+domain+'_count'].gt(0)
  v=dict(period=lab,domain=domain,roots=len(g),unknown_birth=int(g.unknown_birth.sum()),birth_before2022=int(g.birth_before_2022.sum()),old_any=int(a.sum()),new_any=int(b.sum()),both_any=int((a&b).sum()),old_only_any=int((a&~b).sum()),new_only_any=int((~a&b).sum()),neither=int((~a&~b).sum()),mature60=int(g.complete60.sum()),big60=int(g.big60.sum()))
  for h in [5,20,60]:
   a=g['old_'+domain+'_lag'].between(0,h-1);b=g['new_'+domain+'_lag'].between(0,h-1);big=g.big60
   v.update({f'big_old_by{h}':int((a&big).sum()),f'big_new_by{h}':int((b&big).sum()),f'big_lost_by{h}':int((a&~b&big).sum()),f'big_added_by{h}':int((~a&b&big).sum())})
  rootcounts.append(v)
pd.DataFrame(rootcounts).to_csv(O/'ROOT_COUNTS.csv',index=False)
# Original actual first MOBILE campaign association, not new performance.
first=pd.read_csv(D/'ALL_FIRST_ENTRIES.csv');ff=first[(first.account=='PVR')&(first.first_kind=='add')].copy()
ff=ff.merge(ev[['sid','day','old_receipt','new_receipt','original_legal','I_root','segment','qok']].rename(columns={'day':'signal_day'}),on=['sid','signal_day'],how='left',validate='many_to_one')
assert ff.old_receipt.eq(True).all() and ff.original_legal.eq(True).all()
fg=rr[['sid','I_root','segment','new_signal_first','new_qualified_first','unknown_birth','birth_before_2022']]
ff=ff.merge(fg,on=['sid','I_root','segment'],how='left',validate='many_to_one')
ff['new_earlier_same_root']=ff.new_signal_first.notna()&(ff.new_signal_first<ff.signal_day)
ff['new_earlier_qualified_same_root']=ff.new_qualified_first.notna()&(ff.new_qualified_first<ff.signal_day)
ff['same_day_status']=np.where(ff.new_receipt,'retained','old_day_absent')
ff.to_csv(O/'ORIGINAL_FIRST_MOBILE_CAMPAIGNS.csv',index=False)
roundsum=[]
def rm(period,status,g):
 c=g[g.closed.eq(True)];w=c[c.round_pnl>0];l=c[c.round_pnl<0]
 roundsum.append(dict(period=period,status=status,original_campaigns=len(g),closed=len(c),open=len(g)-len(c),positive=len(w),zero=int(c.round_pnl.eq(0).sum()),negative=len(l),original_net_winrate=len(w)/len(c)if len(c)else np.nan,mean_original_win=float(w.round_pnl.mean()),mean_original_loss=float(l.round_pnl.mean()),original_payoff=float(w.round_pnl.mean()/-l.round_pnl.mean())if len(w)and len(l)else np.nan,original_net_sum=float(c.round_pnl.sum()),original_winner_profit_sum=float(w.round_pnl.sum()),new_earlier_same_root=int(g.new_earlier_same_root.sum()),new_earlier_qualified_same_root=int(g.new_earlier_qualified_same_root.sum())))
for label,g in [('ALL',ff)]+[(str(y),g)for y,g in ff.groupby('year')]:
 rm(label,'all_original',g)
 for status,h in g.groupby('same_day_status'):rm(label,status,h)
pd.DataFrame(roundsum).to_csv(O/'ORIGINAL_CAMPAIGN_ASSOCIATION.csv',index=False)
# Fixed cases and period right-tail examples, neither data-selected threshold nor new economics.
rr[rr.big60&((rr.old_signal_lag.between(0,19)&~rr.new_signal_lag.between(0,19))|(~rr.old_signal_lag.between(0,19)&rr.new_signal_lag.between(0,19)))].to_csv(O/'BIG60_ROOT_COVERAGE_CHANGES_BY20.csv',index=False)
rr[(rr.sector=='URFI881121')&rr.I_root.between('2026-01-01','2026-03-31')].to_csv(O/'2026Q1_SEMICONDUCTOR_ROOTS.csv',index=False)
ev[ev.sid.isin(['300666.SZ','301611.SZ','688603.SH','300085.SZ','002583.SZ','600056.SH','002317.SZ','002181.SZ'])].to_csv(O/'NAMED_CASE_EVENTS.csv',index=False)
r.save('ANALYSIS_SEAL.json',dict(code_hash=r.sha(__file__),freeze_hash=r.sha(O/'ANALYSIS_FREEZE.json'),signal_hash_unchanged=r.sha(O/'EVENTS.parquet')==json.loads((O/'SIGNAL_SEAL.json').read_text())['events_hash'],PVR_opportunity_rows=n,union_event_opportunity_rows=seen,missing_opportunity_events=int((~ev.opportunity_observed).sum()),old_legal=len(lx),old_legal_all_within_presize=True,original_first_mobile=len(ff),roots=len(rr),seconds=time.monotonic()-start))
print('EVENT_COUNTS');print(pd.DataFrame(counts).to_string(index=False));print('ROOTS');print(pd.DataFrame(rootcounts).to_string(index=False));print('ROUNDS');print(pd.DataFrame(roundsum).to_string(index=False));print('COMPLETE',time.monotonic()-start,flush=True)
