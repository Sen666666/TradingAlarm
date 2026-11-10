# CP formation-time CE: fixed-case preview only

Status: complete score/rank sealing, full label evaluation NOT started. The full score job was already running when the parent narrowed the next step; it completed once without reading labels. Only the prespecified 18 same-day added/removed examples have subsequently been joined to existing labels, after their membership was sealed. No formula or ordering changes.

## Formula and units

r_j = log(C_j/C_previous same-source observation). Original s_j = max(1.4826 * median(abs(r) over 63 observations strictly before j), 1e-8); z_j=max(s_j,log(1.001)). Native scale is z frozen at the true formation anchor, not the current rolling s/z.

Original amount B_j = median(amount over 21 observations strictly before j); u_j=tanh(r_j/s_j); b_j=tanh(log(amount_j/B_j)); m_j=1+0.5*abs(u_j)*b_j. This b is the original cache v, renamed only in this explanation to avoid collision with new volatility-budget v. m is dimensionless, with range (0.5,1.5); it is reused verbatim, not recomputed.

D_t=original cp.displacement=sum(new upward price-frontier log increments since the true anchor); K_t=original cp.credit=sum(m_j*new upward log frontier increment). Both D and K have log-return units. They are related evidence, not independent tests. Original certification requires both >=sqrt(5)*frozen z and a new frontier increment.

v_j^2=max(mean(last 21 valid same-source r strictly before j squared),log(1.001)^2). It needs all 21 prior valid observations; otherwise UNKNOWN. The current signal r_j does not enter v_j, but it does enter later forecasts. Same-source r history continues across E0/CP resets and receipts, while source change clears this history.

V_t=sum(v_j^2 over original observations after the true CP anchor through t); n is that same exact observation count. Original start/E0_down_reset/lower_anchor reset V/n at their anchor day, which contributes zero. E0_invalid/unprepared/source change clear V/n. Ordinary pullbacks keep accumulating both. On receipt_consumed, compute CE=min(D,K)/sqrt(V) FIRST, then reset V/n with the receipt close as the next anchor.

sqrt(V) is a formation-period cumulative second-moment amplitude. No serial-independence or zero-mean claim has been established; it is not an exact variance of a sum, p-value, win probability, or forecast Sharpe. CE has no gate, n cap, delay, account state change, or revived old certificate.

## Mechanism and cautions

CE can demote evidence accumulated slowly or after high recent volatility, but can also strongly favor a new one-day jump following a quiet period. It is not inherently anti-chasing. The 8 cases are already selected historical examples and cannot establish or refute aggregate validity.

600056 on 2022-03-03 and 03-30 has n=1 in both. CE changes 3.866596 to 1.142547 because the prior21 RMS changes 0.024630 to 0.083463 despite nearly equal current displacement. These cases show a volatility-scale issue, not a long-duration accumulation explanation.

All 103766 legal candidate rows have finite CE; original PVR-unknown 91 slots remain fixed. All 4040575 source observations have exact native credit/displacement/anchor/frozen-scale lineage checks; 4893 entire-prefix comparisons pass. Original baseline 27990 selected rows matches exactly. 15530 i_buy=false candidate rows remain, with no acceptance filter. No original indicator or account run.

## Fixed eight cases

      sid        day       CE  formation_n  variance_budget  source_displacement  source_credit  sigma_frozen  sigma_recent  source_m  original_CP_excess  original_PVR  original_rank  CE_rank  K membership
000506.SZ 2024-10-15 1.464544          9.0         0.017831             0.195567       0.199818      0.071637      0.041548  0.707307            1.220877     65.333293             25        4 20      added
002385.SZ 2022-03-04 0.839527          4.0         0.005069             0.059772       0.067051      0.026387      0.034351  1.246229            1.013013     62.151025             12       11 15       both
300182.SZ 2022-01-04 1.003142          5.0         0.009202             0.096228       0.108149      0.032115      0.042189  1.155139            1.339998     79.096103             42      112 20    neither
600056.SH 2022-03-03 3.866596          1.0         0.000607             0.095236       0.142752      0.010198      0.024630  1.498933            4.176177     88.869195              1        5 20       both
600056.SH 2022-03-30 1.142547          1.0         0.006966             0.095360       0.101946      0.020974      0.083463  1.069065            2.033256     95.833054              1       38 20    removed
600606.SH 2022-03-22 1.903222          3.0         0.001855             0.081974       0.104239      0.017629      0.024623  1.374243            2.079485     62.632838              8        3 14       both
601607.SH 2022-03-24 2.179518          1.0         0.001912             0.095310       0.141619      0.013172      0.043730  1.485877            3.235895     86.098531              1        4 12       both
688582.SH 2024-07-29 0.939625          3.0         0.003970             0.059206       0.064423      0.024736      0.035378  1.019007            1.070392     62.526754             15       13 16       both

