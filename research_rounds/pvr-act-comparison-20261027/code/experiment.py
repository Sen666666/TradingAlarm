"""One frozen stock-ranking substitution; original ACT20 execution and ledger."""
from pathlib import Path
import sys,json,hashlib,copy,csv,gzip,math
O=Path(__file__).resolve().parents[1]; ROOT=O.parents[1]
BASE=ROOT/'research_rounds/tech-finite-compound-20261026'
ACT=ROOT/'research_rounds/actual-risk-recovery-20261027'
FORM=ROOT/'research_rounds/pv-rank-q1-20261027/FORMULA.json'
sys.path[:0]=[str(ACT/'code'),str(BASE/'code')]
import common as C
import engine as E
import run_v2 as R
import analyze_v2 as A
import numpy as np
import pandas as pd
from dataclasses import replace

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
def config():return read(O/'protocol.json')

def score(f):
 """Independent finite-window calculation, no state/account/future input."""
 out=pd.DataFrame(index=f.index,columns=['r','scale','amount_ref','u','b','e','E','score'],dtype=float)
 valid=(f.close.gt(0)&np.isfinite(f.close)&f.amount.gt(0)&np.isfinite(f.amount))
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in f:valid &= ~f[k].fillna(True).astype(bool)
 # Invalid rows and declared source changes restart the full preparation.
 seg=f.segment_id if 'segment_id' in f else pd.Series(0,index=f.index)
 block=((~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())).cumsum()
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 for _,g in f.loc[valid].groupby(block[valid],sort=False):
  r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
  ar=g.amount.shift().rolling(21,min_periods=21).median()
  u=np.tanh(r/s);b=np.tanh(np.log(g.amount/ar));e=u*(1+.5*u.abs()*b)
  z=e.rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  out.loc[g.index]=pd.DataFrame({'r':r,'scale':s,'amount_ref':ar,'u':u,'b':b,'e':e,'E':z,'score':50+50*np.tanh(2*z)},index=g.index)
 return out

