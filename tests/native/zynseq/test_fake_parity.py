"""The recording fake of libzynseq (tests/fakes/native.py) must report what the real library reports."""

import ctypes

import pytest

from tests.fakes.native import _DEFAULT_RETURNS

pytestmark = [pytest.mark.native, pytest.mark.jack]

FAKE = _DEFAULT_RETURNS["libzynseq.so"]
RESTYPES = {"getTempo": ctypes.c_double, "getPPQN": ctypes.c_uint32, "getBpb": ctypes.c_uint8}


@pytest.mark.parametrize("name", sorted(RESTYPES))
def test_fake_default_matches_the_real_library(seq, name):
    getattr(seq, name).restype = RESTYPES[name]
    assert getattr(seq, name)() == FAKE[name]
