#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build/app_template.html + build/map_<region>.svg + build/parts_<region>.js -> index.html

地域は build/map_*.svg から自動検出する（複数地域対応）。
各地域のタイトルは tools/make_map.py の REGIONS 定義から取得する。
"""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")

with open(os.path.join(HERE, "make_map.py"), encoding="utf-8") as f:
    make_map_src = f.read()

TITLE_RE = re.compile(r'"(\w+)":\s*\{\s*"title":\s*"([^"]+)"')
title_matches = TITLE_RE.findall(make_map_src)
TITLES = dict(title_matches)
DEFINED_ORDER = [key for key, _ in title_matches]

available = {
    os.path.basename(p)[len("map_"):-len(".svg")]
    for p in glob.glob(os.path.join(BUILD, "map_*.svg"))
}
if not available:
    raise SystemExit("build/map_*.svg が見つかりません。先に tools/make_map.py を実行してください。")
# REGIONS定義順を優先し、生成済み（build/map_*.svg がある）地域だけを採用する
region_keys = [k for k in DEFINED_ORDER if k in available]
region_keys += sorted(available - set(region_keys))  # 定義に無い分はアルファベット順で末尾に

with open(os.path.join(BUILD, "app_template.html"), encoding="utf-8") as f:
    tpl = f.read()

blocks = []
map_entries = []
for key in region_keys:
    with open(os.path.join(BUILD, f"map_{key}.svg"), encoding="utf-8") as f:
        svg = f.read().strip()
    with open(os.path.join(BUILD, f"parts_{key}.js"), encoding="utf-8") as f:
        parts_js = f.read().strip()

    assert "`" not in svg, f"{key}: SVG contains a backtick, template literal embedding would break"
    assert "${" not in svg, f"{key}: SVG contains ${{, template literal embedding would break"

    title = TITLES.get(key, key)
    blocks.append(f"const SVG_{key.upper()} = `{svg}`;\n{parts_js}")
    map_entries.append(
        f'  {{ id:"{key}", title:"{title}", svg:SVG_{key.upper()}, parts:MAP_PARTS_{key.upper()} }}'
    )

regions_js = "\n\n".join(blocks) + "\n\nconst MAPS = [\n" + ",\n".join(map_entries) + "\n];\n"

out = tpl.replace("__REGIONS_JS__", regions_js)

out_path = os.path.join(ROOT, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(out)

print(f"regions: {', '.join(region_keys)}")
print("wrote", out_path, len(out), "bytes")
