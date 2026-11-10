from study import *
from audit import rows
receipts=[]
for cohort in STARTS:
 full=O/cohort/'accounts-v2';prefix=O/cohort/'technical/prefix'
 for name in ['daily','decisions']:
  x=rows(prefix/f'{name}.jsonl.gz');y=[r for r in rows(full/f'{name}.jsonl.gz') if r['account'].split('__')[0].endswith('0') and r['at'][:10]<='2026-06-30'];assert x==y,(cohort,name);receipts.append(dict(cohort=cohort,stream=name,rows=len(x)))
 for p in prefix.glob('*__S0_*.json'):
  if p.name=='summary.json':continue
  assert read(p)['fills']==[f for f in read(full/p.name)['fills'] if f['at'][:10]<='2026-06-30'],(cohort,p.name)
v=read(O/'full-verification.json');v.update(prefix_paths=21,prefix_daily_rows=sum(r['rows'] for r in receipts if r['stream']=='daily'),prefix_decision_rows=sum(r['rows'] for r in receipts if r['stream']=='decisions'),prefix_fills_exact=True,signal_prefixes=read(O/'signal-validation.json')['physical_prefixes'],synthetic_tests=read(O/'tests.json')['tests']);save(O/'verification.json',v)
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
s=pd.read_csv(O/'summary.csv');p=pd.read_csv(O/'paired.csv');poor=pd.read_csv(O/'baseline-poor-paths.csv');colors={'ACT':'#555555','BUF':'#b58a35','COR':'#247ba0'}
fig,ax=plt.subplots(1,3,figsize=(16,5),sharey=True)
for a,cohort in zip(ax,STARTS):
 for v in colors:
  q=s[(s.cohort==cohort)&(s.strategy==v)&(s.scenario=='base')].sort_values('seed');a.plot(q.seed,q.net_return*100,marker='o',label=v,color=colors[v])
 a.set_title('起点 '+STARTS[cohort]);a.set_xticks([0,1,2],['原排序','近分升序','近分降序']);a.set_ylabel('总收益/%');a.legend()
fig.suptitle('同一起点不同初始组合：三策略基础情景（不同起点持有期不同）');fig.tight_layout();fig.savefig(O/'path-comparison.png',dpi=125);plt.close(fig)
cv=pd.read_csv(O/'curves.csv');fig,ax=plt.subplots(1,3,figsize=(17,5))
for a,r in zip(ax,poor.itertuples()):
 for v in colors:
  q=cv[(cv.cohort==r.cohort)&(cv.seed==r.seed)&(cv.strategy==v)&(cv.scenario=='base')];a.plot(pd.to_datetime(q.date),q.nav/1e4,label=v,color=colors[v])
 a.set_title(f'ACT较差路径：{r.cohort} / 顺序{r.seed}');a.tick_params(axis='x',rotation=25);a.set_ylabel('净值/万元');a.legend()
fig.suptitle('按事前规则选择各起点ACT最差初始路径，再配对比较纠正方案');fig.tight_layout();fig.savefig(O/'poor-paths.png',dpi=125);plt.close(fig)
print(json.dumps(read(O/'verification.json'),ensure_ascii=False,indent=2))
