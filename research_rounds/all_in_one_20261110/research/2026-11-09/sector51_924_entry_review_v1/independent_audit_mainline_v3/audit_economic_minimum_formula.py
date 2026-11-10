"""Pure formula / dated-rule checks only. Does not run an account or select investments."""
from pathlib import Path
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
import json,hashlib
O=Path(__file__).resolve().parent/'economic_minimum_formula';O.mkdir(exist_ok=True);path=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json');rules=json.loads(path.read_text());dt='2024-09-26';Z=D(0)
def version(vs,t):
 out=[v for v in vs if v['from']<=t and (not v.get('to') or t<v['to'])];assert len(out)==1;return out[0]
def brokerage(venue,q,p,side,minimum=True):
 cc=[c for c in version(rules['fee_versions'][venue],dt)['schedule']['components'] if c['name']=='net_brokerage' and c.get('side','both') in ['both',side]];assert len(cc)==1
 c=cc[0];assert c.get('amount_basis','notional')=='notional' and c.get('basis')=='order';out=D(q)*p*D(c['rate']);out=max(out,D(c.get('minimum_local','0'))) if minimum else out
 if c.get('maximum_local') is not None:out=min(out,D(c['maximum_local']))
 if c.get('rounding_unit') is not None:
  u=D(c['rounding_unit']);out=(out/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
 return out
def penalty(venue,q,C):
 pb=C*D('1.0005');ps=C*D('.9995');return brokerage(venue,q,pb,'buy')+brokerage(venue,q,ps,'sell')-brokerage(venue,q,pb,'buy',False)-brokerage(venue,q,ps,'sell',False)
def econ(venue,C,minimum,step):
 def q(k):return minimum+step*k
 def ok(k):return penalty(venue,q(k),C)<=D('.001')*q(k)*C
 if ok(0):return minimum
 lo=0;hi=1
 while not ok(hi):hi*=2
 while hi-lo>1:
  mid=(lo+hi)//2
  if ok(mid):hi=mid
  else:lo=mid
 return q(hi)
rows=[];count=0
for venue,minimum,step in [('SSE_MAIN',100,100),('SZSE_MAIN',100,100),('SZSE_CHINEXT',100,100),('SSE_STAR',200,1),('BSE',100,1)]:
 for px in ['1','7.5','8','10','50','100','300']:
  C=D(px);q=econ(venue,C,minimum,step);p=penalty(venue,q,C);bound=D('.001')*q*C;assert q>=minimum and (q-minimum)%step==0 and p<=bound
  prev=q-step if q>minimum else 0
  if prev:assert penalty(venue,prev,C)>D('.001')*prev*C
  threshold=D(10)/D('.0014');continuous_legal=max(minimum,minimum+max(0,int(((threshold/C-D(minimum))/D(step)).to_integral_value(rounding=ROUND_CEILING)))*step);assert q==continuous_legal
  schedule=version(rules['fee_versions'][venue],dt)['schedule'];buy_comm=brokerage(venue,q,C*D('1.0005'),'buy');proportional_buy=brokerage(venue,q,C*D('1.0005'),'buy',False);sell_comm=brokerage(venue,q,C*D('.9995'),'sell');rows.append(dict(venue=venue,CLOSE=str(C),legal_min=minimum,legal_step=step,q_econ=q,raw_notional=str(q*C),minimum_extra_penalty=str(p),allowed_penalty=str(bound),previous_legal_q=prev,previous_fails=bool(prev),buy_commission=str(buy_comm),sell_commission=str(sell_comm),unfloored_buy_commission=str(proportional_buy),statutory_components_unchanged=[c['name'] for c in schedule['components'] if c['name']!='net_brokerage'],fits_2pct_1200000_even_before_other_fees=q*C*D('1.0005')+buy_comm<=D(24000)));count+=1
assert econ('SSE_MAIN',D(8),100,100)==900 and econ('SSE_MAIN',D('7.5'),100,100)==1000
report=dict(result='PASS',formula_tests=count,continuous_raw_notional_threshold=str(D(10)/D('.0014')),same_rate_minimum_all_five_venues=True,basis='Existing explicitly frozen research fee/quantity schedule, not newly certified broker or exchange rules.',critical_constraints=['Only the net_brokerage minimum surcharge is removed in counterfactual; stamp/handling/regulatory/transfer remain payable.','Both legs use an explicitly stated planning quote/date assumption. This is not a known future exit price or fee bill.','Minimum legal q is a lower bound. After applying amount/quantity/cash/industry caps, any q below it is no trade, not a tiny economic seed.','CLOSE q=900 at C8 needs OPEN q=1000 at price7.5 under this gate; a frozen upper900 cannot be expanded, so no fill if OPEN recheck is required.','At C300 the100-share legal minimum is30000 and exceeds2% of1.2m even before full fees; there is no feasible admitted lot.','Multiple actual partial sell orders can each incur their own minimum; the two-order proxy does not bound future whole-round fees.','Larger original SEED quantity mechanically enlarges the retained seed-equivalent first-ADD core under inherited M3 core rules.','Industry event cost is actual SEED all-in cumulative spend; not refreshed daily and not replenished by sells or dividends.','Cold-start previously valid events retain true event birth date/B identity; only once anchor24k to initial1.2m account NAV, mark left-censored. Unknown chain does not fabricate an event.','Close plans reserve industry event allowance cumulatively before any fill; actual fills charge once. Canceled plans release reservations only, atomic rollback restores event/used/reserved/identity.','Industry round-robin or whole-group selection changes opportunity order; freeze exact industry order, stock head, skip behavior, pass count, and OPEN only-shrink behavior before account execution.'],cases=rows,source_hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest(),str(Path(__file__)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
(O/'FORMULA_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['cases','source_hashes']},ensure_ascii=False))