def prepare():
 p=read(ROOT/'TradingAlarm/runtime/market/current.json');snap=Path(p['path'])
 assert p['as_of']=='2026-10-27' and p['old_prefix_exact']
 roster=list(csv.DictReader((C.DESIGN/'proposed-pool.csv').open()));ids={r['symbol'] for r in roster};sectors={r['sector_id'] for r in roster}
 records=[r for r in read(snap/'manifest.json')['series'] if r['series_id'] in ids|sectors]
 assert len(ids)==407 and len(sectors)==11 and len(records)==418
 save(O/'input.json',{'snapshot':p,'formula_sha256':sha(FORM),'roster_sha256':sha(C.DESIGN/'proposed-pool.csv'),'series':len(records)})
 (O/'input').mkdir();save(O/'input/manifest.json',{'series':records})
 rules=read(BASE/'execution-rules-v2.json')
 # Carry frozen schedules forward by one trading day only, no rate changes.
 extensions=[]
 def extend(x,path=''):
  if isinstance(x,dict):
   for k,v in x.items():
    if k=='to' and v=='2026-10-27':x[k]='2026-10-28';extensions.append(path+'/'+k)
    else:extend(v,path+'/'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):extend(v,path+'/'+str(i))
 extend(rules)
 rules['decision_cutoffs']=sorted(set(rules['decision_cutoffs'])|{'2026-10-27T15:10:00+08:00'})
 save(O/'execution-rules-v2.json',rules);save(O/'execution-extension.json',{'one_day_unchanged_schedule_carry':extensions})
 cfg={'name':'PVR-Q1 versus ACT20_BREAK','authorization':'用户2026-10-27要求只替换评分，回测2024至当前科技股并分析原因',
 'primary_change':'个股RS-H1替换PVR-Q1；行业原RS-H1保留。行业金额单位未核验，不扩展为行业替换。',
 'versions':['RS','PVR'],'scenarios':['base','cost2','delay1'],'start_decision':'2023-12-29','first_execution':'2024-01-02','end':'2026-10-27',
 'initial_cash':1000000,'initial_state':'ACTIVE，复现研究基线；不采用真实账户新设INACTIVE',
 'unchanged':'原407池/11行业快照、E0-NR1/G1-I事件、结构退出、3行业6股每行业2股、15%初仓90%投入、ACT20_BREAK暂停恢复、费用/T+1/日有效/执行延迟',
 'graph_gate':'先固定6个量价窗并人工查看再经济；公式不按图或结果调参。',
 'no_threshold':'不加PVR>50门槛；未知评分按原接口不具备排序资格，明确统计。',
 'validation':'原ACT历史至10/26逐日日账及全部成交核对；独立现金股数/原价审计；PVR公式物理前缀；两种排序账户截止2025末物理前缀；同价不同金额反事实。',
 'stopping':'每组3执行情景各一次；只修实现违约，保留失败。不扫描参数、不自动晋升或改交易台。'}
 save(O/'protocol.json',cfg)
 (O/'scores').mkdir();coverage=[];prefix=[]
 for n,sid in enumerate(sorted(ids)):
  rec=next(r for r in records if r['series_id']==sid);assert sha(rec['raw']['path'])==rec['raw']['sha256']
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet');q=f.loc['2024':];units=set(q.amount_unit.dropna());assert units=={'CNY'},(sid,units)
  z=score(f);z.to_parquet(O/'scores'/f'{sid}.parquet')
  for day in ['2024-12-31','2026-06-30']:
   small=score(f.loc[:day]);pd.testing.assert_frame_equal(small,z.loc[:day],check_exact=True);prefix.append({'symbol':sid,'cutoff':day,'rows':len(small)})
  coverage.append({'symbol':sid,'observations_2024':len(q),'rank_ready':int(z.loc['2024':,'score'].notna().sum()),'missing':int(z.loc['2024':,'score'].isna().sum()),'source_sha256':rec['raw']['sha256'],'signal_sha256':sha(snap/'signals'/f'{sid}.parquet'),'score_sha256':sha(O/'scores'/f'{sid}.parquet')})
  if (n+1)%100==0:print('prepared',n+1,flush=True)
 pd.DataFrame(coverage).to_csv(O/'coverage.csv',index=False)
 # Test meaningful invariants and an explicit amount counterfactual.
 idx=pd.date_range('2020-01-01',periods=150);checks={}
 for label,step in [('up',.005),('down',-.005),('flat',0)]:
  f=pd.DataFrame({'close':100*np.exp(np.arange(150)*step),'amount':1e8,'segment_id':0},index=idx);z=score(f)
  checks[label]=float(z.score.iloc[-1]);assert z.score.first_valid_index()==idx[84]
  if step:assert (z.score.iloc[-1]>50)==(step>0)
  else:assert z.score.iloc[-1]==50
 f=pd.DataFrame({'close':100*np.exp(np.arange(150)*.005),'amount':1e8,'segment_id':0},index=idx);a=score(f);f.loc[idx[-1],'amount']=4e8;b=score(f);assert b.e.iloc[-1]>a.e.iloc[-1]>0
 save(O/'score-validation.json',{'passed':True,'physical_prefixes':len(prefix),'checks':checks,'same_price_high_amount_e':[float(a.e.iloc[-1]),float(b.e.iloc[-1])],'prefix_rows':sum(x['rows'] for x in prefix)})
 graphs(snap)

