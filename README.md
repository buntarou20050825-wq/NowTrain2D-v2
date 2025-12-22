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

## API 仕様

バックエンドは以下の API エンドポイントを提供します。詳細は http://localhost:8000/docs で確認できます。

### 静的データ API（MS2）

- `GET /api/health` - ヘルスチェック
- `GET /api/lines` - 全路線一覧（`operator` パラメータでフィルタ可能）
- `GET /api/lines/{lineId}` - 特定路線の詳細
- `GET /api/stations?lineId={lineId}` - 指定路線の駅一覧
- `GET /api/shapes?lineId={lineId}` - 指定路線の形状（GeoJSON）

### 列車位置 API（MS3-3）

- `GET /api/yamanote/positions` - 山手線の列車位置一覧
  - パラメータ: `now` (Optional[str]) - JST の日時（ISO8601形式）
  - 未指定時はサーバー現在時刻を使用
  - レスポンス: 列車位置の配列、列車数、タイムスタンプ

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

## MS3-3: 列車位置 API の実装

### 概要

MS3-3 では、MS3-2 で計算した抽象的な列車位置に地図座標を付与し、API として提供します。
- 対象は **山手線のみ** (`JR-East.Yamanote`)
- **駅間は直線補間** → 実際の線路形状は考慮しない（簡易実装）
- 将来的に GTFS-RT 統合でリアルタイム位置に差し替え予定

### 実装内容

#### backend/train_position.py (新規作成)

列車の抽象的な状態（`TrainSectionState`）を地図座標付きの位置（`TrainPosition`）に変換するモジュール。

**データクラス:**
- `TrainPosition`: 列車の地図上の位置と付随情報
  - 列車ID、路線、方向、停車/走行状態
  - 座標（`lon`, `lat`）
  - 進捗度（0.0〜1.0）
  - GTFS-RT 統合用フィールド（`is_scheduled`, `delay_seconds`）

**Pydantic モデル:**
- `TrainPositionResponse`: API レスポンス用の列車位置
- `YamanotePositionsResponse`: `/api/yamanote/positions` のレスポンスラッパー
  - `positions`: 列車位置の配列
  - `count`: 列車数
  - `timestamp`: リクエスト時刻（JST, ISO8601）

**主要関数:**
- `_get_station_coord()`: 駅IDから座標を取得
- `_interpolate_coords()`: 駅A→駅B間の進捗に応じて線形補間した座標を返す
- `train_state_to_position()`: `TrainSectionState` → `TrainPosition` 変換
  - 停車中: 駅座標そのものを使用
  - 走行中: from/to 駅間を直線補間
- `get_yamanote_train_positions()`: 指定時刻の全列車位置を取得
- `debug_dump_positions_at()`: デバッグ用の位置情報ダンプ

#### backend/data_cache.py (拡張)

**追加内容:**
- `_is_valid_coord()`: 座標が日本付近の妥当な範囲にあるかチェック
  - 経度: 122.0〜154.0
  - 緯度: 20.0〜46.0
- `station_positions`: 駅ID → (lon, lat) のインデックス（`Dict[str, tuple[float, float]]`）
- `load_all()` 内で駅座標インデックスを構築
  - 全駅の座標を読み込み
  - 座標の妥当性を検証
  - 山手線時刻表で使用されている駅IDが全て存在するか検証

#### backend/main.py (拡張)

**新しいエンドポイント:**

```
GET /api/yamanote/positions
```

**パラメータ:**
- `now` (Optional[str]): JST の日時（ISO8601形式）
  - 例: `2025-01-20T08:00:00+09:00`
  - 未指定の場合はサーバー現在時刻（JST）を使用
  - タイムゾーン無しの場合は JST とみなす

**レスポンス例:**
```json
{
  "positions": [
    {
      "train_id": "JR-East.Yamanote.400G.Weekday",
      "base_id": "JR-East.Yamanote.400G",
      "number": "400G",
      "service_type": "Weekday",
      "line_id": "JR-East.Yamanote",
      "direction": "InnerLoop",
      "is_stopped": false,
      "station_id": null,
      "from_station_id": "JR-East.Yamanote.Shibuya",
      "to_station_id": "JR-East.Yamanote.Harajuku",
      "progress": 0.45,
      "lon": 139.7012,
      "lat": 35.6696,
      "current_time_sec": 14400,
      "is_scheduled": true,
      "delay_seconds": 0
    }
  ],
  "count": 1,
  "timestamp": "2025-01-20T08:00:00+09:00"
}
```

### 動作確認

**APIエンドポイントのテスト:**

