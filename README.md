# Commute city triangulation

This project is intended to find a city in the swiss train network from where you can reach your chosen destinations.
It is not intended to show last kilometer (last mile) solutions, but rather overarching city to city train route options.

The displayed routes are only as accurate as the SBB provides. Which means it is fairly accurate but some ghost routes might exist. That means the GTFS data includes a stop in some location, while in reality and on sbb.ch it is not listed.
There are a lot of ghost stops in the GTFS data. Stops where the train parks or so I assume but no passengers board.

This works on the GTFS data provided by https://opentransportdata.swiss.

All operations are currently done in memory with pandas. That means the whole GTFS feed is loaded into memory.
Might need migration to a Database, if the memory requirements are too high.

## Usage
- poetry
- jupyter

Select the destination city in the notebook and run the rest.

Be sure to have the latest GTFS zip from which ever preferred source.