# backend/constants.py
"""
ODPT API constants and route definitions for NowTrain.
"""

# ODPT API Base URL
# Note: api-challenge.odpt.org is used for JR-East GTFS-RT data
ODPT_BASE_URL = "https://api-challenge.odpt.org/api/v4"

# GTFS-RT endpoints (JR-East)
TRIP_UPDATE_URL = f"{ODPT_BASE_URL}/gtfs/realtime/jreast_odpt_train_trip_update"
VEHICLE_POSITION_URL = f"{ODPT_BASE_URL}/gtfs/realtime/jreast_odpt_train_vehicle"

# 山手線 route_id (GTFS / ODPT体系)
YAMANOTE_ROUTE_ID = "JR-East.Yamanote"

# サービスタイプ定数
SERVICE_TYPE_WEEKDAY = "Weekday"
SERVICE_TYPE_SATURDAY_HOLIDAY = "SaturdayHoliday"
SERVICE_TYPE_UNKNOWN = "Unknown"

# HTTP timeout (seconds)
HTTP_TIMEOUT = 10.0
