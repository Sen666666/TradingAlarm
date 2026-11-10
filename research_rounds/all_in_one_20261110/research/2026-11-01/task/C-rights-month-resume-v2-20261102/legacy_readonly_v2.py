"""Genuine old-source recomputation, isolated trusted snapshot, no ledger clock API."""
import copy,pickle
def serialized_readonly(current,view,cert,verifier,*,before=None):
 # Same live graph, same process: compare exact complete serialization bytes.
 # This does not compare pickle memo layouts of independently restored graphs.
 before=pickle.dumps(current,pickle.HIGHEST_PROTOCOL) if before is None else before
 result=verifier(view,copy.deepcopy(cert))
 if pickle.dumps(current,pickle.HIGHEST_PROTOCOL)!=before:raise ValueError('old certificate verification mutated complete live state')
 return result
def verify_old_certificate(r,cert,*,U,FP):
 entry=U.arm_entry(r.rights_upgrade_record['arm']);E=U.E;M=U.M
 U.require(r.window=='2022' and r.mode==entry['mode'],'wrong legacy mode/window')
 bank={x['id']:x for x in entry['certificates']};cid=cert.get('certificate_id')
 if cid not in bank:return M.MonthRunner.verify_native(r,cert)
 before=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
 expected=bank[cid]
 U.require(E.digest(cert)==expected['certificate_sha'] and E.digest(cert['source_binding'])==expected['source_sha'],'legacy certificate/source changed')
 tid=cert['trusted_id'];U.require(tid in r.trusted and E.digest(r.trusted[tid])==expected['trusted_sha'],'legacy trusted snapshot changed')
 old=r.rights_legacy_inputs
 U.require(type(old) is M.MonthInputs and str(old.path)==entry['input_manifest'] and U.sha(old.path)==entry['input_manifest_sha256'],'legacy input identity changed')
 view=object.__new__(M.MonthRunner);view.__dict__.update(r.__dict__)
 view.trusted={tid:copy.deepcopy(r.trusted[tid])}
 view.inputs=copy.deepcopy(old)
 for name in ['month_old_inputs','horizon_old_inputs','month_old_certificates','horizon_old_certificates','legacy_cert_sources']:
  if hasattr(r,name):setattr(view,name,copy.deepcopy(getattr(r,name)))
 # The genuine verifier only solves its frozen (snapshot,demands,evidence,book).
 # It has no need or permission to observe ANY current/historical live ledger.
 view.account=None
 return serialized_readonly(r,view,cert,M.MonthRunner.verify_native,before=before)
