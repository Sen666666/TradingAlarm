"""Exact original market adapter plus frozen missing-date native cache input."""
import importlib.util,sys
import pandas as pd
from cohort_config import O,ORIGINAL_J
spec=importlib.util.spec_from_file_location('_extension_original_market_adapter',ORIGINAL_J/'market_adapter.py')
original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
canonical_root=original.canonical_root
class MarketAdapter(original.MarketAdapter):
    def _load_qual(self,sid):
        if sid in self._qual:return
        super()._load_qual(sid)
        extra=pd.read_parquet(self._source(O/'NATIVE_QUAL_EXTRA.parquet'),filters=[('sid','==',sid)]).set_index('day')
        assert not self._qual[sid].index.intersection(extra.index).size
        self._qual[sid]=pd.concat([self._qual[sid],extra]).sort_index()
        assert not self._qual[sid].index.has_duplicates
