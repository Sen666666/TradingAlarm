"""First stock and sector rotations, chosen by time, never by profitability."""
from common_abcd import *
import gzip,html,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False})

def main():
 out=HERE/'case-review';out.mkdir(exist_ok=False);meta=read(OLD/'inputs-v2/metadata.json');z=np.load(HERE/'prepared/dual-board.npz');dates=pd.DatetimeIndex(z['dates']);ids={str(s):j for j,s in enumerate(z['symbols'])};rank=z['rank'];long=z['long'];daily=collections_default={};cases={}
 with gzip.open(HERE/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   r=json.loads(line);rot=r.get('rotation');aid=r['account']
   if not aid.endswith('_base') or not rot or not rot['plan']:continue
   p=rot['plan'];key=(aid,p['kind'])
   if key in cases:continue
   day=r['at'][:10];i=dates.get_loc(day)
   if p['kind']=='stock':target=p['incoming'];outs=[p['outgoing']]
   else:
    eligible=[e['symbol'] for e in r['event_eligibility'] if e['q'] is True and e['sector']==p['incoming']]
    values=rank if aid.startswith('D') else long;target=min(eligible,key=lambda s:(-values[i,ids[s]],s));outs=[o['security_id'] for o in r['occupancy'] if o['sector_id']==p['outgoing'] and o['has_position']]
   cases[key]=dict(account=aid,kind=p['kind'],date=day,target=target,outgoing=outs,plan=p)
 for aid in ['C__S0_base','D__S0_base']:
  with gzip.open(HERE/'accounts/daily.jsonl.gz','rt') as f:daily[aid]={r['at'][:10]:r for line in f if (r:=json.loads(line))['account']==aid}
 curves=pd.read_csv(HERE/'analysis/curves.csv');rows=[];body=['<h1>首次主动替换的量价与真实持仓复查</h1><p>按时间选取C/D各自首次行业/个股替换，不按盈利挑例子。名称与行业采用冻结当前快照；展示同源量价与真实持仓，后续价格不参与当时决策。行业目标代表股按当日合格事件及该组排序选取，组合后来不保证买入它。</p>']
 for n,case in enumerate(cases.values()):
  i=dates.get_loc(case['date']);left=dates[max(0,i-63)];right=dates[min(len(dates)-1,i+126)];fig,axes=plt.subplots(3,1,figsize=(14,9),sharex=True,gridspec_kw={'height_ratios':[2.3,1,1.3]});colors=['#087e8b','#dd7c21','#9172c1'];evidence=[]
  for j,sid in enumerate([case['target']]+case['outgoing']):
   sf=pd.read_parquet(SRC/'signals'/f'{sid}.parquet');g=sf.loc[left:right];base=float(sf.loc[case['date'],'close']);label=('原目标：' if j==0 else '主动卖出：')+meta[sid]['name']
   axes[0].plot(g.index,g.close/base,label=label,color=colors[j%3],lw=1.5)
   if j==0:
    v=g.volume/g.volume.rolling(20,min_periods=5).median().shift(1);axes[1].bar(g.index,v,width=1.5,color=colors[0],alpha=.5);axes[1].set_ylabel('目标股量/前20日中位数')
   held=pd.Series({day:sid in r['positions'] for day,r in daily[case['account']].items()});held.index=pd.to_datetime(held.index);held=held.loc[left:right]
   axes[2].step(held.index,held.astype(int)+j*1.4,where='post',label=meta[sid]['name'],color=colors[j%3]);q=sf.loc[case['date']];evidence.append(dict(symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],close=float(q.close),volume=float(q.volume),grade=float(q.grade),IX=bool(q.IX),ix_target=bool(q.ix_target),e0_floor=float(q.e0_floor) if pd.notna(q.e0_floor) else None,raw_history_posthoc=True))
  for ax in axes:ax.axvline(pd.Timestamp(case['date']),color='#333',ls='--',lw=.8);ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
  axes[0].axhline(1,color='#999',lw=.7);axes[0].set_ylabel('以提出替换日价格=1');axes[0].legend(ncol=3);axes[0].set_title(case['account']+'｜首次'+case['kind']+'替换｜'+case['date']);axes[2].set_ylabel('实际持有=1（逐股错行）');axes[2].legend(ncol=3);fig.tight_layout();file=f'first-{case["account"]}-{case["kind"]}.png';fig.savefig(out/file,dpi=135);plt.close(fig)
  body+=['<h2>'+html.escape(case['account']+' / '+case['kind']+' / '+case['date'])+'</h2>','<img src="'+file+'">',pd.DataFrame(evidence).to_html(index=False)];rows.append(dict(**case,evidence=evidence,chart=file))
 write(out/'cases.json',rows);out.joinpath('index.html').write_text('<!doctype html><meta charset="utf-8"><title>首次换仓量价复查</title><style>body{max-width:1200px;margin:40px auto;font:15px/1.7 -apple-system,sans-serif;color:#253345;padding:0 20px}img{width:100%}table{border-collapse:collapse;font-size:13px}td,th{padding:8px;border-bottom:1px solid #ccc}</style>'+''.join(body));print(dict(raw_rotation_cases=len(rows)),flush=True)
if __name__=='__main__':main()
