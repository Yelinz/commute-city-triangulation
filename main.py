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
from rendering import (
    generate_main_legend,
    generate_sub_a_legend,
    generate_sub_b_legend,
    draw_routes,
    draw_stations,
)

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

    # TODO if two are selected only color in the shared routes, other will be gray
    routes_a_layer = draw_routes(stops_a, "#808080", "single")
    routes_b_layer = draw_routes(stops_b, "#808080", "single")
    stations_a_layer = draw_stations(stops_a, "#ffffbf")
    stations_b_layer = draw_stations(stops_b, "#91bfdb")
    stations_shared_layer = draw_stations(shared_stops, "#fc8d59", False)

    routes_a_layer.add_to(map_main)
    routes_b_layer.add_to(map_main)
    # determining shared routes is not the same as shared stops
    # if len(shared_stops):
    #    routes_shared_layer = draw_routes(shared_stops, "inferno")
    #   routes_shared_layer.add_to(map_main)
    stations_a_layer.add_to(map_main)
    stations_b_layer.add_to(map_main)
    stations_shared_layer.add_to(map_main)

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

    # TODO add text how many shared stations there are
    st.markdown(f"Destination A and B have {len(shared_stops)} shared stops.")


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

            print(selected_route, shared_stops)
            chart_data, time_data = route_details(
                selected_route, shared_stops["parent_station"]
            )

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

            # TODO selecting different route does not update
            # improve colors of text, shared
            # move legend up?
            chart = altair.Chart(
                chart_data, title="Reachable stations from selected route"
            ).encode(
                altair.X(
                    "stop_sequence",
                    scale=scale,
                    axis=altair.Axis(grid=False, labels=False),
                ).title("Stops", color="black"),
                altair.Y("route_short_name").title(""),
            )

            layered = (
                altair.layer(
                    chart.mark_line(),
                    chart.mark_point(filled=True, opacity=1).encode(
                        shape=altair.Shape(
                            "shared",
                            scale=altair.Scale(range=["circle", "square"]),
                            legend=altair.Legend(
                                orient="right",
                                legendX=-50,
                                legendY=-500,
                                direction="vertical",
                                # titleAnchor="middle",
                            ),
                        ).title("Station reachable by both"),
                        color=altair.Color("shared", scale=altair.Scale(domain=[True, False], range=["red", "blue"]))
                    ),
                    chart.mark_text(dy=-20).encode(altair.Text("stop_name")),
                    time_annotations,
                )
                .configure_point(size=200)
                .configure_axisLeft(labelColor="black")
                .configure_axisBottom(titleColor="black")
            )

            st.altair_chart(layered, True)
        else:
            st.markdown("Select a route from above to display its stations")
            # TODO hover/ click on station highlights the station in other charts
    else:
        st.markdown("Select a route from above to display its stations")

# TODO display routes of a and b seperatly
mini_map_container = st.container()
mini_a, mini_b = mini_map_container.columns(2)

with mini_a:
    st.markdown("## Routes and stations of destination A")
    map_a = folium.Map(tiles="cartodbpositron")
    routes_a_layer = draw_routes(stops_a, "plasma")
    stations_a_layer = draw_stations(stops_a, "#ffffbf")
    routes_a_layer.add_to(map_a)
    stations_a_layer.add_to(map_a)
    map_a.get_root().add_child(generate_sub_a_legend())
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
    routes_b_layer = draw_routes(stops_b, "viridis")
    stations_b_layer = draw_stations(stops_b, "#91bfdb")
    routes_b_layer.add_to(map_b)
    stations_b_layer.add_to(map_b)
    map_b.get_root().add_child(generate_sub_b_legend())
    st_folium(
        map_b,
        height=400,
        zoom=8,
        center=MAP_CENTER,
        use_container_width=True,
        key="mini_map_b",
    )
