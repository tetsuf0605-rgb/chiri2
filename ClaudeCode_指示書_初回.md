# chiri2 初回実装指示書（Claude Code用）

前提: `chiri2_仕様書_v1.md` と共通ルール（`Webアプリ開発_共通ルール.md`）に従う。
成果物は単一 `index.html`＋PWA一式。vanilla JS・外部依存なし。

## 0. リポジトリ準備

- ローカル: `C:\Users\tetsu\OneDrive\アプリ開発\chiri2`
- 構成:
  ```
  chiri2/
    index.html
    icon.png            … 仮アイコンでよい（後日差し替え）
    manifest.webmanifest
    .nojekyll           … 最初に必ず追加
    tools/make_map.py   … 同梱の生成スクリプト
    build/              … スクリプト出力（コミットしてよい）
  ```
- git init〜初回pushは共通ルール§9の手順。ブランチ main。remote は
  `https://github.com/tetsuf0605-rgb/chiri2.git`（既存リポを流用しない。remote設定ミスに注意）。

## 1. 白地図の生成

```
python tools/make_map.py sea
```
- 初回のみネット接続が必要（Natural Earth 50m GeoJSONをDL、tools/cache にキャッシュ）。
- 出力: `build/map_sea.svg`（白地図）、`build/parts_sea.js`（問題データ）、`build/report_sea.txt`。
- **report_sea.txt を必ず確認**。`[警告]` がある場合（島ポリゴン未検出・河川未検出）は
  そのパーツはマーカーのみで動作する。警告内容をてつやに報告すること。
- SVGとparts JSは `index.html` に**焼き込む**（fetchで読まない。実行時は完全オフライン）。

## 2. index.html 実装

### 2.1 画面（iOS純正風・target系の実装を踏襲）

- タブバー: 「地図」「クイズ」「せいせき」「設定」
- 地図タブ: 地域リスト（Inset Grouped。現状「東南アジア」1件）→ 出題画面
- クイズタブ: rekishi型エンジンの器のみ。`TERMS` が空なら「準備中」表示（ロジックは搭載しておく）
- せいせき: のべ解答・正答率・にがて一覧（rekishi踏襲）
- 設定: 記録リセット／**問題データを訂正**（§2.4）／アプリ情報

### 2.2 地図クイズの出題

`MAP_PARTS_SEA` の各パーツにつき2方向を自動生成する。

- **方向A 位置あて**: 「◯◯はどこ？」→ 地図上のマーカーをタップ。
  正解マーカーは点滅ハイライト。`data-part` が一致すれば正解。
  誤答時は正解マーカーと名前を表示。
- **方向B 名前あて**: マーカー（島・川はシェイプも `.part-shape[data-part=…]` でハイライト）
  を強調表示 →「この◯◯の名前は？」
  - 4択: ダミーは同じ `kind` から3つ（正解と同名・別解一致は除外）
  - 記述: 表記ゆれ吸収（空白・かなカナ・全半角）→ name / yomi / alt のいずれか一致で正解
    → 不一致なら答えを表示して自己採点ボタン（合っていた／まちがえた）
- `res` があるパーツはヒントとして「（ボーキサイト）」等を問題文に添える。
- 緯度・経度パーツ（あ・い・う）は方向Bのみ・記述中心（「この線は北緯何度？」）。
- **安全装置**: 出題対象は「SVG内に `data-part` が存在する id」∩「MAP_PARTS_SEA の id」。
  片方にしか無いidは出題しない（起動時に突合してconsole.warnを出す）。

### 2.3 地図の操作

- SVGはピンチズーム・パン可能に（transformベースの簡易実装でよい）。
- マーカーのヒット円は r=16（viewBox座標）。ズーム時もタップしやすいこと。
- 誤タップ配慮: タップ後に「これでかくてい／やりなおす」は不要。1タップ確定でテンポ優先。

### 2.4 訂正機能（重要・新規）

Claudeが写真から判読した答えに誤りがあった場合、てつやがアプリ内で直せるようにする。

- 設定 →「問題データを訂正」→ パーツ一覧（id・現在の名前を表示。`check:true` は「要確認」バッジ）
- 行をタップ → シートモーダルで編集: 名前／よみ／別解（カンマ区切り）
- 保存先: localStorage `chiri2_v1_overrides` = `{ "sea": { "7": {"name":"ネーピードー","yomi":"…","alt":[…]} } }`
- 起動時に `MAP_PARTS_SEA` へオーバーライドをマージして使用。訂正がある間は設定画面に「訂正n件適用中」表示。
- 「訂正をエクスポート」ボタン: オーバーライドJSONをテキスト表示＋クリップボードコピー。
  → てつやがチャットに貼る → 正本（スクリプトのPARTS）へ反映 → 再生成後にオーバーライドをクリアできる「訂正をクリア」ボタンも用意。
- 個別の「元に戻す」も行単位で可能に。

### 2.5 保存（localStorage）

- 成績等: `chiri2_v1`（のべ解答・正答・パーツ別成績・にがて・中断再開）
- 訂正: `chiri2_v1_overrides`（§2.4）
- 「記録をリセット」は成績と中断のみ。訂正は消さない（別ボタン）。

## 3. PWA

- head に apple-touch-icon / icon / manifest タグ。`manifest.webmanifest` は他アプリを踏襲
  （name: 地名ドリル世界、short_name: chiri2、display: standalone、theme_color: #007AFF）。

## 4. デプロイ

共通ルール§9。Settings → Pages → main / (root)。
Deployment failed / Queued 詰まりは `git commit --allow-empty` で空コミットpush。

## 5. 完了条件チェック

- [ ] report_sea.txt に致命的警告がない（警告があれば報告）
- [ ] iPhoneサイズで51パーツ全てがタップ可能
- [ ] 方向A/Bとも動作、記述の自己採点フォールバック動作
- [ ] 訂正→即反映→エクスポート→クリアの一連が動作
- [ ] TERMSが空でもクイズタブがエラーなく「準備中」表示
- [ ] オフライン（機内モード）で全機能動作
