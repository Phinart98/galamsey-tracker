from types import SimpleNamespace

import numpy as np
from rasterio.errors import RasterioIOError

from tracker import chips


def _item(name):
    return SimpleNamespace(assets={"scl": SimpleNamespace(href=f"{name}/scl"), "visual": SimpleNamespace(href=f"{name}/rgb")})


def test_a_scene_whose_file_cannot_be_read_is_skipped_not_fatal(monkeypatch):
    def read(href, bbox):
        if href.startswith("broken"):
            raise RasterioIOError("not recognized as being in a supported file format")
        if href.endswith("scl"):
            return np.full((1, 4, 4), 4, dtype=np.uint8)
        return np.full((3, 4, 4), 60, dtype=np.uint8)

    monkeypatch.setattr(chips, "_read", read)
    assert chips.scene(_item("broken"), []) is None
    assert chips.scene(_item("good"), []).shape == (4, 4, 3)
