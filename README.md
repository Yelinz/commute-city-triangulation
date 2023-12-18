[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://commute-triangulation.streamlit.app/)

# Commute city triangulation

This project is intended to find a city in the swiss train network from where you can reach your chosen destinations.
It is not intended to show last kilometer (last mile) solutions, but rather overarching city to city train route options.

The displayed routes are only as accurate as the SBB provides. Which means it is fairly accurate but some ghost routes might exist. That means the GTFS data includes a stop in some location, while in reality and on sbb.ch it is not listed.
There are a lot of ghost stops in the GTFS data. Stops where the train parks or so I assume but no passengers board.

Rendered version: https://commute-triangulation.streamlit.app/

This works on the GTFS data provided by https://opentransportdata.swiss.

All operations are currently done in memory with pandas. That means the whole GTFS feed is loaded into memory.
Might need migration to a database, if the memory requirements are too high.

## Usage
Requirements:
- poetry

Install the dependencies
```sh
poetry install --no-root
```

Be sure to have the latest GTFS zip from which ever preferred source.

The name should be `gtfs.zip` and located in the root of the project.

There is a example gtfs file provided but it will not be up to date.

To start the dashboard run:
```sh
poetry run streamlit run main.py
```

Refer to the documentation page on how to use the dashboard and what it conatins.
