"""Read-only mechanism scope check; no model, order, account or price import."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D, getcontext
import hashlib, json

O=Path(__file__).resolve().parent
getcontext().prec=70
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
files=[B/'risk_constraints/ma63_information_diagnostic_v1/2022_2024_ENTRIES.json',
       B/'risk_constraints/ma63_information_diagnostic_v1/strong_ENTRIES.json',
       B/'loss_correction/absolute_loss_2022_2023/READOUT.txt',
       B/'loss_correction/continuation2024_layers/READOUT.txt',
       B/'loss_correction/entry_risk_commitment_review/FINAL_DISPOSITION_STOP.txt',
       B/'loss_correction/mobile_current_grade_quickcheck_v1/SUMMARY.json',
       B/'loss_correction/mobile_current_grade_quickcheck_v1/FIXED_ORIGINAL_TAILS.json',
       W/'industry-mobile-stage-20261031/stage.py',
       W/'case-stage-ledger-20261031/v3/joint_v3.py',
       W/'case-stage-ledger-20261031/budget_v3/model.py',
       W/'market-proof-lifecycle-readonly-20261101/CORE_READOUT.txt',
       W/'stage-progress-R-diagnostic-20261031/READOUT.txt',
       W/'pvr-slot1-native-readiness-20261101/native_rank.py',
       W/'pvr-current-v3-information-capital-20261101/original_score_function.py',
       Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-drawdown-regime-20261027/CONCLUSION.md')]
def read(p):return json.loads(p.read_text())
def agg(rows):
    return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),
      cost=sum((D(x['cost']) for x in rows),D(0)),net=sum((D(x['net']) for x in rows),D(0)),
      strict_realized=sum((D(x['strict_realized']) for x in rows),D(0)),
      open_unrealized=sum((D(x['open_unrealized']) for x in rows),D(0)),
      dividend_AR=sum((D(x['recognized_dividend_AR']) for x in rows),D(0)))
rows=read(files[0]);strong=read(files[1]);assert len(rows)==2265 and len(strong)==1171
two=[x for x in rows if x['opened'][:10]<'2024-01-01']
post=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31']
assert len(two)==1557 and len(post)==303
result={}
for name,z in [('2022_2023',two),('2024_postOct8_newfills',post),('2022_2024',rows),('strong',strong)]:
    result[name]={'all':agg(z),'actions':{a:agg([x for x in z if x['action']==a]) for a in sorted({x['action'] for x in z})}}
    assert sum(v['net'] for v in result[name]['actions'].values())==result[name]['all']['net']
    assert abs(result[name]['all']['net']-sum(result[name]['all'][k] for k in ['strict_realized','open_unrealized','dividend_AR']))<D('0.00000001')
result['scope']={'new_model_events':0,'new_account_events':0,'meaning':'Existing actual-fill lifecycle contributions, not avoidable loss or counterfactual returns; layer observations are dependent.'}
result['sources']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(O/'SCOPE_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({k:v['actions'] for k,v in result.items() if k in ['2022_2023','2024_postOct8_newfills']},ensure_ascii=False,default=str,indent=2))
