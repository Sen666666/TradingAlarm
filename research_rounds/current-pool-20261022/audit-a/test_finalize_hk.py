"""Synthetic data-preservation tests, not historical performance evidence."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from finalize_hk import normalize_hk,merge_hk,unit_crosscheck,FROZEN_HELPER,raw_observations
from test_finalize_a import fixture,encoded,sha


def frame(volume=None,close=10.):
    return normalize_hk(pd.DataFrame([dict(date='2026-10-22',open=10.,high=11.,low=9.,close=close,volume=volume,amount=None if volume is None else volume*10.)]),'00001.HK','synthetic')


class HKTest(unittest.TestCase):
    def test_missing_volume_preserves_price_clock(self):
        x=frame();self.assertTrue(x.price_eligible.iloc[0]);self.assertFalse(x.volume_eligible.iloc[0]);self.assertTrue(np.isnan(x.volume.iloc[0]))
        spec=importlib.util.spec_from_file_location('frozen_mask_test',FROZEN_HELPER);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.assertEqual(len(mod.eligible_prices(x.rename(columns={'trade_date':'date'}))),1)

    def test_zero_volume_also_preserves_price(self):
        x=frame(0.);self.assertTrue(x.price_eligible.iloc[0]);self.assertFalse(x.volume_eligible.iloc[0])

    def test_geometry_does_not_enter_price_clock(self):
        x=frame(100.,close=8.);self.assertFalse(x.price_eligible.iloc[0]);self.assertTrue(x.source_invalid.iloc[0]);self.assertEqual(len(x),1)

    def test_missing_volume_equal_overlap_kept(self):
        merged,conflicts,status=merge_hk(frame(),frame(),'00001.HK');self.assertTrue(status['accepted']);self.assertFalse(conflicts);self.assertTrue(np.isnan(merged.volume.iloc[0]))

    def test_new_finite_volume_does_not_silently_overwrite_missing(self):
        merged,conflicts,status=merge_hk(frame(),frame(100.),'00001.HK');self.assertFalse(status['accepted']);self.assertTrue(conflicts);self.assertTrue(np.isnan(merged.volume.iloc[0]))

    def test_arithmetic_does_not_claim_official_unit_definition(self):
        x=unit_crosscheck(frame(100.));self.assertEqual(x['median_amount_per_volume_over_close'],1.);self.assertFalse(x['official_unit_definition_certified']);self.assertFalse(x['conversion_applied'])

    def test_parser_dropped_raw_observation_recovered_without_fake_price(self):
        with tempfile.TemporaryDirectory() as d:
            path,attempt=fixture(Path(d));records=json.loads((attempt/'decoded.json').read_text());records[0].pop('8')
            data=encoded(records);(attempt/'decoded.json').write_bytes(data)
            cp_path=path.parent.parent/'checkpoints'/path.name;cp=json.loads(cp_path.read_text());cp['pages'][0]['decoded_sha256']=sha(data);cp_path.write_bytes(encoded(cp))
            x=json.loads(path.read_text());x['pages']=cp['pages'];x['bars']=[];x['rows_dropped_by_parser']=1;path.write_bytes(encoded(x))
            raw,*_=raw_observations(path);self.assertEqual(len(raw),1);self.assertTrue(pd.isna(raw.high.iloc[0]));self.assertEqual(raw.close.iloc[0],10.5)


if __name__=='__main__':unittest.main(verbosity=2)
