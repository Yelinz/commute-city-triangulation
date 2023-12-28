import re

import folium
import pandas as pd
import streamlit as st
from st_pages import add_page_title, show_pages_from_config
from streamlit_folium import st_folium

from processing import (
    find_shared,
    get_routes,
    get_stops,
    load_feed,
    parse_stations,
    route_details,
)
from rendering import (
    draw_route_detail,
    draw_routes,
    draw_stations,
    generate_main_legend,
    generate_sub_a_legend,
    generate_sub_b_legend,
)

MAP_CENTER = (46.848, 8.1336)
COLORS = ["#ffffbf", "#91bfdb"]
COLOR_SHARED = "#fc8d59"

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

# TODO restricted to two for now, have it variable to min two and higher max
selected_city_a = filter_col1.selectbox(
    "Destination A",
    stations["stop_id"],
    None,
    format_func=lambda id: stations.loc[stations["stop_id"] == id]["stop_name"].iloc[0],
)
selected_city_b = filter_col1.selectbox(
    "Destination B",
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

shared_stops = find_shared(stops_a, stops_b)

st.markdown("""---""")
## Content
#####
map_container = st.container()

# with does not create a scope
with map_container:
    map_main = folium.Map(tiles="cartodbpositron")

    # TODO if there are 100% shared routes, highlight
    COLOR_A = COLORS[0]
    COLOR_B = COLORS[1]

    routes_a_layer = draw_routes(stops_a, "#808080", "single")
    routes_b_layer = draw_routes(stops_b, "#808080", "single")
    stations_a_layer = draw_stations(stops_a, COLOR_A)
    stations_b_layer = draw_stations(stops_b, COLOR_B)
    stations_shared_layer = draw_stations(shared_stops, COLOR_SHARED, "square")

    # if start is in shared use shared color
    marker_a_color, marker_b_color = COLORS
    if selected_city_a in shared_stops["parent_station"].values:
        marker_a_color = COLOR_SHARED
    if selected_city_b in shared_stops["parent_station"].values:
        marker_b_color = COLOR_SHARED
    start_a = draw_stations(
        stops_a.loc[stops_a["parent_station"] == selected_city_a].drop_duplicates(
            "parent_station"
        ),
        marker_a_color,
        "star",
    )
    start_b = draw_stations(
        stops_b.loc[stops_b["parent_station"] == selected_city_b].drop_duplicates(
            "parent_station"
        ),
        marker_b_color,
        "star",
    )

    routes_a_layer.add_to(map_main)
    routes_b_layer.add_to(map_main)
    stations_a_layer.add_to(map_main)
    stations_b_layer.add_to(map_main)
    stations_shared_layer.add_to(map_main)
    start_a.add_to(map_main)
    start_b.add_to(map_main)

    map_main.get_root().add_child(generate_main_legend())

    selection = st_folium(
        map_main,
        height=800,
        returned_objects=["last_object_clicked_tooltip"],
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="main_map",
    )

    st.markdown(f"Destination A and B have {len(shared_stops)} shared stations.")


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

            chart_data, time_data = route_details(
                selected_route, shared_stops["parent_station"]
            )

            detail_chart = draw_route_detail(chart_data, time_data)

            st.altair_chart(detail_chart, True)
        else:
            st.markdown("Select a route from above to display its stations")
            # TODO hover/ click on station highlights the station in other charts
    else:
        st.markdown("Select a route from above to display its stations")

mini_map_container = st.container()
mini_a, mini_b = mini_map_container.columns(2)

with mini_a:
    st.markdown("## Routes and stations of destination A")
    map_a = folium.Map(tiles="cartodbpositron")
    routes_a_layer = draw_routes(stops_a, "plasma")
    stations_a_layer = draw_stations(stops_a, "#ffffbf")
    start_a = draw_stations(
        stops_a.loc[stops_a["parent_station"] == selected_city_a].drop_duplicates(
            "parent_station"
        ),
        COLOR_A,
        "star",
    )

    routes_a_layer.add_to(map_a)
    stations_a_layer.add_to(map_a)
    start_a.add_to(map_a)

    map_a.get_root().add_child(generate_sub_a_legend())
    st_folium(
        map_a,
        height=400,
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="mini_map_a",
        returned_objects=[],
    )

with mini_b:
    st.markdown("## Routes and stations of destination B")
    map_b = folium.Map(tiles="cartodbpositron")
    routes_b_layer = draw_routes(stops_b, "viridis")
    stations_b_layer = draw_stations(stops_b, "#91bfdb")
    start_b = draw_stations(
        stops_b.loc[stops_b["parent_station"] == selected_city_b].drop_duplicates(
            "parent_station"
        ),
        COLOR_B,
        "star",
    )

    routes_b_layer.add_to(map_b)
    stations_b_layer.add_to(map_b)
    start_b.add_to(map_b)

    map_b.get_root().add_child(generate_sub_b_legend())
    st_folium(
        map_b,
        height=400,
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="mini_map_b",
        returned_objects=[],
    )
