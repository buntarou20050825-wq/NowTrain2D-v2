# backend/data_cache.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from timetable_models import StopTime, TimetableTrain
from train_state import TrainSegment, build_yamanote_segments

logger = logging.getLogger(__name__)


def _is_valid_coord(lon: float, lat: float) -> bool:
    """
    座標が日本付近の妥当な範囲にあるかざっくりチェックする
    """
    return (122.0 <= lon <= 154.0) and (20.0 <= lat <= 46.0)

def _parse_time_to_seconds(time_str: str) -> int:
    """
    "HH:MM" または "HH:MM:SS" 形式の文字列を 0〜86399 の秒に変換する。
    不正な形式の場合は ValueError を発生させる。

    NOTE:
      - 現状は "24:00" や "24:xx" は **不正な形式として扱いエラー** にします。
      - 実データに "24:00" などが含まれている場合は、ログに警告が出て
        該当の stop はスキップされます。
      - TODO(MS3 以降):
        - "24:00" を 00:00 + 24h として解釈するか、
        - 23:59:59 に clamp するか、
        - 仕様として明確に決める必要があります。
    """
    if not time_str:
        raise ValueError("Empty time string")

    parts = time_str.split(":")
    if len(parts) == 2:
        h, m = parts
        s = "0"
    elif len(parts) == 3:
        h, m, s = parts
    else:
        raise ValueError(f"Invalid time format: {time_str} (expected HH:MM or HH:MM:SS)")

    try:
        hour = int(h)
        minute = int(m)
        second = int(s)
    except ValueError as e:
        raise ValueError(f"Invalid time components in '{time_str}': {e}")

    if not (0 <= hour <= 23):
        raise ValueError(f"Invalid hour {hour} in '{time_str}' (must be 0-23)")
    if not (0 <= minute <= 59):
        raise ValueError(f"Invalid minute {minute} in '{time_str}' (must be 0-59)")
    if not (0 <= second <= 59):
        raise ValueError(f"Invalid second {second} in '{time_str}' (must be 0-59)")

    return hour * 3600 + minute * 60 + second


def _normalize_stop_times(raw_tt: List[Dict[str, Any]]) -> List[StopTime]:
    """
    raw_tt: [{"s": station_id, "d": "HH:MM", "a": "HH:MM" 省略可}, ...]
    を StopTime のリストに変換し、
    列車内で時刻が単調増加になるように日跨ぎ（+24h）補正を行う。

    NOTE:
      - 「代表時刻（rep_sec）」として、発車があれば発車、それ以外は到着を使います。
      - 代表時刻が前より小さくなった場合、日付を跨いだとみなして day_offset += 24h。
      - arrival/dep 両方 None の stop は、日跨ぎ判定の起点にはなりません。
        （意図的に「時間情報なしの行は日跨ぎ判定の対象外」としています）
    """
    result: List[StopTime] = []

    day_offset = 0
    prev_rep_sec: int | None = None  # 代表時刻（比較用）

    for i, row in enumerate(raw_tt):
        station_id = row.get("s")
        if not station_id:
            logger.warning("Timetable row %d has no station id 's', skipping", i)
            continue

        dep_str = row.get("d")
        arr_str = row.get("a")

        # 両方とも None の場合は、その駅の時間情報がない → そのまま None で登録
        if dep_str is None and arr_str is None:
            result.append(
                StopTime(
                    station_id=station_id,
                    arrival_sec=None,
                    departure_sec=None,
                )
            )
            # NOTE:
            #   - この stop は rep_sec を持たず、日跨ぎ判定の起点にもなりません。
            continue

        try:
            dep_sec: int | None = _parse_time_to_seconds(dep_str) if dep_str else None
            arr_sec: int | None = _parse_time_to_seconds(arr_str) if arr_str else None
        except ValueError as e:
            logger.warning(
                "[Yamanote timetable] Failed to parse time at stop %d (station %s): %s",
                i,
                station_id,
                e,
            )
            dep_sec = None
            arr_sec = None

        # 代表時刻（比較用）：発車があれば発車、それ以外は到着
        rep_sec: int | None = dep_sec if dep_sec is not None else arr_sec

        # 代表時刻が前より小さい → 日付を跨いだとみなす（+24時間）
        if rep_sec is not None and prev_rep_sec is not None and rep_sec < prev_rep_sec:
            day_offset += 24 * 3600

        if dep_sec is not None:
            dep_sec += day_offset
        if arr_sec is not None:
            arr_sec += day_offset

        if rep_sec is not None:
            prev_rep_sec = rep_sec + day_offset

        result.append(
            StopTime(
                station_id=station_id,
                arrival_sec=arr_sec,
                departure_sec=dep_sec,
            )
        )

    return result


