"""Package all immutable fills/cycles and causal candle data for local review."""
from common_atlas import *
from collections import defaultdict,Counter
from decimal import Decimal as D
import csv,shutil
from functools import lru_cache
from bisect import bisect_right
def loadz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
@lru_cache(None)
def price_data(sid):
 p=loadz(O/'web/data/prices'/f'{sid}.json.gz');return p,{r[0]:r[6] for r in p['bars']},[r[0] for r in p['bars']]
def main():
 data=O/'web/data';data.mkdir(parents=True,exist_ok=False);sources=pd.read_csv(ROUND/'comparison/sources.csv');campaigns=pd.read_csv(ROUND/'comparison/campaigns.csv');summaries=pd.read_csv(ROUND/'comparison/summary.csv');index=[];route_meta=[];allmeta={};inputs={};fill_csv=[];buys_csv=[];checks=Counter();ratings={}
 for sector in ['TECH','DRUG']:
  proof=read(O/'data'/sector/'trace-verification.json');assert proof['passed'] and proof['paths']==30 and proof['economic_accounts_started']==0
  ratings[sector]=loadz(O/'data'/sector/'ratings.json.gz')
  for day,r in ratings[sector].items():save(data/'ratings'/sector/f'{day}.json.gz',r)
  strict={sid:pd.read_parquet(OLD_TABLES[sector]/f'{sid}.parquet') for sid in pool(sector).symbol}
  for _,meta in pool(sector).iterrows():
   sid=meta.symbol;allmeta[sid]=dict(symbol=sid,name=meta['name'],industry=meta.industry,sector_id=meta.sector_id,sector=sector)
   p=PREPS[sector]/'signals'/f'{sid}.parquet';fp=PREPS[sector]/'facts'/f'{sid}.parquet';f=pd.read_parquet(fp).loc['2023-10-01':END];raw=pd.read_parquet(p).reindex(f.index)
   assert (raw.close==f.close).all() and set(raw.amount_unit)=={'CNY'}
   for name in ['open','high','low','close']:np.testing.assert_allclose(raw[name],raw['raw_'+name]*raw.adjustment_factor,rtol=1e-11,atol=1e-10)
   bars=[]
   for day,row in raw.iterrows():
    z=f.loc[day];st=strict[sid].loc[day] if day in strict[sid].index else None
    bars.append([str(day.date()),float(row.raw_open),float(row.raw_high),float(row.raw_low),float(row.raw_close),float(row.amount),float(row.adjustment_factor),float(z.i_floor),bool(z.i_target),bool(z.i_buy),float(z.g_grade),bool(st.strict_target) if st is not None else False,float(row.raw_volume)])
   save(data/'prices'/f'{sid}.json.gz',dict(symbol=sid,columns=['date','raw_open','raw_high','raw_low','raw_close','amount_CNY','causal_factor','I_floor_causal','I_up','I_buy','G1_grade','S_valid','raw_volume_shares'],bars=bars))
   inputs[str(p)]=sha(p);inputs[str(fp)]=sha(fp);checks['stock_price_files']+=1;checks['real_candles']+=len(bars)
 for _,source in sources.iterrows():
  sector,mode,scenario=source.sector,source.policy,source.scenario;route=f'{sector}-{mode}-{scenario}';aid=f'{mode}__S0_{scenario}';path=Path(source.accounts)/f'{aid}.json';assert sha(path)==source.account_sha256;inputs[str(path)]=source.account_sha256;obj=read(path)
  tr=loadz(O/'data'/sector/f'{mode}-{scenario}-trace.json.gz');cc=campaigns[campaigns.sector.eq(sector)&campaigns.policy.eq(mode)&campaigns.scenario.eq(scenario)];summary=summaries[summaries.sector.eq(sector)&summaries.policy.eq(mode)&summaries.scenario.eq(scenario)].iloc[0].to_dict();assert abs(cc.net_pnl.sum()-summary['net_profit'])<1e-5
  logs=obj['audit_log'];fills_by_receipt={r['receipt']['receipt_id']:r for r in logs if r['kind']=='fill'};fillmap={(r['security_id'],r['at'],r['side']):fills_by_receipt[r['receipt_id']] for r in obj['fills']};risk={r['at'][:10]:r for r in logs if r['kind']=='risk_checkpoint'};requests=defaultdict(list);cp=defaultdict(list);fast=defaultdict(list);inherited=defaultdict(list);actions=defaultdict(list)
  for r in logs:
   k=r['kind'];sid=r.get('sid')
   if k=='exit_request':requests[sid].append(r)
   elif k=='cp_checkpoint':cp[sid].append(r)
   elif k in ['fast_support_raise','fast_support_exit']:fast[sid].append(r)
   elif k=='waiting_support_inherited':inherited[sid].append(r)
   elif k=='split':actions[sid].append(r)
  details=[]
  for _,c in cc.iterrows():
   sid=c.symbol;entry=c.entry_at;exit=None if pd.isna(c.exit_at) else c.exit_at;buy=fillmap[sid,entry,'buy'];orderid=buy['order_id'];order=tr['orders'][orderid];day=order['decision_at'];rank=ratings[sector][day]['stocks'][sid];meta=allmeta[sid];price,factor,price_dates=price_data(sid);last=exit or END+' 15:10:00+08:00';ident=f'{route}-{sid}-{entry[:10]}'
   cycle_fills=[buy]
   if exit:cycle_fills.append(fillmap[sid,exit,'sell'])
   converted=[]
   for r in cycle_fills:
    receipt=r['receipt'];date=receipt['at'][:10];assert date in factor,(ident,date,'fill outside real candles');rawprice=float(r['price']);assert abs(rawprice*int(receipt['shares'])-float(receipt['gross_cny']))<1e-5
    converted.append(dict(receipt_id=receipt['receipt_id'],side=receipt['side'],at=receipt['at'],raw_price=rawprice,causal_price=rawprice*factor[date],factor=factor[date],shares=int(receipt['shares']),gross=float(receipt['gross_cny']),fees=float(receipt['fees_cny']),order_id=r['order_id'],raw_open=float(r['raw_open']),components=r['fee_components']))
    fill_csv.append(dict(trade_id=ident,route=route,sector=sector,policy=mode,scenario=scenario,symbol=sid,name=meta['name'],**{k:v for k,v in converted[-1].items() if k!='components'},buy_decision=day,stock_RS=rank[0] if receipt['side']=='buy' else '',pool_RS_order=rank[1] if receipt['side']=='buy' else '',sector_candidate_order=order['sector_rank'] if receipt['side']=='buy' else '',stock_candidate_order=order['stock_rank'] if receipt['side']=='buy' else ''));checks['buy_fills' if receipt['side']=='buy' else 'sell_fills']+=1
   rs=[r for r in requests[sid] if entry<=r['at']<=last];request=rs[-1] if rs else None;why=dict(primary='holding',decision_at=None,CP_touch=False,F_touch=False,E0_off=False,account_paused=False)
   if request:
    dd=request['at'][:10];r=risk[dd];price_row=price['bars'][bisect_right(price_dates,dd)-1];cpday=next((r for r in cp[sid] if r['at'][:10]==dd),None);fday=next((r for r in fast[sid] if r['kind']=='fast_support_exit' and r['at'][:10]==dd),None)
    why.update(decision_at=dd,CP_touch=bool(cpday and cpday['close']<=cpday['old_P']),F_touch=bool(fday),E0_off=not bool(price_row[8]),account_paused=not bool(r['on']),risk=r,cp=cpday,fast=fday)
    why['primary']='ACT' if why['account_paused'] else 'E0' if why['E0_off'] else 'CP1' if why['CP_touch'] else 'F' if why['F_touch'] else 'locked_exit'
   protection=[]
   if mode in MODES:
    protection=[[r['at'][:10],r['old_P'],r['new_P'],r['reason']] for r in cp[sid] if entry[:10]<=r['at'][:10]<=last[:10] and r['at'][:10] in factor]
   elif mode in ['SF','SW3F','SW10F']:
    pp=None
    for r in inherited[sid]:
     if r['at']==entry:pp=float(r['floor'])
    change={r['at'][:10]:r for r in fast[sid] if r['kind']=='fast_support_raise' and entry<=r['at']<=last}
    touch={r['at'][:10]:r for r in fast[sid] if r['kind']=='fast_support_exit' and entry<=r['at']<=last}
    for b in price['bars']:
     dd=b[0]
     if not entry[:10]<=dd<=last[:10] or (exit and dd>=exit[:10]):continue
     old=pp
     if dd in touch:old=float(touch[dd]['floor'])
     if dd in change:pp=float(change[dd]['floor'])
     protection.append([dd,old,pp,'F' if dd in touch else None])
   if exit and protection:protection.append([exit[:10],protection[-1][1],protection[-1][2],'actual_exit'])
   state='closed' if bool(c.closed) else 'holding' if c.final_shares>0 else 'claim'
   item=dict(id=ident,route=route,sector=sector,policy=mode,scenario=scenario,symbol=sid,name=meta['name'],industry=meta['industry'],entry_at=entry,exit_at=exit,status=state,net_pnl=float(c.net_pnl),net_return=float(c.net_return),buy_gross=float(c.buy_gross),fees=float(c.buy_fees+c.sell_fees),dividends=float(c.dividends),final_shares=int(c.final_shares),market_value=float(c.market_value),decision_at=day,order_id=orderid,RS=rank[0],pool_rank=rank[1],pool_count=ratings[sector][day]['ranked_stocks'],sector_rank=order['sector_rank'],sector_count=order['sector_count'],stock_rank=order['stock_rank'],stock_count=order['stock_count'],extended=not order['entry_class']['original'],window=order['entry_class']['window'],origin=order['candidate_origin'],watch_origin=order['entry_class']['origin'],budget=float(order['reserve']['gross_budget_cny']),buy_shares=converted[0]['shares'],sell_reason=why['primary'])
   index.append(item);details.append(dict(id=ident,order_id=orderid,fills=converted,exit=why,protection=protection,actions=[r for r in actions[sid] if entry<=r['at']<=last]))
   buys_csv.append(dict(**item,requested_budget=order['contract']['budget'],signal_floor_causal=order['contract']['floor_signal'],signal_floor_raw=order['floor_raw_at_decision'],reference_raw_price=order['reference_raw_price'],available_before=order['available_before'],reference_target_shares=order['reserve']['target_shares'],priority_rank=order['priority_rank'],reconstruction='exact_admission_and_candidate_id_verified'));checks['cycles']+=1;checks['buy_explanations']+=1
  assert len(details)==len(cc) and int(cc.buy_fills.sum())==len(cc);assert len(obj['fills'])==sum(len(d['fills']) for d in details)
  # Keep actual budget rejections alongside the pure capacity decisions.
  decisionfile=Path(source.accounts)/'decisions.jsonl.gz'
  for d in rows(decisionfile):
   if d['account']==aid and d['at'][:10] in tr['snapshots']:tr['snapshots'][d['at'][:10]]['execution_rejected']=d['rejected']
  save(data/'paths'/f'{route}.json.gz',dict(route=route,summary=summary,cycles=details,orders=tr['orders'],snapshots=tr['snapshots']))
  route_meta.append(dict(id=route,sector=sector,policy=mode,scenario=scenario,label=LABELS[mode],net_return=summary['net_return'],max_drawdown=summary['max_drawdown'],cycles=len(details)))
  print('packaged',route,len(details),flush=True)
 assert checks['cycles']==6340 and checks['buy_fills']==6340 and checks['sell_fills']==6303 and checks['buy_explanations']==6340
 assert len({r['id'] for r in index})==6340
 for filename,rs in [('all-fills.csv',fill_csv),('buy-rankings.csv',buys_csv)]:
  with (data/filename).open('x',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
 save(data/'index.json.gz',dict(title='CP1 × W 交易图册',start='2024-01-02',end=END,cycles=index,routes=route_meta,stocks=allmeta,counts=dict(checks),definition='全部60路径；RS-H1行业/个股轮巡；信号和成交分开；日线代理，非实盘。'))
 save(O/'packaging-verification.json',dict(passed=True,**checks,economic_accounts_started=0,source_sha256=inputs,paths=60,open_positions=int(campaigns.final_shares.gt(0).sum()),raw_ohlc_factor_exact=True))
 assets=O/'web/assets';assets.mkdir(exist_ok=True);lib=ROOT/'research_rounds/czsc-comparison-20261023/assets/lightweight-charts-4.1.3.js';shutil.copy2(lib,assets/lib.name)
 (assets/'ATTRIBUTION.txt').write_text('TradingView Lightweight Charts v4.1.3, Copyright 2024 TradingView, Inc. Apache License 2.0. Original license header retained. https://www.tradingview.com/\n')
 print('verified package',dict(checks),flush=True)
if __name__=='__main__':main()
