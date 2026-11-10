"""Two fixed synthetic market paths only; original CP1, no orders or income."""
from pathlib import Path
import importlib.util,json,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
s=importlib.util.spec_from_file_location('behavior_original_CP1',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 t=time.monotonic();pre=150;n=90;cases=[]
 for name,tail in [('slow_continuous_no_pullback',200*np.exp(.0015*np.arange(1,n+1))),('one_jump_then_flat',np.repeat(220.,n))]:
  close=np.r_[np.repeat(200.,pre),tail];f=pd.DataFrame(dict(close=close,amount=np.repeat(1e8,len(close)),segment_id=0,e0_valid=True,e0_down=False),index=pd.bdate_range('2000-01-03',periods=len(close)));z=m.calculate(f);q=z.iloc[pre:];r=q[q.receipt];passed=bool(len(r)>1) if name.startswith('slow') else bool(len(r)==1 and not q.receipt.iloc[1:].any());assert passed,name
  cases.append(dict(name=name,expectation='multiple new receipts from subsequent price advances without E0 down events' if name.startswith('slow') else 'one jump receipt; flat later produces none even as windows roll',passed=passed,tail_receipts=int(q.receipt.sum()),tail_E0_down_events=int(f.e0_down.iloc[pre:].sum()),receipt_dates=[str(d.date()) for d in r.index],receipt_displacements=r.displacement.tolist(),receipt_frozen_scales=r.scale.tolist(),same_day_receipts_max=1,scope='single original CP1 stream only, not account/industry-stage/cross-scale integration'))
 result=dict(passed=True,original_model=str(P),model_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),synthetic_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),prewarm=pre,tail_observations=n,tests=cases,seconds=time.monotonic()-t,new_history_or_economic_runs=0,cross_scale_stage_consumer_not_implemented_or_tested=True);(O/'CP1_TWO_PATHS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print([(x['name'],x['tail_receipts'],x['passed']) for x in cases],result['seconds'])
if __name__=='__main__':main()
