"""Same independent auditor; precompute the next-session lookup instead of rescanning."""
from pathlib import Path
import sys,inspect,json,gzip,collections
import analyze as a

src=inspect.getsource(a.audit.audit_account).replace('D(1_000_000)','PAD').replace("if not aid.startswith('B0'):","if False:")
old="later=[x for x in calendar if x.date()>when.date()];lots[sid].append([count,later[0]])"
assert src.count(old)==1
src=src.replace(old,"lots[sid].append([count,next_session[when.date()]])")
space=dict(a.audit.audit_account.__globals__,PAD=a.PAD);exec(compile(src,'unlimited_auditor_next_session_lookup','exec'),space);fast=space['audit_account']
def audit(aid,obj,daily,prices,meta,calendar,contributions=None):
 space['next_session']={calendar[j].date():calendar[j+1] for j in range(len(calendar)-1)}
 return fast(aid,obj,daily,prices,meta,calendar,contributions)
def main(mode):
 if mode=='validate':
  p=a.HERE/'technical/short-v2';meta=a.read(a.OLD/'inputs-v2/metadata.json');calendar=[a.audit.t(t) for t in a.read(a.OLD/'inputs-v2/market-rules.json')['calendars']['A']];prices=a.IndependentPrices();checks=[]
  for aid in a.read(p/'summary.json')['accounts']:
   ds=list(a.rows(p/'daily.jsonl.gz',aid));obj=dict(audit_log=list(a.rows(p/'audit.jsonl.gz',aid)))
   original=a.audit_unlimited(aid,obj,ds,prices,meta,calendar);optimized=audit(aid,obj,ds,prices,meta,calendar)
   assert original==optimized,aid;checks.append(dict(account=aid,campaigns=len(original[0])))
  a.write(a.HERE/'technical/auditor-speed-identity.json',dict(passed=True,campaigns_and_receipts_exact=True,accounts=checks,change='precomputed identical next calendar session only'))
  print('Auditor identity passed',flush=True)
 else:
  assert a.read(a.HERE/'technical/auditor-speed-identity.json')['passed'];a.audit_unlimited=audit;a.main(mode)
if __name__=='__main__':main(sys.argv[1])
