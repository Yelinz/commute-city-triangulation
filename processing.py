import streamlit as st
import pandas as pd
import gtfs_kit


@st.cache_data
def load_feed():
    feed = gtfs_kit.read_feed("gtfs_fp2024_2023-10-18_04-15.zip", dist_units="km")
    # TODO maybe clean some stations
    return feed


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
