import configparser
import os
from io import BytesIO
from pathlib import Path

import geopandas
import rasterio
from munch import Munch
from ra2ce.analysis.analysis_config_data.analysis_config_data import AnalysisSectionDamages, AnalysisConfigData
from ra2ce.analysis.analysis_config_data.enums.analysis_damages_enum import AnalysisDamagesEnum
from ra2ce.analysis.analysis_config_data.enums.damage_curve_enum import DamageCurveEnum
from ra2ce.analysis.analysis_config_data.enums.event_type_enum import EventTypeEnum
from ra2ce.network import RoadTypeEnum
from ra2ce.network.network_config_data.enums.aggregate_wl_enum import AggregateWlEnum
from ra2ce.network.network_config_data.enums.source_enum import SourceEnum
from ra2ce.network.network_config_data.network_config_data import NetworkSection, CleanupSection, NetworkConfigData, \
    HazardSection
from ra2ce.network.network_wrappers.osm_network_wrapper.osm_network_wrapper import OsmNetworkWrapper
from ra2ce.ra2ce_handler import Ra2ceHandler
from shapely import Polygon
from shapely.geometry import shape
from viktor import ViktorController, UserError, progress_message, GeoPolygon, GeoPolyline, GeoPoint, Color
from viktor.core import NamedTemporaryFile
from viktor.result import SetParamsResult
from viktor.utils import memoize
from viktor.views import WebResult, WebView, MapResult, MapLegend, MapPolygon, MapView, MapPolyline
import geopandas as gpd
import osmnx

from constants import color_osm_dict, map_legend_osm
from parametrization_new import Parametrization


