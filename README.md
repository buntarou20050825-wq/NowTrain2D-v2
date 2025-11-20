# NowTrain-v2

## プロジェクト概要

NowTrain-v2 は、東京圏の鉄道をリアルタイムで可視化する **2D 鉄道ビューア** です。このプロジェクトは卒業制作として、[Mini Tokyo 3D](https://minitokyo3d.com/) のデータ形式とアイデアを参考にしながら、2D 表示に特化した独自実装として開発されています。

### Mini Tokyo 3D について

- **参考元**: [Mini Tokyo 3D](https://github.com/nagix/mini-tokyo-3d)
- **ライセンス**: MIT License
- **参考箇所**: データ形式（路線・駅・座標の JSON 構造）、アイデア・コンセプト
- **重要**: このプロジェクトは Mini Tokyo 3D のソースコードを直接コピーせず、データ形式を参考にして独自に実装しています。

### 技術スタック

- **フロントエンド**: React + JavaScript + Vite + Mapbox GL JS（2D表示）
- **バックエンド**: FastAPI（Python）
- **デプロイ**: 自前 VPS 上でホスト予定
- **対象路線**: 現在は山手線のみ（将来的に JR 東日本エリア全体に拡張予定）

## ディレクトリ構成

```
NowTrain-v2/
├── frontend/              # React + Vite + Mapbox
│   ├── public/
│   │   └── data/
│   │       └── mini-tokyo-3d/   # Mini Tokyo 3D のデータファイル
│   └── src/
│       ├── api/
│       │   └── staticData.js    # データ読み込みモジュール
│       ├── App.jsx              # メインコンポーネント
│       └── main.jsx
├── backend/               # FastAPI
│   ├── main.py
│   └── requirements.txt
└── data/                  # バックエンド用の元データ
    └── mini-tokyo-3d/
```

## セットアップ

### 前提条件

- Node.js (v18 以上推奨)
- **Python 3.10 以上（3.11 推奨）**
  - MS2 までは 3.9 でも動作しましたが、MS3-1 以降は型ヒント・標準ライブラリの都合により 3.10+ を前提とします
  - MS3-2 以降は `zoneinfo` を使用します。Windows など一部環境では `tzdata` パッケージのインストールが必要な場合があります（`pip install tzdata`）
- Mapbox アクセストークン（[こちら](https://account.mapbox.com/access-tokens/)から取得）

### フロントエンド

1. ディレクトリに移動

```bash
cd frontend
```

2. 依存関係のインストール

```bash
npm install
```

3. 環境変数の設定

`.env.local` ファイルを作成し、Mapbox アクセストークンを設定してください：

```env
VITE_MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
```

**重要**: `.env.local` は `.gitignore` に含まれており、Git にコミットされません。

4. 開発サーバーの起動

```bash
npm run dev
```

デフォルトで http://localhost:5173 で起動します。

### バックエンド（MS2以降）

#### データ準備

**重要**: バックエンドは `data/mini-tokyo-3d/` のデータを使用します。以下のコマンドでフロントエンドのデータをコピーしてください。

**macOS / Linux:**

```bash
cd NowTrain-v2
mkdir -p data/mini-tokyo-3d
cp -r frontend/public/data/mini-tokyo-3d/* data/mini-tokyo-3d/
```

**Windows PowerShell:**

```powershell
cd NowTrain-v2
New-Item -ItemType Directory -Force -Path "data\mini-tokyo-3d" | Out-Null
Copy-Item -Recurse "frontend\public\data\mini-tokyo-3d\*" "data\mini-tokyo-3d\"
```

> **注意**: `data/mini-tokyo-3d/` は `.gitignore` に含まれています。JSON ファイルが壊れた場合は、上記コマンドで再コピーしてください。

#### セットアップ

1. ディレクトリに移動

```bash
cd backend
```

2. 仮想環境の作成（推奨）

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

4. サーバーの起動

```bash
uvicorn main:app --reload --port 8000
```

デフォルトで http://localhost:8000 で起動します。

## CORS 設定について（MS2以降）

バックエンド（FastAPI）の CORS 設定は、環境変数 `FRONTEND_URL` で制御されます。デフォルトは `http://localhost:5173` です。

複数の URL を許可する場合は、`backend/.env` ファイルを作成して以下のように設定してください：

```env
FRONTEND_URL=http://localhost:5173,http://127.0.0.1:5173
```

## API 仕様（MS2）

バックエンドは以下の API エンドポイントを提供します。詳細は http://localhost:8000/docs で確認できます。

- `GET /api/health` - ヘルスチェック
- `GET /api/lines` - 全路線一覧（`operator` パラメータでフィルタ可能）
- `GET /api/lines/{lineId}` - 特定路線の詳細
- `GET /api/stations?lineId={lineId}` - 指定路線の駅一覧
- `GET /api/shapes?lineId={lineId}` - 指定路線の形状（GeoJSON）

## MS1 完了の確認項目

- [x] Mapbox が正しく表示される（地図が出ている）
- [x] 山手線の路線（黄緑色の線）がループ状に表示される
- [x] 山手線の駅（白い円＋黒枠）が各駅位置に表示される
- [x] 駅名ラベル（日本語）が駅の近くに表示される
- [x] `/api/health` が `{"status": "ok"}` を返す
- [x] ブラウザのコンソールにエラーが出ていない

## MS2 完了の確認項目

### バックエンド

- [ ] `data/mini-tokyo-3d/` に `railways.json`, `stations.json`, `coordinates.json` が存在する
- [ ] バックエンド起動時に `Data loaded: XXX railways, YYY stations` のログが表示される
- [ ] `GET /api/health` が正常に `{"status":"ok"}` を返す
- [ ] `GET /api/lines` で路線一覧が取得できる
- [ ] `GET /api/lines?operator=JR-East` で JR東日本の路線のみが返る
- [ ] `GET /api/lines/JR-East.Yamanote` が期待通りの JSON を返す
- [ ] `GET /api/stations?lineId=JR-East.Yamanote` が駅一覧を返す
- [ ] 各駅オブジェクトに `coord.lon` / `coord.lat` が含まれる
- [ ] `GET /api/shapes?lineId=JR-East.Yamanote` が GeoJSON FeatureCollection を返す
- [ ] `/api/shapes` の `coordinates` 配列に数百点以上の座標が含まれている
- [ ] 不正な `lineId` に対して適切なエラー（404 または 400）が返る
- [ ] `http://localhost:8000/docs` で API ドキュメントが確認できる

### フロントエンド

- [ ] MS1 で実装した山手線の静的描画が引き続き動作している
- [ ] ブラウザコンソールに `/api/lines` の結果が表示される
- [ ] フロントとバックを同時に起動しても CORS エラーが出ない

## MS3-1: 山手線の時刻表読み込み

### データ準備

バックエンドは `backend/main.py` から見て `../data` を参照します。時刻表データは既に `data/train-timetables/jreast-yamanote.json` に配置されています。

### 内部データ構造

- 起動時に `DataCache.yamanote_trains` に `TimetableTrain` の配列としてロードされます
- `service_type` は id の末尾から推定（例: `Weekday`, `Holiday`）
  - 当てはまらない場合は `'Unknown'` となり、ログに情報が出力されます
- 終着駅が複数ある場合（`ds` が複数要素を持つ場合）は、そのまま複数保持します
- 日跨ぎ補正により、23時台→0時台の時刻が正しく24時間加算されます

### MS3-1 完了の確認項目

- [x] `backend/timetable_models.py` が作成され、`StopTime` / `TimetableTrain` が定義されている
- [x] `backend/data_cache.py` に時刻表読み込み機能が追加されている
- [x] バックエンド起動時に `Loaded X Yamanote timetable trains` のログが表示される
- [x] バックエンド起動時に `Yamanote service types: [...]` のログが表示される
- [x] 既存の API (`/api/lines` など) が引き続き正常に動作している

## MS3-2: 時刻表ベースの列車位置計算

### 概要

MS3-2 では、時刻表データと現在時刻から「抽象的な列車の位置」を計算するロジックを実装します。
- 対象は **山手線のみ** (`JR-East.Yamanote`)
- **座標（経度緯度）は計算しない** → 「どの列車が」「どの駅の間（もしくはどの駅で停車中）」にいるかまで

### バックエンド構成

バックエンドのレイヤ構成は以下のようになっています：

1. **timetable_models.py** - 時刻表 JSON を Python オブジェクトに変換する静的モデル層
2. **data_cache.py** - JSON 読み込み・キャッシュを担当するデータアクセス層
3. **train_state.py** (MS3-2 で追加) - 時刻表 + 時刻 → 列車状態（駅間 or 停車中）を計算するロジック層
4. API 層 (MS3-3 以降) - `train_state` を呼び出して API レスポンスを作る

### 実装内容

#### backend/train_state.py

以下のデータクラスと関数を実装しています：

**データクラス:**
- `TrainSegment`: 1本の列車の1区間（走行 or 停車）を表す
  - 時間範囲は `[start_sec, end_sec)` の半開区間
- `TrainSectionState`: 列車が今どこにいるか（停車 or 走行）を表す抽象状態
  - `is_stopped`: 停車中かどうか
  - `progress`: 走行中の場合の進捗度 (0.0〜1.0)

**時間系ユーティリティ:**
- `get_service_date()`: サービス日の計算（04:00 を境界とする）
- `to_effective_seconds()`: サービス日開始からの秒数に変換
- `determine_service_type()`: 曜日から service_type を判定（月〜金: "Weekday", 土日: "SaturdayHoliday"）

**セグメント構築:**
- `build_segments_for_train()`: 1本の列車から走行/停車セグメントを構築
- `build_yamanote_segments()`: 全山手線列車のセグメントを構築

**列車状態計算:**
- `get_yamanote_trains_at()`: 指定時刻における山手線の運行中列車の状態を返す
  - 線形走査で該当セグメントを検索
  - `service_type` が "Weekday" / "SaturdayHoliday" 以外の列車は無視

**デバッグ用:**
- `debug_dump_trains_at()`: 指定時刻の列車状態をコンソールにダンプ

#### 循環 import 回避

`train_state.py` では `DataCache` を型ヒントとしてのみ参照するため、`TYPE_CHECKING` を使って循環 import を回避しています：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_cache import DataCache
```

実際の `build_yamanote_segments()` 呼び出しは `data_cache.py` 側から行います。

### 動作確認

テストスクリプト (`test_train_state.py`) で以下を確認できます：

```bash
cd /path/to/NowTrain2D-v2
python test_train_state.py
```

確認ポイント：
- 山手線セグメント数が 30,000 件以上構築されている
- 深夜帯で列車が正しく検出される
- 走行中の列車の進捗度 (0.0〜1.0) が計算される
- 時間系ユーティリティが正しく動作する

### MS3-2 完了の確認項目

- [x] `backend/train_state.py` が作成されている
- [x] `backend/data_cache.py` に `yamanote_segments` フィールドが追加されている
- [x] バックエンド起動時に `Built X Yamanote train segments` のログが表示される
- [x] `get_yamanote_trains_at()` で指定時刻の列車状態が取得できる
- [x] 走行中の列車の進捗度が 0.0〜1.0 で計算される
- [x] 停車中の列車が駅ID とともに正しく検出される

## 開発ロードマップ

- **MS1**: プロジェクト土台 + 2D マップ上に山手線の路線と駅を静的表示 ✅
- **MS2**: FastAPI で静的データを API 化 ✅
- **MS3-1**: 山手線の時刻表読み込みと日跨ぎ正規化 ✅
- **MS3-2** (現在): 時刻表ベースの列車位置計算 ✅
- **MS3-3**: 列車位置 API の実装
- **MS4**: GTFS-RT との統合
- **MS5**: UI/UX 強化
- **MS6**: パフォーマンス調整・デプロイ・仕上げ

## ライセンス

このプロジェクトは教育目的の卒業制作です。Mini Tokyo 3D のデータとアイデアを参考にしていますが、コードは独自に実装されています。

## 謝辞

- [Mini Tokyo 3D](https://github.com/nagix/mini-tokyo-3d) - データ形式とアイデアの参考元
- [Mapbox GL JS](https://www.mapbox.com/) - 地図表示ライブラリ
