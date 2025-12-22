# backend/train_state.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

from zoneinfo import ZoneInfo

from timetable_models import TimetableTrain, StopTime

if TYPE_CHECKING:
    # 型ヒント用。実行時には import されないので循環 import を回避できる
    from data_cache import DataCache

JST = ZoneInfo("Asia/Tokyo")

# 04:00 から新しい「サービス日」が始まる
SERVICE_DAY_START_HOUR = 4

# ============================================================================
# Phase 1: Blend Constants (GTFS-RT + Timetable hybrid)
# ============================================================================
BLEND_FACTOR = 0.3              # 補正の強さ（0.0〜1.0）
STALE_THRESHOLD_SEC = 120       # これより古いGTFS-RTは無視（秒）
MAX_PROGRESS_DELTA = 0.5        # 進捗差がこれ以上なら異常値として無視（0.3→0.5に緩和）


# ============================================================================
# Dataclass 定義
# ============================================================================

SegmentType = Literal["moving", "stopped"]


@dataclass
class TrainSegment:
    """
    1本の列車についての1区間（走行 or 停車）を表す。

    時間範囲は [start_sec, end_sec) の半開区間で表現する。
    """
    train: TimetableTrain

    segment_type: SegmentType  # "moving" or "stopped"

    # 停車中セグメント用: 駅ID
    station_id: str | None

    # 走行中セグメント用: from → to 駅ID
    from_station_id: str | None
    to_station_id: str | None

    # サービス日開始（04:00）からの秒数
    start_sec: int
    end_sec: int


@dataclass
class TrainSectionState:
    """
    列車が今どこにいるか（停車 or 走行）を表す抽象状態。
    """
    train: TimetableTrain

    # 状態識別
    is_stopped: bool

    # 停車中の情報（is_stopped=Trueの場合のみ有効）
    stopped_at_station_id: str | None

    # 走行中の情報（is_stopped=Falseの場合のみ有効）
    from_station_id: str | None
    to_station_id: str | None
    progress: float  # 0.0〜1.0（停車中は 0.0 固定）

    # セグメント情報（デバッグ用）
    segment_type: SegmentType
    segment_start_sec: int
    segment_end_sec: int
    current_time_sec: int


# ============================================================================
# 時間系ユーティリティ
# ============================================================================

def get_service_date(dt_jst: datetime) -> datetime.date:
    """
    指定時刻が属する「サービス日」を返す。

    ルール:
      - 04:00〜翌03:59 までを1サービス日とみなす。
      - 深夜0〜3時台は「前日のサービス日」に属する。
    """
    if dt_jst.tzinfo is None:
        # 念のため JST として扱う
        dt_jst = dt_jst.replace(tzinfo=JST)

    if dt_jst.hour < SERVICE_DAY_START_HOUR:
        return (dt_jst - timedelta(days=1)).date()
    else:
        return dt_jst.date()


def to_effective_seconds(dt_jst: datetime) -> int:
    """
    サービス日開始（当日 or 前日 04:00）からの秒数を返す。

    例（SERVICE_DAY_START_HOUR = 4 の場合）:
      - 2025-01-15 04:00 JST → 0
      - 2025-01-15 05:00 JST → 3600
      - 2025-01-15 23:00 JST → 68400
      - 2025-01-16 02:00 JST → 79200
        （2025-01-15 のサービス日内 22:00 として扱う）
    """
    if dt_jst.tzinfo is None:
        dt_jst = dt_jst.replace(tzinfo=JST)

    service_date = get_service_date(dt_jst)
    service_start = datetime(
        service_date.year,
        service_date.month,
        service_date.day,
        0,  # 00:00 からの秒数を計算する（時刻表データと合わせるため）
        0,
        0,
        tzinfo=dt_jst.tzinfo,
    )
    delta = dt_jst - service_start
    return int(delta.total_seconds())


