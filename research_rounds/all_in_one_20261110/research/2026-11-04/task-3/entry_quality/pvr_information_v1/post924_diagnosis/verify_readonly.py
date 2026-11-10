"""Thin arithmetic/source checks; not a second economic review."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def eq(a,b):assert abs(D(str(a))-D(str(b)))<D('.000001'),(a,b)
s=read('CORE_TABLES.json');rr=read('ALL_JOINED_LAYER_ROWS.json');post=[r for r in rr['2022_2024'] if r['opened'][:10]>'2024-10-08'];tails=[r for r in rr['strong'] if D(r['net'])/D(r['cost'])>=D('.3')]
assert len(rr['2022_2024'])==2265 and len(rr['strong'])==1171 and len(post)==303 and len(tails)==123
assert len({(w,r['layer']) for w,rows in rr.items() for r in rows})==3436
eq(sum((D(r['net']) for r in post),D(0)),'-112457.6005694286215')
for cohort,original in [('post303',post),('strong_tail123',tails),('strong_all',rr['strong'])]:
 a=s[cohort]['all'];eq(sum((D(r['net']) for r in original),D(0)),a['net']);eq(D(a['positive'])+D(a['negative']),a['net'])
 for k in ['by_role_action','by_exit','by_holding','by_G1_source','by_industry_stage']:
  assert sum(v['layers'] for v in s[cohort][k].values())==len(original)
  eq(sum((D(v['net']) for v in s[cohort][k].values()),D(0)),a['net'])
short=[r for r in post if r['held_close_observations']<=5];cpbad=[r for r in short if r['actual_exit_class']=='CP1_add_protection' and D(r['net'])<0];unchanged=[r for r in cpbad if r['ratchet']['entry_to_primary_CP_ratchet']=='UNCHANGED_ENTRY_LINE']
assert len(short)==152 and len(cpbad)==82 and len(unchanged)==61
oldratchet=json.loads((O.parents[1]/'entry_exit_scale/mechanism_review/ACTUAL_CP_REQUEST_RATCHET_SUMMARY.json').read_text())
eq(sum((D(r['net']) for r in unchanged),D(0)),oldratchet['2022_2024|post303_negative_held_to_fill_at_most5']['by_ratchet']['UNCHANGED_ENTRY_LINE']['net'])
opentail=[r for r in tails if r['closed'] is None];assert len(opentail)==32;eq(sum((D(r['net']) for r in opentail),D(0)),'789300.5597946123')
assert len(read('POST_OWN13_TAIL_CONTROLS.json'))==13
src=read('SOURCE_MANIFEST.json')['source_sha256']
for p,h in src.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
context=[Path('/Users/bytedance/Documents/Codex/2026-11-04/task/nd_mobile_authorization_candidate_v1/READOUT.txt'),O.parent/'feature_design/READOUT.txt',O.parent/'feature_design/SCHEMA.json',O.parents[1]/'direction_divergence/READOUT.txt']
(O/'PREVIOUS_SCOPE_BINDING.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in context},indent=2)+'\n')
out=dict(status='PASS_THIN_SOURCE_AND_ARITHMETIC_CHECK',original_layers=3436,post303=303,strong_tail=123,open_strong_tail_mark=32,post_own_tail=13,post_short5_negative_CP=82,unchanged_entry_line_CP_negative=61,source_files_rehashed_unchanged=len(src),new_accounts=0,new_models=0,new_export_reruns=0,limitation='self thin recomputation only; parent independent agent review is separate')
(O/'THIN_VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