```bash
# 現在時刻の列車位置を取得
curl http://localhost:8000/api/yamanote/positions

# 特定時刻の列車位置を取得
curl "http://localhost:8000/api/yamanote/positions?now=2025-01-20T08:00:00%2B09:00"
```

確認ポイント:
- レスポンスに列車位置の配列が含まれている
- 各列車に `lon`, `lat` 座標が設定されている
- 停車中の列車は駅座標と一致している
- 走行中の列車は from/to 駅間の座標になっている
- `progress` が 0.0〜1.0 の範囲内である

### MS3-3 完了の確認項目

- [x] `backend/train_position.py` が作成されている
- [x] `backend/data_cache.py` に `station_positions` フィールドが追加されている
- [x] バックエンド起動時に `Built X station positions` のログが表示される
- [x] `GET /api/yamanote/positions` エンドポイントが実装されている
- [x] `now` パラメータで時刻指定が可能
- [x] レスポンスに列車の座標（lon, lat）が含まれている
- [x] 停車中の列車が駅座標と一致している
- [x] 走行中の列車が駅間で補間された座標を持っている
- [x] API ドキュメント（`/docs`）で新しいエンドポイントが確認できる

## MS3-4: フロントエンドで列車をリアルタイム表示

### 概要

MS3-4 では、バックエンド API から取得した列車位置を、フロントエンドの地図上にマーカーとして表示します。
- **ポーリング方式**: 2秒ごとに `/api/yamanote/positions` から最新の列車位置を取得
- **マーカー表示**: Mapbox GL JS の circle レイヤーで列車を可視化
- **状態による色分け**: 停車中（グレー）/走行中（黄緑）で視覚的に区別

### 実装内容

#### frontend/src/App.jsx (拡張)

**列車マーカー用のレイヤー追加:**

地図ロード時に、列車を表示するための GeoJSON ソースとレイヤーを追加：

```javascript
map.addSource("yamanote-trains", {
  type: "geojson",
  data: {
    type: "FeatureCollection",
    features: [],
  },
});

map.addLayer({
  id: "yamanote-trains-circle",
  type: "circle",
  source: "yamanote-trains",
  paint: {
    "circle-radius": [
      "interpolate",
      ["linear"],
      ["zoom"],
      10, 4,  // ズーム10で半径4px
      14, 8,  // ズーム14で半径8px
    ],
    "circle-stroke-width": 2,
    "circle-stroke-color": "#ffffff",
    "circle-color": [
      "case",
      ["==", ["get", "is_stopped"], true],
      "#555555",  // 停車中: グレー
      "#80C342",  // 走行中: 山手線の黄緑
    ],
    "circle-opacity": 0.9,
  },
});
```

**ポーリング機能の実装:**

2つ目の `useEffect` でポーリングを実装：

```javascript
const TRAIN_UPDATE_INTERVAL_MS = 2000;  // 2秒ごとに更新

useEffect(() => {
  let intervalId = null;

  const fetchAndUpdate = async () => {
    const map = mapRef.current;
    if (!map) return;

    const src = map.getSource("yamanote-trains");
    if (!src) return;

    try {
      const res = await fetch("/api/yamanote/positions");
      if (!res.ok) {
        console.error("[yamanote] fetch error:", res.status);
        return;
      }
      const json = await res.json();
      const positions = json.positions || [];

      // GeoJSON Features に変換
      const features = positions.map((p) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [p.lon, p.lat],
        },
        properties: { ...p },
      }));

      // ソースのデータを更新
      src.setData({
        type: "FeatureCollection",
        features,
      });
      console.log(`[yamanote] Updated ${features.length} trains`);
    } catch (err) {
      console.error("[yamanote] error:", err);
    }
  };

  const startPolling = () => {
    fetchAndUpdate();  // 初回実行
    intervalId = setInterval(fetchAndUpdate, TRAIN_UPDATE_INTERVAL_MS);
  };

  const map = mapRef.current;
  if (map) {
    if (map.loaded()) {
      startPolling();
    } else {
      map.on("load", startPolling);
    }
  }

  return () => {
    if (intervalId) clearInterval(intervalId);
    if (map) map.off("load", startPolling);
  };
}, []);
```

**主要な処理:**
1. 地図がロードされたら、ポーリングを開始
2. 2秒ごとに `/api/yamanote/positions` から列車位置を取得
3. レスポンスを GeoJSON Features に変換
4. `yamanote-trains` ソースのデータを更新（マーカーが自動的に再描画される）
5. コンポーネントのアンマウント時にインターバルをクリア

#### frontend/vite.config.js (拡張)

