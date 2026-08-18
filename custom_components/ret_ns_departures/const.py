"""Constants for the RET & NS Departures integration."""
from datetime import timedelta
from typing import Final

# Integration domain
DOMAIN: Final = "ret_ns_departures"

# Config flow
CONF_STOP_TYPE: Final = "stop_type"
CONF_STOP_ID: Final = "stop_id"
CONF_STOP_NAME: Final = "stop_name"
CONF_LINE_FILTER: Final = "line_filter"
CONF_NS_API_KEY: Final = "ns_api_key"
CONF_STATION_CODE: Final = "station_code"
CONF_STATION_NAME: Final = "station_name"
CONF_STATION_QUERY: Final = "station_query"
CONF_LOCATION: Final = "location"
CONF_STATION: Final = "station"
CONF_MAX_DEPARTURES: Final = "max_departures"
CONF_OPERATOR: Final = "operator"
CONF_MONITOR_DISRUPTIONS: Final = "monitor_disruptions"

# Stop types
STOP_TYPE_RET: Final = "ret"
STOP_TYPE_NS: Final = "ns"

# Operators
OPERATOR_RET: Final = "RET"
OPERATOR_NS: Final = "NS"

# Default values
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
DEFAULT_MAX_DEPARTURES: Final = 5
DEFAULT_STATION_RESULTS: Final = 20
MIN_SCAN_INTERVAL: Final = timedelta(seconds=15)
MIN_STATION_QUERY_LENGTH: Final = 2

# API endpoints
RET_BASE_URL: Final = "https://www.ret.nl/home/reizen/halte"
RET_SITE_URL: Final = "https://www.ret.nl/"
RET_SEARCH_TYPE: Final = "56895"
RET_SEARCH_CATEGORY_HALTES: Final = "Haltes"

# RET halt pages that exist but no longer carry departures. The live board
# lives on the replacement slug (check dienstregeling on ret.nl).
RET_STOP_ALIASES: Final = {
    "centraal-station": ("rotterdam-centraal",),
}
RET_DIVERSIONS_URL: Final = "https://www.ret.nl/home/reizen/omleidingen-verstoringen.html"
RET_DIENSTREGELING_BASE_URL: Final = "https://www.ret.nl/home/reizen/dienstregeling"
RET_DIVERSIONS_CACHE_SECONDS: Final = 900
NS_API_BASE_URL: Final = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2"
NS_DISRUPTIONS_BASE_URL: Final = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3"
NS_DISRUPTIONS_API_BASE_URL: Final = "https://gateway.apiportal.ns.nl/disruptions/v3"
NS_STATIONS_API_BASE_URL: Final = "https://gateway.apiportal.ns.nl/nsapp-stations/v2"
NS_VIRTUAL_TRAIN_API_BASE_URL: Final = (
    "https://gateway.apiportal.ns.nl/virtual-train-api/api/v1"
)
NS_SPOORKAART_API_BASE_URL: Final = (
    "https://gateway.apiportal.ns.nl/Spoorkaart-API/api/v1"
)

# Attribute keys
ATTR_DEPARTURES: Final = "departures"
ATTR_LINE: Final = "line"
ATTR_OPERATOR: Final = "operator"
ATTR_DESTINATION: Final = "destination"
ATTR_PLATFORM: Final = "platform"
ATTR_DELAY: Final = "delay"
ATTR_SCHEDULED_TIME: Final = "scheduled_time"
ATTR_ACTUAL_TIME: Final = "actual_time"
ATTR_STOP_NAME: Final = "stop_name"
ATTR_TRAIN_TYPE: Final = "train_type"
ATTR_TRIP_NUMBER: Final = "trip_number"
ATTR_DESCRIPTION: Final = "description"
ATTR_TRAIN_IMAGE: Final = "train_image"

# Disruption attributes
ATTR_DISRUPTIONS: Final = "disruptions"
ATTR_DISRUPTION_ID: Final = "disruption_id"
ATTR_DISRUPTION_TITLE: Final = "title"
ATTR_DISRUPTION_TYPE: Final = "disruption_type"
ATTR_DISRUPTION_IMPACT: Final = "impact"
ATTR_DISRUPTION_START: Final = "start"
ATTR_DISRUPTION_END: Final = "end"
ATTR_DISRUPTION_CAUSE: Final = "cause"
ATTR_DISRUPTION_PHASE: Final = "phase"
ATTR_DISRUPTION_STATIONS: Final = "stations"
ATTR_DISRUPTION_STATION_CODES: Final = "station_codes"
ATTR_DISRUPTION_LEVEL: Final = "level"
ATTR_DISRUPTION_MAP_TYPE: Final = "map_type"
ATTR_DISRUPTION_GEOMETRY_TYPE: Final = "geometry_type"
ATTR_DISRUPTION_BBOX: Final = "bbox"
ATTR_LATITUDE: Final = "latitude"
ATTR_LONGITUDE: Final = "longitude"
ATTR_GEOJSON: Final = "geojson"
ATTR_MESSAGE: Final = "message"
ATTR_SITUATION: Final = "situation"
ATTR_ADDITIONAL_TRAVEL_TIME: Final = "additional_travel_time"
ATTR_EXPECTED_DURATION: Final = "expected_duration"
ATTR_PERIOD: Final = "period"
ATTR_OTHER_DISRUPTIONS: Final = "other_disruptions"

# Timezone
TIMEZONE: Final = "Europe/Amsterdam"
