"""Market lines and descriptive episode labels only; no financial backtest."""
from common import *
import model,ast,concurrent.futures,sys
FROZEN=read(PH/'freeze.json')['sha256']
def native(x):
 if isinstance(x,dict):return {str(k):native(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [native(v) for v in x]
 if isinstance(x,(np.integer,np.bool_)):return x.item()
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x)
 if x is pd.NA:return None
 return x
def raw():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 cases=[c for c in read(SA/'raw/cases.json')['cases'] if c['group']=='TECH']
 save(O/'cases.json',dict(selection='six prior fixed tech windows plus same six continuous 2024-end; fixed before CP1 historical calculation',focused=cases,continuous=[dict(c,start='2024-01-01',end=END) for c in cases]))
 for batch in range(2):
  fig,axs=plt.subplots(2,3,figsize=(18,7),gridspec_kw={'height_ratios':[3,1]},sharex='col')
  for j,c in enumerate(cases[batch*3:batch*3+3]):
   f=frame(c['symbol']).loc['2024':];a=axs[0,j];a.plot(f.index,f.close,c='#354855');a.set_title(c['name']);a.grid(alpha=.15);axs[1,j].bar(f.index,f.amount/1e8,color='#7d9998');axs[1,j].set_ylabel('成交额/亿元');axs[1,j].tick_params(axis='x',rotation=20)
  fig.suptitle('CP1前原始量价复查 | 2024—2026-10-27 | 无新指标/保护');fig.tight_layout();fig.savefig(O/f'raw-continuous-{batch+1}.png',dpi=120);plt.close(fig)
def freeze():
 assert read(O/'tests.json')['passed'] and read(O/'raw-review.json')['reviewed']
 files=[O/'RULES.txt',O/'cases.json',O/'raw-review.json',O/'tests.json',POOL,ROOT/'research_rounds/pv-rank-q1-20261027/FORMULA.json',ROOT/'research_rounds/pvr-act-comparison-20261027/code/experiment.py',PH/'shadow/summary.json',*sorted((O/'code').glob('*.py'))]
 inputs={}
 for sid in pd.read_csv(POOL).symbol:
  for p in [PREP/'facts'/f'{sid}.parquet',PREP/'signals'/f'{sid}.parquet',PH/'events/TECH'/f'{sid}.parquet']:
   h=sha(p);assert h==FROZEN[str(p)],p;inputs[str(p)]=h
 for c in read(O/'cases.json')['focused']:files.append(PH/f'shadow/TECH-{c["symbol"]}-trace.json')
 hashes={str(p):sha(p) for p in files};hashes.update(inputs)
 save(O/'freeze.json',dict(before_history=True,sha256=hashes,stocks=407,parameter_groups=1,account_backtests=0))
 print('frozen',len(hashes),flush=True)
def oracle(f):
 p=ROOT/'research_rounds/pvr-act-comparison-20261027/code/experiment.py'
 tree=ast.parse(p.read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='score')
 env=dict(pd=pd,np=np);exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),env);return env['score'](f)
def episodes(sid,f,z,zp):
 out=[];valid=f.e0_valid.to_numpy();segments=f.segment_id.to_numpy();starts=[i for i in range(len(f)) if valid[i] and (i==0 or not valid[i-1] or segments[i]!=segments[i-1])]
 for i in starts:
  if f.index[i]<pd.Timestamp('2024-01-01'):continue
  j=i+1
  while j<len(f) and valid[j] and segments[j]==segments[i]:j+=1
  source_break=j<len(f) and segments[j]!=segments[i]
  end=j if j<len(f) and not source_break else j-1
  part=f.iloc[i:end+1];start=part.index[0];initial=float(part.i_floor.iloc[0])
  empty=pd.DataFrame(dict(receipt=False,candidate=np.nan),index=part.index)
  paths={'E0':model.project(part,empty,start,initial),'CP1':model.project(part,z,start,initial),'PRICE':model.project(part,zp,start,initial)}
  ref=paths['E0'];base_exit=ref[-1]['date'] if ref[-1]['exit'] else None;refmap={r['date']:r for r in ref}
  for policy in ['CP1','PRICE']:
   rr=paths[policy];touch=rr[-1]['date'] if rr[-1]['exit'] else None
   early=bool(touch is not None and (base_exit is None or touch<base_exit))
   label_high=label_floor=None;future_n=0;lead=None
   if early:
    at=pd.Timestamp(touch);k=f.index.get_loc(at);future=f.iloc[k+1:k+22];future_n=len(future)
    if future_n==21:
     peak=f.iloc[i:k+1].close.max();oldfloor=refmap[touch]['P_before'];label_high=bool((future.close>peak).any());label_floor=bool((future.close<=oldfloor).any())
    if base_exit is not None:lead=f.index.get_loc(pd.Timestamp(base_exit))-k
   out.append(dict(symbol=sid,policy=policy,start=str(start.date()),end=str(part.index[-1].date()),source_censored=source_break,E0_exit=base_exit,touch=touch,early_touch=early,lead_observations=lead,future_observations=future_n,new_high_21=label_high,break_original_floor_21=label_floor,observations=len(part)))
 return out
