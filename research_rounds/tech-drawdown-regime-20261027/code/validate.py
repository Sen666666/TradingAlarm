from prepare import *
if __name__=='__main__':
 s=pd.Series([np.nan,.5,.61,.5,.4,.39,.6,.61]);assert latch(s).tolist()==[False,False,True,True,True,False,False,True]
 full=pd.read_csv(O/'signals-v1/breadth.csv',index_col=0,parse_dates=True);g=pd.read_csv(O/'signals-v1/market-gates.csv',index_col=0,parse_dates=True);receipts=[];full.index=full.index.as_unit('ns');g.index=g.index.as_unit('ns')
 for cutoff in ['2025-12-31','2026-06-30','2026-08-31']:
  r,t,a,gg,sg=generate(cutoff)
  pd.testing.assert_frame_equal(a,full.loc[:cutoff],check_exact=False,rtol=1e-12,atol=1e-14,check_freq=False);pd.testing.assert_frame_equal(gg,g.loc[:cutoff],check_freq=False)
  receipts.append({'cutoff':cutoff,'rows':len(a),'stocks':len(t)})
 (O/'signal-validation.json').write_text(json.dumps({'passed':True,'hysteresis_contract':True,'physical_prefixes':receipts},indent=2));print('signal prefixes passed',flush=True)
