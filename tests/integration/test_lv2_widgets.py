"""Zynthian widgets declared as zyngui:widget LV2 UIs, found through lilv (zynthian_lv2), and their hot reload.

A throw-away LV2_PATH holds a fake plugin (its TTL only: lilv doesn't need the binary to list UIs),
built-in widget bundles (inside ZYNGUI_BUILTIN_WIDGETS_DIR) and user widget bundles.
"""

import os
import types

import pytest

from tests.bootstrap import STUBBED_MODULES

# lilv's Python bindings only come from the OS package (python3-lilv, not on pip): when missing, the bootstrap
# stubs the module and these tests would run against a MagicMock.
pytestmark = [pytest.mark.integration,
              pytest.mark.skipif("lilv" in STUBBED_MODULES, reason="python3-lilv not installed (stubbed)")]

PLUGIN_URI = "urn:zyntest:plugin"
OTHER_PLUGIN_URI = "urn:zyntest:other"

PLUGIN_MANIFEST = """\
@prefix lv2:  <http://lv2plug.in/ns/lv2core#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix doap: <http://usefulinc.com/ns/doap#> .

<{uri}> a lv2:Plugin ; lv2:binary <plugin.so> ; doap:name "{name}" .
"""

WIDGET_MANIFEST = """\
@prefix ui:     <http://lv2plug.in/ns/extensions/ui#> .
@prefix zyngui: <http://zynthian.org/ns/lv2/zyngui#> .

{triples}

<{ui_uri}> a zyngui:widget ; ui:binary <{module}> ; zyngui:apiVersion {api} .
"""

WIDGET_MODULE = """\
VERSION = {version}

class {cls}:
    def __init__(self, parent):
        self.parent = parent
        self.destroyed = False

    def destroy(self):
        self.destroyed = True
"""


@pytest.fixture
def lv2(tmp_path, monkeypatch):
    """zynthian_lv2 working on a private LV2_PATH: tmp/system (plugins + built-in widgets) and tmp/user."""
    from zyngine import zynthian_lv2 as z

    system = tmp_path / "system"
    user = tmp_path / "user"
    for d in (system, user):
        d.mkdir()
    for uri, name in ((PLUGIN_URI, "Zyntest"), (OTHER_PLUGIN_URI, "Other")):
        bundle = system / f"{name.lower()}.lv2"
        bundle.mkdir()
        (bundle / "manifest.ttl").write_text(PLUGIN_MANIFEST.format(uri=uri, name=name))

    monkeypatch.setenv("LV2_PATH", f"{system}:{user}")
    monkeypatch.setattr(z, "LV2_STAMP_FILE", str(tmp_path / "lv2.stamp"))
    monkeypatch.setattr(z, "ZYNGUI_BUILTIN_WIDGETS_DIR", str(system))
    z.init_lilv()
    yield types.SimpleNamespace(z=z, system=system, user=user, tmp=tmp_path)
    monkeypatch.undo()
    z.init_lilv()


def add_widget(where, name, plugin_uris, api=1, version=1):
    """Create a widget extension bundle <where>/<name>-zyngui.lv2 for the plugins. Returns the module path."""
    bundle = where / f"{name}-zyngui.lv2"
    bundle.mkdir()
    module = f"zynthian_widget_{name}.py"
    ui_uri = f"urn:zyntest:widget:{where.name}:{name}"
    triples = "\n".join(f"<{uri}> ui:ui <{ui_uri}> ." for uri in plugin_uris)
    (bundle / "manifest.ttl").write_text(WIDGET_MANIFEST.format(triples=triples, ui_uri=ui_uri, module=module, api=api))
    (bundle / module).write_text(WIDGET_MODULE.format(version=version, cls=f"zynthian_widget_{name}"))
    return str(bundle / module)


def bump_mtime(path):
    """Make sure a modification time changes, even on filesystems with coarse timestamps."""
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


# --- discovery --------------------------------------------------------------------------------------------------
def test_plugin_without_widget_has_none(lv2):
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI) is None
    assert lv2.z.get_plugin_zyngui_widget("urn:zyntest:not-installed") is None


def test_widget_from_extension_bundle_is_found(lv2):
    fpath = add_widget(lv2.system, "builtin", [PLUGIN_URI])
    lv2.z.init_lilv()
    w = lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)
    assert w["fpath"] == fpath
    assert w["api_version"] == 1
    assert w["user"] is False


def test_one_bundle_can_serve_several_plugins(lv2):
    fpath = add_widget(lv2.system, "shared", [PLUGIN_URI, OTHER_PLUGIN_URI])
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)["fpath"] == fpath
    assert lv2.z.get_plugin_zyngui_widget(OTHER_PLUGIN_URI)["fpath"] == fpath


def test_user_widget_wins_over_builtin(lv2):
    add_widget(lv2.system, "builtin", [PLUGIN_URI])
    user_fpath = add_widget(lv2.user, "mine", [PLUGIN_URI])
    lv2.z.init_lilv()
    w = lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)
    assert w["fpath"] == user_fpath
    assert w["user"] is True