def job(sid):
 f=frame(sid);z=model.calculate(f);p=model.calculate(f,True)
 q=oracle(f)
 for a,b in [('r','r'),('s','scale'),('B','amount_ref'),('u','u'),('v','b')]:pd.testing.assert_series_equal(z[a],q[b],check_names=False,check_exact=True)
 np.testing.assert_allclose(z.u*z.m,q.e,equal_nan=True,rtol=0,atol=0)
 for cut in ['2024-12-31','2026-06-30']:
  for price,full in [(False,z),(True,p)]:pd.testing.assert_frame_equal(model.calculate(f.loc[:cut],price),full.loc[:cut],check_exact=True)
 # Observable cause checks independent of the trigger itself.
 r=z[z.receipt];assert (r.delta_frontier>0).all();assert (r.candidate<f.close.reindex(r.index)).all();assert r.e0_valid.all()
 z.to_parquet(O/'signals'/f'{sid}.parquet');p.to_parquet(O/'price-control'/f'{sid}.parquet')
 date=f.index>=pd.Timestamp('2024-01-01');r=z.loc[date];rp=p.loc[date];sameE=f.i_floor.eq(f.i_floor.shift())
 summary=dict(symbol=sid,rows=len(f),rows_2024=int(date.sum()),ready_2024=int(r.ready.sum()),receipts=int(r.receipt.sum()),price_receipts=int(rp.receipt.sum()),candidate_above_E0=int((r.receipt & r.candidate.gt(r.e0_floor)).sum()),receipt_E0_not_raised=int((r.receipt & sameE.reindex(r.index)).sum()),different_receipt_days=int(r.receipt.ne(rp.receipt).sum()),floor_scale_observations=int((r.ready&r.s.lt(model.S_MIN)).sum()),receipt_floor_scale=int((r.receipt&r.scale.eq(model.S_MIN)).sum()),all_features_exact=True,prefix_cut_checks=2,rows_prefix=sum(len(f.loc[:c]) for c in ['2024-12-31','2026-06-30']))
 return summary,episodes(sid,f,z,p)
def run():
 for p,h in read(O/'freeze.json')['sha256'].items():assert sha(p)==h,p
 (O/'signals').mkdir(exist_ok=False);(O/'price-control').mkdir(exist_ok=False)
 summaries=[];eps=[]
 try:
  with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
   for s,e in ex.map(job,pd.read_csv(POOL).symbol):
    summaries.append(s);eps.extend(e)
    if len(summaries)%50==0:print('prepared',len(summaries),flush=True)
  pd.DataFrame(summaries).to_csv(O/'market-summary.csv',index=False);pd.DataFrame(eps).to_csv(O/'episodes.csv',index=False)
  save(O/'history-verification.json',dict(passed=True,stocks=len(summaries),rows=sum(x['rows'] for x in summaries),prefix_cuts=2*len(summaries),prefix_tables=4*len(summaries),prefix_rows=sum(x['rows_prefix'] for x in summaries),PVR_same_clock_features_exact=True,account_backtests=0))
  print('history complete',flush=True)
 except BaseException as e:
  save(O/'history-failure.json',dict(error=repr(e),completed_stocks=len(summaries)));raise
if __name__=='__main__':globals()[sys.argv[1]]()
