import re
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
import altair
from st_pages import show_pages_from_config, add_page_title
from processing import (
    load_feed,
    parse_stations,
    get_routes,
    get_stops,
    find_shared,
    route_details,
)
from rendering import generate_legend, draw_routes, draw_stations

MAP_CENTER = (46.848, 8.1336)

# Streamlit app
#####
add_page_title(page_title="Home", layout="wide")
show_pages_from_config()

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

# with does not create a scope
with map_container:
    map = folium.Map(tiles="cartodbpositron")

    # TODO if two are selected only color in the shared routes, other will be gray
    routes_a_layer = draw_routes(stops_a, "BuGn")
    routes_b_layer = draw_routes(stops_b, "OrRd")
    stations_a_layer = draw_stations(stops_a, "#1b9e77")
    stations_b_layer = draw_stations(stops_b, "#d95f02")
    stations_shared_layer = draw_stations(shared_stops, "#7570b3", False)

    routes_a_layer.add_to(map)
    routes_b_layer.add_to(map)
    stations_a_layer.add_to(map)
    stations_b_layer.add_to(map)
    stations_shared_layer.add_to(map)

    map.get_root().add_child(generate_legend())

    selection = st_folium(
        map,
        height=800,
        returned_objects=["last_object_clicked_tooltip"],
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="main_map",
    )

# TODO add text how many shared stations there are

station_distance_container = st.container()
with station_distance_container:
    st.markdown("## Station overview of selected route")
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

            chart_data, time_data = route_details(selected_route, shared_stops)

            scale = altair.Scale(domain=[0.8, chart_data["stop_sequence"].max() + 0.2])
            time_annotations = (
                altair.Chart(time_data)
                .mark_text(dy=15)
                .encode(
                    altair.X(
                        "stop_sequence",
                        scale=scale,
                    ),
                    altair.Y("route_short_name"),
                    altair.Text("next_stop"),
                )
            )

            chart = altair.Chart(
                chart_data, title="Reachable stations from selected route"
            ).encode(
                altair.X(
                    "stop_sequence",
                    scale=scale,
                    axis=altair.Axis(grid=False, labels=False),
                ).title("Stops"),
                altair.Y("route_short_name").title(""),
            )

            layered = altair.layer(
                chart.mark_line(),
                chart.mark_point(filled=True, opacity=1).encode(
                    shape=altair.Shape(
                        "shared", scale=altair.Scale(range=["circle", "square"])
                    ).title("Station reachable by both"),
                    color="shared",
                ),
                chart.mark_text(dy=-20).encode(altair.Text("stop_name")),
                time_annotations,
            ).configure_point(size=200)

            st.altair_chart(layered, True)
        else:
            st.markdown("Select a route to display its stations")
    else:
        st.markdown("Select a route to display its stations")

# TODO display routes of a and b seperatly

mini_map_container = st.container()
mini_a, mini_b = mini_map_container.columns(2)

with mini_a:
    st.markdown("## Routes and stations of destination A")
    map_a = folium.Map(tiles="cartodbpositron")
    routes_a_layer.add_to(map_a)
    stations_a_layer.add_to(map_a)
    st_folium(
        map_a,
        height=400,
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="mini_map_a",
    )

with mini_b:
    st.markdown("## Routes and stations of destination B")
    map_b = folium.Map(tiles="cartodbpositron")
    routes_b_layer.add_to(map_b)
    stations_b_layer.add_to(map_b)
    st_folium(
        map_b,
        height=400,
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="mini_map_b",
    )
