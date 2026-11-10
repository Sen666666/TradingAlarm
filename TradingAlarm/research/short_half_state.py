"""Keep original entries; persist half target after first later short-negative observation."""
import pandas as pd

def short_half_state(base,fast,restore=False):
 if not base.index.equals(fast.index):raise ValueError('Aligned dated inputs required')
 state=0.;previous=False;out=[]
 for value,direction in zip(base,fast):
  current=bool(value)
  if not current:state=0.
  elif not previous:state=1.
  elif pd.notna(direction):
   if direction<=0:state=.5
   elif restore:state=1.
  out.append(state);previous=current
 return pd.Series(out,index=base.index,name=base.name)
