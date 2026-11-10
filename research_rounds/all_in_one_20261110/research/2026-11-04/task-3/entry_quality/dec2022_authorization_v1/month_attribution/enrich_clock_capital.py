"""Thin join of original snapshots/entry intents/industry states; no new signals."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D,getcontext
import json,gzip,csv,hashlib,bisect,io
import pandas as pd
getcontext().prec=60
O=Path(__file__).parent;E=O.parents[1];R=E/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
SRC={};FR={};IF={};ST={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 if (O/n).exists():
  assert json.loads((O/n).read_text())==json.loads(json.dumps(x,ensure_ascii=False,default=str)),('preserve identical pre-error output',n)
  return
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(k,a,b)
def iso(s):return pd.Timestamp(s).isoformat()
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};IM={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
rows=read(O/'ALL_AFFECTED_LAYERS.json');rm={r['layer_in_this_book']:r for r in rows};book=read(R/'runs/BASELINE/2022_2024/pair/B.json.gz',gz=True);daily=read(R/'runs/BASELINE/2022_2024/pair/daily.jsonl.gz',gz=True,lines=True)
dm={d['at'][:10]:d for d in daily};month=[d for d in daily if d['at'][:7]=='2022-12'];cal=[d['at'] for d in daily]
def checkedframe(p,h,cols=None):
 p=Path(p);assert sha(p)==h;SRC[str(p)]=h;return pd.read_parquet(p,columns=cols)
def raw(sid,day):
 if sid not in FR:
  p=SM[sid]['refs']['facts'];FR[sid]=checkedframe(p,SM[sid]['output_sha256'][p],['raw_close'])
 f=FR[sid];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert j>=0;return D(str(f.iloc[j].raw_close))
def industry_at(sector,day):
 if sector not in ST:
  r=IM[sector];p=r['refs']['state'];f=checkedframe(p,r['output_sha256'][p]);ST[sector]=f
 f=ST[sector];z=f[f.day.astype(str)<=day];assert len(z);r=z.iloc[-1]
 return {k:(None if pd.isna(r[k]) else r[k].item() if hasattr(r[k],'item') else r[k]) for k in ['day','close','E0_valid','E0_floor','E0_episode','stage_name','attempt_id','action','receipt','receipt_id','authorization_usable']}
def industry_price(sector,day):
 if sector not in IF:
  r=IM[sector];p=r['refs']['CP1_input'];IF[sector]=checkedframe(p,r['output_sha256'][p],['close','segment_id'])
 f=IF[sector];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0;r=f.iloc[i]
 return dict(day=str(f.index[i].date()),close=D(str(r.close)),segment=str(r.segment_id))
capital={lid:dict(month_held_CLOSE_observations=0,month_previous_CLOSE_held_observations=0,CLOSE_mark_yuan_observations=Z,previous_CLOSE_mark_yuan_observations=Z,CLOSE_basis_yuan_observations=Z,previous_CLOSE_basis_yuan_observations=Z) for lid in rm}
for d in month:
 j=cal.index(d['at']);prior=daily[j-1]
 for source,field in [(d,'CLOSE'),(prior,'previous_CLOSE')]:
  value=Z
  for x in source['layers']:
   lid=x['id'];assert lid in capital;c=capital[lid];mark=D(x['qty'])*raw(x['sid'],source['at'][:10]);value+=mark
   c['month_held_CLOSE_observations' if field=='CLOSE' else 'month_previous_CLOSE_held_observations']+=1;c[field+'_mark_yuan_observations']+=mark;c[field+'_basis_yuan_observations']+=D(rm[lid]['cost'])
  eq(value,source['inventory'],'native capitaltime mark')
intent={}
for d in book['decisions']:
 for i in d['intents']:intent[iso(d['at']),i['sid'],i['role']]=i
auth={};newthin=[]
for r in rows:
 lid=r['layer_in_this_book'];i=intent[r['decision_at'],r['sid'],r['role']];a=dict(entry_key=r['key'],layer=lid,sid=r['sid'],name=r['name'],sector=r['sector'],industry=r['industry'],role=r['role'],cohort=r['cohort'],
  decision_at=r['decision_at'],actual_buy_at=r['opened'],actual_exit_at=r['closed'],actual_buycash=r['cost'],initial_qty=r['initial_qty'],
  Dec_month_wealth=r['month_components']['wealth'],Dec_realized_change=r['month_components']['real'],Dec_unrealized_change=r['month_components']['unreal'],Dec_AR_change=r['month_components']['AR'],
  pool_at_actual_fill=r['pool_at_actual_fill'],PVR_priority_score=i.get('PVR_score'),PVR_ready=i.get('PVR_ready'),original_H1_rank=i.get('original_H1_rank'),priority_rank=i.get('priority_rank'),
  original_gross_budget=i['budget'],original_share_cap=i['cap'],industry_state_at_decision=industry_at(r['sector'],r['decision_at'][:10]),
  original_entry_quote_context=r['actual_entry_quote_context'],**capital[lid])
 auth[lid]=a
 if r['cohort'].startswith('Dec_new_'):newthin.append(a)
assert len(newthin)==122
save('DEC122_CLOCK_CAPITALTIME.json',newthin);save('ALL209_CLOCK_CAPITALTIME.json',list(auth.values()))
keys=['entry_key','layer','sid','name','sector','industry','role','cohort','decision_at','actual_buy_at','actual_exit_at','actual_buycash','initial_qty','Dec_month_wealth','Dec_realized_change','Dec_unrealized_change','Dec_AR_change','pool_at_actual_fill','PVR_priority_score','original_H1_rank','priority_rank',*capital[next(iter(capital))].keys()]
f=io.StringIO(newline='');w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(newthin);expected=f.getvalue().encode()
if (O/'DEC122_CLOCK_CAPITALTIME.csv').exists():assert (O/'DEC122_CLOCK_CAPITALTIME.csv').read_bytes()==expected
else:(O/'DEC122_CLOCK_CAPITALTIME.csv').write_bytes(expected)
industries=read(O/'INDUSTRY_WEALTH.json');ip=[]
for name,g in industries:
 rs=[r for r in rows if r['industry']==name];sector=rs[0]['sector'];a=industry_price(sector,'2022-11-30');b=industry_price(sector,'2022-12-30');same=a['segment']==b['segment']
 ip.append(dict(industry=name,sector=sector,actual_month_wealth=g['month_wealth'],layers=g['layers'],stocks=g['stocks'],index_Nov30=a,index_Dec30=b,
  same_source_segment=same,industry_price_return=None if not same else b['close']/a['close']-1,
  Nov30_industry_state=industry_at(sector,'2022-11-30'),Dec30_industry_state=industry_at(sector,'2022-12-30'),
  limitation='Untradeable fixed-source industry price context; not matched-weight benchmark P&L or a future entry gate.'))
save('INDUSTRY_PRICE_AND_AUTHORIZATION_CONTEXT.json',ip)
selected=['000564.SZ','002317.SZ','601858.SH'];camps=read(O/'COMPLETE_STOCK_CAMPAIGNS.json');timeline=[]
for sid in selected:
 rs=[r for r in rows if r['sid']==sid];ev=[]
 for r in rs:
  lid=r['layer_in_this_book'];a=auth[lid];ev.append(dict(kind='known_CLOSE_decision',at=r['decision_at'],entry_key=r['key'],authorization=a))
  ev.append(dict(kind='actual_OPEN_buy',at=r['opened'],entry_key=r['key'],qty=r['initial_qty'],buycash=r['cost'],cohort=r['cohort']))
  for c in camps:
   for er in c['entries']:
    if er['key']!=r['key']:continue
    for p in er['actual_sell_parts']:
     if p['order_created_at']<='2022-12-30 15:10:00+08:00':ev.append(dict(kind='actual_exit_order_created_CLOSE',at=iso(p['order_created_at']),entry_key=r['key'],native_order_id=p['order_id'],reason=p['reason'],C=p['request_close'],I_target=p['I_target'],pre_CLOSE_layer_floor=p['pre_CLOSE_layer_floor'],industry_state_at_request=industry_at(r['sector'],p['order_created_at'][:10])))
     if p['actual_fill']<='2022-12-30 15:10:00+08:00':ev.append(dict(kind='actual_OPEN_sell_part',at=iso(p['actual_fill']),entry_key=r['key'],**p))
  ev.append(dict(kind='Nov30_known_wealth',at='2022-11-30T15:10:00+08:00',entry_key=r['key'],components=r['Nov30_components']))
  ev.append(dict(kind='Dec30_known_wealth',at='2022-12-30T15:10:00+08:00',entry_key=r['key'],components=r['Dec30_components'],month_components=r['month_components']))
 ev.sort(key=lambda x:iso(x['at']));timeline.append(dict(sid=sid,name=rs[0]['name'],month_wealth=sum((D(r['month_components']['wealth']) for r in rs),Z),events=ev,
  observed_month_start_wealth=sum((D(r['Nov30_components']['wealth']) for r in rs),Z),observed_month_end_wealth=sum((D(r['Dec30_components']['wealth']) for r in rs),Z),
  full_actual_campaigns=[c for c in camps if c['sid']==sid],
  warning='Use only event records <= requested asof when interpreting prior knowledge. Full campaign terminal P&L separately labeled and can extend beyond the month. No aftermonth fill is an inmonth event.'))
save('OLD87_THREE_MAJOR_STOCK_CLOCK_CHAINS.json',timeline)
axis=read(B/'ma63_monthly_axis_v1/TELESCOPE_PROOF.json');p=B/'ma63_monthly_axis_v1/DAILY_AXIS.csv';SRC[str(p)]=sha(p);aa=[x for x in csv.DictReader(p.open()) if x['date'][:7]=='2022-12'];assert len(aa)==22
diff=[D(x['No60_previous_close_exposure_pct'])-D(x['MA63_90_previous_close_exposure_pct']) for x in aa]
save('CAPITALTIME_AND_BENCHMARK_CHECKS.json',dict(status='PASS',Dec_actual_fills=122,actual_new_buycash=sum((D(x['actual_buycash']) for x in newthin),Z),Dec122_month_wealth=sum((D(x['Dec_month_wealth']) for x in newthin),Z),
 all209_previous_CLOSE_mark_yuan_observations=sum((x['previous_CLOSE_mark_yuan_observations'] for x in capital.values()),Z),native_days=22,
 capitaltime_definition='Yuan multiplied by native CLOSE observation count; sum of actual held fee-inclusive basis or actual raw marked value. Previous-CLOSE and same-day-CLOSE kept distinct. Not calendar days or a signal.',
 daily_exposure_exactly_equal_days=sum(d==0 for d in diff),daily_exposure_difference_min_pp=min(diff),daily_exposure_difference_max_pp=max(diff),daily_exposure_difference_mean_pp=sum(diff,Z)/22,
 no_exact_equal_exposure_control=True,new_accounts=0,new_signals=0,new_gates=0))
SRC[str(Path(__file__).resolve())]=sha(__file__);save('CLOCK_CAPITAL_SOURCE_SHA256.json',SRC)
print('DEC122 clock/capitaltime and old87 major chains complete')
