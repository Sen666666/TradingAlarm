"""Frozen-sector trajectory audit and six predeclared diagnostic charts."""
from pathlib import Path
import os,json
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tradingalarm-sector-mplcache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import current_pool_bridge as b

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'sector-trajectories-v1';RAW=ROOT/'sector-data-v2'
font='/System/Library/Fonts/STHeiti Light.ttc';font_manager.fontManager.addfont(font)
plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name();plt.rcParams['axes.unicode_minus']=False


def main():
    manifest=json.loads((OUT/'prepared/manifest.json').read_text());refs={x['series_id']:x for x in manifest['series']}
    raw_records={x['symbol']:x for x in json.loads((RAW/'manifest.json').read_text())['series']}
    preselected=json.loads((OUT/'PROTOCOL.json').read_text())['same_six_charts']
    selected={x['symbol'] for x in preselected};summary=[];prefix_checks=[]
    charts=OUT/'charts';charts.mkdir(exist_ok=False)
    for sid,row in refs.items():
        raw_record=raw_records[sid]
        if row['blocked_reason']:raise ValueError('Unexpected blocked input '+sid)
        get=lambda key:pd.read_parquet(b.checked_ref(row['files'][key],OUT/'prepared'))
        states=get('states');events=get('events');signal=get('signal');memories=get('memories')
        latest=states.iloc[-1];segments=[]
        for number,part in states.groupby('segment_id',sort=True):
            ready=part.loc[part.ready.astype(bool)]
            segments.append({'segment_id':int(number),'first':str(part.index[0].date()),'last':str(part.index[-1].date()),
                'observations':len(part),'ready_observations':len(ready),'first_ready':str(ready.index[0].date()) if len(ready) else None,
                'first_rs':str(part.rs.dropna().index[0].date()) if part.rs.notna().any() else None})
        item={'symbol':sid,'market':raw_record['market'],'name':raw_record['name'],'observations':len(states),
            'ready_observations':int(states.ready.sum()),'unknown_warmup_observations':int((states.ready==0).sum()),
            'up_observations':int(((states.ready==1)&(states.target==1)).sum()),
            'original_entries':int(states.entry_kind.eq('original_event').sum()),
            'participation_reclaim_entries':int(states.independent_entry.sum()),'exits':int(states.exited.sum()),
            'participation_memories':len(memories),'latest_ready':bool(latest.ready),
            'latest_target_if_ready':int(latest.target) if latest.ready else None,
            'latest_rs':float(latest.rs) if pd.notna(latest.rs) else None,'segments':segments,
            'source_gaps':raw_record['gaps_over_20_days']}
        summary.append(item)
        if sid not in selected:continue
        # Prefix verification inside each declared source segment; never bridge a source gap.
        for number,part in signal.groupby('segment_id',sort=True):
            for n in sorted({min(65,len(part)),max(1,len(part)*2//3),max(1,len(part)-1)}):
                _,_,prefix,_=b.state_frame(part.iloc[:n].drop(columns='segment_id'))
                expected=states.loc[prefix.index].drop(columns='segment_id')
                pd.testing.assert_frame_equal(prefix,expected,check_exact=True,check_freq=False)
                prefix_checks.append({'symbol':sid,'segment_id':int(number),'prefix_raw_rows':n,'last':str(prefix.index[-1].date()),'passed':True})
        fig,(ax,vax,sax)=plt.subplots(3,1,figsize=(15.5,9),sharex=True,
            gridspec_kw={'height_ratios':[3,1,.34]},layout='constrained')
        fig.set_facecolor('#f7f7f2')
        for panel in (ax,vax,sax):panel.set_facecolor('white');panel.spines[['top','right']].set_visible(False)
        for number,part in signal.groupby('segment_id',sort=True):
            eligible=b.eligible_prices(part)
            st=states.loc[eligible.index]
            ax.plot(eligible.index,eligible.close,color='#154b6a',linewidth=.7,label='指数收盘' if number==0 else None)
            ax.fill_between(eligible.index,eligible.low,eligible.high,color='#3d95b8',alpha=.15,linewidth=0)
            floors=st.floor.where(st.target.eq(1)&st.ready.eq(1))
            ax.plot(st.index,floors,color='#bc6900',linewidth=.8,drawstyle='steps-post',label='存续结构保护点' if number==0 else None)
            original=st.loc[st.entry_kind.eq('original_event')]
            reclaim=st.loc[st.independent_entry.eq(1)]
            ax.scatter(original.index,eligible.loc[original.index,'close'],marker='^',s=16,color='#16835d',alpha=.65,label='原事件建态' if number==0 else None)
            ax.scatter(reclaim.index,eligible.loc[reclaim.index,'close'],marker='D',s=20,color='#a140b5',alpha=.9,label='量记忆收复建态' if number==0 else None)
            for mask,color in [(st.ready.eq(0),'#a7afb3'),(st.ready.eq(1)&st.target.eq(0),'#e8c4ba'),(st.ready.eq(1)&st.target.eq(1),'#75b5a0')]:
                sax.fill_between(st.index,0,1,where=mask.to_numpy(),step='post',color=color,linewidth=0)
            vax.vlines(part.index,0,part.volume/1e9,color='#52696e',linewidth=.7)
        for gap in raw_record['gaps_over_20_days']:
            left,right=pd.Timestamp(gap['left']),pd.Timestamp(gap['right'])
            for panel in (ax,vax,sax):panel.axvspan(left,right,color='#bfc5c8',alpha=.38)
            label=f"源缺口：{gap['calendar_days']}日，不判断趋势"
            if (right-left).days<(signal.index[-1]-signal.index[0]).days*.1:
                ax.text(.98,.96,label,ha='right',va='top',transform=ax.transAxes,fontsize=9,color='#686868')
            else:ax.text(left+(right-left)/2,.96,label,ha='center',va='top',transform=ax.get_xaxis_transform(),fontsize=9,color='#686868')
        ax.set_yscale('log');ax.set_ylabel('指数点位 / 结构（对数轴）');vax.set_ylabel('成交量 / 1e9\n指数源单位')
        sax.set_ylim(0,1);sax.set_yticks([]);sax.set_ylabel('状态',rotation=0,labelpad=22)
        for panel in (ax,vax):panel.grid(axis='y',alpha=.14)
        loc=mdates.AutoDateLocator(minticks=5,maxticks=10);sax.xaxis.set_major_locator(loc);sax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
        ax.set_title(f"{raw_record['name']} · {sid}   |   冻结算法技术轨迹",loc='left',fontsize=17,pad=19)
        text=f"原事件建态 {item['original_entries']} · 量收复建态 {item['participation_reclaim_entries']} · 最新状态："+('上涨存续' if latest.ready and latest.target else '非上涨' if latest.ready else '不可判断（预热不足）')
        ax.text(0,1.02,text,transform=ax.transAxes,fontsize=10,color='#45555c')
        ax.legend(loc='upper left',fontsize=8,framealpha=.85,ncol=2)
        fig.supxlabel('绿=已就绪上涨结构；浅红=已就绪非上涨；灰=源缺口或预热。状态不是账户仓位；不连接缺口、不改机制。',fontsize=9,color='#45555c')
        path=charts/(sid+'.png');fig.savefig(path,dpi=140);plt.close(fig)
    (OUT/'trajectory-summary.json').write_text(json.dumps({'series':summary,'accounts_run':0,'algorithm_changes':0,'technical_only':True},ensure_ascii=False,indent=2)+'\n')
    (OUT/'prefix-validation.json').write_text(json.dumps({'checks':prefix_checks,'passed':len(prefix_checks),'failed':0,'accounts_run':0},ensure_ascii=False,indent=2)+'\n')
    pd.DataFrame([{k:v for k,v in x.items() if k not in ('segments','source_gaps')} for x in summary]).to_csv(OUT/'trajectory-summary.csv',index=False)
    (charts/'manifest.json').write_text(json.dumps([{'symbol':x['symbol'],'file':str((charts/(x['symbol']+'.png')).resolve()),'selection_reason':x['reason']} for x in preselected],ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'series':len(summary),'prefix_checks':len(prefix_checks),'charts':len(preselected),'accounts_run':0}))

if __name__=='__main__':main()
