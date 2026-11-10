"""Summarize completed continuous arms. No engine imports, no account execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,csv,hashlib
ROOT=Path(__file__).resolve().parent
START,END='2023-01-03','2023-04-28'
def read(p):return json.loads(Path(p).read_text())
def load(p):return json.load(gzip.open(p,'rt'))
def rows(p):return [json.loads(l) for l in gzip.open(p,'rt')]
def money(x):return D(str(x))
def window(row):return START<=str(row['at'])[:10]<=END
def account(path):
 a=load(path/'pair/PVR.json.gz');daily=[x for x in rows(path/'pair/daily.jsonl.gz') if window(x)]
 qty=Counter();fills=[];sales=[];splits=[]
 for j in a['journal']:
  sid=j.get('sid');kind=j['kind']
  if kind=='real_buy_fill':
   before=qty[sid];qty[sid]+=j['shares']
   if window(j):fills.append(dict(day=j['at'][:10],sid=sid,qty=j['shares'],economic_class='flat_trial' if before==0 else 'held_add',before_qty=before,cash=money(j['price'])*j['shares']+money(j['fees']),fee=money(j['fees']),layer=j['layer']))
  elif kind=='real_sell_fill':
   qty[sid]-=j['shares'];assert qty[sid]>=0
   if window(j):sales.append(j)
  elif kind=='actual_split':
   qty[sid]=int(money(qty[sid])*money(j['ratio']))
   if window(j):splits.append(j)
 out=dict(buy_fills=len(fills),flat_trials=sum(x['economic_class']=='flat_trial' for x in fills),held_adds=sum(x['economic_class']=='held_add' for x in fills),buy_cash=sum((x['cash'] for x in fills),D(0)),trial_cash=sum((x['cash'] for x in fills if x['economic_class']=='flat_trial'),D(0)),add_cash=sum((x['cash'] for x in fills if x['economic_class']=='held_add'),D(0)),sell_fills=len(sales),sell_net=sum((money(j['price'])*j['shares']-money(j['fees']) for j in sales),D(0)),fee_total=sum((x['fee'] for x in fills),D(0))+sum((money(j['fees']) for j in sales),D(0)),actual_splits=len(splits),end_cash=daily[-1]['available'],end_nav=daily[-1]['nav'],end_holdings=len(daily[-1]['positions']),end_inventory=daily[-1]['inventory'],end_dividend_receivable=daily[-1]['dividend_receivable'])
 return out,daily,fills,a
def encode(x):
 if isinstance(x,D):return str(x)
 raise TypeError(type(x))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=encode)+'\n')
def csvout(p,rs):
 if not rs:return
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def main():
 assert read(ROOT/'baseline/run/BASELINE_VALIDATION.json')['passed']
 assert read(ROOT/'growth/run/DONE.json')['completed']
 out=ROOT/'comparison';assert not out.exists();out.mkdir()
 control,cd,cf,ca=account(ROOT/'baseline/run');growth,gd,gf,ga=account(ROOT/'growth/run')
 cmap={x['at']:x for x in cd};gmap={x['at']:x for x in gd};assert list(cmap)==list(gmap)
 daily=[dict(day=k[:10],original_cash=cmap[k]['available'],growth_cash=gmap[k]['available'],cash_difference=money(gmap[k]['available'])-money(cmap[k]['available']),original_nav=cmap[k]['nav'],growth_nav=gmap[k]['nav'],nav_difference=money(gmap[k]['nav'])-money(cmap[k]['nav']),original_holdings=len(cmap[k]['positions']),growth_holdings=len(gmap[k]['positions'])) for k in cmap]
 fillmap={}
 for arm,fs in [('original',cf),('growth',gf)]:
  for x in fs:
   key=(x['day'],x['sid'])
   assert arm not in fillmap.setdefault(key,{}),(key,'duplicatefill')
   fillmap[key][arm]=x
 pairs=[]
 for (day,sid),v in sorted(fillmap.items()):
  a=v.get('original');b=v.get('growth')
  pairs.append(dict(day=day,sid=sid,original_qty=a['qty'] if a else 0,growth_qty=b['qty'] if b else 0,original_class=a['economic_class'] if a else '',growth_class=b['economic_class'] if b else '',original_before=a['before_qty'] if a else None,growth_before=b['before_qty'] if b else None,original_cash=a['cash'] if a else D(0),growth_cash=b['cash'] if b else D(0)))
 cand=rows(ROOT/'growth/run/GROWTH_CANDIDATES.jsonl.gz');held=[x for x in cand if not x['flat']]
 observations=rows(ROOT/'growth/run/GROWTH_OBSERVATIONS.jsonl.gz')
 realparts=[x for x in rows(ROOT/'growth/run/REALIZED_LAYER_PARTS.jsonl.gz') if window(x)]
 diag=dict(held_candidates=len(held),H_positive_candidates=sum(money(x['H'])>0 for x in held),H_positive_selected=sum(money(x['H'])>0 and x['selected_qty']>0 for x in held),P_positive_candidates=sum(money(x['P'])>0 for x in held),delta_positive_candidates=sum(money(x['delta'])>D('1e-12') for x in held),delta_negative_candidates=sum(money(x['delta'])<D('-1e-12') for x in held),avg_positive_layer_nonpositive=sum(money(x['U_avg'])>0 and money(x['U_layer'])<=0 for x in held),avg_nonpositive_layer_positive=sum(money(x['U_avg'])<=0 and money(x['U_layer'])>0 for x in held),unknown_candidates=sum(bool(x['unknown']) for x in cand),unknown_observations=sum(bool(x['unknown']) for x in observations),realized_parts=len(realparts),negative_added_parts=sum(x['added'] and money(x['realized'])<0 for x in realparts),negative_seed_parts=sum(not x['added'] and money(x['realized'])<0 for x in realparts))
 # Actual trial entry differences are effects of continuous cash/NAV/path, not new trial predicates.
 trials=dict(original_only_day_stock=sum(x['original_class']=='flat_trial' and not x['growth_class'] for x in pairs),growth_only_day_stock=sum(x['growth_class']=='flat_trial' and not x['original_class'] for x in pairs),original_trial_growth_add=sum(x['original_class']=='flat_trial' and x['growth_class']=='held_add' for x in pairs),original_add_growth_trial=sum(x['original_class']=='held_add' and x['growth_class']=='flat_trial' for x in pairs))
 summary=dict(scope=[START,END],sessions=78,seed_checkpoint='2022-12-30',original=control,growth=growth,diagnostics=diag,trial_pairing=trials,end_cash_difference=money(growth['end_cash'])-money(control['end_cash']),end_nav_difference=money(growth['end_nav'])-money(control['end_nav']),original_exact_reproduction=True,new_formula_uses_actual_layer_cost=True,H_all_diagnostic_only=True,not_924_validation=True,not_PIT_or_certified_tradability=True,no_parameter_scan=True)
 save(out/'SUMMARY.json',summary);csvout(out/'DAILY_CASH_NAV.csv',daily);csvout(out/'FILL_PAIRS.csv',pairs);csvout(out/'ORIGINAL_FILLS.csv',cf);csvout(out/'GROWTH_FILLS.csv',gf)
 selected_cases=[x for x in cand if x['sid'] in ('002281.SZ','601019.SH','603589.SH','601000.SH')]
 save(out/'MECHANISM_CASES.json',selected_cases)
 save(out/'SOURCE_HASHES.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'baseline/run/BASELINE_VALIDATION.json',ROOT/'growth/run/DONE.json',ROOT/'growth/run/GROWTH_CANDIDATES.jsonl.gz',ROOT/'growth/run/REALIZED_LAYER_PARTS.jsonl.gz']})
 print(json.dumps(summary,ensure_ascii=False,default=encode))
if __name__=='__main__':main()
