"""Freeze old targets/identities only; never opens a new economic run."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;ROOT=O.parent.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[ROOT/'industry_capital_v1/actual25_role_entry/ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json',ROOT/'core_confirmed_v1/coverage/ALL11_TARGET_CROSSCHECK.json',Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')]
old=read(paths[0]);eleven=read(paths[1]);meta=read(paths[2]);assert len(old)==25 and len({r['sid']for r in old})==18
checks={r['full_mother']['key']:r['full_mother']for r in eleven};targets=[]
for r in old:
 day=r['signal_day'];sid=r['sid'];cp=r['original_opportunity']['CP1_id'];epoch=r['original_native_current_epoch'];k='strong|'+day+'|'+sid+'|core';c=checks.get(k)
 targets.append(dict(target_id='|'.join([sid,day,json.dumps(epoch,separators=(',',':')),cp or 'NO_CP',r['actual_role']]),sid=sid,name=r['name'],signal_day=day,OPEN=r['OPEN'],source_I_epoch=epoch,canonical_receipt_id=cp,original_entry_role=r['actual_role'],baseline_layer_id_reference_only=r['layer'],old_25_context=r,original_ALL11=c is not None,original_CORE_failure_set=c['original_failure_set']if c else None,original_narrow_9_candidate=c['narrow_fallback_necessary_candidate']if c else None))
assert len({t['target_id']for t in targets})==25 and sum(t['original_ALL11']for t in targets)==11 and sum(t['original_narrow_9_candidate']is True for t in targets)==9
semis={sid:r for sid,r in meta.items()if r['industry']=='半导体'};assert len(semis)==126
(O/'FIXED_TARGETS.json').write_text(json.dumps(dict(targets25=targets,semiconductor126=semis),ensure_ascii=False,indent=2)+'\n')
sources={str(p):sha(p)for p in paths+[Path(__file__),O/'PROTOCOL.txt',O/'trace_completed_strong.py']}
(O/'PREPARATION_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
(O/'PREPARATION.json').write_text(json.dumps(dict(prepared=True,target_layers25=25,target_stocks18=18,fixed_ALL11=11,fixed_narrow9=9,fixed_sector_risk_controls2=2,metadata_semiconductors=126,new_economic_files_read=0,new_native_Account=0,new_Market=0,awaiting_root_DONE_notice=True),ensure_ascii=False,indent=2)+'\n')
print('Prepared25/18+11(9+2)+126; new economic files read0')
