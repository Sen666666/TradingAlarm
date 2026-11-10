from pathlib import Path
import gzip,json
O=Path(__file__).resolve().parents[1];A=O.parent/'actual-risk-recovery-20261027'
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
x=rows(O/'CONTROL/technical/short-v2/daily.jsonl.gz');y=[r for r in rows(A/'CONTROL/accounts-v2/daily.jsonl.gz') if r['at'][:10]<='2024-03-29'];assert x==y
for aid in ['I__S0_base','I__S0_cost2','I__S0_delay1']:
 x=json.loads((O/'CONTROL/technical/short-v2'/f'{aid}.json').read_text())['fills'];y=json.loads((A/'CONTROL/accounts-v2'/f'{aid}.json').read_text())['fills'];assert x==[r for r in y if r['at'][:10]<='2024-03-29']
(O/'control-short.json').write_text(json.dumps({'passed':True,'daily_rows':177,'fills_exact':True},indent=2));print('short control exact')
