from pathlib import Path
p=Path(__file__).parent/'run_pilot.py';s=p.read_text()
s=s.replace("rp.loc[future,'ordinary_value']=1e100", "rp.loc[future,'ordinary_value']=1e100;rp.loc[future,'ordinary']=~rp.loc[future,'ordinary'];rp.loc[rp.ordinary_known_at.ge(cut),'ordinary_known_at']=pd.Timestamp('2035-01-04')")
s=s.replace("ap=a.copy();ap.loc[ap.day.ge(cut),'q']=1e50", "ap=a.copy();ap['q']=ap.q.astype(float);ap.loc[ap.day.ge(cut),'q']=1e50")
s=s.replace("max_etaY=0.\n for age", "max_etaY=0.;max_atom_mass=np.zeros(len(Z));min_atom_mass=np.zeros(len(Z));all_y=np.concatenate([b['Y'] for b in bs]);ymax=float(all_y.max());ymin=float(all_y.min())\n for age")
s=s.replace("inv=np.exp(-L);h0=b['q0']*inv;hu=b['qU']*inv;hm=b['qM']*inv", "h0=np.exp(np.log(b['q0'])-L) if b['q0']>0 else np.zeros(len(Z));hu=np.exp(np.log(b['qU'])-L) if b['qU']>0 else np.zeros(len(Z));hm=np.exp(np.log(b['qM'])-L) if b['qM']>0 else np.zeros(len(Z))")
s=s.replace("surv*=h0", "max_atom_mass+=surv*p[:,b['Y']==ymax].sum(axis=1);min_atom_mass+=surv*p[:,b['Y']==ymin].sum(axis=1)\n  surv*=h0")
s=s.replace("max_abs_etaY=max_etaY)", "max_abs_etaY=max_etaY,global_maxY_conditional_mass=max_atom_mass/np.maximum(mass,np.finfo(float).tiny),global_minY_conditional_mass=min_atom_mass/np.maximum(mass,np.finfo(float).tiny))")
start=s.index('def selftest():')
s=s[:start]+'''def influence_diagnostic(beta,Z,n,obs,bs):
 """Fixed q/scaler local data-loss influence; does NOT remove/rebuild empirical atoms."""
 eta=Z@beta;res=-obs.Y.fillna(0).to_numpy(float);info=np.zeros(len(Z))
 for g,b in enumerate(bs):
  _,mu,var=moments(eta,b);res+=n[:,g]*mu;info+=n[:,g]*var*np.sum(Z*Z,axis=1)
 gi=res[:,None]*Z;_,_,hh=objective(beta,Z,n,obs,bs);ix=int(np.nanargmax(obs.Y.to_numpy(float)));delta=np.linalg.solve(hh,gi[ix]);gradnorm=np.linalg.norm(gi,axis=1)
 fc=forecast(Z,beta,bs);clusters={}
 for col in ['sid','root_cluster','signal_day']:
  rows=pd.DataFrame({'cluster':obs[col].astype(str).to_numpy(),'gradient_norm':gradnorm,'information_trace':info})
  agg=rows.groupby('cluster')[['gradient_norm','information_trace']].sum();clusters[col]=dict(clusters=len(agg),gradient_norm_top1_share=agg.gradient_norm.nlargest(1).sum()/agg.gradient_norm.sum(),gradient_norm_top5_share=agg.gradient_norm.nlargest(5).sum()/agg.gradient_norm.sum(),information_trace_top1_share=agg.information_trace.nlargest(1).sum()/agg.information_trace.sum(),information_trace_top5_share=agg.information_trace.nlargest(5).sum()/agg.information_trace.sum())
 def qs(v):return dict(zip(['min','p50','p90','p99','max'],np.quantile(v,[0,.5,.9,.99,1]).tolist()))
 return dict(maxY_round_id=obs.iloc[ix].round_id,maxY=float(obs.iloc[ix].Y),maxY_data_gradient=gi[ix],maxY_fixed_q_scaler_delete_direction_delta=delta,delta_L2=float(np.linalg.norm(delta)),delta_over_beta_L2=float(np.linalg.norm(delta)/max(np.linalg.norm(beta),1e-15)),limitation='Local beta_delete approx beta+H^-1 g_i with q/scaler fixed. Does not account for empirical atom, N or scaler changes. Not complete leave-one-out robustness.',clusters=clusters,train_top1_age_atom_mass=qs(fc['top1_age_conditional_atom_mass']),train_top5_age_atom_mass=qs(fc['top5_age_conditional_atom_mass']),train_global_maxY_mass=qs(fc['global_maxY_conditional_mass']),train_global_minY_mass=qs(fc['global_minY_conditional_mass']),train_fraction_global_maxY_mass_ge95pct=float(np.mean(fc['global_maxY_conditional_mass']>=.95)))

'''+s[start:]
s=s.replace("model.update(marked_beta=bm,marked_QA=qa,", "model.update(influence=influence_diagnostic(bm,Z,n,tr,bs),marked_beta=bm,marked_QA=qa,")
s=s.replace("rr,aa,uu,hashes=load_sources();allobs,_=snapshot(rr,aa,uu,pd.Timestamp('2026-05-15')) if False else (None,None)", "rr,aa,uu,hashes=load_sources()")
p.write_text(s)
p=Path(__file__).parent/'PROTOCOL.md';s=p.read_text();s=s.replace('No post-result minimum-tail gate or parameter search.','No post-result minimum-tail gate or parameter search.\nFixed tail sensitivity: for the largest positive training-Y round at each cut, report its data score g_i and local delete direction H^{-1}g_i, so beta_delete approximately beta+H^{-1}g_i. Hold q and scaler fixed. This does NOT include changes in the empirical atom support, N or scaler and is NOT full-process leave-one-out robustness. No refitted LOO variants. Report gradient-norm and data-information-trace concentration by sid/root/signal date; train/validation maximum |etaY|; train conditional per-age top1/top5 atom mass quantiles; H120 conditional mass on global training min/max Y and fraction with >=95% on global max Y. These are diagnostics only, never model/threshold choices. Large-mark gross-error influence is not bounded; logsumexp stability does not imply statistical robustness.');p.write_text(s)
