from viktor.parametrization import ViktorParametrization, Section, NumberField, FileField, TableInput, TextField, \
    OptionField, DownloadButton, Text, Tab, GeoPolygonField, MultiSelectField, OptionListElement, GeoPointField, Page

option_roads = [
    OptionListElement(label="Motorway", value="motorway"),
    OptionListElement(label="Motorway Link", value="motorway_link"),
    OptionListElement(label="Trunk", value="trunk"),
    OptionListElement(label="Trunk Link", value="trunk_link"),
    OptionListElement(label="Primary", value="primary"),
    OptionListElement(label="Primary Link", value="primary_link"),
    OptionListElement(label="Secondary", value="secondary"),
    OptionListElement(label="Secondary Link", value="secondary_link"),
    OptionListElement(label="Tertiary", value="tertiary"),
    OptionListElement(label="Tertiary Link", value="tertiary_link"),
    OptionListElement(label="Residential", value="residential"),
    OptionListElement(label="Unclassified", value="unclassified"),
]

option_single_link_result_types = [
    OptionListElement(label="Link redundancy", value="link_redundancy"),
    OptionListElement(label="Detour", value="alt_dist"),
    OptionListElement(label="Difference distance", value="diff_dist"),
]


class Parametrization(ViktorParametrization):
    page_criticality_analysis = Page("Criticality Analysis", views=["get_map_view", "single_link_redundancy_map"])
    page_criticality_analysis.tab = Tab("Settings")
    page_criticality_analysis.tab.intro = Section("Introduction")
    page_criticality_analysis.tab.intro.text1 = Text("""
### Single link redundancy


The tool using the single link redundancy analysis from RA2CE to give insight into the criticality of (road) networks. 

It identifies best alternative routes, or high lack of alternative routes in case there is no redundancy.

The redundancy is then expressed in terms of total distance or time for the alternative route, or the difference in time/distance between the original and alternative route.

### How does it work?

Draw first a region of interest on the map, then select the road types you want to include in the analysis. The road network is then extracted from OpenStreetMap and the single link redundancy analysis is performed.

### 

Want to know more? Visit our repository: https://github.com/Deltares/ra2ce

""")

    page_criticality_analysis.tab.network = Section("Network configuration")

    page_criticality_analysis.tab.network.text2 = Text(
        "Select a region of interest and the road types associated with the network.")
    page_criticality_analysis.tab.network.selection_polygon = GeoPolygonField("Region Selection")
    page_criticality_analysis.tab.network.roadtype_select = MultiSelectField("Select road type", options=option_roads)

    page_criticality_analysis.tab.single_link_redun = Section("Result types")
    page_criticality_analysis.tab.single_link_redun.text2 = Text("""
### Redundancy
    
Shows for every link in the network its redundancy e.g. if a detour is feasible.

### Detour 

Shows the total distance or time required for the best alternative route.
    
### Difference distance
    
Shows the difference in distance or time between the original and alternative route.


    """)
    page_criticality_analysis.tab.single_link_redun.result_type = OptionField("Result type", options=
    option_single_link_result_types)

    page_criticality_analysis.tab_disclaimer = Tab("Disclaimer")
    page_criticality_analysis.tab_disclaimer.text1 = Text("""
    
                    GNU GENERAL PUBLIC LICENSE
                      Version 3, 29 June 2007

    Risk Assessment and Adaptation for Critical Infrastructure (RA2CE).
    Copyright (C) 2023 Stichting Deltares

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
    
    """)

    # tab.OD = Section("Origin-Destination")
    # tab.OD.text1 = Text("ADD description from jupyeter notebook here and expllain that tiff file can be upaloded")
    # tab.OD.upload_hazard_map = FileField("Upload hazard map", file_types=['.tif'])
    # tab.OD.origin = GeoPointField("Origin")
    # tab.OD.destination = GeoPointField("Destination")
    # tab.OD.type_destination = OptionField("Type of destination", options=['Education', 'Hospital'])

    page_origin_destination = Page("Origin Destination")
    page_origin_destination.tab = Tab("Settings")
    page_origin_destination.tab.intro = Section("Introduction")
    page_origin_destination.tab.intro.text1 = Text("""
### Original-Destination

Work in Progress ...

Analyse the impact of road disruptions on the accessibility of critical infrastructure in case of a hazard event (flooding, earthquake, etc.).

    """)
