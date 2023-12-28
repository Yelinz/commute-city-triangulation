import streamlit as st
from st_pages import show_pages_from_config

show_pages_from_config()

st.markdown(
    """
# Documentation

This app is a tool to find locations wtih direct train connections to two different cities in Switzerland.

Disclaimer:
Please double check any connection with the real SBB timetable. This tool is only as accurate as the provided data.
Some stops in some routes are only served on special times (Weekend, Rush hour).
Others are faulty data (Train depot) they do not appear in the real timetable.

## Filters
The main filters are the choices for Destination A and B.
Those determine the lines and their stops which will be displayed.

- Destination A
- Destination B

The other filters are to refine the search, to be able to exclude which lines are considered to determine an overlap from the destinations.

If you do not want to take specific lines for example S Bahns, you can exclude them through this filter.

- Exclude lines

These are filters to restrict the time window in which the line has to have a running train.
For example some lines only exist on the weekend or late in the night. Which do not need to be shown if you only care about the usual work week and normal commute times.

- Active weekdays
- Relevant hours

## Charts
There are 4 charts in total.

One main map which shows the stops and if it can be reached from both destinations.

A line overview which appears after clicking on a line on the main map. It shows the stops and the time it takes to get in between them. 

Two smaller maps which show the lines which stop at either destination A or B. One small map for each destination and their lines.


## Glossary

- Line, Route
A train line such as S1 or IC1. 
- Station, Destination, Stop
A train station or stop such as Zürich HB or Bern.

# Links
Source code: https://github.com/Yelinz/commute-city-triangulation
Rendered: https://commute-triangulation.streamlit.app/
"""
)
