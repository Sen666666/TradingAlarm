import contextlib,io,runpy,json,hashlib
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
P=Path(__file__).parent
with contextlib.redirect_stdout(io.StringIO()):a=runpy.run_path(str(P/'analyze.py'))
read,fee,bars=a['read'],a['fee'],a['bars'];R=a['R'];manifest=a['manifest'];p=R/'mainline_m7_downturn_cash_batch_v6/once_20241031'
events=read(p/'CP_EVENTS.json');holds=read(p/'HOLDINGS.json');orders=read(p/'ORDERS.json');caps=read(p/'CAPITAL_LOTS.json');out=[];history=[]
for s,rid,seed in [('300085.SZ','300085.SZ|1|2024-09-23','2024-09-24'),('000158.SZ','000158.SZ|2|2024-09-23','2024-09-24')]:
 cpfile=Path(manifest[s]['refs']['CP1']);h=hashlib.sha256(cpfile.read_bytes()).hexdigest();assert h==manifest[s]['output_sha256'][str(cpfile)];a['hashes'][str(cpfile)]=h;cp=pd.read_parquet(cpfile);bb=bars(s)
 for dt in ['2024-10-09','2024-10-10','2024-10-11','2024-10-14']:
  z=bb.loc[dt];fac=D(str(z.adjustment_factor));hh=[x for x in holds if x['round_id']==rid and x['day']==dt];cc=[x for x in caps if x['round_id']==rid and x['day']==dt];q=sum(x['qty'] for x in hh);cash=sum((D(o['cash_delta']) for o in orders if o['round_id']==rid and o['day']<=dt),D(0));receipts=[]
  for cdt,c in cp.loc[seed:dt].iterrows():
   if not bool(c.receipt):continue
   candidate=D(str(c.candidate));first=None
   # Structural breach uses the engine-observed OPEN/CLOSE only after receipt became known, not intraday lows.
   for bdt,b in bb.loc[cdt:pd.Timestamp(dt)].iterrows():
    for phase,col in [('OPEN','raw_open'),('CLOSE','raw_close')]:
     if bdt==cdt:continue
     if D(str(b[col]))*D(str(b.adjustment_factor))<=candidate:first=(str(bdt.date()),phase,str(b[col]));break
    if first:break
   ev=[x for x in events if x['round_id']==rid and x['day']==str(cdt.date()) and x['event']=='CREATED_AFTER_SEED'];cid=ev[0]['cp_id'] if ev else None;life=[x for x in events if x['round_id']==rid and x['cp_id']==cid and x['day']<=dt] if cid else []
   row=dict(sid=s,asof=dt,receipt_day=str(cdt.date()),candidate_signal=candidate,factor=fac,raw_floor=candidate/fac,first_open_close_breach=first,cp_id=cid,engine_events=life,unbroken_structure=first is None,active_round=q>0)
   receipts.append(row);history.append(row)
  latest=receipts[-1];high=max(receipts,key=lambda c:c['candidate_signal']);unbroken=[c for c in receipts if c['unbroken_structure']];hu=max(unbroken,key=lambda c:c['candidate_signal']) if unbroken else None
  def pnl(fl,qty=q,base=cash):return base+qty*fl*D('.9995')-fee(s,dt,qty,fl*D('.9995')) if qty else None
  row=dict(sid=s,round_id=rid,asof=dt,raw_open=str(z.raw_open),raw_close=str(z.raw_close),qty=q,cashflow=cash,stock_state=cc[0]['stock_state'] if cc else 'ROUND_ALREADY_EXITED',sector_state=cc[0]['sector_state'] if cc else 'ROUND_ALREADY_EXITED',net=cc[0]['round_net'] if cc else cash,latest_receipt=latest,highest_historical_receipt=high,highest_unbroken_historical_structure=hu,all_inventory_at_latest_cp_pressure_net=pnl(latest['raw_floor']),all_inventory_at_highest_unbroken_pressure_net=pnl(hu['raw_floor']) if hu else None,actual_seed_ifloor_raw=D(hh[0]['protection_signal'])/D(hh[0]['factor']) if hh else None,at_I_pressure_net=pnl(D(hh[0]['protection_signal'])/D(hh[0]['factor'])) if hh else None)
  if dt=='2024-10-10':
   nxt=bb.loc['2024-10-11'];px=D(str(nxt.raw_open))*D('.9995');row['fixed_all_inventory_at_next_open_net']=cash+q*px-fee(s,'2024-10-11',q,px)
  out.append(row)
result=dict(rows=out,all_receipt_history=history,hashes=a['hashes'],caveats=['unbroken_structure仅表示receipt形成后未被可见OPEN/CLOSE穿越，不表示仍是引擎有效CP：SUPERSEDED、CONSUMED、INVALIDATED都单列，不能复活旧CP。','全库存移到CP是假设扩大保护范围的静态压力值，不是已有规则，也不是成交回测。若CP已被击穿，当日该floor值不可作可实现退出。','银之杰10/14 OPEN原轮已退出，无当日收盘库存。10/14 CLOSE新receipt属于事后新结构，不能倒用于当日OPEN或复活该轮。','未用盘中高低点、ATR或回吐百分比扫描。'])
(P/'CP_STRUCTURE_PROBE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
