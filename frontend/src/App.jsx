import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { fetchRailways, fetchStations, fetchCoordinates } from "./api/staticData";
// fetchLinesFromApi は今回使わないので削除してもOKですが残しておきます
import { fetchLinesFromApi } from "./api/serverData";

// ==========================================
// 設定: 対応路線リスト
// ==========================================
const AVAILABLE_LINES = [
  { id: 'yamanote', name: '山手線', railwayId: 'JR-East.Yamanote', color: '#80C342' },
  { id: 'chuo_rapid', name: '中央線快速', railwayId: 'JR-East.ChuoRapid', color: '#EB5C01' },
  { id: 'keihin_tohoku', name: '京浜東北線', railwayId: 'JR-East.KeihinTohokuNegishi', color: '#00A7E3' },
  { id: 'sobu_local', name: '総武線各駅停車', railwayId: 'JR-East.ChuoSobuLocal', color: '#FFE500' },
];

const TRAIN_UPDATE_INTERVAL_MS = 2000;
// 線路データの「飛び」を検知して分割する閾値 (度数法: 0.02度 ≒ 約2.2km)
const MAX_SEGMENT_DISTANCE = 0.02;

// Unix Timestamp を HH:MM:SS 形式に変換
const formatTime = (ts) => {
  if (!ts) return "--:--:--";
  return new Date(ts * 1000).toLocaleTimeString('ja-JP', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
};

// ==========================================
// ユーティリティ: 線路データのクリーニング
// ==========================================
// 座標リストを受け取り、距離が離れすぎている箇所で分割して MultiLineString 用の配列を返す
const cleanLineSegments = (coords) => {
  if (!Array.isArray(coords) || coords.length < 2) return [coords];

  const segments = [];
  let currentSegment = [coords[0]];

  for (let i = 1; i < coords.length; i++) {
    const prev = coords[i - 1];
    const curr = coords[i];

    // 距離の二乗（簡易計算）
    const distSq = (prev[0] - curr[0]) ** 2 + (prev[1] - curr[1]) ** 2;

    // 閾値を超えていたら分割 (閾値の2乗と比較)
    if (distSq > MAX_SEGMENT_DISTANCE ** 2) {
      if (currentSegment.length > 1) {
        segments.push(currentSegment);
      }
      currentSegment = [curr];
    } else {
      currentSegment.push(curr);
    }
  }

  if (currentSegment.length > 1) {
    segments.push(currentSegment);
  }

  return segments;
};


function App() {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  // ========== 状態管理 ==========
  const [selectedLine, setSelectedLine] = useState('yamanote'); // 現在の路線ID
  const selectedLineRef = useRef('yamanote'); // ポーリング内で参照するためRefも使う

  const [trackedTrain, setTrackedTrain] = useState(null);
  const trackedTrainRef = useRef(null);

  const [searchQuery, setSearchQuery] = useState("");
  const searchQueryRef = useRef("");

  const [displayMode, setDisplayMode] = useState("all");
  const displayModeRef = useRef("all");

  // ========== アニメーション管理 ==========
  const animationRef = useRef(null);
  const trainPositionsRef = useRef({}); // { trainNumber: { current, target, startTime, properties } }

  // State同期 (useEffect内での参照用)
  useEffect(() => { selectedLineRef.current = selectedLine; }, [selectedLine]);
  useEffect(() => { trackedTrainRef.current = trackedTrain; }, [trackedTrain]);
  useEffect(() => { searchQueryRef.current = searchQuery; }, [searchQuery]);
  useEffect(() => { displayModeRef.current = displayMode; }, [displayMode]);

  // ========== 60fps アニメーションループ ==========
  useEffect(() => {
    const animateTrains = () => {
      const map = mapRef.current;
      // 現在の路線のソースを取得
      const src = map?.getSource("trains-source");

      if (!src || Object.keys(trainPositionsRef.current).length === 0) {
        animationRef.current = requestAnimationFrame(animateTrains);
        return;
      }

      const now = performance.now();
      const duration = TRAIN_UPDATE_INTERVAL_MS;

      const features = Object.keys(trainPositionsRef.current).map(key => {
        const train = trainPositionsRef.current[key];
        const t = Math.min(1.0, (now - train.startTime) / duration);

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

  // ========== マップ初期化 (初回のみ) ==========
  useEffect(() => {
    if (mapRef.current) return;

    mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [139.70, 35.68], // 東京周辺
      zoom: 11,
    });

    mapRef.current = map;

    map.on("load", () => {
      // 共通ソース: 路線図 (LineString)
      map.addSource("railway-line", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
      map.addLayer({
        id: "railway-line-layer",
        type: "line",
        source: "railway-line",
        paint: {
          "line-color": "#80C342", // 初期値
          "line-width": 4,
        },
      }, 'road-label'); // 道路ラベルの下に表示

      // 共通ソース: 駅 (Point)
      map.addSource("stations", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
      map.addLayer({
        id: "stations-circle",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": 3,
          "circle-color": "#ffffff",
          "circle-stroke-color": "#000000",
          "circle-stroke-width": 1,
        },
      });

      // 共通ソース: 列車位置 (Point)
      map.addSource("trains-source", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });

      // 列車マーカー設定
      map.addLayer({
        id: "trains-layer",
        type: "circle",
        source: "trains-source",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            10, 4,
            14, 8,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
          "circle-color": [
            "case",
            ["==", ["get", "trainNumber"], trackedTrain || ""], "#FF0000", // 追跡中
            ["==", ["get", "dataQuality"], "rejected"], "#9C27B0", // 無効データ
            // 遅延による色分け
            ["step", ["get", "delaySeconds"],
              "#00B140", 60, // 定刻
              "#FFA500", 300, // 1分遅延
              "#FF4500" // 5分以上遅延
            ]
          ],
        },
      });

      // ポップアップ設定
      const popup = new mapboxgl.Popup({ closeButton: false, closeOnClick: false });

      map.on('mouseenter', 'trains-layer', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const coordinates = e.features[0].geometry.coordinates.slice();
        const props = e.features[0].properties;

        const html = `
          <div style="font-size:12px; color:black;">
            <strong>${props.trainNumber}</strong><br/>
            ${props.isStopped ? '停車中' : '走行中'}<br/>
            遅延: ${Math.floor(props.delaySeconds / 60)}分
          </div>
        `;
        popup.setLngLat(coordinates).setHTML(html).addTo(map);
      });

      map.on('mouseleave', 'trains-layer', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });

      // 初期ロード完了後にデータ取得を開始
      initLineData(selectedLine);
    });

  }, []); // eslint-disable-line react-hooks/exhaustive-deps


  // ========== 路線切り替え時の処理 ==========
  useEffect(() => {
    if (!mapRef.current || !mapRef.current.loaded()) return;
    initLineData(selectedLine);
  }, [selectedLine]);


  // 路線データ(形状・駅)の読み込みとポーリング開始
  const initLineData = async (lineId) => {
    const map = mapRef.current;
    const config = AVAILABLE_LINES.find(l => l.id === lineId) || AVAILABLE_LINES[0];

    // 1. 地図上の線の色を変更
    if (map.getLayer('railway-line-layer')) {
      map.setPaintProperty('railway-line-layer', 'line-color', config.color);
    }

    // 2. 静的データ(線路形状・駅)を取得して更新
    try {
      const railways = await fetchRailways();
      const stations = await fetchStations();
      const coordsData = await fetchCoordinates();

      if (railways && stations && coordsData) {
        updateStaticMap(map, config, railways, stations, coordsData);
      }
    } catch (e) {
      console.error("Static data load error:", e);
    }

    // アニメーション用バッファをクリア（列車が飛び跳ねるのを防ぐ）
    trainPositionsRef.current = {};

    // 既存の列車マーカーを一旦消す
    const trainsSrc = map.getSource("trains-source");
    if (trainsSrc) {
      trainsSrc.setData({ type: "FeatureCollection", features: [] });
    }
  };

  // 地図の静的要素(線・駅)を更新する関数
  const updateStaticMap = (map, config, railways, stations, coordsData) => {
    const targetRailwayId = config.railwayId;

    // 線路形状 (MultiLineString + クリーニング)
    const railwayCoordsEntry = coordsData.railways?.find(c => c.id === targetRailwayId);
    let multiLineCoords = [];

    if (railwayCoordsEntry && Array.isArray(railwayCoordsEntry.sublines)) {
      railwayCoordsEntry.sublines.forEach(sub => {
        if (Array.isArray(sub.coords) && sub.coords.length > 0) {
          // ★ここでサニタイズ処理: 長すぎる直線を分割
          const cleanedSegments = cleanLineSegments(sub.coords);
          multiLineCoords.push(...cleanedSegments);
        }
      });
    }

    // 駅 (Points)
    const targetLineInfo = railways.find(r => r.id === targetRailwayId);
    const stationIds = targetLineInfo?.stations || [];
    const targetStations = stations.filter(st => stationIds.includes(st.id));

    // Mapboxソース更新
    const lineSource = map.getSource('railway-line');
    if (lineSource) {
      lineSource.setData({
        type: "Feature",
        geometry: { type: "MultiLineString", coordinates: multiLineCoords },
        properties: {}
      });
    }

    const stationSource = map.getSource('stations');
    if (stationSource) {
      stationSource.setData({
        type: "FeatureCollection",
        features: targetStations.map(st => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: st.coord },
          properties: { name: st.title.ja }
        }))
      });
    }
  };


  // ========== データポーリング (定期実行) ==========
  useEffect(() => {
    let intervalId = null;

    const fetchAndUpdate = async () => {
      const map = mapRef.current;
      if (!map || !map.getSource("trains-source")) return;

      const currentLineId = selectedLineRef.current; // Refから最新の値を取得

      try {
        // ★ API呼び出し: 選択中の路線IDを使う
        const res = await fetch(`/api/trains/${currentLineId}/positions/v4`);
        if (!res.ok) return;
        const json = await res.json();
        const positions = json.positions || [];

        // GeoJSON変換 & アニメーション目標更新
        const now = performance.now();

        // 検索フィルタ
        const query = searchQueryRef.current.trim().toUpperCase();
        const filteredPositions = query
          ? positions.filter(p => p.train_number && p.train_number.includes(query))
          : positions;

        const activeKeys = new Set();

        filteredPositions.forEach(p => {
          if (!p.location) return;
          const key = p.train_number;
          activeKeys.add(key);

          const newTarget = [p.location.longitude, p.location.latitude];

          // データ補正 (プロパティを扱いやすい形に)
          const props = {
            trainNumber: p.train_number,
            delaySeconds: p.delay || 0,
            isStopped: p.status === 'stopped',
            dataQuality: 'good'
          };

          if (!trainPositionsRef.current[key]) {
            // 新規列車
            trainPositionsRef.current[key] = {
              current: newTarget,
              target: newTarget,
              startTime: now,
              properties: props
            };
          } else {
            // 更新
            const old = trainPositionsRef.current[key];
            trainPositionsRef.current[key] = {
              current: old.target, // 前回ターゲットを現在地とする
              target: newTarget,
              startTime: now,
              properties: props
            };
          }
        });

        // 消失した列車を削除
        Object.keys(trainPositionsRef.current).forEach(key => {
          if (!activeKeys.has(key)) delete trainPositionsRef.current[key];
        });

      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    // 初回実行と定期実行
    fetchAndUpdate();
    intervalId = setInterval(fetchAndUpdate, TRAIN_UPDATE_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, []); // 依存配列は空 (内部でRefを使って最新の路線IDを見るため)


  return (
    <div style={{ position: 'relative', width: "100vw", height: "100vh" }}>
      {/* コントロールパネル */}
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.95)',
        padding: '15px',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        width: '250px'
      }}>
        <h2 style={{ margin: 0, fontSize: '16px', borderBottom: '2px solid #ddd', paddingBottom: '5px' }}>
          NowTrain コントロール
        </h2>

        {/* 1. 路線選択 (MS11の核心) */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            🛤 路線選択:
          </label>
          <select
            value={selectedLine}
            onChange={(e) => setSelectedLine(e.target.value)}
            style={{ width: '100%', padding: '6px', fontSize: '14px', borderRadius: '4px' }}
          >
            {AVAILABLE_LINES.map(line => (
              <option key={line.id} value={line.id}>
                {line.name}
              </option>
            ))}
          </select>
        </div>

        {/* 2. 列車検索 */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            🔍 列車番号検索:
          </label>
          <div style={{ display: 'flex', gap: '5px' }}>
            <input
              type="text"
              placeholder="例: 1234G"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
              style={{ flex: 1, padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} style={{ cursor: 'pointer' }}>×</button>
            )}
          </div>
        </div>

        {/* 3. 追跡 */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            📍 自動追跡:
          </label>
          <input
            type="text"
            placeholder="追跡する列車番号"
            onChange={(e) => setTrackedTrain(e.target.value.toUpperCase() || null)}
            style={{ width: '100%', padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
          />
        </div>

      </div>

      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

export default App;