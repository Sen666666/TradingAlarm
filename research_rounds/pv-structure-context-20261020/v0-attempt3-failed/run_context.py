"""Offline algorithm trajectories ONLY. No portfolio, order or execution imports."""
from pathlib import Path
import argparse, importlib.util, json, hashlib, datetime, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/pv-event-structure-20261020')
HK={'HK00002','HK00005','HK00101','HK00700','HK00883','HK03690','HK09618'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def draw(f,old,case,out,phases):
 q=f.loc[case['context_start']:case['end']]; o=old.reindex(q.index)
 fig,ax=plt.subplots(6,1,figsize=(13,12),sharex=True,gridspec_kw={'height_ratios':[3,1,1,1,1,1]})
 ax[0].plot(q.index,q.close,color='black',label='price')
 for col,color in [('structure_floor','tab:blue'),('structure_ceiling','tab:red')]:
  if col in q:ax[0].plot(q.index,np.exp(q[col]),color=color,label=col)
 ax[0].set_yscale('log');ax[0].legend(loc='upper left',fontsize=8)
 ax[1].bar(q.index,q.volume,color='gray',width=1);ax[1].set_ylabel('volume')
 ax[2].step(q.index,q.regime,label='structural direction',where='post')
 ax[2].step(q.index,q.developing_direction,label='developing leg',alpha=.45,where='post')
 ax[2].step(q.index,o.target,label='old PV eligibility (0/1)',alpha=.35,where='post');ax[2].legend(fontsize=7,ncol=3)
 ax[3].scatter(q.index,q.phase.map(phases),s=4);ax[3].set_yticks(list(phases.values()),list(phases.keys()),fontsize=6);ax[3].set_ylabel('joint quality')
 if 'e' in q:ax[4].plot(q.index,q.e.clip(0,4),label='effort new/old')
 if 's' in q:ax[4].plot(q.index,q.s.clip(0,4),label='speed new/old')
 ax[4].axhline(1,color='gray',ls=':');ax[4].legend(fontsize=7);ax[4].set_ylim(0,4);ax[4].set_ylabel('clipped display')
 ax[5].plot(q.index,q.rs_rank,label='RS same-pool percentile',color='tab:purple');ax[5].set_ylim(0,100)
 bb=ax[5].twinx();bb.plot(q.index,q.percent_b,color='tab:orange',alpha=.5,label='Bollinger %b');bb.set_ylim(-1,2);bb.axhline(1,color='gray',ls=':');bb.set_ylabel('%b')
 ax[5].legend(fontsize=7,loc='upper left');ax[5].set_ylabel('rank')
 for a in ax:a.axvline(pd.Timestamp(case['prefix1_cutoff']),color='gray',ls=':',lw=.8)
 ax[0].set_title(f"{case['id']} {case['symbol']} | structural context, no trades | {out.name}")
 fig.tight_layout();fig.savefig(out/f"{case['id']}-trajectory.png",dpi=110);plt.close(fig)

def main():
 p=argparse.ArgumentParser();p.add_argument('--version',choices=['v0','v1'],required=True);a=p.parse_args()
 out=BASE/a.version;assert not out.exists(),out;out.mkdir()
 model=BASE/'code'/('context_model.py' if a.version=='v0' else 'context_model_v1.py')
 protocol=BASE/f'protocol-{a.version}.json'; assert protocol.exists()
 spec=importlib.util.spec_from_file_location('candidate_context',model);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 calc=mod.context_frame
 inputs={str(x):sha(x) for x in sorted(SOURCE.glob('*-signals.csv'))}
 dump(out/'freeze.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code':{str(x.name):sha(x) for x in [model,Path(__file__)]},'protocol':sha(protocol),'inputs':inputs,'account_calls':0})
 frames={};olds={};checks=[];summary=[]
 for path in sorted(SOURCE.glob('*-signals.csv')):
  s=path.name.removesuffix('-signals.csv');old=pd.read_csv(path,index_col='date',parse_dates=True);c=old.close;v=old.volume
  f=calc(c,v)
  for n in [max(100,len(c)//2),len(c)-17]:
   if n>=len(c):continue
   short=calc(c.iloc[:n],v.iloc[:n]);pd.testing.assert_frame_equal(f.iloc[:n],short,check_exact=False,rtol=1e-9,atol=1e-9);checks.append({'symbol':s,'prefix_rows':n,'ok':True})
  f['close']=c;f['volume']=v;frames[s]=f;olds[s]=old
 # Exact-date ranks; no forward-fill across market holidays, no pool membership backfill.
 for group,syms in [('hk7',sorted(HK)),('a3',[s for s in frames if s.endswith('.SH')]),('etf17',[s for s in frames if s not in HK and not s.endswith('.SH')])]:
  scores=pd.DataFrame({s:frames[s].oneil_inspired_score.where(frames[s].valid) for s in syms});ranks=scores.rank(axis=1,pct=True,method='average')*100;cnt=scores.count(axis=1)
  for s in syms:frames[s]['rs_rank']=ranks[s].reindex(frames[s].index);frames[s]['rank_n']=cnt.reindex(frames[s].index);frames[s]['rank_pool']=group
 for s,f in frames.items():
  f.to_csv(out/f'{s}-states.csv',index_label='date')
  summary.append({'symbol':s,'observations':len(f),'direction_changes':int(f.regime.diff().fillna(0).ne(0).sum()),'up':int(f.regime.eq(1).sum()),'down':int(f.regime.eq(-1).sum()),'unresolved':int(f.regime.eq(0).sum()),'quality_counts':f.phase.value_counts().to_dict()})
 # Scale and volume-placement checks on actual data: classifications, not profit.
 s='HK09618';c=olds[s].close;v=olds[s].volume;base=calc(c,v)
 for name,ff in [('price_scale',calc(c*7,v)),('volume_scale',calc(c,v*11))]:
  for col in ['regime','developing_direction','phase','event']:pd.testing.assert_series_equal(base[col],ff[col])
  checks.append({'test':name,'ok':True})
 rearranged=calc(c,v.iloc[::-1].set_axis(v.index))
 for col in ['regime','developing_direction','event']:pd.testing.assert_series_equal(base[col],rearranged[col])
 changes=int(base.phase.ne(rearranged.phase).sum());checks.append({'test':'positive volume reordered, fixed price','phase_changes':changes,'structural_direction_changes':0});assert changes>0
 idx=pd.date_range('2000-01-01',periods=320);flat=calc(pd.Series(100.,index=idx),pd.Series(np.tile([1.,2.],160),index=idx));assert flat.event.fillna(0).eq(0).all();assert flat.regime.eq(0).all();checks.append({'test':'flat','ok':True})
 # Common-prefix branches must agree, while later directions may differ.
 pc=pd.Series(np.exp(np.arange(320)*.001+np.sin(np.arange(320)/8)*.02)*100,index=idx);pv=pd.Series(100.,index=idx)
 branch=pc.copy();branch.iloc[220:]*=np.exp(-np.arange(100)*.01)
 aa=calc(pc,pv);bb=calc(branch,pv);pd.testing.assert_frame_equal(aa.iloc[:220],bb.iloc[:220]);checks.append({'test':'common_prefix_different_futures','ok':True})
 # Frozen cases only; all checkpoint comparisons are diagnostics, not target labels.
 cases=[x for x in json.loads((BASE/'raw/case-index.json').read_text()) if x['prefix']==1]
 phases={x:i for i,x in enumerate(sorted(set().union(*(set(f.phase) for f in frames.values()))))};snapshots=[]
 for case in cases:
  f=frames[case['symbol']];draw(f,olds[case['symbol']],case,out,phases)
  for cp in [case['prefix1_cutoff'],case['end']]:
   row=f.loc[:cp].iloc[-1];snapshots.append({'case':case['id'],'requested_cutoff':cp,'actual_date':str(row.name.date()),'regime':row.regime,'developing_direction':row.developing_direction,'phase':row.phase,'rs_rank':row.rs_rank,'rank_n':row.rank_n,'percent_b':row.percent_b})
 pd.DataFrame(snapshots).to_csv(out/'checkpoint-states.csv',index=False)
 dump(out/'summary.json',summary);dump(out/'validation.json',checks)
 assert all(sha(Path(path))==h for path,h in inputs.items())
 dump(out/'manifest.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
 print(json.dumps({'version':a.version,'series':len(frames),'cases':len(cases),'checks':len(checks),'volume_phase_changes':changes,'account_calls':0}))
if __name__=='__main__':main()
