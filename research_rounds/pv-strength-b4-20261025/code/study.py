"""Finite descriptive study. Does not import an account engine."""
import sys
import pandas as pd
from common import ROOT,REPO,OLD,B2,B3,NAMES,sha,read,write,now,identity

def freeze():
    paths=[ROOT/'SCOPE.md',ROOT/'PROTOCOL.md']+[ROOT/'code'/name for name in ['model.py','common.py','study.py','checks.py']]
    paths+=list((ROOT/'reviews').rglob('*.md'))+[ROOT/'reviews/raw/RAW_RECEIPT.json']
    old={}
    for folder in [OLD,B2,B3]:
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and '.mpl' not in str(p):old[str(p.relative_to(REPO))]=sha(p)
    write(ROOT/'freeze.json',dict(recorded_at=now(),formal_candidates=1,parameters=1,accounts=0,
        real_output_revisions=0,sha256={str(p.relative_to(REPO)):sha(p) for p in paths},old_files=old,
        assets=list(NAMES),real_windows=22,synthetic_paths=24,derived_paths=1,history='seen_development'))
    print({'frozen':len(paths),'old_files':len(old)},flush=True)

def real():
    from model import strength_frame
    identity();checks=read(ROOT/'validation/checks.json');assert checks['technical_passed']
    out=ROOT/'results';out.mkdir(exist_ok=False);summary=[]
    for sid,name in NAMES.items():
        f=pd.read_parquet(OLD/'inputs'/(sid+'.parquet'))
        old=pd.read_parquet(B3/'results'/(sid+'.parquet'))
        z,j=strength_frame(f);price,_=strength_frame(f,joint=False)
        base=old[['e0_ready','e0_target','e0_entered','e0_exited','e0_floor','b1_strength','grade']].rename(columns={'grade':'b3_grade'})
        g=f.join(base).join(z)
        for c in ['S21','S63','acute_down','acute_up']:g['price_'+c]=price[c]
        g.to_parquet(out/(sid+'.parquet'));g.loc['2021-01-01':].to_csv(out/(sid+'.csv'),encoding='utf-8-sig')
        write(out/(sid+'-events.json'),j)
        row=dict(asset=sid,name=name,rows=len(g),first=str(g.index[0].date()),last=str(g.index[-1].date()),
            phase_counts=g.phase.value_counts().to_dict(),events=len(j),
            volume_changed_structure_days=int(((z.S21.ne(price.S21)|z.S63.ne(price.S63))&z.S21.notna()).sum()),sha256=sha(out/(sid+'.parquet')))
        summary.append(row);print(row,flush=True)
    write(out/'summary.json',dict(recorded_at=now(),assets=summary,account_runs=0,model='PVS-B4'));identity()

if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='real':real()
    else:raise ValueError(sys.argv[1])
