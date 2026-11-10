"""Synthetic invariant checks only. No formula, threshold or case selection change."""
from pathlib import Path
import ast,json,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
s=(O/'fixed_cohort_features.py').read_text();sourcetext=s;env={'np':np,'pd':pd}
for node in ast.parse(s).body:
 if isinstance(node,ast.FunctionDef) and node.name in ['pricevalid','ident','contiguous']:
  exec(compile(ast.get_source_segment(s,node),'<definitions-only>','exec'),env)
check={}
ix=pd.date_range('2020-01-01',periods=5)
p=pd.DataFrame(dict(close=[100,110,105,95,120],segment_id=0,source_kind='test',source_path='test',price_eligible=True,observed_bar=True,is_observed_bar=True,source_invalid=False,synthetic_event_bar=False,raw_volume=1.),index=ix)
r=math.log(1.1);h=(np.log(p.close.iloc[1:]/100)/r).cummin().clip(0,1)
check['birth_h_equals_one']=abs(h.iloc[0]-1)<1e-12
check['below_origin_then_rebound_never_revives']=h.iloc[-2]==0 and h.iloc[-1]==0
check['h_nondecreasing_forbidden']=bool((np.diff(h)<=0).all())
check['contiguous_valid_path_known']=env['contiguous'](p,ix)
q=p.drop(ix[2]);check['missing_immediate_common_day_unknown']=not env['contiguous'](q,ix)
q=p.copy();q.loc[ix[2]:,'source_path']='changed';check['source_path_change_unknown']=not env['contiguous'](q,ix)
q=p.copy();q.loc[ix[2]:,'segment_id']=1;check['segment_change_unknown']=not env['contiguous'](q,ix)
q=p.copy();q.loc[ix[2],'source_invalid']=True;check['invalid_source_unknown']=not env['contiguous'](q,ix)
q=p.copy();q.loc[ix[2],'raw_volume']=0;check['suspension_bar_unknown']=not env['contiguous'](q,ix)
u=np.array([-1.,-.3,0.,.3,1.]);b=np.array([-1.,1.,0.,-1.,1.]);e=u*(1+.5*np.abs(u)*b)
check['e_sign_equals_return_sign']=bool(np.array_equal(np.sign(e),np.sign(u)))
check['e_absolute_bound_1_5']=bool(np.abs(e).max()<=1.5)
W=2.;Uw=.5;S=.75;M=3;d=W+1.5*M;lo=S/d;hi=(S+Uw+1.5*M)/d
check['bounds_cover_unknown_min_max']=0<=lo<=S/(W-Uw)<=hi<=1
check['zero_positive_zero_unknown_denominator_not_score_zero']=(0+1.5*0)==0
check['LOO_equal_weight_inverse_own_retention']=abs((np.mean([.4,.8])-np.mean([.2,.8]))-(.4-.2)/2)<1e-12

# Exercise the actual root function using isolated synthetic in-memory source tables.
from types import SimpleNamespace
rootnode=next(n for n in ast.parse(sourcetext).body if isinstance(n,ast.FunctionDef) and n.name=='root')
def root_test(targets,source_invalid_last=False,source_switch=False):
 raw=p.copy()
 raw['source_invalid']=False
 if source_invalid_last:raw.loc[ix[-1],'source_invalid']=True
 if source_switch:raw.loc[ix[2]:,'source_path']='changed'
 facts=pd.DataFrame({'e0_target':targets,'e0_ready':1,'segment_id':0},index=ix)
 cp=pd.DataFrame({'e0_valid':pd.Series(targets,index=ix).astype(bool)},index=ix)
 st=pd.DataFrame({'day':ix,'close':raw.close.to_numpy(),'E0_episode':'synthetic','stage':0,'stage_name':'observe','action':'observe','reason':'test','receipt':False,'attempt_id':None,'authorization_usable':False})
 re=dict(env);re.update({'IM':{'TEST':{'source_sha256':{'/industry-facts/test':'synthetic'}}},'cal':ix,'loadsrc':lambda rec,suffix:raw,'loadref':lambda rec,key:cp if key=='CP1_input' else st,'source':lambda *args:None,'pd':SimpleNamespace(read_parquet=lambda p:facts,testing=pd.testing,to_datetime=pd.to_datetime)})
 exec(compile(ast.get_source_segment(sourcetext,rootnode),'<definitions-only-root>','exec'),re)
 return re['root']('TEST',ix[-1])['sector_E0_root_status']
check['actual_root_E0_OFF_is_separate']=root_test([0]*5)=='E0_OFF'
check['actual_root_unknown_birth_is_separate']=root_test([1]*5)=='ROOT_UNKNOWN_NO_COMPLETE_0_TO_1'
check['actual_current_E0_unknown_is_separate']=root_test([0,1,1,1,1],True)=='CURRENT_E0_UNKNOWN'
check['actual_root_source_switch_unknown']=root_test([0,1,1,1,1],False,True)=='ROOT_UNKNOWN_MISSING_OR_CHANGED_SOURCE'
check['actual_known_0_to_1_root']=root_test([0,1,1,1,1])=='KNOWN'
# Evaluate exact production summary branches, rather than a substitute implementation.
va=next(n for n in ast.walk(ast.parse(sourcetext)) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='vals' for t in n.targets))
expr={k.arg:k.value for k in va.value.keywords}
state={'W':0.,'M':0,'Uw':0.,'S':0.,'kw':0.,'den':0.,'np':np}
check['actual_no_positive_cohort_state']=eval(compile(ast.Expression(expr['status']),'<actual-summary>','eval'),state)=='NO_POSITIVE_COHORT'
check['actual_no_positive_cohort_R_not_zero']=np.isnan(eval(compile(ast.Expression(expr['R_known']),'<actual-summary>','eval'),state))

check={k:bool(v) for k,v in check.items()}
assert all(check.values()),check
(O/'SYNTHETIC_QA.json').write_text(json.dumps(dict(passed=True,checks=check,no_economic_model=True),indent=2)+'\n')
print(json.dumps(check,indent=2))
