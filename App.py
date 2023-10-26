import streamlit as st
import pandas as pd
import gtfs_kit
import folium
import seaborn
import pydeck


# maybe it would be more effective to have the feed as a global variable, instead of passing it in
@st.cache_data
def load_feed():
    return gtfs_kit.read_feed("gtfs_fp2024_2023-10-18_04-15.zip", dist_units="km")


@st.cache_data
def parse_stations(_feed):
    return _feed.stops.loc[_feed.stops.stop_id.str.contains("Parent")].sort_values(
        "stop_name"
    )


@st.cache_data
def get_routes(_feed, station_id):
    platforms = _feed.stops.loc[_feed.stops["parent_station"] == station_id]
    all_stop_times = _feed.stop_times.loc[
        _feed.stop_times["stop_id"].isin(platforms["stop_id"].values)
    ]
    route_ids = _feed.trips.loc[
        _feed.trips["trip_id"].isin(all_stop_times["trip_id"].unique())
    ]["route_id"].unique()
    all_routes = _feed.routes.loc[_feed.routes["route_id"].isin(route_ids)]
    # EXT are special trains, not usually accessible
    routes = all_routes.loc[all_routes["route_short_name"] != "EXT"]
    return routes


@st.cache_data
def get_stops(_feed, route_ids, weekdays_exclusion, relevant_hours):
    route_trips = _feed.trips.loc[_feed.trips["route_id"].isin(route_ids)]

    # filter by weekdays

    relevant_stops = _feed.stop_times.loc[_feed.stop_times["trip_id"].isin(route_trips["trip_id"])]

    # parse arrival and departure to timedeltas
    relevant_stops.loc[:, "arrival_time_parsed"] = pd.to_timedelta(
        relevant_stops["arrival_time"]
    )
    relevant_stops.loc[:, "departure_time_parsed"] = pd.to_timedelta(
        relevant_stops["departure_time"]
    )

    # pickup, dropoff type not 0 means no normal passenger transfer
    lower_bound, upper_bound = [pd.Timedelta(x, unit="h") for x in relevant_hours]
    filtered_stops = relevant_stops.loc[
        ((relevant_stops["pickup_type"] == 0) & (relevant_stops["drop_off_type"] == 0))
        & (
            (
                (relevant_stops["arrival_time_parsed"] > lower_bound)
                & (relevant_stops["arrival_time_parsed"] < upper_bound)
            )
            | (
                (relevant_stops["departure_time_parsed"] > lower_bound)
                & (relevant_stops["departure_time_parsed"] < upper_bound)
            )
        )
    ]

    return filtered_stops




