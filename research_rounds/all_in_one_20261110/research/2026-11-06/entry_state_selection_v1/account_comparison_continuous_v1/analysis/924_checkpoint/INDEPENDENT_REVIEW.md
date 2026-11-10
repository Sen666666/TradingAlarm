# Independent checkpoint audit: 2024 September–October

Read-only analysis of saved account histories, not an account rerun. Imported continuous_inputs solely to resolve pickle classes; did not call inputs(). Original Python 3.13.7, PYTHONDONTWRITEBYTECODE=1. One checkpoint load retained in memory. Raw prepared bars read only for endpoint valuation checks.

Source: run_1200000/latest_checkpoint/checkpoint.pkl, metadata last event 2024-12-31 15:10 +08:00. SHA256 independently computed before unpickling and exactly matched metadata: bdbaae91326600d473194b1142682a78a18ccca24d576dc629b8d50ce5fd34d7. latest_checkpoint may subsequently be overwritten by the live run; this report refers specifically to that hash.

## Confirmed ACT timing

E31 audit_log risk_checkpoint: 2024-09-12 close pause, NAV 689139.0560941361460, episode peak 863245.2917487660915, drawdown 20.1688022302357%, episode 2. At the same close PVR NAV 709645.5969097193970, peak 872638.9942777076245, drawdown 18.6782161279533%, on=True. PVR has no pause/resume event during August–October.

E31 trades: 2024-09-13 09:30 exactly 30 sells, all reason ACT_pause, no buys. Available cash increased 323587.3053741361460 to 669115.9059309826440; open cash bridge residual 0. End-of-day holdings zero on every session from September 13 through September 27.

E31 resumed only 2024-09-27 close: flat=True, breakout=True, new peak NAV 689097.9366509826440, episode 3. That close had zero positions and 2380 pending intents. September 30 open bought 52 stocks (50 mobile, 2 core); cash fell to 68933.9415378724180, zero bridge residual.

Therefore September 24–27 E31 lacked admissions because the account was paused, not because the same active candidates merely lost ranking or cash admission. This does not quantify a hypothetical no-ACT strategy or isolate how much of the full-period difference is causally attributable to ACT.

## Account state and money

Date; PVR NAV / inventory / stocks / cash; E31 NAV / inventory / stocks / cash
2024-08-30; 715097.4988227131040 / 457273.13 / 39 / 235256.4649027131040; 698497.5258714931540 / 441295.22 / 34 / 237541.1071514931540
2024-09-23; 715647.6493831954470 / 495736.65 / 45 / 196995.5274631954470; 689097.9366509826440 / 0 / 0 / 669115.9059309826440
2024-09-24; 734733.3572344167470 / 589513.45 / 47 / 122304.4353144167470; E31 unchanged and off
2024-09-25; 742103.2060047316970 / 645606.75 / 52 / 73580.9840847316970; E31 unchanged and off
2024-09-26; 765459.3560047316970 / 668962.90 / 52 / 73580.9840847316970; E31 unchanged and off
2024-09-27; 789760.6560047316970 / 693164.20 / 52 / 73580.9840847316970; E31 unchanged NAV and inventory, resumes at close
2024-09-30; 854753.2660047316970 / 758156.81 / 52 / 73580.9840847316970; 711650.3922578724180 / 622734.42 / 52 / 68933.9415378724180
2024-10-31; 929865.7355448113370 / 815651.88 / 71 / 90682.7596248113370; 753961.8593721013285 / 659528.24 / 58 / 73914.7086521013285

Inventory plus cash is not NAV because dividend receivables remain assets. In particular E31 paused NAV exceeds cash by 19982.03072 of receivables, not an unexplained cash discrepancy.

PVR September 24 and 25 each had 7 buy fills. September 26–30 added no further fills; its late-September gains principally marked existing positions. PVR September 30 open has zero buy/sell fills, despite many pending intents.

## Exact PNL reconciliation and contribution

For each account and stock: ending marked inventory minus beginning marked inventory plus actual sell gross minus buy gross minus all trade fees plus dividend receivables newly accrued in the interval. Beginning/end marks used last eligible observed raw close at or before the boundary. All 12 endpoint inventory sums (both arms at August 30, September 12/23/27/30, October 31) exactly match saved daily inventory. All eight account/interval PNL sums below exactly match daily NAV differences, residual 0E-13. Thus numbers include unrealized changes and are not realized-only trade PNL.

Interval (exclusive starting close, inclusive ending close); PVR PNL; E31 PNL
Aug30–Oct31; 214768.2367220982330; 55464.3335006081745
Sep23–Sep27; 74113.0066215362500; 0
Sep23–Sep30; 139105.6166215362500; 22552.4556068897740
Sep30–Oct31; 75112.4695400796400; 42311.4671142289105

Aug30–Oct31 differential gain: 159303.9032214900585. Ending NAV gap 175903.8761727100085 includes the pre-existing Aug30 gap 16599.9729512199500.

