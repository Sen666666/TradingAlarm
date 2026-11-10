"""Observed own ACT pause intervals only; no gate, H, or signal calculation."""
from pathlib import Path
from decimal import Decimal as D
import argparse,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def intervals(dr,states):
 groups=[]
 for i,r in enumerate(dr):
  if r['ACT_at_OPEN']:continue
  if not groups or i!=groups[-1]['_last_index']+1:
   groups.append(dict(first_paused_OPEN=r['day'],last_paused_OPEN=r['day'],original_pause_CLOSE=dr[i-1]['day'] if i else 'INITIAL_ACT_UNKNOWN',own_resume_CLOSE=None,days=[],_last_index=i))
  g=groups[-1];g['last_paused_OPEN']=r['day'];g['days'].append(r['day']);g['_last_index']=i
 for g in groups:
  last=dr[g.pop('_last_index')];g['own_resume_CLOSE']=last['day'] if last['ACT_after_CLOSE'] else None;rows=[r for r in dr if r['day'] in g['days']]
  g.update(paused_OPEN_days=len(rows),market_DOWN_OPEN_days=sum(states[r['day']]=='DOWN' for r in rows),market_NOT_DOWN_but_ACT_paused_OPEN_days=sum(states[r['day']]=='NOT_DOWN' for r in rows),actual_buy_cash=sum((D(r['actual_buy_cash']) for r in rows),Z),actual_buy_fills=sum(r['buy_fills'] for r in rows))
 return dict(own_paused_OPEN_days=sum(not r['ACT_at_OPEN'] for r in dr),own_paused_CLOSE_days=sum(not r['ACT_after_CLOSE'] for r in dr),NOT_DOWN_but_own_ACT_paused_OPEN_days=sum(states[r['day']]=='NOT_DOWN' and not r['ACT_at_OPEN'] for r in dr),pause_OPEN_intervals=groups)
def main(win):
 out=O/f'full_{win}_v1';assert read(out/'COMPLETED.json')['passed'];dp=out/'D_DAILY_WEALTH.json';bp=T/f'capacity_cost_guard_analysis_v1/full_{win}_v1/B_DAILY_WEALTH.json';clock=O/'ALL_PREDECLARED_MARKET_STATE_SEGMENTS.json';states={d:g['state'] for g in read(clock)['windows'][win]['clocks']['OPEN']['segments'] for d in g['days']}
 result=dict(D_GROSS10=intervals(read(dp),states),ARCHIVED_B=intervals(read(bp),states),scope='Original own ACT booleans and observed transitions only, original ACT20/BREAK63 unchanged. B calendar is diagnostic comparison, never D input. Fewer pause intervals can reflect changed realized risk path; no causal profit isolation or changed recovery rule inferred.',sources={str(p):sha(p) for p in [dp,bp,clock]},code_sha256=sha(Path(__file__)),new_accounts=0,new_finance_or_H_model=0,derived_independent_review='PENDING')
 (out/'OWN_ACT_RECOVERY_WAIT_PATH.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(win,{k:{q:v[q] for q in ['own_paused_OPEN_days','own_paused_CLOSE_days','NOT_DOWN_but_own_ACT_paused_OPEN_days']} for k,v in result.items() if k in ['D_GROSS10','ARCHIVED_B']},flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['long','strong'],required=True);args=ap.parse_args();main(args.window)
