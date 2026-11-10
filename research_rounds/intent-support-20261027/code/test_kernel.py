from study import *
sys.path.append(str(ROOT/'research_rounds/pv-strength-b5-20261025/code'));ev=P.C.import_path('test_intent_ev',ROOT/'research_rounds/pv-strength-b5-20261025/code/evidence.py');env=dict(ev.__dict__);src=(O/'code/fast_kernel.py').read_text();exec(src,env);fn=env['fast_events'];oracle=dict(ev.__dict__);exec(src.replace('0.5 * math.sqrt(5)','math.sqrt(5)'),oracle)
i=pd.date_range('2020-01-01',periods=200);f=pd.DataFrame({'close':100*np.exp(.02*np.sin(np.arange(200)*.4)+np.arange(200)*.001),'volume':100.},index=i)
a,_=fn(f);b,_=fn(f.iloc[:137]);pd.testing.assert_frame_equal(a.iloc[:137],b,check_exact=True)
x,_=ev._event_facts(f);y,_=oracle['fast_events'](f);pd.testing.assert_frame_equal(x,y,check_exact=True)
g=f.copy();g['close']*=10;z,_=fn(g);assert a.event.equals(z.event);np.testing.assert_allclose(a.confirmed_pivot_price*10,z.confirmed_pivot_price,equal_nan=True,rtol=1e-12)
g=f.copy();g['volume']=0;q,_=fn(g);assert q.event.eq(0).all()
g=f.copy();g.loc[i[100]:,'volume']*=4;v,_=fn(g);assert not np.allclose(v.confirmation,a.confirmation,equal_nan=True)
save(O/'tests.json',{'passed':True,'checks':['physical_prefix','copied_kernel_at_original_threshold_exact','price_scale_invariance','zero_volume_cannot_confirm','same_prices_different_volume_change_confirmation'],'normal_events':int(a.event.ne(0).sum()),'high_volume_events':int(v.event.ne(0).sum())})
