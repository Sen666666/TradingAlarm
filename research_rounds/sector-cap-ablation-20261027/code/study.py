"""Remove sector quotas only; keep six stocks and the original candidate order."""
from pathlib import Path
import sys,json,hashlib,inspect
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PRIOR/'code'))
import experiment as P
E=P.E;R=P.R;A=P.A;C=P.C;pd=P.pd;np=P.np
from dataclasses import replace
NO_CAPS=False
original_decide=E.admission.decide
src=inspect.getsource(original_decide)
for old,new in [
 ('counts[e.sector_id] >= (6 if variant == \'S1\' else 2)', 'counts[e.sector_id] >= (6 if variant == \'S1\' else 6)'),
 ('len(counts) >= (1 if variant == \'S1\' else 3)', 'len(counts) >= (1 if variant == \'S1\' else 6)')]:
 assert src.count(old)==1,(old,src.count(old));src=src.replace(old,new)
scope=dict(E.admission.__dict__);exec(src,scope);unrestricted_decide=scope['decide']

def decide(**kwargs):return (unrestricted_decide if NO_CAPS else original_decide)(**kwargs)

class CapacityAccount(E.Account):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  if NO_CAPS:self.max_sectors=6;self.max_issuers_per_sector=6

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(d),f,ensure_ascii=False,indent=2,allow_nan=False)

def initialize():
 assert read(PRIOR/'verification.json')['passed']
 save(O/'protocol.json',{'name':'行业名额单变量消融','authorized':'用户要求原ACT和仅PVR分别取消3行业/每行业2股限制，不加换仓，保留最多6股',
 'scope':'同407科技股、11行业及原当前存续/市值/行业快照，2024首交易日—2026-10-27，初始100万元ACTIVE、有限资金复利，开发检验非样本外',
 'versions':{'RS':'原ACT，3行业2股','RS_NC':'原ACT，仅取消行业配额','PVR':'仅替换个股评分，3行业2股','PVR_NC':'仅PVR，仅取消行业配额'},
 'scenarios':['base','cost2','delay1'],'only_change':'准入和执行双层行业容量由3/2改为6/6；总股数最多6使6/6等价于无行业配额。保留同发行人去重与持仓/待单占位。',
 'order':'仍行业E0趋势准入、行业RS排序，行业内原RS或PVR排序；按原行业轮流首股再次股，不改为全球个股分数排序。',
 'unchanged':'原I/G1新事件与E0-NR1结构持有、PVR公式准备期、ACT20_BREAK阶段20%暂停/63观察突破恢复、单股初仓15%NAV/新增投入90%、现金/费用/整手/权息/T+1/日有效/执行延迟、原价开盘和滑点代理均不变；不加换仓。',
 'paths':'6条新增经济路径；6条原RS/PVR完整技术恒等控制。先原图、合成/短段独立核账后冻结，经济后独立全账、集中度、原14赢家固定窗口参与与逐日机会、物理前缀。',
 'stop':'每新路径一次经济，不按收益改参，不自动扩大范围或切换正式平台。'})
 save(O/'input.json',{'prior':str(PRIOR),'prior_freeze_sha256':sha(PRIOR/'freeze.json'),'snapshot':read(PRIOR/'input.json')['snapshot'],'formula_sha256':read(PRIOR/'input.json')['formula_sha256'],'roster_sha256':read(PRIOR/'input.json')['roster_sha256']})
 (O/'execution-rules-v2.json').symlink_to((PRIOR/'execution-rules-v2.json').resolve())
 graphs()

def graphs():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 snap=Path(read(PRIOR/'input.json')['snapshot']['path']);fig,ax=plt.subplots(3,3,figsize=(17,10),sharex='col',gridspec_kw={'height_ratios':[2,1,1]})
 for j,sid in enumerate(['688498.SH','688048.SH','300502.SZ']):
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc['2025-06-01':'2025-11-14'];facts=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);z=pd.read_parquet(PRIOR/'scores'/f'{sid}.parquet').reindex(f.index);x=np.arange(len(f))
  for i,(_,r) in enumerate(f.iterrows()):
   col='#b8352f' if r.close>=r.open else '#26794f';ax[0,j].vlines(i,r.low,r.high,color=col,lw=.5);ax[0,j].add_patch(Rectangle((i-.3,min(r.open,r.close)),.6,max(abs(r.open-r.close),1e-5),facecolor=col,lw=.4))
  buy=facts.i_buy.fillna(False).astype(bool)&facts.i_target.fillna(False).astype(bool);ax[0,j].scatter(x[buy],f.loc[buy,'low']*.97,marker='^',s=10,color='#333333',label='原I事件')
  ax[0,j].set_title(sid+' 因果复权OHLC');ax[0,j].legend();ax[1,j].bar(x,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('金额 / 亿元');ax[2,j].plot(x,z.score,label='PVR');ax[2,j].axhline(50,color='grey',ls='--',lw=.6);ax[2,j].set_ylim(0,100);ticks=np.linspace(0,len(f)-1,5,dtype=int);ax[2,j].set_xticks(ticks,[str(f.index[i].date())[2:] for i in ticks],rotation=20)
 fig.suptitle('行业容量消融前量价检查；取消配额不会创造新买点，也不自动腾出已满的六股席位');fig.tight_layout();fig.savefig(O/'raw-review.png',dpi=120);plt.close(fig)

def run(version,stage):
 global NO_CAPS
 assert version in ['RS','PVR','RS_NC','PVR_NC'];assert stage in ['short','control','economic','prefix']
 NO_CAPS=version.endswith('_NC');original=P.setup('RS' if version.startswith('RS') else 'PVR')
 E.admission.decide=decide;R.Account=CapacityAccount;R.Runner=E.Runner
 root=O/version;root.mkdir(exist_ok=True)
 if not (root/'execution-rules-v2.json').exists():(root/'execution-rules-v2.json').symlink_to((O/'execution-rules-v2.json').resolve())
 if stage=='economic':assert NO_CAPS and read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed'] and (O/'freeze.json').exists()
 end='2024-06-28' if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27'
 out=root/('technical/short-v2' if stage=='short' else 'technical/control' if stage=='control' else 'technical/prefix' if stage=='prefix' else 'accounts-v2')
 R.run(out,modes=['I'],end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic');R.context=original

def freeze():
 assert read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed']
 fs=[O/'protocol.json',O/'input.json',O/'graph-review.json',PRIOR/'freeze.json',PRIOR/'input/manifest.json',PRIOR/'coverage.csv',PRIOR/'execution-rules-v2.json',*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py')),*sorted((PRIOR/'code').glob('*.py'))]
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(f):sha(f) for f in fs}})

if __name__=='__main__':
 if sys.argv[1]=='initialize':initialize()
 elif sys.argv[1]=='freeze':freeze()
 else:run(sys.argv[2],sys.argv[1])
