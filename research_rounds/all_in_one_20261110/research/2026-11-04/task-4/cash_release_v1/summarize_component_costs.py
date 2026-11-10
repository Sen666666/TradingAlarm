"""Final snapshot cash stocks and unchanged original-order references, no PnL."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import hashlib,json,statistics
O=Path(__file__).resolve().parent;F=O/'funding';OLD=O.parent/'reentry_v1/funding_agent/private_projection';S={}
def read(p):
 p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def stat(a):return dict(n=len(a),minimum=min(a),median=statistics.median(a),maximum=max(a))
cash=read(F/'CONDITIONAL_CASH_BUFFER_COST_BY_OPEN.json')
summary={}
for arm in ['A1','B1']:
 control=arm[0]+'0';a=[float(r[arm]['available']) for r in cash]
 summary[arm]=dict(post_plan_available_cny=stat(a),post_plan_available_pct_decision_NAV=stat([float(r[arm]['available'])/float(r['decision_NAV'])*100 for r in cash]),
  post_plan_available_below_1000_S0s=sum(v<1000 for v in a),
  nominal_stop_risk_increment_pct_decision_NAV=stat([(r[arm]['nominal_risk']-r[control]['nominal_risk'])/float(r['decision_NAV'])*100 for r in cash]),
  scope='All new orders reserved, known fees included; not actual fills or EOD cash; original13 independent S0s, not new continuous liquidity/drawdown; risk is nominal stop exposure, not realized loss')
save('POST_PLAN_CASH_AND_RISK_COMPONENT_COSTS.json',summary)
A=read(F/'A_NATIVE_ALL4172_COMPARISONS.json');B=read(F/'B_MINFIRST_ALL4172_COMPARISONS.json');bb={(r['opening'],r['key']):r for r in B}
refs={r['comparison']['key']:r['original_path_reference'] for r in read(OLD/'ON_ORIGINAL50_ORDER_OPPORTUNITY_REFERENCES.json')}
entries={(r['opening'],r['key']):r for r in read(OLD/'ON_ALL4172_CANDIDATE_COMPARISONS.json')}
out=[];winners=[]
for a in A:
 if not a['old_order']:continue
 b=bb[a['opening'],a['key']];old=a['old_order'];new=b['new_order'];oq=old['quantity'];nq=new['quantity']if new else 0
 kind='lost'if not new else 'shrunk'if nq<oq else 'increased'if nq>oq else 'same_quantity'
 r=dict(OPEN=a['opening'],key=a['key'],sid=a['sid'],name=entries[a['opening'],a['key']]['name'],
  A0_quantity=oq,A1_quantity=a['new_order']['quantity']if a['new_order']else 0,
  B0_quantity=b['old_order']['quantity']if b['old_order']else 0,B1_quantity=nq,B1_relative_to_A0=kind,
  original_whole_order_path_reference=refs[a['key']],no_proportional_PnL=True,
  scope='Two-factor B1 vs A0 diagnostic only; original whole path never rescaled; original path fills may differ from both B0 and B1 quantities')
 out.append(r)
 if (a['sid'],a['opening']) in [('603618.SH','2026-02-09'),('603618.SH','2026-02-10'),('001896.SZ','2026-02-26'),('600584.SH','2026-05-21')]:winners.append(r)
assert len(out)==50 and len(winners)==4
save('B1_TO_ORIGINAL50_ORDER_REFERENCES.json',out);save('FOUR_EXISTING_WINNER_QUANTITY_COMPARISON.json',winners)
save('B1_TO_ORIGINAL50_COUNTS.json',dict(counts=dict(Counter(r['B1_relative_to_A0']for r in out)),
 two_factors_not_cash_single_factor=True,original50_complete=True,missing_new_orders_not_assumed_negative=True))
S[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('COMPONENT_COST_SOURCE_SHA256.json',S)
print(json.dumps(summary,ensure_ascii=False,indent=2));print(Counter(r['B1_relative_to_A0']for r in out))
