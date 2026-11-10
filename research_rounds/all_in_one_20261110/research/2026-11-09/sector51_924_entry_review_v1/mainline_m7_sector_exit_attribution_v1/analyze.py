
import json, hashlib
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');P=R/'mainline_m7_downturn_cash_batch_v6/once_20241031'
rd=lambda p:json.loads(Path(p).read_text())
orders=rd(P/'ORDERS.json');hold=rd(P/'HOLDINGS.json');sec=rd(P/'SECTOR_DAILY.json')
ss=['软件与IT服务','半导体'];A='2024-10-08';E='2024-10-31'
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
m={x['symbol']:x for x in rd(mp)}
sources=[Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json'),R/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json',R/'joint51_candidate_v9_facts/ADDITIONAL_REVIEWED_EVENTS.json',R/'retained_20241010_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20241010_TWO_V1.json']
for x in rd(P.parent/'REVIEWED_BATCH_MANIFEST.json')['adapters']:
 p=Path(x['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'];sources.append(p)
events={(x['sid'],x['ex_date']):x for p in sources for x in rd(p)}
hashes={str(p):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime':p.stat().st_mtime} for p in sources+[mp,P/'ORDERS.json',P/'HOLDINGS.json',P/'SECTOR_DAILY.json',P/'ATTEMPTS.json',P.parent/'REVIEWED_BATCH_MANIFEST.json']}
bars={}
for s in set(x['sid'] for x in orders if x['sector51'] in ss):
 p=Path(next(p for p in m[s]['source_sha256'] if p.endswith('/signal.parquet')))
 h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m[s]['source_sha256'][str(p)]
 hashes[str(p)]={'sha256':h,'mtime':p.stat().st_mtime}
 bars[s]=pd.read_parquet(p)
def value(s,q,start,end,open_end=False):
 b=bars[s];ent=D(0)
 for dt,r in b.loc[start:end].iterrows():
  day=str(dt.date());prev=b[b.index<dt].iloc[-1]
  assert r.observed_bar and r.price_eligible and not r.source_invalid and not r.synthetic_event_bar,(s,day,'quote')
  assert tuple(str(r[c]) for c in ['source_kind','source_path','segment_id'])==tuple(str(prev[c]) for c in ['source_kind','source_path','segment_id']),(s,day,'origin')
  ev=events.get((s,day))
  if abs(D(str(r.adjustment_factor))/D(str(prev.adjustment_factor))-1)>D('1e-11'):
   assert ev,(s,day,'event missing')
   assert abs(D(str(prev.adjustment_factor))*D(str(prev.raw_close))/(D(str(prev.raw_close))-D(ev['d_source']))/D(str(r.adjustment_factor))-1)<D('1e-11')
  if ev and ev['record_date']>=start:ent+=q*D(ev['d_cash'])*D('.8')
 r=b.loc[pd.Timestamp(end)]
 return q*D(str(r.raw_open if open_end else r.raw_close))+ent
anchor=[]
for sector in ss:
 hh=[x for x in hold if x['sector51']==sector and x['day']==A]
 mv=sum((D(x['market_value']) for x in hh),D(0));final=sum((value(x['sid'],x['qty'],A,E) for x in hh),D(0))
 a=next(x for x in sec if x['sector51']==sector and x['day']==A);z=next(x for x in sec if x['sector51']==sector and x['day']==E)
 actual=D(z['marked_net_pnl'])-D(a['marked_net_pnl'])
 anchor.append(dict(sector=sector,stocks=len(set(x['sid'] for x in hh)),anchor_market=mv,passive_end_value=final,passive_pnl=final-mv,actual_pnl=actual,passive_minus_actual=final-mv-actual))
exits=[]
for x in orders:
 if x['sector51'] not in ss or not x['side'].startswith('SELL'):continue
 buys=[o for o in orders if o['sid']==x['sid'] and o['side'].startswith('BUY') and o['order_seq']>x['order_seq']]
 nxt=buys[0] if buys else None;end=nxt['day'] if nxt else E
 v=value(x['sid'],x['qty'],x['day'],end,bool(nxt));gap=v-D(x['cash_delta'])
 exits.append(dict(sector=x['sector51'],sid=x['sid'],name=x['name'],sell=x['day'],side=x['side'],reason=x['reason'],qty=x['qty'],sell_net=x['cash_delta'],next_buy=end if nxt else None,end=end,hold_value=v,hold_minus_sale=gap,reentry_qty=nxt['qty'] if nxt else None,reentry_side=nxt['side'] if nxt else None,reentry_cost=nxt['all_in_cost'] if nxt else None))
agg=[]
for sector in ss:
 for window in ['ALL','POST_1008']:
  xx=[x for x in exits if x['sector']==sector and (window=='ALL' or x['sell']>A)]
  agg.append(dict(sector=sector,window=window,sale_orders=len(xx),missed_gains=sum((x['hold_minus_sale'] for x in xx if x['hold_minus_sale']>0),D(0)),avoided_losses=-sum((x['hold_minus_sale'] for x in xx if x['hold_minus_sale']<0),D(0)),net=sum((x['hold_minus_sale'] for x in xx),D(0))))
result=dict(anchor=anchor,exit_aggregate=agg,exits=exits,hashes=hashes)

result['caveats']=['固定10月8日实际持仓为主对照，不是事后挑选赢家。','逐单退出窗口止于同股首次再次买入的原始开盘价，否则10月31日收盘；正负差分别记为错过上涨/避免下跌，均为端点口径，不反映途中回撤。','逐单窗口彼此可以重叠，后续买入可能少于卖出股数；该逐单合计不是可融资、现金守恒的替代策略收益，不能与10月8日锚定对照相加。','卖出端为实际含滑点费用净所得；假设继续持仓端仅按原始价格及net80现金权益计价，不额外虚构平仓成本。','原订单名称可能为历史名称或代码占位，身份以sid为准。']
attempts=rd(P/'ATTEMPTS.json')
result['actual_attempts']=[x for x in attempts if x['sector51'] in ss and x.get('seed_day')]
result['sector_daily']=[{k:x[k] for k in ['day','sector51','state','strength','M','stocks','market_value','seeds_filled','adds_filled','sells_filled','open_rejected']} for x in sec if x['sector51'] in ss]
out=R/'mainline_m7_sector_exit_attribution_v1'
out.mkdir(exist_ok=True)
(out/'SECTOR_EXIT_ATTRIBUTION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
print(json.dumps({'anchor':anchor,'exit_aggregate':agg,'out':str(out)},ensure_ascii=False,default=str))

