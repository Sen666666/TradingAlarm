"""Finite offline study; reads old baselines, never imports trading engine."""
import sys
import pandas as pd
from common import ROOT,REPO,OLD,B2,NAMES,sha,read,write,now,identity
from model import strength_frame

def freeze():
    paths=[ROOT/'SCOPE.md',ROOT/'PROTOCOL.md']+list((ROOT/'code').glob('*.py'))
    paths+=list((ROOT/'reviews').rglob('*.md'))
    paths+=[ROOT/'reviews/raw/RAW_RECEIPT.json']
    old={}
    for folder in [OLD,B2]:
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and '.mpl' not in str(p):
                old[str(p.relative_to(REPO))]=sha(p)
    write(ROOT/'freeze.json',dict(recorded_at=now(),formal_candidates=1,parameters=1,accounts=0,
        real_output_revisions=0,sha256={str(p.relative_to(REPO)):sha(p) for p in paths},old_files=old,
        assets=list(NAMES),real_windows=22,synthetic_paths=24,history='seen_development',
        prefreeze_independent_technical_probes_disclosed=True))
    print({'frozen':len(paths),'old_files':len(old)},flush=True)

def real():
    identity();checks=read(ROOT/'validation/checks.json')
    assert checks.get('technical_passed',checks.get('passed',False)),checks.keys()
    out=ROOT/'results';out.mkdir(exist_ok=False);summary=[]
    for sid,name in NAMES.items():
        f=pd.read_parquet(OLD/'inputs'/(sid+'.parquet'))
        base=pd.read_parquet(OLD/'results'/(sid+'.parquet'))
        b2=pd.read_parquet(B2/'results'/(sid+'.parquet'))
        z,j=strength_frame(f);price,_=strength_frame(f,joint=False)
        g=f.join(base[['strength','e0_ready','e0_target','e0_entered','e0_exited','e0_floor']].rename(columns={'strength':'b1_strength'}))
        g=g.join(b2[['pace_5','pace_21','signed_retention']].add_prefix('b2_')).join(z)
        g['price_grade']=price.grade;g['price_freeze_created']=price.freeze_created
        g.to_parquet(out/(sid+'.parquet'));g.loc['2021-01-01':].to_csv(out/(sid+'.csv'),encoding='utf-8-sig')
        write(out/(sid+'-events.json'),j)
        row=dict(asset=sid,name=name,rows=len(g),first=str(g.index[0].date()),last=str(g.index[-1].date()),
            scored=int(g.grade.notna().sum()),grade_counts={str(int(k)):int(v) for k,v in g.grade.value_counts().items()},
            volume_changed_days=int((z.grade.ne(price.grade)&z.grade.notna()).sum()),sha256=sha(out/(sid+'.parquet')))
        summary.append(row);print(row,flush=True)
    write(out/'summary.json',dict(recorded_at=now(),assets=summary,account_runs=0,model='PVS-B3',
        synthetic_checks_sha256=sha(ROOT/'validation/checks.json')));identity()

if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='real':real()
    else:raise ValueError('freeze or real')
