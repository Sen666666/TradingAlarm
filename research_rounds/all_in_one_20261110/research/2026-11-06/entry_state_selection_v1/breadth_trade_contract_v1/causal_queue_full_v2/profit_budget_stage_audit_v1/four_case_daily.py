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
cases=[('688126.SH','2026-06-11','M3'),('605358.SH','2026-06-11','M3'),('002408.SZ','2022-01-05','M3'),('002583.SZ','2024-10-21','PVR3')]
for sid,start,arm in cases:
 r=z[z.sid.eq(sid)&z.day.eq(start)&z.arm.eq(arm)].iloc[0];m=sm[sid];h=pd.read_parquet(next(p for p in m['source_sha256']if p.endswith('/signal.parquet')));f=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1']);Q=int(r.entry_q);K=D(str(r.entry_price))*Q+D(str(r.entry_fee));fac=D(str(h.loc[pd.Timestamp(start)].adjustment_factor));sec=r.event_id.split('|')[-1];sector=panel[panel.sector.eq(sec)].set_index('day')[arm+'_candidate'];end=r.exit_day if isinstance(r.exit_day,str)else '2026-06-30';out=[]
 for d in cal[(cal>=pd.Timestamp(r.entry_day))&(cal<=pd.Timestamp(end))]:
  if isinstance(r.exit_day,str) and d==pd.Timestamp(r.exit_day):
   out.append(dict(day=str(d.date()),action='original_core_exit_at_open_before_close',core_exit_pnl=r.net_pnl));break
  k=cal.get_loc(d);prev=cal[k-1];S=D(str(f.loc[prev,'i_floor']))/fac;op=D(str(h.loc[d,'raw_open']));cl=D(str(h.loc[d,'raw_close']));C=val(Q,cl*D('.9995'),sid,d);Vs=val(Q,S*D('.9995'),sid,d);newS=D(str(f.loc[d,'i_floor']))/fac if pd.notna(f.loc[d,'i_floor']) else S;Vsnew=val(Q,newS*D('.9995'),sid,d);L=Vsnew-K;rp=max(D(0),-L);avail=D(3000)-rp;fresh=bool(cp.loc[d,'receipt']);qual=int(sector.get(d,-1));net=C-K
  row=dict(day=str(d.date()),open=float(op),close=float(cl),core_oldS=float(S),core_newS=float(newS),K=float(K),stop_old_net=float(Vs),stop_new_net=float(Vsnew),protected_principal=float(min(K,Vsnew)),principal_risk=float(rp),locked_scenario_profit=float(max(D(0),L)),giveback=float(max(D(0),C-Vsnew)),net=float(net),fresh=fresh,sector=qual,free_principal=float(avail))
  if fresh and cp.loc[d,'candidate']==cp.loc[d,'candidate'] and bool(f.loc[d,'i_target']) and k+1<len(cal):
   ns=D(str(cp.loc[d,'candidate']))/fac;ns=max(ns,newS);nd=cal[k+1];no=D(str(h.loc[nd,'raw_open']));p=no*D('1.0005');qr,_,_=meta(sid,nd);mn=qr.buy_minimum;minr=D(mn)*p+fees(mn,p,sid,nd,'buy')-val(mn,ns*D('.9995'),sid,nd);oldrisk=max(D(0),D(Q)*(p-newS*D('.9995'))+D(str(r.entry_fee))+fees(Q,newS*D('.9995'),sid,nd,'sell'));nextnet=val(Q,no*D('.9995'),sid,nd)-K;vsnext=val(Q,newS*D('.9995'),sid,nd);rpn=max(D(0),K-vsnext);an=D(3000)-rpn;closeq=qty(sid,d,cl*D('1.0005'),ns,min(D(24000),D(48000)-Q*cl),avail);openq=qty(sid,nd,p,ns,min(D(24000),D(48000)-Q*no),an)
   row.update(cp_newS=float(ns),next_day=str(nd.date()),next_open=float(no),next_net=float(nextnet),next_min_qty=mn,next_min_risk=float(minr),next_old_free=float(max(D(0),D(3000)-oldrisk)),next_principal_free=float(an),close_qcap=closeq[0],open_q_uncapped=openq[0],capped_q=min(closeq[0],openq[0]))
  out.append(row)
 print('\nCASE',sid,start,arm,'actual_actions',r.actions);print(pd.DataFrame(out).to_csv(index=False))
