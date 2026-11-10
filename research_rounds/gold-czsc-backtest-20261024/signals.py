"""Sequential native CZSC observations. No terminal-geometry backdating."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('CZSC_HOME',str(ROOT/'.tools/czsc/cache'));os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.tools/czsc/mpl'))
import czsc
import numpy as np,pandas as pd
SPECS=[('first_buy','cxt_first_buy_V221126',{'di':1}),('first_sell','cxt_first_sell_V221126',{'di':1}),('second','cxt_second_bs_V230320',{'di':1,'ma_type':'SMA','timeperiod':21}),('third','cxt_third_bs_V230319',{'di':1,'ma_type':'SMA','timeperiod':34}),('third_aux','cxt_third_buy_V230228',{'di':1})]
BUY_SETS={'B1':['B1'],'B2':['B2'],'B3':['B3'],'B3A':['B3A'],'B23':['B2','B3'],'B123':['B1','B2','B3']}
LABELS={'B1':'一买','B2':'均线辅助二买','B3':'中枢三买辅助','B3A':'笔三买辅助','B23':'二买或中枢三买','B123':'一买或二买或中枢三买'}

def build(bars):
    raw=[czsc.RawBar(symbol='AU0',dt=dt.to_pydatetime(),id=i,freq=czsc.Freq.D,open=float(row.open),high=float(row.high),low=float(row.low),close=float(row.close),vol=float(row.volume),amount=0.) for i,(dt,row) in enumerate(bars.iterrows())]
    c=czsc.CZSC([raw[0]],max_bi_num=100,min_bi_len=6);seen=set();rows=[];events=[]
    for i,b in enumerate(raw):
        if i:c.update(b)
        bi=c.bi_list[-1] if c.bi_list else None
        row=dict(date=bars.index[i],bi_count=len(c.bi_list),bi_start=str(bi.sdt) if bi else '',bi_end=str(bi.edt) if bi else '',bi_direction=str(bi.direction) if bi else '',bi_low=float(bi.low) if bi else np.nan,bi_high=float(bi.high) if bi else np.nan)
        row.update({k:0 for k in ['B1','B2','B3','B3A','S1','S2','S3']})
        for alias,name,params in SPECS:
            sigs=czsc._native.call_signal(name,c,params);ss=sigs[0] if sigs else None
            row[alias+'_value']=ss.value if ss else '';kind=None
            if ss:
                if alias=='first_buy' and ss.v1=='一买':kind='B1'
                elif alias=='first_sell' and ss.v1=='一卖':kind='S1'
                elif alias=='second' and ss.v1 in ['二买','二卖']:kind='B2' if ss.v1=='二买' else 'S2'
                elif alias=='third' and ss.v1=='三买' and ss.v2 in ['均线新高','均线底分']:kind='B3'
                elif alias=='third' and ss.v1=='三卖' and ss.v2 in ['均线新低','均线顶分']:kind='S3'
                elif alias=='third_aux' and ss.v1=='三买':kind='B3A'
            if kind is None or bi is None:continue
            key=(kind,str(bi.sdt),str(bi.edt),float(bi.fx_a.fx),float(bi.fx_b.fx))
            if key in seen:continue
            seen.add(key)
            valid=not kind.startswith('B') or (b.low>=bi.low and b.close>bi.low)
            if valid:row[kind]=1
            events.append(dict(recognized=str(b.dt.date()),kind=kind,value=ss.value,valid=valid,endpoint=str(pd.Timestamp(bi.edt).date()),support=float(bi.low),start=str(pd.Timestamp(bi.sdt).date()),lag_days=(b.dt.date()-pd.Timestamp(bi.edt).date()).days))
        row['new_sell']=int(any(row[k] for k in ['S1','S2','S3']));row['new_buy']=int(any(row[k] for k in ['B1','B2','B3','B3A']))
        rows.append(row)
    return pd.DataFrame(rows).set_index('date'),pd.DataFrame(events)
