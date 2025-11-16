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
MIN_SCAN_INTERVAL: Final = timedelta(seconds=15)

# API endpoints
OVAPI_BASE_URL: Final = "http://v0.ovapi.nl"
NS_API_BASE_URL: Final = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2"
NS_DISRUPTIONS_BASE_URL: Final = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3"

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

# Timezone
TIMEZONE: Final = "Europe/Amsterdam"
