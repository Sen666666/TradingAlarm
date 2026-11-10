from pathlib import Path
import json,hashlib,datetime
O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
seal=read(O/'FREEZE.json')
for p,h in seal['source_hashes'].items():assert sha(p)==h,('frozen source drift',p)
for n,h in seal['artifact_hashes'].items():assert sha(O/n)==h,('frozen artifact drift',n)
assert read(O/'POST_ECONOMIC_AUDIT.json')['passed']
sources=dict(seal['source_hashes'])
for f in [O/'economic/SOURCE_HASHES.json',O/'report/SOURCE_HASHES.json',O/'report/MECHANISM_SOURCE_HASHES.json']:
 sources.update(read(f))
for p,h in sources.items():assert sha(p)==h,('final source drift',p)
save(O/'FINAL_SOURCE_HASHES.json',sources)
stop=dict(status='ONE_RUN_COMPLETE_BROAD_UNION_NOT_PROMOTED',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_economic_runs=1,baseline='Original repaired dynamic A_UNION_B cached',no_parameter_changes_after_freeze=True,no_second_new_arm=True,not_shared_account=True,no_annualization=True,NET80_not_actual_tax=True,known_closed_initial_winrate=[834/2616,1226/4411],unknown_execution=[103,559],financial_unknown_closed=[11,54],next_research_not_executed='New-path corporate entitlement coverage and explicit role/quality contract, not selecting a 35% subgroup',freeze_sha256=sha(O/'FREEZE.json'))
save(O/'STOP.json',stop)
out={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='FINAL_OUTPUT_HASHES.json'}
save(O/'FINAL_OUTPUT_HASHES.json',out)
assert all(sha(O/n)==h for n,h in out.items())
print('SEALED_FINAL',len(sources),len(out),sha(O/'FINAL_OUTPUT_HASHES.json'),flush=True)
