"""Source/protocol and saved original facts only; no neutral/model/account execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import hashlib,json
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');P=O.parent/'loss_correction/volume_neutral_interpretation_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
f=load(P/'MOTHER_AND_SOURCE_FREEZE.json');a=load(P/'NATIVE_ENTRY_SEMANTICS_AUDIT.json');r=load(P/'READER_FIELDS.json')
for p,h in f['source_sha256'].items():assert sha(p)==h,('freeze',p)
for k in ['facts_source_sha256','native_source_sha256']:
 for p,h in a[k].items():assert sha(p)==h,(k,p)
assert sha(P/'PROTOCOL.txt')==f['protocol_sha256']and sha(P/'READER_FIELDS.json')==f['reader_fields_sha256']and sha(P/'NATIVE_ENTRY_SEMANTICS_AUDIT.json')==f['native_audit_sha256']
paths={Path(p).stem:p for p in a['facts_source_sha256']};assert len(paths)==len(a['facts_source_sha256'])==1205
frames={};counts={};allrows=0
for win,m in f['mothers'].items():
 rows=load(m['source_path']);assert sha(m['source_path'])==m['source_sha256']and len(rows)==m['rows']
 assert [[x['layer'],x['sid'],x['budget_order']]for x in rows]==m['original_identities']
 assert len({x['budget_order']for x in rows})==m['unique_budget_orders']==len(rows)
 assert Counter(x['role']for x in rows)==Counter(m['roles'])and Counter(x['action']for x in rows)==Counter(m['actions'])
 assert sum((D(x['cost'])for x in rows),D(0))==D(m['associated_original_cost'])and abs(sum((D(x['net'])for x in rows),D(0))-D(m['associated_original_net']))<D('1e-20')
 c=Counter(all_actual_layers=len(rows));core=[];mobile0=[]
 for x in rows:
  sid=x['sid']
  if sid not in frames:frames[sid]=pd.read_parquet(paths[sid],columns=['i_target','i_buy','segment_id'])
  day=pd.Timestamp(x['decision_at'][:10]);fr=frames[sid].loc[day];assert pd.notna(fr.i_target)and pd.notna(fr.i_buy)
  assert x['budget_order'].split('|')[1].split('T')[0]==str(day.date());assert pd.Timestamp(x['decision_at']).hour==15
  role=x['role'];c[role]+=1;c[role+'_i_target_'+str(bool(fr.i_target))]+=1;c[role+'_i_buy_'+str(bool(fr.i_buy))]+=1
  z=dict(layer=x['layer'],sid=sid,role=role,budget_order=x['budget_order'],decision_at=x['decision_at'],signal_at=x['signal_at'],receipt=x['receipt'],watch_epoch=x['watch_epoch'],original_i_target=bool(fr.i_target),original_i_buy=bool(fr.i_buy),original_source_segment=str(int(fr.segment_id)))
  if role=='core':core.append(z)
  elif not bool(fr.i_buy):mobile0.append(z)
 assert dict(c)==a['windows'][win]['counts'];assert core==a['windows'][win]['all_core_rows'];assert mobile0==a['windows'][win]['mobile_without_same_day_i_buy_rows'];assert not a['windows'][win]['core_counterexamples']
 counts[win]=dict(c);allrows+=len(rows)
fixed=load(O.parent/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
assert {k:v['original_members_unchanged']for k,v in f['fixed_original_tail_members'].items()}==fixed
assert all(v['rows']==len(fixed[k])for k,v in f['fixed_original_tail_members'].items())
assert {k:len(v)for k,v in fixed.items()}=={'2022_2024':83,'strong':94}
assert allrows==3436 and len(frames)==1205
x=dict(status='PASS_FROZEN_INTERPRETATION_SOURCE_AND_ALL3436_ORIGINAL_DECISION_FACTS_ONLY',counts=counts,facts_sources_SHA_and_saved_rows_checked=1205,native_sources_SHA_checked=len(a['native_source_sha256']),protocol_source_SHA_checked=len(f['source_sha256']),
 source_semantics='Read original Facts.packet I daily-event buy_allowed -> S0 checks -> J.planning event core vs continuing mobile. Core needs same-day i_buy with persistent I/otherS0, then unheld/unconsumed epoch. Mobile freshCP1+continuing Q substitutes market_buyable and does not need i_buy. Not just function-name inference.',
 reader_scope='Two axes Istate/freshI and freshCP1 plus completebotharm streams; old financialstate/ACTcontext not neutral eligibility. Allfixed83/94 retained. Raw I floor/candidate/factor/source clocks separated; unknowns not False/0. Original money associated only; lifetime entrynet distinct phasewealth.',
 remaining_unverified=['This confirms original filled rows, not all unfilled candidates or complete newneutral Q.', 'No neutral features generated, no fullACT/stage output or account outcomes under thisprotocol.', 'Reader fields such as execution masks/RS freshness must carry actual available source/time scope; not all declared interfacefields are already populated.'],
 reviewer_new_model_or_account_runs=0,inputs={str(p):sha(p)for p in [P/'PROTOCOL.txt',P/'READER_FIELDS.json',P/'MOTHER_AND_SOURCE_FREEZE.json',P/'NATIVE_ENTRY_SEMANTICS_AUDIT.json',Path(__file__)]})
(O/'VOLUME_INTERPRETATION_PROTOCOL_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],counts=counts,sources=1205)))
