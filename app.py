import re
import streamlit as st
import pandas as pd
import gtfs_kit
import seaborn
from streamlit_folium import st_folium
import folium
import altair


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


@st.cache_data
def find_shared(_feed, a, b):
    all_a = _feed.stops.loc[_feed.stops["stop_id"].isin(a)]
    all_b = _feed.stops.loc[_feed.stops["stop_id"].isin(b)]

    both = pd.concat([all_a, all_b])
    duped = both.duplicated(["stop_id", "parent_station"])
    # zurich hb is missing rotkreuz aarau
    return both.loc[duped]


def draw_stations(stations, color, circle=True):
    marker_layer = folium.FeatureGroup(name="Stops")

    for row in stations.to_dict(orient="records"):
        location = [row["stop_lat"], row["stop_lon"]]
        tooltip = row["stop_name"]
        if circle:
            folium.CircleMarker(
                location=location,
                tooltip=tooltip,
                radius=3,
                fill=True,
                fillColor=color,
                color="#000000",
                weight=1,
                fillOpacity=1,
            ).add_to(marker_layer)
        else:
            icon_square = folium.plugins.BeautifyIcon(
                icon_shape="rectangle-dot",
                icon_size=[10, 10],
                background_color=color,
                border_width=2,
            )
            folium.Marker(
                location,
                tooltip=tooltip,
                icon=icon_square,
            ).add_to(marker_layer)

    return marker_layer


def draw_routes(stop_data, color_map_name):
    path_layer = folium.FeatureGroup(name="Paths")
    grouped = stop_data.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")
    colors = seaborn.color_palette(color_map_name, n_colors=grouped.ngroups).as_hex()
    idx = 0
    for name, group in grouped:
        stop_coords = []
        tooltip_content = f"<span style='display: none'>[{group.iloc[0]['route_id']}]</span>{group.iloc[0]['route_short_name']}"

        for row_index, row in group.iterrows():
            stop_coords.append(row[["stop_lat", "stop_lon"]].values)
            tooltip_content += f"<br/>{row['stop_name']}"

            folium.PolyLine(
                stop_coords, tooltip=tooltip_content, color=colors[idx]
            ).add_to(path_layer)
        idx += 1

    return path_layer


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
    "Station A",
    stations["stop_id"],
    None,
    format_func=lambda id: stations.loc[stations["stop_id"] == id]["stop_name"].iloc[0],
)
selected_city_b = filter_col1.selectbox(
    "Station B",
    stations["stop_id"],
    None,
    format_func=lambda id: stations.loc[stations["stop_id"] == id]["stop_name"].iloc[0],
)

routes_a = get_routes(feed, selected_city_a)
routes_b = get_routes(feed, selected_city_b)
all_routes = (
    pd.concat([routes_a, routes_b])
    .drop_duplicates(subset="route_id")
    .sort_values("route_short_name")
)

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

if selected_city_a is not None and selected_city_a == selected_city_b:
    st.error("Same cities selected")


stops_a = get_stops(
    feed,
    routes_a.loc[~routes_a["route_id"].isin(route_exclusion)]["route_id"],
    active_weekdays,
    relevant_hours,
)
stops_b = get_stops(
    feed,
    routes_b.loc[~routes_b["route_id"].isin(route_exclusion)]["route_id"],
    active_weekdays,
    relevant_hours,
)


shared_stops = find_shared(feed, stops_a["stop_id"], stops_b["stop_id"])

st.markdown("""---""")
## Content
#####
map_container = st.container()
map_col, map_legend_col = map_container.columns([2, 1])

# with does not create a scope
with map_col:
    map = folium.Map(tiles="cartodbpositron")

    routes_a_layer = draw_routes(stops_a, "viridis")
    stations_a_layer = draw_stations(stops_a, "#1b9e77")
    routes_b_layer = draw_routes(stops_b, "plasma")
    stations_b_layer = draw_stations(stops_b, "#d95f02")
    stations_shared_layer = draw_stations(shared_stops, "#7570b3", False)

    routes_a_layer.add_to(map)
    routes_b_layer.add_to(map)
    stations_a_layer.add_to(map)
    stations_b_layer.add_to(map)
    stations_shared_layer.add_to(map)

    selection = st_folium(
        map,
        height=800,
        returned_objects=["last_object_clicked_tooltip"],
        zoom=8,
        center=(46.848, 8.1336),
        use_container_width=True,
    )

with map_legend_col:
    # legend for route colors, city reachable colors
    # create a legend with branca?
    # https://nbviewer.org/gist/talbertc-usgs/18f8901fc98f109f2b71156cf3ac81cd
    pass


station_distance_container = st.container()
with station_distance_container:
    # after selected route
    # display every station and how long it takes to get from each one
    # some kind of graph
    if selection["last_object_clicked_tooltip"]:
        id_match = re.match(r"\[(.+)\]", selection["last_object_clicked_tooltip"])
        if id_match:
            selected_route = get_stops(
                feed,
                [id_match[1]],
                active_weekdays,
                relevant_hours,
            )
            edges = list(
                zip(
                    selected_route["stop_sequence"].index,
                    selected_route["stop_sequence"],
                )
            )
            edges.pop(0)

            chart = altair.Chart()

            # try https://altair-viz.github.io/user_guide/compound_charts.html#order-of-layers

            st.altair_chart(chart, True)
        else:
            st.markdown("Station selected")
    else:
        st.markdown("# Nothing selected")