class Controller(ViktorController):
    label = 'Overview'
    children = []
    parametrization = Parametrization

    @MapView('Selection Map', duration_guess=1)
    def get_map_view(self, params: Munch, **kwargs):
        features = []

        if params.network_configuration.tab.selection_polygon:
            features.append(MapPolygon.from_geo_polygon(params.network_configuration.tab.selection_polygon))

        root_dir = Path(self.get_work_dir())
        network_gpkg = root_dir.joinpath("static", 'output_graph', 'base_network.gpkg')
        if network_gpkg.exists():
            legend = map_legend_osm
            gdf = gpd.read_file(network_gpkg)
            for index, row in gdf.iterrows():
                linestring = row['geometry']
                road_type = row["highway"]

                geopolyline = GeoPolyline(*[GeoPoint(*[point[1], point[0]]) for point in linestring.coords])
                color = color_osm_dict.get(road_type, "#000000")
                polyline = MapPolyline.from_geo_polyline(geopolyline, color=Color.from_hex(color))

                features.append(polyline)
        else:
            legend = MapLegend([
                # (Color.green(), "Origins"),
                # (Color.blue(), "Hospitals"),
            ])

        return MapResult(features, legend=legend)

    @WebView('Detailed Network Info', duration_guess=1)
    def detailed_network_info(self, params: Munch, **kwargs):
        root_dir = Path(self.get_work_dir())

        network_gpkg = root_dir.joinpath("static", 'output_graph', 'base_network.gpkg')
        if network_gpkg.exists():
            gdf = gpd.read_file(network_gpkg)
            res_map = gdf.explore(color='black', tiles="CartoDB positron")
            path_save = Path(__file__).parent.joinpath("network_map_results.html")
            res_map.save(path_save)

            return WebResult.from_path(path_save)
        else:
            raise UserError("Network not available")

    def download_network(self, params, **kwargs):

        # 1. check if all required fields are filled
        if params.network_configuration.tab.selection_polygon is None:
            raise UserError("Please select a region of interest")
        if not params.network_configuration.tab.roadtype_select:
            raise UserError("Please select road types")

        root_dir = Path(self.get_work_dir())
        static_path = root_dir.joinpath("static")
        output_path = root_dir.joinpath("output")

        # 2. Clean up workign directory
        output_directories = [
            root_dir / "static" / "output_graph",
            root_dir / "static" / "network",
        ]
        clean_files(output_directories)

        # 3. Network configuration

        polygon = Polygon(
            [[point.lon, point.lat] for point in params.network_configuration.tab.selection_polygon.points])
        gdf = geopandas.GeoDataFrame(geometry=[polygon])
        path_to_polygon_geojson = root_dir / "static/network/map.geojson"
        gdf.to_file(path_to_polygon_geojson, driver="GeoJSON")

        _network_section = NetworkSection(
            directed=False,
            source=SourceEnum.OSM_DOWNLOAD,
            road_types=[RoadTypeEnum(road_type) for road_type in params.network_configuration.tab.roadtype_select],
            polygon=path_to_polygon_geojson,
            save_gpkg=True

        )

        # pass the specified sections as arguments for configuration

        _network_config_data = NetworkConfigData(
            root_path=root_dir,
            static_path=static_path,
            output_path=output_path,
            network=_network_section,
        )

        _graph, _gdf = OsmNetworkWrapper.get_network_from_polygon(_network_config_data, polygon)

        handler = Ra2ceHandler.from_config(_network_config_data, None)
        progress_message("Downloading the network from OSM ... Depending on the size, this can take up to a few minutes ")
        handler.configure()
        return SetParamsResult(params)


    @WebView('Hazard Map', duration_guess=5)
    def hazard_map(self, params: Munch, **kwargs):
        features = []

        import folium

        # open raster file
        raster_file = params.hazard_mapping.section.hazard_select.file
        data = BytesIO(raster_file.getvalue_binary())
        with rasterio.open(data) as src:
            crs = src.crs
            t = src.transform
            shapes_values = list(rasterio.features.shapes(src.read(1), transform=t))
            # Get the bounding box
            bounds = src.bounds
            # Get the extent
            extent = [
                [bounds.left, bounds.top],
                [bounds.right, bounds.top],
                [bounds.right, bounds.bottom],
                [bounds.left, bounds.bottom],
                [bounds.left, bounds.top]
            ]
        features = [
            {'type': 'Feature', 'properties': {'value': value}, 'geometry': shape(geom)}
            for geom, value in shapes_values if value > 0  # Filter out zero values
        ]

        # Create a GeoDataFrame from the list of features
        gdf = gpd.GeoDataFrame.from_features(features, crs=crs)

        # Now you can use 'gdf.explore()' to visualize the GeoDataFrame
        m = gdf.explore(
            column='value',  # The column based on which to apply colors
            cmap='Blues',  # Your chosen colormap
            tiles='CartoDB positron',
            scheme='Quantiles',
            style_kwds={'fillOpacity': 0.7, 'lineOpacity': 0.1}
        )

        # Add layer control to toggle layers
        folium.LayerControl().add_to(m)

        polygon = Polygon(
            [[point.lon, point.lat] for point in params.network_configuration.tab.selection_polygon.points])
        # add polygon to map:
        folium.GeoJson(polygon, name='polygon').add_to(m)
        m.save("map.html")

        path_save = Path(__file__).parent.joinpath("hazard.html")
        m.save(path_save)

        return WebResult.from_path(path_save)
        # Display the map


    def overlay_hazard(self, params, **kwargs):

        # 1. check if all required fields are filled
        if params.network_configuration.tab.selection_polygon is None:
            raise UserError("Please select a region of interest")
        if not params.network_configuration.tab.roadtype_select:
            raise UserError("Please select road types")
        if params.hazard_mapping.section.hazard_select is None:
            raise UserError("Please upload a hazard file")

        root_dir = Path(self.get_work_dir())
        static_path = root_dir.joinpath("static")
        output_path = root_dir.joinpath("output")
        hazard_path = root_dir.joinpath("static", "hazard")

        # 3. Network configuration


        path_to_polygon_geojson = root_dir / "static/network/map.geojson"

        _network_section = NetworkSection(
            directed=False,
            source=SourceEnum.OSM_DOWNLOAD,
            road_types=[RoadTypeEnum(road_type) for road_type in params.network_configuration.tab.roadtype_select],
            polygon=path_to_polygon_geojson,
            save_gpkg=True

        )

        raster_file = params.hazard_mapping.section.hazard_select.file
        data = BytesIO(raster_file.getvalue_binary())

        # Copy hazard file to static/hazard
        hazard_file = hazard_path.joinpath("hazard.tif")
        with open(hazard_file, 'wb') as f:
            f.write(data.getvalue())

        _hazard = HazardSection(
            hazard_map=[hazard_file],  # [Path(geotiff_files[0])],
            hazard_field_name=['waterdepth'],
            aggregate_wl=AggregateWlEnum.MAX,
            hazard_crs='EPSG:28992'
        )

        # pass the specified sections as arguments for configuration

        _network_config_data = NetworkConfigData(
            root_path=root_dir,
            static_path=static_path,
            output_path=output_path,
            hazard=_hazard,
            network=_network_section,
        )
        progress_message("Overlaying the hazard map on the network ... Depending on the size of the hazard, this can take up to a few minutes.")
        handler = Ra2ceHandler.from_config(_network_config_data, None)
        handler.configure()


        # return MapResult(features)

    @WebView('Overlaid Network', duration_guess=5)
    def overlaid_network(self, params: Munch, **kwargs):
        root_dir = Path(self.get_work_dir())

        network_gpkg = root_dir.joinpath("static", 'output_graph', 'base_network_hazard.gpkg')
        if network_gpkg.exists():
            gdf = gpd.read_file(network_gpkg)
            res_map = gdf.explore(column="EV1_ma", tiles="CartoDB positron", cmap="viridis_r", scheme='EqualInterval')
            path_save = Path(__file__).parent.joinpath("network_map_results.html")
            res_map.save(path_save)

            return WebResult.from_path(path_save)
        else:
            raise UserError("Network not available")


    def run_analysis(self, params: Munch, **kwargs):
        root_dir = Path(self.get_work_dir())
        output_directories = [
            root_dir / "output" / "damages"
        ]
        clean_files(output_directories)

        root_dir = Path(self.get_work_dir())
        static_path = root_dir.joinpath("static")
        output_path = root_dir.joinpath("output")
        hazard_path = root_dir.joinpath("static", "hazard")

        path_to_polygon_geojson = root_dir / "static/network/map.geojson"

        _network_section = NetworkSection(
            directed=False,
            source=SourceEnum.OSM_DOWNLOAD,
            road_types=[RoadTypeEnum(road_type) for road_type in params.network_configuration.tab.roadtype_select],
            polygon=path_to_polygon_geojson,
            save_gpkg=True

        )

        raster_file = params.hazard_mapping.section.hazard_select.file
        data = BytesIO(raster_file.getvalue_binary())

        # Copy hazard file to static/hazard
        hazard_file = hazard_path.joinpath("hazard.tif")
        with open(hazard_file, 'wb') as f:
            f.write(data.getvalue())

        _hazard = HazardSection(
            hazard_map=[hazard_file],  # [Path(geotiff_files[0])],
            hazard_field_name=['waterdepth'],
            aggregate_wl=AggregateWlEnum.MAX,
            hazard_crs='EPSG:28992'
        )

        # pass the specified sections as arguments for configuration

        _network_config_data = NetworkConfigData(
            root_path=root_dir,
            static_path=static_path,
            output_path=output_path,
            hazard=_hazard,
            network=_network_section,
        )

        _section_damage = [AnalysisSectionDamages(
            name='Manual_damageXX',
            analysis=AnalysisDamagesEnum.DAMAGES,
            event_type=EventTypeEnum.EVENT,
            damage_curve=DamageCurveEnum.HZ,
            save_gpkg=True,
            save_csv=True,
        )]

        _analysis_config_data = AnalysisConfigData(analyses=_section_damage, root_path=root_dir,
                                                   output_path=output_path)

        handler = Ra2ceHandler.from_config(_network_config_data, _analysis_config_data)
        handler.configure()
        handler.run_analysis()




    @WebView('Result Analysis', duration_guess=5)
    def result_analysis(self, params: Munch, **kwargs):
        root_dir = Path(self.get_work_dir())

        network_gpkg = root_dir.joinpath("output", 'damages', 'Manual_damageXX_link_based.gpkg')
        if network_gpkg.exists():
            gdf = gpd.read_file(network_gpkg)
            res_map = gdf.explore(column="dam_EV1_HZ", tiles="CartoDB positron", cmap="viridis_r", scheme='EqualInterval')
            path_save = Path(__file__).parent.joinpath("damage_map_results.html")
            res_map.save(path_save)

            return WebResult.from_path(path_save)
        else:
            raise UserError("Network not available")



    @staticmethod
    def run_network(road_type: list[str], poly_coords: list[list[float]], root_dir: str):
        """

        """

        root_dir = Path(root_dir)
        output_directories = [
            root_dir / "output" / "single_link_redundancy",
            root_dir / "static" / "output_graph",
            root_dir / "static" / "network",
        ]
        clean_files(output_directories)

        get_network(root_dir, poly_coords)
        _network_ini_name = "network.ini"  # set the name for the network.ini settings file
        _analyses_ini_name = "analyses.ini"  # set the name for the analysis.ini
        network_ini = root_dir / _network_ini_name  # set path to network.ini
        analyses_ini = root_dir / _analyses_ini_name  # set path to analysis.ini

        # modify network.ini
        # modify_network_ini(network_ini, road_type)
        osmnx.utils.config(cache_folder=Path(__file__).parent / "osmnx_cache")

        try:
            handler = Ra2ceHandler(network=network_ini, analysis=analyses_ini)
            progress_message(message=f'Running RA2CE: initialising network')

            handler.configure()
            progress_message(message=f'Running RA2CE: running analysis')
            handler.run_analysis()
        except Exception as e:
            raise UserError(f"Error running RA2CE: {e}")

        return {}

    @WebView("Criticality analysis results", duration_guess=4)
    def single_link_redundancy_map(self, params: Munch, **kwargs):
        """
        Callback to run a single link redundancy analysis and display the results on a map.
        """

        # 1. Get the root working directory for SLR
        root_dir = self.get_working_dir('single_link_redundancy')

        # 2. Get the selected road types and polygon coordinates
        poly = params.page_criticality_analysis.tab.network.selection_polygon
        poly_coord = []
        for p in poly.points:
            poly_coord.append([p.lon, p.lat])

        # 3. Run the network analysis if input have changed (memoized)
        self.run_network(params.page_criticality_analysis.tab.network.roadtype_select, poly_coord, str(root_dir))

        # 4. Post-process the results and display on the map
        analysis_output_folder = root_dir / "output" / "single_link_redundancy"  # specify path to output folder
        redundancy_gdf = gpd.read_file(analysis_output_folder / "beira_redundancy.gpkg")

        if params.page_criticality_analysis.tab.single_link_redun.result_type == 'link_redundancy':
            redundancy_gdf['redundancy'] = redundancy_gdf['detour'].astype(str)

            res_map = redundancy_gdf.explore(column='redundancy', tiles="CartoDB positron",
                                             cmap=['red', 'green'])
        elif params.page_criticality_analysis.tab.single_link_redun.result_type == 'alt_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='alt_dist', tiles="CartoDB positron", cmap='winter_r')

        elif params.page_criticality_analysis.tab.single_link_redun.result_type == 'diff_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='diff_dist', tiles="CartoDB positron", cmap='winter_r')

        else:
            raise UserError("Invalid result type")
        path_save = Path(__file__).parent / "working_directory/single_link_redun" / "map_result.html"
        res_map.save(path_save)

        return WebResult.from_path(path_save)

    # @WebView("Origin Destination", duration_guess=4)
    # def origin_destination_map(self, params: Munch, **kwargs):
    #
    #     root_dir = Path(__file__).parent / "working_directory/origin_destination_analysis_without_hazard"
    #     origins_inspection = root_dir / "static" / "network" / "origins.shp"
    #
    #     # change shapefile:
    #
    #     origins_gdf = gpd.read_file(origins_inspection, driver="SHP")
    #     origins_gdf.head()
    #     res_map = origins_gdf.explore(column="POPULATION", cmap="viridis_r", tiles="CartoDB dark_matter")
    #
    #     _network_ini_name = "network.ini"  # set the name for the network.ini
    #     _analysis_ini_name = "analysis.ini"  # set the name for the analysis.ini
    #
    #     network_ini = root_dir / _network_ini_name
    #     analysis_ini = root_dir / _analysis_ini_name
    #
    #     handler = Ra2ceHandler(network=network_ini, analysis=analysis_ini)
    #     handler.configure()
    #     handler.run_analysis()
    #
    #
    #     ### WITH HAZARD
    #     root_dir = Path(__file__).parent / "working_directory/origin_destination_analysis_with_hazard"
    #     hazard_folder = root_dir / "static" / "hazard"  # find the hazard folder where you locate your floo dmap
    #     hazard_map = hazard_folder / "max_flood_depth.tif"  # set the location of the hazard map
    #     _network_ini_name = "network.ini"  # set the name for the network.ini
    #     _analysis_ini_name = "analysis.ini"  # set the name for the analysis.ini
    #
    #     network_ini = root_dir / _network_ini_name
    #     analysis_ini = root_dir / _analysis_ini_name
    #
    #     handler = Ra2ceHandler(network=network_ini, analysis=analysis_ini)
    #     handler.configure()
    #     handler.run_analysis()
    #
    #     analysis_output_path = root_dir / "output" / "multi_link_origin_closest_destination"
    #     gdf = gpd.read_file(analysis_output_path / 'multi_link_origin_closest_destination_destinations.gpkg')
    #     print(gdf.head())  # show the origins
    #
    #     gdf_education = gdf[gdf['category'] == 'education']
    #     gdf_education['access_PD1'] = gdf_education.apply(lambda row: '1' if row['EV1_ma_PD1'] > 0 else '0', axis=1)
    #     res_map = gdf_education.explore(column='access_PD1', cmap=['red', 'green'], tiles="CartoDB dark_matter")
    #
    #
    #     res_map.save("res_map.html")
    #
    #
    #     return WebResult.from_path("res_map.html")

    @staticmethod
    def get_work_dir() -> Path:
        """
        Get the right root working directory
        """
        root_dir = Path(
            __file__).parent / "work_dir"
        return root_dir