def determine_service_type(dt_jst: datetime) -> str:
    """
    指定日時から service_type を判定する。

    - 月〜金: "Weekday"
    - 土・日: "SaturdayHoliday"
    - 祝日判定や特別ダイヤは **MS4 以降の TODO** とする。
    """
    if dt_jst.tzinfo is None:
        dt_jst = dt_jst.replace(tzinfo=JST)

    service_date = get_service_date(dt_jst)
    weekday = service_date.weekday()  # 0=月, 6=日

    if weekday in (5, 6):  # 土・日
        return "SaturdayHoliday"
    else:
        return "Weekday"


# ============================================================================
# セグメント構築ロジック
# ============================================================================

def build_segments_for_train(train: TimetableTrain) -> list[TrainSegment]:
    """
    1本の TimetableTrain から TrainSegment のリストを構築する。

    - 時間範囲はすべて [start_sec, end_sec) の半開区間とする。
    - 到着/発車時刻が欠けている停車は「停車セグメントなし」として扱う。
    - 時刻が不正・逆転している場合は、その区間をスキップする。
    """
    segments: list[TrainSegment] = []
    stops = train.stops

    if len(stops) < 2:
        return segments  # 区間を構成できない

    # --- 停車セグメント ---
    for stop in stops:
        if stop.station_id is None:
            continue

        arr = stop.arrival_sec
        dep = stop.departure_sec

        # 到着＋発車の両方があり、正しい順序であれば停車セグメントを作る
        if arr is not None and dep is not None and dep > arr:
            segments.append(
                TrainSegment(
                    train=train,
                    segment_type="stopped",
                    station_id=stop.station_id,
                    from_station_id=None,
                    to_station_id=None,
                    start_sec=arr,
                    end_sec=dep,
                )
            )

    # --- 走行セグメント ---
    prev_stop: StopTime | None = None
    for stop in stops:
        if prev_stop is None:
            prev_stop = stop
            continue

        if prev_stop.station_id is None or stop.station_id is None:
            prev_stop = stop
            continue

        # 前駅の発車時刻
        dep = prev_stop.departure_sec or prev_stop.arrival_sec
        # 現在駅の到着時刻
        arr = stop.arrival_sec or stop.departure_sec

        if dep is None or arr is None:
            prev_stop = stop
            continue

        # 逆転・ゼロ長時間の区間はスキップ
        if arr <= dep:
            prev_stop = stop
            continue

        segments.append(
            TrainSegment(
                train=train,
                segment_type="moving",
                station_id=None,
                from_station_id=prev_stop.station_id,
                to_station_id=stop.station_id,
                start_sec=dep,
                end_sec=arr,
            )
        )

        prev_stop = stop

    # start_sec でソート（時系列順）
    segments.sort(key=lambda s: s.start_sec)
    return segments


def build_yamanote_segments(trains: list[TimetableTrain]) -> list[TrainSegment]:
    """
    山手線の TimetableTrain 一覧から、全 TrainSegment を構築する。

    - 引数は **必ず list** を渡す（filter オブジェクトなどは渡さない）。
    - service_type が "Weekday" / "SaturdayHoliday" 以外の列車については
      セグメントは作るが、後の get_yamanote_trains_at() で無視される。
      （起動時ログで気付けるようにする）
    """
    import logging

    logger = logging.getLogger(__name__)

    all_segments: list[TrainSegment] = []
    skipped_trains = 0
    unknown_service_types: set[str] = set()

    for train in trains:
        st = train.service_type or ""
        if st not in ("Weekday", "SaturdayHoliday"):
            unknown_service_types.add(st)

        segs = build_segments_for_train(train)
        if not segs:
            skipped_trains += 1
            continue

        all_segments.extend(segs)

    logger.info(
        "Built %d Yamanote train segments from %d trains (skipped %d trains with no segments)",
        len(all_segments),
        len(trains),
        skipped_trains,
    )

    if unknown_service_types:
        logger.warning(
            "Found Yamanote trains with unknown service_type values: %s. "
            "These trains will be ignored in get_yamanote_trains_at() for now.",
            sorted(unknown_service_types),
        )

    return all_segments


