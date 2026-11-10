from pathlib import Path
import gzip,json,collections
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE/2022_2024/pair')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
a=json.load(gzip.open(B/'B.json.gz','rt'));ds=[json.loads(x) for x in gzip.open(B/'daily.jsonl.gz','rt')];ds=[x for x in ds if x['at'].startswith('2022')];last=ds[-1]
closed=[x for x in a['layers'] if x.get('closed') and x['closed'][:10]<='2022-12-30'];d=pd.DataFrame(closed);d['net_pnl']=pd.to_numeric(d.cash)+pd.to_numeric(d.dividend)
loss=float(d.loc[d.net_pnl.lt(0),'net_pnl'].sum());win=float(d.loc[d.net_pnl.gt(0),'net_pnl'].sum());openpnl=float(last['inventory'])+sum(float(x['cash'])+float(x['dividend'])for x in last['layers']);net=float(last['nav'])-1e6
assert abs(loss+win+openpnl-net)<1e-7
summary=dict(source='frozen original 1m-start account; not current 1.2m account',days=len(ds),end_NAV=float(last['nav']),net_pnl=net,return_fraction=net/1e6,closed_layers=len(d),losing_layers=int(d.net_pnl.lt(0).sum()),negative_layers_net_pnl=loss,positive_layers_net_pnl=win,realized_net=loss+win,open_layer_marked_pnl=openpnl,reconciliation_residual=loss+win+openpnl-net,fees_already_in_pnl=float(last['fees_cny']),shared_loss_record_only=float(last['shared_loss']),mean_stock_exposure=float(np.mean([float(x['inventory'])/float(x['nav'])for x in ds])),max_stock_exposure=max(float(x['inventory'])/float(x['nav'])for x in ds),mean_stocks=float(np.mean([len(x['positions'])for x in ds])),max_stocks=max(len(x['positions'])for x in ds),buy_fills=979,sell_fills=731,by_kind=d.groupby('kind').agg(layers=('id','size'),losses=('net_pnl',lambda x:(x<0).sum()),net_pnl=('net_pnl','sum')).reset_index().to_dict('records'))
by=d.groupby('sid').agg(layers=('id','size'),losing_layers=('net_pnl',lambda x:(x<0).sum()),net_pnl=('net_pnl','sum')).sort_values('net_pnl');by.to_csv(O/'2022_REPEAT_LOSSES.csv');d.to_csv(O/'2022_CLOSED_LAYER_PNL.csv',index=False)
# Per-layer held-path maxima from actual daily holdings; after-the-fact diagnostic, not attainable exits.
raw={};peak={}
for row in ds:
 t=pd.Timestamp(row['at'][:10])
 for x in row['layers']:
  sid=x['sid']
  if sid not in raw:
   r=pd.read_parquet(P/'bars'/f'{sid}.parquet').set_index('trade_date');r.index=pd.to_datetime(r.index);raw[sid]=r.close
  p=float(raw[sid].loc[:t].iloc[-1]);pnl=float(x['cash'])+float(x['dividend'])+x['qty']*p
  if x['id'] not in peak or pnl>peak[x['id']]['peak_marked_pnl']:peak[x['id']]=dict(layer=x['id'],sid=sid,kind=x['kind'],peak_day=str(t.date()),peak_marked_pnl=pnl,peak_qty=x['qty'],peak_raw_close=p)
rows=[]
for x in closed:
 if x['id'] not in peak:continue
 z=peak[x['id']];pnl=float(x['cash'])+float(x['dividend']);rows.append(dict(**z,final_pnl=pnl,giveback=z['peak_marked_pnl']-pnl,opened=x['opened'],closed=x['closed'],initial_qty=x['initial_qty']))
p=pd.DataFrame(rows).sort_values('giveback',ascending=False);p.to_csv(O/'2022_ACTUAL_HELD_GIVEBACK.csv',index=False)
(O/'2022_LEDGER_RECONCILIATION.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2));print(p.head(12).to_string(index=False))
