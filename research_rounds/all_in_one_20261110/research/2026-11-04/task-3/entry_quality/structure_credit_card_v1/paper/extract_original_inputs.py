"""Saved nine-point inputs only. No R/D arithmetic, model imports or account run."""
from pathlib import Path
import gzip, hashlib, json

O=Path(__file__).resolve().parent
Q=O.parents[1]
sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);sources[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
cp=Q/'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json'
cs=read(cp)
bpath=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
book=read(bpath,True)
yr=read(Q/'mobile_unit_risk_revision_v1/yingxin/SIX_SINGLE_ORDER_ARITHMETIC.json')
hr=read(Q/'mobile_unit_risk_revision_v1/hainengda/THREE_ENTRY_PAPER_RESULTS.json')['rows']
oldpaper={x['layer']:x for x in yr+hr}
out=[]
for sid in ['000620.SZ','002583.SZ']:
 ci,c=next((i,c) for i,c in enumerate(cs) if c['campaign']['sid']==sid)
 for ei,e in enumerate(c['entries']):
  t=e['actual_buy'];a=e['original_signal_and_authorization'];day=t['signal_at'][:10]
  oi,o=next((i,o) for i,o in enumerate(c['observations']) if o['day']==day)
  p=oldpaper[e['layer']]
  prior_buys=[dict(book_trade_index=i,raw=x) for i,x in enumerate(book['trades']) if x.get('side')=='buy' and x.get('security_id')==sid and x['at']<t['signal_at']]
  prior_sells=[dict(book_trade_index=i,raw=x) for i,x in enumerate(book['trades']) if x.get('side')=='sell' and x.get('security_id')==sid and x['at']<t['signal_at']]
  struct_tokens=sorted({x['snapshot']['stock_structure'] for x in o['actual_live_layers'] if x['snapshot'].get('stock_structure')})
  out.append(dict(sid=sid,layer=e['layer'],signal_at=t['signal_at'],actual_OPEN_at=t['at'],original_quantity=t['shares'],
   original_signal_authorization={k:a.get(k) for k in ['watch_epoch','decision_NAV','original_I_floor','original_I_alive','signal_factor','fill_factor','signal_source_segment','fill_source_segment','receipt','attempt','budget_order']},
   saved_stock_structure_tokens_in_live_layers=struct_tokens,
   original_frozen_intent=a['frozen_intent'],original_market_CP_canonical=e['original_CP_and_scale_proof'].get('CP1_canonical_trace'),
   original_signal_stock=o['stock'],original_signal_bar=o['original_raw_and_adjusted_bar'],original_live_layers_after_original_CLOSE_checks=o['actual_live_layers'],
   original_prior_observed_protection=o['prior_observed_original_protection'],original_pending_sells=o['original_pending_sells'],
   original_actual_buy=t,original_prior_buys=prior_buys,original_prior_sells=prior_sells,
   saved_causal_s63=p['s63'],saved_single_order_paper_reference=p,
   raw_source_reference=dict(chain_path=str(cp.resolve()),entry_index=f'[{ci}].entries[{ei}]',signal_observation_index=f'[{ci}].observations[{oi}]',original_book_path=str(bpath.resolve())),
   warning='All original-prefix inputs; prior_buys/sells are raw source rows, not a newly accumulated cash path. CP, watch epoch, industry episode and stock_structure are distinct fields. No shared-budget arithmetic yet.'))
save('ORIGINAL_NINE_INPUTS.json',out)
save('PRE_ARITHMETIC_SOURCE_MANIFEST.json',dict(status='INPUT_EXTRACTION_ONLY_AWAITING_B_ANCHOR_AND_PROTOCOL_FREEZE',
 source_sha256=sources,script_sha256=sha(__file__),rows=len(out),new_accounts=0,new_models=0,new_backtests=0,new_counterfactual_paths=0,R_D_arithmetic_executed=False))
print('9 original source snapshots extracted; no new R/D arithmetic executed')
