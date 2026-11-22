#!/usr/bin/env python3
"""Runs on the zynthian (sent by zyn_device.sh over ssh), using zynthian-ui's own code.

  python3 - indb <plugin_uri>    exit 0 if the plugin is already in the engines DB, 1 if not
  python3 - enable <plugin_uri>  enable it in the engines DB (regenerate_engines_db.sh adds new plugins disabled)
"""

import importlib.util
import logging
import os
import sys

logging.disable(logging.INFO)

ui_dir = os.environ["ZYNTHIAN_UI_DIR"]
spec = importlib.util.spec_from_file_location("zl", f"{ui_dir}/zyngine/zynthian_lv2.py")
zl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zl)

cmd, uri = sys.argv[1], sys.argv[2]
keys = [key for key, info in zl.engines.items() if info.get("URL") == uri]
if cmd == "indb":
    sys.exit(0 if keys else 1)
if not keys:
    print(f"ERROR: <{uri}> isn't in the engines DB: check that the bundle is in LV2_PATH and loads (lv2info)")
    sys.exit(1)
for key in keys:
    info = zl.engines[key]
    if info.get("ENABLED"):
        print(f"{key}: already enabled ({info.get('TYPE')} / {info.get('CAT')})")
        continue
    info["ENABLED"] = True
    info["EDIT"] = max(1, info.get("EDIT", 0))  # user edit: regenerations keep it enabled
    zl.save_engines()
    print(f"{key}: enabled ({info.get('TYPE')} / {info.get('CAT')})")
