"""Direct native ledger role/entry/exit evidence; no account or simulation."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import gzip,hashlib,json
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
RUN=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26/pair')
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
paths=read(ROOT/'POST_PURCHASE_ALL25_PATHS.json')
with gzip.open(RUN/'B.json.gz','rt')as f:book=json.load(f)
by={l['id']:l for l in book['layers']};rows=[]
for p in paths:
 lid=p['layer'];l=by[lid];m=book['metadata'][str(lid)];buy=next(t for t in book['trades']if t.get('layer')==lid and t['side']=='buy')
 journal=next(j for j in book['journal']if j['kind']=='real_buy_fill'and j['layer']==lid)
 assert m['role']==p['role']==journal['role'];assert l['kind']==('core'if m['role']=='core'else'add')
 decision=next(d for d in book['decisions']if d['at']==l['signal_at']);intent=next(i for i in decision['intents']if i['sid']==l['sid']and i['role']==m['role'])
 sells=[dict(whole_trade=t,layer_parts=[part for part in t['parts']if part['layer']==lid])for t in book['trades']if t['side']=='sell'and any(part['layer']==lid for part in t['parts'])]
 exits=[a for a in book['audit']if a['kind']=='pilot_layer_exit'and lid in a['layers']]
 assert D(buy['floor'])==D(intent['floor'])
 closed=l['qty']==0;cash=D(l['cash']);div=D(l['dividend'])
 if closed:assert cash+div==D(p['net'])
 rows.append(dict(layer=lid,sid=l['sid'],name=p['name'],role=m['role'],native_kind=l['kind'],entry_pool=journal['pool'],metadata_pool_at_end=m['pool'],
  native_open=l['opened'],signal_at=l['signal_at'],entry_protection_continuous=buy['floor'],entry_raw_floor_from_prior_report=p['original_initial_raw_floor'],
  actual_buy=buy,actual_buy_journal=journal,original_frozen_intent=intent,original_end_layer=l,original_end_metadata=m,
  protection_rule='CORE: original ACT/I_target structure exit; active I_floor updates last_core_line, stored x.floor is not a direct close stop'if m['role']=='core'else'MOBILE: check continuous close <= preceding stored line first; only if untriggered update max(old,I_floor,receipt CP1 candidate)',
  actual_exit_decisions=exits,actual_sell_fills=sells,all_closed=closed,whole_original_closed_net=cash+div if closed else None,
  original_open_cash_balance_not_profit=cash+div if not closed else None,prior_report_net_or_mark_label=p['net'],
  prior_report_role_exact=True,initial_hardline_is_entry_frozen_line_only_no_new_exit_rule=True))
assert len(rows)==25 and len({r['sid']for r in rows})==18
save('ALL25_ROLE_PROTECTION_DIRECT_EVIDENCE.json',rows)
summary=dict(layers=25,stocks=18,role_counts=dict(Counter(r['role']for r in rows)),entry_pool_counts=dict(Counter(r['entry_pool']for r in rows)),
 closed_negative=sum(r['all_closed']and r['whole_original_closed_net']<0 for r in rows),closed_positive=sum(r['all_closed']and r['whole_original_closed_net']>0 for r in rows),
 still_open=sum(not r['all_closed']for r in rows),core_line_must_not_use_stored_x_floor=True,mobile_check_then_update_order_explicit=True,
 new_accounts=0,new_restores=0,new_policy_paths=0)
save('ROLE_PROTECTION_SUMMARY.json',summary)
sources=[ROOT/'POST_PURCHASE_ALL25_PATHS.json',RUN/'B.json.gz',Path(__file__),Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')]
save('ROLE_SOURCE_SHA256.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in sources})
print(json.dumps(summary,ensure_ascii=False,indent=2))
