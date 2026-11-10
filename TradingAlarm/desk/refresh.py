"""Bounded THS update pipeline. Publish only after all stages pass; old snapshots stay readable."""
import copy
import csv
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import numpy as np
import pandas as pd
from .data import ROOT, BASE, NR, TZ, MarketData, clean


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False));tmp.replace(path)


def compute_recovery(signals, roster):
    """Exact frozen market price clock and independently valid amount breadth."""
    returns={};mom={}
    for sid in roster.symbol:
        f=signals[sid];valid=(f.price_eligible&f.observed_bar&~f.synthetic_event_bar)
        raw=f.loc[valid];rs=[];ms=[]
        for _,g in raw.groupby('segment_id',sort=False):
            r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();u=r*np.minimum(1,np.sqrt(q));m=u.ewm(span=21,adjust=False).mean();ready=np.arange(len(g))>=64
            rs.append(r.where(ready));m.iloc[:64]=np.nan;ms.append(m)
        returns[sid]=pd.concat(rs).sort_index();mom[sid]=pd.concat(ms).sort_index()
    sector_r=[];sector_b=[]
    for sector,group in roster.groupby('sector_id'):
        sector_r.append(pd.concat({s:returns[s] for s in group.symbol},axis=1).mean(axis=1))
        f=pd.concat({s:mom[s] for s in group.symbol},axis=1);n=f.notna().sum(axis=1);sector_b.append((f.gt(0).sum(axis=1)/n).where(n>=5))
    r=pd.concat(sector_r,axis=1).mean(axis=1);price=np.exp(r.fillna(0)).cumprod()
    b=pd.concat(sector_b,axis=1);breadth=b.mean(axis=1).where(b.notna().sum(axis=1)>=8)
    z=pd.DataFrame(dict(market=price,prior_high63=price.shift().rolling(63,min_periods=63).max(),breadth=breadth));z['breakout']=(z.market>z.prior_high63)&(z.market.diff()>0)&(z.breadth>.6)
    return z


def prepare_facts(signal):
    paths=[ROOT/'research_rounds/b5-g1-20261025/code',ROOT/'research_rounds/pv-strength-b5-20261025/code',ROOT/'research_rounds/pv-participation-response-20261020/code']
    for p in reversed(paths):sys.path.insert(0,str(p))
    from data_utils import eligible_prices
    from api import run_b5
    from grade import classify
    from policy import e0_policy
    from policies_g1 import project
    f=eligible_prices(signal)[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
    z=run_b5(f,enhancements=False);e=z['evidence'].copy();g,_=classify(e)
    e['decline_candidate']=False;b,_=e0_policy(e);ip=project(e,b,g,'G1_I')
    keep=f[['close','segment_id']].copy()
    for prefix,frame in [('e0',b),('i',ip)]:
        for c in ['target','floor']:keep[prefix+'_'+c]=frame[c]
    keep['i_buy']=ip.buy_event
    for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
    # B5 base readiness is unchanged by disabling decline recovery.
    keep['e0_ready']=z['state']['ready']
    keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index)
    return keep


def facts_job(args):
    sid,signal_path,old_path,old_day,target=args
    facts=prepare_facts(pd.read_parquet(signal_path));original=pd.read_parquet(old_path).loc[:old_day]
    for c in ['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','factor','raw_close']:
        np.testing.assert_allclose(facts.loc[original.index,c].astype(float),original[c].astype(float),rtol=0,atol=0,equal_nan=True,err_msg=sid+'/'+c)
    facts.to_parquet(target)
    return dict(symbol=sid,rows=len(facts),prefix_rows=len(original),sha256=hashlib.sha256(Path(target).read_bytes()).hexdigest())


