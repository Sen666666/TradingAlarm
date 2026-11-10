"""Terminate original long episode at nonpositive existing five-bar price direction."""
import pandas as pd

def short_reversal_state(base,fast):
 if not base.index.equals(fast.index):raise ValueError('Aligned dated inputs required')
 live=False;previous=False;out=[]
 for value,direction in zip(base,fast):
  current=bool(value)
  if not current:live=False
  elif not previous:live=True
  if pd.notna(direction) and direction<=0:live=False
  out.append(float(live));previous=current
 return pd.Series(out,index=base.index,name=base.name)
