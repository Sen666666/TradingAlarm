"""Arithmetic over exported actual H1 semiconductor paths, no policy replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,importlib.util
import pandas as pd
P=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
s=importlib.util.spec_from_file_location('saved_semis_cache',W/'pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/analyze_readonly.py');S=importlib.util.module_from_spec(s);s.loader.exec_module(S)
Z=D(0)
def n(x):return D(str(x))
def read(p):return json.loads(Path(p).read_text())
def save(name,x):
 with (P/name).open('x') as f:json.dump(S.clean(x),f,ensure_ascii=False,indent=2,default=str)
def main():
 out={};puran={};sources={}
 for pol in ['PVR_BASELINE','PVR_NO60']:
  accepted=read(P/(pol+'-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json'));funnel=read(P/(pol+'-SEMICONDUCTOR_FUNNEL.json'))['all_market_receipts']
  layers=read(P.parent/'pvr_no60_2025_26/analysis/2025_26'/pol/'LAYERS.json');lm={x['layer']:x for x in layers}
  actions=read(P.parent/'pvr_no60_2025_26'/(pol+'-ENTRY_ACTIONS.json'));am={x['layer']:x for x in actions};summary=[]
  for a in accepted:
   l=lm[a['layer']];fill=a['actual_fill'];end=l['closed'][:10] if l['closed'] else '2026-06-30';start=fill['at'][:10];f=S.frame(a['sid']).loc[start:end]
   if l['closed']:f=f.loc[f.index<pd.Timestamp(end)]
   assert len(f)>0,'requires a recorded held CLOSE; no future exit-day close'
   costprice=n(fill['price'])*n(a['entry_factor_known_corporate_action_units']);maxgain=(n(f.close.max())/costprice-1)*100
   exits=a['exit_requests'];reasons=[x['reason'] for x in exits]
   summary.append(dict(layer=a['layer'],sid=a['sid'],name=a['name'],signal=a['signal_day'],opened=start,closed=end if l['closed'] else None,role=a['role'],pool=a['pool_at_fill'],action=am[a['layer']]['action'],buy_cost=n(l['cost']),net=n(l['net']),quantity=l['qty'],initial_nominal_price_to_floor_risk=n(a['initial_nominal_price_to_floor_risk']),original_initial_raw_floor=n(a['actual_initial_raw_floor']),actual_price=n(fill['price']),actual_exit_reasons=reasons,observations_from_fill_through_exit=len(f),maximum_close_gain_during_actual_holding_pct=maxgain,closed_net_negative=not l['qty'] and n(l['net'])<0,ever_close_above_actual_fill=maxgain>0))
  groups={}
  for k,rs in [('all',summary),('closed_negative_no_positive_close',[x for x in summary if x['closed_net_negative'] and not x['ever_close_above_actual_fill']]),('closed_negative_previously_positive_close',[x for x in summary if x['closed_net_negative'] and x['ever_close_above_actual_fill']]),('closed_positive',[x for x in summary if not x['quantity'] and x['net']>0]),('open',[x for x in summary if x['quantity']])]:
   groups[k]=dict(layers=len(rs),buy_cost=sum((x['buy_cost'] for x in rs),Z),net=sum((x['net'] for x in rs),Z),initial_nominal_risk=sum((x['initial_nominal_price_to_floor_risk'] for x in rs),Z))
  exits=Counter(r for x in summary for r in x['actual_exit_reasons']);same_day=Counter(x['observations_from_fill_through_exit'] for x in summary if x['closed_net_negative'])
  out[pol]=dict(groups=groups,actual_exit_requests=dict(exits),closed_loss_holding_observation_counts=dict(same_day),actual_entry_actions=dict(Counter(x['action'] for x in summary)),all_actual_layers=summary,scope='H1 actual new filled layers only; lifecycle net to actual exit/Jun30, not whole H1 interval and not independent trials; maximum-close gain is post-result diagnostic only')
  rr=[x for x in funnel if x['sid']=='688766.SH'];puran[pol]=dict(market_receipts=len(rr),category_counts=dict(Counter(x['category'] for x in rr)),normalized_no_plan=Counter(x['normalized_no_plan']['normalized'] for x in rr if x['normalized_no_plan']),all_receipts=rr)
 save('SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json',out);save('PURAN_H1_FULL_FUNNEL.json',puran)
 # Development-only exposure test of a proposed signature, not trading logic:
 # before a new mobile addition's signal close, was any still-held prior real
 # layer's actual protection already strictly higher than its original floor?
 probe=[]
 for sid in ['002747.SZ','002718.SZ','002969.SZ','300489.SZ']:
  a=read(P/(sid+'-FULL_SAVED_PATH.json'))
  for pol,z in a['policies'].items():
   for l in z['layers']:
    if l['entry_action']['action']!='add_to_existing_stock':continue
    signal=l['actual_fill']['signal_at'][:10];prior=[q for q in z['layers'] if q['actual_fill']['at']<l['actual_fill']['at'] and (not q['original_terminal_layer']['closed'] or q['original_terminal_layer']['closed'][:10]>signal)]
    witness=[]
    for q in prior:
     for r in q['after_close_actual_layer_state']:
      if r['day']<signal and n(r['active_actual_floor'])>n(q['initial_adjusted_floor']):witness.append(dict(layer=q['layer'],day=r['day'],initial=q['initial_adjusted_floor'],actual=r['active_actual_floor']));break
    probe.append(dict(sid=sid,policy=pol,layer=l['layer'],signal_day=signal,original_entry_action=l['entry_action'],has_prior_actual_protection_advance=bool(witness),prior_witness=witness,original_actual_layer_net=n(l['original_financial_attribution']['net']),quantity=l['original_terminal_layer']['qty'],interpretation='opportunity cost/exposure control only; removing this layer does not simulate later funding/holdings'))
 save('PRIOR_PROGRESS_DEVELOPMENT_PROBE.json',dict(rows=probe,zero_economic_paths=True,policy_implemented=False,prior_day_strict_before_signal=True,proposed_signature_falsified_as_sufficient='The largest extra closed winner Jiamei Dec8 mobile +66785 has no earlier protection advance before Dec5 signal; a strict prior-day proof would suppress it. Ordinary losses can also occur after prior proof. No economic gate warranted.'))
 save('LIFECYCLE_SOURCE_BINDING.json',dict(caches=S.SRC,reader=str(Path(__file__)),sha256=S.sha(__file__),financial_events=0,new_signals=0))
 print(json.dumps(S.clean(dict(semis={k:{q:v for q,v in a.items() if q!='all_actual_layers'} for k,a in out.items()},puran={k:{q:v for q,v in a.items() if q!='all_receipts'} for k,a in puran.items()})),indent=2,ensure_ascii=False))
if __name__=='__main__':main()