def refresh_market(runtime,progress=lambda _:None):
    runtime=Path(runtime);old=MarketData(runtime);end=old.expected_close()
    if not old.integrity['passed']:raise ValueError('冻结策略或数据完整性核验失败，请先检查本地文件')
    if end is None:raise ValueError('交易日历已到期，请先更新核验后的交易日历')
    if old.as_of==end:return dict(as_of=end,already_current=True,network_requests=0)
    market=runtime/'market';market.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (market/'.update.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('另一个本机实例正在更新资料，请等待完成') from None
        pointer=market/'active-update.json';active=json.loads(pointer.read_text()) if pointer.exists() else None
        if active and active['end']==end and active['base_identity']==old.identity and active['state']!='complete':
            run=Path(active['path'])
        else:
            run=market/('update-'+datetime.now(TZ).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);run.mkdir()
        active=dict(path=str(run),end=end,base_identity=old.identity,state='running');atomic(pointer,active)
        try:
            result=_update(old,end,run,progress);active['state']='complete';atomic(pointer,active);return result
        except Exception as exc:
            active.update(state='failed',error_type=type(exc).__name__);atomic(pointer,active)
            atomic(run/('failure-'+datetime.now(TZ).strftime('%Y%m%d-%H%M%S-%f')+'.json'),dict(error_type=type(exc).__name__,message=str(exc)[:500]))
            raise


def _update(old,end,run,progress):
    # Only increment the existing 1709 stock/90 index reference. Do not change membership.
    collector=module('desk_history_batch',ROOT/'research_rounds/current-pool-20261022/code/history_batch.py');collector.PAGE=12
    sys.path.insert(0,str(ROOT/'TradingAlarm/research'))
    import ths_readonly as ths
    import ths_readonly_fu as fu
    manifest_paths=[BASE/'data/core-v3/manifest.json',BASE/'data/references/manifest.json']
    records={r['series_id']:r for p in manifest_paths for r in json.loads(p.read_text())['series']}
    if old.published:records={r['series_id']:r for r in json.loads((Path(old.published['path'])/'manifest.json').read_text())['series']}
    master={r['symbol']:r['ths_symbol'] for r in csv.DictReader((ROOT/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv').open())}
    earliest=(datetime.fromisoformat(old.as_of)-timedelta(days=5)).date().isoformat()
    items=[dict(series_id=s,symbol=master.get(s,s),node='9602' if r['kind']=='stock' else '9603',end=end,earliest=earliest,mode='tail',rights=r['kind']=='stock',max_pages=5) for s,r in sorted(records.items())]
    results={}
    for i in range(0,len(items),100):
        group=items[i:i+100];plan=dict(schema_version=1,items=[{k:v for k,v in x.items() if k!='series_id'} for x in group],max_requests=len(group)*7+4,request_interval_seconds=.3,read_timeout_seconds=15,session_preference='auto')
        folder=run/f'batch-{i//100:02d}';folder.mkdir(exist_ok=True);collector.immutable(folder/'protocol.json',collector.encoded(plan));col=collector.Collector(plan,folder,ths,fu,collector.digest(collector.encoded(plan)))
        progress(f'同花顺增量：{i}/{len(items)} 个参照序列')
        col.run()
        if col.stopped_nodes:raise ValueError('同花顺会话或连接不可用，更新已停止；请在官方客户端重新登录后重试')
        for item in group:
            cp=collector.read_json(folder/'checkpoints'/f"{item['symbol']}.json")
            if not cp or cp['history_status']!='complete' or (item['rights'] and cp['rights_status']!='received'):raise ValueError('资料未完整取得：'+item['series_id'])
            results[item['series_id']]=(folder,item,cp)
    progress('校验重叠日线、权益和因果信号')
    for directory in ['rs-h1-execution-20261025','a-share-selection-e0-20261024','sector-stock-20261021']:
        sys.path.append(str(ROOT/'research_rounds'/directory/'code'))
    bridge=module('desk_signal_bridge',ROOT/'research_rounds/rs-h1-execution-20261025/code/current_pool_bridge.py')
    normal=module('desk_action_normalizer',ROOT/'research_rounds/a-share-selection-e0-20261024/code/normalize_actions.py')
    prepared=run/'prepared';prepared.mkdir(exist_ok=True);[(prepared/d).mkdir(exist_ok=True) for d in ['bars','signals','facts','actions']]
    all_signals={};new_records=[];coverage=[]
    with np.load(old.h1_path) as z:
        h1_tail_context=(pd.DatetimeIndex(z['dates']),{str(s):j for j,s in enumerate(z['symbols'])},z['close'],z['segment'])
    for i,(sid,record) in enumerate(records.items()):
        rec=copy.deepcopy(record);folder,item,cp=results[sid];path=folder/'history'/f"{item['symbol']}.json";response=json.loads(path.read_text());wire=pd.DataFrame(response['bars']).rename(columns={'date':'trade_date'})
        raw=bridge.read_raw(Path(rec['raw']['path']),rec)
        if wire.empty:raise ValueError('增量响应为空：'+sid)
        wire['trade_date']=pd.to_datetime(wire.trade_date);wire=wire.set_index('trade_date');ix=raw.index.intersection(wire.index)
        if not len(ix):raise ValueError('增量与旧源没有重叠：'+sid)
        for c in ['open','high','low','close','volume','amount']:
            a=raw.loc[ix,c].to_numpy(float);b=wire.loc[ix,c].to_numpy(float);valid=np.isfinite(a)&np.isfinite(b)
            if not np.allclose(a[valid],b[valid],rtol=0 if c in ['open','high','low','close'] else 1e-6,atol=1e-6 if c in ['open','high','low','close'] else 1):raise ValueError('重叠行情冲突：'+sid+'/'+c)
        tail=wire.loc[wire.index>raw.index[-1]].copy()
        if len(tail):
            for c in raw.columns:
                if c not in tail:tail[c]=raw[c].iloc[-1]
            for c in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:tail[c]=True
            tail['source_invalid']=False;tail['synthetic_event_bar']=False;tail['source_path']=str(path);tail['observed_at']=datetime.now(TZ).isoformat()
        merged=pd.concat([raw,tail]);merged.index.name='trade_date'
        o=merged[['open','high','low','close']]
        valid=np.isfinite(o).all(axis=1)&o.gt(0).all(axis=1)&merged.high.ge(merged[['open','close']].max(axis=1))&merged.low.le(merged[['open','close']].min(axis=1))
        if not valid.loc[tail.index].all():raise ValueError('新日线价格非法：'+sid)
        target=prepared/'bars'/f'{sid}.parquet';merged.reset_index().to_parquet(target,index=False);rec['raw']=dict(path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        if rec.get('segments'):rec['segments'][-1]['end']=str(merged.index.max().date())
        if rec.get('unavailable_from') and len(tail):raise ValueError('新资料跨越未解来源边界：'+sid)
        events,_=bridge.read_actions(record,Path(record['raw']['path']).parent)
        if item['rights']:
            rightspath=folder/cp['rights']['attempt']/'decoded.json';rights=json.loads(rightspath.read_text());extra,_,unresolved=normal.normalize(rights,str(rightspath),old.as_of,end)
            if unresolved:raise ValueError('新权益条件未识别：'+sid)
            byday={x['effective_date']:x for x in events}
            for x in extra:
                if x['effective_date']>old.as_of:byday[x['effective_date']]=x
            events=sorted(byday.values(),key=lambda e:e['effective_date'])
            oldactions=json.loads(Path(record['adjustment']['actions']['path']).read_text());oldactions['events']=events;ap=prepared/'actions'/f'{sid}.json';atomic(ap,oldactions);rec['adjustment']['actions']=dict(path=str(ap),sha256=hashlib.sha256(ap.read_bytes()).hexdigest())
        if sid in old.facts:
            parts=[]
            for j,part in enumerate(bridge.source_segments(merged,rec)):
                f=bridge.prepare_signal(merged.loc[part['start']:part['end']],rec,events);f['segment_id']=j;parts.append(f)
            signal=pd.concat(parts)
            signal.to_parquet(prepared/'signals'/f'{sid}.parquet')
        else:
            signal=reference_tail(sid,merged,events,old.as_of,h1_tail_context)
        all_signals[sid]=signal
        new_records.append(rec);coverage.append(dict(symbol=sid,added=len(tail),last=str(merged.index.max().date())))
        if i%100==0:progress(f'计算与旧前缀核验：{i}/{len(records)}')
    from concurrent.futures import ProcessPoolExecutor
    tasks=[(sid,str(prepared/'signals'/f'{sid}.parquet'),str(old.facts_dir/f'{sid}.parquet'),old.as_of,str(prepared/'facts'/f'{sid}.parquet')) for sid in old.facts]
    fact_receipts=[]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for r in pool.map(facts_job,tasks):
            fact_receipts.append(r)
            if len(fact_receipts)%40==0:progress(f'原I/G1信号与前缀核验：{len(fact_receipts)}/{len(tasks)}')
    progress('更新原1709股/90行业RS-H1横向排名')
    extend_h1(old,all_signals,prepared/'h1.npz')
    recovery=compute_recovery(all_signals,pd.DataFrame(old.roster));prior=old.recovery
    for c in ['market','prior_high63','breadth']:
        np.testing.assert_allclose(recovery.loc[prior.index,c],prior[c],rtol=1e-12,atol=1e-12,equal_nan=True)
    np.testing.assert_array_equal(recovery.loc[prior.index,'breakout'],prior.breakout)
    if str(recovery.index[-1].date())!=end:raise ValueError('市场恢复序列未覆盖目标收盘')
    recovery.to_csv(prepared/'recovery.csv');atomic(prepared/'manifest.json',dict(series=new_records,coverage=coverage,facts=fact_receipts))
    receipt=dict(path=str(prepared),as_of=end,published_at=datetime.now(TZ).isoformat(),series=len(records),algorithm='ACT20_BREAK',old_prefix_exact=True)
    atomic(prepared/'receipt.json',receipt)
    atomic(old.runtime/'market/current.json',receipt)
    return receipt


def reference_tail(sid,raw,events,old_day,context):
    """Increment only the RS reference close; no E0 needed outside the tech pool."""
    dates,columns,closes,segments=context;j=columns[sid]
    prior_indices=np.flatnonzero(np.isfinite(closes[:,j])&(dates<=pd.Timestamp(old_day)))
    if not len(prior_indices):raise ValueError('RS参照没有可用因果原点：'+sid)
    i=prior_indices[-1];origin=dates[i]
    if origin not in raw.index:raise ValueError('RS因果原点原价缺失：'+sid)
    factor=D(str(closes[i,j]))/D(str(raw.loc[origin,'close']));segment=int(segments[i,j])
    previous=D(str(raw.loc[:old_day].close.dropna().iloc[-1]));extra={pd.Timestamp(e['effective_date']):e for e in events if e['effective_date']>old_day}
    new=raw.loc[raw.index>pd.Timestamp(old_day)];days=sorted(set(new.index)|set(extra));rows=[]
    for day in days:
        e=extra.get(day)
        if e:
            cash=D(e.get('signal_cash_per_old_share',e['cash_per_old_share']));split=D(e.get('signal_split_ratio',e['split_ratio']))
            if previous<=cash:raise ValueError('参照权益因果因子非法：'+sid)
            factor*=previous/((previous-cash)/split)
        if day in new.index:
            r=new.loc[day];rows.append(dict(date=day,close=float(D(str(r.close))*factor),volume=r.volume,observed_bar=bool(r.observed_bar),price_eligible=bool(r.price_eligible),segment_id=segment))
            if np.isfinite(r.close) and r.close>0:previous=D(str(r.close))
        elif e:
            previous=(previous-cash)/split
    return pd.DataFrame(rows).set_index('date') if rows else pd.DataFrame(columns=['close','volume','observed_bar','price_eligible','segment_id'],index=pd.DatetimeIndex([],name='date'))


def extend_h1(old,signals,target):
    model=module('desk_rs_h1',ROOT/'research_rounds/rs-h1-execution-20261025/code/rs_h1_model.py')
    with np.load(old.h1_path) as z:a={k:z[k] for k in z.files}
    dates=pd.DatetimeIndex(a['dates']);new=pd.DatetimeIndex(sorted(set().union(*(set(f.index) for f in signals.values()))));new=new[new>dates[-1]];cal=dates.append(new);n=len(a['symbols']);nnew=len(new)
    if not nnew:raise ValueError('没有新的完整市场观察')
    for key in ['close','segment','raw','score']:a[key]=np.vstack([a[key],np.full((nnew,n),np.nan)])
    for key in ['obs_count','h','nref']:a[key]=np.vstack([a[key],np.zeros((nnew,n),int)])
    for j,s in enumerate(a['symbols']):
        f=signals[str(s)];count=int(a['obs_count'][len(dates)-1,j])
        for i,day in enumerate(new,len(dates)):
            a['h'][i,j]=min(252,int(a['h'][len(dates)-1,j])+i-len(dates)+1)
            if day in f.index:
                r=f.loc[day]
                if bool(r.observed_bar) and bool(r.price_eligible) and np.isfinite(r.volume) and r.volume>0:
                    a['close'][i,j]=r.close;a['segment'][i,j]=r.segment_id;count+=1
            a['obs_count'][i,j]=count
    for t in range(len(dates),len(cal)):
        for left,right in [(0,1709),(1709,n)]:
            age=a['h'][t,left:right];ready=np.isfinite(a['close'][t,left:right])&(a['obs_count'][t,left:right]>=6)&(age>=5)
            for h in np.unique(age[ready]):
                v=model.raw_momentum(a['close'][:,left:right],a['segment'][:,left:right],a['obs_count'][:,left:right],t,int(h));ref=np.sort(v[np.isfinite(v)]);indices=np.flatnonzero((age==h)&ready);jj=indices+left;a['raw'][t,jj]=v[indices];a['nref'][t,jj]=len(ref)
                if len(ref)>=20:
                    vv=v[indices];pct=100*(np.searchsorted(ref,vv,'left')+.5*(np.searchsorted(ref,vv,'right')-np.searchsorted(ref,vv,'left')))/len(ref);a['score'][t,jj]=np.where(np.isfinite(vv),pct,np.nan)
    a['dates']=cal.values;np.savez_compressed(target,**a)
