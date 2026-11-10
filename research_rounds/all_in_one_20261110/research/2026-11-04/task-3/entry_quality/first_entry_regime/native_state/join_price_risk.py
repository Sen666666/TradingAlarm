"""Complete native-state x original prior63-high crossing. Zero model/account imports."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,json,hashlib,itertools,csv
O=Path(__file__).resolve().parent;P=O.parent/'price_risk_groups'
spec=importlib.util.spec_from_file_location('native_state_pure_agg',O/'analyze.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,z):
 with (O/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,default=str)
def key(x):return (x['window'],x['layer'],x['sid'],x['decision_at'])
sources={};mother={};allrows={};joint={};joins={}
for ref in ['2022_2024','strong']:
 np=O/(ref+'_FIRST_ROWS.json');pp=P/(ref+'_FIRST_ROWS.json');sources[str(np)]=sha(np);sources[str(pp)]=sha(pp)
 native=read(np);price=read(pp);pmap={key(x):x for x in price};out=[]
 assert len(pmap)==len(price)
 for x in native:
  k=(ref,x['layer'],x['sid'],x['decision_at']);p=pmap[k]
  for f in ['opened','budget_order','role','pool_at_fill','cost','net','strict_realized','open_unrealized','recognized_dividend_AR']:
   assert x[f]==p[f],(ref,k,f)
  x['window']=ref;x['price_risk_state']={f:p[f] for f in ['stock_prior63','industry_prior63','stock_breakout','industry_breakout','stock_gap_prior63high_pct','industry_gap_prior63high_pct','decision_protection_width_pct','decision_budget_pct_NAV','decision_cap_reference_gross_pct_NAV']}
  x['stock_breakout']=p['stock_breakout'];out.append(x)
  assert x['native_ACT_fast'] in [False,True] and x['native_industry_stage'] in ['probe','confirmed','expanded'] and x['stock_breakout'] in ['above_prior63closehigh','not_above_prior63closehigh']
 mother[ref]=A.agg(out);allrows[ref]=out
 joins[ref]=dict(native_first_rows=len(native),price_first_rows_available=len(price),exact_identity_joins=len(out),unchanged_original_money_and_role_pool=True,selected='2022-23 first772' if ref=='2022_2024' else 'strong first671',price_three_year_extra_not_joined=len(price)-len(out))
 save(ref+'_JOINT_FIRST_ROWS.json',out)
levels={'native_ACT_fast':[False,True],'native_industry_stage':['probe','confirmed','expanded'],'stock_breakout':['not_above_prior63closehigh','above_prior63closehigh'],'role':['core','mobile']}
for values in itertools.product(*levels.values()):
 labels=dict(zip(levels,values));panel={}
 for ref,rows in allrows.items():
  z=[x for x in rows if all(x[k]==v for k,v in labels.items())];agg=A.agg(z);total=mother[ref]
  for metric in ['layers','cost','positive_net','negative_net','terminal_tail_layer_count','terminal_tail_layer_net']:
   agg[metric+'_mother_share_pct']=None if not total[metric] else D(str(agg[metric]))/D(str(total[metric]))*100
  panel[ref]=agg
 joint[json.dumps(labels,ensure_ascii=False)]=dict(labels=labels,cohorts=panel)
for ref,total in mother.items():
 assert sum(r['cohorts'][ref]['layers'] for r in joint.values())==total['layers']
 for metric in ['cost','net','positive_net','negative_net','terminal_tail_layer_net']:
  assert abs(sum((D(str(r['cohorts'][ref][metric])) for r in joint.values()),D(0))-D(str(total[metric])))<D('1e-18')
save('JOINT_COMPLETE_CROSS.json',dict(mothers=mother,levels=levels,all_cells=list(joint.values()),cell_count=len(joint),no_cell_selected_or_threshold_search=True,all_empty_cells_retained=True))
assert sum(v['exact_identity_joins'] for v in joins.values())==1443
save('JOINT_JOIN_VALIDATION.json',dict(checks=joins,total_exact_identity_joins=1443,total_expected_first_mother=772+671,unknown_join_keys=0,unknown_crossing_dimensions=0,sources=sources,script_sha256=sha(Path(__file__)),group_sums_exact=True,new_accounts=0,new_features=0))
flat=[]
for r in joint.values():
 for ref,m in r['cohorts'].items():flat.append(dict(window=ref,**r['labels'],**{k:str(v) if isinstance(v,D) else v for k,v in m.items()}))
with (O/'JOINT_COMPLETE_CROSS.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
for r in joint.values():
 print(r['labels'],[(ref,m['layers'],round(float(m['positive_net']),2),round(float(m['negative_net']),2),round(float(m['net']),2),m['terminal_tail_layer_count']) for ref,m in r['cohorts'].items()])
