"""Saved-label matching and saved-journal classification; no execution engine calls."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,time,collections,bisect,math
import pandas as pd

O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
P=W/'opportunity-quality-ranking-20261031'
META=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def enc(x):
 if isinstance(x,D):return str(x)
 if hasattr(x,'item'):return x.item()
 raise TypeError(type(x).__name__)
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=enc)+'\n');t.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def sign(x):return 'unknown' if x is None else 'positive' if x>0 else 'negative' if x<0 else 'zero'
def simple_stats(rs,h):
 vs=[x['labels'][str(h)] for x in rs if x['labels'][str(h)]['valid']];a=[x['return_pct'] for x in vs]
 return dict(events=len(rs),stocks=len({x['sid'] for x in rs}),dates=len({x['day'] for x in rs}),labelled=len(a),censored=len(rs)-len(a),mean=sum(a)/len(a) if a else None,median=pd.Series(a,dtype=float).median() if a else None,positive=sum(x>0 for x in a)/len(a) if a else None,MAE_mean=sum(x['MAE_pct'] for x in vs)/len(vs) if vs else None,MFE_mean=sum(x['MFE_pct'] for x in vs)/len(vs) if vs else None)
def first_later():
 out=[]
 for win in ['2022','2025_26']:
  rs=rows(P/win/'CANDIDATES.jsonl.gz');labels={(x['sid'],x['day'],x['receipt']):x['labels'] for x in rows(P/win/'PRICE_LABELS.jsonl.gz')}
  for r in rs:r['labels']=labels[r['sid'],r['day'],r['receipt']]
  for scope in ['all_including_inherited','complete_attempts_only']:
   use=[r for r in rs if scope=='all_including_inherited' or not r['attempt_inherited']]
   for match in ['day_stage','day_industry_attempt_exact_age']:
    groups=collections.defaultdict(list)
    for r in use:groups[(r['day'],r['industry_stage']) if match=='day_stage' else (r['day'],r['industry_attempt'])].append(r)
    for stage in ['all','confirmed','expanded']:
     gs={k:v for k,v in groups.items() if stage=='all' or v[0]['industry_stage']==stage}
     common={k:v for k,v in gs.items() if any(x['first_stock_attempt_in_window'] for x in v) and any(not x['first_stock_attempt_in_window'] for x in v)}
     f=[x for v in common.values() for x in v if x['first_stock_attempt_in_window']];later=[x for v in common.values() for x in v if not x['first_stock_attempt_in_window']]
     for h in [21,63]:
      contrasts=[];byday=collections.defaultdict(list)
      for k,v in common.items():
       fv=[x['labels'][str(h)]['return_pct'] for x in v if x['first_stock_attempt_in_window'] and x['labels'][str(h)]['valid']];lv=[x['labels'][str(h)]['return_pct'] for x in v if not x['first_stock_attempt_in_window'] and x['labels'][str(h)]['valid']]
       if fv and lv:
        pair=(sum(fv)/len(fv),sum(lv)/len(lv));contrasts.append(pair);byday[k[0]].append(pair)
      daily=[(sum(x[0] for x in v)/len(v),sum(x[1] for x in v)/len(v)) for v in byday.values()]
      a=sum(x[0] for x in daily)/len(daily) if daily else None;b=sum(x[1] for x in daily)/len(daily) if daily else None
      out.append(dict(window=win,scope=scope,matching=match,stage=stage,horizon=h,total_groups=len(gs),comparable_groups=len(contrasts),comparable_dates=len(daily),first=simple_stats(f,h),later=simple_stats(later,h),date_equal_first=a,date_equal_later=b,date_equal_later_minus_first=b-a if daily else None,group_equal_later_minus_first=sum(b-a for a,b in contrasts)/len(contrasts) if contrasts else None))
 save('FIRST_LATER_MATCHED.json',out)
 for r in out:
  if r['scope']=='complete_attempts_only' and r['stage']=='all':print('MATCHED',r['window'],r['matching'],r['horizon'],r['comparable_groups'],r['comparable_dates'],'later-first',r['date_equal_later_minus_first'],flush=True)
 return out

def aggregate(rs):
 return dict(layers=len(rs),stocks=len({x['sid'] for x in rs}),receipts=len({x['receipt'] for x in rs}),buy_cash=sum((n(x['actual_buy_cash']) for x in rs),Z),closed_positive=sum((n(x['net_contribution']) for x in rs if x['closed'] and n(x['net_contribution'])>0),Z),closed_negative=sum((n(x['net_contribution']) for x in rs if x['closed'] and n(x['net_contribution'])<0),Z),open_contribution=sum((n(x['net_contribution']) for x in rs if not x['closed']),Z))

def funded():
 manifests={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};price={};sources={};allout=[];totals=[]
 def fact(sid,date):
  if sid not in price:
   p=manifests[sid]['refs']['facts'];f=pd.read_parquet(p,columns=['factor','raw_close']);price[sid]=f;sources[p]=sha(p)
  f=price[sid];i=f.index.searchsorted(pd.Timestamp(date),side='right')-1
  if i<0:return None
  r=f.iloc[i]
  if not math.isfinite(float(r.raw_close)) or not math.isfinite(float(r.factor)):return None
  return dict(source_day=str(f.index[i].date()),raw_close=n(r.raw_close),factor=n(r.factor))
 for win,base in [('2022','2022-normal-reference-20261031'),('2025_26','q2-normal-continuation-20261031')]:
  root=W/base/'runs/B_diag/pair';bp=root/'B.json.gz';b=book(bp);sources[str(bp)]=sha(bp);ds=rows(root/'daily.jsonl.gz');sources[str(root/'daily.jsonl.gz')]=sha(root/'daily.jsonl.gz');dmap={day(r['at']):r for r in ds};dd=sorted(dmap)
  entrylist=read(W/'stage-progress-R-diagnostic-20261031'/win/'B_diag/ENTRIES.json');targets={x['layer']:x for x in entrylist};jl={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};meta=b['metadata'];layer={x['id']:x for x in b['layers']}
  # Quantity-only journal walk recovers true flat boundaries, no orders/strategy execution.
  split=collections.defaultdict(list)
  for a in b['audit']:
   if a['kind']=='split':split[day(a['at'])].append(a)
  q=collections.defaultdict(int);live=collections.defaultdict(set);cycles={};completed=collections.defaultdict(list);layercycle={};lastbuy={};done_days=set();result=[];checks=[]
  txdays=collections.defaultdict(list)
  for t in b['trades']:txdays[day(t['at'])].append(t)
  for date in dd:
   for a in split[date]:
    for lid in tuple(live[a['sid']]):q[lid]=int(D(q[lid])*n(a['ratio']))
   for t in txdays[date]:
    sid=t['security_id']
    if t['side']=='sell':
     for part in t['parts']:
      lid=part['layer'];q[lid]-=part['shares'];assert q[lid]>=0,(win,'negative qty',lid)
      if q[lid]==0:live[sid].discard(lid)
     if not live[sid]:
      c=cycles.pop(sid);c.update(exit_at=t['at'],exit_layers=[x['layer'] for x in t['parts']],net=sum((n(layer[k]['cash'])+n(layer[k]['dividend']) for k in c['layers']),Z));assert all(layer[k]['qty']==0 for k in c['layers']);completed[sid].append(c)
     continue
    lid=t['layer'];held=bool(live[sid]);action='add' if held else 'reentry' if completed[sid] else 'first';oldids=sorted(live[sid]);priorcycle=completed[sid][-1] if completed[sid] else None
    if not held:cycles[sid]=dict(stock=sid,start_at=t['at'],layers=[])
    layercycle[lid]=cycles[sid];cycles[sid]['layers'].append(lid)
    if lid in targets:
     e=targets[lid];j=jl[lid];ix=bisect.bisect_left(dd,date)-1;prior=dmap[dd[ix]] if ix>=0 else None;prevday=dd[ix] if ix>=0 else None;old=[];known=None
     if prior:
      stocklayers=[x for x in prior['layers'] if x['sid']==sid];f=fact(sid,prevday)
      if stocklayers and f:
       for x in stocklayers:
        line=n(x['last_core_line'] if x['role']=='core' else x['floor']);net=n(x['cash'])+n(x['dividend'])+D(x['qty'])*f['raw_close']
        old.append(dict(layer=x['id'],role=x['role'],pool=x['pool'],qty=x['qty'],cash=n(x['cash']),dividend=n(x['dividend']),raw_mark=f['raw_close'],raw_unit_cost=x['unit_cost'],adjusted_protection=line,raw_protection=line/f['factor'],economic_net=net,attempt=x['attempt'],stock_structure=x.get('stock_structure')))
       known=sum((x['economic_net'] for x in old),Z)
     cf=fact(sid,date);lb=lastbuy.get(sid);pf=fact(sid,day(lb['at'])) if lb else None;comparison=None
     if lb and cf and pf:
      now=n(t['price'])*cf['factor'];previous=n(lb['price'])*pf['factor'];comparison=dict(previous_at=lb['at'],previous_layer=lb['layer'],previous_raw_fill=n(lb['price']),previous_factor=pf['factor'],previous_same_unit_price=previous,current_raw_fill=n(t['price']),current_raw_open=n(t['raw_open']),current_factor=cf['factor'],current_same_unit_price=now,fill_below_previous=now<previous,open_below_previous=n(t['raw_open'])*cf['factor']<previous)
     m=meta[str(lid)];priorids=priorcycle['exit_layers'] if priorcycle else [];ps={meta[str(k)].get('stock_structure') for k in priorids};pa={meta[str(k)]['attempt'] for k in priorids}
     record=dict(window=win,layer=lid,sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],receipt=e['canonical_stock_receipt'],signal_day=e['signal_day'],fill_at=t['at'],actual_action=action,actual_prefill_qty=sum(q[k] for k in live[sid]),actual_prefill_layers=oldids,actual_buy_qty=t['shares'],actual_buy_cash=e['actual_buy_cash'],new_role='mobile',new_pool_at_fill='confirmed',new_adjusted_line=t['floor'],stock_structure=m.get('stock_structure'),industry_attempt=m['attempt'],known_snapshot_day=prevday,old_live_layers_at_previous_close=old,old_live_layer_economic_net=known,old_live_economic_sign=sign(known) if action=='add' else 'not_add',snapshot_caveat='previous close, not exact pre-fill; includes previous-close layers sold at this open',same_open_position_difference=sorted(oldids)!=sorted(x['layer'] for x in old),last_actual_buy_comparison=comparison,prior_completed_cycle=priorcycle if action=='reentry' else None,reentry_previous_cycle_sign=sign(priorcycle['net']) if action=='reentry' else 'not_reentry',reentry_same_stock_E0=(m.get('stock_structure') in ps) if action=='reentry' and m.get('stock_structure') is not None and None not in ps else None,reentry_same_industry_attempt=m['attempt'] in pa if action=='reentry' else None,net_contribution=e['net_contribution'],closed=e['closed'],terminal_quantity=e['terminal_quantity'])
     result.append(record)
    q[lid]+=t['shares'];live[sid].add(lid);lastbuy[sid]=t
   observed={x['id']:x['qty'] for x in dmap[date]['layers']};reconstructed={lid:qty for lid,qty in q.items() if qty};assert reconstructed==observed,(win,date,'quantity-only journal differs daily')
   checks.append(dict(day=date,quantity_difference=0))
  assert len(result)==len(entrylist) and {x['layer'] for x in result}==set(targets)
  for r in result:
   # Dates/prices in a completed prior cycle are already before the current actual buy.
   if r['prior_completed_cycle']:assert r['prior_completed_cycle']['exit_at']<=r['fill_at']
  partitions={a:aggregate([r for r in result if r['actual_action']==a]) for a in ['first','add','reentry']}
  add=[r for r in result if r['actual_action']=='add'];adds={s:aggregate([r for r in add if r['old_live_economic_sign']==s]) for s in ['positive','negative','zero','unknown']}
  re=[r for r in result if r['actual_action']=='reentry'];res={s:aggregate([r for r in re if r['reentry_previous_cycle_sign']==s]) for s in ['positive','negative','zero','unknown']}
  cross=[]
  for sg in ['positive','negative','zero','unknown']:
   for low in [True,False,None]:
    rr=[r for r in add if r['old_live_economic_sign']==sg and (r['last_actual_buy_comparison']['fill_below_previous'] if r['last_actual_buy_comparison'] else None)==low]
    cross.append(dict(old_sign=sg,below_last_actual_buy=low,**aggregate(rr)))
  total=dict(window=win,total=aggregate(result),action=partitions,adds_prior_close_sign=adds,adds_sign_by_below_last_actual_buy=cross,reentry_prior_full_exit_sign=res,reentry_same_stock_E0=collections.Counter(str(r['reentry_same_stock_E0']) for r in re),reentry_same_industry_attempt=collections.Counter(str(r['reentry_same_industry_attempt']) for r in re),prior_close_vs_actual_live_layers_differ=sum(r['same_open_position_difference'] for r in add),daily_quantity_reconciliation_days=len(checks),new_account_replays=0)
  save(win+'/ENTRIES.json',result);save(win+'/SUMMARY.json',total);save(win+'/DAILY_QUANTITY_CHECKS.json',checks);allout.extend(result);totals.append(total)
  print('FUNDED',win,'actions',json.dumps(partitions,default=enc),'ADD_SIGNS',json.dumps(adds,default=enc),flush=True)
 save('SUMMARY.json',totals);save('SOURCE_HASHES.json',sources)
 return allout,totals

def main():
 t=time.monotonic();matches=first_later();es,ts=funded();save('COMPLETION.json',dict(readonly=True,new_account_paths=0,new_indicators=0,seconds=time.monotonic()-t,funded_layers=len(es),matched_tables=len(matches)));print('DONE',time.monotonic()-t,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