## Daily budget contributions

      sid   case_day        day         r        m  delta_frontier  original_credit_increment  sigma_recent  variance_contribution  variance_fraction  variance_budget  formation_n
000506.SZ 2024-10-15 2024-09-19  0.046884 1.060626        0.046884                   0.049726      0.045957               0.002112           0.118446         0.002112          1.0
000506.SZ 2024-10-15 2024-09-20  0.015152 1.048505        0.015152                   0.015887      0.046814               0.002192           0.122905         0.004304          2.0
000506.SZ 2024-10-15 2024-09-23  0.000000 1.000000        0.000000                   0.000000      0.045820               0.002099           0.117739         0.006403          3.0
000506.SZ 2024-10-15 2024-09-24 -0.007547 1.014251        0.000000                   0.000000      0.044960               0.002021           0.113360         0.008424          4.0
000506.SZ 2024-10-15 2024-09-25  0.051672 1.168955        0.044125                   0.051580      0.044847               0.002011           0.112795         0.010436          5.0
000506.SZ 2024-10-15 2024-09-26  0.007168 1.023934        0.007168                   0.007340      0.044937               0.002019           0.113246         0.012455          6.0
000506.SZ 2024-10-15 2024-09-27 -0.007168 1.026102        0.000000                   0.000000      0.043472               0.001890           0.105982         0.014345          7.0
000506.SZ 2024-10-15 2024-09-30  0.042260 1.195102        0.035091                   0.041938      0.041956               0.001760           0.098718         0.016105          8.0
000506.SZ 2024-10-15 2024-10-15  0.047147 0.707307        0.047147                   0.033347      0.041548               0.001726           0.096809         0.017831          9.0
002385.SZ 2022-03-04 2022-03-01  0.021506 1.007736        0.021506                   0.021673      0.036942               0.001365           0.269229         0.001365          1.0
002385.SZ 2022-03-04 2022-03-02  0.011751 1.049677        0.011751                   0.012335      0.036139               0.001306           0.257646         0.002671          2.0
002385.SZ 2022-03-04 2022-03-03 -0.008211 0.995993        0.000000                   0.000000      0.034904               0.001218           0.240341         0.003889          3.0
002385.SZ 2022-03-04 2022-03-04  0.034726 1.246229        0.026515                   0.033043      0.034351               0.001180           0.232784         0.005069          4.0
300182.SZ 2022-01-04 2021-12-28  0.006711 1.008098        0.006711                   0.006766      0.043232               0.001869           0.203107         0.001869          1.0
300182.SZ 2022-01-04 2021-12-29  0.009983 1.035240        0.009983                   0.010335      0.043099               0.001858           0.201866         0.003727          2.0
300182.SZ 2022-01-04 2021-12-30  0.042146 1.152562        0.042146                   0.048575      0.043115               0.001859           0.202010         0.005585          3.0
300182.SZ 2022-01-04 2021-12-31  0.004751 1.004552        0.004751                   0.004772      0.042855               0.001837           0.199584         0.007422          4.0
300182.SZ 2022-01-04 2022-01-04  0.032637 1.155139        0.032637                   0.037700      0.042189               0.001780           0.193432         0.009202          5.0
600056.SH 2022-03-03 2022-03-03  0.095236 1.498933        0.095236                   0.142752      0.024630               0.000607           1.000000         0.000607          1.0
600056.SH 2022-03-30 2022-03-30  0.095360 1.069065        0.095360                   0.101946      0.083463               0.006966           1.000000         0.006966          1.0
600606.SH 2022-03-22 2022-03-18  0.029705 1.091037        0.029705                   0.032409      0.024684               0.000609           0.328440         0.000609          1.0
600606.SH 2022-03-22 2022-03-21 -0.004890 0.993523        0.000000                   0.000000      0.025288               0.000639           0.344724         0.001249          2.0
600606.SH 2022-03-22 2022-03-22  0.057158 1.374243        0.052268                   0.071830      0.024623               0.000606           0.326836         0.001855          3.0
601607.SH 2022-03-24 2022-03-24  0.095310 1.485877        0.095310                   0.141619      0.043730               0.001912           1.000000         0.001912          1.0
688582.SH 2024-07-29 2024-07-25  0.033049 1.160267        0.033049                   0.038346      0.036633               0.001342           0.338016         0.001342          1.0
688582.SH 2024-07-29 2024-07-26  0.017166 0.985429        0.017166                   0.016916      0.037103               0.001377           0.346743         0.002719          2.0
688582.SH 2024-07-29 2024-07-29  0.008990 1.019007        0.008990                   0.009161      0.035378               0.001252           0.315241         0.003970          3.0

