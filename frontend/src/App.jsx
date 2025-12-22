import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { fetchRailways, fetchStations, fetchCoordinates } from "./api/staticData";
import { fetchLinesFromApi } from "./api/serverData";

const YAMANOTE_ID = "JR-East.Yamanote";
const TRAIN_UPDATE_INTERVAL_MS = 2000;

// Unix Timestamp を HH:MM:SS 形式に変換
const formatTime = (ts) => {
  if (!ts) return "--:--:--";
  return new Date(ts * 1000).toLocaleTimeString('ja-JP', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
};

// 位置データのソース切り替え
// 'timetable' = 時刻表ベース（既存）
// 'gtfs-rt'   = GTFS-RTリアルタイム（新規）
// 'hybrid'    = ハイブリッド（時刻表補間 + GTFS-RT補正）
const POSITION_SOURCE = 'hybrid';

// 山手線30駅の座標（外回り順）
const YAMANOTE_STATIONS = [
  { id: 'Osaki', lat: 35.6202, lon: 139.7282 },
  { id: 'Gotanda', lat: 35.6263, lon: 139.7234 },
  { id: 'Meguro', lat: 35.6335, lon: 139.7157 },
  { id: 'Ebisu', lat: 35.6466, lon: 139.7098 },
  { id: 'Shibuya', lat: 35.6580, lon: 139.7015 },
  { id: 'Harajuku', lat: 35.6713, lon: 139.7026 },
  { id: 'Yoyogi', lat: 35.6835, lon: 139.7021 },
  { id: 'Shinjuku', lat: 35.6902, lon: 139.7004 },
  { id: 'ShinOkubo', lat: 35.7007, lon: 139.7001 },
  { id: 'Takadanobaba', lat: 35.7127, lon: 139.7037 },
  { id: 'Mejiro', lat: 35.7202, lon: 139.7062 },
  { id: 'Ikebukuro', lat: 35.7299, lon: 139.7109 },
  { id: 'Otsuka', lat: 35.7316, lon: 139.7279 },
  { id: 'Sugamo', lat: 35.7338, lon: 139.7403 },
  { id: 'Komagome', lat: 35.7368, lon: 139.7479 },
  { id: 'Tabata', lat: 35.7374, lon: 139.7615 },
  { id: 'NishiNippori', lat: 35.7318, lon: 139.7668 },
  { id: 'Nippori', lat: 35.7271, lon: 139.7709 },
  { id: 'Uguisudani', lat: 35.7213, lon: 139.7779 },
  { id: 'Ueno', lat: 35.7135, lon: 139.7768 },
  { id: 'Okachimachi', lat: 35.7071, lon: 139.7745 },
  { id: 'Akihabara', lat: 35.6982, lon: 139.7729 },
  { id: 'Kanda', lat: 35.6916, lon: 139.7706 },
  { id: 'Tokyo', lat: 35.6813, lon: 139.7670 },
  { id: 'Yurakucho', lat: 35.6749, lon: 139.7629 },
  { id: 'Shimbashi', lat: 35.6663, lon: 139.7579 },
  { id: 'Hamamatsucho', lat: 35.6555, lon: 139.7570 },
  { id: 'Tamachi', lat: 35.6457, lon: 139.7476 },
  { id: 'TakanawaGateway', lat: 35.6354, lon: 139.7407 },
  { id: 'Shinagawa', lat: 35.6288, lon: 139.7387 },
];

function App() {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  // ========== 列車追跡機能 ==========
  const [trackedTrain, setTrackedTrain] = useState(null);
  const trackedTrainRef = useRef(null);

  // ========== 電車ID検索機能 ==========
  const [searchQuery, setSearchQuery] = useState("");
  const searchQueryRef = useRef("");

  // ========== 表示モード切り替え ==========
  // 'all' = 全て表示, 'timetable' = 時刻表のみ, 'gtfs' = GTFS-RTのみ, 'blend' = ブレンドのみ
  const [displayMode, setDisplayMode] = useState("all");
  const displayModeRef = useRef("all");

  // ========== GTFS-RT更新遅延計測用 ==========
  const trainStatesRef = useRef({});  // { trainNumber: { stopSeq, lastUpdate } }

  // ========== MS9: クライアントサイド補間アニメーション ==========
  const animationRef = useRef(null); // rAF ID
  const trainPositionsRef = useRef({}); // { trainNumber: { current, target, startTime, properties } }
  const lastFetchTimeRef = useRef(0);

  // trackedTrain同期
  useEffect(() => {
    trackedTrainRef.current = trackedTrain;
  }, [trackedTrain]);

  // searchQuery同期
  useEffect(() => {
    searchQueryRef.current = searchQuery;
  }, [searchQuery]);

  // displayMode同期
  useEffect(() => {
    displayModeRef.current = displayMode;
  }, [displayMode]);

  // ========== MS9: 60fps アニメーションループ ==========
  useEffect(() => {
    const animateTrains = () => {
      const map = mapRef.current;
      const src = map?.getSource("yamanote-trains");

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

  useEffect(() => {
    if (mapRef.current) return;

    mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: [139.70, 35.68],
      zoom: 11,
    });

    mapRef.current = map;

    map.on("load", async () => {
      // データ読み込み
      const railways = await fetchRailways();
      if (!railways) {
        console.error("Failed to load railways data");
        return;
      }

      const stations = await fetchStations();
      if (!stations) {
        console.error("Failed to load stations data");
        return;
      }

      const coordsData = await fetchCoordinates();
      if (!coordsData) {
        console.error("Failed to load coordinates data");
        return;
      }
      // ========== ポップアップ設定 ==========
      // useEffect内、マップ初期化後に追加

      // ポップアップを作成
      const popup = new mapboxgl.Popup({
        closeButton: true,
        closeOnClick: false,
      });

      // マーカークリック時にポップアップ表示
      map.on('click', 'yamanote-trains-circle', (e) => {
        const feature = e.features[0];
        const props = feature.properties;
        const coords = feature.geometry.coordinates;

        // GTFS Status をテキストに変換
        const getStatusText = (status) => {
          switch (status) {
            case 1: return '停車中';
            case 2: return '走行中';
            default: return status ? `不明(${status})` : 'N/A';
          }
        };

        // 駅IDから駅名を抽出（簡易）
        const getShortStationName = (stationId) => {
          if (!stationId) return 'N/A';
          return stationId.split('.').pop() || stationId;
        };

        const html = `
          <div style="font-family: sans-serif; font-size: 12px; min-width: 220px;">
            <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
              🚃 ${props.trainNumber} (${props.direction === 'OuterLoop' ? '外回り' : '内回り'})
            </h3>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td><b>品質:</b></td><td>${props.dataQuality || 'N/A'}</td></tr>
              <tr><td><b>状態:</b></td><td>${props.isStopped === 'true' || props.isStopped === true ? '停車中' : '走行中'}</td></tr>
              <tr><td><b>停車駅:</b></td><td>${getShortStationName(props.stationId)}</td></tr>
              <tr><td><b>区間:</b></td><td>${getShortStationName(props.fromStation)} → ${getShortStationName(props.toStation)}</td></tr>
              <tr><td><b>進捗:</b></td><td>${(parseFloat(props.progress) * 100).toFixed(1)}%</td></tr>
              <tr style="border-top: 1px solid #eee;"><td colspan="2" style="padding-top: 4px;"><b>GTFS-RT情報</b></td></tr>
              <tr><td><b>Stop Seq:</b></td><td>${props.stopSequence || 'N/A'}</td></tr>
              <tr><td><b>Status:</b></td><td>${getStatusText(props.gtfsStatus)}</td></tr>
              <tr style="border-top: 1px solid #eee;"><td colspan="2" style="padding-top: 4px;"><b>時刻情報</b></td></tr>
              <tr><td><b>${props.isStopped === 'true' || props.isStopped === true ? '到着時刻' : '前駅発車'}:</b></td><td>${formatTime(props.departureTimeRaw)}</td></tr>
              <tr><td><b>${props.isStopped === 'true' || props.isStopped === true ? '発車予定' : '次駅到着'}:</b></td><td>${formatTime(props.arrivalTimeRaw)}</td></tr>
              ${parseInt(props.delaySeconds) >= 60 ? `<tr><td><b style="color: ${parseInt(props.delaySeconds) >= 300 ? '#FF4500' : '#FFA500'}">遅延:</b></td><td style="color: ${parseInt(props.delaySeconds) >= 300 ? '#FF4500' : '#FFA500'}; font-weight: bold;">+${Math.floor(parseInt(props.delaySeconds) / 60)}分</td></tr>` : ''}
              <tr style="border-top: 1px solid #eee;"><td colspan="2" style="padding-top: 4px;"><b>座標</b></td></tr>
              <tr><td><b>現在位置:</b></td><td>${parseFloat(coords[1]).toFixed(5)}, ${parseFloat(coords[0]).toFixed(5)}</td></tr>
            </table>
          </div>
        `;

        popup.setLngLat(coords).setHTML(html).addTo(map);
      });

      // ★ 時刻表マーカー（Ghost）クリック時のポップアップ
      map.on('click', 'yamanote-trains-timetable-circle', (e) => {
        const feature = e.features[0];
        const props = feature.properties;
        const coords = feature.geometry.coordinates;

        const html = `
          <div style="font-family: sans-serif; font-size: 12px; min-width: 180px;">
            <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 4px; color: #888;">
              📍 ${props.trainNumber} - 時刻表位置
            </h3>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td><b>方向:</b></td><td>${props.direction === 'OuterLoop' ? '外回り' : '内回り'}</td></tr>
              <tr><td><b>タイプ:</b></td><td>時刻表ベース（予定位置）</td></tr>
              <tr><td><b>座標:</b></td><td>${parseFloat(coords[1]).toFixed(5)}, ${parseFloat(coords[0]).toFixed(5)}</td></tr>
            </table>
          </div>
        `;

        popup.setLngLat(coords).setHTML(html).addTo(map);
      });

      // ★ GTFS-RTマーカー（実測）クリック時のポップアップ
      map.on('click', 'yamanote-trains-gtfs-circle', (e) => {
        const feature = e.features[0];
        const props = feature.properties;
        const coords = feature.geometry.coordinates;

        const html = `
          <div style="font-family: sans-serif; font-size: 12px; min-width: 180px;">
            <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #FF5722; padding-bottom: 4px; color: #FF5722;">
              📡 ${props.trainNumber} - GTFS-RT位置
            </h3>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td><b>方向:</b></td><td>${props.direction === 'OuterLoop' ? '外回り' : '内回り'}</td></tr>
              <tr><td><b>タイプ:</b></td><td>GTFS-RT実測位置</td></tr>
              <tr><td><b>座標:</b></td><td>${parseFloat(coords[1]).toFixed(5)}, ${parseFloat(coords[0]).toFixed(5)}</td></tr>
            </table>
          </div>
        `;

        popup.setLngLat(coords).setHTML(html).addTo(map);
      });

      // カーソルをポインターに
      map.on('mouseenter', 'yamanote-trains-circle', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'yamanote-trains-circle', () => {
        map.getCanvas().style.cursor = '';
      });

      // ★ 時刻表マーカーのカーソル
      map.on('mouseenter', 'yamanote-trains-timetable-circle', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'yamanote-trains-timetable-circle', () => {
        map.getCanvas().style.cursor = '';
      });

      // ★ GTFS-RTマーカーのカーソル
      map.on('mouseenter', 'yamanote-trains-gtfs-circle', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'yamanote-trains-gtfs-circle', () => {
        map.getCanvas().style.cursor = '';
      });

      // 山手線データの抽出
      const yamanoteLine = railways.find((r) => r.id === YAMANOTE_ID);
      const yamanoteStationIds = yamanoteLine?.stations || [];

      const yamanoteStations = stations.filter((st) =>
        yamanoteStationIds.includes(st.id)
      );

      // 山手線の座標データを取得
      const railwayCoords = coordsData.railways || [];
      const yamanoteCoordsEntry = railwayCoords.find((c) => c.id === YAMANOTE_ID);

      let yamanoteCoords = [];
      if (yamanoteCoordsEntry && Array.isArray(yamanoteCoordsEntry.sublines)) {
        let previousEnd = null;

        for (const sub of yamanoteCoordsEntry.sublines) {
          if (!Array.isArray(sub.coords) || sub.coords.length === 0) continue;

          let coords = sub.coords;

          if (previousEnd) {
            const first = coords[0];
            const last = coords[coords.length - 1];

            const distFirst =
              (first[0] - previousEnd[0]) ** 2 + (first[1] - previousEnd[1]) ** 2;
            const distLast =
              (last[0] - previousEnd[0]) ** 2 + (last[1] - previousEnd[1]) ** 2;

            if (distLast < distFirst) {
              coords = [...coords].reverse();
            }
          }

          yamanoteCoords = yamanoteCoords.concat(coords);
          previousEnd = coords[coords.length - 1];
        }
      }

      console.log("Yamanote Line:", yamanoteLine);
      console.log("Yamanote Stations:", yamanoteStations.length);
      console.log("Yamanote Coords:", yamanoteCoords.length);

      // GeoJSON の構築
      const yamanoteLineFeature = {
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: yamanoteCoords,
        },
        properties: {
          id: YAMANOTE_ID,
          name_ja: yamanoteLine?.title?.ja || "山手線",
          name_en: yamanoteLine?.title?.en || "Yamanote Line",
        },
      };

      const yamanoteStationFeatures = yamanoteStations.map((st) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: st.coord,
        },
        properties: {
          id: st.id,
          railway: st.railway,
          name_ja: st.title?.ja || "",
          name_en: st.title?.en || "",
        },
      }));

      const yamanoteStationsCollection = {
        type: "FeatureCollection",
        features: yamanoteStationFeatures,
      };

      const yamanoteLineCollection = {
        type: "FeatureCollection",
        features: [yamanoteLineFeature],
      };

      // 山手線の線を追加
      map.addSource("yamanote-line", {
        type: "geojson",
        data: yamanoteLineCollection,
      });

      map.addLayer({
        id: "yamanote-line-layer",
        type: "line",
        source: "yamanote-line",
        paint: {
          "line-color": "#80C342", // 山手線の黄緑
          "line-width": 3,
        },
      });

      // 駅を追加
      map.addSource("yamanote-stations", {
        type: "geojson",
        data: yamanoteStationsCollection,
      });

      map.addLayer({
        id: "yamanote-stations-circle",
        type: "circle",
        source: "yamanote-stations",
        paint: {
          "circle-radius": 4,
          "circle-color": "#ffffff",
          "circle-stroke-color": "#000000",
          "circle-stroke-width": 1,
        },
      });

      map.addLayer({
        id: "yamanote-stations-label",
        type: "symbol",
        source: "yamanote-stations",
        layout: {
          "text-field": ["get", "name_ja"],
          "text-size": 10,
          "text-anchor": "top",
          "text-offset": [0, 0.6],
        },
        paint: {
          "text-color": "#000000",
          "text-halo-color": "#ffffff",
          "text-halo-width": 1,
        },
      });

      // 列車マーカー用ソース & レイヤー追加
      if (!map.getSource("yamanote-trains")) {
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
              10, ["case", ["==", ["get", "trainNumber"], trackedTrain || ""], 8, 4],
              14, ["case", ["==", ["get", "trainNumber"], trackedTrain || ""], 12, 8],
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
            "circle-color": [
              "case",
              // 追跡中は赤
              ["==", ["get", "trainNumber"], trackedTrain || ""],
              "#FF0000",
              // dataQuality: rejected (無効) = 紫
              ["==", ["get", "dataQuality"], "rejected"],
              "#9C27B0",
              // MS6: 遅延による色分け（step式）
              ["step",
                ["get", "delaySeconds"],
                "#00B140", // 0~59秒: 緑（定刻）
                60, "#FFA500", // 60~299秒: オレンジ（1~5分遅れ）
                300, "#FF4500" // 300秒~: 赤（5分以上遅れ）
              ]
            ],
            "circle-opacity": 0.9,
          },
        });
      }

      // ★ 比較表示用: 時刻表位置マーカー（Ghost - 半透明）
      if (!map.getSource("yamanote-trains-timetable")) {
        map.addSource("yamanote-trains-timetable", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });

        map.addLayer({
          id: "yamanote-trains-timetable-circle",
          type: "circle",
          source: "yamanote-trains-timetable",
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10, 3,
              14, 6,
            ],
            "circle-stroke-width": 1,
            "circle-stroke-color": "#888888",
            "circle-color": "#CCCCCC",
            "circle-opacity": 0.4,
          },
        });
      }

      // ★ 比較表示用: GTFS-RT実測位置マーカー（強調表示）
      if (!map.getSource("yamanote-trains-gtfs")) {
        map.addSource("yamanote-trains-gtfs", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });

        map.addLayer({
          id: "yamanote-trains-gtfs-circle",
          type: "circle",
          source: "yamanote-trains-gtfs",
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10, 4,
              14, 7,
            ],
            "circle-stroke-width": 3,
            "circle-stroke-color": "#FF5722",  // オレンジ系の強調色
            "circle-color": "#FFFFFF",
            "circle-opacity": 0.9,
          },
        });
      }

      // MS2: API の動作確認
      const apiData = await fetchLinesFromApi();
      console.log("API /api/lines result:", apiData);
    });

    return () => { };
  }, []);



  // stop_sequence → 駅インデックス
  function stopSeqToStationIndex(stopSeq, direction) {
    if (direction === 'OuterLoop') {
      return (stopSeq - 1) % 30;
    } else {
      return (32 - stopSeq - 1) % 30;
    }
  }

  // 次の駅インデックス
  function getNextStationIndex(currentIndex, direction) {
    if (direction === 'OuterLoop') {
      return (currentIndex + 1) % 30;
    } else {
      return (currentIndex - 1 + 30) % 30;
    }
  }

  // 2点間の線形補間
  function interpolatePosition(from, to, progress) {
    return {
      lat: from.lat + (to.lat - from.lat) * progress,
      lon: from.lon + (to.lon - from.lon) * progress,
    };
  }

  // ポーリング用 useEffect
  useEffect(() => {
    let intervalId = null;

    const fetchAndUpdate = async () => {
      const map = mapRef.current;
      if (!map) return;

      const src = map.getSource("yamanote-trains");
      if (!src) return;

      try {
        // ★ MS4: v4 API（TripUpdate-only）を使用
        const res = await fetch("/api/trains/yamanote/positions/v4");
        if (!res.ok) return;
        const json = await res.json();

        // v4 では positions 配列を使用
        const v4Positions = json.positions || [];

        // ★ MS4: v4レスポンスを既存のフラット構造にマッピング
        // 既存UIとの互換性を維持するため、既存プロパティ名に変換
        const gtfsTrains = v4Positions
          .filter(p => p.location && p.location.latitude != null && p.location.longitude != null)
          .map(p => {
            // dataQuality の擬似生成（既存の色分け互換）
            let dataQuality = 'good';
            if (p.status === 'unknown') {
              dataQuality = 'stale';
            } else if (p.status === 'invalid') {
              dataQuality = 'rejected';
            }

            return {
              // 既存プロパティ（フラット）
              trainNumber: p.train_number || '',
              tripId: p.trip_id,
              direction: p.direction,
              latitude: p.location.latitude,
              longitude: p.location.longitude,
              stopSequence: p.segment?.prev_seq || null,
              departureTime: p.times?.t0_departure || null,
              nextArrivalTime: p.times?.t1_arrival || null,
              isStopped: p.status === 'stopped',
              progress: p.progress,
              dataQuality: dataQuality,
              source: 'v4-tripupdate',
              // 追加情報
              status: p.status,
              fromStation: p.segment?.prev_station_id || null,
              toStation: p.segment?.next_station_id || null,
              stationId: p.status === 'stopped' ? p.segment?.prev_station_id : null,
              // MS6: 遅延情報
              delay: p.delay || 0,
              // 比較座標（v4では同じ座標を使う）
              timetableLatitude: null,
              timetableLongitude: null,
              gtfsLatitude: null,
              gtfsLongitude: null,
            };
          });

        // ★ デバッグ: v4 APIレスポンスの生データ確認
        if (gtfsTrains.length > 0) {
          const sample = gtfsTrains[0];
          console.log('[debug] v4 API response sample:', {
            trainNumber: sample.trainNumber,
            direction: sample.direction,
            stopSequence: sample.stopSequence,
            latitude: sample.latitude,
            longitude: sample.longitude,
            departureTime: sample.departureTime,
            nextArrivalTime: sample.nextArrivalTime,
            dataQuality: sample.dataQuality,
            source: sample.source,
          });
        }

        const now = Math.floor(Date.now() / 1000);  // 現在時刻（UNIXタイムスタンプ）
        // ★ デバッグ: 現在時刻とdepartureTimeの比較
        console.log('[debug] now:', now, 'date:', new Date(now * 1000).toLocaleTimeString('ja-JP'));

        // ========== stopSequence変化検知（GTFS-RT遅延計測用） ==========
        for (const train of gtfsTrains) {
          const prevState = trainStatesRef.current[train.trainNumber];

          if (prevState && prevState.stopSeq !== train.stopSequence) {
            // stopSequenceが変わった！= 新しい駅に到着した
            const prevStationIdx = stopSeqToStationIndex(prevState.stopSeq, train.direction);
            const newStationIdx = stopSeqToStationIndex(train.stopSequence, train.direction);
            const prevStation = YAMANOTE_STATIONS[prevStationIdx]?.id || '?';
            const newStation = YAMANOTE_STATIONS[newStationIdx]?.id || '?';

            const detectTime = new Date(now * 1000).toLocaleTimeString('ja-JP');
            const departureTimeStr = train.departureTime
              ? new Date(train.departureTime * 1000).toLocaleTimeString('ja-JP')
              : 'N/A';

            // 遅延 = 検知時刻 - 出発時刻（マイナスなら出発前に検知）
            const delay = train.departureTime ? (now - train.departureTime) : null;

            console.log(`%c[GTFS-RT更新検知] ${train.trainNumber}`, 'background: purple; color: white; font-size: 14px;');
            console.log({
              列車: train.trainNumber,
              方向: train.direction,
              区間変化: `${prevStation} → ${newStation}`,
              stopSeq変化: `${prevState.stopSeq} → ${train.stopSequence}`,
              検知時刻: detectTime,
              新駅出発予定: departureTimeStr,
              遅延秒数: delay !== null ? `${delay}秒` : 'N/A',
              備考: delay !== null && delay > 0 ? '⚠️ 出発時刻を過ぎてから検知' : '✓ 出発前に検知',
            });
            console.log('---');
          }

          // 状態を更新
          trainStatesRef.current[train.trainNumber] = {
            stopSeq: train.stopSequence,
            lastUpdate: now,
          };
        }

        // v4 API は既にブレンド済みの座標を返すのでそのまま使用
        const positions = gtfsTrains.map(train => {
          // 追跡中の列車を詳細ログ
          if (trackedTrainRef.current && train.trainNumber === trackedTrainRef.current) {
            console.log(`[TRACKED ${trackedTrainRef.current}] ===========================`);
            console.log({
              fromBackend: {
                latitude: train.latitude,
                longitude: train.longitude,
                fromStation: train.fromStation,
                toStation: train.toStation,
                progress: train.progress,
                direction: train.direction,
                isStopped: train.isStopped,
                stationId: train.stationId,
                dataQuality: train.dataQuality,
              },
              time: {
                now,
                timestamp: json.timestamp,
              }
            });
            console.log(`[TRACKED ${trackedTrainRef.current}] ===========================`);
          }

          return {
            lat: train.latitude,
            lon: train.longitude,
            direction: train.direction,
            trainNumber: train.trainNumber,
            fromStation: train.fromStation,
            toStation: train.toStation,
            progress: train.progress,
            isStopped: train.isStopped,
            stationId: train.stationId,
            dataQuality: train.dataQuality,
            // GTFS-RT情報
            stopSequence: train.stopSequence,
            gtfsStatus: train.status,
            // 時刻情報（v4 API）
            departureTimeRaw: train.departureTime,
            arrivalTimeRaw: train.nextArrivalTime,
            // MS6: 遅延情報
            delaySeconds: train.delay || 0,
            // 比較座標（v4ではない）
            timetableLat: train.timetableLatitude,
            timetableLon: train.timetableLongitude,
            gtfsLat: train.gtfsLatitude,
            gtfsLon: train.gtfsLongitude,
          };
        });

        // GeoJSON に変換（検索フィルタ適用）
        const query = searchQueryRef.current.trim().toLowerCase();
        const filteredPositions = query
          ? positions.filter(p => p.trainNumber.toLowerCase().includes(query))
          : positions;

        // 表示モードに応じてブレンドマーカーを表示/非表示
        const mode = displayModeRef.current;
        const showBlend = mode === 'all' || mode === 'blend';
        const showTimetable = mode === 'all' || mode === 'timetable';
        const showGtfs = mode === 'all' || mode === 'gtfs';

        const features = showBlend ? filteredPositions.map(p => ({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [p.lon, p.lat],
          },
          properties: { ...p },
        })) : [];

        // MS9: 目標位置を更新（アニメーション用）
        const animNow = performance.now();
        filteredPositions.forEach(p => {
          const key = p.trainNumber;
          const newTarget = [p.lon, p.lat];

          if (!trainPositionsRef.current[key]) {
            trainPositionsRef.current[key] = {
              current: newTarget.slice(),
              target: newTarget.slice(),
              startTime: animNow,
              properties: { ...p },
            };
          } else {
            const old = trainPositionsRef.current[key];
            trainPositionsRef.current[key] = {
              current: old.target.slice(),
              target: newTarget.slice(),
              startTime: animNow,
              properties: { ...p },
            };
          }
        });

        const activeTrains = new Set(filteredPositions.map(p => p.trainNumber));
        Object.keys(trainPositionsRef.current).forEach(key => {
          if (!activeTrains.has(key)) delete trainPositionsRef.current[key];
        });
        lastFetchTimeRef.current = animNow;

        src.setData({
          type: "FeatureCollection",
          features,
        });

        // ★ 比較表示用マーカーのデータを設定（検索フィルタ + 表示モード適用）
        const filteredGtfsTrains = query
          ? gtfsTrains.filter(t => t.trainNumber.toLowerCase().includes(query))
          : gtfsTrains;

        // 時刻表位置（Ghost）
        const timetableSrc = map.getSource("yamanote-trains-timetable");
        if (timetableSrc) {
          const timetableFeatures = showTimetable ? filteredGtfsTrains
            .filter(t => t.timetableLatitude && t.timetableLongitude)
            .map(t => ({
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: [t.timetableLongitude, t.timetableLatitude],
              },
              properties: {
                trainNumber: t.trainNumber,
                direction: t.direction,
                type: "timetable",
              },
            })) : [];
          timetableSrc.setData({
            type: "FeatureCollection",
            features: timetableFeatures,
          });
        }

        // GTFS-RT実測位置（強調）
        const gtfsSrc = map.getSource("yamanote-trains-gtfs");
        if (gtfsSrc) {
          const gtfsFeatures = showGtfs ? filteredGtfsTrains
            .filter(t => t.gtfsLatitude && t.gtfsLongitude)
            .map(t => ({
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: [t.gtfsLongitude, t.gtfsLatitude],
              },
              properties: {
                trainNumber: t.trainNumber,
                direction: t.direction,
                type: "gtfs",
              },
            })) : [];
          gtfsSrc.setData({
            type: "FeatureCollection",
            features: gtfsFeatures,
          });
        }

        // dataQuality 別の集計
        const qualityCounts = {};
        positions.forEach(p => {
          qualityCounts[p.dataQuality] = (qualityCounts[p.dataQuality] || 0) + 1;
        });
        console.log(`[v3 hybrid] trains: ${positions.length}`, qualityCounts);

        // 消失検知
        if (trackedTrain) {
          const found = positions.find(p => p.trainNumber === trackedTrain);
          if (!found) {
            console.error(`[TRACKED ${trackedTrain}] ⚠️⚠️⚠️ 消失！APIレスポンスに存在しない`);
          }
        }
      } catch (err) {
        console.error("[hybrid] error:", err);
      }
    };

    const startPolling = () => {
      fetchAndUpdate();
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

  return (
    <div style={{ position: 'relative', width: "100vw", height: "100vh" }}>
      {/* 列車追跡UI */}
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        zIndex: 1000,
        background: 'white',
        padding: '10px',
        borderRadius: '5px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
      }}>
        {/* 検索フィルタ */}
        <div style={{ marginBottom: '8px' }}>
          <span style={{ marginRight: '5px', fontWeight: 'bold' }}>🔍 検索:</span>
          <input
            type="text"
            placeholder="列車番号で絞り込み"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
            style={{
              width: '140px',
              marginRight: '10px',
              padding: '4px 8px',
              border: '1px solid #ccc',
              borderRadius: '4px',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              style={{
                padding: '4px 8px',
                cursor: 'pointer',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: '#f5f5f5',
              }}
            >
              クリア
            </button>
          )}
          {searchQuery && (
            <span style={{ marginLeft: '10px', fontSize: '12px', color: '#666' }}>
              フィルタ中: "{searchQuery}"
            </span>
          )}
        </div>
        {/* 追跡機能 */}
        <div style={{ marginBottom: '8px' }}>
          <span style={{ marginRight: '5px', fontWeight: 'bold' }}>📍 追跡:</span>
          <input
            type="text"
            placeholder="列車番号 (例: 005G)"
            onChange={(e) => setTrackedTrain(e.target.value.toUpperCase() || null)}
            style={{ width: '120px', marginRight: '5px' }}
          />
          <span style={{ fontSize: '12px', color: '#666' }}>
            {trackedTrain ? `追跡中: ${trackedTrain}` : '未選択'}
          </span>
        </div>
        {/* 表示モード切り替え */}
        <div>
          <span style={{ marginRight: '5px', fontWeight: 'bold' }}>👁 表示:</span>
          {[
            { mode: 'all', label: '全て' },
            { mode: 'blend', label: 'ブレンド' },
            { mode: 'timetable', label: '時刻表のみ' },
            { mode: 'gtfs', label: 'GTFS-RTのみ' },
          ].map(({ mode, label }) => (
            <button
              key={mode}
              onClick={() => setDisplayMode(mode)}
              style={{
                padding: '4px 8px',
                marginRight: '5px',
                cursor: 'pointer',
                border: displayMode === mode ? '2px solid #2196F3' : '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: displayMode === mode ? '#E3F2FD' : '#f5f5f5',
                fontWeight: displayMode === mode ? 'bold' : 'normal',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

export default App;