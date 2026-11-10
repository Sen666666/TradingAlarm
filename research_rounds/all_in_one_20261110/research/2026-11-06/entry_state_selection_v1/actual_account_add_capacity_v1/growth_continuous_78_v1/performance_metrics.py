"""Read-only performance and round attribution for two completed research arms."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,csv,hashlib
ROOT=Path(__file__).resolve().parent
START,END='2023-01-03','2023-04-28'
NAV0=D('844956.557699312823')
Z=D(0)
def load(p):return json.load(gzip.open(p,'rt'))
def rows(p):return [json.loads(l) for l in gzip.open(p,'rt')]
def dec(x):return D(str(x))
def encode(x):
 if isinstance(x,D):return str(x)
 raise TypeError(type(x))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=encode)+'\n')
def stats(rs):
 ps=[r['pnl_including_dividend'] for r in rs];wins=[x for x in ps if x>0];losses=[x for x in ps if x<0]
 return dict(closed=len(rs),wins=len(wins),losses=len(losses),zero=sum(x==0 for x in ps),win_rate=D(len(wins))/len(rs) if rs else None,mean_win=sum(wins,Z)/len(wins) if wins else None,mean_loss=sum(losses,Z)/len(losses) if losses else None,payoff_ratio=(sum(wins,Z)/len(wins))/abs(sum(losses,Z)/len(losses)) if wins and losses else None,profit_factor=sum(wins,Z)/abs(sum(losses,Z)) if wins and losses else None,net_pnl=sum(ps,Z),known_net_dividend=sum((r['dividend'] for r in rs),Z),pnl_excluding_dividend=sum((r['pnl_excluding_dividend'] for r in rs),Z),right_tail_ge30pct=sum(r['net_return']>=D('.3') for r in rs))
def arm(path):
 a=load(path/'pair/PVR.json.gz');live={};allrounds=[];seq={}
 for j in a['journal']:
  kind=j['kind'];sid=j.get('sid')
  if kind=='real_buy_fill':
   if sid not in live:
    seq[sid]=seq.get(sid,0)+1;r=dict(sid=sid,round=seq[sid],entered=j['at'],exited=None,qty=0,buy_cash=Z,sell_net=Z,layers=[],add_fills=0,seed_qty=j['shares']);live[sid]=r;allrounds.append(r)
   r=live[sid];r['add_fills']+=int(r['qty']>0);r['qty']+=j['shares'];r['buy_cash']+=dec(j['price'])*j['shares']+dec(j['fees']);r['layers'].append(j['layer'])
  elif kind=='real_sell_fill':
   r=live[sid];r['qty']-=j['shares'];r['sell_net']+=sum((dec(x['net_cash']) for x in j['parts']),Z);assert r['qty']>=0
   if not r['qty']:r['exited']=j['at'];del live[sid]
  elif kind=='actual_split' and sid in live:
   live[sid]['qty']=int(dec(live[sid]['qty'])*dec(j['ratio']))
   assert live[sid]['qty']>0,'split-to-zero round needs separate attribution audit'
 dividend={x['id']:dec(x['dividend']) for x in a['layers']}
 for r in allrounds:
  r['dividend']=sum((dividend[k] for k in r['layers']),Z)
  r['pnl_excluding_dividend']=r['sell_net']-r['buy_cash'] if r['exited'] else None
  r['pnl_including_dividend']=r['pnl_excluding_dividend']+r['dividend'] if r['exited'] else None
  r['net_return']=r['pnl_including_dividend']/r['buy_cash'] if r['exited'] else None
 closed=[r for r in allrounds if r['exited'] and START<=r['exited'][:10]<=END]
 new=[r for r in allrounds if START<=r['entered'][:10]<=END]
 dd=[x for x in rows(path/'pair/daily.jsonl.gz') if START<=x['at'][:10]<=END]
 values=[NAV0]+[dec(x['nav']) for x in dd];peak=values[0];worst=Z;trough=None
 for day,value in zip(['2022-12-30']+[x['at'][:10] for x in dd],values):
  peak=max(peak,value);draw=value/peak-1
  if draw<worst:worst=draw;trough=day
 result=dict(start_nav=NAV0,end_nav=values[-1],return_fraction=values[-1]/NAV0-1,window_max_drawdown_fraction=worst,drawdown_trough_day=trough,exit_cohort=stats(closed),exit_cohort_inherited=stats([r for r in closed if r['entered'][:10]<START]),exit_cohort_new=stats([r for r in closed if r['entered'][:10]>=START]),new_entry_cohort_rounds=len(new),new_entry_cohort_closed=sum(r['exited'] is not None for r in new),new_entry_cohort_open=sum(r['exited'] is None for r in new),end_open_rounds=len(live))
 return result,closed,allrounds
def main():
 assert json.loads((ROOT/'growth/run/DONE.json').read_text())['completed']
 out=ROOT/'performance';assert not out.exists();out.mkdir()
 baseline,bc,ba=arm(ROOT/'baseline/run');growth,gc,ga=arm(ROOT/'growth/run')
 tail=sorted(bc,key=lambda r:r['pnl_including_dividend'],reverse=True)[:5]
 cases=[dict(original=r,growth_window_closed=[x for x in gc if x['sid']==r['sid']],growth_end_open=[x for x in ga if x['sid']==r['sid'] and not x['exited']]) for r in tail]
 parts=[x for x in rows(ROOT/'growth/run/REALIZED_LAYER_PARTS.jsonl.gz') if START<=x['at'][:10]<=END]
 states=json.loads((ROOT/'growth/run/GROWTH_STATES.json').read_text())['PVR']
 diag=dict(window_negative_add_parts_loss=sum((max(Z,-dec(x['realized'])) for x in parts if x['added']),Z),window_negative_seed_parts_loss=sum((max(Z,-dec(x['realized'])) for x in parts if not x['added']),Z),window_layer_realized_net=sum((dec(x['realized']) for x in parts),Z),end_live_H=sum((dec(s['H']) for s in states.values() if s['qty']),Z),end_live_H_all=sum((dec(s['H_all']) for s in states.values() if s['qty']),Z),end_live_positive_H_stocks=sum(s['qty']>0 and dec(s['H'])>0 for s in states.values()),end_live_positive_H_all_stocks=sum(s['qty']>0 and dec(s['H_all'])>0 for s in states.values()))
 save(out/'SUMMARY.json',dict(original=baseline,growth=growth,growth_loss_diagnostics=diag,definitions='METRICS_CONTRACT.md',scope='78-day research window only; no 924 or PIT/tradability claim'))
 save(out/'RIGHT_TAIL_CASES.json',cases);save(out/'ORIGINAL_CLOSED_ROUNDS.json',bc);save(out/'GROWTH_CLOSED_ROUNDS.json',gc);save(out/'ORIGINAL_ALL_ROUNDS.json',ba);save(out/'GROWTH_ALL_ROUNDS.json',ga)
 save(out/'SOURCE_HASHES.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'METRICS_CONTRACT.md',ROOT/'baseline/run/pair/PVR.json.gz',ROOT/'growth/run/pair/PVR.json.gz',ROOT/'baseline/run/pair/daily.jsonl.gz',ROOT/'growth/run/pair/daily.jsonl.gz',ROOT/'growth/run/REALIZED_LAYER_PARTS.jsonl.gz',ROOT/'growth/run/GROWTH_STATES.json']})
 print(json.dumps(dict(original=baseline,growth=growth,growth_loss_diagnostics=diag),ensure_ascii=False,default=encode))
if __name__=='__main__':main()
