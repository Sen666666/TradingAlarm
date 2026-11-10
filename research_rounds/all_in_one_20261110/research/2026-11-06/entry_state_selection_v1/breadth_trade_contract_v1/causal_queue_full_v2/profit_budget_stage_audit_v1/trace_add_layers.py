import pandas as pd,json,sys
from pathlib import Path
from decimal import Decimal as D
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
P=R/'breadth_trade_contract_v1/causal_queue_full_v2'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
sm={x['symbol']:x for x in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];names=rules['security_metadata']
panel=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
cal=pd.DatetimeIndex(sorted(panel.day.unique()));z=pd.read_csv(P/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv')
def meta(sid,d):
 s=str(pd.Timestamp(d).date());i=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][i['venue']],s,proxies)['schedule'];return QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x)for x in v['components'])),D(str(names[sid]['par_value']))
def fees(q,p,sid,d,side):
 _,fs,par=meta(sid,d);return sum(fs.incremental(side,D(q)*D(str(p)),{},{},1,shares=int(q),par_value=par).values(),D(0))
def val(q,p,sid,d):return D(q)*p-fees(q,p,sid,d,'sell')
def qty(sid,d,p,S,budget,riskmax):
 qr,_,_=meta(sid,d);q=qr.buy_floor(int(budget/p))
 while q:
  c=D(q)*p+fees(q,p,sid,d,'buy');v=val(q,S*D('.9995'),sid,d)
  if c<=budget and c-v<=riskmax:return q,float(c),float(c-v)
  q=qr.buy_floor(q-1)
 return 0,0.,0.
cases=[('688126.SH','2026-06-11','M3','2026-06-26',237),('605358.SH','2026-06-11','M3','2026-06-26',100),('002408.SZ','2022-01-05','M3','2022-01-10',100),('002583.SZ','2024-10-21','PVR3','2024-10-22',100)]
for sid,start,arm,signal,aq in cases:
 r=z[z.sid.eq(sid)&z.day.eq(start)&z.arm.eq(arm)].iloc[0];m=sm[sid];h=pd.read_parquet(next(p for p in m['source_sha256']if p.endswith('/signal.parquet')));f=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1']);fac=D(str(h.loc[pd.Timestamp(start)].adjustment_factor));sd=pd.Timestamp(signal);od=cal[cal.get_loc(sd)+1];stop=max(D(str(f.loc[sd,'i_floor'])),D(str(cp.loc[sd,'candidate'])))/fac
 p=D(str(h.loc[od,'raw_open']))*D('1.0005');cost=aq*p+fees(aq,p,sid,od,'buy');risk=cost-val(aq,stop*D('.9995'),sid,od);addpending=False;exitpending=False;out=[];exitv=None
 for d in cal[(cal>=od)&(cal<=pd.Timestamp('2026-06-30'))]:
  op=D(str(h.loc[d,'raw_open']));cl=D(str(h.loc[d,'raw_close']));old=stop
  if addpending or exitpending:
   exitv=val(aq,op*D('.9995'),sid,d)
   out.append(dict(day=str(d.date()),action='sell_add',q=aq,price=float(op*D('.9995')),fees=float(fees(aq,op*D('.9995'),sid,d,'sell')),net_pnl=float(exitv-cost),reason='old_CP_broken'if addpending else'I_off'));break
  if not bool(f.loc[d,'i_target']):exitpending=True
  elif cl<=stop:addpending=True
  else:
   if pd.notna(f.loc[d,'i_floor']):stop=max(stop,D(str(f.loc[d,'i_floor']))/fac)
   if bool(cp.loc[d,'receipt'])and pd.notna(cp.loc[d,'candidate']):stop=max(stop,D(str(cp.loc[d,'candidate']))/fac)
  out.append(dict(day=str(d.date()),action='buy_add'if d==od else'hold',q=aq,open=float(op),close=float(cl),old_stop=float(old),next_stop=float(stop),hypothetical_net=float(val(aq,cl*D('.9995'),sid,d)-cost),next_exit=bool(addpending or exitpending)))
 print('\nCASE',sid,'signal',signal,'entry',str(od.date()),'Q',aq,'cost',float(cost),'risk',float(risk),'entryfee',float(fees(aq,p,sid,od,'buy')),'end_net',float(exitv-cost)if exitv else out[-1]['hypothetical_net'])
 print(pd.DataFrame(out).to_csv(index=False))
