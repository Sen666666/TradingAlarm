"""One authorized new cohort. Joint historical loop once, immutable saved ledgers first."""
from pathlib import Path
from dataclasses import asdict,is_dataclass
from enum import Enum
from collections import Counter,defaultdict
import argparse,json,math,time,hashlib,resource
import pandas as pd
from cohort_config import O,R,CONFIG,TEMPLATE_ID
from gates import require_economic_authorization,sha,PROTOCOL_SHA256

def clean(v):
    if is_dataclass(v):return clean(asdict(v))
    if isinstance(v,Enum):return v.value
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,float) and not math.isfinite(v):return None
    if hasattr(v,'item'):
        try:return clean(v.item())
        except (TypeError,ValueError):pass
    return v

def save(p,v):
    with Path(p).open('x') as f:json.dump(clean(v),f,indent=2,ensure_ascii=False,default=str,allow_nan=False);f.write('\n')

def verify(approved,joint):
    planned=approved['input_sha256']
    for p,h in joint.s.hashes.items():assert planned.get(str(Path(p).resolve()))==h,('UNPLANNED_BASE_SOURCE',p)
    joint.market.verify_sources()
    for p,h in planned.items():assert sha(p)==h,('END_INPUT_DRIFT',p)
    for n,h in approved['code_sha256'].items():assert sha(O/n)==h,('END_CODE_DRIFT',n)
    for p,h in json.loads((O.parent/'OLD_TREE_SHA256_BEFORE.json').read_text()).items():assert sha(p)==h,('OLD_TREE_CHANGED',p)

from label_export import report

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',required=True,choices=list(CONFIG));args=p.parse_args();start=time.monotonic();a=require_economic_authorization(args.window)
    dest=O/('economic_'+args.window);assert not dest.exists(),'NO_OVERWRITE_OR_RETRY';dest.mkdir();save(dest/'STARTED.json',dict(window=args.window,authorization_sha256=a['authorization_sha256'],protocol_sha256=PROTOCOL_SHA256))
    try:
        from joint_engine import run_joint
        joint=run_joint(args.window)
        joint.s.dump(dest/'joint')
        for n,x in [('PRICE_AUDIT',joint.price_audit),('OFFER_AUDIT',joint.offer_audit),('AB_DECISION_AUDIT',joint.ab_decision_audit),('FROZEN_RESPONSIBILITIES',joint.frozen_responsibilities)]:save(dest/(n+'.json'),x)
        save(dest/'EXECUTION_BOOKS.json',{rid:dict(responsibility=b.responsibility(),parents=b.parents,orders=b.orders,lots=b.lots,events=b.events) for rid,b in joint.books.items()})
        save(dest/'ECONOMIC_LOOP_COMPLETE.json',dict(window=args.window,seconds=time.monotonic()-start,rounds=len(joint.s.rounds),actions=len(joint.s.actions),peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,source_checks_passed=False,source_verification_pending=True))
        print('ECONOMIC_LOOP_COMPLETE',args.window,len(joint.s.rounds),flush=True)
        verify(a,joint)
        save(dest/'SOURCE_VERIFIED.json',dict(all_sources_passed=True,old_tree_unchanged=True))
        summary=report(joint,dest,args.window);verify(a,joint)
        save(dest/'COMPLETE.json',dict(window=args.window,seconds=time.monotonic()-start,summary_sha256=sha(dest/'SUMMARY.json'),old_outputs_unchanged=True,no_economic_retry=True))
        print('COHORT_READY',json.dumps(summary,ensure_ascii=False),flush=True)
    except BaseException as exc:
        save(dest/'FAILED_NO_RETRY.json',dict(error=repr(exc),seconds=time.monotonic()-start,economics_completed=(dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),no_economic_retry=True));raise
if __name__=='__main__':main()