Largest positive stock contributions to that differential (PVR PNL; E31 PNL; difference):
600619.SH: 12462.5310058533000; 189.464074552500; 12273.0669313008000
601336.SH: 11011.3794516422000; 152.3332534228000; 10859.0461982194000
600958.SH: 10418.3977403312500; 236.5616245632000; 10181.8361157680500
600292.SH: 9853.0266444032000; 0; 9853.0266444032000
300489.SZ: 8757.4160040015000; 0; 8757.4160040015000
601601.SH: 7600.8846581286000; -681.6697061274000; 8282.5543642560000
601628.SH: 7871.1672528522000; 9.0803273264000; 7862.0869255258000

September23–27 PVR largest contributions, E31 all zero: 601336 7007.4158087198; 601601 6072; 600958 5735; 601628 4023; 601319 3406.5595647517; 603093 3374; 601066 3248; 601881 3240; 601995 3210. These are factual exposure gains, not a forecast of attainable returns.

## Concrete execution/admission examples

601336.SH: both bought 400 September 2 at 32.896440. E31 sold 400 September 13 at 31.904040 (ACT_pause). PVR retained and added 400 September 24 at 33.626805. E31 reentered only 300 September 30 at 45.12255. Both exited October 16 at 47.07645, I_structure_exit (PVR 800/E31 300).

600958.SH: Aug30 PVR already held 3700, E31 4800. E31 sold all September 13 at 8.475760 (ACT_pause) and did not reenter by October31. PVR sold 3700 October10 at 11.244375, CP1_add_protection.

600619.SH: identical rank842 on September10, but September11 E31 core admission rejected probe_risk, PVR bought100 at5.272635. PVR added2000 Sep20,1900 Sep23,1800 Sep24, reached5800 shares; sold5700 October11 at9.105445 (CP1_add_protection). E31 only bought100 October16 at9.50475. Thus this example already differs before ACT pause and cannot be attributed solely to pause or that day's rank.

300489.SZ: October18 close mobile rank PVR5/E3138, both sizecap200. October21 PVR bought200 at68.064015; E31 rejected probe_risk. PVR added100 October22 at81.680820 and100 October24 at94.04700; E31 rejections included cash_or_original_reserve,probe_risk on Oct22/23 and cash_or_original_reserve on Oct24. No E31 position through Oct31.

600292.SH: October22 both had industry_invalidated and no fill. October22 close rank PVR14/E3153 (core caps1000/800), next open PVR bought100 at7.223610; E31 core and mobile rejected cash_or_original_reserve. PVR subsequently bought400 Oct24,1400 Oct25,1500 Oct30,700 Oct31. E31 remained unfilled with cash/original reserve and sometimes probe risk rejections. October23 close ranks PVR8/E3191, October24 close PVR7/E31112. These are explicit ranking and funding-path differences; they do not identify a pure rank treatment effect holding account state constant.

Funding result comparisons above filter strictly 09:30, avoiding close sizing rejects. Distinct stock/sector risk exposure and account cash were already different. No threshold changes or counterfactual reruns were made.

## Additional ACT evidence for 2022 interpretation

PVR pause Apr21: NAV948680.6573587016925, peak1200000, drawdown20.9432785534%; E31 pause Apr22: NAV957369.5219745419130, peak1200000, drawdown20.2192065021%. Both resume Jun17; new episode peaks reset to PVR937437.1824527855865 and E31944823.2598292611880. Each has exactly one pause and one resume in2022. Annual drawdown is not capped20% because subsequent drawdown is measured against reset episode peak, and triggers occur at close before next-open execution. The resume row's episode_drawdown records the old-peak calculation even though its peak field has just been reset; do not recompute that row from the new peak or call it a logging inconsistency.

## Verified source labels and sectors

Source /Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json, SHA256 36ec5a8358db213f96c9716d056fe6fab5d8fdca6b60e67693afbe72f2cb8a54. Sector IDs agree with checkpoint runner.sector_by_sid. These labels are original input metadata, not historical-name/PIT guarantees.

600619.SH 海立股份: 白色家电 URFI881131.
601336.SH 新华保险: 保险 URFI881156.
600958.SH 东方证券: 证券 URFI881157.
600292.SH metadata label 电投水电: 电力 URFI881145; do not describe this as verified 2024 name.
300489.SZ 光智科技: 光学光电子 URFI881122.
601601.SH metadata label XD中国太: 保险 URFI881156; preserve caveat on source abbreviation/ex-dividend prefix.
601628.SH 中国人寿: 保险 URFI881156.

601628: both bought400 Sep3 at34.177080. E31 sold800 Sep13 at33.823080 ACT_pause and did not buy again in the interval. PVR added400 Sep19 at35.027505 and sold900 Oct10 at43.258360 CP1_add_protection.

Across all stocks, Aug30–Oct31 PVR-minus-E31 sector contribution: insurance URFI881156 36734.5373891126500; securities URFI881157 24202.4521283042000; white appliances URFI881131 15425.1414242518000; optical/optoelectronics URFI881122 15258.7476051631000; electricity URFI881145 10110.5390281873500. These are ex-post accounting contributions, not causal effects of replacing a sector or ranking rule.
