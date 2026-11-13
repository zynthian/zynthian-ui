# -*- coding: utf-8 -*-
"""Test double for the ``zyncoder.zyncore`` ctypes wrapper.

The real module loads ``libzyncore.so`` (needs the Zynthian hardware/JACK
stack). Production code does ``from zyncoder.zyncore import lib_zyncore``,
which binds the object at import time, so the fake must be installed in
``sys.modules`` *before* any ``zyngine`` module is imported. ``conftest.py``
does that.

``FakeZyncore`` answers any attribute with a recording callable:

    lib_zyncore.set_midi_filter_event_ignore(9, 0, 60)
    assert zyncore.calls_to("set_midi_filter_event_ignore") == [(9, 0, 60)]

Default return value is ``0`` (``b""`` / ``0.0`` if the wrapper set a ``c_char_p`` / ``c_float`` ``restype``). Override with ``zyncore.set_return(name, value)``
(a value, or a callable receiving the call args).
"""

import ctypes
from types import ModuleType


class FakeFunction:
    """Callable stand-in for a ctypes function; records calls."""

    def __init__(self, owner, name):
        # Use object.__setattr__-free plain attrs; ctypes-style attributes
        # (restype, argtypes, errcheck) can be assigned freely by callers.
        self._owner = owner
        self._name = name

    def _default_return(self):
        """Default result, honouring the ``restype`` the wrapper assigned (as ctypes would)."""
        restype = self.__dict__.get("restype")
        if restype is ctypes.c_char_p:
            return b""
        if restype in (ctypes.c_float, ctypes.c_double):
            return 0.0
        return 0

    def __call__(self, *args):
        self._owner.log.append((self._name, args))
        if self._name in self._owner.returns:
            ret = self._owner.returns[self._name]
            return ret(*args) if callable(ret) else ret
        return self._default_return()

    def __repr__(self):
        return f"<FakeFunction {self._name}>"


# Values of the C constants that Python reads at *import* time (zynthian_chain_manager does
# ``NUM_ZMOP_CHAINS = lib_zyncore.zmop_get_num_chains()`` etc.). Kept in sync with
# zyncoder/zynmidirouter.h by tests/unit/test_fake_zyncore.py::test_router_constants_match_header.
ROUTER_CONSTANTS = {
    "zmop_get_num_chains": 17,   # NUM_ZMOP_CHAINS
    "zmip_get_num_devs": 24,     # number of device inputs (ZMIP_DEV0..DEV23)
    "zmop_get_num_devs": 24,     # NUM_ZMOP_DEVS
    "zmip_get_seq_index": 24,    # ZMIP_SEQ
    "zmip_get_step_index": 25,   # ZMIP_STEP
    "zmip_get_int_index": 26,    # ZMIP_FAKE_INT
    "zmip_get_ctrl_index": 27,   # ZMIP_CTRL
    "zmop_get_mod_index": 16,    # ZMOP_MOD
    "zmop_get_step_index": 17,   # ZMOP_STEP
}


class FakeZyncore:
    DEFAULT_RETURNS = ROUTER_CONSTANTS

    def __init__(self):
        self.log = []        # [(function name, args tuple), ...] in call order
        self.returns = {}    # name -> value | callable(*args)
        self._funcs = {}
        self._apply_defaults()

    def _apply_defaults(self):
        self.returns.update(self.DEFAULT_RETURNS)

    # -- attribute access -------------------------------------------------
    def __getattr__(self, name):
        # Only called for attributes not found normally.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        funcs = self.__dict__.setdefault("_funcs", {})
        if name not in funcs:
            funcs[name] = FakeFunction(self, name)
        return funcs[name]

    # -- test helpers -----------------------------------------------------
    def reset_fake(self):
        """Forget calls and configured return values (ctypes-style ``restype``/``argtypes`` that the
        wrappers assigned at import time are kept - they are part of the library's "ABI").

        Named ``reset_fake`` (not ``reset``) because libzynmixer exports a C function ``reset``.
        Helper names must never shadow a real C symbol: check with
        ``nm -D --defined-only build/*.so`` before adding one.
        """
        self.log.clear()
        self.returns.clear()
        self._apply_defaults()

    def fn(self, name):
        """The fake function called ``name`` - use if a C symbol ever collides with a helper name."""
        return self.__getattr__(name)

    def set_return(self, name, value):
        self.returns[name] = value

    def calls_to(self, name):
        """Args tuples of every call to ``name``, in order."""
        return [args for n, args in self.log if n == name]

    def call_count(self, name=None):
        return len(self.log) if name is None else len(self.calls_to(name))

    def names_called(self):
        return {n for n, _ in self.log}


def build_module(fake):
    """Create a drop-in replacement for the ``zyncoder.zyncore`` module."""
    mod = ModuleType("zyncoder.zyncore")
    mod.lib_zyncore = fake
    mod.lib_zyncore_init = lambda: fake
    mod.get_lib_zyncore = lambda: fake
    return mod
