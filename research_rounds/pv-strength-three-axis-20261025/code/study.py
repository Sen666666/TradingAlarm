"""Freeze -> synthetic checks -> real trajectories. Never imports an account engine."""
import sys
from pathlib import Path
import pandas as pd
from common import ROOT,REPO,OLD,NAMES,read,write,sha,now,identity
from model import three_axis_frame

def freeze():
    paths=[ROOT/'PROTOCOL.md',ROOT/'SCOPE.md']+list((ROOT/'code').glob('*.py'))
    paths+=list((ROOT/'reviews/mechanism').glob('*.md'))+list((ROOT/'reviews/adversarial').glob('*.md'))
    for sid in NAMES: paths += [OLD/'inputs'/(sid+'.parquet'),OLD/'results'/(sid+'.parquet')]
    paths += [OLD/'inputs/manifest.json',OLD/'reviews/raw/windows.json']+list((OLD/'validation').glob('*.parquet'))
    snapshots={str(p.relative_to(REPO)):sha(p) for p in paths}
    old={str(p.relative_to(OLD)):sha(p) for p in OLD.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    write(ROOT/'freeze.json',dict(recorded_at=now(),status='before_formal_synthetic_and_real_B2',
        design_unit_probes_before_freeze_disclosed=True,formal_candidates=1,real_output_revisions=0,
        account_runs=0,sha256=snapshots,old_b1_files=old,assets=list(NAMES),
        synthetic_fixtures=17,real_fixed_plots=22,history='seen_development'))
    print({'frozen':len(snapshots),'old_B1_files':len(old)},flush=True)

def real():
    identity();check=read(ROOT/'validation/checks.json');assert check['technical_passed']
    out=ROOT/'results';out.mkdir(exist_ok=False);summary=[]
    for sid,name in NAMES.items():
        f=pd.read_parquet(OLD/'inputs'/(sid+'.parquet'));base=pd.read_parquet(OLD/'results'/(sid+'.parquet'))
        z,j=three_axis_frame(f);ab,_=three_axis_frame(f,joint=False)
        g=f.join(base[['strength','e0_ready','e0_target','e0_entered','e0_exited','e0_floor','price_only_strength']].rename(columns={'strength':'b1_strength','price_only_strength':'b1_price_only'}))
        g=g.join(z)
        for k in ['down_zone_log_pct','up_zone_log_pct','down_events','up_events']:
            g['all_price_'+k]=ab[k]
        g.to_parquet(out/(sid+'.parquet'));g.loc['2021-01-01':].to_csv(out/(sid+'.csv'),encoding='utf-8-sig')
        write(out/(sid+'-events.json'),j)
        summary.append(dict(asset=sid,name=name,rows=len(g),first=str(g.index[0].date()),last=str(g.index[-1].date()),
            scored=int(g.pace_21.notna().sum()),structure_broken=int(g.structure_broken.fillna(0).sum()),
            structures_created=int(g.structure_created.fillna(0).sum()),impulses=int(g.impulse_created.fillna(0).ne(0).sum()),
            sha256=sha(out/(sid+'.parquet'))))
        print(summary[-1],flush=True)
    write(out/'summary.json',dict(recorded_at=now(),assets=summary,account_runs=0,composite_score=False,
        synthetic_check_sha256=sha(ROOT/'validation/checks.json')))
    identity()

if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='real':real()
    else:raise ValueError('freeze or real')
