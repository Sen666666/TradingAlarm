from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O/'once_20241008';Z=D(0)
read=lambda p:json.loads(p.read_text())
def save(n,x):(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
o=read(P/'ORDERS.json');ss=read(P/'SECTOR_DAILY.json');rr=read(P/'FUNDING_REQUESTS.json');refs=read(P/'REFERENCE_DAILY.json');lots=read(P/'CAPITAL_LOTS.json');at=read(P/'ATTEMPTS.json');fund=read(P/'TRANSFERS.json');days=['2024-09-23','2024-09-27','2024-09-30','2024-10-08'];focus=['证券保险','软件与IT服务','半导体','动力电池','白酒']
def strict_bool(x):
 if x is True or x=='True':return True
 if x is False or x=='False':return False
 raise ValueError(('UNKNOWN_BOOLEAN',x))
rows=[]
for d in days:
 for sec in focus:
  sr=next(r for r in ss if r['day']==d and r['sector51']==sec);ts=[t for t in o if t['sector51']==sec and t['day']<=d];now=[t for t in ts if t['day']==d];lr=[r for r in lots if r['day']==d and r['sector51']==sec];br=[t for t in ts if t['side'].startswith('BUY')];ar=[t for t in ts if t['side']=='BUY_ADD'];neveraddrounds={r['round_id'] for r in lr if strict_bool(r['confirmed_history']) and not any(t['round_id']==r['round_id'] and t['side']=='BUY_ADD' and t['day']<=d for t in o)}
  rows.append(dict(day=d,sector51=sec,market_value=sr['market_value'],weight_pct=sr['account_weight_pct'],cumulative_sector_marked_net=sr['marked_net_pnl'],first_actual_SEED=min((t['day'] for t in br),default=None),first_actual_ADD=min((t['day'] for t in ar),default=None),cumulative_SEED_fills=sum(t['side']=='BUY_SEED' for t in ts),cumulative_ADD_fills=len(ar),day_SEED_fills=sum(t['side']=='BUY_SEED' for t in now),day_ADD_fills=sum(t['side']=='BUY_ADD' for t in now),day_SEED_buy_cost=-sum((D(t['cash_delta']) for t in now if t['side']=='BUY_SEED'),Z),day_ADD_buy_cost=-sum((D(t['cash_delta']) for t in now if t['side']=='BUY_ADD'),Z),day_donor_net=sum((D(t['cash_delta']) for t in now if t.get('transfer_rank')),Z),confirmed_without_historical_ADD_rounds=len(neveraddrounds),confirmed_without_historical_ADD_mark=sum((D(r['market_value']) for r in lr if r['round_id'] in neveraddrounds),Z),true_winner_rounds=len({r['round_id'] for r in lr if strict_bool(r['current_winner'])}),winner_core=sum((D(r['core_value']) for r in lr),Z)))
save('FOUR_DAY_FIVE_FOCUS',rows)
don=[]
for d in days:
 for sec in sorted({t['sector51'] for t in o if t['day']==d and t.get('transfer_rank')}):
  ts=[t for t in o if t['day']==d and t['sector51']==sec and t.get('transfer_rank')];don.append(dict(day=d,sector51=sec,sales=len(ts),shares=sum(t['qty'] for t in ts),net_cash=sum((D(t['cash_delta']) for t in ts),Z),fees=sum((D(t['fee']) for t in ts),Z),reasons=sorted({t['reason'] for t in ts})))
save('KEYDAY_DONOR_SECTORS',don)
bridge=[{k:v for k,v in r.items() if k!='receivers'} for r in fund if r['phase']=='OPEN' and r['event'] in ['TRANSFER_CASH','RECEIVER_FUNDING'] and r['day'] in days];save('KEYDAY_FUNDING_BRIDGES',bridge)
# All donors, complete in-window adjusted-price aftermath, not simulated forgone account profit.
manifest={r['symbol']:r for r in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))};cache={};paths=[]
for t in o:
 if not t.get('transfer_rank'):continue
 s=t['sid']
 if s not in cache:
  p=next(p for p in manifest[s]['source_sha256'] if p.endswith('/signal.parquet'));assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==manifest[s]['source_sha256'][p];cache[s]=pd.read_parquet(p)
 z=cache[s];dt=pd.Timestamp(t['day']);ref=z.loc[dt];adj=D(t['price'])*D(str(ref.adjustment_factor))
 for d,r in z[(z.index>=dt)&(z.index<=pd.Timestamp('2024-10-08'))].iterrows():
  known=all(pd.notna(r[c]) and r[c]>0 for c in ['raw_close','adjustment_factor']) and all(str(r[c])==str(ref[c]) for c in ['source_kind','source_path','segment_id'])
  paths.append(dict(order_seq=t['order_seq'],sid=s,sector51=t['sector51'],sale_day=t['day'],qty=t['qty'],net_released=t['cash_delta'],reason=t['reason'],evaluation_day=str(d.date()),same_source=known,adjusted_close_change_from_sale_proxy=(D(str(r.raw_close))*D(str(r.adjustment_factor))/adj-1) if known else None,not_counterfactual_account_profit=True))
save('ALL_DONOR_IN_WINDOW_PRICE_PATHS',paths)
print('DETAIL_REPORT',len(rows),len(don),len(paths))
