from pathlib import Path
p=Path(__file__).parent/'run_pilot.py';s=p.read_text()
s=s.replace("r=pd.concat(frames,ignore_index=True,sort=False);a=", "r=pd.concat(frames,ignore_index=True,sort=False);r['window']=r.window.astype(str);a=")
s=s.replace("return dict(gradient_max_error=err", "stress_forecast=forecast(np.array([[1e6,0,0,0,0],[-1e6,0,0,0,0]]),np.array([1.,0,0,0,0]),bs);assert np.max(abs(stress_forecast['prob'].sum(axis=1)-1))<1e-10\n onlyatom=[dict(N=1,Y=np.array([1.]),q=np.array([1.]),q0=0.,qU=0.,qM=0.) for _ in range(5)];zero_base_forecast=forecast(np.array([[-1e6,0,0,0,0]]),np.array([1.,0,0,0,0]),onlyatom);assert zero_base_forecast['prob'][0,2]==1\n return dict(gradient_max_error=err")
s=s.replace("real_data_fits=0)", "full_forecast_extreme_eta_pass=True,zero_base_full_forecast_pass=True,real_data_fits=0)")
s=s.replace("hrows=[]\n for _,z", "hrows=[];admin_H=0\n for _,z")
s=s.replace("uday=fr.get(z.round_id,pd.NaT);cat='S'", "uday=fr.get(z.round_id,pd.NaT);cat='S'\n  source_end=end if pd.notna(end) else (uday if pd.notna(uday) else pd.to_datetime(z.last_known_mark_day));assert hday<=CAL[-1]\n  if pd.isna(source_end) or source_end<hday:\n   if pd.isna(end) and pd.isna(uday):admin_H+=1;continue")
s=s.replace("hdf=pd.DataFrame(hrows);", "dump('H120_OBSERVABILITY_QA.json',dict(H=H,original_entered=int(x.entered.sum()),observed_H_rows=len(hrows),administrative_before_H=admin_H,calendar_end=str(CAL[-1]),nonterminal_S_requires_observed_source_through_H=True));assert len(hrows)+admin_H==int(x.entered.sum())\n hdf=pd.DataFrame(hrows);")
p.write_text(s)
