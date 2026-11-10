"""Local CZSC comparison; frozen model imports are read-only."""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'outputs/v1'
PRIOR = ROOT / 'research_rounds/pv-participation-response-20261020'
os.environ.setdefault('CZSC_HOME', str(ROOT / '.tools/czsc/cache'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.tools/czsc/mpl'))
sys.path.insert(0, str(PRIOR / 'code'))
import numpy as np
import pandas as pd
import czsc
from czsc.utils.plotting.lightweight import plot_czsc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from numeric import event_frame_numeric
from participation import participation_frame
from data_utils import load_source, eligible_prices

FONT = FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
GREEN, RED, BLUE, AMBER, INK = '#16836b', '#c34f53', '#487db6', '#d89432', '#33465a'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def date(value):
    return pd.Timestamp(value).strftime('%Y-%m-%d')

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def direction(bi):
    return 1 if str(bi.direction) in ('向上', 'Direction.Up', 'Up') else -1

def bi_record(bi):
    return dict(start=date(bi.sdt), end=date(bi.edt), direction=direction(bi),
                start_price=float(bi.fx_a.fx), end_price=float(bi.fx_b.fx),
                high=float(bi.high), low=float(bi.low))

def bi_key(bi):
    return (date(bi.sdt), date(bi.edt), direction(bi),
            float(bi.fx_a.fx), float(bi.fx_b.fx))

def snapshot(c):
    bis = c.bi_list
    last = bis[-1] if bis else None
    return dict(czsc_bi_count=len(bis), czsc_latest_bi_direction=direction(last) if last else 0,
                czsc_latest_bi_start=date(last.sdt) if last else None,
                czsc_latest_bi_end=date(last.edt) if last else None,
                czsc_latest_bi_start_price=float(last.fx_a.fx) if last else None,
                czsc_latest_bi_end_price=float(last.fx_b.fx) if last else None,
                czsc_last_bi_extend=bool(c.last_bi_extend),
                czsc_fx_count=len(c.fx_list), czsc_zs_count=len(c.zs_list))

def raw_bars(sid, bars):
    # Amount is not available in these frozen inputs. Zero is an API placeholder,
    # never measured turnover and never used by the structural comparison.
    return [czsc.RawBar(symbol=sid, dt=d.to_pydatetime(), id=i, freq=czsc.Freq.D,
                        open=float(r.open), close=float(r.close), high=float(r.high),
                        low=float(r.low), vol=float(r.volume), amount=0.)
            for i, (d, r) in enumerate(bars.iterrows())]

def causal_czsc(sid, bars):
    raw = raw_bars(sid, bars)
    c = czsc.CZSC([raw[0]], max_bi_num=1000, min_bi_len=6)
    rows, edits, first_seen, previous = [], [], {}, set()
    for n, bar in enumerate(raw):
        if n:
            c.update(bar)
        current = {bi_key(b) for b in c.bi_list}
        added, removed = current-previous, previous-current
        for key in added:
            first_seen.setdefault(key, n)
        if added or removed:
            edits.append(dict(asof=date(bar.dt), added=[list(k) for k in sorted(added)],
                              removed=[list(k) for k in sorted(removed)]))
        rows.append(dict(date=bars.index[n], **snapshot(c),
                         czsc_added_bis=len(added), czsc_removed_bis=len(removed)))
        previous = current
    final = []
    for bi in c.bi_list:
        rec = bi_record(bi)
        k = bi_key(bi)
        seen = first_seen[k]
        endpoint = bars.index.get_indexer([pd.Timestamp(bi.edt)])[0]
        rec.update(first_seen=date(bars.index[seen]),
                   first_seen_lag_observations=int(seen-endpoint))
        final.append(rec)
    zs = [dict(start=date(z.sdt),end=date(z.edt),lower=float(z.zd),upper=float(z.zg),
               valid=bool(z.is_valid)) for z in c.zs_list]
    fx = [dict(date=date(x.dt),price=float(x.fx),mark=str(x.mark)) for x in c.fx_list]
    return c, pd.DataFrame(rows).set_index('date'), edits, final, zs, fx

def spans(index, mask):
    groups = []
    start = None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        if start is not None and (not on or i == len(mask)-1):
            end = i if on else i-1
            groups.append((start,end))
            start = None
    return groups

def frame_for(record):
    source = load_source(record['symbol'], PRIOR)
    bars = eligible_prices(source, record['symbol'], record['excluded_dates'])
    source_events = event_frame_numeric(source.close, source.volume)
    state, memories = participation_frame(bars, source_events, mode='volume')
    baseline = pd.read_csv(ROOT/record['baseline_path'],index_col='date',
                           parse_dates=True,float_precision='round_trip')
    assert bars.index.equals(baseline.index)
    pd.testing.assert_frame_equal(state, baseline[state.columns],
                                  check_dtype=False, check_exact=True,
                                  check_freq=False)
    for col in ['open','high','low','close','volume']:
        np.testing.assert_array_equal(bars[col], baseline[col])
    return source, bars, state, memories, baseline

def prefix_checks(record, source, bars, state, causal):
    checks=[]
    for cutoff in ['2024-09-30','2025-06-30','2026-04-30','2026-10-16']:
        part=bars.loc[:cutoff]
        when=part.index[-1]
        events=event_frame_numeric(source.loc[:when].close,source.loc[:when].volume)
        replay,_=participation_frame(part,events,mode='volume')
        pd.testing.assert_frame_equal(replay,state.loc[:when],check_exact=True,check_freq=False)
        c=czsc.CZSC(raw_bars(record['symbol'],part),max_bi_num=1000,min_bi_len=6)
        expected=causal.loc[when]
        actual=snapshot(c)
        for key,value in actual.items():
            old=expected[key]
            assert (pd.isna(old) and value is None) or old==value,(record['symbol'],cutoff,key,old,value)
        checks.append(dict(cutoff=date(when),observations=len(part),
                           frozen_model_exact=True,czsc_stream_vs_fresh_prefix=True))
    return checks

def make_plot(sid,name,bars,state,causal,bis,zs,fx):
    d=bars[['open','high','low','close','volume']].join(state).join(causal)
    d=d.loc['2024-01-01':'2026-10-16']
    f=make_subplots(rows=4,cols=1,shared_xaxes=True,vertical_spacing=.045,
                    row_heights=[.34,.34,.13,.19],
                    subplot_titles=['我们的冻结算法：上行结构与保护点',
                                    'CZSC：分型、笔、中枢（截至末日的结构回画）',
                                    '成交量 / 此前21个观察中位数',
                                    '逐日当时可见：结构状态与最新笔方向'])
    candles=dict(x=d.index,open=d.open,high=d.high,low=d.low,close=d.close,
                 increasing_line_color=RED,decreasing_line_color=GREEN,
                 increasing_fillcolor=RED,decreasing_fillcolor=GREEN,
                 whiskerwidth=.2,showlegend=False)
    for row in [1,2]:
        f.add_trace(go.Candlestick(**candles),row=row,col=1)
    f.add_trace(go.Scatter(x=d.index,y=d.floor,mode='lines',name='我们的保护点',
                           line=dict(color=GREEN,width=2,shape='hv'),connectgaps=False),row=1,col=1)
    for col,symbol,color,label in [('entered','triangle-up',GREEN,'结构建立（非成交）'),
                                   ('exited','triangle-down',RED,'结构失效（非成交）'),
                                   ('independent_entry','star',AMBER,'量记忆独立恢复')]:
        q=d.loc[d[col].eq(1)]
        f.add_trace(go.Scatter(x=q.index,y=q.close,mode='markers',name=label,
                               marker=dict(symbol=symbol,color=color,size=9)),row=1,col=1)
    for a,b in spans(d.index,d.target.eq(1).to_numpy()):
        f.add_vrect(x0=d.index[a],x1=d.index[b],fillcolor=GREEN,opacity=.055,
                    line_width=0,row=1,col=1)
    point={}
    for b in bis:
        point[b['start']]=b['start_price'];point[b['end']]=b['end_price']
    pts=sorted(point.items())
    f.add_trace(go.Scatter(x=[x[0] for x in pts],y=[x[1] for x in pts],
                           name='CZSC 笔（端点回画）',mode='lines+markers',
                           line=dict(color=BLUE,width=1.5),marker=dict(size=3)),row=2,col=1)
    visiblefx=[x for x in fx if x['date']>=date(d.index[0])]
    f.add_trace(go.Scatter(x=[x['date'] for x in visiblefx],y=[x['price'] for x in visiblefx],
                           name='CZSC 分型',mode='markers',
                           marker=dict(symbol='diamond-open',color=AMBER,size=4)),row=2,col=1)
    for z in zs:
        if z['valid'] and z['end']>=date(d.index[0]):
            f.add_shape(type='rect',x0=z['start'],x1=z['end'],y0=z['lower'],y1=z['upper'],
                        fillcolor='rgba(216,148,50,.12)',line=dict(color='rgba(216,148,50,.5)',width=.7),
                        row=2,col=1)
    f.add_trace(go.Bar(x=d.index,y=d.volume_ratio,name='相对成交量',
                       marker_color='#aab8c8',showlegend=False),row=3,col=1)
    f.add_hline(y=2,line_dash='dash',line_color=AMBER,row=3,col=1)
    f.add_trace(go.Scatter(x=d.index,y=d.target,name='我们的上行结构 0/1',
                           line=dict(color=GREEN,width=1.5,shape='hv')),row=4,col=1)
    f.add_trace(go.Scatter(x=d.index,y=d.czsc_latest_bi_direction+3,
                           customdata=d[['czsc_latest_bi_end','czsc_last_bi_extend']].astype(str).to_numpy(),
                           hovertemplate='%{x|%Y-%m-%d}<br>最新笔端点：%{customdata[0]}<br>延伸中：%{customdata[1]}<extra>CZSC 当时可见</extra>',
                           name='CZSC 当日最新笔方向',line=dict(color=BLUE,width=1.4,shape='hv')),row=4,col=1)
    f.update_yaxes(tickvals=[0,1,2,3,4],
                    ticktext=['未建立','上行有效','笔向下','无笔','笔向上'],range=[-.3,4.3],row=4,col=1)
    f.update_yaxes(title_text='因果复权价格',row=1,col=1)
    f.update_yaxes(title_text='同一因果复权价格',row=2,col=1)
    f.update_yaxes(title_text='倍数',row=3,col=1)
    f.update_xaxes(rangeslider_visible=False,range=[d.index[0],d.index[-1]],
                    rangebreaks=[dict(bounds=['sat','mon'])],showgrid=True,gridcolor='#eef1f5')
    f.update_layout(template='plotly_white',height=1050,
                    title=dict(text=name+' '+sid+'｜同一份日线，两个不同输出',font=dict(size=20)),
                    margin=dict(l=78,r=30,t=92,b=85),
                    legend=dict(orientation='h',y=-.07,x=0,font=dict(size=11)),
                    font=dict(family='Arial, PingFang SC, sans-serif',size=12),
                    hovermode='x unified',dragmode='zoom',barmode='overlay')
    f.write_html(OUT/'charts'/f'{sid}-comparison.html',include_plotlyjs=True,
                 config=dict(displaylogo=False,responsive=True,scrollZoom=True))
    static_plot(sid,name,d,bis,zs)
    return d

def static_plot(sid,name,d,bis,zs):
    fig,ax=plt.subplots(4,1,figsize=(16,11),sharex=True,
                         gridspec_kw={'height_ratios':[3,3,1,1.35]})
    x=np.arange(len(d));pos={date(t):i for i,t in enumerate(d.index)}
    for row in [0,1]:
        for i,(_,b) in enumerate(d.iterrows()):
            color=RED if b.close>=b.open else GREEN
            ax[row].vlines(i,b.low,b.high,color=color,lw=.45,alpha=.7)
            ax[row].add_patch(Rectangle((i-.3,min(b.open,b.close)),.6,
                                abs(b.close-b.open) or b.close*1e-5,
                                facecolor=color,edgecolor=color,lw=.25,alpha=.8))
    ax[0].plot(x,d.floor,color=GREEN,lw=1.5,label='保护点')
    for a,b in spans(d.index,d.target.eq(1).to_numpy()):
        ax[0].axvspan(a,b,color=GREEN,alpha=.07,lw=0)
    for col,m,c,label in [('entered','^',GREEN,'建立'),('exited','v',RED,'失效'),
                          ('independent_entry','*',AMBER,'量恢复')]:
        mask=d[col].eq(1).to_numpy()
        ax[0].scatter(x[mask],d.close.iloc[np.flatnonzero(mask)],marker=m,c=c,s=23,label=label,zorder=4)
    points={}
    for b in bis:
        if b['start'] in pos: points[pos[b['start']]]=b['start_price']
        if b['end'] in pos: points[pos[b['end']]]=b['end_price']
    if points:
        pts=sorted(points.items());ax[1].plot(*zip(*pts),color=BLUE,lw=1.2,label='CZSC 笔')
    for z in zs:
        if not z['valid'] or z['end']<date(d.index[0]):continue
        a=pos.get(z['start'],0);b=pos.get(z['end'],len(d)-1)
        ax[1].add_patch(Rectangle((a,z['lower']),max(1,b-a),z['upper']-z['lower'],
                                  facecolor=AMBER,edgecolor=AMBER,alpha=.13,lw=.6))
    ax[2].bar(x,d.volume_ratio,color='#aab8c8',width=.85)
    ax[2].axhline(2,color=AMBER,ls='--',lw=.8)
    ax[3].step(x,d.target,where='post',color=GREEN,lw=1.2)
    ax[3].step(x,d.czsc_latest_bi_direction+3,where='post',color=BLUE,lw=1.2)
    ax[3].set_yticks([0,1,2,3,4],['未建','有效','笔向下','无笔','笔向上'],fontproperties=FONT)
    titles=['我们的冻结算法｜底色=上行结构有效，三角=建立/失效，绿线=保护点',
            'CZSC｜蓝线=笔，橙框=中枢；此面板按末日结构回画端点',
            '成交量 / 此前21观察中位数；虚线=2倍',
            '逐日当时可见输出｜绿=我们的结构，蓝=CZSC最新笔方向']
    for a,title in zip(ax,titles):
        a.set_title(title,fontproperties=FONT,fontsize=11,loc='left')
        a.grid(alpha=.12)
        a.spines[['top','right']].set_visible(False)
    ticks=np.unique(np.linspace(0,len(d)-1,9).astype(int))
    ax[3].set_xticks(ticks,d.index[ticks].strftime('%Y-%m-%d'),fontsize=9)
    fig.suptitle(name+' '+sid+'｜同一份因果复权日线的输出对照',fontproperties=FONT,fontsize=18,y=.995)
    fig.text(.055,.012,'2024-01-01 — 2026-10-16｜结构标记不是成交；笔端点日期不等于确认日期；不比较策略收益。',
             fontproperties=FONT,fontsize=10,color='#64748b')
    fig.tight_layout(rect=(0,.035,1,.97))
    fig.savefig(OUT/'charts'/f'{sid}-comparison.png',dpi=135)
    plt.close(fig)

def summarize(record,d,bis,zs,edits):
    mismatch=d.target.eq(1)&d.czsc_latest_bi_direction.eq(-1)
    runs=spans(d.index,mismatch.to_numpy())
    longest=max(runs,key=lambda p:p[1]-p[0],default=None)
    last=d.iloc[-1]
    finalbis=[b for b in bis if b['end']>=date(d.index[0])]
    revisions=[e for e in edits if e['asof']>=date(d.index[0]) and e['removed']]
    pairs=[]
    for a,b in runs:
        pairs.append(dict(start=date(d.index[a]),end=date(d.index[b]),observations=b-a+1))
    return dict(symbol=record['symbol'],name=record['name'],observations=len(d),
                entries=int(d.entered.sum()),exits=int(d.exited.sum()),
                independent_volume_entries=int(d.independent_entry.sum()),
                active_observations=int(d.target.sum()),
                up_state_down_bi_observations=int(mismatch.sum()),
                up_state_down_bi_runs=pairs,
                longest_up_state_down_bi=(pairs[runs.index(longest)] if longest else None),
                displayed_final_bis=len(finalbis),
                displayed_final_zs=sum(z['valid'] and z['end']>=date(d.index[0]) for z in zs),
                bi_list_revision_days=len(revisions),
                median_final_bi_confirmation_lag=float(np.median([b['first_seen_lag_observations'] for b in finalbis])),
                latest=dict(date=date(d.index[-1]),target=int(last.target),
                            floor=None if pd.isna(last.floor) else float(last.floor),
                            close=float(last.close),entry_kind=str(last.entry_kind) if pd.notna(last.entry_kind) else '',
                            czsc_bi_direction=int(last.czsc_latest_bi_direction),
                            czsc_bi_end=str(last.czsc_latest_bi_end),
                            czsc_last_bi_extend=bool(last.czsc_last_bi_extend),
                            rs_score=None if pd.isna(last.rs_score) else float(last.rs_score),
                            rank_score=None if pd.isna(last.rank_score) else float(last.rank_score),
                            peer_count=int(last.peer_count)))

def native_chart(c,sid,name):
    html=plot_czsc(c,theme='light',show_sma=(5,20),
                   title=name+' '+sid+'｜CZSC 1.0.2 原生图')
    html=html.replace('https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js',
                      '../../../assets/lightweight-charts-4.1.3.js')
    html=re.sub(r'<link[^>]+(?:fonts\.googleapis|fonts\.gstatic)[^>]*>','',html)
    (OUT/'charts'/f'{sid}-native.html').write_text(html)

def main():
    assert (HERE/'RAW_REVIEW.md').is_file(),'Original price-volume review must precede model charts'
    assert czsc.__version__=='1.0.2'
    freeze=json.loads((OUT/'input-freeze.json').read_text())
    assert sha(HERE/'PROTOCOL.md')==freeze['protocol_sha256']
    for p,h in freeze['algorithm_code'].items():assert sha(ROOT/p)==h
    for record in freeze['series']:
        assert sha(ROOT/record['source_path'])==record['source_sha256']
        assert sha(ROOT/record['baseline_path'])==record['baseline_sha256']
    run=dict(started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
             build_code_sha256=sha(__file__),raw_review_sha256=sha(HERE/'RAW_REVIEW.md'),
             input_freeze_sha256=sha(OUT/'input-freeze.json'),
             native_js_sha256=sha(HERE/'assets/lightweight-charts-4.1.3.js'),
             python=sys.version,dependencies={k:metadata.version(k) for k in
                 ['czsc','wbt','pandas','numpy','plotly','matplotlib','pyarrow']},
             czsc_settings=dict(min_bi_len=6,max_bi_num=1000,amount_placeholder=0),
             algorithm_changes=0,accounts_run=0,market_data_downloads=0)
    (OUT/'run-freeze.json').write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')
    summaries,checks=[],[]
    for record in freeze['series']:
        sid,name=record['symbol'],record['name']
        source,bars,state,memories,baseline=frame_for(record)
        c,causal,edits,bis,zs,fx=causal_czsc(sid,bars)
        cases=prefix_checks(record,source,bars,state,causal)
        checks.append(dict(symbol=sid,baseline_observations=len(state),saved_state_exact=True,prefixes=cases))
        state=state.join(baseline[['rs_score','rank_score','peer_count']])
        d=make_plot(sid,name,bars,state,causal,bis,zs,fx)
        native_chart(c,sid,name)
        all_days=bars[['open','high','low','close','volume']].join(state).join(causal)
        all_days.to_csv(OUT/'data'/f'{sid}-daily-output.csv',float_format='%.17g')
        memories.to_csv(OUT/'data'/f'{sid}-volume-memories.csv',index=False)
        write_json(OUT/'data'/f'{sid}-bi-edits.json',edits)
        write_json(OUT/'data'/f'{sid}-terminal-geometry.json',dict(bis=bis,zs=zs,fx=fx))
        summary=summarize(record,d,bis,zs,edits)
        summaries.append(summary)
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    write_json(OUT/'summary.json',summaries)
    for p,h in freeze['algorithm_code'].items():assert sha(ROOT/p)==h
    verification=dict(status='passed',algorithm_changes=0,accounts_run=0,market_data_downloads=0,
                      saved_baseline_exact_observations=sum(x['baseline_observations'] for x in checks),
                      selected_prefix_pairs=sum(len(x['prefixes']) for x in checks),series=checks,
                      frozen_algorithm_hashes_unchanged=True,
                      boundary='Observed development history; no execution or profitability comparison')
    write_json(OUT/'verification.json',verification)
    packages=sorted((d.metadata['Name'],d.version) for d in metadata.distributions())
    (HERE/'requirements.lock.txt').write_text('\n'.join(k+'=='+v for k,v in packages)+'\n')
    write_json(OUT/'file-manifest.json',{str(p.relative_to(HERE)):sha(p)
                for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='file-manifest.json'})
    print(json.dumps({'status':'passed','series':len(summaries),
                       'baseline_rows':verification['saved_baseline_exact_observations']}))

if __name__=='__main__':
    main()
