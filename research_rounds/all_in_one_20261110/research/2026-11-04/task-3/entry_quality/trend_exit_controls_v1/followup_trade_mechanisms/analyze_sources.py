"""Thin attribution of existing completed native outputs; no strategy execution."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,importlib.util,bisect
import pandas as pd
import numpy as np

getcontext().prec=60
O=Path(__file__).parent;ROOT=O.parent;E=ROOT.parent
V=ROOT/'execution_review/account_comparison/results_v2'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);SRC={};FF={};CTX={};SM={}
ARMS=['EARLY_EMA20','EARLY_BOLL20_MID']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,why):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(why,a,b)
def iso(t):return pd.Timestamp(t).isoformat()
def frow(sid,day):
 if sid not in FF:
  p=Path(SM[sid]['refs']['facts']);h=sha(p);assert h==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
  FF[sid]=pd.read_parquet(p,columns=['close','raw_close','factor','segment_id','i_target','i_floor','e0_target','e0_floor'])
 f=FF[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0
 return f.iloc[i],str(f.index[i].date())
SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
META=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
spec=importlib.util.spec_from_file_location('mechanism_readonly_indicators',ROOT/'indicator_provider.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);provider=mod.IndicatorProvider();SRC[str(ROOT/'indicator_provider.py')]=sha(ROOT/'indicator_provider.py');im=read(ROOT/'indicators/MANIFEST.json');SRC[im['data_file']]=sha(im['data_file']);assert SRC[im['data_file']]==im['data_sha256']
MATRIX=read(V/'PERIOD_ACCOUNT_MATRIX.json');MM={(x['arm'],x['window'],x['period']):x for x in MATRIX}

def load(arm,window):
 r=ROOT/'runs'/arm/window;book=read(r/'pair/B.json.gz',gz=True);daily=read(r/'pair/daily.jsonl.gz',gz=True,lines=True)
 rows=read(V/(arm+'_'+window+'_LAYERS.json'));camps=read(V/(arm+'_'+window+'_STOCK_CAMPAIGNS.json'))
 logs=[] if arm=='BASELINE' else read(r/'pair/trend-exit-policy.jsonl.gz',gz=True,lines=True)
 pp=defaultdict(list)
 for x in logs:
  for lid in x['added_indicator_layer_ids']:pp[lid].append(x)
 return dict(arm=arm,window=window,book=book,daily=daily,dmap={iso(x['at']):x for x in daily},dtime=[iso(x['at']) for x in daily],
  rows=rows,bykey={x['key']:x for x in rows},byid={x['layer_in_this_book']:x for x in rows},camps=camps,
  buys={t['layer']:t for t in book['trades'] if t['side']=='buy'},journal={j['layer']:j for j in book['journal'] if j['kind']=='real_buy_fill'},
  tools=pp,raw_layers={x['id']:x for x in book['layers']},period={})

def components_at(run,at):
 if at is None:return {x['key']:dict(real=Z,unreal=Z,AR=Z,wealth=Z) for x in run['rows']}
 at=iso(at);day=at[:10];d=run['dmap'][at];held={x['id']:x for x in d['layers']};out={}
 for r in run['rows']:
  lid=r['layer_in_this_book']
  if r['opened']>at:real=unreal=ar=Z
  elif r['closed'] is not None and r['closed']<=at:real=D(run['raw_layers'][lid]['cash']);unreal=Z;ar=D(run['raw_layers'][lid]['dividend'])
  else:
   x=held[lid];eq(x['cash'],-D(r['cost']),'No partial spans fixed year boundary');q,qd=frow(r['sid'],day)
   real=Z;unreal=D(x['qty'])*D(str(q.raw_close))-D(r['cost']);ar=D(x['dividend'])
  out[r['key']]=dict(real=real,unreal=unreal,AR=ar,wealth=real+unreal+ar)
 eq(sum((v['wealth'] for v in out.values()),Z),D(d['nav'])-D(1000000),'boundary layer wealth')
 return out

def period_values(run):
 if run['window']=='strong':
  run['period']['strong']={r['key']:dict(real=D(r['strict_realized']),unreal=D(r['open_unrealized']),AR=D(r['AR']),wealth=D(r['net'])) for r in run['rows']};return
 bounds=[None,'2022-12-30T15:10:00+08:00','2023-12-29T15:10:00+08:00','2024-12-31T15:10:00+08:00'];comp=[components_at(run,b) for b in bounds]
 for j,y in enumerate(['2022','2023','2024']):
  rr={k:{m:comp[j+1][k][m]-comp[j][k][m] for m in ['real','unreal','AR','wealth']} for k in run['bykey']};run['period'][y]=rr
  m=MM[run['arm'],run['window'],y]
  for key,field in [('wealth','net_wealth_change'),('real','strict_realized_change'),('unreal','open_unrealized_change'),('AR','AR_change')]:eq(sum((v[key] for v in rr.values()),Z),m[field],('calendar layer sum',run['arm'],y,key))

def state(run,lid,at,indicator):
 key=(run['arm'],run['window'],lid,iso(at),indicator)
 if key in CTX:return CTX[key]
 sid=run['byid'][lid]['sid'];f,qd=frow(sid,iso(at)[:10]);at=iso(at);d=run['dmap'].get(at);h=None if d is None else next((x for x in d['layers'] if x['id']==lid),None)
 ix=bisect.bisect_left(run['dtime'],at)-1;prev=run['daily'][ix] if ix>=0 else None
 pre=None if prev is None else next((x for x in prev['layers'] if x['id']==lid),None)
 oldfloor=pre['floor'] if pre is not None else run['buys'][lid]['floor']
 ind=provider.at(sid,at,indicator)
 r=dict(at=at,source_quote_day=qd,causal_close=str(f.close),I_target=bool(f.i_target),I_floor=None if not np.isfinite(f.i_floor) else str(f.i_floor),
  E0_target=bool(f.e0_target),E0_floor=None if not np.isfinite(f.e0_floor) else str(f.e0_floor),native_ACT_on=None if d is None else d['on'],
  original_pre_CLOSE_layer_floor=oldfloor,pre_floor_source='prior native held CLOSE' if pre is not None else 'actual entry frozen floor',
  close_at_or_below_pre_CP_layer_floor=(D(str(f.close))<=D(oldfloor)) if run['byid'][lid]['role']=='mobile' else None,
  native_post_CLOSE_layer_floor=None if h is None else h['floor'],indicator=ind,
  indicator_below=(ind['causal_close']<ind['line']) if ind['status']=='READY' else None,
  indicator_is_actual_exit_rule_in_this_arm=run['arm']!='BASELINE')
 CTX[key]=r;return r

def detail(run,key,indicator):
 r=run['bykey'][key];lid=r['layer_in_this_book'];b=run['buys'][lid];j=run['journal'][lid]
 sells=[]
 for p in r['actual_sale_parts']:
  sells.append(dict(p,request_state=state(run,lid,p['order_created_at'],indicator)))
 return dict(entry_key=key,sid=r['sid'],name=META[r['sid']]['name'],arm=run['arm'],role=r['role'],action=r['actual_entry_action'],pool_at_actual_fill=j['pool'],
  receipt=r['receipt'],decision_at=r['decision_at'],actual_buy_at=r['opened'],actual_exit_at=r['closed'],initial_qty=r['initial_qty'],remaining_qty=r['qty'],
  actual_buy_raw_open=b['raw_open'],actual_buy_price=b['price'],buy_gross=b['gross_cny'],buy_fee=b['fees_cny'],cost=r['cost'],
  terminal_strict_realized=r['strict_realized'],terminal_open_mark=r['open_unrealized'],terminal_AR=r['AR'],terminal_net=r['net'],
  decision_state=state(run,lid,r['decision_at'],indicator),actual_sell_parts=sells,
  native_tool_requests=run['tools'].get(lid,[]),watch_epoch=r['watch_epoch'],budget_order=r['budget_order'],
  other_actual_entry_keys_same_stock=[x['key'] for x in run['rows'] if x['sid']==r['sid'] and x['key']!=key])

def select(rows,field,n=5):
 return dict(positive=sorted([r for r in rows if r[field]>0],key=lambda x:x[field],reverse=True)[:n],
  negative=sorted([r for r in rows if r[field]<0],key=lambda x:x[field])[:n])

def compare(base,run,period):
 bv=base['period'][period];av=run['period'][period];indicator=run['arm'][6:];g={'matched':[],'new_entry_key':[],'baseline_entry_missing':[]}
 bsids={x['sid'] for x in base['rows']};asids={x['sid'] for x in run['rows']}
 for key in sorted(bv.keys()|av.keys()):
  b=bv.get(key);a=av.get(key);kind='matched' if b is not None and a is not None else 'new_entry_key' if a is not None else 'baseline_entry_missing'
  effect=(a['wealth'] if a else Z)-(b['wealth'] if b else Z);sid=(run['bykey'][key] if a else base['bykey'][key])['sid']
  g[kind].append(dict(key=key,sid=sid,name=META[sid]['name'],period=period,kind=kind,period_effect=effect,baseline_period=b,candidate_period=a,
   new_key_stock_also_traded_by_baseline=sid in bsids,new_key_is_stock_never_traded_by_baseline=sid not in bsids))
 top={k:select(v,'period_effect') for k,v in g.items()};details={}
 for kind,signs in top.items():
  details[kind]={}
  for sign,rr in signs.items():
   dd=[]
   for r in rr:
    k=r['key'];dd.append(dict(r,baseline=None if k not in base['bykey'] else detail(base,k,indicator),candidate=None if k not in run['bykey'] else detail(run,k,indicator)))
   details[kind][sign]=dd
 stock=defaultdict(lambda:dict(baseline=Z,candidate=Z))
 for k,v in bv.items():stock[base['bykey'][k]['sid']]['baseline']+=v['wealth']
 for k,v in av.items():stock[run['bykey'][k]['sid']]['candidate']+=v['wealth']
 ss=[dict(sid=s,name=META[s]['name'],**v,delta=v['candidate']-v['baseline']) for s,v in stock.items()]
 st=select(ss,'delta');st_details={}
 for sign,rr in st.items():
  st_details[sign]=[]
  for s in rr:
   camps={}
   for label,source,values in [('baseline',base,bv),('candidate',run,av)]:
    cc=[]
    for c in source['camps']:
     if c['sid']!=s['sid']:continue
     keys=c['entry_keys'];pc=sum((values[k]['wealth'] for k in keys),Z)
     if not pc and not any(values[k]['wealth'] for k in keys):continue
     cc.append(dict(c,period_contribution=pc,entries=[detail(source,k,indicator) for k in keys]))
    camps[label]=cc
   st_details[sign].append(dict(s,actual_stock_campaigns=camps,matching='Actual campaigns listed independently; no forced one-to-one campaign correspondence.'))
 summary={k:dict(entries=sum(r['period_effect']!=0 for r in v),effect=sum((r['period_effect'] for r in v),Z)) for k,v in g.items()}
 total=sum((x['effect'] for x in summary.values()),Z);m=MM[run['arm'],run['window'],period];bm=MM['BASELINE',run['window'],period];eq(total,D(m['net_wealth_change'])-D(bm['net_wealth_change']),'period comparison bridge')
 summary.update(account_delta=total,baseline_period_wealth=bm['net_wealth_change'],candidate_period_wealth=m['net_wealth_change'],
  candidate_new_key_entries_on_existing_baseline_stocks=sum(r['sid'] in bsids and r['period_effect']!=0 for r in g['new_entry_key']),
  candidate_new_key_entries_on_stock_absent_baseline=sum(r['sid'] not in bsids and r['period_effect']!=0 for r in g['new_entry_key']))
 return dict(arm=run['arm'],window=run['window'],period=period,summary=summary,top_layer_effects=details,top_actual_stock_aggregates=st_details,
  limits='Actual-calendar endpoint decomposition, not pure exit causality. Same-key quantities/cost may differ; new entry key can be an add/reentry in a stock already traded by baseline. No account execution.')

def cash_chains(base,run):
 new=[r for r in run['rows'] if r['key'] not in base['bykey'] and D(r['net'])>0];new.sort(key=lambda r:D(r['net']),reverse=True)
 audit=run['book']['audit'];fillidx={a['receipt']['receipt_id']:i for i,a in enumerate(audit) if a['kind']=='fill'}
 reserve={a['order_id']:(i,a) for i,a in enumerate(audit) if a['kind']=='reserve'}
 settle={a['settlement']['settlement_id']:(i,a) for i,a in enumerate(audit) if a['kind']=='settle'}
 chains=[];seen_days=set()
 for target in new:
  lid=target['layer_in_this_book'];buy=run['buys'][lid];at=buy['at'];day=at[:10]
  if day in seen_days:continue
  sellers=[t for t in run['book']['trades'] if t['at']==at and t['side']=='sell' and any(p['reason'].startswith('trend_early_') for p in t['parts'])]
  if not sellers:continue
  bi=fillidx[buy['receipt_id']];oid=audit[bi]['order_id'];ri,res=reserve[oid]
  rel=[]
  for t in sellers:
   fi=fillidx[t['receipt_id']];si,se=settle[t['settlement_id']];assert fi<si<ri<bi,(run['arm'],day,'cash release order')
   rel.append(dict(sid=t['security_id'],name=META[t['security_id']]['name'],actual_sell_at=t['at'],gross=t['gross_cny'],fee=t['fees_cny'],net=D(t['gross_cny'])-D(t['fees_cny']),
    audit_fill_index=fi,audit_settle_index=si,settle_event=se,parts=[dict(p,full_entry_key=run['byid'][p['layer']]['key'],tool_requests=run['tools'].get(p['layer'],[])) for p in t['parts']]))
  ix=bisect.bisect_left(run['dtime'],iso(at))-1;prior=run['daily'][ix];today=next(d for d in run['daily'] if d['at'][:10]==day)
  trades=[t for t in run['book']['trades'] if t['at'][:10]==day];allsell=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in trades if t['side']=='sell'),Z);allbuy=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in trades if t['side']=='buy'),Z)
  eq(D(prior['available'])+allsell-allbuy,today['available'],'actual daily spendable cash bridge')
  chains.append(dict(arm=run['arm'],window=run['window'],day=day,actual_tool_sales_released_before_target_reserve=rel,
   target_new_entry=detail(run,target['key'],run['arm'][6:]),target_reserve_event=res,audit_target_reserve_index=ri,audit_target_fill_index=bi,
   previous_CLOSE_available=prior['available'],all_actual_day_sell_net=allsell,all_actual_day_buycash=allbuy,end_CLOSE_available=today['available'],
   other_actual_day_buy_keys=[r['key'] for r in run['rows'] if r['opened'][:10]==day and r['key']!=target['key']],
   caution='Native audit establishes sell-fill -> settled cash -> target reserve -> target fill order only. Cash is fungible, existing cash and other sales also fund the day; freed sector/pool/risk capacity and competing orders also change. No unique earmarking or counterfactual necessity claim.'))
  seen_days.add(day)
  if len(chains)==2:break
 assert len(chains)>=2,(run['arm'],'Need two actual same-OPEN ordered cash examples')
 return chains

SUM={};TOP={};CHAINS=[]
for window in ['2022_2024','strong']:
 base=load('BASELINE',window);period_values(base)
 for arm in ARMS:
  run=load(arm,window);period_values(run)
  for period in (['2022','2023','2024'] if window=='2022_2024' else ['strong']):
   x=compare(base,run,period);save(arm+'_'+period+'_TOP_TRADES_AND_CAMPAIGNS.json',x);SUM[arm+'|'+period]=x['summary'];TOP[arm+'|'+period]=x
  if window=='strong':CHAINS+=cash_chains(base,run)
save('PERIOD_LAYER_PATH_SUMMARY.json',SUM);save('ACTUAL_CASH_RELEASE_CHAINS.json',CHAINS)
save('VALIDATION.json',dict(status='PASS',completed_comparisons=len(SUM),cash_release_chains=len(CHAINS),period_components_checked=['strict realized','open unrealized','recognized AR','net wealth'],
 native_calendar_boundary_wealth_all_exact=True,full_entry_key_not_cross_arm_layerID=True,new_accounts=0,new_account_steps=0,new_rules=0,
 limitations=['Existing ten completed-account experiment only; this followup reads BASELINE/EMA20/MID six paths.','No causal allocation of money to specific subsequent trades. No claim new key is new stock.','Every annual figure is actual year-boundary wealth, not terminal P&L grouped by entry year.','Partial layers are already fully closed before all year boundaries; no unknown basis is forced to zero.']))
SRC[str(Path(__file__).resolve())]=sha(__file__);save('SOURCE_SHA256.json',SRC)
save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print(json.dumps(SUM,ensure_ascii=False,default=str));print('CASH_CHAINS',[(x['arm'],x['day'],x['target_new_entry']['name'],x['target_new_entry']['terminal_net']) for x in CHAINS])