**プロキシ設定の追加:**

開発サーバーに API プロキシを設定し、CORS の問題を回避：

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

この設定により、フロントエンド（http://localhost:5173）から `/api/*` へのリクエストが、バックエンド（http://localhost:8000）にプロキシされます。

### 技術的なポイント

#### マーカーの色分け

Mapbox GL JS の `case` 式を使って、列車の状態に応じて色を動的に変更：

- **停車中** (`is_stopped: true`): `#555555` (グレー)
- **走行中** (`is_stopped: false`): `#80C342` (山手線の黄緑)

#### ズーム対応

`interpolate` 式を使って、ズームレベルに応じてマーカーサイズを変更：

- ズーム 10: 半径 4px（広域表示時は小さく）
- ズーム 14: 半径 8px（詳細表示時は大きく）

#### パフォーマンス考慮

- GeoJSON ソースの `setData()` メソッドを使用することで、効率的にマーカーを更新
- レイヤーを再作成せず、データのみを更新するため、描画パフォーマンスが向上

### 動作確認

**必要な手順:**

1. バックエンドを起動
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

2. フロントエンドを起動
   ```bash
   cd frontend
   npm run dev
   ```

3. ブラウザで http://localhost:5173 を開く

**確認ポイント:**
- 地図上に山手線の路線と駅が表示される
- 2秒ごとにコンソールに `[yamanote] Updated X trains` のログが表示される
- 地図上に列車を表す円形マーカーが表示される
- マーカーの色が停車中（グレー）/走行中（黄緑）で変わる
- ズームイン/アウトでマーカーサイズが変化する
- マーカーが時刻に応じて移動する（時刻表ベースの位置計算）

### MS3-4 完了の確認項目

- [x] `frontend/src/App.jsx` に列車マーカー用のレイヤーが追加されている
- [x] ポーリング機能が実装されている（2秒ごとに API を呼び出し）
- [x] `/api/yamanote/positions` から取得したデータを GeoJSON に変換している
- [x] `frontend/vite.config.js` にプロキシ設定が追加されている
- [x] 地図上に列車マーカーが表示される
- [x] マーカーの色が停車中/走行中で変わる
- [x] ズームレベルに応じてマーカーサイズが変化する
- [x] コンソールに列車数の更新ログが表示される

## 開発ロードマップ

- **MS1**: プロジェクト土台 + 2D マップ上に山手線の路線と駅を静的表示 ✅
- **MS2**: FastAPI で静的データを API 化 ✅
- **MS3-1**: 山手線の時刻表読み込みと日跨ぎ正規化 ✅
- **MS3-2**: 時刻表ベースの列車位置計算 ✅
- **MS3-3**: 列車位置 API の実装 ✅
- **MS3-4**: フロントエンドで列車をリアルタイム表示 ✅
- **MS3-5**: 列車マーカーの路線形状追従 ✅
- **MS4-1**: GTFS-RT データの取得とパース ✅
- **MS4-2**: リアルタイム位置情報の取得 (VehiclePosition) ✅
- **MS5**: TripUpdate ベースの v4 API + 線路形状追従 ✅
- **MS6**: 遅延情報の取得と可視化 ✅
- **MS7**: イージングによる加減速表現 ✅ → MS8 で置換
- **MS8**: 物理演算ベースの台形速度制御 ✅
- **MS9**: クライアントサイド補間アニメーション (60fps) ✅

---

## MS5: TripUpdate ベースの v4 API + 線路形状追従 ✅

### 概要

GTFS-RT の **TripUpdate** から取得した予測発着時刻を使って列車位置を計算する新しい v4 API を実装しました。VehiclePosition（座標直接取得）ではなく、時刻ベースで位置を算出することで、より安定した表示を実現します。

### 実装内容

#### 1. TripUpdate パーサー (`backend/gtfs_rt_tripupdate.py`)

**データクラス:**
- `RealtimeStationSchedule`: 1駅の到着/発車予測時刻
- `TrainSchedule`: 1列車の全駅スケジュール

**主要関数:**
- `fetch_trip_updates()`: GTFS-RT から山手線の予測時刻を取得
- `trip_id` のパターンで山手線をフィルタ（`42...G` 形式）

#### 2. 位置計算エンジン (`backend/train_position_v4.py`)

**データクラス:**
- `SegmentProgress`: 列車の現在区間と進捗率

**主要関数:**
- `compute_progress_for_train()`: 予測時刻から進捗率を計算
- `calculate_coordinates()`: 進捗率から線路形状に沿った座標を算出

#### 3. v4 API エンドポイント (`backend/main.py`)

