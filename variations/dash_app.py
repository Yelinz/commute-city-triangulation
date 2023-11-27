from dash import Dash, html, dcc, callback, Output, Input
import gtfs_kit
import plotly.graph_objects as go
import dash_cytoscape as cyto
import pandas as pd
from collections import defaultdict

# maybe dash bootstrap

feed = gtfs_kit.read_feed("gtfs_fp2024_2023-10-18_04-15.zip", dist_units="km")

app = Dash(__name__)


def generate_labelled_input(label, input):
    return html.Label([label, input])


def parse_stations(feed):
    return (
        feed.stops.loc[feed.stops.stop_id.str.contains("Parent")]
        .filter(["stop_id", "stop_name"])
        .sort_values("stop_name")
        .rename(columns={"stop_id": "value", "stop_name": "label"})
        .to_dict("records")
    )


stations = parse_stations(feed)

app.layout = html.Div(
    [
        html.H1(children="Direct train connections"),
        html.Div(
            [
                generate_labelled_input("City A", dcc.Dropdown(stations, id="city-a")),
                generate_labelled_input("City B", dcc.Dropdown(stations, id="city-b")),
            ]
        ),
        html.Div(
            [
                generate_labelled_input(
                    "Route exclusions", dcc.Dropdown(multi=True, id="route-exclusions")
                ),
                generate_labelled_input(
                    "Active weekdays",
                    dcc.Dropdown(
                        [
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        ],
                        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                        multi=True,
                        id="active-weekdays",
                    ),
                ),
                generate_labelled_input(
                    "Relevant hours",
                    dcc.RangeSlider(0, 23, 1, value=[6, 22], id="relevant-hours"),
                ),
            ]
        ),
        # TODO: customize modebar
        dcc.Graph(id="map", config={"displayModeBar": False}),
        cyto.Cytoscape(id="route-detail"),
    ]
)


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


@callback(
    Output("route-exclusions", "options"),
    Input("city-a", "value"),
    Input("city-b", "value"),
)
def set_route_exclusion_options(city_a, city_b):
    routes_a = get_routes(feed, city_a)
    routes_b = get_routes(feed, city_b)

    # TODO add different color for a and b "label": html.Span(['Montreal'], style={'color': 'Gold'}),
    return (
        pd.concat([routes_a, routes_b])
        .drop_duplicates(subset="route_id")
        .filter(["route_id", "route_short_name"])
        .sort_values("route_short_name")
        .rename(columns={"route_id": "value", "route_short_name": "label"})
        .to_dict("records")
    )


def get_stops(_feed, _routes, excluded_routes, active_days, relevant_hours):
    # filter out excluded routes
    if excluded_routes is not None:
        _routes = _routes.loc[~_routes["route_id"].isin(excluded_routes)]

    # filter by weekdays
    query_string = ""
    for i, weekday in enumerate(active_days):
        query_string += f"{weekday.lower()} == 1"
        if i < len(active_days) - 1:
            query_string += " and "
    active_services = _feed.calendar.query(query_string)["service_id"]

    route_trips = _feed.trips.loc[
        _feed.trips["route_id"].isin(_routes["route_id"])
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


@callback(
    Output("map", "figure"),
    Input("city-a", "value"),
    Input("city-b", "value"),
    Input("route-exclusions", "value"),
    Input("active-weekdays", "value"),
    Input("relevant-hours", "value"),
)
def generate_map(city_a, city_b, route_exclusion, active_weekdays, relevant_hours):
    map_figure = go.Figure()
    map_figure.update_layout(
        margin={"l": 0, "t": 0, "b": 0, "r": 0},
        mapbox={
            "style": "carto-positron",
            "center": {"lon": 8.1336, "lat": 46.848},
            "zoom": 7,
        },
        hovermode="x",
        # legend_traceorder="reversed"
    )

    stops_a = defaultdict(list)
    if city_a:
        stops_a = get_stops(
            feed,
            get_routes(feed, city_a),
            route_exclusion,
            active_weekdays,
            relevant_hours,
        )
        grouped = stops_a.sort_values(["route_short_name", "stop_sequence"]).groupby(
            "route_id"
        )
        for name, group in grouped:
            map_figure.add_trace(
                go.Scattermapbox(
                    mode="lines",
                    lon=group["stop_lon"],
                    lat=group["stop_lat"],
                    legendgroup="routes-a",
                    hoverinfo="text",
                    hovertext=group.iloc[0]["route_short_name"],
                    name=group.iloc[0]["route_short_name"],
                    # legendgrouptitle={"text": "Routes from A"},
                ),
            )
    stops_b = defaultdict(list)
    if city_b:
        stops_b = get_stops(
            feed,
            get_routes(feed, city_b),
            route_exclusion,
            active_weekdays,
            relevant_hours,
        )

    map_figure.add_trace(
        go.Scattermapbox(
            mode="lines",
            lon=[-50, -60, 40],
            lat=[30, 10, -20],
            legendgroup="routes-b",
            # legendgrouptitle={"text": "Routes from B"},
        ),
    )
    # Stations
    map_figure.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=stops_a["stop_lon"],
            lat=stops_a["stop_lat"],
            marker={"size": 10},
            legendgroup="stations-a",
            legendgrouptitle={"text": "Stations from A"},
            name="Stations",
            hoverinfo="text",
            hovertext=stops_a["stop_name"],
        ),
    )
    map_figure.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=stops_b["stop_lon"],
            lat=stops_b["stop_lat"],
            marker={"size": 10},
            legendgroup="stations-b",
            legendgrouptitle={"text": "Stations from B"},
        ),
    )
    map_figure.add_trace(
        go.Scattermapbox(
            mode="markers",
            lon=[],
            lat=[],
            marker={"size": 10},
            legendgroup="stations-shared",
            legendgrouptitle={"text": "Stations shared"},
        ),
    )

    return map_figure


@callback(
    Output("route-detail", "elements"),
    Input("map", "hoverData"),
    Input("map", "clickData"),
)
def generate_map(hover, click):
    # FIXME: No real interactivity on lines on map https://github.com/plotly/plotly.js/issues/1960
    print(click)
    return []


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
