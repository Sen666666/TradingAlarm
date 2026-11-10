from pathlib import Path
import gzip,json,hashlib
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent/'stock_pnl_2022';O.mkdir(exist_ok=True)
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/pair')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
a=json.load(gzip.open(B/'B.json.gz','rt'));ds=[json.loads(x)for x in gzip.open(B/'daily.jsonl.gz','rt')];ds=[x for x in ds if x['at'].startswith('2022')];end=ds[-1];zero=D(0);raw={};sources={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def get(sid):
 if sid not in raw:
  p=P/'bars'/f'{sid}.parquet';f=pd.read_parquet(p).set_index('trade_date');f.index=pd.to_datetime(f.index);raw[sid]=f;sources[str(p)]=sha(p)
 return raw[sid]
rows=[]
for x in a['layers']:
 if x.get('closed') and x['closed'][:10]<='2022-12-30':rows.append(dict(sid=x['sid'],id=x['id'],status='closed',pnl=D(x['cash'])+D(x['dividend'])))
inv=zero
for x in end['layers']:
 p=D(str(get(x['sid']).loc[:'2022-12-30'].iloc[-1].close));mark=x['qty']*p;inv+=mark;rows.append(dict(sid=x['sid'],id=x['id'],status='open',pnl=D(x['cash'])+D(x['dividend'])+mark))
assert abs(inv-D(end['inventory']))<D('1e-7')
g={}
for r in rows:g[r['sid']]=g.get(r['sid'],zero)+r['pnl']
sorted_rows=sorted(g.items(),key=lambda x:x[1]);net=sum(g.values(),zero);assert abs(net-(D(end['nav'])-D(1000000)))<D('1e-7')
pd.DataFrame([dict(rank=i+1,sid=s,pnl=str(p))for i,(s,p)in enumerate(sorted_rows)]).to_csv(O/'ALL_STOCK_NET_PNL.csv',index=False)
summary=dict(year=2022,original_initial_cash='1000000',not_new_1200000=True,stocks=len(g),losers=sum(v<0 for v in g.values()),loser_net_total=str(sum((v for v in g.values()if v<0),zero)),winners=sum(v>0 for v in g.values()),winner_net_total=str(sum((v for v in g.values()if v>0),zero)),net=str(net),ending_nav=end['nav'],inventory_rebuilt=str(inv),fees_already_included=end['fees_cny'],top10_loss=str(sum((p for s,p in sorted_rows[:10]),zero)),remaining550_net=str(sum((p for s,p in sorted_rows[10:]),zero)),top10_fraction_of_net_loss=float(sum((p for s,p in sorted_rows[:10]),zero)/net),top10=[dict(sid=s,pnl=str(p))for s,p in sorted_rows[:10]])
(O/'SUMMARY.json').write_text(json.dumps(summary,indent=2));top3=[]
for sid,annual in sorted_rows[:3]:
 r=get(sid);tr=[t for t in a['trades']if t['security_id']==sid and t['at'].startswith('2022')];bp={t['layer']:t for t in tr if t['side']=='buy'};dd=[];tt=[];q=0;cf=zero;maxopen=zero;campaign=0;campcf=zero;campstart=None;camps=[]
 for day in ds:
  date=day['at'][:10];events=[t for t in tr if t['at'][:10]==date]
  for t in events:
   if q==0 and t['side']=='buy':campaign+=1;campstart=date;campcf=zero
   delta=(-D(t['gross_cny'])-D(t['fees_cny']))if t['side']=='buy'else D(t['gross_cny'])-D(t['fees_cny']);cf+=delta;campcf+=delta;q+=t['shares']*(1 if t['side']=='buy'else -1);openvalue=q*D(t['raw_open']);maxopen=max(maxopen,openvalue)
   tt.append(dict(date=date,side=t['side'],kind=t.get('kind','mixed'),shares=t['shares'],raw_open=t['raw_open'],fill_price=t['price'],gross=t['gross_cny'],fees=t['fees_cny'],quantity_after=q,cashflow=str(delta),campaign=campaign,reason=t['reason']))
   assert q>=0
   if q==0:camps.append(dict(start=campstart,end=date,campaign=campaign,net_pnl=str(campcf)))
  live=[x for x in day['layers']if x['sid']==sid];assert q==sum(x['qty']for x in live),(sid,date,q)
  p=D(str(r.loc[:date].iloc[-1].close));basis=zero
  for x in live:
   principal=x['qty']*D(str(x['unit_cost']));b=bp[x['id']];basis+=principal*(1+D(b['fees_cny'])/D(b['gross_cny']))
  dd.append(dict(day=date,qty=q,raw_close=str(p),marked_value=str(q*p),remaining_cost=str(basis),stock_cumulative_cashflow=str(cf),stock_year_to_date_pnl=str(cf+q*p),unrealized_on_current_holdings=str(q*p-basis),pending_exit=sid in day['pending_sells']))
 assert q==0 and abs(cf-annual)<D('1e-7')
 acts=json.loads((P/'actions'/f'{sid}.json').read_text());yracts=[e for e in acts['events']if e['effective_date'].startswith('2022')];heldacts=[e for e in yracts if any(c['start']<=e['effective_date']<=c['end']for c in camps)]
 assert not heldacts
 costs=max(dd,key=lambda x:D(x['remaining_cost']));marks=max(dd,key=lambda x:D(x['marked_value']));pnlpk=max(dd,key=lambda x:D(x['stock_year_to_date_pnl']))
 item=dict(sid=sid,annual_pnl=str(annual),buy_orders=sum(t['side']=='buy'for t in tr),sell_orders=sum(t['side']=='sell'for t in tr),cumulative_buy_gross=str(sum((D(t['gross_cny'])for t in tr if t['side']=='buy'),zero)),fees=str(sum((D(t['fees_cny'])for t in tr),zero)),max_close_marked_value=marks['marked_value'],max_close_value_day=marks['day'],max_remaining_cost=costs['remaining_cost'],max_cost_day=costs['day'],max_after_trade_open_mark=str(maxopen),campaigns=camps,corporate_actions_2022=yracts,corporate_actions_during_holdings=heldacts,raw_vs_adjustment='PnL from raw-currency fill cashflows and actual shares; adjusted indicator floor never multiplied directly by raw shares')
 top3.append(item);pd.DataFrame(tt).to_csv(O/f'{sid}_TRADES.csv',index=False);pd.DataFrame(dd).to_csv(O/f'{sid}_DAILY.csv',index=False)
 (O/f'{sid}_EVENTS.json').write_text(json.dumps(dict(trades=tr,exit_audit=[x for x in a['audit']if x.get('sid')==sid and x.get('at','').startswith('2022') and ('exit' in x['kind']or'sell'in x['kind'])]),ensure_ascii=False,indent=2))
 sources[str(P/'actions'/f'{sid}.json')]=sha(P/'actions'/f'{sid}.json')
(O/'TOP3_SUMMARY.json').write_text(json.dumps(top3,ensure_ascii=False,indent=2));sources[str(B/'B.json.gz')]=sha(B/'B.json.gz');sources[str(B/'daily.jsonl.gz')]=sha(B/'daily.jsonl.gz');(O/'SOURCE_SHA256.json').write_text(json.dumps(sources,indent=2))
print(json.dumps(summary,indent=2));print(json.dumps(top3,ensure_ascii=False,indent=2))
