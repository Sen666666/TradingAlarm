"""Use correct original raw/action CLOSE mark domain in existing read-only audit."""
from pathlib import Path
import importlib.util,json,hashlib,sys
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O))
from native_mark_sidecar import NativeCloseMarks
spec=importlib.util.spec_from_file_location('eta_financial_auditor_v1_unchanged',O/'audit_completed_eta_accounts.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
oracle=NativeCloseMarks();base=A.row;differences={}
def native_row(sid,day):
    row,known=base(sid,day);price,detail=oracle.at(sid,day)
    if price!=A.n(row.raw_close):differences[sid,day]=dict(detail,old_facts_carry=str(row.raw_close),old_fact_day=known)
    row=row.copy();row.raw_close=price;return row,detail['raw_observed_day']
A.row=native_row
window='2022_2024';dst=O/'PVR_ETA_2022_2024_ACCOUNT_AUDIT.json';assert not dst.exists()
result=A.audit_eta(window)
result.update(base_auditor_script_sha256=result['auditor_script_sha256'],auditor_script_sha256=sha(__file__),
              native_mark_source_sha256=oracle.source_sha256,native_mark_sidecar_sha256=sha(O/'native_mark_sidecar.py'),
              cold_mark_scope=dict(held_stock_day_queries=len(oracle.queries),stale_action_reference_differences_from_facts_carry=list(differences.values())),
              initial_auditor_failure='Original unchanged facts-only helper first failed2023Jun20 inventory by76.14; corrected only this new read-only oracle to original native raw/action theoretical ex-reference policy. No book/source/NAV mutation or financial replay.',
              source_sha256={**result['source_sha256'],str(O/'audit_completed_eta_accounts.py'):sha(O/'audit_completed_eta_accounts.py'),str(O/'native_mark_sidecar.py'):sha(O/'native_mark_sidecar.py')})
result['limits'].append('Cold mark version2 independently uses source runtime raw bars/observed geometry mask and intervening declared signal cash/split transforms, retaining original observed known_at; synthetic reference is not a tradable quote.')
dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
summary=dict(status=result['status'],window=window,ending_NAV=result['ending_NAV'],cold_mark_queries=len(oracle.queries),stale_action_differences=len(differences),receipt=str(dst),receipt_sha256=sha(dst))
(O/'PVR_ETA_STALE_MARK_RESOLUTION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
