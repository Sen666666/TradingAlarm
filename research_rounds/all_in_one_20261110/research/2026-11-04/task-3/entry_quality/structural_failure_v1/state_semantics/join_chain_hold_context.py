from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent;E=O.parents[1]
c=json.loads((O/'TEN_REPRESENTATIVE_CHAINS.json').read_text());hr=json.loads((O/'HELD_NEGATIVELEG_FIRST_SCOPE.json').read_text());h={(x['window'],x['layer']):x for x in hr};assert len(h)==len(hr)==2741
p={r:E/'entry_exit_scale/holding_exit'/(r+'_LAYERS.json') for r in ['2022_2024','strong']};s={r:{x['layer']:x for x in json.loads(q.read_text())} for r,q in p.items()}
for chain in c['chains']:
 ref='strong' if chain['cohort']=='strong' else '2022_2024'
 for e in chain['entry_nodes']:
  o=s[ref][e['layer']];e['original_exit_request_events']=o['original_exit_request_events'];e['actual_terminal_exit_class']=o['actual_exit_class'];e['first_original_pre_request_I_on_negativeleg']=h.get((ref,e['layer']));e['not_counterfactual_exit']='original request/actual exit and first causal state only; no alternative exit price/new PnL'
(O/'TEN_REPRESENTATIVE_CHAINS_WITH_HOLD_CONTEXT.json').write_text(json.dumps(c,ensure_ascii=False,indent=2,allow_nan=False)+'\n');(O/'TEN_CHAIN_HOLD_SOURCE_SHA256.json').write_text(json.dumps({str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in p.values()},indent=2)+'\n')
print('joined',len(c['chains']),'chains',sum(len(x['entry_nodes']) for x in c['chains']),'original entries')
