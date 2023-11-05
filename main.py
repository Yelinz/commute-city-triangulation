import re
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
import altair
from st_pages import show_pages_from_config
from processing import (
    load_feed,
    parse_stations,
    get_routes,
    get_stops,
    find_shared,
    draw_routes,
    draw_stations,
)

# Streamlit app
#####
show_pages_from_config()
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
            selected_route = selected_route.sort_values(["stop_sequence", "route_id"])
            chart_data = selected_route[
                ["stop_sequence", "route_short_name", "stop_name"]
            ]
            chart_data = chart_data.assign(
                shared=selected_route["stop_id"].isin(shared_stops["stop_id"])
            )

            time_data = selected_route[["stop_sequence", "route_short_name"]]
            time_data = time_data.assign(
                stop_sequence=time_data["stop_sequence"] + 0.5,
                arrival_time_parsed=pd.to_timedelta(selected_route["arrival_time"]),
                departure_time_parsed=pd.to_timedelta(selected_route["departure_time"]),
            )

            time_data["next_stop"] = ""
            for idx in time_data.index:
                if idx == time_data.idxmax().iloc[0]:
                    break
                travel_time = (
                    time_data.iloc[idx + 1]["arrival_time_parsed"]
                    - time_data.iloc[idx]["departure_time_parsed"]
                )
                time_data.loc[idx, "next_stop"] = f"{travel_time.seconds // 60} min"

            time_data = time_data.drop(
                ["arrival_time_parsed", "departure_time_parsed"], axis=1
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