# ============================================================================
# セグメント → 現在状態 の変換
# ============================================================================

def _state_from_segment(seg: TrainSegment, current_sec: int) -> TrainSectionState | None:
    """
    1つの TrainSegment について、指定時刻 current_sec における状態を返す。

    - current_sec が [start_sec, end_sec) に含まれない場合は None を返す。
    - 含まれる場合のみ TrainSectionState を返す。
    """
    if current_sec < seg.start_sec or current_sec >= seg.end_sec:
        return None

    duration = seg.end_sec - seg.start_sec
    if duration <= 0:
        # 理論上起こらないが、防御的に None を返す
        return None

    if seg.segment_type == "stopped":
        # 停車中：駅上に表示、progress は常に 0.0
        return TrainSectionState(
            train=seg.train,
            is_stopped=True,
            stopped_at_station_id=seg.station_id,
            from_station_id=None,
            to_station_id=None,
            progress=0.0,
            segment_type=seg.segment_type,
            segment_start_sec=seg.start_sec,
            segment_end_sec=seg.end_sec,
            current_time_sec=current_sec,
        )

    # moving の場合: 0.0〜1.0 の位置に線形補間する
    progress = (current_sec - seg.start_sec) / duration
    # 浮動小数点誤差を防ぐため軽くクリップ
    if progress < 0.0:
        progress = 0.0
    elif progress > 1.0:
        progress = 1.0

    return TrainSectionState(
        train=seg.train,
        is_stopped=False,
        stopped_at_station_id=None,
        from_station_id=seg.from_station_id,
        to_station_id=seg.to_station_id,
        progress=progress,
        segment_type=seg.segment_type,
        segment_start_sec=seg.start_sec,
        segment_end_sec=seg.end_sec,
        current_time_sec=current_sec,
    )


# ============================================================================
# メイン関数
# ============================================================================

def get_yamanote_trains_at(
    dt_jst: datetime,
    data_cache: DataCache,
) -> list[TrainSectionState]:
    """
    指定 JST 時刻における「山手線の運行中列車の抽象状態」を返す。

    - DataCache.yamanote_segments を線形走査する。
    - service_type が "Weekday" / "SaturdayHoliday" 以外の列車は無視する。
    - エラーのあるセグメントはスキップし、ログに WARNING を出す。
    """
    import logging

    logger = logging.getLogger(__name__)

    if dt_jst.tzinfo is None:
        dt_jst = dt_jst.replace(tzinfo=JST)

    try:
        current_sec = to_effective_seconds(dt_jst)
        service_type = determine_service_type(dt_jst)
    except Exception as e:
        logger.error("Failed to process time parameters: %s", e)
        return []

    result: list[TrainSectionState] = []
    skipped_segments = 0

    for seg in data_cache.yamanote_segments:
        st = seg.train.service_type or ""

        # 現状、Weekday / SaturdayHoliday のみ表示対象
        if st not in ("Weekday", "SaturdayHoliday"):
            continue

        # 今日の service_type の列車だけを対象にする
        if st != service_type:
            continue

        try:
            state = _state_from_segment(seg, current_sec)
        except Exception as e:
            logger.warning(
                "Failed to calculate state for segment [%s %s→%s] at t=%d: %s",
                seg.train.base_id,
                seg.from_station_id or seg.station_id,
                seg.to_station_id or "停車",
                current_sec,
                e,
            )
            skipped_segments += 1
            continue

        if state is not None:
            result.append(state)

    if skipped_segments > 0:
        logger.info("Skipped %d segments due to errors", skipped_segments)

    return result


# ============================================================================
# デバッグ用関数
# ============================================================================

