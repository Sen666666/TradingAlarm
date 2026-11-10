"""C1 saved-book evidence only: no strategy/runner import, no account replay."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,hashlib,bisect,time,csv
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
META=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
SM={x['symbol']:x for x in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
frames={};mark_cache={}
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def price(sid,d):
 if (sid,d) not in mark_cache:
  if sid not in frames:frames[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['raw_close'])
  f=frames[sid];i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0
  v=n(f.iloc[i].raw_close);assert v.is_finite() and v>0;mark_cache[sid,d]=v
 return mark_cache[sid,d]
def dd(values):
 peak=values[0][1];worst=(Z,values[0][0]);highday=values[0][0]
 for d,v in values:
  if v>peak:peak=v;highday=d
  gap=1-v/peak
  if gap>worst[0]:worst=(gap,d);peakdate=highday
 return dict(percent=worst[0]*100,day=worst[1],preceding_peak_day=locals().get('peakdate'))
def aggregate(es):
 return dict(layers=len(es),stocks=len({x['sid'] for x in es}),buy_cash=sum((x['cost'] for x in es),Z),closed_positive=sum((x['net'] for x in es if not x['qty'] and x['net']>0),Z),closed_negative=sum((x['net'] for x in es if not x['qty'] and x['net']<0),Z),open_net=sum((x['net'] for x in es if x['qty']),Z),tail_net=sum((x['net'] for x in es if x['cost'] and x['net']/x['cost']>=D('.3')),Z))
def bucket(d):return 'D0' if d==0 else 'D(0,10%)' if d<D('.1') else 'D[10%,20%)' if d<D('.2') else 'D>=20%'

def account(win,ref,root):
 b=book(root/'pair/B.json.gz');ds=rows(root/'pair/daily.jsonl.gz');byday={day(r['at']):r for r in ds};end=day(ds[-1]['at']);jr={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};cost=collections.defaultdict(lambda:Z)
 for t in b['trades']:
  if t['side']=='buy':cost[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny'])
 layers=[];stock=collections.defaultdict(lambda:Z)
 for x in b['layers']:
  val=D(x['qty'])*price(x['sid'],end) if x['qty'] else Z;net=n(x['cash'])+n(x['dividend'])+val;j=jr[x['id']];m=b['metadata'][str(x['id'])]
  r=dict(layer=x['id'],sid=x['sid'],name=META[x['sid']]['name'],industry=META[x['sid']]['industry'],sector=m['sector'],role=j['role'],pool_at_fill=j['pool'],signal_day=day(x['signal_at']),opened=x['opened'],closed=x['closed'],qty=x['qty'],cost=cost[x['id']],net=net,value=val,receipt=j['CP1_id'],attempt=m['attempt']);layers.append(r);stock[x['sid']]+=net
 assert abs(sum(stock.values(),Z)-(n(b['ending_NAV'])-D(1000000)))<D('.00000001')
 flows=collections.defaultdict(lambda:Z);div=collections.defaultdict(lambda:Z)
 for t in b['trades']:flows[t['security_id']]+=(n(t['gross_cny']) if t['side']=='sell' else -n(t['gross_cny']))-n(t['fees_cny'])
 for a in b['audit']:
  if a['kind']=='dividend_accrual':div[a['receivable']['security_id']]+=n(a['receivable']['net_local'])
 for sid in stock:
  terminal=sum((x['value'] for x in layers if x['sid']==sid),Z);assert abs(flows[sid]+div[sid]+terminal-stock[sid])<D('.00000001')
 values={}
 for r in ds:
  d=day(r['at']);values[d]={sid:D(q)*price(sid,d) for sid,q in r['positions'].items() if q};assert abs(sum(values[d].values(),Z)-n(r['inventory']))<D('.00001'),(win,ref,d,'raw mark inventory mismatch')
 checks=rows(root/'pair/balances.jsonl.gz');assert len(ds)==len(checks)==242 and all(n(r['independent_NAV_difference'])==0 and n(r['maximum_stock_quantity_difference'])==0 for r in checks)
 metrics=dict(window=win,reference=ref,return_pct=(n(b['ending_NAV'])/D(1000000)-1)*100,global_DD=dd([('initial',D(1000000))]+[(day(r['at']),n(r['nav'])) for r in ds]),mean_exposure_pct=sum((n(r['inventory'])/n(r['nav'])*100 for r in ds),Z)/len(ds),peak_exposure_pct=max(n(r['inventory'])/n(r['nav'])*100 for r in ds),mean_cash_pct=sum((n(r['available'])/n(r['nav'])*100 for r in ds),Z)/len(ds),fees=sum((n(t['fees_cny']) for t in b['trades']),Z),buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in b['trades'] if t['side']=='buy'),Z),buy_fills=sum(t['side']=='buy' for t in b['trades']),sell_fills=sum(t['side']=='sell' for t in b['trades']),paused_closes=sum(not r['on'] for r in ds),whole_layers=aggregate(layers),new_confirmed_mobile=aggregate([x for x in layers if x['role']=='mobile' and x['pool_at_fill']=='confirmed']),open_contribution=sum((x['net'] for x in layers if x['qty']),Z),terminal_inventory=ds[-1]['inventory'],terminal_dividend_receivable=ds[-1]['dividend_receivable'])
 phases=[x for x in b['audit'] if x['kind']=='risk_checkpoint'];worst=max(phases,key=lambda x:n(x['episode_drawdown']));metrics['worst_ACT_phase_DD']=dict(day=day(worst['at']),percent=n(worst['episode_drawdown'])*100,phase=worst['episode'],phase_peak=worst['peak']);metrics['ACT_events']=[r for r in phases if r.get('event')]
 quarters=[];prior=D(1000000)
 for q in sorted({str(pd.Timestamp(d).to_period('Q')) for d in byday}):
  rr=[r for r in ds if str(pd.Timestamp(day(r['at'])).to_period('Q'))==q];tx=[t for t in b['trades'] if str(pd.Timestamp(day(t['at'])).to_period('Q'))==q];quarters.append(dict(quarter=q,return_pct=(n(rr[-1]['nav'])/prior-1)*100,DD_pct=dd([('quarter_start',prior)]+[(day(r['at']),n(r['nav'])) for r in rr]),mean_exposure_pct=sum((n(r['inventory'])/n(r['nav'])*100 for r in rr),Z)/len(rr),new_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in tx if t['side']=='buy'),Z)));prior=n(rr[-1]['nav'])
 metrics['quarters']=quarters;save(Path('analysis')/win/ref/'METRICS.json',metrics);save(Path('analysis')/win/ref/'LAYERS.json',layers);save(Path('analysis')/win/ref/'STOCKS.json',[dict(sid=s,name=META[s]['name'],industry=META[s]['industry'],net=v) for s,v in sorted(stock.items(),key=lambda x:-x[1])])
 return dict(book=b,daily=ds,byday=byday,metrics=metrics,layers=layers,stock=stock,values=values,journal=jr)

def run(win):
 root=O/'runs'/win
 if not (root/'DONE.json').exists():return None
 marker=O/'analysis'/win/'COMPLETION.json';code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();book_sha=hashlib.sha256((root/'pair/B.json.gz').read_bytes()).hexdigest()
 if marker.exists() and read(marker).get('analysis_code_sha256')==code_sha and read(marker).get('C1_book_sha256')==book_sha:
  print('REUSE_SAVED_ANALYSIS',win,flush=True);return read(O/'analysis'/win/'COMPARISON.json')
 baseline=W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag'
 data={'Bdiag':account(win,'Bdiag',baseline),'C1':account(win,'C1',root)};cc=read(root/'pair/C1.json')['decisions'];cmap={day(x['at']):x for x in cc};c1=data['C1'];base=data['Bdiag'];calendar=list(c1['byday']);cindex={d:i for i,d in enumerate(calendar)}
 assert len(cc)==242
 for r in cc:
  d=day(r['at']);expected=max(D(0),D(1)-n(r['decision_nav'])/n(r['high']));assert expected==n(r['drawdown']);assert n(r['decision_nav'])==n(c1['byday'][d]['nav']);assert n(r['fraction'])==D('.1')+D('.5')*max(Z,1-expected/D('.2'))
 rows_c=[]
 for ref,a in data.items():
  for g in ['D0','D(0,10%)','D[10%,20%)','D>=20%']:
   es=[x for x in a['layers'] if x['role']=='mobile' and x['pool_at_fill']=='confirmed' and bucket(n(cmap[x['signal_day']]['drawdown']))==g];rows_c.append(dict(reference=ref,C1_calendar_DD_group=g,**aggregate(es)))
 save(Path('analysis')/win/'CONFIRMED_BUYS_ON_SAME_C1_DATES.json',rows_c)
 # Exact post-boundary wealth bridge, not full-life old-lot losses mislabeled
 # as interval losses. 10% is an existing formula anchor (c35), not a new rule.
 crossing=next((day(r['at']) for r in cc if n(r['drawdown'])>=D('.1')),None);bridges=[]
 if crossing:
  for ref,a in data.items():
   snap=a['byday'][crossing];old={x['id']:x for x in snap['layers']};parts=collections.defaultdict(lambda:Z)
   for l in a['layers']:
    before=old.get(l['layer']);oldnet=(n(before['cash'])+n(before['dividend'])+D(before['qty'])*price(l['sid'],crossing)) if before else Z
    if before:parts['held_at_first_C1_D10_close']+=l['net']-oldnet
    elif day(l['opened'])>crossing:parts['new_actual_layers_after_boundary']+=l['net']
   residual=sum(parts.values(),Z)-(n(a['book']['ending_NAV'])-n(snap['nav']));assert abs(residual)<D('.00000001');bridges.append(dict(reference=ref,boundary=crossing,parts=dict(parts),interval_NAV_change=n(a['book']['ending_NAV'])-n(snap['nav']),residual=residual))
 save(Path('analysis')/win/'FIRST_D10_POST_BOUNDARY_WEALTH_BRIDGE.json',bridges)
 # Fixed recovery anchors only; actual fills and observed commitment are
 # reported separately. No invented notion of a safe or "large" stage.
 events=[]
 for previous,r in zip(cc,cc[1:]):
  prev,cur=n(previous['fraction']),n(r['fraction']);why=[]
  if prev<=D('.35')<cur:why.append('cap_recovers_above_original_35pct_anchor')
  if prev<D('.6')==cur:why.append('new_full_history_peak_cap60')
  for kind in why:events.append(dict(day=day(r['at']),kind=kind))
 events +=[dict(day=day(r['at']),kind='original_ACT_resume') for r in c1['metrics']['ACT_events'] if r['event']=='resume']
 candidates=rows(W/'opportunity-quality-ranking-20261031'/win/'CANDIDATES.jsonl.gz');bycand=collections.Counter(r['day'] for r in candidates)
 recover=[]
 for event in events:
  d=event['day'];first=next((l for l in c1['layers'] if l['role']=='mobile' and l['pool_at_fill']=='confirmed' and l['signal_day']>=d and day(l['opened'])>d),None)
  current=n(c1['byday'][d]['pool_confirmed'][0])/n(c1['byday'][d]['nav']);later=next((r for r in c1['daily'] if first and day(r['at'])>=day(first['opened']) and n(r['pool_confirmed'][0])/n(r['nav'])>=current),None)
  recover.append(dict(**event,confirmed_weight_at_milestone=current,first_fresh_confirmed_buy=first,source_sessions_to_first_fill=cindex[day(first['opened'])]-cindex[d] if first else None,first_recovered_observed_weight_after_a_new_fill=day(later['at']) if later else None,weight_recovery_may_include_price_moves_not_pure_active_capital=True,close_cap_space=cmap[d]['cap_minus_commitment'],ACT_on=c1['byday'][d]['on'],same_day_qualified_market_candidates=bycand[d]))
 save(Path('analysis')/win/'RECOVERY_MILESTONES.json',recover)
 # Reconstruct current-attempt probe occupancy; distinguish original old-
 # attempt conservative occupancy and observed failed migration events.
 attempts=read(W/'stage-progress-R-diagnostic-20261031/ATTEMPTS.json');amap={a['market_attempt_id']:a['financial_attempt_id'] for a in attempts};im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in im};industry=rows(root/'pair/industry.jsonl.gz');unfunded={(r['day'],r['sector']) for r in industry if r['result']=='confirmed_unfunded'};migration=[]
 for d,r in c1['byday'].items():
  groups=collections.defaultdict(list)
  for x in r['layers']:
   if x['pool']=='probe':groups[x['sector']].append(x)
  for sector,ls in groups.items():
   st=states[sector][d];aid=amap.get(st['attempt_id']);eligible=[x for x in ls if st['E0_valid'] and st['stage_name'] in ('confirmed','expanded') and x['attempt']==aid];value=sum((D(x['qty'])*price(x['sid'],d) for x in eligible),Z)
   if value and float(value)+float(r['pool_confirmed'][0])>float(cmap[d]['confirmed_cap'])+1e-6:migration.append(dict(day=d,sector=sector,current_attempt_probe_value=value,current_probe_layers=[x['id'] for x in eligible],explicit_failed_industry_migration_event=(d,sector) in unfunded))
 fund=rows(root/'pair/funding.jsonl.gz');resource=[r for r in fund if any(k in str(r.get('result','')) for k in ['probe_risk','pool_capital'])];save(Path('analysis')/win/'PROBE_MIGRATION_AND_RESOURCES.json',dict(current_attempt_probe_cannot_fit_target_pool=migration,days=len({r['day'] for r in migration}),explicit_failed_industry_migration_events_with_probe=sum(r['explicit_failed_industry_migration_event'] for r in migration),peak_current_attempt_probe_value=max((r['current_attempt_probe_value'] for r in migration),default=Z),funding_records_with_probe_or_pool_reason=len(resource),unique_open_stock_role_requests=len({(day(r['at']),r['sid'],r['role']) for r in resource}),exclusive_probe_rejection_count='unknown: original failure strings merge route reasons; not an exclusive causal count'))
 metrics=dict(over_cap_closes=sum(r['over_cap'] for r in cc),max_over_cap_cny=max(max(Z,-n(r['cap_minus_commitment'])) for r in cc),minimum_c=min(n(r['fraction']) for r in cc),days_at_c10=sum(n(r['fraction'])==D('.1') for r in cc),days_at_c60=sum(n(r['fraction'])==D('.6') for r in cc),H_end=cc[-1]['high'],global_DD_equals_controller=max(n(r['drawdown']) for r in cc)*100,first_D10_day=crossing)
 for ref,a in data.items():
  ordered=sorted(a['stock'],key=a['stock'].get,reverse=True);save(Path('analysis')/win/ref/'TOP10_PATHS.json',[dict(sid=sid,name=META[sid]['name'],net=a['stock'][sid],layers=[l for l in a['layers'] if l['sid']==sid],trades=[t for t in a['book']['trades'] if t['security_id']==sid]) for sid in list(dict.fromkeys(ordered[:10]+ordered[-3:]))])
 top=sorted(base['stock'],key=base['stock'].get,reverse=True)[:10];save(Path('analysis')/win/'BASELINE_TOP10_COMPARISON.json',[dict(sid=s,name=META[s]['name'],Bdiag=base['stock'][s],C1=c1['stock'].get(s,Z)) for s in top])
 def fingerprint(t):return tuple(t.get(k) for k in ['at','security_id','side','shares','gross_cny','fees_cny'])
 left,right=base['book']['trades'],c1['book']['trades'];ix=next((i for i,(a,b) in enumerate(zip(left,right)) if fingerprint(a)!=fingerprint(b)),min(len(left),len(right)));save(Path('analysis')/win/'FIRST_ECONOMIC_DIVERGENCE.json',dict(index=ix,baseline=left[ix] if ix<len(left) else None,C1=right[ix] if ix<len(right) else None))
 if win=='2025_26':
  cases=[];calendarall=list(base['byday'])
  for sector,lo,hi in [('URFI881267','2025-07-01','2025-09-30'),('URFI881276','2025-10-01','2025-12-31'),('URFI881107','2026-01-01','2026-03-31')]:
   for ref,a in data.items():
    qs=[r for r in a['daily'] if lo<=day(r['at'])<=hi];weights=[(day(r['at']),sum((v for sid,v in a['values'][day(r['at'])].items() if META[sid]['sector_id']==sector),Z)/n(r['nav'])*100) for r in qs];buys=[t for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi and META[t['security_id']]['sector_id']==sector];confirmed=[t for t in buys if a['journal'][t['layer']]['role']=='mobile' and a['journal'][t['layer']]['pool']=='confirmed'];peak=max(weights,key=lambda x:x[1]);cases.append(dict(reference=ref,sector=sector,industry=next(v['industry'] for v in META.values() if v['sector_id']==sector),window=[lo,hi],first_actual_buy=buys[0] if buys else None,all_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),confirmed_mobile_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in confirmed),Z),actual_peak_weight_pct=peak[1],peak_day=peak[0],daily_weights=weights))
  save(Path('analysis')/win/'THREE_FROZEN_STRONG_CASES.json',cases)
 save(Path('analysis')/win/'CAP_DIAGNOSTIC.json',metrics);save(Path('analysis')/win/'COMPLETION.json',dict(passed=True,original_daily_journal_bridges=242,layer_and_stock_money_bridges=True,new_account_runs=0,C1_book_sha256=book_sha,analysis_code_sha256=code_sha))
 result=dict(window=win,Bdiag=base['metrics'],C1=c1['metrics'],cap=metrics);save(Path('analysis')/win/'COMPARISON.json',result);print('ANALYZED',win,'Bdiag/C1',str(base['metrics']['return_pct']),str(c1['metrics']['return_pct']),'overcap',metrics['over_cap_closes'],flush=True);return result

def main():
 started=time.monotonic();result=[x for w in ['2022','2025_26'] if (x:=run(w)) is not None];save('COMPARISON.json',result);save('ANALYSIS_COMPLETION.json',dict(seconds=time.monotonic()-started,windows=len(result),new_account_runs=0))
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ANALYSIS_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
