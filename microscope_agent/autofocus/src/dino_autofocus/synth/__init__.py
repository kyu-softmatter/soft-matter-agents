"""Synthetic widefield-fluorescence focal series, for training and evaluating the head.

Vendored from psf-autofocus ``afocus`` at dc63189 (plus the uncommitted ``--pad``
option of ``make_dataset.py``) so this repo no longer needs the sibling checkout.
Only the generator is here: ``optics`` (PSF models, Zernike, instrument configs),
``sim`` (geometry, scene randomisation, rendering, camera, dataset shards),
``features`` (the edge/radial descriptors stored in each shard) and
``models.preprocess`` (the fixed conditioning scale).  The psf-autofocus networks,
estimators and search policies were left behind.

    uv run python scripts/make_dataset.py --out data/k100x \
        --system-config configs/kinetix_100x_oil.yaml
"""
