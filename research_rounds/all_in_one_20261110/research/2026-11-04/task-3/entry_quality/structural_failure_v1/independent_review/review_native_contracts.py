"""Pure native-contract review on saved No60 records; no account or market replay."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import json,gzip,hashlib,importlib.util
import pandas as pd
getcontext().prec=60
O=Path(__file__).resolve().parent;F=O.parent;E=F.parent;B=E/'trend_exit_controls_v1/runs/BASELINE';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
risk=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py');SRC[str(risk)]=sha(risk);spec=importlib.util.spec_from_file_location('independent_native_risk_formula_only',risk);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
recovery=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv');SRC[str(recovery)]=sha(recovery);rec=pd.read_csv(recovery,index_col=0,parse_dates=True);results={}
for win in ['2022_2024','strong']:
 book=read(B/win/'pair/B.json.gz');daily=read(B/win/'pair/daily.jsonl.gz',True);rr=[x for x in book['audit'] if x['kind']=='risk_checkpoint'];assert len(rr)==len(daily)==(726 if win=='2022_2024' else 242)
 state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0);events=[];paused=[];missed=[];episode=None
 for r in rr:
  day=pd.Timestamp(r['at'][:10]);row=rec.loc[day];assert r['fast']==bool(row.fast_on) and r['breakout']==bool(row.breakout)
  prior_on=state['on'];state,dd,event=M.advance(state,D(r['nav']),r['flat'],r['fast'],r['breakout'],'ACT20_BREAK')
  for k in ['on','peak','saw_off','previous_fast','episode']:assert state[k]==(D(r[k]) if k=='peak' else r[k])
  assert event==r['event'] and abs(dd-D(r['episode_drawdown']))<D('1e-20')
  if event=='pause':episode=dict(pause=r['at'],pause_NAV=r['nav'],phase_peak=r['peak'],first_flat=None,resume=None,paused_flat_observations=0,missed_breakout_while_not_flat=0);events.append(episode)
  if not prior_on or event=='pause':
   paused.append(r)
   if episode and r['flat'] and episode['first_flat'] is None:episode['first_flat']=r['at']
   if episode and r['flat']:episode['paused_flat_observations']+=1
   if r['breakout'] and not r['flat']:missed.append(r);episode['missed_breakout_while_not_flat']+=1
  if event=='resume':episode['resume']=r['at'];episode['resume_NAV']=r['nav']
 reserves=defaultdict(set);fills=defaultdict(set);fillcount=Counter();roles=Counter()
 for j in book['journal']:
  if j['kind']=='real_reserve' and j.get('receipt'):reserves[j['receipt']].add(j['budget_order'])
  if j['kind']=='real_buy_fill':
   roles[j['role'],j['pool']]+=1
   if j.get('CP1_id'):fills[j['CP1_id']].add(j['budget_order']);fillcount[j['CP1_id']]+=1
 assert all(len(v)==1 for v in reserves.values()) and all(len(v)==1 for v in fills.values())
 def nominal(d):return sum(D(str(d[k][1])) for k in ['pool_probe','pool_confirmed'])/D(d['nav'])
 results[win]=dict(checkpoints=len(rr),ACT_formula_and_current_external_flags_exact=True,episodes=events,breakout_lost_only_because_not_flat=len(missed),canonical_CP_reserved_ids=len(reserves),canonical_CP_filled_ids=len(fills),same_canonical_CP_multiple_distinct_reserve_or_fill_orders=0,CP_multiple_fill_records_same_original_order=sum(n>1 for n in fillcount.values()),fill_role_pool_counts={str(k):v for k,v in roles.items()},max_CLOSE_nominal_mark_to_floor_risk_fraction=str(max(nominal(d) for d in daily)),CLOSEs_nominal_risk_above_three_pct=sum(nominal(d)>D('.03') for d in daily),max_CLOSE_inventory_fraction=str(max(D(d['inventory'])/D(d['nav']) for d in daily)))
# Minimal formula counterexamples, not new financial paths or performance tests.
off=dict(on=False,peak=D(100),saw_off=False,previous_fast=True,episode=1)
s,_,ev=M.advance(off,D(80),True,True,True,'ACT20_BREAK');assert s['on'] and ev=='resume'
s,_,ev=M.advance(off,D(80),False,True,True,'ACT20_BREAK');assert not s['on'];s,_,ev=M.advance(s,D(80),True,True,False,'ACT20_BREAK');assert not s['on'] and ev is None
out=dict(status='PASS_NATIVE_ACT_PVR_CONTRACT_FACTS_NO_MECHANISM_SELECTED',results=results,formula_findings=['Original ACT20_BREAK pauses at20% drawdown from own current ON-episode peak; resume requires actualflat and current externalbreakout. No E0episode-age variable exists in this rule.','External recovery is sector-equal-weight stock log-return syntheticprice breaking prior63closehigh, positivecurrentpricechange and21amount-weightedpositive breadth>.6. Segment64valid warmup is not E0episode age.','A transient breakout can theoretically be missed beforeflat, but this original726+242 mother has0 such observations; latching it is not supported as the main current failure.','Stock CP canonical receipts are consumed once per order. Distinct new local CP receipts and persistent mature industry capacity may repeatedly finance risk; that is standing authorization, not a duplicate-ID bug.','No60 already removes original account3% nominal admission and confirmed60% capital caps. Mark-to-floor risk is not a maximum loss/DD and can grow with winners; observed risk excess does not prove those removed caps would improve economics.'],source_sha256=SRC,script_sha256=sha(__file__),new_accounts=0,new_market_or_signal_models=0,new_orders=0,limits=['Saved actualNAV/flat are inputs to pure ACT formula verification, not a counterfactual resumed account.','Canonical receipt/order identity checks do not certify statistical or economic independence of different stock/industry frontiers.','Diagnostic wealth/capital views may add only on mutually exclusive accounting dimensions; causal mechanism categories overlap.'])
(O/'NATIVE_ACT_PVR_CONTRACT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