def get_trips(_feed, _routes, _excluded_routes, _weekdays_exclusion, _relevant_hours):
    # TODO modularize this mess
    # filter out excluded routes
    if _excluded_routes is not None:
        _routes = _routes.loc[~_routes["route_id"].isin(_excluded_routes)]

    route_trips = _feed.trips.loc[_feed.trips["route_id"].isin(_routes["route_id"])]

    # all stops of the trips
    relevant_stops = _feed.stop_times.loc[
        _feed.stop_times["trip_id"].isin(route_trips["trip_id"].values)
    ]

    # parse arrival and departure to timedeltas
    # TODO sets on a copy?
    relevant_stops.loc[:, "arrival_time_parsed"] = pd.to_timedelta(
        relevant_stops["arrival_time"]
    )
    relevant_stops.loc[:, "departure_time_parsed"] = pd.to_timedelta(
        relevant_stops["departure_time"]
    )

    # pickup, dropoff type not 0 means no normal passenger transfer
    lower_bound, upper_bound = [pd.Timedelta(x, unit="h") for x in _relevant_hours]
    filtered_stops = relevant_stops.loc[
        ((relevant_stops["pickup_type"] == 0) & (relevant_stops["drop_off_type"] == 0))
        & (
            (
                (relevant_stops["arrival_time_parsed"] > lower_bound)
                & (relevant_stops["arrival_time_parsed"] < upper_bound)
            )
            | (
                (relevant_stops["departure_time_parsed"] > lower_bound)
                & (relevant_stops["departure_time_parsed"] < upper_bound)
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

    # join all the data into one dataframe
    stop_data = pd.merge(longest_trips_stop_times, route_trips, on="trip_id")
    stop_data = pd.merge(stop_data, _routes, on="route_id")
    stop_data = pd.merge(stop_data, longest_trips_parent_stops, on="stop_id")
    return stop_data


# def draw_stations(input_stations, *station_dfs):
def draw_stations(stations):
    shown_stops = stations.drop_duplicates(subset=["parent_station"], keep='first')

    scatter = []
    for stop_index, stop in shown_stops.iterrows():
        scatter.append(
            {
                "name": stop["stop_name"],
                "position": stop[["stop_lon", "stop_lat"]].to_list(),
            }
        )
    
    return pydeck.Layer(
        type="ScatterplotLayer",
        data=scatter,
        pickable=True,
        stroked=True,
        filled=True,
        radius_scale=6,
        radius_min_pixels=1,
        radius_max_pixels=100,
        line_width_min_pixels=1,
        line_width_max_pixels=1,
        get_radius=15,
        # TODO: different color for each route
        get_color=[255, 140, 0],
    )


def draw_routes(trip_data):
    grouped = trip_data.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")
    # TODO: different palette for each route
    colors = seaborn.color_palette("viridis", n_colors=grouped.ngroups)
    idx = 0
    route_segments = []
    for name, group in grouped:
        destination_stop_in_route = False
        stop_coords = []
        tooltip_content = f"{group.iloc[0]['route_short_name']}"

        for row_index, row in group.iterrows():
            stop_coords.append(row[["stop_lon", "stop_lat"]].to_list())
            # tooltip_content += f"<br/>{row['stop_name']}"

        route_segments.append(
            {
                "name": tooltip_content,
                "color": [round(n * 255) for n in colors[idx]],
                "path": stop_coords,
            }
        )
        idx += 1

    return pydeck.Layer(
        type="PathLayer",
        data=route_segments,
        pickable=True,
        width_scale=20,
        width_min_pixels=2,
        get_color="color",
        get_width=5,
    )


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

# restricted to two for now
selected_city_a = filter_col1.selectbox(
    "City A",
    stations["stop_id"],
    None,
    format_func=lambda id: stations.loc[stations["stop_id"] == id]["stop_name"].iloc[0],
)
# selected_city_b = filter_col1.selectbox("City B", stations["stop_name"], None)

routes_a = get_routes(feed, selected_city_a)
all_routes = routes_a
route_exclusion = filter_col2.multiselect(
    "Exclude lines (optional)",
    all_routes["route_id"],
    format_func=lambda id: all_routes.loc[all_routes["route_id"] == id][
        "route_short_name"
    ].iloc[0],
)
weekdays_exclusion = filter_col2.multiselect(
    "Weekday exclusion (optional)",
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    ["Saturday", "Sunday"],
)
relevant_hours = filter_col2.slider(
    "Relevant hours",
    0, 23, (6, 22), 1
)

# if selected_city_a is not None and selected_city_a == selected_city_b:
#    st.error("Same cities selected")


filtered_routes = all_routes.loc[~all_routes["route_id"].isin(route_exclusion)]
stops = get_stops(feed, filtered_routes["route_id"], weekdays_exclusion, relevant_hours)
print(stops)
trips_a = get_trips(feed, routes_a, route_exclusion, weekdays_exclusion, relevant_hours)

st.markdown("""---""")
## Content
#####
content_container = st.container()
map_col, other_col = content_container.columns([2, 1])

with map_col:
    view_state = pydeck.ViewState(
        latitude=46.848, longitude=8.1336, zoom=7  # Geographical center of switzerland
    )
    route_layer = draw_routes(trips_a)
    station_layer = draw_stations(trips_a)

    deck = pydeck.Deck(
        layers=[route_layer, station_layer],
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
    )
    st.pydeck_chart(
        deck,
        True,
    )

with other_col:
    # bar chart with time from destination to other stations, which filters on click?
    pass
