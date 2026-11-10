"""Strict old-live versus new-fill quarter wealth bridge, saved books only."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,sys
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent
sys.path.insert(0,str(P));import analyze_results as A
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):(O/p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
out=[]
for ref in ['SC','PVR_SLOT1']:
 root=W/'2022-normal-reference-20261031/runs/B_diag' if ref=='SC' else P/'runs/2022'
 ds=rows(root/'pair/daily.jsonl.gz');layers=read(P/'analysis/2022'/ref/'LAYERS.json');byid={x['layer']:x for x in layers}
 def net_at(lid,r):
  x=next((x for x in r['layers'] if x['id']==lid),None)
  if x:return n(x['cash'])+n(x['dividend'])+D(x['qty'])*A.A.price(x['sid'],day(r['at']))
  l=byid[lid];assert l['closed'] is not None and day(l['closed'])<=day(r['at'])
  return n(l['net'])
 prev=None
 for q in ['2022Q1','2022Q2','2022Q3','2022Q4']:
  rr=[r for r in ds if str(pd.Timestamp(day(r['at'])).to_period('Q'))==q];end=rr[-1]
  old={x['id'] for x in prev['layers']} if prev else set()
  oldchange=sum((net_at(lid,end)-net_at(lid,prev) for lid in old),D(0))
  new=[l for l in layers if (prev is None or day(l['opened'])>day(prev['at'])) and day(l['opened'])<=day(end['at'])]
  newnet=sum((net_at(l['layer'],end) for l in new),D(0))
  navchange=n(end['nav'])-(n(prev['nav']) if prev else D(1000000));assert abs(oldchange+newnet-navchange)<D('.00000001')
  out.append(dict(reference=ref,quarter=q,old_live_layers_at_boundary=len(old),new_actual_fill_layers=len(new),
    old_live_later_wealth_change=oldchange,new_actual_layers_through_quarter_end=newnet,quarter_NAV_change=navchange,residual=D(0)))
  prev=end
save('2022_QUARTER_OLD_NEW_WEALTH_BRIDGE.json',out)
# Same-day entry uses the original frozen intent floor, not an absent previous held layer.
cases=read(O/'2022_DETERMINISTIC_FAILURE_CHAINS.json')
for r in cases:
 l=r['selected_layer'];p=r['previous_close_known_line_adjusted']
 if p is None and day(l['opened'])==day(r['exit_request']['request_at']):
  intent=next(x for x in r['all_actual_buy_chain'] if x['layer']==l['layer'])
  r['protective_line_before_trigger_adjusted']=intent['original_floor'];r['line_source']='same-day entry, original prior-decision frozen intent'
 else:r['protective_line_before_trigger_adjusted']=p;r['line_source']='previous completed close held-layer line'
save('2022_FAILURE_KNOWN_LINE_READOUT.json',cases)
print('QUARTER_BRIDGES',out,flush=True)
