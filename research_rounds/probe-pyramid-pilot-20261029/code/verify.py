"""Causal/serialization identity and frozen input audit; no new economic variants."""
from pilot import *
import ast
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
def main():
 original=rows(O/'results-v2-serialization-failed/daily.jsonl.gz');final=rows(O/'results/daily.jsonl.gz');assert original==final
 prefix=rows(O/'technical-prefix/daily.jsonl.gz');fullprefix=[r for r in final if r['account']=='P1' and r['at'][:10]<='2025-12-31'];assert prefix==fullprefix
 early=read(O/'technical-prefix/P1.json');full=read(O/'results/P1.json');ft=[r for r in full['trades'] if r['at'][:10]<='2025-12-31'];assert early['trades']==ft
 fd=[r for r in full['decisions'] if r['at'][:10]<='2025-12-31'];assert early['decisions']==fd
 frozen=read(O/'FREEZE.json');mismatched={k:dict(frozen=v,current=sha(ROOT/k)) for k,v in frozen['sha256'].items() if sha(ROOT/k)!=v};assert set(mismatched)<= {str((O/'code/analyze.py').relative_to(ROOT))}
 oldtree=ast.parse((O/'pilot-v2-failed.txt').read_text());newtree=ast.parse((O/'code/pilot.py').read_text())
 for symbol in ['allocate','fee','Account','Pilot']:
  left=next(n for n in oldtree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==symbol);right=next(n for n in newtree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==symbol);assert ast.dump(left)==ast.dump(right),(symbol,'economic implementation changed')
 previous=read(O/'FREEZE-v2.json')['sha256'];current=frozen['sha256'];changed=[k for k,v in previous.items() if k in current and current[k]!=v];assert changed==[str((O/'code/pilot.py').relative_to(ROOT))]
 records=read(ROOT/'research_rounds/pvr-act-comparison-20261027/input/manifest.json')['series'];checks=[]
 for r in records:
  assert sha(r['raw']['path'])==r['raw']['sha256'];checks.append(r['raw']['path'])
  actions=r.get('adjustment',{}).get('actions')
  if actions:
   assert sha(actions['path'])==actions['sha256'];checks.append(actions['path'])
 # Provider identity check on existing ACT fills, not a newly simulated ACT account.
 act=read(ROOT/'research_rounds/pvr-act-comparison-20261027/RS/accounts-v2/I__S0_base.json');raw={};fillchecks=0
 for x in act['audit_log']:
  if x['kind']!='fill':continue
  r=x['receipt'];sid=r['security_id'];day=r['at'][:10]
  if sid not in raw:raw[sid]=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet')
  op=D(str(raw[sid].loc[day].raw_open));assert op==D(x['raw_open']);assert D(x['price'])==op*(D('1.0005') if r['side']=='buy' else D('.9995'));fillchecks+=1
 # Every initial/add contract and funding event is a past-close decision.
 count=0
 for name in ['P0','P1','D1']:
  obj=read(O/f'results/{name}.json');dmap={r['at']:D(r['nav']) for r in obj['decisions']}
  for r in obj['decisions']:
   for i in r['intents']:
    assert D(i['budget'])<=D(r['nav'])*D('.02');assert i['kind'] in ('core','add');count+=1
    if i['kind']=='add':assert i['reason']=='CP1_confirmation' and i['score']>50
  for r in obj['audit']:
   if r['kind']=='pilot_frozen_funding':assert r['signal_at']<r['at'] and D(r['budget'])<=D(r['desired'])
 save(O/'VERIFICATION.json',dict(passed=True,complete_daily_rows_unchanged_after_serialization_fix=len(final),physical_cutoff='2025-12-31',physical_prefix_rows=len(prefix),prefix_trades=len(ft),prefix_decisions=len(fd),frozen_artifacts_unchanged=len(frozen['sha256'])-len(mismatched),reporting_only_changes=mismatched,reporting_change_reason='Add existing ACT reference curve; no trading logic changes',economic_classes_AST_identical=True,original_raw_and_action_hash_checks=len(checks),existing_ACT_fill_provider_checks=fillchecks,intent_budget_checks=count,rule_parameter_changes_after_results=0,economic_replays_for_output_repair=1,successful_new_paths=3,notes='Prefix ran with physical truncated prices/facts/CP1/H1; PVR looked up only at current date. B0 audit prefix is only a legacy count-assertion bypass.'))
 print('VERIFIED',len(final),len(prefix),len(ft),len(checks),count)
if __name__=='__main__':main()
