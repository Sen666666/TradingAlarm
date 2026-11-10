from pathlib import Path
import json,csv,hashlib,time,collections
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';BASE=ROOT/'TradingAlarm/runtime/market'
OLD=BASE/'update-20261027-153013-2ffe04/prepared';NEW=BASE/'update-20261030-153010-c551af/prepared';CUT=pd.Timestamp('2026-10-27');DAYS=pd.date_range('2026-10-28','2026-10-30');start=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frame(p):
 f=pd.read_parquet(p)
 if 'trade_date' in f.columns:f=f.set_index('trade_date')
 f.index=pd.to_datetime(f.index);return f
def compare(a,b,cols=None):
 cols=cols or sorted(set(a.columns)&set(b.columns));a=a.loc[a.index<=CUT,cols];b=b.loc[b.index<=CUT,cols];common=a.index.intersection(b.index);different={};samples={}
 for c in cols:
  aa=a.loc[common,c];bb=b.loc[common,c];eq=aa.eq(bb)|(aa.isna()&bb.isna());n=int((~eq).sum())
  if n:different[c]=n;samples[c]=[str(x) for x in common[~eq][:3]]
 return dict(old_rows=len(a),new_prefix_rows=len(b),missing_old_dates=len(a.index.difference(b.index)),added_historical_dates=len(b.index.difference(a.index)),different_fields=different,first_dates=samples)
