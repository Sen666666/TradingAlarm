"""Native daily risk and existing factual factor helper; no signal/account replay."""
from pathlib import Path
from decimal import Decimal as D
import gzip,json,importlib.util,hashlib
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0)
P=T/'independent_review/trend_confirmation_full_ledger_v1/generic_saved_finance_reader.py';sp=importlib.util.spec_from_file_location('reviewed_past_factor_only',P);F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F)
n=F.n
out={}
for win in ('strong','long'):
 summ=json.loads((O/f'full_{win}_v1/SUMMARY.json').read_text());wr={}
 for arm in ('B','UNIFORM50','A_ONLY','A_OR_B'):
  p=T/'trend_confirmation_native_v1'/f'full-{win}-v1/pair'/f'{arm}.json.gz'
  with gzip.open(p,'rt') as f:b=json.load(f)
  nav={r['at'][:10]:n(r['nav']) for r in b['decisions']};risk=Z;weights=[]
  for t in b['trades']:
   if t['side']!='buy':continue
   factor=F.factor(t['security_id'],t['at']);v=D(t['shares'])*max(Z,n(t['price'])-n(t['floor'])/factor);risk+=v;weights.append(v/nav[t['signal_at'][:10]]*100)
  wr[arm]=dict(mean_close_native_nominal_mark_floor_risk_pct=summ[arm]['whole_calendar']['mean_close_nominal_risk_pct'],actual_buy_fill_count=len(weights),sum_initial_nominal_risk_CNY_recycled_turnover_not_simultaneous=risk,mean_initial_nominal_risk_pct_decision_NAV_per_fill=sum(weights,Z)/len(weights),maximum_initial_nominal_risk_pct_decision_NAV_per_fill=max(weights),source_book_sha256=F.sha(p))
 out[win]=wr;print(win,{a:(str(v['mean_close_native_nominal_mark_floor_risk_pct']),str(v['mean_initial_nominal_risk_pct_decision_NAV_per_fill'])) for a,v in wr.items()},flush=True)
out['scope']='Initial nominal price-to-frozen-floor distance at actual execution using original causal factor asof fill. Excludes fees; gaps/slippage not a guarantee of execution or max loss. Per-fill risk and turnover sums are not simultaneous account risk. Native CLOSE mark-floor risk reads saved pool_probe/pool_confirmed only. Derived statistics not yet independently audited.'
out['factor_helper']=dict(path=str(P),sha256=F.sha(P),used_functions=['factor','n','sha'],new_features=0,new_accounts=0)
(O/'NOMINAL_RISK_SEPARATE_READOUT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
