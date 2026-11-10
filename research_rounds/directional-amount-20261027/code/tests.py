from model import run
import pandas as pd,numpy as np,json
from pathlib import Path
O=Path(__file__).resolve().parents[1]
def frame(prices,amount):
 return pd.DataFrame(dict(close=prices,amount=amount,segment_id=0),index=pd.bdate_range('2020-01-01',periods=len(prices)))
# Fixed oscillating prehistory supplies a nonzero daily scale without a future input.
pre=100*np.exp(np.tile([0,.01],40));tail=pre[-1]*np.exp(np.arange(1,31)*.004);normal=frame(np.r_[pre,tail],np.ones(110)*100)
low=normal.copy();low.iloc[80:,low.columns.get_loc('amount')]=25
n=run(normal);l=run(low);tn=n.iloc[80:].index[n.iloc[80:].event.eq(1)][0];tl=l.iloc[80:].index[l.iloc[80:].event.eq(1)][0];assert tl>tn
flat=frame(np.r_[pre,np.full(30,pre[-1])],np.r_[np.ones(80)*100,np.ones(30)*100000]);f=run(flat);assert f.iloc[80:].event.eq(0).all();assert f.iloc[80:].delta_frontier.eq(0).all()
big=normal.copy();big.iloc[90,big.columns.get_loc('close')]=big.close.iloc[89]*.9;big.iloc[90,big.columns.get_loc('amount')]=300;z=run(big);assert z.iloc[90].shock==1 and z.iloc[90].grade==-2;assert z.iloc[90].c_target==0
scaled=normal.copy();scaled.amount*=1000;pd.testing.assert_frame_equal(run(scaled),n)
# identical existing price interval at greater amount cannot advance its frontier.
osc=frame(np.r_[pre,pre[-1]*np.exp(np.tile([.003,.001],15))],np.r_[np.ones(80)*100,np.ones(30)*10000]);o=run(osc);assert o.iloc[82:].delta_frontier.eq(0).all();assert o.iloc[80:].event.eq(0).all()
# A physical cutoff cannot change past state.
pd.testing.assert_frame_equal(run(big.iloc[:95]),z.iloc[:95])
# Segment state restarts and remains unprepared, regardless of previous history.
seg=normal.copy();seg.loc[seg.index[90]:,'segment_id']=1;ss=run(seg);assert ss.iloc[90:].ready.eq(0).all()
res=dict(passed=True,checks=7,normal_confirm=str(tn.date()),low_amount_confirm=str(tl.date()))
(O/'synthetic-r1.json').write_text(json.dumps(res,indent=2)+'\n');print(res)