def test_widget_needing_a_newer_api_is_ignored(lv2):
    builtin_fpath = add_widget(lv2.system, "builtin", [PLUGIN_URI])
    add_widget(lv2.user, "future", [PLUGIN_URI], api=lv2.z.ZYNGUI_WIDGET_API_VERSION + 1)
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)["fpath"] == builtin_fpath


def test_widget_with_missing_module_is_ignored(lv2):
    fpath = add_widget(lv2.user, "broken", [PLUGIN_URI])
    os.remove(fpath)
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI) is None


# --- cache & change detection -------------------------------------------------------------------------------
def test_lookups_are_cached(lv2, monkeypatch):
    calls = []
    find = lv2.z._find_plugin_zyngui_widget
    monkeypatch.setattr(lv2.z, "_find_plugin_zyngui_widget", lambda uri: calls.append(uri) or find(uri))
    lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)
    lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)
    assert calls == [PLUGIN_URI]


def test_no_change_means_no_reload(lv2):
    generation = lv2.z.lv2_generation
    assert lv2.z.check_lv2_changes() is False
    assert lv2.z.lv2_generation == generation


def test_new_widget_bundle_is_detected(lv2):
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI) is None  # cached as "no widget"
    generation = lv2.z.lv2_generation
    fpath = add_widget(lv2.user, "new", [PLUGIN_URI])
    bump_mtime(lv2.user)
    assert lv2.z.check_lv2_changes() is True
    assert lv2.z.lv2_generation == generation + 1
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)["fpath"] == fpath


def test_removed_widget_bundle_is_detected(lv2):
    import shutil
    add_widget(lv2.user, "gone", [PLUGIN_URI])
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI) is not None
    shutil.rmtree(lv2.user / "gone-zyngui.lv2")
    bump_mtime(lv2.user)
    assert lv2.z.check_lv2_changes() is True
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI) is None


def test_stamp_file_forces_reload(lv2):
    """Updates inside an existing bundle don't change LV2_PATH folders: installers touch the stamp file"""
    stamp = lv2.tmp / "lv2.stamp"
    stamp.write_text("")
    lv2.z.check_lv2_changes()
    generation = lv2.z.lv2_generation
    bump_mtime(stamp)
    assert lv2.z.check_lv2_changes() is True
    assert lv2.z.lv2_generation == generation + 1


# --- widget module cache in the control screen ------------------------------------------------------------------
@pytest.fixture
def control():
    """Just the state load_widget_module / destroy_widgets use, without building the Tk screen."""
    from zyngui.zynthian_gui_control import zynthian_gui_control as cls
    fake = types.SimpleNamespace(modules={}, widgets={}, current_widget=None, hidden=0)
    fake.hide_widgets = lambda: setattr(fake, "hidden", fake.hidden + 1)
    fake.destroy_widgets = lambda path: cls.destroy_widgets(fake, path)
    fake.load_widget_module = lambda path: cls.load_widget_module(fake, path)
    return fake


def test_widget_module_is_loaded_once(control, tmp_path):
    fpath = add_widget(tmp_path, "w", [PLUGIN_URI])
    module = control.load_widget_module(fpath)
    assert module.VERSION == 1
    assert control.load_widget_module(fpath) is module


def test_updated_widget_module_is_reloaded_and_old_instances_destroyed(control, tmp_path):
    fpath = add_widget(tmp_path, "w", [PLUGIN_URI])
    module = control.load_widget_module(fpath)
    widget = module.zynthian_widget_w(control)
    widget.zyngui_module_path = fpath
    control.widgets["w"] = widget
    control.current_widget = widget

    with open(fpath, "w") as f:
        f.write(WIDGET_MODULE.format(version=2, cls="zynthian_widget_w"))
    bump_mtime(fpath)
    new_module = control.load_widget_module(fpath)

    assert new_module.VERSION == 2
    assert widget.destroyed
    assert "w" not in control.widgets
    assert control.hidden == 1


def test_broken_widget_module_returns_none(control, tmp_path):
    fpath = tmp_path / "zynthian_widget_bad.py"
    fpath.write_text("this is not python\n")
    assert control.load_widget_module(str(fpath)) is None
    assert control.load_widget_module(str(tmp_path / "zynthian_widget_missing.py")) is None


def test_widget_help_page_is_returned(lv2):
    fpath = add_widget(lv2.user, "helped", [PLUGIN_URI])
    bundle = os.path.dirname(fpath)
    manifest = os.path.join(bundle, "manifest.ttl")
    with open(manifest) as f:
        ttl = f.read()
    with open(manifest, "w") as f:
        f.write(ttl.replace("zyngui:apiVersion 1 .", "zyngui:apiVersion 1 ; zyngui:help <help.html> ."))
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)["help"] == os.path.join(bundle, "help.html")


def test_widget_without_help_page(lv2):
    add_widget(lv2.user, "nohelp", [PLUGIN_URI])
    lv2.z.init_lilv()
    assert lv2.z.get_plugin_zyngui_widget(PLUGIN_URI)["help"] is None
