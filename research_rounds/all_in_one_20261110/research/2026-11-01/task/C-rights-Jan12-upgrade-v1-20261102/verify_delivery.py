"""Saved no-event upgrade evidence only; never restores or runs an account."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def main():
 checks=[]
 def check(n,v,d=None):checks.append(dict(check=n,passed=bool(v),detail=d));assert v,(n,d)
 f=read(O/'SOURCE_FREEZE.json');ident=read(O/'IDENTITY.json');complete=read(O/'COMPLETION.json');rows=read(O/'UPGRADE_RESULTS.json');reg=read(O/'UPGRADED_CHECKPOINTS.json')
 check('all frozen old/new source files exact',all(sha(p)==h for p,h in f['sources'].items()),len(f['sources']))
 check('new identity exact',sha(O/'IDENTITY.json')==f['identity_sha256'])
 check('only selected2022 arms imported',set(ident['arms'])=={'2022-C10','2022-C_BATCH20'} and len(reg)==2)
 check('all14 original certificates recomputed including8 outside month_old',complete['original_certificates_recomputed']==14 and complete['certificates_outside_month_old']==8)
 for r in rows:
  arm=r['arm'];e=ident['arms'][arm];cp=next(x for x in reg if x['arm']==arm)
  check(arm+' original source checkpoint/provenance unchanged',sha(e['checkpoint'])==e['checkpoint_sha256'] and sha(e['provenance'])==e['provenance_sha256'])
  check(arm+' exact whole and per-field prefix',r['before']==r['after'] and r['before']['whole']==e['prefix_sha256'])
  check(arm+' certificate source/clock/projection evidence complete',len(r['certificates'])==7 and {c['known_at'][:10] for c in r['certificates']}=={'2022-01-04','2022-01-05','2022-01-06','2022-01-07','2022-01-10','2022-01-11','2022-01-12'})
  check(arm+' upgraded checkpoint and provenance exact',sha(cp['checkpoint'])==cp['sha256'] and sha(Path(cp['checkpoint']).with_suffix('.provenance.json'))==cp['provenance_sha256'])
  cross=read(O/(arm+'-RESTORE.json'));check(arm+' crossprocess prefix and duplicate upgrade exact',cross['restored'] and cross['prefix']==r['before'] and cross['duplicate_upgrade']=='already_upgraded' and cross['historical_events']==0)
  # Future sample is deliberately NOT approved; no permission is invented.
  grant=dict(parent_approved=False,scope='2022_JAN13_NO_SUBSCRIPTION_ACTION_ONLY',identity_sha256=sha(O/'IDENTITY.json'),arm=arm,input_checkpoint_sha256=cp['sha256'],day='2022-01-13',phase='ACTION',no_OPEN_CLOSE=True,note='DRAFT ONLY; requires explicit future parent approval and trusted grant hash')
  (O/(arm+'-JAN13-GRANT.DRAFT.json')).write_text(json.dumps(grant,ensure_ascii=False,indent=2)+'\n')
 neg=read(O/'NEGATIVE_TESTS.json');check('22 rejection gates passed',neg['passed'] and neg['checks']==22 and all(r['passed'] for r in neg['tests']))
 check('no events/reset/original writes/2025 payload access',all(complete[k]==0 for k in ['historical_events','original_writes','accounts_reset','accounts_2025_opened']))
 check('Jan12 cursor preserved in both outputs',all(r['cursor']=='2022-01-12 15:10:00+08:00' for r in rows))
 v=dict(passed=True,checks=len(checks),tests=checks,scope='saved evidence/hash checks only; no financial event or account restore')
 (O/'VERIFICATION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print('VERIFIED_NO_EVENT_DELIVERY',len(checks))
if __name__=='__main__':main()
