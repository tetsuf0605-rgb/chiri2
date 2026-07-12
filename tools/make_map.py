#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chiri2 白地図生成スクリプト（方式A: Natural Earth 50m → SVG）

使い方:
    python tools/make_map.py sea

出力:
    build/map_sea.svg    ... 白地図SVG（index.htmlに焼き込む）
    build/parts_sea.js   ... 問題データ MAP_PARTS_SEA（index.htmlに焼き込む）
    build/report_sea.txt ... 生成レポート（島の割り当て結果・要確認項目）

依存: Python 3.8+ 標準ライブラリのみ。
初回のみネット接続が必要（Natural Earth GeoJSONをDLし tools/cache に保存。2回目以降はキャッシュ使用）。
データはパブリックドメイン（Natural Earth）。
"""
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
BUILD = os.path.join(HERE, "..", "build")

DATA_URLS = {
    "countries": [
        "https://raw.githubusercontent.com/martynafford/natural-earth-geojson/master/50m/cultural/ne_50m_admin_0_countries.json",
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson",
    ],
    "rivers": [
        "https://raw.githubusercontent.com/martynafford/natural-earth-geojson/master/50m/physical/ne_50m_rivers_lake_centerlines.json",
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_rivers_lake_centerlines.geojson",
    ],
}

# ============================================================
# 地域定義
#   mode: island = 該当ポリゴンをタグ付け＋マーカー
#         zone   = マーカーのみ（海・海峡・半島など面が無い/曖昧な対象）
#         city   = マーカー（都市）
#         river  = 河川ラインを描画＋マーカー
#         grid   = 緯線/経線を強調描画＋マーカー
#   check: True = 写真からの判読に自信が低い（訂正機能での確認推奨）
# ============================================================
REGIONS = {
    "sea": {
        "title": "東南アジア",
        "bbox": (90.0, -12.0, 145.0, 28.0),  # lon0, lat0, lon1, lat1
        "width": 700,
        "simplify_px": 0.6,
        "parts": [
            # --- 緯度・経度 ---
            {"id": "あ", "name": "北緯0度", "yomi": "", "alt": ["0度", "0", "赤道"], "kind": "緯度",
             "mode": "grid", "axis": "lat", "deg": 0, "lon": 92.0, "lat": 0.0},
            {"id": "い", "name": "北緯10度", "yomi": "", "alt": ["10度", "10"], "kind": "緯度",
             "mode": "grid", "axis": "lat", "deg": 10, "lon": 92.0, "lat": 10.0, "check": True},
            {"id": "う", "name": "東経100度", "yomi": "", "alt": ["100度", "100"], "kind": "経度",
             "mode": "grid", "axis": "lon", "deg": 100, "lon": 100.0, "lat": -10.5, "check": True},
            # --- 海・海峡・海溝 ---
            {"id": "え", "name": "アンダマン海", "yomi": "あんだまんかい", "alt": [], "kind": "海",
             "mode": "zone", "lon": 96.0, "lat": 10.0},
            {"id": "お", "name": "南シナ海", "yomi": "みなみしなかい", "alt": [], "kind": "海",
             "mode": "zone", "lon": 112.0, "lat": 13.0},
            {"id": "か", "name": "スンダ海溝", "yomi": "すんだかいこう", "alt": ["ジャワ海溝"], "kind": "海溝",
             "mode": "zone", "lon": 97.5, "lat": -6.0},
            {"id": "き", "name": "マラッカ海峡", "yomi": "まらっかかいきょう", "alt": [], "kind": "海峡",
             "mode": "zone", "lon": 100.3, "lat": 3.6},
            {"id": "く", "name": "ロンボク海峡", "yomi": "ろんぼくかいきょう", "alt": [], "kind": "海峡",
             "mode": "zone", "lon": 115.75, "lat": -8.75},
            {"id": "け", "name": "マカッサル海峡", "yomi": "まかっさるかいきょう", "alt": [], "kind": "海峡",
             "mode": "zone", "lon": 117.8, "lat": -1.0},
            {"id": "こ", "name": "フィリピン海溝", "yomi": "ふぃりぴんかいこう", "alt": [], "kind": "海溝",
             "mode": "zone", "lon": 127.3, "lat": 9.0},
            {"id": "さ", "name": "太平洋", "yomi": "たいへいよう", "alt": ["フィリピン海"], "kind": "海",
             "mode": "zone", "lon": 135.0, "lat": 18.0, "check": True},
            {"id": "し", "name": "アラフラ海", "yomi": "あらふらかい", "alt": [], "kind": "海",
             "mode": "zone", "lon": 135.0, "lat": -9.5},
            # --- 島 ---
            {"id": "す", "name": "ルソン島", "yomi": "るそんとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 121.2, "lat": 16.5},
            {"id": "せ", "name": "ミンダナオ島", "yomi": "みんだなおとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 124.8, "lat": 7.8},
            {"id": "そ", "name": "カリマンタン島", "yomi": "かりまんたんとう", "alt": ["ボルネオ島"], "kind": "島",
             "mode": "island", "lon": 114.0, "lat": 0.8},
            {"id": "た", "name": "スマトラ島", "yomi": "すまとらとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 101.8, "lat": -0.6},
            {"id": "ち", "name": "ジャワ島", "yomi": "じゃわとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 110.2, "lat": -7.4},
            {"id": "つ", "name": "バリ島", "yomi": "ばりとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 115.15, "lat": -8.37},
            {"id": "て", "name": "ティモール島", "yomi": "てぃもーるとう", "alt": [], "kind": "島",
             "mode": "island", "lon": 125.6, "lat": -9.2},
            # --- 半島・地峡・台地 ---
            {"id": "と", "name": "インドシナ半島", "yomi": "いんどしなはんとう", "alt": [], "kind": "半島",
             "mode": "zone", "lon": 104.0, "lat": 19.0},
            {"id": "な", "name": "マレー半島", "yomi": "まれーはんとう", "alt": [], "kind": "半島",
             "mode": "zone", "lon": 101.6, "lat": 5.8},
            {"id": "は", "name": "クラ地峡", "yomi": "くらちきょう", "alt": [], "kind": "地峡",
             "mode": "zone", "lon": 98.8, "lat": 10.4},
            {"id": "ひ", "name": "コラート台地", "yomi": "こらーとだいち", "alt": [], "kind": "台地",
             "mode": "zone", "lon": 102.8, "lat": 15.2},
            # --- 川 ---
            {"id": "に", "name": "エーヤワディー川", "yomi": "えーやわでぃーがわ", "alt": ["イラワジ川"], "kind": "川",
             "mode": "river", "match": ["irrawaddy", "ayeyarwady"], "lon": 95.3, "lat": 19.5},
            {"id": "ぬ", "name": "チャオプラヤ川", "yomi": "ちゃおぷらやがわ", "alt": ["メナム川"], "kind": "川",
             "mode": "river", "match": ["chao phraya"], "lon": 100.1, "lat": 15.5},
            {"id": "ね", "name": "メコン川", "yomi": "めこんがわ", "alt": [], "kind": "川",
             "mode": "river", "match": ["mekong"], "lon": 105.8, "lat": 15.0},
            {"id": "の", "name": "ホン川", "yomi": "ほんがわ", "alt": ["ソンコイ川", "紅河"], "kind": "川",
             "mode": "river", "match": ["song hong", "red (asia)", "yuan (red)"], "lon": 104.5, "lat": 22.3, "check": True},
            # --- 産地 a〜d ---
            {"id": "a", "name": "ビンタン島", "yomi": "びんたんとう", "alt": [], "kind": "島",
             "res": "ボーキサイト", "mode": "island", "lon": 104.45, "lat": 1.05},
            {"id": "b", "name": "バンカ島", "yomi": "ばんかとう", "alt": [], "kind": "島",
             "res": "すず", "mode": "island", "lon": 106.1, "lat": -2.3},
            {"id": "c", "name": "ブリトン島", "yomi": "ぶりとんとう", "alt": ["ビリトン島"], "kind": "島",
             "res": "すず", "mode": "island", "lon": 107.9, "lat": -2.87},
            {"id": "d", "name": "モルッカ諸島", "yomi": "もるっかしょとう", "alt": ["マルク諸島"], "kind": "諸島",
             "res": "香辛料", "mode": "zone", "lon": 127.5, "lat": -2.0},
            # --- 都市 1〜20 ---
            {"id": "1", "name": "ハノイ", "yomi": "はのい", "alt": [], "kind": "都市",
             "mode": "city", "lon": 105.85, "lat": 21.03},
            {"id": "2", "name": "ホンゲイ", "yomi": "ほんげい", "alt": ["ハロン"], "kind": "都市",
             "res": "炭田", "mode": "city", "lon": 107.08, "lat": 20.95},
            {"id": "3", "name": "ホーチミン", "yomi": "ほーちみん", "alt": ["サイゴン"], "kind": "都市",
             "mode": "city", "lon": 106.66, "lat": 10.78},
            {"id": "4", "name": "プノンペン", "yomi": "ぷのんぺん", "alt": [], "kind": "都市",
             "mode": "city", "lon": 104.92, "lat": 11.56},
            {"id": "5", "name": "ビエンチャン", "yomi": "びえんちゃん", "alt": [], "kind": "都市",
             "mode": "city", "lon": 102.60, "lat": 17.97},
            {"id": "6", "name": "ネーピードー", "yomi": "ねーぴーどー", "alt": ["ネピドー"], "kind": "都市",
             "mode": "city", "lon": 96.08, "lat": 19.75, "check": True},
            {"id": "7", "name": "ヤンゴン", "yomi": "やんごん", "alt": ["ラングーン"], "kind": "都市",
             "mode": "city", "lon": 96.16, "lat": 16.85},
            {"id": "8", "name": "バンコク", "yomi": "ばんこく", "alt": [], "kind": "都市",
             "mode": "city", "lon": 100.50, "lat": 13.75},
            {"id": "9", "name": "クアラルンプール", "yomi": "くあらるんぷーる", "alt": [], "kind": "都市",
             "mode": "city", "lon": 101.69, "lat": 3.14},
            {"id": "10", "name": "ジョホールバール", "yomi": "じょほーるばーる", "alt": ["ジョホールバル"], "kind": "都市",
             "mode": "city", "lon": 103.76, "lat": 1.49},
            {"id": "11", "name": "シンガポール", "yomi": "しんがぽーる", "alt": [], "kind": "都市",
             "mode": "city", "lon": 103.85, "lat": 1.29},
            {"id": "12", "name": "パレンバン", "yomi": "ぱれんばん", "alt": [], "kind": "都市",
             "mode": "city", "lon": 104.75, "lat": -2.99},
            {"id": "13", "name": "ジャカルタ", "yomi": "じゃかるた", "alt": [], "kind": "都市",
             "mode": "city", "lon": 106.85, "lat": -6.21},
            {"id": "14", "name": "バンドン", "yomi": "ばんどん", "alt": [], "kind": "都市",
             "mode": "city", "lon": 107.61, "lat": -6.91},
            {"id": "15", "name": "スラバヤ", "yomi": "すらばや", "alt": [], "kind": "都市",
             "mode": "city", "lon": 112.75, "lat": -7.25},
            {"id": "16", "name": "バンダルスリブガワン", "yomi": "ばんだるすりぶがわん", "alt": [], "kind": "都市",
             "mode": "city", "lon": 114.94, "lat": 4.89},
            {"id": "17", "name": "バギオ", "yomi": "ばぎお", "alt": ["ケソン"], "kind": "都市",
             "mode": "city", "lon": 120.59, "lat": 16.41, "check": True},
            {"id": "18", "name": "マニラ", "yomi": "まにら", "alt": [], "kind": "都市",
             "mode": "city", "lon": 120.98, "lat": 14.60},
            {"id": "19", "name": "ダバオ", "yomi": "だばお", "alt": [], "kind": "都市",
             "mode": "city", "lon": 125.61, "lat": 7.07},
            {"id": "20", "name": "ディリ", "yomi": "でぃり", "alt": [], "kind": "都市",
             "mode": "city", "lon": 125.57, "lat": -8.56},
        ],
    },
}

# ============================================================
# データ取得
# ============================================================

def fetch(kind):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, kind + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    last_err = None
    for url in DATA_URLS[kind]:
        try:
            print("downloading:", url)
            req = urllib.request.Request(url, headers={"User-Agent": "chiri2-map-builder"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read().decode("utf-8")
            json.loads(data)  # 検証
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            return json.loads(data)
        except Exception as e:  # noqa: BLE001
            print("  failed:", e)
            last_err = e
    raise SystemExit(f"{kind} のダウンロードに失敗しました: {last_err}")

# ============================================================
# 幾何ユーティリティ
# ============================================================

def polys_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def lines_of(geom):
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return geom["coordinates"]
    return []


def ring_bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_overlap(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def ring_area(ring):
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            xt = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < xt:
                inside = not inside
        j = i
    return inside


def clip_ring(ring, bbox):
    """Sutherland-Hodgman で矩形にクリップ"""
    x0, y0, x1, y1 = bbox

    def clip_edge(pts, inside, inter):
        out = []
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
                if not ib:
                    out.append(inter(a, b))
            elif ib:
                out.append(inter(a, b))
        return out

    def ix(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + t * (b[1] - a[1]))

    def iy(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), y)

    pts = [(p[0], p[1]) for p in ring]
    for inside, inter in (
        (lambda p: p[0] >= x0, lambda a, b: ix(a, b, x0)),
        (lambda p: p[0] <= x1, lambda a, b: ix(a, b, x1)),
        (lambda p: p[1] >= y0, lambda a, b: iy(a, b, y0)),
        (lambda p: p[1] <= y1, lambda a, b: iy(a, b, y1)),
    ):
        pts = clip_edge(pts, inside, inter)
        if len(pts) < 3:
            return []
    return pts


def clip_polyline(points, bbox):
    """Liang-Barsky で折れ線をクリップ。複数の折れ線を返す"""
    x0, y0, x1, y1 = bbox

    def clip_seg(a, b):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    return None
            else:
                t = q / p
                if p < 0:
                    if t > t1:
                        return None
                    if t > t0:
                        t0 = t
                else:
                    if t < t0:
                        return None
                    if t < t1:
                        t1 = t
        return ((a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy))

    lines = []
    cur = []
    for i in range(len(points) - 1):
        a = (points[i][0], points[i][1])
        b = (points[i + 1][0], points[i + 1][1])
        seg = clip_seg(a, b)
        if seg is None:
            if len(cur) >= 2:
                lines.append(cur)
            cur = []
            continue
        p, q = seg
        if not cur:
            cur = [p, q]
        elif abs(cur[-1][0] - p[0]) < 1e-9 and abs(cur[-1][1] - p[1]) < 1e-9:
            cur.append(q)
        else:
            if len(cur) >= 2:
                lines.append(cur)
            cur = [p, q]
    if len(cur) >= 2:
        lines.append(cur)
    return lines


def simplify(pts, tol):
    """Douglas-Peucker（スタック版）"""
    if len(pts) < 3 or tol <= 0:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        dmax, k = -1.0, -1
        for m in range(i + 1, j):
            px, py = pts[m]
            if l2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / l2
                t = max(0.0, min(1.0, t))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > dmax:
                dmax, k = d, m
        if dmax > tol:
            keep[k] = True
            stack.append((i, k))
            stack.append((k, j))
    return [p for p, f in zip(pts, keep) if f]

# ============================================================
# メイン
# ============================================================

def build(region_key):
    cfg = REGIONS[region_key]
    bbox = cfg["bbox"]
    x0, y0, x1, y1 = bbox
    width = cfg["width"]
    scale = width / (x1 - x0)
    height = round((y1 - y0) * scale)
    tol = cfg["simplify_px"]

    def proj(lon, lat):
        return ((lon - x0) * scale, (y1 - lat) * scale)

    def fmt_path(pts, close):
        d = []
        for i, (x, y) in enumerate(pts):
            d.append(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}")
        if close:
            d.append("Z")
        return "".join(d)

    report = []
    countries = fetch("countries")
    rivers = fetch("rivers")

    # --- 島パーツの割り当て（元の経緯度ポリゴンで判定） ---
    island_parts = [p for p in cfg["parts"] if p["mode"] == "island"]
    assign = {}  # (feature_i, poly_i) -> part
    for part in island_parts:
        best = None  # (area, fi, pi)
        for fi, feat in enumerate(countries.get("features", [])):
            for pi, poly in enumerate(polys_of(feat.get("geometry") or {})):
                outer = poly[0]
                bb = ring_bbox(outer)
                if not (bb[0] <= part["lon"] <= bb[2] and bb[1] <= part["lat"] <= bb[3]):
                    continue
                if point_in_ring(part["lon"], part["lat"], outer):
                    a = ring_area(outer)
                    if best is None or a < best[0]:
                        best = (a, fi, pi)
        if best is None:
            report.append(f"[警告] 島ポリゴン未検出 → マーカーのみ: {part['id']} {part['name']}")
        else:
            assign[(best[1], best[2])] = part
            report.append(f"[OK] 島割り当て: {part['id']} {part['name']} (面積 {best[0]:.3f}deg2)")

    # --- 陸地パス ---
    land_svg = []
    clip_bbox = bbox
    for fi, feat in enumerate(countries.get("features", [])):
        for pi, poly in enumerate(polys_of(feat.get("geometry") or {})):
            outer = poly[0]
            if not bbox_overlap(ring_bbox(outer), clip_bbox):
                continue
            sub_paths = []
            for ring in poly:  # outer + holes
                clipped = clip_ring(ring, clip_bbox)
                if len(clipped) < 3:
                    continue
                pts = simplify([proj(x, y) for x, y in clipped], tol)
                if len(pts) < 3:
                    continue
                sub_paths.append(fmt_path(pts, close=True))
            if not sub_paths:
                continue
            part = assign.get((fi, pi))
            attr = f' data-part="{part["id"]}"' if part else ""
            cls = "land part-shape" if part else "land"
            land_svg.append(f'<path class="{cls}"{attr} fill-rule="evenodd" d="{"".join(sub_paths)}"/>')

    # --- 河川 ---
    river_svg = []
    for part in [p for p in cfg["parts"] if p["mode"] == "river"]:
        matched = 0
        for feat in rivers.get("features", []):
            props = feat.get("properties") or {}
            names = " / ".join(
                str(props.get(k, "")) for k in ("name", "NAME", "name_en", "NAME_EN")
            ).lower()
            if not any(m in names for m in part["match"]):
                continue
            for line in lines_of(feat.get("geometry") or {}):
                for seg in clip_polyline(line, clip_bbox):
                    pts = simplify([proj(x, y) for x, y in seg], tol)
                    if len(pts) < 2:
                        continue
                    river_svg.append(
                        f'<path class="river part-shape" data-part="{part["id"]}" d="{fmt_path(pts, close=False)}"/>'
                    )
                    matched += 1
        if matched == 0:
            report.append(f"[警告] 河川ライン未検出 → マーカーのみ: {part['id']} {part['name']}（match={part['match']}）")
        else:
            report.append(f"[OK] 河川描画: {part['id']} {part['name']} ({matched}区間)")

    # --- 経緯線 ---
    grid_svg = []
    lon = math.ceil(x0 / 5) * 5
    while lon <= x1:
        ax, _ = proj(lon, 0)
        grid_svg.append(f'<line class="grid" x1="{ax:.1f}" y1="0" x2="{ax:.1f}" y2="{height}"/>')
        lon += 5
    lat = math.ceil(y0 / 5) * 5
    while lat <= y1:
        _, ay = proj(0, lat)
        grid_svg.append(f'<line class="grid" x1="0" y1="{ay:.1f}" x2="{width}" y2="{ay:.1f}"/>')
        lat += 5
    for part in [p for p in cfg["parts"] if p["mode"] == "grid"]:
        if part["axis"] == "lat":
            _, ay = proj(0, part["deg"])
            grid_svg.append(
                f'<line class="grid-q part-shape" data-part="{part["id"]}" x1="0" y1="{ay:.1f}" x2="{width}" y2="{ay:.1f}"/>'
            )
        else:
            ax, _ = proj(part["deg"], 0)
            grid_svg.append(
                f'<line class="grid-q part-shape" data-part="{part["id"]}" x1="{ax:.1f}" y1="0" x2="{ax:.1f}" y2="{height}"/>'
            )

    # --- マーカー（全パーツ共通。タップ対象） ---
    marker_svg = []
    for part in cfg["parts"]:
        mx, my = proj(part["lon"], part["lat"])
        kind_cls = {"都市": "m-city", "島": "m-island", "諸島": "m-island"}.get(part["kind"], "m-zone")
        marker_svg.append(
            f'<g class="marker {kind_cls}" data-part="{part["id"]}" transform="translate({mx:.1f},{my:.1f})">'
            f'<circle class="hit" r="16"/><circle class="dot" r="4"/></g>'
        )

    style = (
        "<style>"
        ".land{fill:#eef1ec;stroke:#94a3ae;stroke-width:.7;vector-effect:non-scaling-stroke}"
        ".river{fill:none;stroke:#8db8da;stroke-width:1.3;stroke-linecap:round;vector-effect:non-scaling-stroke}"
        ".grid{stroke:#d3dae1;stroke-width:.5}"
        ".grid-q{stroke:#9aa7b5;stroke-width:1.1;stroke-dasharray:6 4}"
        ".marker .hit{fill:#000;fill-opacity:0;pointer-events:all}"
        ".marker .dot{fill:#3a3a3c;stroke:#fff;stroke-width:1.2}"
        ".m-city .dot{fill:#1c1c1e}"
        "</style>"
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'data-region="{region_key}">{style}'
        f'<g id="grid">{"".join(grid_svg)}</g>'
        f'<g id="land">{"".join(land_svg)}</g>'
        f'<g id="rivers">{"".join(river_svg)}</g>'
        f'<g id="markers">{"".join(marker_svg)}</g>'
        f"</svg>"
    )

    # --- 出力 ---
    os.makedirs(BUILD, exist_ok=True)
    svg_path = os.path.join(BUILD, f"map_{region_key}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    parts_out = []
    for p in cfg["parts"]:
        parts_out.append({
            "id": p["id"], "name": p["name"], "yomi": p.get("yomi", ""),
            "alt": p.get("alt", []), "kind": p["kind"],
            "res": p.get("res", ""), "check": bool(p.get("check")),
        })
    js = (
        "// 自動生成: tools/make_map.py（編集はスクリプト側で）\n"
        f"const MAP_PARTS_{region_key.upper()} = "
        + json.dumps(parts_out, ensure_ascii=False, indent=1)
        + ";\n"
    )
    js_path = os.path.join(BUILD, f"parts_{region_key}.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)

    report.append(f"SVGサイズ: {len(svg.encode('utf-8')) / 1024:.1f} KB（目安: 100KB以下）")
    report.append("要確認(check=True): " + ", ".join(p["id"] for p in cfg["parts"] if p.get("check")))
    rep_path = os.path.join(BUILD, f"report_{region_key}.txt")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")

    print("\n".join(report))
    print(f"\n出力: {svg_path}\n      {js_path}\n      {rep_path}")


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "sea"
    if key not in REGIONS:
        raise SystemExit(f"未定義の地域: {key}（定義済み: {', '.join(REGIONS)}）")
    build(key)
