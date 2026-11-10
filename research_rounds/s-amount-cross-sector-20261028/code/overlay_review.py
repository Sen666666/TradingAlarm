"""Fixed-window signal overlays and causal state examples. No accounts."""
from sa_common import *
from raw_review import CASES
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def scalar(x):
 if pd.isna(x):return None
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x)
 return str(x)

def last_true_date(series):
 z=series[series]
 return None if z.empty else str(z.index[-1].date())

def trace_example(group,sid,day,f,facts,old,new,kind):
 z=new.loc[day];o=old.loc[day];hist=new.loc[:day];oh=old.loc[:day]
 prev=f.index.get_loc(day)-1
 fields=['event','candidate_direction','anchor_date','anchor_price','displacement','delta_frontier','frontier','credit','threshold','amount_baseline','weight','strict_target','strict_floor','strict_exited','next_anchor_date','next_leg_direction']
 t={name:scalar(z[name]) for name in fields}
 t.update(group=group,symbol=sid,date=str(day.date()),class_name=kind,close=float(f.loc[day,'close']),amount=float(f.loc[day,'amount']),original_i_buy=bool(facts.loc[day,'i_buy']),old_target=bool(o.strict_target),old_floor=scalar(o.strict_floor),old_event=scalar(o.event),
          new_last_up_event=last_true_date(hist.event.eq(1)),old_last_up_event=last_true_date(oh.event.eq(1)),
          new_active_since=last_true_date(hist.strict_target&~hist.strict_target.shift(fill_value=False)),
          old_active_since=last_true_date(oh.strict_target&~oh.strict_target.shift(fill_value=False)),
          old_last_exit=last_true_date(~oh.strict_target&oh.strict_target.shift(fill_value=False)),
          new_last_exit=last_true_date(hist.strict_exited),
          previous_new_floor=scalar(new.iloc[prev].strict_floor) if prev>=0 else None,
          previous_old_floor=scalar(old.iloc[prev].strict_floor) if prev>=0 else None)
 if kind=='new_only':
  t['mechanism']='今日新核上行确认、旧结构无效' if z.event==1 else '新核较早建立的S状态仍有效，旧结构当前无效；不是今天金额更强'
 elif z.strict_exited:
  t['mechanism']='新S当天触及旧保护失效，旧S仍有效；不能归因于当前金额不足'
 elif z.candidate_direction==1 and z.credit<z.threshold:
  t['mechanism']='旧S已有效，新核向上候选尚未积够新前沿信用；需结合两个锚点历史，不能假定相同极点'
 else:
  t['mechanism']='两核已处于不同摆动/持久状态，查看最近确认、退出和保护；不能归因于单日放量'
 return t

def main():
 for group in PREPS:assert read(O/f'signal-validation-{group}.json')['passed']
 assert read(O/'raw-review.json')['reviewed']
 out=O/'overlay';out.mkdir(exist_ok=False)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 windows=[];examples=[]
 for group,cases in CASES.items():
  names=pool(group).set_index('symbol')['name'];fig,axs=plt.subplots(4,3,figsize=(18,12),gridspec_kw={'height_ratios':[3,1,3,1]})
  for k,(sid,start,end) in enumerate(cases):
   facts=pd.read_parquet(PREPS[group]/'facts'/f'{sid}.parquet');f=pd.read_parquet(PREPS[group]/'signals'/f'{sid}.parquet').reindex(facts.index)
   old=pd.read_parquet(OLD_TABLES[group]/f'{sid}.parquet').reindex(f.index)
   new=pd.read_parquet(O/'signals'/group/f'{sid}.parquet').reindex(f.index)
   a=facts.i_buy.astype(bool)&old.strict_target.astype(bool);b=facts.i_buy.astype(bool)&new.strict_target
   g=f.loc[start:end];common=(a&b).reindex(g.index);old_only=(a&~b).reindex(g.index);new_only=(b&~a).reindex(g.index)
   i,j=2*(k//3),k%3;ax=axs[i,j]
   ax.plot(g.index,g.close,c='#253747',lw=1);ax.fill_between(g.index,g.low,g.high,color='#99a7b5',alpha=.25)
   for mask,col,marker,label,size in [(common,'#238078','o','共同I交集',12),(old_only,'#d8791c','x','原S独有',28),(new_only,'#2966b4','^','新S独有',25)]:
    ax.scatter(g.index[mask],g.close[mask],s=size,c=col,marker=marker,label=label,zorder=3)
   ax.set_title(f'{names.loc[sid]} {sid}',fontsize=11);ax.set_ylabel('因果复权价格');ax.legend(fontsize=7)
   axs[i+1,j].bar(g.index,g.amount/1e8,color=np.where(g.close.ge(g.close.shift()),'#c65353','#318579'),width=1.5);axs[i+1,j].set_ylabel('实际金额/亿元')
   for aa in [ax,axs[i+1,j]]:aa.tick_params(axis='x',rotation=25,labelsize=7);aa.grid(alpha=.18)
   windows.append(dict(group=group,symbol=sid,name=names.loc[sid],start=start,end=end,common=int(common.sum()),old_only=int(old_only.sum()),new_only=int(new_only.sum())))
   for kind,mask in [('old_only',old_only),('new_only',new_only)]:
    days=mask.index[mask]
    if len(days):examples.append(trace_example(group,sid,days[0],f,facts,old,new,kind))
  fig.suptitle(('科技' if group=='TECH' else '创新药')+'｜同一原始窗的原I买点交集；标记是资格，不是账户成交',fontsize=15)
  fig.tight_layout(rect=(0,0,1,.97));fig.savefig(out/f'{group.lower()}-overlay.png',dpi=125);plt.close(fig)
 save(out/'window-comparison.json',windows);save(out/'causal-examples.json',examples)
 print(json.dumps({'windows':windows,'examples':len(examples)},ensure_ascii=False))

if __name__=='__main__':main()
