from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
P=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1/run_all1709_once'
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((P/(n+'.json')).read_text())
src={str(P/(n+'.json')):sha(P/(n+'.json')) for n in ['EXACT_TRADE_JOURNAL','ACTIONS','DAY_LEDGER','SOURCE_ROUNDS','EQUITY_BRIDGES','CLAIM_LEDGER','RESULT']}
journal=read('EXACT_TRADE_JOURNAL');actions={x['execution_action_id']:x for x in read('ACTIONS')};rounds={x['round_id']:x for x in read('SOURCE_ROUNDS')}
for e in read('EQUITY_BRIDGES'):
 if e['day'][:10]<='2024-10-31':assert e['record_q']==0,e
mfile=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');src[str(mfile)]=sha(mfile);manifest={x['symbol']:x for x in json.loads(mfile.read_text())}
raw={};pos={};stockrows=[];sectorrows=[];daily=[];trade=[];qa=[]
def frame(sid):
 if sid not in raw:
  x=manifest[sid];p=next(p for p in x['source_sha256'] if p.endswith('/signal.parquet'));assert sha(p)==x['source_sha256'][p];src[p]=sha(p);raw[sid]=pd.read_parquet(p)
 return raw[sid]
for dayrec in read('DAY_LEDGER'):
 day=dayrec['day'][:10]
 if day>'2024-10-31':break
 today=[j for j in journal if j['day'][:10]==day]
 for j in today:
  rr=j['round_id'];a=actions[j['action_id']];r=rounds[rr];sgn=1 if j['side'].startswith('buy') else -1
  for layer,alloc in j['report_only_allocations'].items():
   key=(rr,layer);z=pos.setdefault(key,dict(q=0,cost=D(0),round=r,layer=layer));q=alloc['q']
   if sgn==1:z['q']+=q;z['cost']+=D(q)*D(j['exact_price'])+D(alloc['fee'])
   else:
    assert z['q']>=q
    z['cost']-=z['cost']*D(q)/D(z['q']);z['q']-=q
   assert z['q']>=0
  if day>='2024-09-02':
   nav=D(dayrec['OPEN']['NAV']);gross=D(j['q'])*D(j['exact_price']);fee=D(j['exact_whole_order_fee']);cash=sum(D(v['cash_delta']) for v in j['report_only_allocations'].values())
   trade.append(dict(day=day,industry=r['industry'],sector=r['sector'],sid=r['sid'],name=r['name'],side=j['side'],signal_day=a.get('signal_day'),shares=j['q'],proxy_price=j['exact_price'],gross=str(gross),fee=str(fee),cash_delta=str(cash),gross_pct_post_open_NAV=str(100*gross/nav),reason=a['reason'],round_id=rr,source_action_id=j['action_id']))
 if day<'2024-09-02':continue
 close=dayrec['CLOSE'];nav=D(close['NAV']);sec=defaultdict(lambda:dict(q=0,mv=D(0),cost=D(0),names=set(),rounds=set()));stocks={}
 for (rr,layer),z in pos.items():
  if not z['q']:continue
  r=z['round'];sid=r['sid'];f=frame(sid);assert pd.Timestamp(day) in f.index,(sid,day);price=D(str(f.loc[pd.Timestamp(day),'raw_close']));mv=D(z['q'])*price
  k=stocks.setdefault(sid,dict(day=day,industry=r['industry'],sector=r['sector'],sid=sid,name=r['name'],shares=0,market_value=D(0),remaining_buy_cost_with_fee=D(0),close_price=price,core_q=0,add_q=0))
  k['shares']+=z['q'];k['market_value']+=mv;k['remaining_buy_cost_with_fee']+=z['cost'];k[layer+'_q']+=z['q']
  s=sec[r['sector']];s['industry']=r['industry'];s['mv']+=mv;s['cost']+=z['cost'];s['names'].add(sid);s['rounds'].add(rr)
 total=sum((s['mv'] for s in sec.values()),D(0));diff=total-D(close['gross_inventory']);assert abs(diff)<D('0.00000001'),(day,diff)
 assert D(close['cash'])+total+D(close['receivable'])==nav,(day,'NAV bridge')
 for z in stocks.values():
  z['weight_pct_NAV']=100*z['market_value']/nav;stockrows.append({k:str(v) if isinstance(v,D) else v for k,v in z.items()})
 for sid,z in sec.items():sectorrows.append(dict(day=day,sector=sid,industry=z['industry'],stocks=len(z['names']),market_value=str(z['mv']),remaining_buy_cost_with_fee=str(z['cost']),weight_pct_NAV=str(100*z['mv']/nav),names=';'.join(sorted(z['names']))))
 daily.append(dict(day=day,NAV=close['NAV'],cash=close['cash'],receivable=close['receivable'],gross_inventory=str(total),stock_weight_pct=str(100*total/nav),cash_weight_pct=str(100*D(close['cash'])/nav),receivable_weight_pct=str(100*D(close['receivable'])/nav),held_stocks=len(stocks),held_industries=len(sec),live_rounds=close['live_rounds'],buy_core=sum(j['side']=='buy_core' for j in today),buy_add=sum(j['side']=='buy_add' for j in today),sell_add=sum(j['side']=='sell_add' for j in today),sell_all=sum(j['side']=='sell_all' for j in today),certified=close['certified'],unknown=json.dumps(close['unknown'],ensure_ascii=False),fees=str(sum((D(j['exact_whole_order_fee']) for j in today),D(0)))))
 qa.append(dict(day=day,inventory_difference=str(diff),NAV_bridge_difference=str(D(close['cash'])+total+D(close['receivable'])-nav)))
