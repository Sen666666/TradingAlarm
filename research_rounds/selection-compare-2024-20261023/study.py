"""One frozen, offline 2024 sector-to-stock selection comparison. No accounts."""
from __future__ import annotations
import argparse, collections, hashlib, json, math, os, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
POOL=ROOT/'research_rounds/current-pool-20261022'
for p in (POOL/'code',POOL/'audit-a',ROOT/'TradingAlarm/research'):
    sys.path.insert(0,str(p))
os.environ.setdefault('CZSC_HOME',str(ROOT/'.tools/czsc/cache'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
import current_pool_bridge as bridge
import finalize_a as fa
from stock_actions import parse_ths_rights
fa.LEGACY_RIGHTS=ROOT/'TradingAlarm/research/data/ths-refresh-20261018/rights'
START,END='2024-01-01','2024-12-31'
SAMPLES=['000001.SZ','600519.SH','600030.SH','688981.SH','300308.SZ','002594.SZ','000977.SZ','601127.SH']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is pd.NA or x is pd.NaT:return None
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    return x
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')

def inspect_stock(r):
    p=POOL/'audit-a/prepared-current-master-v1/bars'/(r['current_symbol']+'.parquet')
    x=dict(symbol=r['current_symbol'],name=r['name'],native=r['ths_symbol'],sector_id=r['industry_index_symbol'],sector_name=r['industry_name'],
           scope='current_survivor',cap_status='unknown_not_applied',raw_path=str(p),source_sha256=sha(p) if p.exists() else None)
    if not p.exists():x.update(eligible_raw=False,reason='本地原价缓存缺失，2024覆盖未知');return x
    f=pd.read_parquet(p,columns=['trade_date']);d=pd.to_datetime(f.trade_date)
    x.update(first=str(d.min().date()),last=str(d.max().date()),year_observations=int(d.between(START,END).sum()))
    x['eligible_raw']=bool(x['year_observations'] and x['sector_id'])
    x['reason']='待检查除权和量价' if x['eligible_raw'] else '本地无2024观察或行业未匹配'
    return x

def freeze():
    if (HERE/'freeze.json').exists():raise FileExistsError('freeze already exists')
    roster=POOL/'audit-snapshot/current-stock-master.industry-resolved.csv'
    master=pd.read_csv(roster,dtype=str).fillna('')
    master=master.loc[master.current_symbol.str.endswith(('.SH','.SZ','.BJ'))]
    with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(inspect_stock,master.to_dict('records')))
    # Preserve available delisted histories; don't mix historical SW classifications into current THS indices.
    retired_path=ROOT/'TradingAlarm/research/results/stock-data-audit/ths-retired-collection.json'
    retired=json.loads(retired_path.read_text())['records'];seen={r['symbol'] for r in rows}
    for sid,r in retired.items():
        if sid in seen or r.get('status')!='downloaded' or r.get('last','')<START or r.get('first','')>END:continue
        p=ROOT/'TradingAlarm/research/data/ths-raw'/(r['ths_symbol']+'.json')
        rows.append(dict(symbol=sid,name=sid,native=r['ths_symbol'],sector_id='',sector_name='',scope='available_retired',eligible_raw=False,
            raw_path=str(p),source_sha256=sha(p) if p.exists() else None,first=r['first'],last=r['last'],cap_status='unknown_not_applied',reason='2024有退市历史；缺可匹配的同源行业归属，双方法共同排除并保留记录'))
    pd.DataFrame(rows).to_csv(HERE/'universe.csv',index=False,encoding='utf-8-sig')
    batches=fa.discover_history_batches(POOL/'downloads')
    evidence=[]
    for b in batches:
        evidence.append(dict(path=str(b/'protocol.json'),sha256=sha(b/'protocol.json')))
        for cp in sorted((b/'checkpoints').glob('*.json')):
            if cp.stem.startswith(('USZA','USHA','USHT','USTM')):evidence.append(dict(path=str(cp),sha256=sha(cp)))
    for p in sorted(fa.LEGACY_RIGHTS.glob('*.json')):evidence.append(dict(path=str(p),sha256=sha(p)))
    pm=POOL/'sector-trajectories-v1/prepared/manifest.json'
    sector_manifest=json.loads(pm.read_text())
    frozen=json.loads((POOL/'sector-trajectories-v1/input-manifest.json').read_text())['upstream_sha256']
    for k,p in bridge.UPSTREAM.items():assert sha(p)==frozen[k]
    code={str(p):sha(p) for p in [Path(__file__),*bridge.UPSTREAM.values(),POOL/'code/current_pool_bridge.py',POOL/'audit-a/finalize_a.py',ROOT/'TradingAlarm/research/stock_actions.py']}
    import czsc
    native=Path(czsc._native.__file__)
    protocol=dict(frozen_at=pd.Timestamp.now(tz='Asia/Shanghai').isoformat(),period=[START,END],user_scope='2024 local verifiable A-share sample; market-cap qualification separately displayed, not a gate; no funds, slots, orders or account returns',
        sample_basis='2026-10-22 surviving stocks with 2024 local histories; available retired stocks explicitly inventoried; current THS industry classification held fixed. Survivor/classification/availability selection biases retained. Historical development, not unseen or historical-full-universe.',
        price_input='Same prefix-causal theoretical-ex-price adjusted eligible daily OHLCV for both. Full available local origin warmup; source stock cache is already share/CNY normalized; only observations <=2024-12-31 consumed. Unparsed in-window actions, empty/missing action evidence, unresolved origin actions excluded identically.',
        own='Frozen numeric.event_frame_numeric(joint=True,event_exit=False) + participation_frame(mode=volume); up=target, watch=target or pending. No algorithm changes.',
        chan=dict(version=czsc.__version__,native_sha256=sha(native),frequency='daily',min_bi_len=6,max_bi_num=100,
            watch_signal='cxt_first_buy_V221126 di=1; watch persists above that known down-stroke low',
            participation_signals=['cxt_second_bs_V230320 di=1,ma_type=SMA,timeperiod=21 (MA-assisted second buy)','cxt_third_buy_V230228 di=1 (stroke third-buy auxiliary)'],
            adapter='Both industry and stock: observed 2nd/3rd buy enables participation at confirmation close; support=then-current down-stroke low, raised only by new distinct valid buy signals. Daily low strictly below support invalidates state; same-day invalidation prevents reentry. First-buy watch similarly invalidates below its low. This is one operational CZSC strategy, not the whole Chan theory.',
            causal='Process source observations in order, record actual signal recognition date, never use final-year stroke endpoint dates as prior entry dates. Deduplicate by signal kind + then-visible final stroke identity; subsequent geometry revisions are recorded as new observations, no history overwrite.'),
        joint='Participation: industry-up AND stock-up on that day, with positive observed stock volume. Watch: industry-watch AND stock-watch. Keep first 2024 session carry-ins separately. No 3x2 capacity constraint. Unknown dates do not synthesize bars.',
        ranking='Same frozen 4x63 RS for both methods; sectors descending RS then stocks descending RS, stable code tie break. Any missing rank in a current group falls back for the whole group to stable code order. Display limits only; all names retained.',
        evaluation='Monthly counts, full daily/episode lists, overlap, recognition lead/lag, first stock/sector gate, examples selected by fixed rules. No future-return optimization, no order/fill/portfolio/fee claims.',
        source_documents=['https://czsc.readthedocs.io/en/latest/api/czsc.signals.cxt_third_buy_V230228.html','https://czsc.readthedocs.io/en/latest/_modules/czsc/signals/cxt.html'],
        universe_sha256=sha(HERE/'universe.csv'),sector_manifest=dict(path=str(pm),sha256=sha(pm)),code=code,rights_evidence=evidence,
        batches=[str(b) for b in batches],raw_candidates=sum(r['eligible_raw'] for r in rows),inventory_total=len(rows),algorithm_changes=0,market_downloads=0,account_runs=0)
    dump(HERE/'freeze.json',protocol)
    print(json.dumps({k:protocol[k] for k in ['raw_candidates','inventory_total','frozen_at']},ensure_ascii=False),flush=True)

def prepare_stock(row,prot):
    p=Path(row['raw_path']);assert sha(p)==row['source_sha256']
    raw=fa.annotate_observations(pd.read_parquet(p),row['symbol'])
    raw=raw.loc[raw.trade_date.le(END)].set_index('trade_date');raw.index.name='date'
    rights=fa.rights_sources(row['symbol'],row['native'],list(map(Path,prot['batches'])),parse_ths_rights)
    evidence={'status':rights['status'],'source_path':rights['source_path'],'source_sha256':rights['source_sha256'],'unparsed':rights['unparsed'],'issues':rights['issues']}
    if not rights['records']:raise ValueError('缺除权资料或空响应不能认证无事件')
    origin=str(raw.index[0].date()).replace('-','')
    for r in rights['unparsed']:
        if origin<=str(r['row'].get('1','99999999'))<=END.replace('-',''):raise ValueError('输入区间存在未解析公司行为')
    events=[dict(effective_date=e['effective_date'],cash_per_old_share=str(e['gross_cash_per_old_share']),split_ratio=str(1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']),source_id=rights['source_sha256']) for e in rights['events'] if e['effective_date']<=END]
    if len({e['effective_date'] for e in events})!=len(events):raise ValueError('同日公司行为待聚合')
    rec={'adjustment':{'method':'theoretical_ex_price'}}
    signal=bridge.prepare_signal(raw,rec,events,cutoff=END)
    eligible=bridge.eligible_prices(signal)
    if not np.isfinite(eligible.volume).all() or eligible.volume.lt(0).any():raise ValueError('输入存在缺失或负成交量，双方法共同保留未知')
    return eligible,raw,events,rec,evidence

def chan_frame(sid,bars):
    import czsc
    raw=[czsc.RawBar(symbol=sid,dt=dt.to_pydatetime(),id=i,freq=czsc.Freq.D,open=float(o),high=float(h),low=float(l),close=float(c),vol=float(v),amount=0.)
        for i,(dt,o,h,l,c,v) in enumerate(zip(bars.index,bars.open,bars.high,bars.low,bars.close,bars.volume))]
    c=czsc.CZSC([raw[0]],max_bi_num=100,min_bi_len=6)
    active=False;watch=False;floor=wfloor=math.nan;cause='';first_seen='';seen=set();rows=[]
    for i,b in enumerate(raw):
        if i:c.update(b)
        exited=bool(active and b.low<floor)
        if exited:active=False;floor=math.nan
        if watch and b.low<wfloor:watch=False;wfloor=math.nan
        vals=[]
        for name,params in [('cxt_first_buy_V221126',{'di':1}),('cxt_second_bs_V230320',{'di':1,'ma_type':'SMA','timeperiod':21}),('cxt_third_buy_V230228',{'di':1})]:
            ss=czsc._native.call_signal(name,c,params)
            if ss and ss[0].v1 in ('一买','二买','三买'):vals.append((ss[0].v1,ss[0].value))
        new=[];endpoint=None;newkind=''
        if vals:
            bi=c.bi_list[-1]
            endpoint=str(pd.Timestamp(bi.edt).date())
            for kind,value in vals:
                key=(kind,str(bi.sdt),str(bi.edt),float(bi.fx_a.fx),float(bi.fx_b.fx))
                if key in seen:continue
                seen.add(key)
                if b.low<float(bi.low):continue
                new.append(kind)
                if kind=='一买':watch=True;wfloor=float(bi.low)
                elif not exited:
                    active=True;floor=max(floor,float(bi.low)) if math.isfinite(floor) else float(bi.low)
                    cause=kind;first_seen=str(b.dt.date());newkind=kind
        rows.append(dict(date=bars.index[i],chan_up=int(active),chan_watch=int(watch or active),chan_floor=floor if active else math.nan,
                         chan_watch_floor=wfloor if watch else math.nan,chan_signal='+'.join(x[0] for x in vals),chan_new_signal='+'.join(new),
                         chan_cause=cause if active else '',chan_recognized=first_seen if active else '',chan_endpoint=endpoint,chan_invalidated=int(exited)))
    return pd.DataFrame(rows).set_index('date')

def process_stock(row):
    prot=json.loads((HERE/'freeze.json').read_text())
    status=dict(symbol=row['symbol'],name=row['name'],sector_id=row['sector_id'],sector_name=row['sector_name'],status='excluded')
    try:
        bars,raw,events,rec,rights=prepare_stock(row,prot)
        eligible,ev,own,mem=bridge.state_frame(bars)
        chan=chan_frame(row['symbol'],eligible)
        cols=['open','high','low','close','volume','raw_open','raw_high','raw_low','raw_close','adjustment_factor']
        result=eligible[cols].join(own.add_prefix('own_')).join(chan)
        year=result.loc[START:END].copy();assert len(year)
        year['symbol']=row['symbol'];year['sector_id']=row['sector_id']
        (HERE/'daily').mkdir(exist_ok=True)
        year.to_parquet(HERE/'daily'/(row['symbol']+'.parquet'))
        status.update(status='included',reason='双方同一因果复权日线；市值另列',rows=len(year),warmup_rows=len(eligible)-len(year),first=str(eligible.index[0].date()),
                      last=str(year.index[-1].date()),rights=rights,rs_missing_days=int(year.own_rs.isna().sum()),zero_volume_days=int(year.volume.eq(0).sum()))
        if row['symbol'] in SAMPLES:
            checks=[]
            for cutoff in ['2024-01-31','2024-06-28','2024-09-30','2024-12-31']:
                part=eligible.loc[:cutoff]
                if part.empty:continue
                cs=bridge.prepare_signal(raw,rec,events,cutoff=part.index[-1]);pe,pev,po,pm=bridge.state_frame(cs)
                pd.testing.assert_frame_equal(po,own.loc[:part.index[-1]],check_exact=True)
                pc=chan_frame(row['symbol'],part)
                pd.testing.assert_frame_equal(pc,chan.loc[:part.index[-1]],check_exact=True)
                checks.append(str(part.index[-1].date()))
            status['prefix_checks']=checks
        dump(HERE/'status'/(row['symbol']+'.json'),status)
        return status
    except (ValueError,KeyError,FileNotFoundError,TypeError,AssertionError) as exc:
        status.update(reason=str(exc),error_type=type(exc).__name__)
        dump(HERE/'status'/(row['symbol']+'.json'),status)
        return status

def raw_review():
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    prot=json.loads((HERE/'freeze.json').read_text());univ=pd.read_csv(HERE/'universe.csv',dtype=str).fillna('')
    fig,axs=plt.subplots(4,4,figsize=(18,12));notes=[]
    for i,sid in enumerate(SAMPLES):
        row=univ.loc[univ.symbol.eq(sid)].iloc[0].to_dict()
        try:
            b,raw,events,rec,evidence=prepare_stock(row,prot);b=b.loc['2023-01-01':END]
            a,v=axs[i//2,(i%2)*2:(i%2)*2+2]
            a.plot(b.index,b.close,color='#264b70',lw=.9);v.bar(b.index,b.volume,width=2,color='#9db0be')
            for x in (a,v):x.grid(alpha=.15);x.tick_params(labelsize=7)
            a.set_title(row['name']+' '+sid+' 因果价格',fontproperties=font,fontsize=10)
            v.set_title('同一输入成交量',fontproperties=font,fontsize=10)
            notes.append(dict(symbol=sid,rows=len(b),last=str(b.index[-1].date()),input_ok=True))
        except Exception as exc:notes.append(dict(symbol=sid,reason=str(exc)))
    fig.tight_layout();fig.savefig(HERE/'raw-review.png',dpi=120);plt.close(fig);dump(HERE/'raw-review.json',notes)

def run():
    prot=json.loads((HERE/'freeze.json').read_text())
    for p,h in prot['code'].items():assert sha(p)==h,(p,'changed frozen code')
    for e in prot['rights_evidence']:assert sha(e['path'])==e['sha256']
    (HERE/'status').mkdir(exist_ok=False);(HERE/'sector-daily').mkdir(exist_ok=False)
    sm=json.loads(Path(prot['sector_manifest']['path']).read_text())
    ss=pd.read_csv(POOL/'sector-trajectories-v1/trajectory-summary.csv',dtype={'symbol':str}).set_index('symbol')
    sectors=[]
    for e in sm['series']:
        if ss.loc[e['series_id'],'market']!='A':continue
        frames={}
        for key in ['states','signal']:
            ref=e['files'][key];p=Path(prot['sector_manifest']['path']).parent/ref['path'];assert sha(p)==ref['sha256'];frames[key]=pd.read_parquet(p).loc[:END]
        bars=frames['signal'];own=frames['states']
        chan=chan_frame(e['series_id'],bars)
        result=bars[['open','high','low','close','volume']].join(own.add_prefix('own_')).join(chan)
        result=result.loc[START:END];result['sector_id']=e['series_id'];result['sector_name']=ss.loc[e['series_id'],'name']
        result.to_parquet(HERE/'sector-daily'/(e['series_id']+'.parquet'))
        checks=[]
        if e['series_id'] in ['URFI881121','URFI881155']:
            for cutoff in ['2024-06-28','2024-09-30','2024-12-31']:
                part=bars.loc[:cutoff];_,_,po,_=bridge.state_frame(part)
                # saved sector state carries the explicit continuity segment column.
                pd.testing.assert_frame_equal(po,own.loc[:cutoff,po.columns],check_exact=True)
                pc=chan_frame(e['series_id'],part);pd.testing.assert_frame_equal(pc,chan.loc[:cutoff],check_exact=True)
                checks.append(cutoff)
        sectors.append(dict(symbol=e['series_id'],name=ss.loc[e['series_id'],'name'],prefix_checks=checks))
    dump(HERE/'sector-verification.json',sectors)
    rows=pd.read_csv(HERE/'universe.csv').fillna('').to_dict('records');todo=[r for r in rows if r['eligible_raw'] is True]
    finished=[];started=time.time()
    with ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('spawn')) as pool:
        fs=[pool.submit(process_stock,row) for row in todo]
        for f in as_completed(fs):
            finished.append(f.result())
            if len(finished)%200==0:print(json.dumps({'finished':len(finished),'total':len(todo),'included':sum(x['status']=='included' for x in finished),'seconds':round(time.time()-started)}),flush=True)
    pd.DataFrame([{k:v for k,v in r.items() if k!='rights'} for r in finished]).to_csv(HERE/'coverage.csv',index=False,encoding='utf-8-sig')
    assert all(sha(p)==h for p,h in prot['code'].items())
    dump(HERE/'run-complete.json',dict(included=sum(r['status']=='included' for r in finished),attempted=len(todo),code_unchanged=True,account_runs=0,downloads=0,prefix_checks={r['symbol']:r.get('prefix_checks') for r in finished if r.get('prefix_checks')}))
    print((HERE/'run-complete.json').read_text(),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','raw','run']);args=parser.parse_args()
    {'freeze':freeze,'raw':raw_review,'run':run}[args.action]()