def _validate_train_data(train: TimetableTrain) -> List[str]:
    """
    列車データの簡易妥当性チェック。
    問題があれば warning メッセージのリストを返す。
    """
    warnings: List[str] = []

    # 1. 停車駅数
    if len(train.stops) < 2:
        warnings.append(f"too few stops: {len(train.stops)}")

    # 2. 時刻の単調増加チェック（日跨ぎ補正後）
    prev_sec: int | None = None
    for i, stop in enumerate(train.stops):
        sec = stop.departure_sec if stop.departure_sec is not None else stop.arrival_sec
        if sec is None:
            continue
        if prev_sec is not None and sec < prev_sec:
            warnings.append(f"non-monotonic time at stop index {i} ({stop.station_id})")
            break
        prev_sec = sec

    # 3. 始発駅と最初の stop の一致チェック
    if train.origin_stations and train.stops:
        first_stop_id = train.stops[0].station_id
        if first_stop_id not in train.origin_stations:
            warnings.append(
                f"first stop {first_stop_id} not in origin_stations {train.origin_stations}"
            )

    return warnings


def _parse_yamanote_timetables(raw_data: List[Dict[str, Any]]) -> List[TimetableTrain]:
    """
    jreast-yamanote.json の配列を TimetableTrain リストに変換する。
    不正なデータはスキップし、警告ログを出す。

    NOTE:
      - service_type は id の末尾から推定（例: "Weekday", "Holiday"）。
      - 上記に当てはまらない場合は "Unknown" としてログに警告を出す。
      - destination_stations:
          - ds が存在すれば ds をそのまま使用（複数あれば複数のまま保持）。
          - ds が無い場合は、tt の最後の station_id を終着駅とみなす。
    """
    trains: List[TimetableTrain] = []
    skipped_count = 0

    for idx, row in enumerate(raw_data):
        try:
            full_id: str = row.get("id", "")
            if not full_id:
                logger.warning("Train at index %d has no 'id', skipping", idx)
                skipped_count += 1
                continue

            base_id: str = row.get("t", full_id)
            line_id: str = row.get("r", "")
            number: str = row.get("n", "")
            train_type: str = row.get("y", "")
            direction: str = row.get("d", "")

            # service_type を id の末尾から推定
            service_type = "Unknown"
            if "." in full_id:
                suffix = full_id.split(".")[-1]
                service_type = suffix
                if suffix not in ("Weekday", "Holiday"):
                    logger.info(
                        "Yamanote train %s has non-standard service_type suffix '%s'; "
                        "service_type will be '%s'",
                        full_id,
                        suffix,
                        service_type,
                    )
            else:
                logger.info(
                    "Yamanote train %s has no '.' in id, service_type set to 'Unknown'",
                    full_id,
                )

            origin_stations = row.get("os") or []

            # 終着駅：
            # 1. tt の最後の駅を候補にする
            # 2. ds フィールドがあれば ds を優先（複数あれば複数のまま）
            destination_stations: List[str] = []
            raw_tt = row.get("tt") or []
            if raw_tt:
                last_stop = raw_tt[-1]
                last_station = last_stop.get("s")
                if last_station:
                    destination_stations = [last_station]

            if "ds" in row and row["ds"]:
                # ds が複数ある場合、そのまま複数保持する
                destination_stations = list(row["ds"])

            stops = _normalize_stop_times(raw_tt)

            # 最低限のデータ検証
            if not stops:
                logger.warning("Train %s has no valid stops, skipping", full_id)
                skipped_count += 1
                continue

            train = TimetableTrain(
                base_id=base_id,
                service_type=service_type,
                line_id=line_id,
                number=number,
                train_type=train_type,
                direction=direction,
                origin_stations=origin_stations,
                destination_stations=destination_stations,
                stops=stops,
            )

            # 簡易検証（任意）
            warnings = _validate_train_data(train)
            if warnings:
                logger.warning(
                    "Train %s validation warnings: %s", full_id, "; ".join(warnings)
                )

            trains.append(train)

        except Exception as e:
            logger.error("Failed to parse train at index %d: %s", idx, e)
            skipped_count += 1
            continue

    if skipped_count > 0:
        logger.warning("Skipped %d Yamanote timetable trains due to errors", skipped_count)

    return trains


