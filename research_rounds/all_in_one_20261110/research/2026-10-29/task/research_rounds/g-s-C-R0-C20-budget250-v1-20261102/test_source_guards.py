"""Import/legacy/technical identity adversaries, no financial events."""
import copy
import budget250 as B
E=B.E;P=B.HERE
r=B.Runner.restore(P/'IMPORT_NECESSARY.pkl');before=E.digest(B.economic_view(r));tests=[]
def reject(name,fn):
 try:fn()
 except (ValueError,AssertionError,KeyError) as ex:tests.append(dict(name=name,rejected=True,reason=str(ex)));return
 raise AssertionError('guard did not reject '+name)
cid=next(c for c,z in r.authority.certificates.items() if any(z['Q'].values()));c=r.authority.certificates[cid];sid=next(s for s,q in c['Q'].items() if q);q=c['Q'][sid]
try:
 c['Q'][sid]=q+1;reject('old certificate Q body changed',lambda:r.verify_native(c))
finally:c['Q'][sid]=q
old=r.legacy_certificates[cid];bad=copy.deepcopy(c);bad['Q'][sid]+=1
try:
 r.authority.certificates[cid]=bad;r.legacy_certificates[cid]=copy.deepcopy(bad)
 reject('both legacy registry and authority changed cannot keep old CID',lambda:B.R.approved_payload(r,cid,sid,full_verify=False))
finally:r.authority.certificates[cid]=c;r.legacy_certificates[cid]=old
try:
 del r.legacy_certificates[cid];reject('unregistered old source cannot masquerade as current',lambda:r.verify_native(c))
finally:r.legacy_certificates[cid]=old
reject('original grant cannot authorize new technical source',lambda:r.validate_grant(B.OLD/'CONTINUATION_AUTHORIZATION.json'))
oldcap=B.CAP
try:
 B.CAP=500000;reject('technical cap differs from explicit250000 binding',B.guard)
finally:B.CAP=oldcap
E.require(E.digest(B.economic_view(r))==before,'adversarial guard test changed saved financial/strategy view')
B.save(P/'SOURCE_GUARD_TESTS.json',dict(passed=True,tests=tests,financial_events=0,complete_state_unchanged=True));print('SOURCE_GUARDS_PASS',len(tests))