## Same-day membership counts

account        day  year   N  K  CE_known  CE_unknown  PVR_unknown  top_overlap  added
    PVR 2022-01-04  2022 155 20       155           0            0            4     16
    PVR 2022-03-03  2022  83 20        83           0            0           11      9
    PVR 2022-03-04  2022  15 15        15           0            0           15      0
    PVR 2022-03-22  2022  14 14        14           0            0           14      0
    PVR 2022-03-24  2022  12 12        12           0            0           12      0
    PVR 2022-03-30  2022  63 20        63           0            0            5     15
    PVR 2024-07-29  2024  16 16        16           0            0           16      0
    PVR 2024-10-15  2024  25 20        25           0            0           15      5

Four dates have N<=K: 2022-03-04/03-22/03-24 and 2024-07-29. Their selected members are identical despite changed ranks. 300182 2022-01-04 is outside both top20 (42 ->112), so its CE change does not affect membership.

## Predetermined positive and negative examples

Each of 2022-01-04/03-03/03-30: first three added by sealed CE order, and first three removed by original order. Chosen without labels, then all 18 displayed. Returns and MAEs are the original native-price 5/20-observation paths, not realized trade outcomes or account returns.

       day membership       sid  original_rank  CE_rank  formation_n  source_r  sigma_recent  original_CP_excess       CE      ret5     ret20      mae5     mae20
2022-01-04      added 000719.SZ            110        1          2.0  0.095068      0.012571            5.459371 5.360280  0.067059 -0.045882 -0.008235 -0.102353
2022-01-04      added 002987.SZ             49        2          1.0  0.095252      0.021629            1.727856 4.403846  0.056812  0.110590  0.000000  0.000000
2022-01-04      added 002157.SZ             96        3          2.0  0.056353      0.014962            1.650099 4.044535  0.049902 -0.298434 -0.001957 -0.298434
2022-01-04    removed 002246.SZ              1       28          1.0  0.095221      0.043285            2.837362 2.199880 -0.146928 -0.232413 -0.188780 -0.253785
2022-01-04    removed 002603.SZ              3       82          1.0  0.037551      0.026886            1.449418 1.396694  0.200983  0.029484 -0.039312 -0.039312
2022-01-04    removed 600664.SH              4       61          5.0  0.027780      0.016153            1.690458 1.547470 -0.008242 -0.126374 -0.046703 -0.170330
2022-03-03      added 600299.SH             80        3          2.0  0.094927      0.014311            3.361774 4.445257 -0.125097 -0.233100 -0.125097 -0.260295
2022-03-03      added 600415.SH             48        8          2.0  0.062003      0.015958            2.788642 3.069525 -0.055336 -0.005929 -0.116601 -0.116601
2022-03-03      added 603871.SH             25        9          1.0  0.095269      0.032404            1.820281 2.940070 -0.222796 -0.211613 -0.229677 -0.313978
2022-03-03    removed 000830.SZ              5       56          6.0  0.035575      0.025485            1.878846 0.986073 -0.054639  0.019920 -0.070006 -0.116107
2022-03-03    removed 601898.SH              6       22          2.0  0.041813      0.028812            1.358777 1.520878 -0.014474  0.064474 -0.021053 -0.146053
2022-03-03    removed 600428.SH              7       82         15.0  0.033834      0.020258            1.023351 0.529972 -0.117647 -0.127451 -0.117647 -0.200000
2022-03-30      added 300820.SZ             21        3          2.0  0.156329      0.040106            2.097745 2.936710 -0.097489 -0.210153 -0.097489 -0.365939
2022-03-30      added 603737.SH             27        4          1.0  0.095310      0.035395            1.243150 2.692781  0.032800 -0.133419  0.000000 -0.205906
2022-03-30      added 000786.SZ             24        5          1.0  0.077925      0.031040            1.196188 2.510510  0.061790 -0.030394  0.000000 -0.079826
2022-03-30    removed 600056.SH              1       38          1.0  0.095360      0.083463            2.033256 1.142547 -0.350628 -0.507911 -0.350628 -0.528851
2022-03-30    removed 002807.SZ              4       35          2.0  0.022586      0.015976            1.103301 1.223024  0.089330 -0.012407  0.000000 -0.032258
2022-03-30    removed 601512.SH              5       52          7.0  0.030221      0.020864            1.465281 0.768700  0.119912 -0.031903  0.000000 -0.103410

