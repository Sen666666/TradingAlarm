from pathlib import Path
import ast,json,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
tree=ast.parse((O/'relative_clock.py').read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='rdc')
env=dict(np=np,pd=pd,math=math);exec(compile(ast.Module(body=[fn],type_ignores=[]),'rdc_only','exec'),env)
v=0.9875468618243614
g=np.r_[np.ones(80),v,np.ones(10),v,np.ones(10),v,np.ones(10)]
C=100*g;I=1000*g;x=np.log(C/I);z=env['rdc'](x,np.r_[False,np.ones(len(x)-1,bool)])
events=z[z.relative_event.ne(0)].copy();events['index']=events.index
out=dict(theoretical_ratio=.1,common_factor_shock=v-1,x_distinct=np.unique(x).tolist(),x_range=float(np.ptp(x)),events=events.to_dict('records'),up=int(z.relative_event.eq(1).sum()),down=int(z.relative_event.eq(-1).sum()),original_code_unchanged=True,no_parameter_repair=True)
assert out['up']==2 and out['down']==2
(O/'NUMERICAL_COUNTEREXAMPLE.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
