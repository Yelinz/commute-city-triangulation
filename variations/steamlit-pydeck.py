import streamlit as st
import pandas as pd
import gtfs_kit
import seaborn
import pydeck


#
# FIXME: Steamlit version has to be abandoned as there is no good interactivity.
# https://discuss.streamlit.io/t/is-pydeck-chart-click-interaction-possible/49965/2
# version 1.28
#


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
def get_stops(_feed, route_ids, active_days, relevant_hours):
    # filter by weekdays
    query_string = ""
    for i, weekday in enumerate(active_days):
        query_string += f"{weekday.lower()} == 1"
        if i < len(active_days) - 1:
            query_string += " and "
    active_services = _feed.calendar.query(query_string)["service_id"]

    route_trips = _feed.trips.loc[
        _feed.trips["route_id"].isin(route_ids)
        & _feed.trips["service_id"].isin(active_services)
    ]

    relevant_stops = _feed.stop_times.loc[
        _feed.stop_times["trip_id"].isin(route_trips["trip_id"])
    ]

    # parse arrival and departure to timedeltas
    relevant_stops.loc[:, "arrival_time_parsed"] = pd.to_timedelta(
        relevant_stops["arrival_time"]
    )
    relevant_stops.loc[:, "departure_time_parsed"] = pd.to_timedelta(
        relevant_stops["departure_time"]
    )

    # pickup, dropoff type not 0 means no normal passenger transfer
    # filter by arrival and departure time
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

    stops_trips = pd.merge(
        filtered_stops, _feed.trips[["trip_id", "route_id"]], on="trip_id", how="left"
    )
    # map the stops to the route
    stops_route = pd.merge(
        stops_trips,
        _feed.routes[["route_id", "route_short_name"]],
        on="route_id",
        how="left",
    )

    # only use longest trips
    longest_trips = stops_route.loc[
        stops_route.groupby(["route_id"])["stop_sequence"].idxmax()
    ]
    # stops_to_display = stops_route.loc[stops_route["trip_id"].isin(longest_trips["trip_id"])]

    longest_trips_stop_times = _feed.stop_times.loc[
        _feed.stop_times["trip_id"].isin(longest_trips["trip_id"])
    ]
    longest_trips_stations = _feed.stops.loc[
        _feed.stops["stop_id"].isin(longest_trips_stop_times["stop_id"])
    ]
    # TODO: consider all trip options, as some might have divergent routes
    # dedupe stops per route
    # deduped_stops = stops.sort_values(["stop_sequence"]).groupby("route_id").apply(lambda x: x.loc[x["stop_sequence"].idxmax()])
    # print(deduped_stops)

    # add all additional data which is needed
    stop_data = pd.merge(longest_trips_stop_times, _feed.trips, on="trip_id")
    stop_data = pd.merge(stop_data, _feed.routes, on="route_id")
    stop_data = pd.merge(stop_data, _feed.stops, on="stop_id")
    return stop_data


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
    # shown_stops = stations.drop_duplicates(subset=["parent_station"], keep='first')

    scatter = []
    for stop_index, stop in stations.iterrows():
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
    grouped = trip_data.sort_values(["route_id", "stop_sequence"]).groupby("route_id")
    # TODO: different palette for each route
    colors = seaborn.color_palette("viridis", n_colors=grouped.ngroups)
    idx = 0
    route_segments = []
    for name, group in grouped:
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
active_weekdays = filter_col2.multiselect(
    "Active weekdays",
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
)
relevant_hours = filter_col2.slider("Relevant hours", 0, 23, (6, 22), 1)

# if selected_city_a is not None and selected_city_a == selected_city_b:
#    st.error("Same cities selected")


filtered_routes = all_routes.loc[~all_routes["route_id"].isin(route_exclusion)]
stops_a = get_stops(feed, filtered_routes["route_id"], active_weekdays, relevant_hours)

st.markdown("""---""")
## Content
#####
map_container = st.container()
map_col, map_legend_col = map_container.columns([2, 1])

with map_col:
    view_state = pydeck.ViewState(
        latitude=46.848, longitude=8.1336, zoom=7  # Geographical center of switzerland
    )
    route_layer = draw_routes(stops_a)
    station_layer = draw_stations(stops_a)

    deck = pydeck.Deck(
        layers=[route_layer, station_layer],
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
    )
    print(deck)
    deck.on_click(lambda x: print(x))
    re = st.pydeck_chart(
        deck,
        True,
    )
    print(re)

with map_legend_col:
    # legend for route colors, city reachable colors
    pass


station_distance_container = st.container()
with station_distance_container:
    # after selected route
    # display every station and how long it takes to get from each one
    pass
