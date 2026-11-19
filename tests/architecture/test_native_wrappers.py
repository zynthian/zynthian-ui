"""The ctypes wrappers of zynlibs only call functions their C/C++ library defines.

ctypes resolves a library function when it is first called: a misspelt or removed name (``togglePfl`` for
``togglePFL``) only fails at that call, with an AttributeError the callers often swallow. Static check: every
``<lib>.name`` used in a wrapper must be a function defined (with a body) in the library's sources.
"""

import re

import pytest

from tests.bootstrap import REPO_ROOT

# wrapper: (attribute holding the CDLL, library sources)
WRAPPERS = {
    "zynlibs/zynmixer/zynmixer.py": ("lib_zynmixer", ["zynlibs/zynmixer/mixer.c"]),
    "zynlibs/zynseq/zynseq.py": ("libseq", ["zynlibs/zynseq/*.cpp", "zynlibs/zynseq/zynseq.h"]),
    "zynlibs/zynsmf/zynsmf.py": ("libsmf", ["zynlibs/zynsmf/*.cpp"]),
}

# CDLL attributes that aren't library functions (or appear in comments)
NOT_FUNCTIONS = {"_handle", "functionName"}

# Known missing functions, still called: fixing one fails this test until it is removed here.
KNOWN_MISSING = {
    # OSC feedback was removed from mixer.c; the /MIXER/ HEARTBEAT and SETUP registration fails
    "zynlibs/zynmixer/zynmixer.py": {"addOscClient", "removeOscClient"},
    # zynseq's own MIDI learn (enable_midi_learn / disable_midi_learn) and load(): not used, not in the library
    "zynlibs/zynseq/zynseq.py": {"enableMidiLearn", "load"},
}

DEFINITION = re.compile(r"^[A-Za-z_][\w \t\*&:<>,]*?\b(\w+)\s*\([^;{]*\)\s*(?:const\s*)?\{", re.M)


def defined_functions(patterns):
    names = set()
    for pattern in patterns:
        for path in sorted(REPO_ROOT.glob(pattern)):
            names |= set(DEFINITION.findall(path.read_text(errors="replace")))
    return names


@pytest.mark.parametrize("wrapper", sorted(WRAPPERS))
def test_wrapper_calls_only_defined_functions(wrapper):
    attr, sources = WRAPPERS[wrapper]
    used = set(re.findall(rf"\b{attr}\.(\w+)", (REPO_ROOT / wrapper).read_text()))
    used -= NOT_FUNCTIONS
    used -= {"restype", "argtypes"}
    missing = used - defined_functions(sources)
    assert missing == KNOWN_MISSING.get(wrapper, set())


DECLARATION = re.compile(r"^[A-Za-z_][\w \t\*&:<>,]*?\b(\w+)\s*\([^;{]*\)\s*;", re.M)

# library header: the sources defining its functions
HEADERS = {
    "zynlibs/zynmixer/mixer.h": ["zynlibs/zynmixer/mixer.c"],
    "zynlibs/zynseq/zynseq.h": ["zynlibs/zynseq/*.cpp", "zynlibs/zynseq/zynseq.h"],
    "zynlibs/zynsmf/zynsmf.h": ["zynlibs/zynsmf/*.cpp"],
}


@pytest.mark.parametrize("header", sorted(HEADERS))
def test_header_declares_only_defined_functions(header):
    """A declared function the library doesn't define is an undefined symbol for its ctypes users"""
    declared = set(DECLARATION.findall((REPO_ROOT / header).read_text()))
    assert declared - defined_functions(HEADERS[header]) == set()