def debug_dump_trains_at(dt_jst: datetime, data_cache: DataCache, limit: int = 10) -> None:
    """
    指定時刻における山手線の列車状態をコンソールにダンプするデバッグ用関数。

    - 平日朝/深夜/土休日などの動作確認に使う。
    """
    states = get_yamanote_trains_at(dt_jst, data_cache)

    print("\n" + "=" * 60)
    print(f"時刻 (JST): {dt_jst.isoformat()}")
    print(f"サービス日: {get_service_date(dt_jst)}")
    print(f"サービス秒: {to_effective_seconds(dt_jst)}")
    print(f"運行列車数: {len(states)}")
    print("=" * 60 + "\n")

    for i, s in enumerate(states[:limit], 1):
        if s.is_stopped:
            print(
                f"{i:2d}. {s.train.number:>6s} {s.train.direction:>10s} "
                f"[停車] {s.stopped_at_station_id}"
            )
        else:
            print(
                f"{i:2d}. {s.train.number:>6s} {s.train.direction:>10s} "
                f"{s.from_station_id} → {s.to_station_id} "
                f"({s.progress * 100:5.1f}%)"
            )

    if len(states) > limit:
        print(f"\n... 他 {len(states) - limit} 本\n")


# ============================================================================
# Phase 1: Blend Logic (GTFS-RT + Timetable hybrid)
# ============================================================================

def blend_progress(
    ideal: float,
    rt: float,
    staleness_sec: float
) -> tuple[float, str]:
    """
    時刻表ベースの進捗とGTFS-RTベースの進捗をブレンドする。
    
    Args:
        ideal: 時刻表ベースの進捗 (0.0〜1.0)
        rt: GTFS-RTベースの進捗 (0.0〜1.0)
        staleness_sec: GTFS-RTデータの古さ（現在時刻 - GTFS-RTタイムスタンプ）
    
    Returns:
        (blended_progress, data_quality)
        - blended_progress: ブレンド後の進捗 (0.0〜1.0)
        - data_quality: "good" | "stale" | "rejected" | "timetable_only"
    """
    # 1. 鮮度チェック: データが古すぎたら時刻表のみ使用
    if staleness_sec > STALE_THRESHOLD_SEC:
        return (max(0.0, min(1.0, ideal)), "timetable_only")
    
    # 2. 乖離チェック: 差が大きすぎたら異常値として無視
    delta = rt - ideal
    if abs(delta) > MAX_PROGRESS_DELTA:
        return (max(0.0, min(1.0, ideal)), "rejected")
    
    # 3. ブレンド計算
    blended = ideal + BLEND_FACTOR * delta
    
    # 4. 結果を 0.0〜1.0 にクランプ
    blended = max(0.0, min(1.0, blended))
    
    # 5. データ品質の判定
    quality = "good" if staleness_sec < 60 else "stale"
    
    return (blended, quality)


# ============================================================================
# 将来のパフォーマンス最適化（TODO メモ）
# ============================================================================

# 将来の最適化用スケルトン（MS6 以降の TODO）

# from collections import defaultdict

# class SegmentIndex:
#     """
#     時刻帯別に TrainSegment をバケット分けして高速検索するためのインデックス。
#
#     現時点（MS3-2）では使わないが、全路線対応時のためにスケルトンだけ残しておく。
#     """
#     def __init__(self, segments: list[TrainSegment], bucket_seconds: int = 3600):
#         self.bucket_seconds = bucket_seconds
#         self.buckets: dict[int, list[TrainSegment]] = defaultdict(list)
#
#         for seg in segments:
#             start_bucket = seg.start_sec // bucket_seconds
#             end_bucket = (seg.end_sec - 1) // bucket_seconds
#             for b in range(start_bucket, end_bucket + 1):
#                 self.buckets[b].append(seg)
#
#     def query(self, time_sec: int) -> list[TrainSegment]:
#         bucket = time_sec // self.bucket_seconds
#         return [
#             s for s in self.buckets.get(bucket, [])
#             if s.start_sec <= time_sec < s.end_sec
#         ]