for name,rows in [('DAILY_ACCOUNT',daily),('DAILY_SECTOR_POSITIONS',sectorrows),('DAILY_STOCK_POSITIONS',stockrows),('EXACT_ACTIONS',trade),('QA',qa)]:pd.DataFrame(rows).to_csv(O/(name+'.csv'),index=False)
out={p.name:sha(p) for p in O.glob('*.csv')};(O/'SOURCE_HASHES.json').write_text(json.dumps(src,indent=2));(O/'OUTPUT_SEAL.json').write_text(json.dumps(dict(outputs=out,days=len(daily),trades=len(trade),stock_rows=len(stockrows),sector_rows=len(sectorrows),max_inventory_error=max(abs(D(z['inventory_difference'])) for z in qa).__str__(),source_unchanged=all(sha(p)==h for p,h in src.items()),new_economic_runs=0,account='all1709 original shared M3 A+B autumn birth cohort, no B1'),ensure_ascii=False,indent=2))
lines=['924原M3 A+B共享账户逐日时间线','口径：原all1709共享秋季出生cohort；2024/9/2从120万元空仓开始，只开放9月至12月原A/B新生邀请。不是旧PVR、不是科技407分支，也不是新B1。','所有仓位百分比分母为当天收盘NAV，现金+股票市值+应收权益=100%；不是股票内部归一化，也不是最初120万元。剩余成本是未卖份额分摊的原买入价款加买费，与市值不同。','成交为旧账OPEN±5bp条件代理，不证明真实撮合；本次仅提取旧账，没有新跑账户。期内现金权益应收与逐日数量已核，逐股市值汇总与原总账误差小于1e-8元。','']
tr=pd.DataFrame(trade);sp=pd.DataFrame(stockrows);sc=pd.DataFrame(sectorrows)
for d in daily:
 day=d['day'];lines += [f"{day} 收盘：NAV {float(d['NAV']):,.2f}元；现金{float(d['cash']):,.2f}元（{float(d['cash_weight_pct']):.2f}%）；股票{float(d['gross_inventory']):,.2f}元（{float(d['stock_weight_pct']):.2f}%），{d['held_stocks']}股/{d['held_industries']}行业。"]
 tt=tr[tr.day.eq(day)]
 if tt.empty:lines.append('当日无买卖。')
 for z in tt.itertuples():lines.append(f"  {dict(buy_core='首买',buy_add='追加',sell_add='卖追加层',sell_all='全平')[z.side]} {z.industry} {z.name} {z.sid} {z.shares}股 × {z.proxy_price}元；价款{float(z.gross):,.2f}，费用{float(z.fee):.2f}；"+(f"原信号收盘{z.signal_day}。" if isinstance(z.signal_day,str) else '追加/退出原规则。'))
 lines.append('行业收盘仓位：'+'；'.join(f"{z.industry} {float(z.market_value):,.2f}元/{float(z.weight_pct_NAV):.2f}%" for z in sc[sc.day.eq(day)].sort_values('market_value',key=lambda x:x.astype(float),ascending=False).itertuples()))
 lines.append('具体持仓：'+'；'.join(f"{z.name} {z.sid} {z.shares}股（首层{z.core_q}+追加{z.add_q}），市值{float(z.market_value):,.2f}，占NAV{float(z.weight_pct_NAV):.3f}%" for z in sp[sp.day.eq(day)].sort_values('market_value',key=lambda x:x.astype(float),ascending=False).itertuples()))
 lines.append('')
(O/'924共享账户逐日实录.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(days=len(daily),trades=len(trade),stocks=len(raw),max_error=max(abs(D(z['inventory_difference'])) for z in qa).__str__()),ensure_ascii=False))
print(sc[sc.day.isin(['2024-09-24','2024-10-08'])].to_string(index=False))
