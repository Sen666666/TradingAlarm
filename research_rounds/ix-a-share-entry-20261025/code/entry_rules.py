"""Four fixed buy-event definitions; the shared IX target is never changed."""
import numpy as np
import pandas as pd

def events(g,ix):
 prev=g.grade.groupby(g.segment_id,sort=False).transform(lambda a:a.ffill().shift())
 valid=g.ready.astype(bool)&prev.notna()
 common=ix.buy_event.astype(bool)&g.ready.astype(bool)
 out=pd.DataFrame(index=g.index)
 out['previous_grade']=prev
 out['IX']=common
 out['W23']=common&valid&prev.eq(2)&g.grade.eq(3)
 out['W2H']=common&valid&prev.eq(2)&g.grade.ge(3)
 out['C3']=common&valid&prev.lt(3)&g.grade.ge(3)
 out['raw_W23']=valid&prev.eq(2)&g.grade.eq(3)
 out['raw_W2H']=valid&prev.eq(2)&g.grade.ge(3)
 out['raw_C3']=valid&prev.lt(3)&g.grade.ge(3)
 return out