## Direct single-day-jump tilt check

       day     strategy   N  K  n1_count  n1_fraction   mean_n  median_n  mean_signal_log_r  median_signal_log_r  mean_signal_price_return  median_signal_price_return  mean_prior21_rms  mean_CE
2022-01-04 ORIGINAL_PVR 155 20        13     0.650000 2.000000       1.0           0.047734             0.039825                  0.049243                    0.040630          0.025490 1.996420
2022-01-04 CP_TIMING_CE 155 20        10     0.500000 1.650000       1.5           0.067846             0.072224                  0.070599                    0.074954          0.019519 3.418228
2022-03-03 ORIGINAL_PVR  83 20        10     0.500000 3.150000       1.5           0.062135             0.068875                  0.064514                    0.071302          0.025230 2.414962
2022-03-03 CP_TIMING_CE  83 20        11     0.550000 2.050000       1.0           0.080613             0.088784                  0.084113                    0.092846          0.024091 3.032382
2022-03-04 ORIGINAL_PVR  15 15         2     0.133333 7.200000       5.0           0.040156             0.040050                  0.041316                    0.040863          0.026583 1.284061
2022-03-04 CP_TIMING_CE  15 15         2     0.133333 7.200000       5.0           0.040156             0.040050                  0.041316                    0.040863          0.026583 1.284061
2022-03-22 ORIGINAL_PVR  14 14         2     0.142857 3.142857       3.0           0.048468             0.039472                  0.050102                    0.040262          0.028938 1.559026
2022-03-22 CP_TIMING_CE  14 14         2     0.142857 3.142857       3.0           0.048468             0.039472                  0.050102                    0.040262          0.028938 1.559026
2022-03-24 ORIGINAL_PVR  12 12         3     0.250000 2.833333       2.5           0.054048             0.060127                  0.056140                    0.061982          0.031461 1.665616
2022-03-24 CP_TIMING_CE  12 12         3     0.250000 2.833333       2.5           0.054048             0.060127                  0.056140                    0.061982          0.031461 1.665616
2022-03-30 ORIGINAL_PVR  63 20         6     0.300000 3.500000       2.5           0.048804             0.038684                  0.050485                    0.039479          0.028166 1.386186
2022-03-30 CP_TIMING_CE  63 20        16     0.800000 1.200000       1.0           0.075752             0.074567                  0.079085                    0.077418          0.031114 2.276881
2024-07-29 ORIGINAL_PVR  16 16         5     0.312500 4.625000       3.0           0.036664             0.022547                  0.037826                    0.022803          0.022924 1.658131
2024-07-29 CP_TIMING_CE  16 16         5     0.312500 4.625000       3.0           0.036664             0.022547                  0.037826                    0.022803          0.022924 1.658131
2024-10-15 ORIGINAL_PVR  25 20        10     0.500000 1.500000       1.5           0.052556             0.052790                  0.054399                    0.054208          0.059246 1.074083
2024-10-15 CP_TIMING_CE  25 20         7     0.350000 2.000000       2.0           0.050619             0.049557                  0.052373                    0.050809          0.054383 1.173866

## Limits

Current-survivor/static future-selected stock universe and non-PIT industry/market-cap sources remain. This is consumed development history, not out-of-sample. The entire pool evaluation remains paused. 2026 right censoring and missing labels must stay UNKNOWN. Daily next-open labels are not verified executable fills. Original root epoch literal None must be preserved with keep_default_na=False; root-identity sensitivity remains. No parameter sweep, new portfolio, threshold optimization, or strategy promotion.