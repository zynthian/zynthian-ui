"""Every real snapshot we can find must convert to the current schema.

Sources: the public example snapshots of the zynthian-data repo (``../zynthian-data`` or $ZYNTHIAN_TEST_DATA_REPO;
CI checks out just that folder) and any directories in
``ZYNTHIAN_TEST_SNAPSHOT_DIRS`` (os.pathsep separated), e.g. your own ``zynthian-my-data/snapshots``. Files are only
read; nothing is copied into the repository.
"""

import json
import os
from pathlib import Path

import pytest

from tests.bootstrap import zynthian_data_snapshots

pytestmark = pytest.mark.integration


def snapshot_files():
    dirs = [d for d in (zynthian_data_snapshots(),) if d]
    dirs += [Path(d) for d in os.environ.get("ZYNTHIAN_TEST_SNAPSHOT_DIRS", "").split(os.pathsep) if d]
    files = []
    for d in dirs:
        if d.is_dir():
            files += sorted(d.rglob("*.zss"))
    return files


FILES = snapshot_files()


@pytest.fixture
def converter(state_manager):
    from zyngine.zynthian_legacy_snapshot import zynthian_legacy_snapshot
    return zynthian_legacy_snapshot()          # no state manager: steps that need one (V1, V3) are skipped


@pytest.mark.skipif(not FILES, reason="no snapshot corpus found (../zynthian-data, ZYNTHIAN_TEST_DATA_REPO or ZYNTHIAN_TEST_SNAPSHOT_DIRS)")
@pytest.mark.parametrize("path", FILES, ids=[f.name for f in FILES])
def test_snapshot_converts_to_the_current_schema(converter, path):
    from zyngine.zynthian_legacy_snapshot import SNAPSHOT_SCHEMA_VERSION
    original = json.loads(path.read_text())
    state = converter.convert_file(str(path))
    assert state is not None, "conversion failed"
    assert isinstance(state.get("chains"), dict) and isinstance(state.get("zs3"), dict)
    assert "zs3-0" in state["zs3"]
    json.dumps(state)                                     # still serialisable
    if original.get("schema_version", 0) == SNAPSHOT_SCHEMA_VERSION:
        assert state == original                          # already current: untouched
