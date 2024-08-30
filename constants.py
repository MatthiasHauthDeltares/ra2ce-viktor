from viktor import MapLegend, Color

color_osm_dict = {
    "highway": "#d186b6",
    "highway_link": "#d186b6",
    "trunk": "#f09aa8",
    "trunk_link": "#f09aa8",
    "primary": "#feb8a0",
    "primary_link": "#feb8a0",
    "secondary": "#fcd6a4",
    "secondary_link": "#fcd6a4",
    "tertiary": "#f7fabf",
    "tertiary_link": "#f7fabf",
    "residential": "#50554d",
    "unclassified": "#50554d",
}


map_legend_osm = MapLegend([
                (Color.from_hex("#d186b6"), "Highway"),
                (Color.from_hex("#f09aa8"), "Trunk"),
                (Color.from_hex("#feb8a0"), "Primary"),
                (Color.from_hex("#fcd6a4"), "Secondary"),
                (Color.from_hex("#f7fabf"), "Tertiary"),
                (Color.from_hex("#50554d"), "Residential"),
            ])