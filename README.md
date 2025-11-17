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
- Python 3.8 以上
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

### バックエンド

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

## CORS 設定について

バックエンド（FastAPI）の CORS 設定は、デフォルトでフロントエンドの開発サーバー（`http://localhost:5173`）を許可しています。

フロントエンドのポートを変更する場合は、`backend/main.py` の `origins` リストも合わせて変更してください。

## MS1 完了の確認項目

- [ ] Mapbox が正しく表示される（地図が出ている）
- [ ] 山手線の路線（黄緑色の線）がループ状に表示される
- [ ] 山手線の駅（白い円＋黒枠）が各駅位置に表示される
- [ ] 駅名ラベル（日本語）が駅の近くに表示される
- [ ] `/api/health` が `{"status": "ok"}` を返す
- [ ] ブラウザのコンソールにエラーが出ていない

## 開発ロードマップ

- **MS1** (現在): プロジェクト土台 + 2D マップ上に山手線の路線と駅を静的表示 ✅
- **MS2**: FastAPI で静的データを API 化
- **MS3**: 時刻表ベースの列車シミュレーション
- **MS4**: GTFS-RT との統合
- **MS5**: UI/UX 強化
- **MS6**: パフォーマンス調整・デプロイ・仕上げ

## ライセンス

このプロジェクトは教育目的の卒業制作です。Mini Tokyo 3D のデータとアイデアを参考にしていますが、コードは独自に実装されています。

## 謝辞

- [Mini Tokyo 3D](https://github.com/nagix/mini-tokyo-3d) - データ形式とアイデアの参考元
- [Mapbox GL JS](https://www.mapbox.com/) - 地図表示ライブラリ
