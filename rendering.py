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


def draw_routes(stop_data, color_map_name):
    path_layer = folium.FeatureGroup(name="Paths")
    grouped = stop_data.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id")
    colors = seaborn.color_palette(color_map_name, n_colors=grouped.ngroups).as_hex()
    idx = 0
    for name, group in grouped:
        stop_coords = []
        tooltip_content = f"<span style='display: none'>[{group.iloc[0]['route_id']}]</span>{group.iloc[0]['route_short_name']}"

        for row_index, row in group.iterrows():
            stop_coords.append(row[["stop_lat", "stop_lon"]].values)
            tooltip_content += f"<br/>{row['stop_name']}"

            folium.PolyLine(
                stop_coords, tooltip=tooltip_content, color=colors[idx]
            ).add_to(path_layer)
        idx += 1

    return path_layer


def generate_legend():
    # referenced from https://nbviewer.org/gist/talbertc-usgs/18f8901fc98f109f2b71156cf3ac81cd
    template = """
    {% macro html(this, kwargs) %}
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
                <li><span style='background:#1b9e77; border-radius:50px;'></span>Reachable by A</li>
                <li><span style='background:#d95f02; border-radius:50px;'></span>Reachable by B</li>
                <li><span style='background:#7570b3;'></span>Reachable by both</li>
            </ul>
            <p>Lines</p>
            <ul class='legend-lines'>
                <!-- BuGn and OrRd in css https://bennettfeely.com/scales/-->
                <li><span style='background: #87c3c7; background-image: linear-gradient(90deg, #e5f5df, #d4eece, #bde5bf, #9fd9bb, #7bcbc4, #58b7cd, #399cc6, #1e7eb7, #0b60a1, #0b60a1);'></span>From destination A</li>
                <li><span style='background: #eb8f70; background-image: linear-gradient(90deg, #feebcf, #fddcaf, #fdca94, #fdb07a, #fa8e5d, #f16c49, #e04630, #c81e13, #a70403, #a70403);'></span>From destination B</li>
            </ul>
        </div>
    </div>
    </body>
    </html>

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
    {% endmacro %}"""

    macro = MacroElement()
    macro._template = Template(template)

    return macro
