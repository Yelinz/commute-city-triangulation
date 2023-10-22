import streamlit as st
import pandas as pd
import gtfs_kit
import folium
import seaborn
from streamlit_folium import st_folium


@st.cache_data
def load_feed():
    return gtfs_kit.read_feed("gtfs_fp2024_2023-10-18_04-15.zip", dist_units="km")

@st.cache_data
def parse_stations(_feed):
    return _feed.stops.loc[_feed.stops.stop_id.str.contains("Parent")]

@st.cache_data
def get_routes(_feed, station_id):
    platforms = _feed.stops.loc[_feed.stops["parent_station"] == station_id]
    all_stop_times = _feed.stop_times.loc[_feed.stop_times["stop_id"].isin(platforms["stop_id"].values)]
    route_ids = _feed.trips.loc[_feed.trips["trip_id"].isin(all_stop_times["trip_id"].unique())]["route_id"].unique()
    all_routes = _feed.routes.loc[_feed.routes["route_id"].isin(route_ids)]
    # EXT are special trains, not usually accessible
    routes = all_routes.loc[all_routes["route_short_name"] != "EXT"]
    return routes

@st.cache_data
def get_trips(_feed, route_ids):
    route_trips = _feed.trips.loc[_feed.trips["route_id"].isin(route_ids)]

    # all stops of the trips
    relevant_stops = _feed.stop_times.loc[
        _feed.stop_times["trip_id"].isin(route_trips["trip_id"].values)
    ]

    # parse arrival and departure to timedeltas
    relevant_stops.loc[:, "arrival_time_parsed"] = pd.to_timedelta(
        relevant_stops["arrival_time"]
    )
    relevant_stops.loc[:, "departure_time_parsed"] = pd.to_timedelta(
        relevant_stops["departure_time"]
    )

    # limit arrival and departure to "normal" times 06-22
    # pickup, dropoff type not 0 means no normal passenger transfer
    filtered_stops = relevant_stops.loc[
        ((relevant_stops["pickup_type"] == 0) & (relevant_stops["drop_off_type"] == 0))
        & (
            (
                (relevant_stops["arrival_time_parsed"] > pd.Timedelta(6, unit="h"))
                & (relevant_stops["arrival_time_parsed"] < pd.Timedelta(22, unit="h"))
            )
            | (
                (relevant_stops["departure_time_parsed"] > pd.Timedelta(6, unit="h"))
                & (relevant_stops["departure_time_parsed"] < pd.Timedelta(22, unit="h"))
            )
        )
    ]

    merged = pd.merge(route_trips, filtered_stops, on="trip_id")

    # find longest trip, so the path generation does not get confused by direction or shorter trips
    # might be problematic if the longest is a rare trip and not representative of the usual stops
    longest_trips = merged.loc[merged.groupby(["route_id"])["stop_sequence"].idxmax()]
    longest_trips_stop_times = _feed.stop_times.loc[
        _feed.stop_times["trip_id"].isin(longest_trips["trip_id"].values)
    ]

    # find stops to display
    longest_trips_parent_stops = _feed.stops.loc[
        _feed.stops.loc[:, "stop_id"].isin(longest_trips_stop_times["stop_id"].values)
    ]

    # parent stops and stops with no parent
    all_stops = pd.concat(
        [
            longest_trips_parent_stops.drop_duplicates(["parent_station"]),
            longest_trips_parent_stops[longest_trips_parent_stops["parent_station"].isna()],
        ]
    )


    # join all the data into one dataframe
    stop_data = pd.merge(longest_trips_stop_times, route_trips, on="trip_id")
    # TODO stop_data = pd.merge(stop_data, routes, on="route_id")
    stop_data = pd.merge(stop_data, longest_trips_parent_stops, on="stop_id")
    longest_trips_stop_times.loc[longest_trips_stop_times["trip_id"] == "258.TA.91-21-D-j23-1.76.H"]
    relevant_stops.loc[relevant_stops["trip_id"] == "258.TA.91-21-D-j23-1.76.H"]

def draw_stations(stations):
    pass

def draw_routes(route_segments):
    pass

# Streamlit app
#####
st.set_page_config(layout="wide")
st.header("Direct train connections")

feed = load_feed()
stations = parse_stations(feed)

## Filters
#####
filter_container = st.container()
filter_col1, filter_col2 = filter_container.columns(2)

# TODO: maybe have an arbitrary amount of selection? filter out selected from other select?
selected_city_a = filter_col1.selectbox("City A", stations["stop_name"], None)
selected_city_b = filter_col1.selectbox("City B", stations["stop_name"], None)
line_exclusion = filter_col2.multiselect("Exclude lines (optional)", [1,2])
weekdays_exclusion = filter_col2.multiselect("Weekday exclusion (optional)", [1,2])

if selected_city_a is not None and selected_city_a == selected_city_b:
    st.error("Same cities selected")


st.markdown("""---""")
## Content
#####
content_container = st.container()
map_col, other_col = content_container.columns([2,1])

map = folium.Map(tiles="cartodbpositron")

with map_col:
    # use pydeck?
    st_folium(map, use_container_width=True)

with other_col:
    # bar chart with time from destination to other stations, which filters on click?
    pass

"""
Please double check any connection with the real SBB timetable. This tool is only as accurate as the provided data.
Some stops in some routes are only served on special times (Weekend, Rush hour).
Others are faulty data (Train depot) they do not appear in the real timetable.
"""