from pathlib import Path
import sys,json,hashlib,inspect,math,csv
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
COMBO=ROOT/'research_rounds/swf-pvr-combination-20261028';PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027';BASE=ROOT/'research_rounds/tech-finite-compound-20261026';SREF=ROOT/'research_rounds/strict-entry-capacity-20261027';FREF=ROOT/'research_rounds/intent-support-20261027'
sys.path.insert(0,str(PRIOR/'code'));import experiment as P
E=P.E;R=P.R;A=P.A;C=P.C;pd=P.pd;np=P.np
PARENT=ROOT/'research_rounds/innovative-drug-sfw3-20261028'
SNAP=Path(P.read(PRIOR/'input.json')['snapshot']['path']);PREP=PARENT/'prepared';POOL=ROOT/'research_rounds/sector-ix-i-20261026/scope.json'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def signal(rec):
 path=Path(rec['raw']['path']);assert sha(path)==rec['raw']['sha256'];raw=C.read_raw(path,rec);events,_=C.read_actions(rec,path.parent);parts=[]
 for j,part in enumerate(C.source_segments(raw,rec)):
  f=C.prepare_signal(raw.loc[part['start']:part['end']],rec,events);f['segment_id']=j;parts.append(f)
 return pd.concat(parts)
