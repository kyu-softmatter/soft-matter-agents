Legacy samples root for `tests/server/test_api_map.py` (T-102): one sample with a 4x scan
(`scan4x_*/scan.json`, boxes derived from its hole and margin) and a brightfield sample map
(`sample_map_*/summary.json` with recorded boxes, `mosaic.json` in stage orientation). The
test writes `mosaic.npy` itself so no binary file is kept here. Sample events (hole fit,
boundary, flags, candidates) are written by the test into a temporary records store.
