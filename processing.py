import gtfs_kit
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner="Loading initial data...")
def load_feed():
    feed = gtfs_kit.read_feed("gtfs.zip", dist_units="km")
    # TODO maybe clean some stations
    return feed


@st.cache_data(show_spinner="Loading initial data...")
def parse_stations(_feed):
    return _feed.stops.loc[_feed.stops.stop_id.str.contains("Parent")].sort_values(
        "stop_name"
    )


@st.cache_data(show_spinner="Finding routes...")
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


@st.cache_data(show_spinner="Finding stops...")
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
    relevant_stops = relevant_stops.assign(
        arrival_time_parsed=pd.to_timedelta(relevant_stops["arrival_time"]),
        departure_time_parsed=pd.to_timedelta(relevant_stops["departure_time"]),
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
    # longest_trips_stations = _feed.stops.loc[
    #    _feed.stops["stop_id"].isin(longest_trips_stop_times["stop_id"])
    # ]

    # TODO: consider all trip options, as some might have divergent routes
    # dedupe stops per route
    # deduped_stops = stops.sort_values(["stop_sequence"]).groupby("route_id").apply(lambda x: x.loc[x["stop_sequence"].idxmax()])
    # print(deduped_stops)

    # add all additional data which is needed
    stop_data = pd.merge(longest_trips_stop_times, _feed.trips, on="trip_id")
    stop_data = pd.merge(stop_data, _feed.routes, on="route_id")
    stop_data = pd.merge(stop_data, _feed.stops, on="stop_id")
    return stop_data


def find_shared(_stops_a, _stops_b):
    return (
        pd.merge(_stops_a, _stops_b, how="inner", on=["parent_station"])
        .drop_duplicates("parent_station")
        .rename(
            columns={
                "stop_id_x": "stop_id",
                "stop_name_x": "stop_name",
                "stop_lat_x": "stop_lat",
                "stop_lon_x": "stop_lon",
                "parent_station_x": "parent_station",
            }
        )
    )


def route_details(_selected_route, shared_stops):
    selected_route = _selected_route.sort_values(["stop_sequence", "route_id"])
    chart_data = selected_route[["stop_sequence", "route_short_name", "stop_name"]]
    chart_data = chart_data.assign(
        shared=selected_route["parent_station"].isin(shared_stops)
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

    time_data = time_data.drop(["arrival_time_parsed", "departure_time_parsed"], axis=1)

    return chart_data, time_data
