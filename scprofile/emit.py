"""The one write path, holding the string encoding that keeps the object readable elsewhere."""
from __future__ import annotations


class classic_string_encoding:
    """Write string columns as HDF5 string DATASETS, not nullable-string groups.

    On pandas >= 3 a string column cannot be held as `object`, and anndata >= 0.11 writes the new
    dtype as a nullable string: a group of `values` + `mask`. The result is valid AnnData, round
    trips through anndata perfectly, and is unreadable by anything else - a viewer reports a
    property access on undefined, which points nowhere near the cause.

    Scoped and restored: this is a global on the anndata module, and this package has no business
    changing how objects written elsewhere in the caller's process are stored.
    """

    def __init__(self):
        self._prev, self._had = None, False

    def __enter__(self):
        try:
            import anndata as ad
            self._prev = ad.settings.allow_write_nullable_strings
            ad.settings.allow_write_nullable_strings = False
            self._had = True
        except Exception:                                                 # noqa: BLE001
            self._had = False
        return self

    def __exit__(self, *exc):
        if self._had:
            import anndata as ad
            ad.settings.allow_write_nullable_strings = self._prev
        return False


def write_h5ad(adata, path, **kw):
    """The only write in this package, so the guarantee is held in one place."""
    with classic_string_encoding():
        adata.write_h5ad(str(path), **kw)
    return path