def clean_files(all_directories: list):
    """
    Clean all files in the specified directories
    """
    # Iterate through all specified directories
    for directory_path in all_directories:
        # List all files in the directory
        file_list = os.listdir(directory_path)

        # Iterate through the files and delete files created after the code start time
        for file_name in file_list:
            file_path = os.path.join(directory_path, file_name)
            os.remove(file_path)


def modify_network_ini(network_init_path: Path, road_types: list[str]):
    """Write into network.ini the selected road types for the network"""

    config = configparser.ConfigParser()
    # Read the existing configuration from the file
    config.read(network_init_path)

    new_road_types = ""
    for road_type in road_types:
        new_road_types += road_type.lower() + ","
    new_road_types = new_road_types[:-1]

    config.set("network", "road_types", new_road_types)

    # Write the updated configuration back to the file
    with open(network_init_path, "w") as config_file:
        config.write(config_file)


def get_network(root_dir: Path, poly_coords: list[list[float]]):
    # create  geojson from the selected polygon
    if poly_coords:
        polygon = Polygon([[point[0], point[1]] for point in poly_coords])
        gdf = geopandas.GeoDataFrame(geometry=[polygon])
        path_to_geojson = root_dir / "static/network/map.geojson"
        gdf.to_file(path_to_geojson, driver="GeoJSON")
