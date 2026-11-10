"""Read existing descriptive outputs only; no feature/model or account imports."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import Counter
import json, hashlib
getcontext().prec=70
O=Path(__file__).resolve().parent
B=O.parent;A=B/'analysis_summary'
sources={}
def read(p):
    p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())
protocol=read(B/'decision_features/PROTOCOL.json')
dist=read(A/'DISTRIBUTIONS.json');overlap=read(A/'MONEY_WEIGHTED_OVERLAP.json')
literal=read(A/'LITERAL_HYPOTHESIS_DESCRIPTIVE.json')
cells=read(A/'ALL_CELL_COMPARISONS.json');tails=read(A/'FIXED_ORIGINAL_TAILS.json')
q=read(B/'decision_features/DESCRIPTIVE_CUTS.json')
out={'literal':{},'action_outcome_medians':{},'role_outcome_medians':{},'tail_controls':{}}
keep=['width_pct','r5_pct','r20_pct','CP1_used_scale_over_current_z','initial_width_over_current_z','entry_to_primary_request_held_CLOSE_observations']
def compact(z):
    return dict(labels=z.get('labels'),money=z['money'],medians={k:z['features'][k]['quantiles'][3] if z['features'][k]['quantiles'] else None for k in keep})
for scope in ['two_year','post303','strong']:
    out['literal'][scope]={k:dict(money=v['money'],negative_money_share=v['negative_money_share'],positive_money_share=v['positive_money_share'],by_action=[compact(z) for z in v['by_action']]) for k,v in literal[scope].items()}
    out['action_outcome_medians'][scope]=[compact(z) for z in dist[scope]['action_outcome_terminal']]
    out['role_outcome_medians'][scope]=[compact(z) for z in dist[scope]['role_outcome']]
out['overall_overlap']=[x for x in overlap if x['weak'] in ['two_year','post303'] and x['action']=='ALL' and x['role']=='ALL']
checks=[]
for scope in ['two_year','post303']:
    matches=[x for x in cells if x['weak']==scope and x['strongstate']=='all_positive' and x['pair']=='width_r5' and x['labels']=={'width_pct_q':'Q1','r5_pct_q':'Q4'}]
    assert len(matches)==1
    cell=matches[0];assert cell['weak_money']==literal[scope]['tightest_width_Q1_hottest_r5_Q4']['money']
    assert cell['strong_money']==literal['strong']['tightest_width_Q1_hottest_r5_Q4']['money']
    checks.append(scope+'_literal_equals_complete_cell')
for scope,original in tails.items():
    rows=[r for x in original for r in x['matched_rows']]
    groups={}
    for name,predicate in [('tight_hot5',lambda r:r['width_pct_q']=='Q1' and r['r5_pct_q']=='Q4'),('tight',lambda r:r['width_pct_q']=='Q1'),('hot5',lambda r:r['r5_pct_q']=='Q4'),('tight_hot20',lambda r:r['width_pct_q']=='Q1' and r['r20_pct_q']=='Q4')]:
        rr=[r for r in rows if predicate(r)]
        groups[name]=dict(layers=len(rr),original_path_net=sum((D(r['net']) for r in rr),D(0)),roles=dict(Counter(r['role'] for r in rr)),actions=dict(Counter(r['action'] for r in rr)),rows=[{k:r[k] for k in ['sid','name','layer','decision_at','role','action','net','width_pct','r5_pct','r20_pct','actual_exit_class']} for r in rr])
    out['tail_controls'][scope]=dict(original_members=len(original),exact_matched_members=sum(not x['unmatched'] for x in original),unmatched=sum(x['unmatched'] for x in original),groups=groups)
out['descriptive_pooled_cuts']=q
out['checks']=checks;out['sources']=sources
out['scope']={'new_features':0,'new_models':0,'new_accounts':0,'meaning':'Existing original-path descriptive evidence only; no avoided loss, attainable profit or counterfactual returns.'}
(O/'EVIDENCE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(dict(checks=checks,original_tails={k:{c:v[c] for c in ['original_members','exact_matched_members','unmatched']} for k,v in out['tail_controls'].items()},new_models=0,new_accounts=0),ensure_ascii=False))
