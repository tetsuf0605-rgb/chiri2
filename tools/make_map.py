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
             "mode": "river", "match": ["chao phraya", "chaophraya", "mae nam"], "lon": 100.1, "lat": 15.5},
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
    "sasia": {
        "title": "南アジア",
        "bbox": (62.0, -1.0, 98.0, 37.0),
        "width": 700,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "北緯20度", "yomi": "", "alt": ["20度", "20"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 20, "lon": 64.0, "lat": 20.0},
            {"id": "い", "name": "東経80度", "yomi": "", "alt": ["80度", "80"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 80, "lon": 80.0, "lat": 0.5},
            {"id": "う", "name": "アラビア海", "yomi": "あらびあかい", "alt": [], "kind": "海", "mode": "zone", "lon": 65.0, "lat": 15.0},
            {"id": "え", "name": "ベンガル湾", "yomi": "べんがるわん", "alt": [], "kind": "湾", "mode": "zone", "lon": 89.0, "lat": 15.0},
            {"id": "お", "name": "セイロン島", "yomi": "せいろんとう", "alt": ["スリランカ島", "スリランカ"], "kind": "島", "mode": "island", "lon": 80.7, "lat": 7.9},
            {"id": "か", "name": "K2", "yomi": "けーつー", "alt": ["ケーツー", "ゴッドウィンオースティン"], "kind": "山", "mode": "zone", "lon": 76.51, "lat": 35.88},
            {"id": "き", "name": "カラコルム山脈", "yomi": "からこるむさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 75.0, "lat": 35.2},
            {"id": "く", "name": "ヒマラヤ山脈", "yomi": "ひまらやさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 84.0, "lat": 28.5},
            {"id": "け", "name": "エベレスト山", "yomi": "えべれすとさん", "alt": ["エベレスト", "チョモランマ", "サガルマータ"], "kind": "山", "mode": "zone", "lon": 86.93, "lat": 27.99},
            {"id": "こ", "name": "デカン高原", "yomi": "でかんこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 77.0, "lat": 17.0},
            {"id": "さ", "name": "ヒンドスタン平原", "yomi": "ひんどすたんへいげん", "alt": ["ヒンドゥスタン平原"], "kind": "平原", "mode": "zone", "lon": 81.0, "lat": 26.5},
            {"id": "し", "name": "インダス川", "yomi": "いんだすがわ", "alt": [], "kind": "川", "mode": "river", "match": ["indus"], "lon": 68.5, "lat": 27.5},
            {"id": "す", "name": "サトレジ川", "yomi": "さとれじがわ", "alt": ["サトレジュ川"], "kind": "川", "mode": "river", "match": ["sutlej"], "lon": 74.5, "lat": 30.5, "check": True},
            {"id": "せ", "name": "ガンジス川", "yomi": "がんじすがわ", "alt": [], "kind": "川", "mode": "river", "match": ["ganges", "ganga"], "lon": 83.0, "lat": 25.5},
            {"id": "そ", "name": "タール砂漠", "yomi": "たーるさばく", "alt": ["大インド砂漠"], "kind": "砂漠", "mode": "zone", "lon": 71.5, "lat": 26.5},
            {"id": "た", "name": "カシミール地方", "yomi": "かしみーるちほう", "alt": ["カシミール"], "kind": "地方", "mode": "zone", "lon": 75.0, "lat": 34.0},
            {"id": "ち", "name": "パンジャブ地方", "yomi": "ぱんじゃぶちほう", "alt": ["パンジャブ"], "kind": "地方", "mode": "zone", "lon": 73.5, "lat": 31.0},
            {"id": "つ", "name": "アッサム地方", "yomi": "あっさむちほう", "alt": ["アッサム"], "kind": "地方", "mode": "zone", "lon": 93.5, "lat": 26.5},
            {"id": "て", "name": "カラコルム峠", "yomi": "からこるむとうげ", "alt": [], "kind": "峠", "mode": "zone", "lon": 77.83, "lat": 35.51, "check": True},
            {"id": "1", "name": "シュリーナガル", "yomi": "しゅりーながる", "alt": ["スリナガル"], "kind": "都市", "mode": "city", "lon": 74.80, "lat": 34.08},
            {"id": "2", "name": "カラチ", "yomi": "からち", "alt": [], "kind": "都市", "mode": "city", "lon": 67.01, "lat": 24.86},
            {"id": "3", "name": "アーメダバード", "yomi": "あーめだばーど", "alt": ["アフマダーバード"], "kind": "都市", "mode": "city", "lon": 72.57, "lat": 23.03, "check": True},
            {"id": "4", "name": "ムンバイ", "yomi": "むんばい", "alt": ["ボンベイ"], "kind": "都市", "mode": "city", "lon": 72.88, "lat": 19.08},
            {"id": "5", "name": "バンガロール", "yomi": "ばんがろーる", "alt": ["ベンガルール"], "kind": "都市", "mode": "city", "lon": 77.59, "lat": 12.97},
            {"id": "6", "name": "チェンナイ", "yomi": "ちぇんない", "alt": ["マドラス"], "kind": "都市", "mode": "city", "lon": 80.27, "lat": 13.08},
            {"id": "7", "name": "デリー", "yomi": "でりー", "alt": ["ニューデリー"], "kind": "都市", "mode": "city", "lon": 77.21, "lat": 28.61},
            {"id": "8", "name": "バラナシ", "yomi": "ばらなし", "alt": ["ベナレス", "ワーラーナシ"], "kind": "都市", "res": "聖地", "mode": "city", "lon": 83.01, "lat": 25.32},
            {"id": "9", "name": "パトナ", "yomi": "ぱとな", "alt": [], "kind": "都市", "mode": "city", "lon": 85.14, "lat": 25.59, "check": True},
            {"id": "10", "name": "コルカタ", "yomi": "こるかた", "alt": ["カルカッタ"], "kind": "都市", "mode": "city", "lon": 88.36, "lat": 22.57},
            {"id": "11", "name": "カトマンズ", "yomi": "かとまんず", "alt": [], "kind": "都市", "mode": "city", "lon": 85.32, "lat": 27.71},
            {"id": "12", "name": "ティンプー", "yomi": "てぃんぷー", "alt": [], "kind": "都市", "mode": "city", "lon": 89.64, "lat": 27.47},
            {"id": "13", "name": "ダッカ", "yomi": "だっか", "alt": [], "kind": "都市", "mode": "city", "lon": 90.41, "lat": 23.81},
            {"id": "14", "name": "コロンボ", "yomi": "ころんぼ", "alt": [], "kind": "都市", "mode": "city", "lon": 79.86, "lat": 6.93},
            {"id": "15", "name": "マレ", "yomi": "まれ", "alt": [], "kind": "都市", "mode": "city", "lon": 73.51, "lat": 4.17},
        ],
    },
    "wasia": {
        "title": "西アジア",
        "bbox": (25.0, 10.0, 77.0, 45.0),
        "width": 700,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "北回帰線", "yomi": "きたかいきせん", "alt": ["北緯23.4度"], "kind": "緯線", "mode": "grid", "axis": "lat", "deg": 23.4, "lon": 70.0, "lat": 23.4},
            {"id": "い", "name": "北緯40度", "yomi": "", "alt": ["40度", "40"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 40, "lon": 27.0, "lat": 40.0, "check": True},
            {"id": "う", "name": "東経30度", "yomi": "", "alt": ["30度", "30"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 30, "lon": 30.0, "lat": 43.0, "check": True},
            {"id": "え", "name": "黒海", "yomi": "こっかい", "alt": [], "kind": "海", "mode": "zone", "lon": 35.0, "lat": 43.0},
            {"id": "お", "name": "地中海", "yomi": "ちちゅうかい", "alt": [], "kind": "海", "mode": "zone", "lon": 30.0, "lat": 33.5},
            {"id": "か", "name": "紅海", "yomi": "こうかい", "alt": [], "kind": "海", "mode": "zone", "lon": 38.0, "lat": 20.0},
            {"id": "き", "name": "バブエルマンデブ海峡", "yomi": "ばぶえるまんでぶかいきょう", "alt": ["バベルマンデブ海峡"], "kind": "海峡", "mode": "zone", "lon": 43.4, "lat": 12.6},
            {"id": "く", "name": "アデン湾", "yomi": "あでんわん", "alt": [], "kind": "湾", "mode": "zone", "lon": 48.0, "lat": 12.5},
            {"id": "け", "name": "アラビア海", "yomi": "あらびあかい", "alt": [], "kind": "海", "mode": "zone", "lon": 62.0, "lat": 15.0},
            {"id": "こ", "name": "ホルムズ海峡", "yomi": "ほるむずかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 56.5, "lat": 26.6},
            {"id": "さ", "name": "ペルシア湾", "yomi": "ぺるしあわん", "alt": ["ペルシャ湾"], "kind": "湾", "mode": "zone", "lon": 51.0, "lat": 27.5},
            {"id": "し", "name": "ボスポラス海峡", "yomi": "ぼすぽらすかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 29.1, "lat": 41.1, "check": True},
            {"id": "す", "name": "ヴァン湖", "yomi": "う゛ぁんこ", "alt": ["バン湖"], "kind": "湖", "mode": "zone", "lon": 42.9, "lat": 38.6, "check": True},
            {"id": "せ", "name": "キプロス島", "yomi": "きぷろすとう", "alt": [], "kind": "島", "mode": "island", "lon": 33.2, "lat": 35.1},
            {"id": "そ", "name": "シナイ半島", "yomi": "しないはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 33.8, "lat": 29.5},
            {"id": "た", "name": "アラビア半島", "yomi": "あらびあはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 45.0, "lat": 23.0},
            {"id": "ち", "name": "ナイル川", "yomi": "ないるがわ", "alt": [], "kind": "川", "mode": "river", "match": ["nile"], "lon": 31.5, "lat": 27.0},
            {"id": "つ", "name": "チグリス川", "yomi": "ちぐりすがわ", "alt": ["ティグリス川"], "kind": "川", "mode": "river", "match": ["tigris"], "lon": 43.5, "lat": 35.0},
            {"id": "て", "name": "ユーフラテス川", "yomi": "ゆーふらてすがわ", "alt": [], "kind": "川", "mode": "river", "match": ["euphrates"], "lon": 39.0, "lat": 35.8},
            {"id": "と", "name": "インダス川", "yomi": "いんだすがわ", "alt": [], "kind": "川", "mode": "river", "match": ["indus"], "lon": 69.0, "lat": 27.5},
            {"id": "な", "name": "アナトリア高原", "yomi": "あなとりあこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 33.0, "lat": 39.0},
            {"id": "に", "name": "ネフド砂漠", "yomi": "ねふどさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 41.0, "lat": 28.5, "check": True},
            {"id": "ぬ", "name": "ルブアルハリ砂漠", "yomi": "るぶあるはりさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 50.0, "lat": 20.0},
            {"id": "ね", "name": "ザグロス山脈", "yomi": "ざぐろすさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 48.0, "lat": 32.5},
            {"id": "の", "name": "イラン高原", "yomi": "いらんこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 55.0, "lat": 32.5},
            {"id": "は", "name": "ヒンドゥークシュ山脈", "yomi": "ひんどぅーくしゅさんみゃく", "alt": ["ヒンズークシ山脈"], "kind": "山脈", "mode": "zone", "lon": 66.0, "lat": 35.5, "check": True},
            {"id": "ひ", "name": "エルブールズ山脈", "yomi": "えるぶーるずさんみゃく", "alt": ["エルブルズ山脈"], "kind": "山脈", "mode": "zone", "lon": 52.0, "lat": 36.3},
            {"id": "ふ", "name": "カイバー峠", "yomi": "かいばーとうげ", "alt": ["カイバル峠"], "kind": "峠", "mode": "zone", "lon": 71.1, "lat": 34.1},
            {"id": "へ", "name": "カラコルム山脈", "yomi": "からこるむさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 75.5, "lat": 35.8, "check": True},
            {"id": "ほ", "name": "パミール高原", "yomi": "ぱみーるこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 73.0, "lat": 38.5},
            {"id": "1", "name": "イスタンブール", "yomi": "いすたんぶーる", "alt": [], "kind": "都市", "mode": "city", "lon": 28.98, "lat": 41.01},
            {"id": "2", "name": "アンカラ", "yomi": "あんから", "alt": [], "kind": "都市", "mode": "city", "lon": 32.86, "lat": 39.93},
            {"id": "3", "name": "トビリシ", "yomi": "とびりし", "alt": [], "kind": "都市", "mode": "city", "lon": 44.83, "lat": 41.72, "check": True},
            {"id": "4", "name": "ニコシア", "yomi": "にこしあ", "alt": [], "kind": "都市", "mode": "city", "lon": 33.38, "lat": 35.19, "check": True},
            {"id": "5", "name": "ベイルート", "yomi": "べいるーと", "alt": [], "kind": "都市", "mode": "city", "lon": 35.50, "lat": 33.89, "check": True},
            {"id": "6", "name": "ダマスカス", "yomi": "だますかす", "alt": [], "kind": "都市", "mode": "city", "lon": 36.31, "lat": 33.51, "check": True},
            {"id": "7", "name": "エルサレム", "yomi": "えるされむ", "alt": ["イェルサレム"], "kind": "都市", "mode": "city", "lon": 35.22, "lat": 31.77, "check": True},
            {"id": "8", "name": "アンマン", "yomi": "あんまん", "alt": [], "kind": "都市", "mode": "city", "lon": 35.93, "lat": 31.95, "check": True},
            {"id": "9", "name": "カイロ", "yomi": "かいろ", "alt": [], "kind": "都市", "mode": "city", "lon": 31.24, "lat": 30.04},
            {"id": "10", "name": "バグダッド", "yomi": "ばぐだっど", "alt": ["バグダード"], "kind": "都市", "mode": "city", "lon": 44.36, "lat": 33.31},
            {"id": "11", "name": "タブリーズ", "yomi": "たぶりーず", "alt": [], "kind": "都市", "mode": "city", "lon": 46.29, "lat": 38.08, "check": True},
            {"id": "12", "name": "テヘラン", "yomi": "てへらん", "alt": [], "kind": "都市", "mode": "city", "lon": 51.39, "lat": 35.69},
            {"id": "13", "name": "キルクーク", "yomi": "きるくーく", "alt": [], "kind": "都市", "res": "油田", "mode": "city", "lon": 44.39, "lat": 35.47, "check": True},
            {"id": "14", "name": "アバダン", "yomi": "あばだん", "alt": [], "kind": "都市", "mode": "city", "lon": 48.30, "lat": 30.34, "check": True},
            {"id": "15", "name": "バーレーン", "yomi": "ばーれーん", "alt": ["マナーマ"], "kind": "都市", "res": "島・精油", "mode": "city", "lon": 50.59, "lat": 26.22, "check": True},
            {"id": "16", "name": "クウェート", "yomi": "くうぇーと", "alt": [], "kind": "都市", "res": "油田", "mode": "city", "lon": 47.98, "lat": 29.38},
            {"id": "17", "name": "ドーハ", "yomi": "どーは", "alt": [], "kind": "都市", "mode": "city", "lon": 51.53, "lat": 25.29, "check": True},
            {"id": "18", "name": "アブダビ", "yomi": "あぶだび", "alt": [], "kind": "都市", "mode": "city", "lon": 54.37, "lat": 24.45, "check": True},
            {"id": "19", "name": "ドバイ", "yomi": "どばい", "alt": [], "kind": "都市", "mode": "city", "lon": 55.27, "lat": 25.20, "check": True},
            {"id": "20", "name": "リヤド", "yomi": "りやど", "alt": [], "kind": "都市", "mode": "city", "lon": 46.68, "lat": 24.63},
            {"id": "21", "name": "ジッダ", "yomi": "じっだ", "alt": ["ジェッダ"], "kind": "都市", "mode": "city", "lon": 39.17, "lat": 21.49, "check": True},
            {"id": "22", "name": "メッカ", "yomi": "めっか", "alt": ["マッカ"], "kind": "都市", "res": "聖地", "mode": "city", "lon": 39.83, "lat": 21.39},
            {"id": "23", "name": "メディナ", "yomi": "めでぃな", "alt": ["マディーナ"], "kind": "都市", "res": "聖地", "mode": "city", "lon": 39.61, "lat": 24.47},
            {"id": "24", "name": "サヌア", "yomi": "さぬあ", "alt": [], "kind": "都市", "mode": "city", "lon": 44.19, "lat": 15.35, "check": True},
            {"id": "25", "name": "マスカット", "yomi": "ますかっと", "alt": [], "kind": "都市", "mode": "city", "lon": 58.41, "lat": 23.59, "check": True},
            {"id": "26", "name": "バンダルアバース", "yomi": "ばんだるあばーす", "alt": ["バンダレアッバース"], "kind": "都市", "mode": "city", "lon": 56.27, "lat": 27.19, "check": True},
            {"id": "27", "name": "シーラーズ", "yomi": "しーらーず", "alt": [], "kind": "都市", "mode": "city", "lon": 52.54, "lat": 29.60, "check": True},
            {"id": "28", "name": "カブール", "yomi": "かぶーる", "alt": ["カーブル"], "kind": "都市", "mode": "city", "lon": 69.17, "lat": 34.53},
            {"id": "29", "name": "カンダハール", "yomi": "かんだはーる", "alt": [], "kind": "都市", "mode": "city", "lon": 65.71, "lat": 31.61, "check": True},
            {"id": "30", "name": "イスラマバード", "yomi": "いすらまばーど", "alt": [], "kind": "都市", "mode": "city", "lon": 73.05, "lat": 33.68},
            {"id": "31", "name": "ペシャワール", "yomi": "ぺしゃわーる", "alt": ["ペシャーワル"], "kind": "都市", "mode": "city", "lon": 71.52, "lat": 34.01, "check": True},
        ],
    },
    "africa": {
        "title": "アフリカ",
        "bbox": (-20.0, -36.0, 55.0, 38.0),
        "width": 700,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "赤道", "yomi": "せきどう", "alt": ["0度", "緯度0度"], "kind": "緯線", "mode": "grid", "axis": "lat", "deg": 0, "lon": -15.0, "lat": 0.0},
            {"id": "い", "name": "本初子午線", "yomi": "ほんしょしごせん", "alt": ["経度0度", "0度"], "kind": "経線", "mode": "grid", "axis": "lon", "deg": 0, "lon": 0.0, "lat": -28.0},
            {"id": "う", "name": "東経30度", "yomi": "", "alt": ["30度", "30"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 30, "lon": 30.0, "lat": -32.0, "check": True},
            {"id": "え", "name": "ギニア湾", "yomi": "ぎにあわん", "alt": [], "kind": "湾", "mode": "zone", "lon": 3.0, "lat": 2.0},
            {"id": "お", "name": "地中海", "yomi": "ちちゅうかい", "alt": [], "kind": "海", "mode": "zone", "lon": 15.0, "lat": 34.5},
            {"id": "か", "name": "インド洋", "yomi": "いんどよう", "alt": [], "kind": "海", "mode": "zone", "lon": 48.0, "lat": -8.0},
            {"id": "き", "name": "ベンゲラ海流", "yomi": "べんげらかいりゅう", "alt": [], "kind": "海流", "res": "寒流", "mode": "zone", "lon": 9.0, "lat": -18.0},
            {"id": "く", "name": "ジブラルタル海峡", "yomi": "じぶらるたるかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": -5.6, "lat": 35.95},
            {"id": "け", "name": "カナリア諸島", "yomi": "かなりあしょとう", "alt": [], "kind": "諸島", "mode": "island", "lon": -16.6, "lat": 28.27},
            {"id": "こ", "name": "マダガスカル島", "yomi": "まだがすかるとう", "alt": [], "kind": "島", "mode": "island", "lon": 46.8, "lat": -19.5},
            {"id": "さ", "name": "ナイル川", "yomi": "ないるがわ", "alt": [], "kind": "川", "mode": "river", "match": ["nile"], "lon": 31.0, "lat": 23.0},
            {"id": "し", "name": "ヴィクトリア湖", "yomi": "う゛ぃくとりあこ", "alt": ["ビクトリア湖"], "kind": "湖", "mode": "zone", "lon": 33.0, "lat": -1.0},
            {"id": "す", "name": "タンガニーカ湖", "yomi": "たんがにーかこ", "alt": [], "kind": "湖", "mode": "zone", "lon": 29.5, "lat": -6.5},
            {"id": "せ", "name": "ザンベジ川", "yomi": "ざんべじがわ", "alt": [], "kind": "川", "mode": "river", "match": ["zambezi"], "lon": 33.0, "lat": -16.0},
            {"id": "そ", "name": "コンゴ川", "yomi": "こんごがわ", "alt": ["ザイール川"], "kind": "川", "mode": "river", "match": ["congo"], "lon": 17.0, "lat": -0.5},
            {"id": "た", "name": "ニジェール川", "yomi": "にじぇーるがわ", "alt": [], "kind": "川", "mode": "river", "match": ["niger"], "lon": 5.0, "lat": 9.5},
            {"id": "ち", "name": "チャド湖", "yomi": "ちゃどこ", "alt": [], "kind": "湖", "mode": "zone", "lon": 14.1, "lat": 13.2},
            {"id": "つ", "name": "アトラス山脈", "yomi": "あとらすさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": -4.0, "lat": 32.5},
            {"id": "て", "name": "エチオピア高原", "yomi": "えちおぴあこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 39.0, "lat": 9.5},
            {"id": "と", "name": "コンゴ盆地", "yomi": "こんごぼんち", "alt": [], "kind": "盆地", "mode": "zone", "lon": 22.0, "lat": -1.0},
            {"id": "な", "name": "ケニア山", "yomi": "けにあさん", "alt": [], "kind": "山", "mode": "zone", "lon": 37.31, "lat": -0.15, "check": True},
            {"id": "に", "name": "キリマンジャロ山", "yomi": "きりまんじゃろさん", "alt": [], "kind": "山", "mode": "zone", "lon": 37.35, "lat": -3.07, "check": True},
            {"id": "ぬ", "name": "カラハリ砂漠", "yomi": "からはりさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 22.0, "lat": -24.0},
            {"id": "ね", "name": "ナミブ砂漠", "yomi": "なみぶさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 14.5, "lat": -24.0},
            {"id": "の", "name": "サハラ砂漠", "yomi": "さはらさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 10.0, "lat": 23.0},
            {"id": "は", "name": "サヘル", "yomi": "さへる", "alt": ["サヘル地方"], "kind": "地方", "mode": "zone", "lon": 10.0, "lat": 15.0},
            {"id": "ひ", "name": "西サハラ", "yomi": "にしさはら", "alt": [], "kind": "地方", "mode": "zone", "lon": -13.0, "lat": 25.0, "check": True},
            {"id": "ふ", "name": "象牙海岸", "yomi": "ぞうげかいがん", "alt": [], "kind": "海岸", "mode": "zone", "lon": -5.5, "lat": 4.8, "check": True},
            {"id": "へ", "name": "黄金海岸", "yomi": "おうごんかいがん", "alt": [], "kind": "海岸", "mode": "zone", "lon": -0.5, "lat": 5.0, "check": True},
            {"id": "ほ", "name": "奴隷海岸", "yomi": "どれいかいがん", "alt": [], "kind": "海岸", "mode": "zone", "lon": 3.5, "lat": 6.0, "check": True},
            {"id": "ま", "name": "アガラス岬", "yomi": "あがらすみさき", "alt": ["アグラス岬"], "kind": "岬", "mode": "zone", "lon": 20.0, "lat": -34.83},
            {"id": "1", "name": "ラバト", "yomi": "らばと", "alt": [], "kind": "都市", "mode": "city", "lon": -6.85, "lat": 34.02, "check": True},
            {"id": "2", "name": "カサブランカ", "yomi": "かさぶらんか", "alt": [], "kind": "都市", "mode": "city", "lon": -7.59, "lat": 33.57, "check": True},
            {"id": "3", "name": "ダカール", "yomi": "だかーる", "alt": [], "kind": "都市", "mode": "city", "lon": -17.45, "lat": 14.69},
            {"id": "4", "name": "モンロビア", "yomi": "もんろびあ", "alt": [], "kind": "都市", "mode": "city", "lon": -10.80, "lat": 6.30, "check": True},
            {"id": "5", "name": "アビジャン", "yomi": "あびじゃん", "alt": [], "kind": "都市", "mode": "city", "lon": -4.02, "lat": 5.34, "check": True},
            {"id": "6", "name": "アクラ", "yomi": "あくら", "alt": [], "kind": "都市", "mode": "city", "lon": -0.19, "lat": 5.60, "check": True},
            {"id": "7", "name": "アブジャ", "yomi": "あぶじゃ", "alt": [], "kind": "都市", "mode": "city", "lon": 7.49, "lat": 9.06, "check": True},
            {"id": "8", "name": "アルジェ", "yomi": "あるじぇ", "alt": [], "kind": "都市", "mode": "city", "lon": 3.06, "lat": 36.75},
            {"id": "9", "name": "チュニス", "yomi": "ちゅにす", "alt": [], "kind": "都市", "mode": "city", "lon": 10.17, "lat": 36.81},
            {"id": "10", "name": "トリポリ", "yomi": "とりぽり", "alt": [], "kind": "都市", "mode": "city", "lon": 13.19, "lat": 32.89},
            {"id": "11", "name": "アレクサンドリア", "yomi": "あれくさんどりあ", "alt": [], "kind": "都市", "mode": "city", "lon": 29.92, "lat": 31.20, "check": True},
            {"id": "12", "name": "カイロ", "yomi": "かいろ", "alt": [], "kind": "都市", "mode": "city", "lon": 31.24, "lat": 30.04},
            {"id": "13", "name": "ハルツーム", "yomi": "はるつーむ", "alt": [], "kind": "都市", "mode": "city", "lon": 32.53, "lat": 15.55},
            {"id": "14", "name": "アディスアベバ", "yomi": "あでぃすあべば", "alt": [], "kind": "都市", "mode": "city", "lon": 38.75, "lat": 9.02},
            {"id": "15", "name": "カンパラ", "yomi": "かんぱら", "alt": [], "kind": "都市", "mode": "city", "lon": 32.58, "lat": 0.32, "check": True},
            {"id": "16", "name": "ナイロビ", "yomi": "ないろび", "alt": [], "kind": "都市", "mode": "city", "lon": 36.82, "lat": -1.29},
            {"id": "17", "name": "ダルエスサラーム", "yomi": "だるえすさらーむ", "alt": [], "kind": "都市", "mode": "city", "lon": 39.28, "lat": -6.82},
            {"id": "18", "name": "キサンガニ", "yomi": "きさんがに", "alt": [], "kind": "都市", "mode": "city", "lon": 25.19, "lat": 0.52, "check": True},
            {"id": "19", "name": "ヤウンデ", "yomi": "やうんで", "alt": [], "kind": "都市", "mode": "city", "lon": 11.52, "lat": 3.87, "check": True},
            {"id": "20", "name": "キンシャサ", "yomi": "きんしゃさ", "alt": [], "kind": "都市", "mode": "city", "lon": 15.31, "lat": -4.33},
            {"id": "21", "name": "ヨハネスブルク", "yomi": "よはねすぶるく", "alt": ["ヨハネスバーグ"], "kind": "都市", "mode": "city", "lon": 28.05, "lat": -26.20, "check": True},
            {"id": "22", "name": "ケープタウン", "yomi": "けーぷたうん", "alt": [], "kind": "都市", "mode": "city", "lon": 18.42, "lat": -33.93},
            {"id": "23", "name": "アンタナナリボ", "yomi": "あんたななりぼ", "alt": [], "kind": "都市", "mode": "city", "lon": 47.51, "lat": -18.88},
            {"id": "24", "name": "ジブチ", "yomi": "じぶち", "alt": [], "kind": "都市", "mode": "city", "lon": 43.15, "lat": 11.59, "check": True},
        ],
    },
    "russia": {
        "title": "ロシアと周辺諸国",
        "bbox": (18.0, 25.0, 165.0, 80.0),
        "width": 760,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "北極圏", "yomi": "ほっきょくけん", "alt": ["北緯66.6度"], "kind": "緯線", "mode": "grid", "axis": "lat", "deg": 66.5, "lon": 150.0, "lat": 66.5, "check": True},
            {"id": "い", "name": "東経60度", "yomi": "", "alt": ["60度", "60"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 60, "lon": 60.0, "lat": 74.0, "check": True},
            {"id": "う", "name": "北緯50度", "yomi": "", "alt": ["50度", "50"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 50, "lon": 22.0, "lat": 50.0, "check": True},
            {"id": "え", "name": "バルト海", "yomi": "ばるとかい", "alt": [], "kind": "海", "mode": "zone", "lon": 20.0, "lat": 58.0},
            {"id": "お", "name": "オホーツク海", "yomi": "おほーつくかい", "alt": [], "kind": "海", "mode": "zone", "lon": 148.0, "lat": 54.0},
            {"id": "か", "name": "カスピ海", "yomi": "かすぴかい", "alt": [], "kind": "海", "mode": "zone", "lon": 51.0, "lat": 42.0},
            {"id": "き", "name": "黒海", "yomi": "こっかい", "alt": [], "kind": "海", "mode": "zone", "lon": 34.0, "lat": 43.0},
            {"id": "く", "name": "カムチャツカ半島", "yomi": "かむちゃつかはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 159.0, "lat": 56.0},
            {"id": "け", "name": "宗谷海峡", "yomi": "そうやかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 142.0, "lat": 45.8, "check": True},
            {"id": "こ", "name": "コラ半島", "yomi": "こらはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 37.0, "lat": 67.5},
            {"id": "さ", "name": "ノバヤゼムリャ諸島", "yomi": "のばやぜむりゃしょとう", "alt": ["ノヴァヤゼムリャ"], "kind": "諸島", "mode": "island", "lon": 56.0, "lat": 73.5, "check": True},
            {"id": "し", "name": "サハリン島", "yomi": "さはりんとう", "alt": ["樺太"], "kind": "島", "mode": "island", "lon": 143.0, "lat": 51.0},
            {"id": "す", "name": "バイカル湖", "yomi": "ばいかるこ", "alt": [], "kind": "湖", "mode": "zone", "lon": 108.0, "lat": 53.5},
            {"id": "せ", "name": "ボルガ川", "yomi": "ぼるががわ", "alt": ["ヴォルガ川"], "kind": "川", "mode": "river", "match": ["volga"], "lon": 47.0, "lat": 50.0},
            {"id": "そ", "name": "オビ川", "yomi": "おびがわ", "alt": [], "kind": "川", "mode": "river", "match": ["ob"], "lon": 70.0, "lat": 62.0},
            {"id": "た", "name": "エニセイ川", "yomi": "えにせいがわ", "alt": [], "kind": "川", "mode": "river", "match": ["yenisey", "yenisei"], "lon": 87.0, "lat": 66.0},
            {"id": "ち", "name": "レナ川", "yomi": "れながわ", "alt": [], "kind": "川", "mode": "river", "match": ["lena"], "lon": 124.0, "lat": 64.0},
            {"id": "つ", "name": "アムール川", "yomi": "あむーるがわ", "alt": ["黒竜江"], "kind": "川", "mode": "river", "match": ["amur"], "lon": 132.0, "lat": 51.0},
            {"id": "て", "name": "オビ川", "yomi": "おびがわ", "alt": [], "kind": "川", "mode": "river", "match": ["ob"], "lon": 74.0, "lat": 56.0, "check": True},
            {"id": "と", "name": "ドニエプル川", "yomi": "どにえぷるがわ", "alt": ["ドニプロ川"], "kind": "川", "mode": "river", "match": ["dnieper", "dnipro"], "lon": 33.0, "lat": 48.0, "check": True},
            {"id": "な", "name": "アラル海", "yomi": "あらるかい", "alt": [], "kind": "湖", "mode": "zone", "lon": 60.0, "lat": 45.0},
            {"id": "に", "name": "バルハシ湖", "yomi": "ばるはしこ", "alt": [], "kind": "湖", "mode": "zone", "lon": 74.0, "lat": 46.3},
            {"id": "ぬ", "name": "カラクーム砂漠", "yomi": "からくーむさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 59.0, "lat": 39.5},
            {"id": "ね", "name": "西シベリア平原", "yomi": "にししべりあへいげん", "alt": [], "kind": "平原", "mode": "zone", "lon": 75.0, "lat": 60.0},
            {"id": "の", "name": "中央シベリア高原", "yomi": "ちゅうおうしべりあこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": 100.0, "lat": 65.0},
            {"id": "は", "name": "スタノボイ山脈", "yomi": "すたのぼいさんみゃく", "alt": ["外興安嶺"], "kind": "山脈", "mode": "zone", "lon": 130.0, "lat": 56.0, "check": True},
            {"id": "ひ", "name": "東ヨーロッパ平原", "yomi": "ひがしよーろっぱへいげん", "alt": ["ロシア平原"], "kind": "平原", "mode": "zone", "lon": 40.0, "lat": 57.0},
            {"id": "へ", "name": "カザフステップ", "yomi": "かざふすてっぷ", "alt": ["カザフ高原"], "kind": "高原", "mode": "zone", "lon": 68.0, "lat": 49.0, "check": True},
            {"id": "a", "name": "クリボイログ", "yomi": "くりぼいろぐ", "alt": ["クリヴィーリフ"], "kind": "都市", "res": "鉄", "mode": "city", "lon": 33.42, "lat": 47.91, "check": True},
            {"id": "b", "name": "チュメニ油田", "yomi": "ちゅめにゆでん", "alt": ["チュメニ"], "kind": "都市", "res": "油田", "mode": "zone", "lon": 70.0, "lat": 61.0, "check": True},
            {"id": "c", "name": "クズネツク", "yomi": "くずねつく", "alt": ["クズバス"], "kind": "都市", "res": "炭田", "mode": "zone", "lon": 87.0, "lat": 54.0, "check": True},
            {"id": "d", "name": "カラガンダ", "yomi": "からがんだ", "alt": [], "kind": "都市", "res": "炭田", "mode": "city", "lon": 73.10, "lat": 49.80, "check": True},
            {"id": "1", "name": "ムルマンスク", "yomi": "むるまんすく", "alt": [], "kind": "都市", "mode": "city", "lon": 33.08, "lat": 68.97},
            {"id": "2", "name": "サンクトペテルブルク", "yomi": "さんくとぺてるぶるく", "alt": ["ペテルブルグ", "レニングラード"], "kind": "都市", "mode": "city", "lon": 30.34, "lat": 59.93},
            {"id": "3", "name": "モスクワ", "yomi": "もすくわ", "alt": [], "kind": "都市", "mode": "city", "lon": 37.62, "lat": 55.75},
            {"id": "4", "name": "ニジニノブゴロド", "yomi": "にじにのぶごろど", "alt": ["ゴーリキー"], "kind": "都市", "mode": "city", "lon": 44.00, "lat": 56.33, "check": True},
            {"id": "5", "name": "ボルゴグラード", "yomi": "ぼるごぐらーど", "alt": ["スターリングラード"], "kind": "都市", "mode": "city", "lon": 44.52, "lat": 48.72, "check": True},
            {"id": "6", "name": "ウラジオストク", "yomi": "うらじおすとく", "alt": [], "kind": "都市", "mode": "city", "lon": 131.89, "lat": 43.12},
            {"id": "7", "name": "ヤクーツク", "yomi": "やくーつく", "alt": [], "kind": "都市", "mode": "city", "lon": 129.73, "lat": 62.03, "check": True},
            {"id": "8", "name": "ノリリスク", "yomi": "のりりすく", "alt": [], "kind": "都市", "mode": "city", "lon": 88.20, "lat": 69.35, "check": True},
            {"id": "9", "name": "マガダン", "yomi": "まがだん", "alt": [], "kind": "都市", "mode": "city", "lon": 150.81, "lat": 59.56, "check": True},
            {"id": "10", "name": "キーウ", "yomi": "きーう", "alt": ["キエフ"], "kind": "都市", "mode": "city", "lon": 30.52, "lat": 50.45},
            {"id": "11", "name": "ミンスク", "yomi": "みんすく", "alt": [], "kind": "都市", "mode": "city", "lon": 27.57, "lat": 53.90, "check": True},
            {"id": "12", "name": "ハリコフ", "yomi": "はりこふ", "alt": ["ハルキウ"], "kind": "都市", "mode": "city", "lon": 36.23, "lat": 49.99, "check": True},
            {"id": "13", "name": "ドネツク", "yomi": "どねつく", "alt": [], "kind": "都市", "res": "鉄", "mode": "city", "lon": 37.80, "lat": 48.02, "check": True},
            {"id": "14", "name": "オデーサ", "yomi": "おでーさ", "alt": ["オデッサ"], "kind": "都市", "mode": "city", "lon": 30.73, "lat": 46.48, "check": True},
            {"id": "15", "name": "バクー", "yomi": "ばくー", "alt": [], "kind": "都市", "res": "油田", "mode": "city", "lon": 49.87, "lat": 40.41},
            {"id": "16", "name": "トビリシ", "yomi": "とびりし", "alt": [], "kind": "都市", "mode": "city", "lon": 44.83, "lat": 41.72, "check": True},
            {"id": "17", "name": "タシケント", "yomi": "たしけんと", "alt": [], "kind": "都市", "mode": "city", "lon": 69.24, "lat": 41.31},
            {"id": "18", "name": "アルマトイ", "yomi": "あるまとい", "alt": ["アルマアタ"], "kind": "都市", "mode": "city", "lon": 76.89, "lat": 43.24, "check": True},
            {"id": "19", "name": "エカテリンブルク", "yomi": "えかてりんぶるく", "alt": ["スベルドロフスク"], "kind": "都市", "mode": "city", "lon": 60.61, "lat": 56.84},
            {"id": "20", "name": "ノボシビルスク", "yomi": "のぼしびるすく", "alt": [], "kind": "都市", "mode": "city", "lon": 82.92, "lat": 55.03},
            {"id": "21", "name": "イルクーツク", "yomi": "いるくーつく", "alt": [], "kind": "都市", "mode": "city", "lon": 104.30, "lat": 52.29},
            {"id": "22", "name": "オムスク", "yomi": "おむすく", "alt": [], "kind": "都市", "mode": "city", "lon": 73.37, "lat": 54.99, "check": True},
            {"id": "23", "name": "ウランバートル", "yomi": "うらんばーとる", "alt": [], "kind": "都市", "mode": "city", "lon": 106.92, "lat": 47.92, "check": True},
        ],
    },
    "namerica": {
        "title": "北アメリカ",
        "bbox": (-170.0, 5.0, -35.0, 72.0),
        "width": 720,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "北緯40度", "yomi": "", "alt": ["40度", "40"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 40, "lon": -128.0, "lat": 40.0, "check": True},
            {"id": "い", "name": "西経140度", "yomi": "", "alt": ["140度", "140"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": -140, "lon": -140.0, "lat": 60.0, "check": True},
            {"id": "う", "name": "西経100度", "yomi": "", "alt": ["100度", "100"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": -100, "lon": -100.0, "lat": 12.0, "check": True},
            {"id": "え", "name": "ハドソン湾", "yomi": "はどそんわん", "alt": [], "kind": "湾", "mode": "zone", "lon": -85.0, "lat": 60.0},
            {"id": "お", "name": "セントローレンス湾", "yomi": "せんとろーれんすわん", "alt": [], "kind": "湾", "mode": "zone", "lon": -62.0, "lat": 48.0, "check": True},
            {"id": "か", "name": "大西洋", "yomi": "たいせいよう", "alt": [], "kind": "海", "mode": "zone", "lon": -60.0, "lat": 30.0},
            {"id": "き", "name": "メキシコ湾", "yomi": "めきしこわん", "alt": [], "kind": "湾", "mode": "zone", "lon": -90.0, "lat": 25.0},
            {"id": "く", "name": "カリブ海", "yomi": "かりぶかい", "alt": [], "kind": "海", "mode": "zone", "lon": -75.0, "lat": 15.0},
            {"id": "け", "name": "北極海", "yomi": "ほっきょくかい", "alt": [], "kind": "海", "mode": "zone", "lon": -120.0, "lat": 71.0},
            {"id": "こ", "name": "ベーリング海峡", "yomi": "べーりんぐかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": -168.0, "lat": 65.5},
            {"id": "さ", "name": "太平洋", "yomi": "たいへいよう", "alt": [], "kind": "海", "mode": "zone", "lon": -145.0, "lat": 35.0},
            {"id": "し", "name": "パナマ運河", "yomi": "ぱなまうんが", "alt": [], "kind": "運河", "mode": "zone", "lon": -79.6, "lat": 9.1},
            {"id": "す", "name": "グリーンランド", "yomi": "ぐりーんらんど", "alt": [], "kind": "島", "mode": "zone", "lon": -42.0, "lat": 70.0},
            {"id": "せ", "name": "ニューファンドランド島", "yomi": "にゅーふぁんどらんどとう", "alt": [], "kind": "島", "mode": "island", "lon": -56.0, "lat": 48.5, "check": True},
            {"id": "そ", "name": "キューバ島", "yomi": "きゅーばとう", "alt": [], "kind": "島", "mode": "island", "lon": -79.0, "lat": 21.9},
            {"id": "た", "name": "フロリダ半島", "yomi": "ふろりだはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": -81.5, "lat": 28.5},
            {"id": "ち", "name": "カリフォルニア半島", "yomi": "かりふぉるにあはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": -113.0, "lat": 27.5},
            {"id": "つ", "name": "バンクーバー島", "yomi": "ばんくーばーとう", "alt": [], "kind": "島", "mode": "island", "lon": -125.5, "lat": 49.7, "check": True},
            {"id": "て", "name": "ユカタン半島", "yomi": "ゆかたんはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": -89.0, "lat": 19.5},
            {"id": "と", "name": "ロッキー山脈", "yomi": "ろっきーさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": -114.0, "lat": 50.0},
            {"id": "な", "name": "アパラチア山脈", "yomi": "あぱらちあさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": -81.0, "lat": 36.0},
            {"id": "に", "name": "マッケンジー川", "yomi": "まっけんじーがわ", "alt": [], "kind": "川", "mode": "river", "match": ["mackenzie"], "lon": -125.0, "lat": 66.0, "check": True},
            {"id": "ぬ", "name": "ユーコン川", "yomi": "ゆーこんがわ", "alt": [], "kind": "川", "mode": "river", "match": ["yukon"], "lon": -150.0, "lat": 64.0, "check": True},
            {"id": "ね", "name": "セントローレンス川", "yomi": "せんとろーれんすがわ", "alt": [], "kind": "川", "mode": "river", "match": ["saint lawrence", "st. lawrence"], "lon": -71.0, "lat": 47.0, "check": True},
            {"id": "の", "name": "ミズーリ川", "yomi": "みずーりがわ", "alt": [], "kind": "川", "mode": "river", "match": ["missouri"], "lon": -100.0, "lat": 47.0, "check": True},
            {"id": "は", "name": "アーカンソー川", "yomi": "あーかんそーがわ", "alt": [], "kind": "川", "mode": "river", "match": ["arkansas"], "lon": -97.0, "lat": 36.0, "check": True},
            {"id": "ひ", "name": "テネシー川", "yomi": "てねしーがわ", "alt": [], "kind": "川", "mode": "river", "match": ["tennessee"], "lon": -87.0, "lat": 35.0, "check": True},
            {"id": "ふ", "name": "リオグランデ川", "yomi": "りおぐらんでがわ", "alt": ["リオグランデ"], "kind": "川", "mode": "river", "match": ["rio grande", "río grande", "rio bravo"], "lon": -102.0, "lat": 29.0, "check": True},
            {"id": "へ", "name": "コロラド川", "yomi": "ころらどがわ", "alt": [], "kind": "川", "mode": "river", "match": ["colorado"], "lon": -113.5, "lat": 36.0},
            {"id": "ほ", "name": "グレートソルト湖", "yomi": "ぐれーとそるとこ", "alt": ["大塩湖"], "kind": "湖", "mode": "zone", "lon": -112.5, "lat": 41.2},
            {"id": "ま", "name": "コロンビア川", "yomi": "ころんびあがわ", "alt": [], "kind": "川", "mode": "river", "match": ["columbia"], "lon": -120.0, "lat": 46.5, "check": True},
            {"id": "み", "name": "五大湖", "yomi": "ごだいこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -87.0, "lat": 44.0},
            {"id": "む", "name": "ミシガン湖", "yomi": "みしがんこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -87.0, "lat": 43.5, "check": True},
            {"id": "め", "name": "エリー湖", "yomi": "えりーこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -81.2, "lat": 42.2, "check": True},
            {"id": "も", "name": "オンタリオ湖", "yomi": "おんたりおこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -77.8, "lat": 43.7, "check": True},
            {"id": "や", "name": "ミシシッピ川", "yomi": "みしっしっぴがわ", "alt": [], "kind": "川", "mode": "river", "match": ["mississippi"], "lon": -91.0, "lat": 32.0},
            {"id": "ゆ", "name": "ウィニペグ湖", "yomi": "うぃにぺぐこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -97.3, "lat": 52.5, "check": True},
            {"id": "よ", "name": "ラブラドル高原", "yomi": "らぶらどるこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": -70.0, "lat": 54.0, "check": True},
            {"id": "ら", "name": "ラブラドル半島", "yomi": "らぶらどるはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": -72.0, "lat": 56.0, "check": True},
            {"id": "れ", "name": "グレートプレーンズ", "yomi": "ぐれーとぷれーんず", "alt": [], "kind": "平原", "mode": "zone", "lon": -103.0, "lat": 43.0},
            {"id": "ろ", "name": "中央平原", "yomi": "ちゅうおうへいげん", "alt": ["プレーリー"], "kind": "平原", "mode": "zone", "lon": -92.0, "lat": 42.0, "check": True},
            {"id": "1", "name": "バロー", "yomi": "ばろー", "alt": ["ウトキアグヴィク"], "kind": "都市", "mode": "city", "lon": -156.79, "lat": 71.29, "check": True},
            {"id": "2", "name": "アンカレジ", "yomi": "あんかれじ", "alt": [], "kind": "都市", "mode": "city", "lon": -149.90, "lat": 61.22},
            {"id": "3", "name": "バンクーバー", "yomi": "ばんくーばー", "alt": [], "kind": "都市", "mode": "city", "lon": -123.12, "lat": 49.28},
            {"id": "4", "name": "ウィニペグ", "yomi": "うぃにぺぐ", "alt": [], "kind": "都市", "mode": "city", "lon": -97.14, "lat": 49.90, "check": True},
            {"id": "5", "name": "モントリオール", "yomi": "もんとりおーる", "alt": [], "kind": "都市", "mode": "city", "lon": -73.57, "lat": 45.50, "check": True},
            {"id": "6", "name": "オタワ", "yomi": "おたわ", "alt": [], "kind": "都市", "mode": "city", "lon": -75.70, "lat": 45.42, "check": True},
            {"id": "7", "name": "トロント", "yomi": "とろんと", "alt": [], "kind": "都市", "mode": "city", "lon": -79.38, "lat": 43.65, "check": True},
            {"id": "8", "name": "ボストン", "yomi": "ぼすとん", "alt": [], "kind": "都市", "mode": "city", "lon": -71.06, "lat": 42.36, "check": True},
            {"id": "9", "name": "ニューヨーク", "yomi": "にゅーよーく", "alt": [], "kind": "都市", "mode": "city", "lon": -74.01, "lat": 40.71},
            {"id": "10", "name": "ワシントンD.C.", "yomi": "わしんとん", "alt": ["ワシントン"], "kind": "都市", "mode": "city", "lon": -77.04, "lat": 38.91, "check": True},
            {"id": "11", "name": "ピッツバーグ", "yomi": "ぴっつばーぐ", "alt": [], "kind": "都市", "res": "鉄鋼", "mode": "city", "lon": -79.996, "lat": 40.44, "check": True},
            {"id": "12", "name": "デトロイト", "yomi": "でとろいと", "alt": [], "kind": "都市", "res": "自動車", "mode": "city", "lon": -83.05, "lat": 42.33, "check": True},
            {"id": "13", "name": "シカゴ", "yomi": "しかご", "alt": [], "kind": "都市", "mode": "city", "lon": -87.63, "lat": 41.88},
            {"id": "14", "name": "セントルイス", "yomi": "せんとるいす", "alt": [], "kind": "都市", "mode": "city", "lon": -90.20, "lat": 38.63, "check": True},
            {"id": "15", "name": "ダラス", "yomi": "だらす", "alt": [], "kind": "都市", "mode": "city", "lon": -96.80, "lat": 32.78, "check": True},
            {"id": "16", "name": "アトランタ", "yomi": "あとらんた", "alt": [], "kind": "都市", "mode": "city", "lon": -84.39, "lat": 33.75, "check": True},
            {"id": "17", "name": "ニューオーリンズ", "yomi": "にゅーおーりんず", "alt": [], "kind": "都市", "mode": "city", "lon": -90.07, "lat": 29.95, "check": True},
            {"id": "18", "name": "マイアミ", "yomi": "まいあみ", "alt": [], "kind": "都市", "mode": "city", "lon": -80.19, "lat": 25.76},
            {"id": "19", "name": "ヒューストン", "yomi": "ひゅーすとん", "alt": [], "kind": "都市", "res": "石油", "mode": "city", "lon": -95.37, "lat": 29.76, "check": True},
            {"id": "20", "name": "サンアントニオ", "yomi": "さんあんとにお", "alt": [], "kind": "都市", "mode": "city", "lon": -98.49, "lat": 29.42, "check": True},
            {"id": "21", "name": "デンバー", "yomi": "でんばー", "alt": [], "kind": "都市", "mode": "city", "lon": -104.99, "lat": 39.74, "check": True},
            {"id": "22", "name": "シアトル", "yomi": "しあとる", "alt": [], "kind": "都市", "mode": "city", "lon": -122.33, "lat": 47.61},
            {"id": "23", "name": "サンフランシスコ", "yomi": "さんふらんしすこ", "alt": [], "kind": "都市", "mode": "city", "lon": -122.42, "lat": 37.77},
            {"id": "24", "name": "ロサンゼルス", "yomi": "ろさんぜるす", "alt": [], "kind": "都市", "mode": "city", "lon": -118.24, "lat": 34.05},
            {"id": "25", "name": "サンディエゴ", "yomi": "さんでぃえご", "alt": [], "kind": "都市", "mode": "city", "lon": -117.16, "lat": 32.72, "check": True},
            {"id": "26", "name": "ラスベガス", "yomi": "らすべがす", "alt": [], "kind": "都市", "mode": "city", "lon": -115.14, "lat": 36.17, "check": True},
            {"id": "27", "name": "フェニックス", "yomi": "ふぇにっくす", "alt": [], "kind": "都市", "mode": "city", "lon": -112.07, "lat": 33.45, "check": True},
            {"id": "28", "name": "エルパソ", "yomi": "えるぱそ", "alt": [], "kind": "都市", "mode": "city", "lon": -106.49, "lat": 31.76, "check": True},
            {"id": "29", "name": "メキシコシティ", "yomi": "めきしこしてぃ", "alt": [], "kind": "都市", "mode": "city", "lon": -99.13, "lat": 19.43},
            {"id": "30", "name": "ハバナ", "yomi": "はばな", "alt": [], "kind": "都市", "mode": "city", "lon": -82.38, "lat": 23.11},
            {"id": "31", "name": "キングストン", "yomi": "きんぐすとん", "alt": [], "kind": "都市", "mode": "city", "lon": -76.79, "lat": 17.99, "check": True},
        ],
    },
    "oceania": {
        "title": "オセアニア",
        "bbox": (110.0, -48.0, 180.0, 5.0),
        "width": 700,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "東経140度", "yomi": "", "alt": ["140度", "140"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 140, "lon": 140.0, "lat": -46.0, "check": True},
            {"id": "い", "name": "南回帰線", "yomi": "みなみかいきせん", "alt": ["南緯23.4度"], "kind": "緯線", "mode": "grid", "axis": "lat", "deg": -23.4, "lon": 113.0, "lat": -23.4},
            {"id": "う", "name": "東経120度", "yomi": "", "alt": ["120度", "120"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 120, "lon": 120.0, "lat": -46.0, "check": True},
            {"id": "え", "name": "南緯20度", "yomi": "", "alt": ["20度", "20"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": -20, "lon": 113.0, "lat": -20.0, "check": True},
            {"id": "お", "name": "太平洋", "yomi": "たいへいよう", "alt": [], "kind": "海", "mode": "zone", "lon": 160.0, "lat": -10.0},
            {"id": "か", "name": "インド洋", "yomi": "いんどよう", "alt": [], "kind": "海", "mode": "zone", "lon": 112.0, "lat": -30.0},
            {"id": "き", "name": "タスマン海", "yomi": "たすまんかい", "alt": [], "kind": "海", "mode": "zone", "lon": 160.0, "lat": -38.0},
            {"id": "く", "name": "サンゴ海", "yomi": "さんごかい", "alt": ["珊瑚海"], "kind": "海", "mode": "zone", "lon": 154.0, "lat": -16.0},
            {"id": "け", "name": "バス海峡", "yomi": "ばすかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 146.0, "lat": -39.5, "check": True},
            {"id": "こ", "name": "クック海峡", "yomi": "くっくかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 174.5, "lat": -41.3, "check": True},
            {"id": "さ", "name": "タスマニア島", "yomi": "たすまにあとう", "alt": [], "kind": "島", "mode": "island", "lon": 146.6, "lat": -42.0},
            {"id": "し", "name": "ニューギニア島", "yomi": "にゅーぎにあとう", "alt": [], "kind": "島", "mode": "zone", "lon": 141.0, "lat": -5.5},
            {"id": "す", "name": "ニュージーランド北島", "yomi": "にゅーじーらんどきたじま", "alt": ["北島"], "kind": "島", "mode": "island", "lon": 175.5, "lat": -38.5, "check": True},
            {"id": "せ", "name": "ニュージーランド南島", "yomi": "にゅーじーらんどみなみじま", "alt": ["南島"], "kind": "島", "mode": "island", "lon": 170.5, "lat": -43.5, "check": True},
            {"id": "そ", "name": "ハワイ諸島", "yomi": "はわいしょとう", "alt": [], "kind": "諸島", "mode": "zone", "lon": 178.0, "lat": 3.0, "check": True},
            {"id": "た", "name": "ニューカレドニア島", "yomi": "にゅーかれどにあとう", "alt": [], "kind": "島", "mode": "island", "lon": 165.5, "lat": -21.3, "check": True},
            {"id": "つ", "name": "グレートバリアリーフ", "yomi": "ぐれーとばりありーふ", "alt": ["大堡礁"], "kind": "地形", "mode": "zone", "lon": 147.0, "lat": -18.0},
            {"id": "て", "name": "グレートディバイディング山脈", "yomi": "ぐれーとでぃばいでぃんぐさんみゃく", "alt": ["大分水嶺"], "kind": "山脈", "mode": "zone", "lon": 149.0, "lat": -32.0},
            {"id": "と", "name": "ヨーク岬", "yomi": "よーくみさき", "alt": ["ケープヨーク"], "kind": "岬", "mode": "zone", "lon": 142.5, "lat": -10.7},
            {"id": "な", "name": "マリー川", "yomi": "まりーがわ", "alt": ["マレー川"], "kind": "川", "mode": "river", "match": ["murray"], "lon": 142.0, "lat": -34.5, "check": True},
            {"id": "に", "name": "ダーリング川", "yomi": "だーりんぐがわ", "alt": [], "kind": "川", "mode": "river", "match": ["darling"], "lon": 145.0, "lat": -31.0, "check": True},
            {"id": "ぬ", "name": "エア湖", "yomi": "えあこ", "alt": ["エーア湖"], "kind": "湖", "mode": "zone", "lon": 137.3, "lat": -28.4},
            {"id": "ね", "name": "グレートサンディー砂漠", "yomi": "ぐれーとさんでぃーさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 124.0, "lat": -21.0, "check": True},
            {"id": "の", "name": "グレートビクトリア砂漠", "yomi": "ぐれーとびくとりあさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": 128.0, "lat": -28.0},
            {"id": "は", "name": "グレートアーテジアン盆地", "yomi": "ぐれーとあーてじあんぼんち", "alt": ["大鑽井盆地"], "kind": "盆地", "mode": "zone", "lon": 143.0, "lat": -25.0, "check": True},
            {"id": "ひ", "name": "ナラボー平原", "yomi": "ならぼーへいげん", "alt": [], "kind": "平原", "mode": "zone", "lon": 128.0, "lat": -31.5, "check": True},
            {"id": "ふ", "name": "サザンアルプス山脈", "yomi": "さざんあるぷすさんみゃく", "alt": ["サザンアルプス"], "kind": "山脈", "mode": "zone", "lon": 170.2, "lat": -43.5, "check": True},
            {"id": "a", "name": "マウントアイザ", "yomi": "まうんとあいざ", "alt": ["マウントアイザ鉱山"], "kind": "都市", "res": "鉛・亜鉛", "mode": "zone", "lon": 139.5, "lat": -20.7, "check": True},
            {"id": "b", "name": "マウントホエールバック", "yomi": "まうんとほえーるばっく", "alt": ["ピルバラ"], "kind": "都市", "res": "鉄鉱石", "mode": "zone", "lon": 119.7, "lat": -23.4, "check": True},
            {"id": "c", "name": "カルグーリー", "yomi": "かるぐーりー", "alt": [], "kind": "都市", "res": "金", "mode": "city", "lon": 121.47, "lat": -30.75, "check": True},
            {"id": "d", "name": "ボーエン", "yomi": "ぼーえん", "alt": ["モウラ炭田"], "kind": "都市", "res": "石炭", "mode": "zone", "lon": 148.0, "lat": -21.5, "check": True},
            {"id": "1", "name": "ダーウィン", "yomi": "だーうぃん", "alt": [], "kind": "都市", "mode": "city", "lon": 130.84, "lat": -12.46},
            {"id": "2", "name": "ケアンズ", "yomi": "けあんず", "alt": [], "kind": "都市", "mode": "city", "lon": 145.77, "lat": -16.92, "check": True},
            {"id": "3", "name": "ポートモレスビー", "yomi": "ぽーともれすびー", "alt": [], "kind": "都市", "mode": "city", "lon": 147.18, "lat": -9.44, "check": True},
            {"id": "4", "name": "アリススプリングス", "yomi": "ありすすぷりんぐす", "alt": [], "kind": "都市", "mode": "city", "lon": 133.88, "lat": -23.70, "check": True},
            {"id": "5", "name": "ウルル", "yomi": "うるる", "alt": ["エアーズロック"], "kind": "地形", "mode": "zone", "lon": 131.04, "lat": -25.34},
            {"id": "6", "name": "ブリズベン", "yomi": "ぶりずべん", "alt": [], "kind": "都市", "mode": "city", "lon": 153.03, "lat": -27.47},
            {"id": "7", "name": "ニューカッスル", "yomi": "にゅーかっする", "alt": [], "kind": "都市", "res": "石炭", "mode": "city", "lon": 151.78, "lat": -32.93, "check": True},
            {"id": "8", "name": "シドニー", "yomi": "しどにー", "alt": [], "kind": "都市", "mode": "city", "lon": 151.21, "lat": -33.87},
            {"id": "9", "name": "キャンベラ", "yomi": "きゃんべら", "alt": [], "kind": "都市", "mode": "city", "lon": 149.13, "lat": -35.28},
            {"id": "10", "name": "メルボルン", "yomi": "めるぼるん", "alt": [], "kind": "都市", "mode": "city", "lon": 144.96, "lat": -37.81},
            {"id": "11", "name": "アデレード", "yomi": "あでれーど", "alt": [], "kind": "都市", "mode": "city", "lon": 138.60, "lat": -34.93, "check": True},
            {"id": "12", "name": "パース", "yomi": "ぱーす", "alt": [], "kind": "都市", "mode": "city", "lon": 115.86, "lat": -31.95},
            {"id": "13", "name": "ジオールドトン", "yomi": "じおーるどとん", "alt": ["ジェラルトン"], "kind": "都市", "mode": "city", "lon": 114.61, "lat": -28.77, "check": True},
            {"id": "14", "name": "ポートヘッドランド", "yomi": "ぽーとへっどらんど", "alt": [], "kind": "都市", "res": "鉄鉱石積出", "mode": "city", "lon": 118.60, "lat": -20.31, "check": True},
            {"id": "15", "name": "オークランド", "yomi": "おーくらんど", "alt": [], "kind": "都市", "mode": "city", "lon": 174.76, "lat": -36.85, "check": True},
            {"id": "16", "name": "クライストチャーチ", "yomi": "くらいすとちゃーち", "alt": [], "kind": "都市", "mode": "city", "lon": 172.64, "lat": -43.53, "check": True},
            {"id": "17", "name": "ウェリントン", "yomi": "うぇりんとん", "alt": [], "kind": "都市", "mode": "city", "lon": 174.78, "lat": -41.29},
        ],
    },
    "samerica": {
        "title": "南アメリカ",
        "bbox": (-92.0, -56.0, -32.0, 25.0),
        "width": 620,
        "simplify_px": 0.6,
        "parts": [
            {"id": "あ", "name": "北緯10度", "yomi": "", "alt": ["10度", "10"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 10, "lon": -40.0, "lat": 10.0, "check": True},
            {"id": "い", "name": "赤道", "yomi": "せきどう", "alt": ["0度", "緯度0度"], "kind": "緯線", "mode": "grid", "axis": "lat", "deg": 0, "lon": -35.0, "lat": 0.0},
            {"id": "う", "name": "南緯20度", "yomi": "", "alt": ["20度", "20"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": -20, "lon": -34.0, "lat": -20.0, "check": True},
            {"id": "え", "name": "西経40度", "yomi": "", "alt": ["40度", "40"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": -40, "lon": -40.0, "lat": 12.0, "check": True},
            {"id": "お", "name": "カリブ海", "yomi": "かりぶかい", "alt": [], "kind": "海", "mode": "zone", "lon": -73.0, "lat": 13.0},
            {"id": "か", "name": "大西洋", "yomi": "たいせいよう", "alt": [], "kind": "海", "mode": "zone", "lon": -40.0, "lat": 5.0},
            {"id": "き", "name": "太平洋", "yomi": "たいへいよう", "alt": [], "kind": "海", "mode": "zone", "lon": -85.0, "lat": -15.0},
            {"id": "く", "name": "ペルー海流", "yomi": "ぺるーかいりゅう", "alt": ["フンボルト海流"], "kind": "海流", "res": "寒流", "mode": "zone", "lon": -78.0, "lat": -20.0},
            {"id": "け", "name": "ガラパゴス諸島", "yomi": "がらぱごすしょとう", "alt": [], "kind": "諸島", "mode": "island", "lon": -91.1, "lat": -0.45, "check": True},
            {"id": "こ", "name": "トリニダード島", "yomi": "とりにだーどとう", "alt": [], "kind": "島", "mode": "island", "lon": -61.3, "lat": 10.4, "check": True},
            {"id": "さ", "name": "小アンティル諸島", "yomi": "しょうあんてぃるしょとう", "alt": [], "kind": "諸島", "mode": "zone", "lon": -61.5, "lat": 15.0, "check": True},
            {"id": "し", "name": "フォークランド諸島", "yomi": "ふぉーくらんどしょとう", "alt": ["マルビナス諸島"], "kind": "諸島", "mode": "island", "lon": -59.0, "lat": -51.7, "check": True},
            {"id": "す", "name": "フエゴ島", "yomi": "ふえごとう", "alt": ["ティエラデルフエゴ"], "kind": "島", "mode": "island", "lon": -68.5, "lat": -54.0, "check": True},
            {"id": "せ", "name": "チロエ諸島", "yomi": "ちろえしょとう", "alt": ["チロエ島"], "kind": "諸島", "mode": "island", "lon": -73.8, "lat": -42.6, "check": True},
            {"id": "そ", "name": "オリノコ川", "yomi": "おりのこがわ", "alt": [], "kind": "川", "mode": "river", "match": ["orinoco"], "lon": -65.0, "lat": 8.0},
            {"id": "た", "name": "パラナ川", "yomi": "ぱらながわ", "alt": [], "kind": "川", "mode": "river", "match": ["parana", "paraná"], "lon": -58.0, "lat": -27.0},
            {"id": "ち", "name": "ラプラタ川", "yomi": "らぷらたがわ", "alt": [], "kind": "川", "mode": "river", "match": ["la plata", "de la plata"], "lon": -57.5, "lat": -34.5, "check": True},
            {"id": "つ", "name": "アマゾン川", "yomi": "あまぞんがわ", "alt": [], "kind": "川", "mode": "river", "match": ["amazon", "amazonas"], "lon": -60.0, "lat": -3.0},
            {"id": "て", "name": "チチカカ湖", "yomi": "ちちかかこ", "alt": [], "kind": "湖", "mode": "zone", "lon": -69.3, "lat": -15.8},
            {"id": "と", "name": "アンデス山脈", "yomi": "あんですさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": -70.0, "lat": -30.0},
            {"id": "な", "name": "ギアナ高地", "yomi": "ぎあなこうち", "alt": [], "kind": "高地", "mode": "zone", "lon": -62.0, "lat": 5.0},
            {"id": "に", "name": "アマゾン盆地", "yomi": "あまぞんぼんち", "alt": ["セルバ"], "kind": "盆地", "mode": "zone", "lon": -65.0, "lat": -4.0},
            {"id": "ぬ", "name": "ブラジル高原", "yomi": "ぶらじるこうげん", "alt": [], "kind": "高原", "mode": "zone", "lon": -47.0, "lat": -15.0},
            {"id": "ね", "name": "リャノ", "yomi": "りゃの", "alt": [], "kind": "地方", "mode": "zone", "lon": -68.0, "lat": 6.5, "check": True},
            {"id": "の", "name": "カンポ", "yomi": "かんぽ", "alt": ["カンポセラード"], "kind": "地方", "mode": "zone", "lon": -50.0, "lat": -12.0, "check": True},
            {"id": "は", "name": "グランチャコ", "yomi": "ぐらんちゃこ", "alt": ["チャコ"], "kind": "地方", "mode": "zone", "lon": -61.0, "lat": -23.0, "check": True},
            {"id": "ひ", "name": "パンパ", "yomi": "ぱんぱ", "alt": [], "kind": "地方", "mode": "zone", "lon": -62.0, "lat": -35.0},
            {"id": "ふ", "name": "パタゴニア", "yomi": "ぱたごにあ", "alt": [], "kind": "地方", "mode": "zone", "lon": -69.0, "lat": -45.0},
            {"id": "へ", "name": "アタカマ砂漠", "yomi": "あたかまさばく", "alt": [], "kind": "砂漠", "mode": "zone", "lon": -69.5, "lat": -23.5},
            {"id": "ほ", "name": "アコンカグア山", "yomi": "あこんかぐあさん", "alt": [], "kind": "山", "mode": "zone", "lon": -70.01, "lat": -32.65},
            {"id": "ま", "name": "マゼラン海峡", "yomi": "まぜらんかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": -71.0, "lat": -53.5},
            {"id": "a", "name": "シウダーグアヤナ", "yomi": "しうだーぐあやな", "alt": ["セロボリバル"], "kind": "都市", "res": "鉄", "mode": "zone", "lon": -63.0, "lat": 6.5, "check": True},
            {"id": "b", "name": "カラジャス", "yomi": "からじゃす", "alt": [], "kind": "都市", "res": "鉄", "mode": "zone", "lon": -50.2, "lat": -6.0, "check": True},
            {"id": "c", "name": "ポトシ", "yomi": "ぽとし", "alt": [], "kind": "都市", "res": "銀", "mode": "zone", "lon": -65.75, "lat": -19.58, "check": True},
            {"id": "d", "name": "チュキカマタ", "yomi": "ちゅきかまた", "alt": [], "kind": "都市", "res": "銅", "mode": "zone", "lon": -68.9, "lat": -22.3, "check": True},
            {"id": "e", "name": "エルテニエンテ", "yomi": "えるてにえんて", "alt": [], "kind": "都市", "res": "銅", "mode": "zone", "lon": -70.35, "lat": -34.08, "check": True},
            {"id": "1", "name": "ハバナ", "yomi": "はばな", "alt": [], "kind": "都市", "mode": "city", "lon": -82.38, "lat": 23.11, "check": True},
            {"id": "2", "name": "キングストン", "yomi": "きんぐすとん", "alt": [], "kind": "都市", "mode": "city", "lon": -76.79, "lat": 17.99, "check": True},
            {"id": "3", "name": "ポルトープランス", "yomi": "ぽるとーぷらんす", "alt": [], "kind": "都市", "mode": "city", "lon": -72.34, "lat": 18.59, "check": True},
            {"id": "4", "name": "サントドミンゴ", "yomi": "さんとどみんご", "alt": [], "kind": "都市", "mode": "city", "lon": -69.93, "lat": 18.49, "check": True},
            {"id": "5", "name": "パナマシティ", "yomi": "ぱなましてぃ", "alt": ["パナマ"], "kind": "都市", "mode": "city", "lon": -79.52, "lat": 8.98, "check": True},
            {"id": "6", "name": "ボゴタ", "yomi": "ぼごた", "alt": [], "kind": "都市", "mode": "city", "lon": -74.07, "lat": 4.71},
            {"id": "7", "name": "メデジン", "yomi": "めでじん", "alt": [], "kind": "都市", "mode": "city", "lon": -75.56, "lat": 6.24, "check": True},
            {"id": "8", "name": "カラカス", "yomi": "からかす", "alt": [], "kind": "都市", "mode": "city", "lon": -66.90, "lat": 10.49},
            {"id": "9", "name": "ジョージタウン", "yomi": "じょーじたうん", "alt": [], "kind": "都市", "mode": "city", "lon": -58.16, "lat": 6.80, "check": True},
            {"id": "10", "name": "マナオス", "yomi": "まなおす", "alt": ["マナウス"], "kind": "都市", "mode": "city", "lon": -60.03, "lat": -3.12},
            {"id": "11", "name": "ブラジリア", "yomi": "ぶらじりあ", "alt": [], "kind": "都市", "mode": "city", "lon": -47.88, "lat": -15.79},
            {"id": "12", "name": "レシフェ", "yomi": "れしふぇ", "alt": [], "kind": "都市", "mode": "city", "lon": -34.88, "lat": -8.05, "check": True},
            {"id": "13", "name": "リオデジャネイロ", "yomi": "りおでじゃねいろ", "alt": [], "kind": "都市", "mode": "city", "lon": -43.20, "lat": -22.91},
            {"id": "14", "name": "サンパウロ", "yomi": "さんぱうろ", "alt": [], "kind": "都市", "mode": "city", "lon": -46.63, "lat": -23.55},
            {"id": "15", "name": "アスンシオン", "yomi": "あすんしおん", "alt": [], "kind": "都市", "mode": "city", "lon": -57.58, "lat": -25.28, "check": True},
            {"id": "16", "name": "モンテビデオ", "yomi": "もんてびでお", "alt": [], "kind": "都市", "mode": "city", "lon": -56.16, "lat": -34.90, "check": True},
            {"id": "17", "name": "ブエノスアイレス", "yomi": "ぶえのすあいれす", "alt": [], "kind": "都市", "mode": "city", "lon": -58.38, "lat": -34.60},
            {"id": "18", "name": "サンティアゴ", "yomi": "さんてぃあご", "alt": [], "kind": "都市", "mode": "city", "lon": -70.65, "lat": -33.46},
            {"id": "19", "name": "ラパス", "yomi": "らぱす", "alt": [], "kind": "都市", "mode": "city", "lon": -68.15, "lat": -16.50},
            {"id": "20", "name": "クスコ", "yomi": "くすこ", "alt": [], "kind": "都市", "mode": "city", "lon": -71.97, "lat": -13.53, "check": True},
            {"id": "21", "name": "リマ", "yomi": "りま", "alt": [], "kind": "都市", "mode": "city", "lon": -77.04, "lat": -12.05},
            {"id": "22", "name": "キト", "yomi": "きと", "alt": [], "kind": "都市", "mode": "city", "lon": -78.47, "lat": -0.18},
        ],
    },
    "europe": {
        "title": "ヨーロッパ",
        "bbox": (-25.0, 34.0, 45.0, 71.0),
        "width": 700,
        "simplify_px": 0.5,
        "parts": [
            {"id": "あ", "name": "東経15度", "yomi": "", "alt": ["15度", "15"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 15, "lon": 15.0, "lat": 69.5, "check": True},
            {"id": "い", "name": "東経30度", "yomi": "", "alt": ["30度", "30"], "kind": "経度", "mode": "grid", "axis": "lon", "deg": 30, "lon": 30.0, "lat": 68.0, "check": True},
            {"id": "う", "name": "北緯60度", "yomi": "", "alt": ["60度", "60"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 60, "lon": -22.0, "lat": 60.0, "check": True},
            {"id": "え", "name": "北緯50度", "yomi": "", "alt": ["50度", "50"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 50, "lon": -10.0, "lat": 50.0, "check": True},
            {"id": "お", "name": "北緯40度", "yomi": "", "alt": ["40度", "40"], "kind": "緯度", "mode": "grid", "axis": "lat", "deg": 40, "lon": -9.0, "lat": 40.0, "check": True},
            {"id": "か", "name": "ボスニア湾", "yomi": "ぼすにあわん", "alt": [], "kind": "湾", "mode": "zone", "lon": 20.5, "lat": 63.0, "check": True},
            {"id": "き", "name": "バルト海", "yomi": "ばるとかい", "alt": [], "kind": "海", "mode": "zone", "lon": 19.0, "lat": 56.5},
            {"id": "く", "name": "北海", "yomi": "ほっかい", "alt": [], "kind": "海", "mode": "zone", "lon": 3.0, "lat": 56.0},
            {"id": "け", "name": "ノルウェー海", "yomi": "のるうぇーかい", "alt": [], "kind": "海", "mode": "zone", "lon": -3.0, "lat": 66.0},
            {"id": "こ", "name": "ドーバー海峡", "yomi": "どーばーかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": 1.4, "lat": 50.9, "check": True},
            {"id": "さ", "name": "ビスケー湾", "yomi": "びすけーわん", "alt": [], "kind": "湾", "mode": "zone", "lon": -5.0, "lat": 45.5},
            {"id": "し", "name": "ジブラルタル海峡", "yomi": "じぶらるたるかいきょう", "alt": [], "kind": "海峡", "mode": "zone", "lon": -5.6, "lat": 35.95},
            {"id": "す", "name": "地中海", "yomi": "ちちゅうかい", "alt": [], "kind": "海", "mode": "zone", "lon": 15.0, "lat": 38.0},
            {"id": "せ", "name": "エーゲ海", "yomi": "えーげかい", "alt": [], "kind": "海", "mode": "zone", "lon": 25.0, "lat": 38.5},
            {"id": "そ", "name": "黒海", "yomi": "こっかい", "alt": [], "kind": "海", "mode": "zone", "lon": 34.0, "lat": 43.5},
            {"id": "た", "name": "コラ半島", "yomi": "こらはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 37.0, "lat": 67.5},
            {"id": "ち", "name": "アイルランド島", "yomi": "あいるらんどとう", "alt": [], "kind": "島", "mode": "island", "lon": -8.0, "lat": 53.3},
            {"id": "つ", "name": "グレートブリテン島", "yomi": "ぐれーとぶりてんとう", "alt": ["ブリテン島"], "kind": "島", "mode": "island", "lon": -1.5, "lat": 53.0},
            {"id": "て", "name": "アイスランド", "yomi": "あいすらんど", "alt": [], "kind": "島", "mode": "island", "lon": -19.0, "lat": 64.9},
            {"id": "と", "name": "ユトランド半島", "yomi": "ゆとらんどはんとう", "alt": ["ユラン半島"], "kind": "半島", "mode": "zone", "lon": 9.3, "lat": 56.2},
            {"id": "な", "name": "イベリア半島", "yomi": "いべりあはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": -4.0, "lat": 40.0},
            {"id": "に", "name": "スカンディナビア半島", "yomi": "すかんでぃなびあはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 15.0, "lat": 63.0},
            {"id": "ぬ", "name": "バルカン半島", "yomi": "ばるかんはんとう", "alt": [], "kind": "半島", "mode": "zone", "lon": 22.0, "lat": 42.5},
            {"id": "ね", "name": "ライン川", "yomi": "らいんがわ", "alt": [], "kind": "川", "mode": "river", "match": ["rhine", "rhein"], "lon": 7.5, "lat": 50.5},
            {"id": "の", "name": "セーヌ川", "yomi": "せーぬがわ", "alt": [], "kind": "川", "mode": "river", "match": ["seine"], "lon": 2.5, "lat": 48.8, "check": True},
            {"id": "は", "name": "エルベ川", "yomi": "えるべがわ", "alt": [], "kind": "川", "mode": "river", "match": ["elbe"], "lon": 11.5, "lat": 53.0},
            {"id": "ひ", "name": "ロアール川", "yomi": "ろあーるがわ", "alt": ["ロワール川"], "kind": "川", "mode": "river", "match": ["loire"], "lon": 0.5, "lat": 47.4, "check": True},
            {"id": "ふ", "name": "ローヌ川", "yomi": "ろーぬがわ", "alt": [], "kind": "川", "mode": "river", "match": ["rhone", "rhône"], "lon": 4.8, "lat": 44.5, "check": True},
            {"id": "へ", "name": "ドナウ川", "yomi": "どなうがわ", "alt": [], "kind": "川", "mode": "river", "match": ["danube", "donau"], "lon": 20.0, "lat": 45.0},
            {"id": "ほ", "name": "ボルガ川", "yomi": "ぼるががわ", "alt": ["ヴォルガ川"], "kind": "川", "mode": "river", "match": ["volga"], "lon": 45.0, "lat": 50.0, "check": True},
            {"id": "ま", "name": "アルプス山脈", "yomi": "あるぷすさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 10.0, "lat": 46.5},
            {"id": "み", "name": "ピレネー山脈", "yomi": "ぴれねーさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 0.5, "lat": 42.7},
            {"id": "む", "name": "アペニン山脈", "yomi": "あぺにんさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 13.5, "lat": 42.5},
            {"id": "め", "name": "スカンディナビア山脈", "yomi": "すかんでぃなびあさんみゃく", "alt": [], "kind": "山脈", "mode": "zone", "lon": 13.0, "lat": 65.0},
            {"id": "や", "name": "北ヨーロッパ平原", "yomi": "きたよーろっぱへいげん", "alt": [], "kind": "平原", "mode": "zone", "lon": 18.0, "lat": 52.5},
            {"id": "1", "name": "レイキャビク", "yomi": "れいきゃびく", "alt": [], "kind": "都市", "mode": "city", "lon": -21.94, "lat": 64.15},
            {"id": "2", "name": "ダブリン", "yomi": "だぶりん", "alt": [], "kind": "都市", "mode": "city", "lon": -6.26, "lat": 53.35, "check": True},
            {"id": "3", "name": "グラスゴー", "yomi": "ぐらすごー", "alt": [], "kind": "都市", "mode": "city", "lon": -4.25, "lat": 55.86, "check": True},
            {"id": "4", "name": "マンチェスター", "yomi": "まんちぇすたー", "alt": [], "kind": "都市", "mode": "city", "lon": -2.24, "lat": 53.48, "check": True},
            {"id": "5", "name": "ロンドン", "yomi": "ろんどん", "alt": [], "kind": "都市", "mode": "city", "lon": -0.13, "lat": 51.51},
            {"id": "6", "name": "パリ", "yomi": "ぱり", "alt": [], "kind": "都市", "mode": "city", "lon": 2.35, "lat": 48.86},
            {"id": "7", "name": "リスボン", "yomi": "りすぼん", "alt": [], "kind": "都市", "mode": "city", "lon": -9.14, "lat": 38.72},
            {"id": "8", "name": "マドリード", "yomi": "まどりーど", "alt": ["マドリッド"], "kind": "都市", "mode": "city", "lon": -3.70, "lat": 40.42},
            {"id": "9", "name": "バルセロナ", "yomi": "ばるせろな", "alt": [], "kind": "都市", "mode": "city", "lon": 2.17, "lat": 41.39, "check": True},
            {"id": "10", "name": "マルセイユ", "yomi": "まるせいゆ", "alt": [], "kind": "都市", "mode": "city", "lon": 5.37, "lat": 43.30, "check": True},
            {"id": "11", "name": "ボルドー", "yomi": "ぼるどー", "alt": [], "kind": "都市", "mode": "city", "lon": -0.58, "lat": 44.84, "check": True},
            {"id": "12", "name": "リヨン", "yomi": "りよん", "alt": [], "kind": "都市", "mode": "city", "lon": 4.83, "lat": 45.76, "check": True},
            {"id": "13", "name": "アムステルダム", "yomi": "あむすてるだむ", "alt": [], "kind": "都市", "mode": "city", "lon": 4.90, "lat": 52.37, "check": True},
            {"id": "14", "name": "ブリュッセル", "yomi": "ぶりゅっせる", "alt": [], "kind": "都市", "mode": "city", "lon": 4.35, "lat": 50.85, "check": True},
            {"id": "15", "name": "リヨン", "yomi": "りよん", "alt": [], "kind": "都市", "mode": "city", "lon": 4.83, "lat": 45.76},
            {"id": "16", "name": "マルセイユ", "yomi": "まるせいゆ", "alt": [], "kind": "都市", "mode": "city", "lon": 5.37, "lat": 43.30, "check": True},
            {"id": "17", "name": "ジェノバ", "yomi": "じぇのば", "alt": ["ジェノヴァ"], "kind": "都市", "mode": "city", "lon": 8.93, "lat": 44.41, "check": True},
            {"id": "18", "name": "ミラノ", "yomi": "みらの", "alt": [], "kind": "都市", "mode": "city", "lon": 9.19, "lat": 45.46},
            {"id": "19", "name": "ローマ", "yomi": "ろーま", "alt": [], "kind": "都市", "mode": "city", "lon": 12.50, "lat": 41.90},
            {"id": "20", "name": "ナポリ", "yomi": "なぽり", "alt": [], "kind": "都市", "mode": "city", "lon": 14.27, "lat": 40.85, "check": True},
            {"id": "21", "name": "ハンブルク", "yomi": "はんぶるく", "alt": [], "kind": "都市", "mode": "city", "lon": 9.99, "lat": 53.55},
            {"id": "22", "name": "ケルン", "yomi": "けるん", "alt": [], "kind": "都市", "mode": "city", "lon": 6.96, "lat": 50.94, "check": True},
            {"id": "23", "name": "フランクフルト", "yomi": "ふらんくふると", "alt": [], "kind": "都市", "mode": "city", "lon": 8.68, "lat": 50.11, "check": True},
            {"id": "24", "name": "ベルリン", "yomi": "べるりん", "alt": [], "kind": "都市", "mode": "city", "lon": 13.40, "lat": 52.52},
            {"id": "25", "name": "ミュンヘン", "yomi": "みゅんへん", "alt": [], "kind": "都市", "mode": "city", "lon": 11.58, "lat": 48.14, "check": True},
            {"id": "26", "name": "プラハ", "yomi": "ぷらは", "alt": [], "kind": "都市", "mode": "city", "lon": 14.42, "lat": 50.08, "check": True},
            {"id": "27", "name": "ウィーン", "yomi": "うぃーん", "alt": [], "kind": "都市", "mode": "city", "lon": 16.37, "lat": 48.21},
            {"id": "28", "name": "ブダペスト", "yomi": "ぶだぺすと", "alt": [], "kind": "都市", "mode": "city", "lon": 19.04, "lat": 47.50, "check": True},
            {"id": "29", "name": "ワルシャワ", "yomi": "わるしゃわ", "alt": [], "kind": "都市", "mode": "city", "lon": 21.01, "lat": 52.23},
            {"id": "30", "name": "コペンハーゲン", "yomi": "こぺんはーげん", "alt": [], "kind": "都市", "mode": "city", "lon": 12.57, "lat": 55.68, "check": True},
            {"id": "31", "name": "オスロ", "yomi": "おすろ", "alt": [], "kind": "都市", "mode": "city", "lon": 10.75, "lat": 59.91, "check": True},
            {"id": "32", "name": "ストックホルム", "yomi": "すとっくほるむ", "alt": [], "kind": "都市", "mode": "city", "lon": 18.07, "lat": 59.33},
            {"id": "33", "name": "ヘルシンキ", "yomi": "へるしんき", "alt": [], "kind": "都市", "mode": "city", "lon": 24.94, "lat": 60.17},
            {"id": "34", "name": "ベオグラード", "yomi": "べおぐらーど", "alt": [], "kind": "都市", "mode": "city", "lon": 20.46, "lat": 44.79, "check": True},
            {"id": "35", "name": "ソフィア", "yomi": "そふぃあ", "alt": [], "kind": "都市", "mode": "city", "lon": 23.32, "lat": 42.70, "check": True},
            {"id": "36", "name": "ザグレブ", "yomi": "ざぐれぶ", "alt": [], "kind": "都市", "mode": "city", "lon": 15.98, "lat": 45.81, "check": True},
            {"id": "37", "name": "アテネ", "yomi": "あてね", "alt": [], "kind": "都市", "mode": "city", "lon": 23.73, "lat": 37.98},
            {"id": "38", "name": "ブカレスト", "yomi": "ぶかれすと", "alt": [], "kind": "都市", "mode": "city", "lon": 26.10, "lat": 44.43, "check": True},
            {"id": "39", "name": "キシナウ", "yomi": "きしなう", "alt": ["キシニョフ"], "kind": "都市", "mode": "city", "lon": 28.86, "lat": 47.01, "check": True},
            {"id": "40", "name": "ブラチスラバ", "yomi": "ぶらちすらば", "alt": [], "kind": "都市", "mode": "city", "lon": 17.11, "lat": 48.15, "check": True},
            {"id": "41", "name": "クラクフ", "yomi": "くらくふ", "alt": [], "kind": "都市", "mode": "city", "lon": 19.94, "lat": 50.06, "check": True},
            {"id": "42", "name": "ワルシャワ", "yomi": "わるしゃわ", "alt": [], "kind": "都市", "mode": "city", "lon": 21.01, "lat": 52.23, "check": True},
            {"id": "43", "name": "ビリニュス", "yomi": "びりにゅす", "alt": [], "kind": "都市", "mode": "city", "lon": 25.28, "lat": 54.69, "check": True},
            {"id": "44", "name": "ミンスク", "yomi": "みんすく", "alt": [], "kind": "都市", "mode": "city", "lon": 27.57, "lat": 53.90, "check": True},
            {"id": "45", "name": "リガ", "yomi": "りが", "alt": [], "kind": "都市", "mode": "city", "lon": 24.11, "lat": 56.95, "check": True},
            {"id": "46", "name": "タリン", "yomi": "たりん", "alt": [], "kind": "都市", "mode": "city", "lon": 24.75, "lat": 59.44, "check": True},
            {"id": "47", "name": "サンクトペテルブルク", "yomi": "さんくとぺてるぶるく", "alt": ["ペテルブルグ"], "kind": "都市", "mode": "city", "lon": 30.31, "lat": 59.94, "check": True},
            {"id": "48", "name": "ストックホルム", "yomi": "すとっくほるむ", "alt": [], "kind": "都市", "mode": "city", "lon": 18.07, "lat": 59.33, "check": True},
            {"id": "49", "name": "オウル", "yomi": "おうる", "alt": [], "kind": "都市", "mode": "city", "lon": 25.47, "lat": 65.01, "check": True},
            {"id": "50", "name": "ベルゲン", "yomi": "べるげん", "alt": [], "kind": "都市", "mode": "city", "lon": 5.32, "lat": 60.39, "check": True},
            {"id": "51", "name": "オスロ", "yomi": "おすろ", "alt": [], "kind": "都市", "mode": "city", "lon": 10.75, "lat": 59.91, "check": True},
            {"id": "52", "name": "スタバンゲル", "yomi": "すたばんげる", "alt": ["スタヴァンゲル"], "kind": "都市", "mode": "city", "lon": 5.73, "lat": 58.97, "check": True},
            {"id": "53", "name": "ナルビク", "yomi": "なるびく", "alt": [], "kind": "都市", "res": "鉄鉱石積出", "mode": "city", "lon": 17.43, "lat": 68.44, "check": True},
            {"id": "54", "name": "キルナ", "yomi": "きるな", "alt": [], "kind": "都市", "res": "鉄", "mode": "city", "lon": 20.22, "lat": 67.86, "check": True},
        ],
    },
}

# ============================================================
# 河川フォールバック座標（Natural Earthでヒットしない/分割される川の保険）
#   経度,緯度 の粗いポリライン。データが引けなかった場合のみ描画する。
#   ざっくり流路（後で微調整可）。
# ============================================================
RIVER_FALLBACK = {
    "sea_ぬ": [  # チャオプラヤ川（sea）
        (99.9, 18.8), (100.1, 17.6), (100.2, 16.5),
        (100.1, 15.7), (100.5, 14.9), (100.5, 14.0), (100.55, 13.4),
    ],
    "sea_に": [  # エーヤワディー川（sea）
        (97.3, 25.5), (96.2, 23.8), (95.3, 21.9),
        (95.1, 20.1), (95.2, 18.5), (95.0, 17.0), (95.2, 16.0),
    ],
    "sea_の": [  # ホン川（sea）
        (103.0, 22.6), (104.0, 21.9), (105.0, 21.3), (106.0, 20.6), (106.5, 20.2),
    ],
    # --- 南アメリカ（samerica） ---
    "samerica_ち": [  # ラプラタ川
        (-58.5, -34.0), (-57.5, -34.6), (-56.5, -35.2), (-55.9, -35.7),
    ],
    # --- ヨーロッパ（europe） ---
    "europe_ね": [  # ライン川
        (8.5, 46.5), (7.6, 47.6), (8.2, 49.0), (7.6, 50.4), (6.9, 51.4), (6.1, 51.9), (4.5, 51.9),
    ],
    "europe_の": [  # セーヌ川
        (4.8, 47.7), (3.5, 48.4), (2.35, 48.86), (1.4, 49.1), (0.7, 49.4), (0.2, 49.5),
    ],
    "europe_は": [  # エルベ川
        (14.4, 50.6), (13.5, 51.4), (12.0, 52.2), (11.0, 53.1), (9.9, 53.5), (9.0, 53.9),
    ],
    "europe_ひ": [  # ロアール川
        (4.3, 44.9), (3.0, 46.5), (2.2, 47.4), (0.9, 47.4), (-0.5, 47.4), (-1.8, 47.3), (-2.1, 47.3),
    ],
    "europe_ふ": [  # ローヌ川
        (6.1, 46.2), (5.3, 45.8), (4.8, 45.2), (4.7, 44.3), (4.8, 43.7), (4.6, 43.3),
    ],
    "europe_へ": [  # ドナウ川
        (8.2, 48.1), (10.0, 48.7), (12.0, 48.8), (13.4, 48.6), (16.4, 48.1), (19.0, 47.5),
        (20.0, 46.0), (22.9, 44.6), (25.0, 44.0), (27.0, 44.2), (28.7, 45.2), (29.7, 45.2),
    ],
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
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return geom["coordinates"]
    return []


def lines_of(geom):
    t = geom.get("type")
    if t == "LineString":
        return [geom["coordinates"]]
    if t == "MultiLineString":
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
# マーカー種別（kind → CSSクラス／形状）
# ============================================================
MARKER_CLASS = {
    "都市": "m-city",
    "島": "m-island", "諸島": "m-island",
    "川": "m-river",
    "海": "m-sea", "湾": "m-sea", "海流": "m-sea", "海溝": "m-sea",
    "海峡": "m-strait", "運河": "m-strait",
    "山": "m-mountain", "山脈": "m-mountain", "峠": "m-mountain",
    "湖": "m-lake",
    "緯度": "m-grid", "経度": "m-grid", "緯線": "m-grid", "経線": "m-grid",
}


def marker_shape(kind_cls):
    """kind別クラスに応じたSVG図形（circle/rect/polygon）を返す。ヒット円は別途共通で描画する。"""
    if kind_cls == "m-mountain":
        return '<polygon class="dot" points="0,-5 4.3,3 -4.3,3"/>'
    if kind_cls == "m-strait":
        return '<rect class="dot" x="-3.3" y="-3.3" width="6.6" height="6.6" transform="rotate(45)"/>'
    if kind_cls == "m-grid":
        return '<rect class="dot" x="-2.6" y="-2.6" width="5.2" height="5.2"/>'
    if kind_cls == "m-sea":
        return '<circle class="dot" r="5"/>'
    if kind_cls == "m-river":
        return '<circle class="dot" r="3"/>'
    return '<circle class="dot" r="4"/>'


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
            fb = RIVER_FALLBACK.get(f"{region_key}_{part['id']}")
            if fb:
                for seg in clip_polyline([(lon, lat) for lon, lat in fb], clip_bbox):
                    pts = simplify([proj(x, y) for x, y in seg], tol)
                    if len(pts) < 2:
                        continue
                    river_svg.append(
                        f'<path class="river river-fb part-shape" data-part="{part["id"]}" d="{fmt_path(pts, close=False)}"/>'
                    )
                    matched += 1
                report.append(f"[代替] 河川フォールバック描画: {part['id']} {part['name']}（データ未ヒットのため手動座標）")
            else:
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
        if not (x0 <= part["lon"] <= x1 and y0 <= part["lat"] <= y1):
            report.append(f"[警告] bbox外のためマーカー省略: {part['id']} {part['name']} (lon={part['lon']}, lat={part['lat']})")
            continue
        mx, my = proj(part["lon"], part["lat"])
        kind_cls = MARKER_CLASS.get(part["kind"], "m-land")
        marker_svg.append(
            f'<g class="marker {kind_cls}" data-part="{part["id"]}" data-kind="{part["kind"]}" '
            f'transform="translate({mx:.1f},{my:.1f})">'
            f'<circle class="hit" r="16"/>{marker_shape(kind_cls)}</g>'
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
        ".m-river .dot{fill:#2f6690}"
        ".m-sea .dot{fill:#fff;stroke:#5aa0c6;stroke-width:2}"
        ".m-strait .dot{fill:#1a5276;stroke:#fff;stroke-width:1}"
        ".m-mountain .dot{fill:#8a5a2f;stroke:#fff;stroke-width:1}"
        ".m-lake .dot{fill:#7ec8e3}"
        ".m-island .dot{fill:#3f9142}"
        ".m-grid .dot{fill:#8e8e93;stroke:#fff;stroke-width:1}"
        ".m-land .dot{fill:#c9a878}"
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
