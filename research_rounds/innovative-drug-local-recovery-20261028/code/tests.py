from recovery import *
idx=pd.date_range('2020-01-01',periods=100);symbols=[f'S{k}_{j}' for k in range(4) for j in range(5)];roster=pd.DataFrame([dict(symbol=s,sector_id=s.split('_')[0]) for s in symbols]);r=pd.DataFrame(.01,index=idx,columns=symbols);m=pd.DataFrame(1.,index=idx,columns=symbols);checks=0
z,c=calculate(r,m,roster);assert z.breakout.iloc[-1] and c.valid_sectors.iloc[-1]==4;checks+=1
m.loc[:,symbols[-5:]]=np.nan;z,c=calculate(r,m,roster);assert z.breakout.iloc[-1] and c.valid_sectors.iloc[-1]==3;checks+=1
m.loc[idx[-1],symbols[10]]=np.nan;z,c=calculate(r,m,roster);assert not z.breakout.iloc[-1] and c.valid_sectors.iloc[-1]==2 and pd.isna(z.breadth.iloc[-1]);checks+=1
m.loc[idx[-1],symbols[10]]=1
for k in range(3):m.loc[:,[f'S{k}_{j}' for j in [3,4]]]=-1
z,c=calculate(r,m,roster);assert z.breadth.iloc[-1]==.6 and not z.breakout.iloc[-1];checks+=1
m.loc[:,symbols]=1;r.loc[idx[-1],:]=-.01;z,c=calculate(r,m,roster);assert not z.breakout.iloc[-1];checks+=1
r.loc[idx[-1],:]=.01;z,c=calculate(r,m,roster);q,cc=calculate(r[symbols[::-1]],m[symbols[::-1]],roster.iloc[::-1]);pd.testing.assert_frame_equal(z,q,check_exact=True);checks+=1
save(O/'tests.json',{'passed':True,'coverage_and_threshold_cases':checks,'inherited_execution_contract':str(COMBO/'tests.json'),'inherited_execution_boundary':str(COMBO/'execution-boundary-check.json')})