def graphs(snap):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 h=dict(np.load(snap/'h1.npz'));dates=pd.DatetimeIndex(h['dates']);cols={str(s):j for j,s in enumerate(h['symbols'])}
 windows=[('2024','2024-01-01','2024-12-31',['688498.SH','300308.SZ','002439.SZ']),('2026','2026-04-01','2026-10-27',['688498.SH','300502.SZ','688041.SH'])]
 for name,start,end,ids in windows:
  fig,axes=plt.subplots(3,3,figsize=(18,12),gridspec_kw={'height_ratios':[2,1,1]},sharex='col')
  for j,sid in enumerate(ids):
   f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];z=pd.read_parquet(O/'scores'/f'{sid}.parquet').reindex(f.index);x=np.arange(len(f));a=axes[0,j]
   for i,(_,r) in enumerate(f.iterrows()):
    color='#bd302d' if r.close>=r.open else '#237b53';a.vlines(i,r.low,r.high,color=color,lw=.55);a.add_patch(Rectangle((i-.3,min(r.open,r.close)),.6,max(abs(r.close-r.open),.00001),facecolor=color,edgecolor=color,lw=.4))
   a.set_title(sid+' 因果复权原始OHLC');axes[1,j].bar(x,f.amount/1e8,color='#7a8ea3',width=.8);axes[1,j].set_ylabel('成交金额 / 亿元')
   rs=pd.Series(h['score'][:,cols[sid]],index=dates).reindex(f.index);axes[2,j].plot(x,rs,label='原RS-H1',lw=1);axes[2,j].plot(x,z.score,label='PVR-Q1',lw=1);axes[2,j].axhline(50,color='grey',ls='--',lw=.6);axes[2,j].set_ylim(0,100);axes[2,j].legend();ticks=np.linspace(0,len(f)-1,5,dtype=int);axes[2,j].set_xticks(ticks,[str(f.index[i].date())[2:] for i in ticks],rotation=25)
  fig.suptitle('排序替换前图检：价格、真实金额、两种评分（未运行资金结果）');fig.tight_layout();fig.savefig(O/f'raw-review-{name}.png',dpi=125);plt.close(fig)

def setup(version,cutoff=None):
 cfg=config();snap=Path(read(O/'input.json')['snapshot']['path'])
 R.CORE=O/'input';R.PREP=snap;R.HERE=O;E.PREP=snap;E.RISK_MODE='ACT20_BREAK'
 recovery=pd.read_csv(snap/'recovery.csv',index_col=0,parse_dates=True)
 old_recovery=pd.read_csv(ACT/'recovery.csv',index_col=0,parse_dates=True)
 # ACT20_BREAK reads breakout, not fast_on, for recovery. Preserve the old
 # diagnostic field exactly on its historical prefix and extend its definition.
 recovery['fast_on']=old_recovery.fast_on.reindex(recovery.index)
 recovery['fast_on']=recovery.fast_on.where(recovery.fast_on.notna(),recovery.breadth.gt(.6)).astype(bool)
 E.risk_policy.RECOVERY=recovery
 original=R.context
 def context(limit=None,ids=None):
  b,m=original(limit,ids)
  if version=='PVR':
   dates,col,scores=b._h1_cache
   for line in b.lines:
    scores[:,col[line.security_id]]=pd.read_parquet(O/'scores'/f'{line.security_id}.parquet').score.reindex(dates).to_numpy()
  return b,m
 R.context=context
 return original

def run(version,stage):
 cfg=config();assert version in cfg['versions'];assert stage in ['economic','short','prefix']
 if stage=='economic':assert read(O/'graph-review.json')['reviewed'];assert read(O/'technical-checks.json')['passed']
 root=O/version;root.mkdir(exist_ok=True)
 (root/'execution-rules-v2.json').symlink_to(O/'execution-rules-v2.json') if not (root/'execution-rules-v2.json').exists() else None
 original=setup(version)
 end='2024-03-29' if stage=='short' else '2025-12-31' if stage=='prefix' else cfg['end'];out=root/('technical/short-v2' if stage=='short' else 'technical/prefix' if stage=='prefix' else 'accounts-v2')
 R.run(out,modes=['I'],stresses=cfg['scenarios'],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic')
 R.context=original
 if stage!='prefix':
  A.CORE=O/'input';A.PREP=Path(read(O/'input.json')['snapshot']['path']);A.HERE=root
  A.main('short' if stage=='short' else 'full')

def freeze():
 assert read(O/'graph-review.json')['reviewed'];assert read(O/'technical-checks.json')['passed']
 fs=[FORM,O/'protocol.json',O/'input.json',O/'execution-rules-v2.json',O/'input/manifest.json',O/'coverage.csv',O/'score-validation.json',O/'graph-review.json',*sorted((O/'code').glob('*.py')),*sorted((ACT/'code').glob('*.py')),*sorted((BASE/'code').glob('*.py'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(p):sha(p) for p in fs}})

if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='freeze':freeze()
 else:run(sys.argv[2],sys.argv[1])