```
GET /api/trains/yamanote/positions/v4
```

**レスポンス例:**
```json
{
  "source": "tripupdate_v4",
  "status": "success",
  "total_trains": 26,
  "positions": [
    {
      "trip_id": "4211004G",
      "train_number": "1004G",
      "direction": "InnerLoop",
      "status": "running",
      "progress": 0.67,
      "delay": 0,
      "location": {
        "latitude": 35.628541,
        "longitude": 139.720505
      },
      "segment": {
        "prev_seq": 29,
        "next_seq": 30,
        "prev_station_id": "JR-East.Yamanote.Meguro",
        "next_station_id": "JR-East.Yamanote.Gotanda"
      },
      "times": {
        "now_ts": 1766371826,
        "t0_departure": 1766371756,
        "t1_arrival": 1766371860
      }
    }
  ]
}
```

### MS5 完了の確認項目

- [x] `backend/gtfs_rt_tripupdate.py` を作成
- [x] `backend/train_position_v4.py` を作成
- [x] `/api/trains/yamanote/positions/v4` エンドポイントを実装
- [x] `calculate_coordinates()` で線路形状に沿った座標を計算
- [x] フロントエンドを v4 API に移行

---

## MS6: 遅延情報の取得と可視化 ✅

### 概要

GTFS-RT TripUpdate に含まれる遅延秒数（`delay`）をバックエンドで取得し、フロントエンドで色分け表示・ポップアップ表示を行います。

### 実装内容

#### バックエンド

| ファイル | 変更内容 |
|---------|---------|
| `gtfs_rt_tripupdate.py` | `RealtimeStationSchedule.delay` フィールド追加 |
| `train_position_v4.py` | `SegmentProgress.delay` フィールド追加 |
| `main.py` | v4 API レスポンスに `delay` 追加 |

**遅延取得ロジック:**
1. `stu.arrival.delay` を優先
2. なければ `stu.departure.delay`
3. 両方なければ `0`

**SegmentProgress への反映:**
- `status="stopped"` → 現在駅の発車遅延
- `status="running"` → 次駅の到着遅延

#### フロントエンド (`frontend/src/App.jsx`)

**色分けルール:**

| 遅延秒数 | 色 | 意味 |
|---------|-----|-----|
| 0〜59秒 | 🟢 `#00B140` | 定刻 |
| 60〜299秒 | 🟠 `#FFA500` | 1〜5分遅れ |
| 300秒〜 | 🔴 `#FF4500` | 5分以上遅れ |
| dataQuality=rejected | 🟣 紫 | データ品質不良 |

**ポップアップ表示:**
- 60秒以上の遅延がある場合のみ表示
- 形式: `遅延: +X分`
- 遅延度合いに応じて文字色を変更

### MS6 完了の確認項目

- [x] `RealtimeStationSchedule` に `delay` フィールド追加
- [x] `SegmentProgress` に `delay` フィールド追加
- [x] v4 API レスポンスに `delay` フィールド追加
- [x] フロントエンドで `step` 式による色分け実装
- [x] ポップアップに遅延情報を表示

---

## MS7: イージングによる加減速表現 ✅ → MS8 で置換

### 概要

列車の動きを「等速移動」から「発車時はゆっくり、中間は速く、到着前は減速」に変更する Ease-in-out Cubic 関数を実装しました。

**注意**: MS8 でより現実的な物理演算に置き換えられました。

---

## MS8: 物理演算ベースの台形速度制御 ✅

### 概要

山手線 E235 系の実スペックに基づいた **台形速度制御（Trapezoidal Velocity Profile）** を実装し、列車の動きを極限までリアルにしました。

### 車両性能パラメータ

| パラメータ | 値 | 説明 |
|----------|-----|------|
| 加速度 | 3.0 km/h/s | 0→90km/h まで 30秒 |
| 減速度 | 4.2 km/h/s | 90→0km/h まで 約25秒 |

### 速度プロファイル

```
速度 ▲
     │      ┌──────────┐
     │     /            \
     │    /              \
     │   /                \
     └──┴────────────────┴──→ 時間
       加速     定速     減速
       30s              25s
```

### 実装内容 (`backend/train_position_v4.py`)

```python
def calculate_physics_progress(elapsed_time: float, total_duration: float) -> float:
    """
    山手線E235系の性能に基づく台形速度制御で進捗率(0.0-1.0)を計算する。
    """
    T_ACC = 30.0  # 加速時間
    T_DEC = 25.0  # 減速時間
    
    # 短区間の場合は「三角走行」に自動調整
    if total_duration < (T_ACC + T_DEC):
        factor = total_duration / (T_ACC + T_DEC)
        t_acc, t_dec = T_ACC * factor, T_DEC * factor
    else:
        t_acc, t_dec = T_ACC, T_DEC
    
    # 速度プロファイルを積分して位置を計算
    ...
```

