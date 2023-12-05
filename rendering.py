from branca.element import Template, MacroElement
import seaborn
import folium


def draw_stations(stations, color, circle=True):
    marker_layer = folium.FeatureGroup(name="Stops")

    for row in stations.to_dict(orient="records"):
        location = [row["stop_lat"], row["stop_lon"]]
        tooltip = row["stop_name"]
        if circle:
            folium.CircleMarker(
                location=location,
                tooltip=tooltip,
                radius=3,
                fill=True,
                fillColor=color,
                color="#000000",
                weight=1,
                fillOpacity=1,
            ).add_to(marker_layer)
        else:
            icon_square = folium.plugins.BeautifyIcon(
                icon_shape="rectangle-dot",
                icon_size=[10, 10],
                background_color=color,
                border_width=2,
            )
            folium.Marker(
                location,
                tooltip=tooltip,
                icon=icon_square,
            ).add_to(marker_layer)

    return marker_layer


def draw_routes(stop_data, color_name, COLOR_TYPE="colormap"):
    path_layer = folium.FeatureGroup(name="Paths")
    grouped = stop_data.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")
    if COLOR_TYPE == "colormap":
        colors = seaborn.color_palette(color_name, n_colors=grouped.ngroups).as_hex()
    idx = 0
    for name, group in grouped:
        stop_coords = []
        tooltip_content = f"<span style='display: none'>[{group.iloc[0]['route_id']}]</span>{group.iloc[0]['route_short_name']}"

        for row_index, row in group.iterrows():
            stop_coords.append(row[["stop_lat", "stop_lon"]].values)
            tooltip_content += f"<br/>{row['stop_name']}"

            color = colors[idx] if COLOR_TYPE == "colormap" else color_name
            folium.PolyLine(stop_coords, tooltip=tooltip_content, color=color).add_to(
                path_layer
            )
        idx += 1

    return path_layer


LEGEND_STYLE = """
    <style type='text/css'>
        .maplegend .legend-title {
            text-align: left;
            margin-bottom: 5px;
            font-weight: bold;
            font-size: 90%;
        }
        .maplegend .legend-scale p {
            font-weight: bold;
            font-size: 80%;
            margin-bottom: 0px;
        }
        .maplegend .legend-scale ul {
            margin: 0;
            margin-bottom: 5px;
            padding: 0;
            float: left;
            list-style: none;
        }
        .maplegend .legend-scale ul li {
            font-size: 80%;
            list-style: none;
            margin-left: 0;
            line-height: 18px;
            margin-bottom: 2px;
        }
        .maplegend ul.legend-stations li span {
            display: block;
            float: left;
            height: 10px;
            width: 10px;
            margin-right: 5px;
            margin-left: 0;
            margin-top: 4px;
            border: 1px solid #000;
        }
        .maplegend ul.legend-lines li span {
            display: block;
            float: left;
            height: 16px;
            width: 30px;
            margin-right: 5px;
            margin-left: 0;
            margin-top: 1px;
            border: 1px solid #000;
        }
        .maplegend .legend-source {
            font-size: 80%;
            color: #777;
            clear: both;
        }
        .maplegend a {
            color: #777;
        }
    </style>
"""


def generate_main_legend():
    # referenced from https://nbviewer.org/gist/talbertc-usgs/18f8901fc98f109f2b71156cf3ac81cd
    template = f"""
    {{% macro html(this, kwargs) %}}
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.7); border-radius:6px; padding: 10px; font-size:14px; right: 20px; top: 20px;'
    >
        <div class='legend-title'>Legend</div>
        <div class='legend-scale'>
            <p>Stations</p>
            <ul class='legend-stations'>
                <li><span style='background:#ffffbf; border-radius:50px;'></span>Reachable by A</li>
                <li><span style='background:#91bfdb; border-radius:50px;'></span>Reachable by B</li>
                <li><span style='background:#fc8d59;'></span>Reachable by both</li>
            </ul>
            <p>Lines</p>
            <ul class='legend-lines'>
                <li><span style='background: #808080;'></span>Not shared routes</li>
                <!-- inferno in css https://bennettfeely.com/scales/ -->
                <li><span style='background: #eb8f70; background-image: linear-gradient(90deg, #000004, #160b39, #420a68, #6a176e, #932667, #ba3655, #dd513a, #f3761b, #fca50a, #f6d746, #f6d746);'></span>Shared routes</li>
            </ul>
        </div>
    </div>
    </body>
    </html>
    {LEGEND_STYLE}
    {{% endmacro %}}
    """

    macro = MacroElement()
    macro._template = Template(template)

    return macro


def generate_sub_a_legend():
    template = f"""
    {{% macro html(this, kwargs) %}}
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.7); border-radius:6px; padding: 10px; font-size:14px; right: 20px; top: 20px;'
    >
        <div class='legend-title'>Legend</div>
        <div class='legend-scale'>
            <p>Stations</p>
            <ul class='legend-stations'>
                <li><span style='background:#ffffbf; border-radius:50px;'></span>Reachable by A</li>
            </ul>
            <p>Lines</p>
            <ul class='legend-lines'>
                <!-- plasma in css https://bennettfeely.com/scales/ -->
                <li><span style='background: #a84a73; background-image: linear-gradient(90deg, #0d0887, #41049d, #6a00a8, #8f0da4, #b12a90, #cb4679, #e16462, #f1834c, #fca636, #fcce25, #fcce25);'></span>Shared routes</li>
            </ul>
        </div>
    </div>
    </body>
    </html>
    {LEGEND_STYLE}
    {{% endmacro %}}
    """

    macro = MacroElement()
    macro._template = Template(template)

    return macro


def generate_sub_b_legend():
    template = f"""
    {{% macro html(this, kwargs) %}}
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.7); border-radius:6px; padding: 10px; font-size:14px; right: 20px; top: 20px;'
    >
        <div class='legend-title'>Legend</div>
        <div class='legend-scale'>
            <p>Stations</p>
            <ul class='legend-stations'>
                <li><span style='background:#91bfdb; border-radius:50px;'></span>Reachable by B</li>
            </ul>
            <p>Lines</p>
            <ul class='legend-lines'>
                <!-- viridis in css https://bennettfeely.com/scales/ -->
                <li><span style='background: #4a7d70; background-image: linear-gradient(90deg, #440154, #482475, #414487, #355f8d, #2a788e, #21908d, #22a884, #42be71, #7ad151, #bddf26, #bddf26);'></span>Shared routes</li>
            </ul>
        </div>
    </div>
    </body>
    </html>
    {LEGEND_STYLE}
    {{% endmacro %}}
    """

    macro = MacroElement()
    macro._template = Template(template)

    return macro
