import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { fetchRailways, fetchStations, fetchCoordinates } from "./api/staticData";
import { fetchLinesFromApi } from "./api/serverData";

const YAMANOTE_ID = "JR-East.Yamanote";
const TRAIN_UPDATE_INTERVAL_MS = 2000;

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

  // ========== GTFS-RT更新遅延計測用 ==========
  const trainStatesRef = useRef({});  // { trainNumber: { stopSeq, lastUpdate } }

  // trackedTrain同期
  useEffect(() => {
    trackedTrainRef.current = trackedTrain;
  }, [trackedTrain]);

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

        // 時刻をフォーマット
        const formatTime = (unix) => {
          if (!unix) return 'N/A';
          const d = new Date(unix * 1000);
          return d.toLocaleTimeString('ja-JP');
        };

        // 駅名を取得
        const getStationName = (index) => {
          if (index < 0 || index >= YAMANOTE_STATIONS.length) return '不明';
          return YAMANOTE_STATIONS[index].id;
        };

        const currentStationIdx = props.currentStationIndex;
        const nextStationIdx = props.nextStationIndex;

        const html = `
          <div style="font-family: sans-serif; font-size: 12px; min-width: 200px;">
            <h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
              ${props.trainNumber} (${props.direction === 'OuterLoop' ? '外回り' : '内回り'})
            </h3>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td><b>状態:</b></td><td>${props.source} ${props.interpolated ? '(補間中)' : ''}</td></tr>
              <tr><td><b>現在駅:</b></td><td>${getStationName(currentStationIdx)} (seq: ${props.stopSequence})</td></tr>
              <tr><td><b>次の駅:</b></td><td>${getStationName(nextStationIdx)}</td></tr>
              <tr><td><b>発車時刻:</b></td><td>${formatTime(props.departureTime)}</td></tr>
              <tr><td><b>次駅到着:</b></td><td>${formatTime(props.nextArrivalTime)}</td></tr>
              <tr><td><b>GTFS-RT更新:</b></td><td>${formatTime(props.timestamp)}</td></tr>
              <tr><td><b>座標:</b></td><td>${coords[1].toFixed(4)}, ${coords[0].toFixed(4)}</td></tr>
              <tr><td><b>GTFS座標:</b></td><td>${props.gtfsLat?.toFixed(4)}, ${props.gtfsLon?.toFixed(4)}</td></tr>
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
              // dataQuality: good (ブレンド成功) = 青
              ["==", ["get", "dataQuality"], "good"],
              "#2196F3",
              // dataQuality: stale (古いGTFS-RT) = 水色
              ["==", ["get", "dataQuality"], "stale"],
              "#00BCD4",
              // dataQuality: rejected (乖離大) = 紫
              ["==", ["get", "dataQuality"], "rejected"],
              "#9C27B0",
              // dataQuality: timetable_only = 黄色
              ["==", ["get", "dataQuality"], "timetable_only"],
              "#FFEB3B",
              // 停車中（外回り）は緑
              ["all", ["==", ["get", "isStopped"], true], ["==", ["get", "direction"], "OuterLoop"]],
              "#80C342",
              // 停車中（内回り）はオレンジ
              ["all", ["==", ["get", "isStopped"], true], ["==", ["get", "direction"], "InnerLoop"]],
              "#FF9500",
              // フォールバック
              "#80C342",
            ],
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
        // v3 API（出発時刻付き）を使用
        const res = await fetch("/api/trains/yamanote/positions/v3");
        if (!res.ok) return;
        const json = await res.json();
        const gtfsTrains = json.trains || [];

        // ★ デバッグ: APIレスポンスの生データ確認
        if (gtfsTrains.length > 0) {
          const sample = gtfsTrains[0];
          console.log('[debug] API response sample:', {
            trainNumber: sample.trainNumber,
            direction: sample.direction,
            stopSequence: sample.stopSequence,
            latitude: sample.latitude,
            longitude: sample.longitude,
            departureTime: sample.departureTime,
            nextArrivalTime: sample.nextArrivalTime,
            timestamp: sample.timestamp,  // これがundefinedかも
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

        // v3 API は既にブレンド済みの座標を返すのでそのまま使用
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
          };
        });

        // GeoJSON に変換
        const features = positions.map(p => ({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [p.lon, p.lat],
          },
          properties: { ...p },
        }));

        src.setData({
          type: "FeatureCollection",
          features,
        });

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
      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

export default App;