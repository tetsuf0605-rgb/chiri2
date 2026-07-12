#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build/app_template.html + build/map_sea.svg + build/parts_sea.js -> index.html"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
BUILD = os.path.join(ROOT, "build")

with open(os.path.join(BUILD, "app_template.html"), encoding="utf-8") as f:
    tpl = f.read()
with open(os.path.join(BUILD, "map_sea.svg"), encoding="utf-8") as f:
    svg = f.read().strip()
with open(os.path.join(BUILD, "parts_sea.js"), encoding="utf-8") as f:
    parts_js = f.read().strip()

assert "`" not in svg, "SVG contains a backtick, template literal embedding would break"
assert "${" not in svg, "SVG contains ${, template literal embedding would break"

out = tpl.replace("__SVG_SEA__", svg).replace("__PARTS_SEA__", parts_js)

out_path = os.path.join(ROOT, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(out)

print("wrote", out_path, len(out), "bytes")
