from ra2ce.network import RoadTypeEnum
from viktor import LineBreak, BooleanField
from viktor.parametrization import ViktorParametrization, Section, NumberField, FileField, TableInput, TextField, \
    OptionField, DownloadButton, Text, Tab, GeoPolygonField, MultiSelectField, OptionListElement, GeoPointField, Page, \
    Step, ActionButton

option_roads = [
    OptionListElement(label="Motorway", value=RoadTypeEnum.MOTORWAY.value),
    OptionListElement(label="Motorway Link", value=RoadTypeEnum.MOTORWAY_LINK.value),
    OptionListElement(label="Trunk", value=RoadTypeEnum.TRUNK.value),
    OptionListElement(label="Trunk Link", value=RoadTypeEnum.TRUNK_LINK.value),
    OptionListElement(label="Primary", value=RoadTypeEnum.PRIMARY.value),
    OptionListElement(label="Primary Link", value=RoadTypeEnum.PRIMARY_LINK.value),
    OptionListElement(label="Secondary", value=RoadTypeEnum.SECONDARY.value),
    OptionListElement(label="Secondary Link", value=RoadTypeEnum.SECONDARY_LINK.value),
    OptionListElement(label="Tertiary", value=RoadTypeEnum.TERTIARY.value),
    OptionListElement(label="Tertiary Link", value=RoadTypeEnum.TERTIARY_LINK.value),
    OptionListElement(label="Residential", value=RoadTypeEnum.RESIDENTIAL.value),
    OptionListElement(label="Unclassified", value=RoadTypeEnum.UNCLASSIFIED.value),
]

option_single_link_result_types = [
    OptionListElement(label="Link redundancy", value="link_redundancy"),
    OptionListElement(label="Detour", value="alt_dist"),
    OptionListElement(label="Difference distance", value="diff_dist"),
]


class Parametrization(ViktorParametrization):
    network_configuration = Step("Network definition", views=["get_map_view", "detailed_network_info"])
    network_configuration.tab = Tab("Settings")
    network_configuration.tab.text1 = Text("""
### 1. Network configuration
    
The first step is to obtain a road network for which a resilience analysis will be performed. The road network is 
extracted from OpenStreetMap based on the region of interest and the road types selected.
    
Please click on 'Create polygon' below and start drawing a polygon on the map to define the region of interest. Select as well
the types of roads.

    """)
    network_configuration.tab.selection_polygon = GeoPolygonField("Region Selection")
    network_configuration.tab.roadtype_select = MultiSelectField("Select road type", options=option_roads)
    network_configuration.tab.lb = LineBreak()
    network_configuration.tab.text2 = Text("""
### 2. Download network

Click on the button below to download the network from OSM.
    """)

    network_configuration.tab.button_download = ActionButton("Download network", "download_network")

    hazard_mapping = Step("Hazard mapping", views=["hazard_map", "overlaid_network"])
    hazard_mapping.section = Section("Settings")
    hazard_mapping.section.text1 = Text(""" 
### 1. Hazard mapping
    
The second step is to define the hazard(s) that will be used in the analysis. The hazard(s) can be selected from the
dropdown list below.

    """)
    hazard_mapping.section.hazard_select = FileField("Select hazard file", file_types=[".tif", ".tiff"])
    hazard_mapping.section.dummy = BooleanField("on/off")

    hazard_mapping.section.lb = LineBreak()
    hazard_mapping.section.text2 = Text("""
### 2. Overlay hazard map

Click on the button below to overlay the hazard map on the network.
    """)
    hazard_mapping.section.button_overlay = ActionButton("Overlay hazard map", "overlay_hazard")

    analysis_selection = Step("Analysis selection", views=[])


