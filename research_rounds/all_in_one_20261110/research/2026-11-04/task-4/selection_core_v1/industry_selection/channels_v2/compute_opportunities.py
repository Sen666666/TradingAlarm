"""Frozen CONT/START industry opportunity sets. No rank quota/accounts/labels."""
from pathlib import Path
from collections import Counter
import hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;OLD=O.parent;ROOT=OLD.parent
B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
SNAPSHOTS=['2024-09-24','2026-01-15','2022-01-24'];BEGIN='2022-01-01';END='2026-06-30';SOURCES={}
COLS=['open','high','low','close','volume','amount','segment_id','observed_bar','price_eligible','synthetic_event_bar','source_invalid','amount_unit']
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'SHA mismatch')
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,pd.Timestamp):return str(v.date())
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not np.isfinite(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def pq(p,h,cols):
 f=pd.read_parquet(bind(p,h),columns=cols);f.index=pd.DatetimeIndex(f.index).as_unit('ns')
 assert f.index.is_unique and f.index.is_monotonic_increasing;return f
def yes(s):return s.eq(True).fillna(False)
def no(s):return s.eq(False).fillna(False)
def pos(s):return s.gt(0)&np.isfinite(s)
def complete(valid,seg,n):
 return valid.rolling(n,min_periods=n).sum().eq(n)&seg.rolling(n,min_periods=n).max().eq(seg.rolling(n,min_periods=n).min())

def stock_state(signal,calendar):
 s=signal.reindex(calendar);seg=pd.to_numeric(s.segment_id,errors='coerce')
 numeric={k:pd.to_numeric(s[k],errors='coerce')for k in ['open','high','low','close','volume','amount']}
 o,h,l,c,v,a=[numeric[k]for k in ['open','high','low','close','volume','amount']]
 observed=yes(s.observed_bar);flags=observed&yes(s.price_eligible)&no(s.synthetic_event_bar)&no(s.source_invalid)
 price=flags&pos(o)&pos(h)&pos(l)&pos(c)&l.le(o)&l.le(c)&h.ge(o)&h.ge(c)&h.ge(l)
 av=observed&no(s.synthetic_event_bar)&no(s.source_invalid)&s.amount_unit.eq('CNY').fillna(False)&pos(a)
 full=price&pos(v)&av&seg.notna();v25=complete(full,seg,25)
 A=a.where(av);median=A.shift(1).rolling(21,min_periods=21).median();mean=A.shift(1).rolling(5,min_periods=5).mean()
 U=v25&median.ge(20000000)&mean.ge(10000000)
 C=c.where(price);ma=C.rolling(20,min_periods=20).mean()
 assert ma[U].notna().all()and ma.shift(5)[U].notna().all()
 above=C.gt(ma);above5=C.shift(5).gt(ma.shift(5))
 previous=U.shift(1,fill_value=False);prev5=U.shift(5,fill_value=False)
 return dict(U=U,N25valid=v25,observed_price=price,above=above,above5=above5,
  entrants1=U&~previous,leavers1=~U&previous,prev5=prev5,pair5=U&prev5,entrants5=U&~prev5,leavers5=~U&prev5,
  flow5=A.rolling(5,min_periods=5).sum().where(U,0.),flow20=A.shift(5).rolling(20,min_periods=20).sum().where(U,0.))

def add_channels(panel):
 pieces=[]
 for day,g in panel.groupby('date',sort=True):
  g=g.copy();rk=g.rs_ind5.notna();N=int(rk.sum());g['p_rs5']=np.nan;g['R5_midrank_integer_numerator']=np.nan
  if N:
   units=2*g.loc[rk,'rs_ind5'].rank(method='average')-1
   g.loc[rk,'p_rs5']=units/(2*N);g.loc[rk,'R5_midrank_integer_numerator']=units
  g['N_R5_known']=N
  k20=g.rs_ind20.notna();N20=int(k20.sum());g['p_rs20']=np.nan;g['N_R20_known']=N20
  if N20:g.loc[k20,'p_rs20']=(g.loc[k20,'rs_ind20'].rank(method='average')-.5)/N20
  kc=g.rs_ind20.notna()&g.breadth20_t.notna();ks=g.p_rs5.notna()&g.delta_breadth5.notna()
  g['CONT']=pd.Series(pd.NA,index=g.index,dtype='boolean');g['START']=pd.Series(pd.NA,index=g.index,dtype='boolean')
  # Rational comparisons avoid epsilon changes at the frozen .60/.80 cutoffs.
  g.loc[kc,'CONT']=g.loc[kc,'rs_ind20'].gt(0)&(5*g.loc[kc,'N_above20_t']).ge(3*g.loc[kc,'N_U_t'])
  g.loc[ks,'START']=(5*g.loc[ks,'R5_midrank_integer_numerator']).ge(8*N)&g.loc[ks,'N_above20_t'].gt(g.loc[ks,'N_above20_tminus5'])
  g['UNION']=g.CONT|g.START;g['CONT_known']=kc;g['START_known']=ks;g['UNION_known']=g.UNION.notna()
  def label(a,b):
   if pd.isna(a)or pd.isna(b):return 'CONT_'+('UNKNOWN'if pd.isna(a)else str(bool(a)).upper())+'_START_'+('UNKNOWN'if pd.isna(b)else str(bool(b)).upper())
   if a and b:return 'BOTH'
   if a:return 'CONT_ONLY'
   if b:return 'START_ONLY'
   return 'NONE'
  g['channel_label']=[label(a,b)for a,b in zip(g.CONT,g.START)]
  g['missing_channel_inputs']=['|'.join(k for k,missing in [('CONT',not a),('START',not b)]if missing)for a,b in zip(kc,ks)]
  g['CONTINUE_static']=g.CONT;g['START_static']=g.START;g['UNION_static']=g.UNION
  pieces.append(g)
 return pd.concat(pieces,ignore_index=True)

def snapshot_reports(table):
 reports={}
 for day in SNAPSHOTS:
  g=table.loc[table.date.eq(day)]
  reports[day]=dict(CONT=int(g.CONT.eq(True).sum()),START=int(g.START.eq(True).sum()),UNION=int(g.UNION.eq(True).sum()),
   both=int((g.CONT.eq(True)&g.START.eq(True)).sum()),unknown_union=int(g.UNION.isna().sum()),
   CONT_sectors=g.loc[g.CONT.eq(True),'industry_static'].tolist(),START_sectors=g.loc[g.START.eq(True),'industry_static'].tolist(),
   UNION_sectors=g.loc[g.UNION.eq(True),'industry_static'].tolist(),
   focal=g.loc[g.industry_static.isin(['软件开发','房地产'])].to_dict('records'))
 return reports

def main():
 begun=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_STATIC_DIAGNOSTIC.txt');bind(ROOT/'industry_channels_v2/FROZEN_CHANNELS_DESIGN.txt');bind(O/'CONTRACT.txt')
 sm=read(B/'STOCK_MANIFEST.json');im=read(B/'INDUSTRY_MANIFEST.json');meta=read(META)
 cp=read(MARKET/'checkpoints/USHI1B0300.json');market=pd.read_csv(bind(MARKET/'canonical/USHI1B0300.csv',cp['canonical_sha256']),parse_dates=['date']).set_index('date')
 market.index=market.index.as_unit('ns');study=market.index[(market.index>=BEGIN)&(market.index<=END)]
 first=market.index.get_loc(study[0]);calendar=market.index[first-29:market.index.get_loc(study[-1])+1]
 sectors=sorted(r['series']for r in im);sidpos={s:i for i,s in enumerate(sectors)};n=len(calendar)
 names={meta[r['symbol']]['sector_id']:meta[r['symbol']]['industry']for r in sm};static=Counter(meta[r['symbol']]['sector_id']for r in sm)
 fields=['N_U','N25','Nobs','Nup','Nup5','entrants1','leavers1','prev5','pair5','entrants5','leavers5','flow5','flow20']
 agg={k:np.zeros((90,n),dtype=float)for k in fields};snaprows=[];prefix=[]
 old=pd.read_parquet(bind(OLD/'U_T_STOCK_ELIGIBILITY.parquet'),columns=['sid','date','qualified_U_t','above_sma20_T']);old=old.set_index(['sid','date'])
 sample={0,len(sm)//4,len(sm)//2,3*len(sm)//4,len(sm)-1}
 for i,r in enumerate(sm):
  sid=r['symbol'];sec=meta[sid]['sector_id'];si=sidpos[sec]
  paths=[p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet')];assert len(paths)==1
  s=pq(paths[0],r['source_sha256'][paths[0]],COLS);x=stock_state(s,calendar);u=x['U']
  vals={'N_U':u,'N25':x['N25valid'],'Nobs':x['observed_price'],'Nup':u&x['above'],'Nup5':u&x['above5'],
        **{k:x[k]for k in ['entrants1','leavers1','prev5','pair5','entrants5','leavers5','flow5','flow20']}}
  for k,v in vals.items():agg[k][si]+=v.to_numpy(dtype=float)
  for day in SNAPSHOTS:
   d=pd.Timestamp(day);was=old.loc[(sid,day)];now=bool(u.loc[d]);assert now==bool(was.qualified_U_t),(sid,day,'old U_t mismatch')
   if now:assert bool(x['above'].loc[d])==bool(was.above_sma20_T),(sid,day,'old current breadth mismatch')
   snaprows.append(dict(sid=sid,date=day,sector_id_static=sec,qualified_U_t=now,
       above20_t=bool(x['above'].loc[d])if now else None,above20_tminus5=bool(x['above5'].loc[d])if now else None))
  if i in sample:
   for day in SNAPSHOTS:
    cutcal=calendar[calendar<=day];small=stock_state(s.loc[:day],cutcal)
    for k in x:
     pd.testing.assert_series_equal(small[k],x[k].loc[cutcal],check_exact=True)
    prefix.append(dict(sid=sid,date=day,exact=True))
  if(i+1)%200==0:
   p=dict(status='RUNNING',stocks_completed=i+1,stocks_required=len(sm),seconds=time.monotonic()-begun);save('PROGRESS.json',p);print(json.dumps(p),flush=True)
 pieces=[];flow5pool=agg['flow5'].sum(axis=0);flow20pool=agg['flow20'].sum(axis=0)
 for r in im:
  sec=r['series'];si=sidpos[sec];g=pq(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id']).reindex(calendar)
  I=g.close;seg=g.segment_id;M=market.close.reindex(calendar);valid=pos(I)&seg.notna()&pos(M)
  f=pd.DataFrame(index=calendar);f['sector_id_static']=sec;f['industry_static']=names[sec]
  for h in(5,20):f['rs_ind'+str(h)]=(np.log(I/I.shift(h))-np.log(M/M.shift(h))).where(complete(valid,seg,h+1))
  for dest,src in [('N_U_t','N_U'),('N25valid','N25'),('Nobserved','Nobs'),('N_above20_t','Nup'),('N_above20_tminus5','Nup5'),
      ('U_joiners1','entrants1'),('U_leavers1','leavers1'),('N_U_previous5','prev5'),('N_U_intersection_previous5','pair5'),('U_joiners5','entrants5'),('U_leavers5','leavers5')]:f[dest]=agg[src][si].astype(int)
  known=f.N_U_t.gt(0);f['Nstatic']=static[sec]
  f['breadth20_t']=(f.N_above20_t/f.N_U_t).where(known)
  f['breadth20_tminus5']=(f.N_above20_tminus5/f.N_U_t).where(known)
  f['delta_breadth5']=((f.N_above20_t-f.N_above20_tminus5)/f.N_U_t).where(known)
  f['B_now']=f.breadth20_t;f['B_lag5_pairedU']=f.breadth20_tminus5;f['dB5_paired']=f.delta_breadth5
  f['B_lag5_ownU']=f.breadth20_t.shift(5);f['dB5_ownU']=f.breadth20_t-f.B_lag5_ownU
  f['paired_minus_own_dB5_diagnostic']=f.delta_breadth5-f.dB5_ownU
  f['Nliquid']=f.N_U_t
  f['paired_breadth_known']=known
  f['share5']=pd.Series(np.divide(agg['flow5'][si],flow5pool,out=np.full(n,np.nan),where=flow5pool>0),index=calendar).where(known)
  f['share20']=pd.Series(np.divide(agg['flow20'][si],flow20pool,out=np.full(n,np.nan),where=flow20pool>0),index=calendar).where(known)
  f['share_change_diagnostic']=f.share5/f.share20-1
  f['N_U_pool']=agg['N_U'].sum(axis=0).astype(int);f['membership_PIT_verified']=False;f['formal_PIT_opportunity']=pd.Series(pd.NA,index=calendar,dtype='boolean')
  f['phase']=np.where(f.index.year==2026,'2026H1',f.index.year.astype(str))
  f=f.reset_index(names='date');f['date']=f.date.dt.strftime('%Y-%m-%d');pieces.append(f)
 table=add_channels(pd.concat(pieces,ignore_index=True)).sort_values(['sector_id_static','date']).reset_index(drop=True)
 for field in ['CONT','START','UNION']:
  table[field+'_prevsession']=table.groupby('sector_id_static',sort=False)[field].shift(1)
 table['prevsession_date']=table.groupby('sector_id_static',sort=False).date.shift(1)
 table=table.loc[table.date.between(BEGIN,END)].sort_values(['date','sector_id_static']).reset_index(drop=True)
 snap=table.loc[table.date.isin(SNAPSHOTS)].copy();snap.to_parquet(O/'SNAPSHOTS_3D.parquet',index=False);snap.to_csv(O/'SNAPSHOTS_3D.csv',index=False)
 reports=snapshot_reports(snap);save('SNAPSHOTS_3D_COUNTS_AND_SECTORS.json',reports)
 pd.DataFrame(snaprows).to_parquet(O/'PAIRED_BREADTH_STOCKS_3D.parquet',index=False)
 # Publish first three-day evidence immediately, before the full exports.
 for day,v in reports.items():print(json.dumps(clean(dict(date=day,**v)),ensure_ascii=False),flush=True)
 table.to_parquet(O/'INDUSTRY_OPPORTUNITIES_DAILY.parquet',index=False);table.to_csv(O/'INDUSTRY_OPPORTUNITIES_DAILY.csv',index=False)
 counts=table.groupby('date').agg(CONT_count=('CONT',lambda x:int(x.eq(True).sum())),START_count=('START',lambda x:int(x.eq(True).sum())),UNION_count=('UNION',lambda x:int(x.eq(True).sum())),unknown_union=('UNION',lambda x:int(x.isna().sum())),N_U_pool=('N_U_pool','first')).reset_index()
 counts.to_csv(O/'DAILY_COUNTS.csv',index=False)
 save('SUMMARY.json',dict(complete=True,first_study_date=study[0],last_study_date=study[-1],common_sessions=len(study),industry_rows=len(table),
      static_stocks=1709,industry_indices=90,source_stocks_read=len(sm),snapshot_rows=len(snap),old_U_snapshots_bit_exact=True,old_current_breadth_snapshots_exact=True,
      prefix_checks=prefix,all_UNION_unknown=int(table.UNION.isna().sum()),
      phases=counts.assign(phase=counts.date.str[:4]).groupby('phase').agg(sessions=('date','size'),mean_CONT=('CONT_count','mean'),mean_START=('START_count','mean'),mean_UNION=('UNION_count','mean'),unknown_rows=('unknown_union','sum')).reset_index().to_dict('records'),
      no_TopK_qualification=True,share_is_diagnostic_only=True,new_accounts=0,new_CP_FSM=0,new_forward_labels=0,seconds=time.monotonic()-begun))
 save('SOURCE_SHA256.json',SOURCES);save('PROGRESS.json',dict(status='COMPLETE',sessions=len(study),industry_rows=len(table),seconds=time.monotonic()-begun))
 paths=[O/'INDUSTRY_OPPORTUNITIES_DAILY.parquet',O/'INDUSTRY_OPPORTUNITIES_DAILY.csv',O/'SNAPSHOTS_3D.parquet',O/'SNAPSHOTS_3D_COUNTS_AND_SECTORS.json',O/'PAIRED_BREADTH_STOCKS_3D.parquet',O/'DAILY_COUNTS.csv',O/'SUMMARY.json',O/'SOURCE_SHA256.json',O/'CONTRACT.txt',Path(__file__)]
 save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths})

if __name__=='__main__':main()
