"""Explain native OPEN rejection and common-fee arithmetic; no account run."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parents[1];sys.path.insert(0,str(E/'trend_exit_controls_v1'))
import load_inputs as V
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())

def main():
 p=O/'SIMPLE_LOCAL_CASH_RESULTS.json';cash=read(p);rows={r['sid']:r for r in cash['cases']}
 tfile=O.parent/'chains/LOCAL_DIAGNOSTIC_TRIGGERS.json';triggers={r['sid']:r for r in read(tfile)}
 _,market,_=V.J.M.context('2024-12-31',ids=['000564.SZ'])
 windows=[]
 for day in ['2022-12-12','2022-12-13','2022-12-14']:
  at=V.J.M.N.iso(day+'T09:30:00+08:00');raw=market.raw['000564.SZ'].loc[pd.Timestamp(day)];w=market.window('000564.SZ',at,'sell',1)
  windows.append(dict(at=str(at),raw={k:float(raw[k])for k in ['open','high','low','close','volume']},native_window_present=w is not None,market_open=w.market_open if w else None,sell_allowed=w.sell_allowed if w else None,capacity_shares=w.capacity_shares if w else None,execution_price=str(w.execution_price)if w else None,flat_bar=bool(raw.high<=raw.low),reason='Native conservative H/L flat-bar proxy sets buy/sell false; actual legal limit status and queue priority are not certified.'if w and w.sell_allowed is False and raw.high<=raw.low else'Native executable-window conditions apply.'))
 assert windows[0]['flat_bar']and windows[1]['flat_bar']and windows[0]['sell_allowed']is False and windows[1]['sell_allowed']is False
 assert windows[2]['sell_allowed']is True and windows[2]['capacity_shares']>=rows['000564.SZ']['T_units']
 ep=Path(triggers['000620.SZ']['trigger_event_source']);ev=pd.read_parquet(ep);first=ev.loc['2022-01-17'];later=ev.loc['2022-01-20'];assert first.event==-1 and later.event==1
 removed=triggers['000620.SZ']['later_original_mobile_contracts'];orig_removed_net=sum((D(x['endpoint_net'])for x in removed),D(0));b=D(rows['000620.SZ']['B']['local_delta'])
 out=dict(status='NATIVE_OPEN_AND_SHARED_FEE_BRIDGES_READ_ONLY',supply_case=dict(sid='000564.SZ',trigger_at=rows['000564.SZ']['trigger_at'],windows=windows,A=rows['000564.SZ']['A'],causal_limit='The price decline already realized before the first eligible Dec14 OPEN cannot be saved by this Dec9 CLOSE action under the frozen execution proxy.'),repeated_mobile_case=dict(sid='000620.SZ',confirmed_down_day='2022-01-17',past_pivot_date=str(first.confirmed_pivot_date),new_positive_event_day='2022-01-20',later_positive_event_value=float(later.event),removed_mobile_contracts=removed,static_removed_original_layer_net=str(orig_removed_net),naive_sign_flip_of_removed_net=str(-orig_removed_net),fee_aware_local_B=str(b),shared_order_minimum_fee_interaction=str(b+orig_removed_net),candidate_scope_warning='B prohibits every later mobile until original campaign evaluation H; it also deletes orders after Jan20 positive progress. Therefore B is not the payoff or a mathematical upper bound of a down-event-to-next-up-event gate.'),winner_countercase=dict(sid='002317.SZ',A=rows['002317.SZ']['A'],B=rows['002317.SZ']['B'],interpretation='Early-exit payoff is negative for the original T inventory. This is a retained counterexample, not an exception used to tune the trigger.'),source_sha256={str(p.resolve()):sha(p),str(tfile.resolve()):sha(tfile),str(ep):sha(ep),str(Path(__file__).resolve()):sha(__file__)},new_financial_accounts=0,new_financial_events=0)
 with(O/'CRITICAL_EXECUTION_BRIDGES.json').open('x')as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'status':out['status'],'flat_proxy_blocks':[w['at']for w in windows if w['sell_allowed']is False],'fee_interaction':str(b+orig_removed_net)},ensure_ascii=False))

if __name__=='__main__':main()