### 効果

- **発車時**: ゆっくり動き出し、30秒かけて最高速度へ
- **定速走行**: 最高速度を維持
- **到着時**: 25秒かけてスムーズに減速・停止
- **短区間**: 加速→即減速の「三角走行」に自動調整

### MS8 完了の確認項目

- [x] `calculate_physics_progress()` 関数を実装
- [x] MS7 の `ease_in_out_cubic()` を置換
- [x] 加速・定速・減速の3フェーズを正しく計算
- [x] 短区間での三角走行に対応

---

## MS9: クライアントサイド補間アニメーション (60fps) ✅

### 概要

API ポーリング間隔（2秒）を維持しつつ、フロントエンドで `requestAnimationFrame` を使って中間位置を補間し、60fps の滑らかなアニメーションを実現しました。

### 実装内容 (`frontend/src/App.jsx`)

#### 1. アニメーション用 Ref

```javascript
const animationRef = useRef(null);         // rAF ID
const trainPositionsRef = useRef({});      // { trainNumber: { current, target, startTime, properties } }
const lastFetchTimeRef = useRef(0);
```

#### 2. 目標位置の更新 (`fetchAndUpdate` 内)

API からデータを受信したら:
- 初回: `current` と `target` に同じ座標をセット
- 2回目以降: 古い `target` → `current`、新座標 → `target`

#### 3. アニメーションループ

```javascript
useEffect(() => {
  const animateTrains = () => {
    const now = performance.now();
    const duration = TRAIN_UPDATE_INTERVAL_MS; // 2000ms
    
    const features = Object.keys(trainPositionsRef.current).map(key => {
      const train = trainPositionsRef.current[key];
      const t = Math.min(1.0, (now - train.startTime) / duration);
      
      // LERP補間
      const lon = train.current[0] + (train.target[0] - train.current[0]) * t;
      const lat = train.current[1] + (train.target[1] - train.current[1]) * t;
      
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [lon, lat] },
        properties: { ...train.properties, lon, lat },
      };
    });
    
    src.setData({ type: "FeatureCollection", features });
    animationRef.current = requestAnimationFrame(animateTrains);
  };
  
  animationRef.current = requestAnimationFrame(animateTrains);
  
  return () => {
    if (animationRef.current) cancelAnimationFrame(animationRef.current);
  };
}, []);
```

### 効果

- ワープ移動が **スーッと滑らかな移動** に変化
- MS8 の物理演算による加減速が **アニメーション速度の緩急** として可視化
- CPU 負荷を抑えつつ 60fps を維持

### MS9 完了の確認項目

- [x] `animationRef`, `trainPositionsRef`, `lastFetchTimeRef` を追加
- [x] `fetchAndUpdate` で目標位置を更新
- [x] `requestAnimationFrame` でアニメーションループを実装
- [x] LERP 補間で滑らかな移動を実現
- [x] コンポーネントアンマウント時に `cancelAnimationFrame`

---

## デバッグツール

### TripUpdate 更新監視 (`backend/watch_updates.py`)

GTFS-RT の予測時刻が実際にリアルタイム更新されていることを検証するツール。

```bash
cd backend
python watch_updates.py
```

**機能:**
- 20秒間隔で TripUpdate API をポーリング
- 到着/発車時刻の変化を検出して表示
- 遅延秒数の変化（改善/悪化）を追跡
- 列車の増減を検出

**出力例:**
```
[12:05:23] ポーリング#3 - 列車数: 26
  🚅 [1205G] Shinjuku: 到着 12:00:00 → 12:00:15 (+15s) (Delay: 60s)
  ⏱️  [1422G] Shibuya: 遅延 60s → 90s (悪化)
  📊 今回の変化: 2件 (累計: 5件)
```

---

## ライセンス

このプロジェクトは教育目的の卒業制作です。Mini Tokyo 3D のデータとアイデアを参考にしていますが、コードは独自に実装されています。

## 謝辞

- [Mini Tokyo 3D](https://github.com/nagix/mini-tokyo-3d) - データ形式とアイデアの参考元
- [Mapbox GL JS](https://www.mapbox.com/) - 地図表示ライブラリ
- [公共交通オープンデータセンター (ODPT)](https://developer.odpt.org/) - リアルタイム列車情報 API