class DataCache:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.railways: List[Dict[str, Any]] = []
        self.stations: List[Dict[str, Any]] = []
        self.coordinates: Dict[str, Any] = {}

        # MS3-1: 山手線の時刻表（TimetableTrain の配列）
        self.yamanote_trains: List[TimetableTrain] = []

        # MS3-2: 山手線のセグメント（TrainSegment の配列）
        self.yamanote_segments: List[TrainSegment] = []

        # MS3-3: 駅座標インデックス
        self.station_positions: Dict[str, tuple[float, float]] = {}

        # MS3-5: 線路形状追従用
        self.track_points: List[tuple[float, float]] = []  # 山手線全周の座標リスト
        self.station_track_indices: Dict[str, int] = {}    # 駅ID → track_pointsのインデックス

        # MS1-TripUpdate: 列車番号から静的列車データへのインデックス
        # key: (train_number, service_type), value: TimetableTrain
        self._train_lookup: Dict[tuple[str, str], TimetableTrain] = {}
        # key: (train_number, service_type), value: {stop_sequence: station_id}
        self._seq_to_station_cache: Dict[tuple[str, str], Dict[int, str]] = {}

        # TODO (MS6): パフォーマンス最適化
        # self.railways_by_id: Dict[str, Dict[str, Any]] = {}
        # self.stations_by_id: Dict[str, Dict[str, Any]] = {}

    def _load_json(self, rel_path: str) -> Any:
        path = self.data_dir / rel_path
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_all(self) -> None:
        """全ての静的データを読み込む（MS1+MS2+MS3-1 用）"""
        # 1) MS2 までのデータ
        self.railways = self._load_json("mini-tokyo-3d/railways.json")
        self.stations = self._load_json("mini-tokyo-3d/stations.json")
        self.coordinates = self._load_json("mini-tokyo-3d/coordinates.json")

        logger.info("Loaded %d railways, %d stations", len(self.railways), len(self.stations))

        # 2) MS3-1: 山手線の時刻表
        try:
            raw_yamanote = self._load_json("mini-tokyo-3d/train-timetables/jreast-yamanote.json")
        except FileNotFoundError:
            logger.error(
                "Yamanote timetable file not found. "
                "Expected at: %s",
                self.data_dir / "train-timetables/jreast-yamanote.json",
            )
            logger.error(
                "Please copy jreast-yamanote.json from mini-tokyo-3d/data/train-timetables "
                "into data/train-timetables/."
            )
            # MS3-1 では、時刻表が無くても他の API を動かせるように空で継続
            self.yamanote_trains = []
            return

        self.yamanote_trains = _parse_yamanote_timetables(raw_yamanote)

        logger.info("Loaded %d Yamanote timetable trains", len(self.yamanote_trains))
        if self.yamanote_trains:
            service_types = {t.service_type for t in self.yamanote_trains}
            logger.info("Yamanote service types: %s", sorted(service_types))

        # MS3-2: 山手線のセグメントを構築
        self.yamanote_segments = build_yamanote_segments(self.yamanote_trains)
        logger.info("Built %d Yamanote train segments", len(self.yamanote_segments))

        # MS1-TripUpdate: 列車検索インデックスを構築
        self._build_train_lookup_index()

        # MS3-3: 駅座標インデックスの構築
        station_positions: Dict[str, tuple[float, float]] = {}

        for st in self.stations:
            station_id = st.get("id")
            coord = st.get("coord")

            if not station_id or not coord or len(coord) < 2:
                continue

            lon, lat = float(coord[0]), float(coord[1])
            if not _is_valid_coord(lon, lat):
                logger.warning(
                    "Station %s has invalid coord %s; skipping", station_id, coord
                )
                continue

            station_positions[station_id] = (lon, lat)

        self.station_positions = station_positions
        logger.info("Built %d station positions", len(self.station_positions))

        # MS3-5: 線路形状データの読み込みと駅マッピング
        self._load_track_coordinates()

        # MS3-3: 山手線時刻表の駅IDが station_positions に存在するか検証
        missing_station_ids: set[str] = set()

        for train in self.yamanote_trains:
            for stop in train.stops:
                if stop.station_id not in self.station_positions:
                    missing_station_ids.add(stop.station_id)

        if missing_station_ids:
            logger.warning(
                "Missing positions for %d station IDs used in Yamanote timetable "
                "(first 10): %s",
                len(missing_station_ids),
                sorted(list(missing_station_ids))[:10],
            )
        else:
            logger.info("All Yamanote timetable station IDs have positions")

    def _load_track_coordinates(self) -> None:
        """
        MS3-5: coordinates.json から山手線の線路座標を読み込み、
        各駅の最寄りインデックスを計算する。
        """
        # 1. coordinates.json をロード（既に load_all で self.coordinates にロード済み）
        if not self.coordinates:
            logger.warning("Coordinates data not loaded, skipping track loading")
            return

        # 2. JR-East.Yamanote の座標データを抽出
        yamanote_coords: List[tuple[float, float]] = []
        railways_coords = self.coordinates.get("railways", [])
        
        target_railway = None
        for r in railways_coords:
            if r.get("id") == "JR-East.Yamanote":
                target_railway = r
                break
        
        if not target_railway:
            logger.warning("JR-East.Yamanote not found in coordinates.json")
            return

        sublines = target_railway.get("sublines", [])
        for subline in sublines:
            coords = subline.get("coords", [])
            # リストのリストになっている場合があるので注意（データ構造依存）
            # coordinates.json の仕様では coords は [[lon, lat], ...]
            for c in coords:
                if len(c) >= 2:
                    yamanote_coords.append((float(c[0]), float(c[1])))

        # 3. 隣接する重複座標を除去
        self.track_points = []
        for coord in yamanote_coords:
            if not self.track_points or self.track_points[-1] != coord:
                self.track_points.append(coord)
        
        logger.info("Loaded %d track points for Yamanote Line", len(self.track_points))

        # 4. 各駅の最寄りインデックスを計算
        self.station_track_indices = {}
        
        # 山手線の駅のみ対象
        yamanote_station_ids = set()
        for train in self.yamanote_trains:
            for stop in train.stops:
                yamanote_station_ids.add(stop.station_id)
        
        mapped_count = 0
        for station_id in yamanote_station_ids:
            coord = self.station_positions.get(station_id)
            if not coord:
                continue
            
            # 最も近い点を探索
            min_dist = float('inf')
            min_idx = 0
            
            for i, track_coord in enumerate(self.track_points):
                # ユークリッド距離の2乗で比較（平方根計算を省略）
                dist_sq = (coord[0] - track_coord[0]) ** 2 + (coord[1] - track_coord[1]) ** 2
                if dist_sq < min_dist:
                    min_dist = dist_sq
                    min_idx = i
            
            self.station_track_indices[station_id] = min_idx
            mapped_count += 1
            
        logger.info("Mapped %d stations to track indices", mapped_count)

    # ========================================================================
    # MS1-TripUpdate: 列車検索・駅マッピングメソッド
    # ========================================================================

    def _build_train_lookup_index(self) -> None:
        """
        列車番号+サービスタイプから TimetableTrain を引けるインデックスを構築する。
        同時に stop_sequence -> station_id のマップもキャッシュする。
        """
        self._train_lookup.clear()
        self._seq_to_station_cache.clear()

        for train in self.yamanote_trains:
            key = (train.number, train.service_type)
            
            # 同一キーが重複する場合は最初のものを使用
            if key not in self._train_lookup:
                self._train_lookup[key] = train
                
                # stop_sequence -> station_id マップを構築
                # TimetableTrain.stops には stop_sequence がないので、
                # enumerate で 1 始まりの連番を生成する
                seq_map: Dict[int, str] = {}
                for seq, stop in enumerate(train.stops, start=1):
                    seq_map[seq] = stop.station_id
                
                self._seq_to_station_cache[key] = seq_map

        logger.info(
            "Built train lookup index: %d entries, %d seq-to-station maps",
            len(self._train_lookup),
            len(self._seq_to_station_cache)
        )

    def get_static_train(
        self, train_number: str | None, service_type: str | None
    ) -> TimetableTrain | None:
        """
        列車番号から静的時刻表データを検索する。
        
        Args:
            train_number: 列車番号 (例: "301G")
            service_type: サービスタイプ (例: "Weekday", "SaturdayHoliday")
                          指定されている場合は、そのタイプを優先する。
        
        Returns:
            見つかった TimetableTrain、見つからない場合は None
        """
        if not train_number:
            return None
        
        # 1. 完全一致を試す
        if service_type:
            result = self._train_lookup.get((train_number, service_type))
            if result:
                return result
        
        # 2. サービスタイプ関係なく探す（最初に見つかったものを返す）
        for (num, st), train in self._train_lookup.items():
            if num == train_number:
                return train
        
        return None

    def get_seq_to_station_map(
        self, train_number: str | None, service_type: str | None
    ) -> Dict[int, str] | None:
        """
        列車の stop_sequence -> station_id マップを取得する。
        
        Args:
            train_number: 列車番号 (例: "301G")
            service_type: サービスタイプ (例: "Weekday")
        
        Returns:
            {stop_sequence: station_id} のマップ、見つからない場合は None
        """
        if not train_number:
            return None
        
        # 1. 完全一致を試す
        if service_type:
            result = self._seq_to_station_cache.get((train_number, service_type))
            if result:
                return result
        
        # 2. サービスタイプ関係なく探す
        for (num, st), seq_map in self._seq_to_station_cache.items():
            if num == train_number:
                return seq_map
        
        return None