def main():
 old=read(OLD/'manifest.json');new=read(NEW/'manifest.json');records={n:{x['series_id']:x for x in m['series']} for n,m in [('old',old),('new',new)]};pools={};industries={};ids=set();source={}
 for sec,p in [('TECH',RR/'tech-compound-design-20261026/proposed-pool.csv'),('DRUG',RR/'innovative-drug-local-recovery-20261028/pool.csv')]:
  rows=list(csv.DictReader(p.open()));pools[sec]=[r['symbol'] for r in rows];industries[sec]=sorted({r['sector_id'] for r in rows});ids.update(pools[sec]+industries[sec]);source[str(p)]=sha(p)
 identity=dict(old=read(OLD/'receipt.json'),new=read(NEW/'receipt.json'),before_new_economic_actions=True,roster_sha=source,series_count={'old':len(old['series']),'new':len(new['series'])});save(O/'INPUT_IDENTITY.json',identity)
 rows=[];latest=[];action_rows=[];need_fields=['open','high','low','close','volume','amount','price_eligible','volume_eligible','observed_bar','synthetic_event_bar','source_invalid']
 for sid in sorted(ids):
  for kind in ['bars','signals','facts']:
   a=OLD/kind/f'{sid}.parquet';b=NEW/kind/f'{sid}.parquet'
   if not a.exists() or not b.exists():rows.append(dict(sid=sid,kind=kind,status='missing',old_exists=a.exists(),new_exists=b.exists()));continue
   aa=frame(a);bb=frame(b);z=compare(aa,bb);rows.append(dict(sid=sid,kind=kind,status='same_prefix' if not z['different_fields'] and not z['missing_old_dates'] and not z['added_historical_dates'] else 'prefix_change',file_sha_same=sha(a)==sha(b),appended_rows=int((bb.index>CUT).sum()),**z))
   for day in DAYS:
    present=day in bb.index;v=bb.loc[day] if present else None
    r=dict(sid=sid,kind=kind,day=str(day.date()),present=present)
    if present:
     cols=need_fields if kind=='bars' else ['i_target','i_buy','i_floor','e0_ready','g_ready','factor'] if kind=='facts' else ['adjustment_factor','segment_id']
     r['missing_required']=[c for c in cols if c not in bb or pd.isna(v.get(c))]
     for c in cols+(['observed_at'] if kind=='bars' else []):
      if c in bb and not pd.isna(v.get(c)):r[c]=v[c].item() if hasattr(v[c],'item') else v[c]
    latest.append(r)
  if 'actions' not in records['old'][sid].get('adjustment',{}) or 'actions' not in records['new'][sid].get('adjustment',{}):
   action_rows.append(dict(sid=sid,applicable=False,kind=records['old'][sid]['kind'],historical_events_identical=True,new_events=[]));continue
  a=Path(records['old'][sid]['adjustment']['actions']['path']);b=Path(records['new'][sid]['adjustment']['actions']['path']);aa=read(a);bb=read(b);ea=[x for x in aa.get('events',[]) if x['effective_date']<='2026-10-27'];eb=[x for x in bb.get('events',[]) if x['effective_date']<='2026-10-27'];extra=[x for x in bb.get('events',[]) if '2026-10-27'<x['effective_date']<='2026-10-30'];action_rows.append(dict(sid=sid,same_file_sha=sha(a)==sha(b),historical_events_identical=ea==eb,old_events=len(ea),new_prefix_events=len(eb),new_events=extra,new_event_keys=sorted(set().union(*(set(x) for x in extra))) if extra else [],unresolved=bb.get('unresolved'),exact_pay_dates_certified=bb.get('exact_pay_dates_certified')))
 save(O/'PREFIX_FIELDS.json',rows);save(O/'LATEST_FIELDS.json',latest);save(O/'ACTIONS.json',action_rows)
 # H1 membership/order and every historical numeric array, not whole-file hash.
 za=np.load(OLD/'h1.npz');zb=np.load(NEW/'h1.npz');da=pd.DatetimeIndex(za['dates']);db=pd.DatetimeIndex(zb['dates']);mask_a=da<=CUT;mask_b=db<=CUT;assert da[mask_a].equals(db[mask_b]);h1={};assert np.array_equal(za['symbols'],zb['symbols'])
 for k in za.files:
  if k in ['dates','symbols']:continue
  a=za[k];b=zb[k];a=a[mask_a] if a.ndim and len(a)==len(da) else a;b=b[mask_b] if b.ndim and len(b)==len(db) else b
  h1[k]=dict(shape=list(a.shape),identical=bool(np.array_equal(a,b,equal_nan=True)))
 save(O/'H1_PREFIX.json',dict(symbols=len(za['symbols']),symbols_order_identical=True,history_dates=len(da[mask_a]),new_dates=[str(x.date()) for x in db[db>CUT]],fields=h1))
 ra=pd.read_csv(OLD/'recovery.csv',index_col=0,parse_dates=True);rb=pd.read_csv(NEW/'recovery.csv',index_col=0,parse_dates=True);market=compare(ra,rb);float_diffs={c:float((ra[c]-rb.loc[ra.index,c]).abs().max()) for c in ['market','prior_high63','breadth']};market['numeric_max_abs']=float_diffs;market['breakout_exact']=bool(ra.breakout.equals(rb.loc[ra.index,'breakout']));market['new_rows']=rb.loc[DAYS].reset_index().to_dict('records');save(O/'MARKET_PREFIX.json',market)
 # Actual L0 DRUG uses an independently frozen local clock and prepared cache.
 drugprep=RR/'innovative-drug-sfw3-20261028/prepared';drugclock=RR/'innovative-drug-local-recovery-20261028/recovery.csv';local=pd.read_csv(drugclock,index_col=0,parse_dates=True)
 actual_old=[]
 for sid in pools['DRUG']+industries['DRUG']:
  p=drugprep/'facts'/f'{sid}.parquet'
  actual_old.append(dict(sid=sid,path=str(p),exists=p.exists(),last_date=str(frame(p).index.max().date()) if p.exists() else None,new_counterpart_exists=(NEW/'facts'/f'{sid}.parquet').exists()))
 tech_cache_ok=all(r['status']=='same_prefix' for r in rows if r['sid'] in pools['TECH']+industries['TECH'] and r['kind'] in ['bars','signals','facts'])
 counts={sec:{kind:dict(required=len(pools[sec])+len(industries[sec]),new_files=sum((NEW/kind/f'{s}.parquet').exists() for s in pools[sec]+industries[sec])) for kind in ['bars','signals','facts']} for sec in pools}
 summary=dict(prefix_rows=len(rows),prefix_changes=[dict(sid=r['sid'],kind=r['kind'],details=r) for r in rows if r['status']=='prefix_change'],coverage=counts,TECH_cache_prefix_exact=tech_cache_ok,H1_all_prefix_fields_exact=all(x['identical'] for x in h1.values()),actions_all_prefix_exact=all(x['historical_events_identical'] for x in action_rows),new_action_events=[x for x in action_rows if x['new_events']],TECH_market_breakout_prefix_exact=market['breakout_exact'],DRUG_clock_path=str(drugclock),DRUG_clock_last=str(local.index.max().date()),DRUG_clock_not_same_as_TECH=True,DRUG_actual_old_cache=actual_old,calendar_dates=[str(x.date()) for x in DAYS],unknown_real_trade_fields=['dated historical/current suspension flag','actual exchange upper/lower price limits/order book','listing/delisting/ST historical point-in-time chain','corporate action first known_at','actual missing dividend paid_at/bonus sellable_at'],calculation_seconds=time.monotonic()-start)
 save(O/'SUMMARY.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ['DRUG_actual_old_cache','new_action_events','prefix_changes']},ensure_ascii=False,indent=2));print('changes',len(summary['prefix_changes']),'new_actions',len(summary['new_action_events']),flush=True)
if __name__=='__main__':main()
