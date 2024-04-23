import configparser
from io import StringIO
from pathlib import Path

from munch import Munch
from shapely import Polygon
from viktor.core import Storage, File, Color
from viktor.utils import memoize

from viktor import ViktorController, UserError
from viktor.views import MapView, MapResult, MapPolygon, MapPoint, MapPolyline, WebView, WebResult, MapLegend
import geopandas
from viktor.geometry import GeoPoint, GeoPolyline
from ra2ce.ra2ce_handler import Ra2ceHandler  # import the ra2cehandler to run ra2ce analyses
import geopandas as gpd
from pathlib import Path
import os

from oldfolder.overview.parametrization import Parametrization


class Controller(ViktorController):
    label = 'Overview'
    children = []
    parametrization = Parametrization

    @MapView('Selection Map', duration_guess=1)
    def get_map_view(self, params: Munch, **kwargs):
        features = []

        if params.page_criticality_analysis.tab.network.selection_polygon:
            features.append(MapPolygon.from_geo_polygon(params.tab.network.selection_polygon))

        # if params.tab.OD.origin:
        #     features.append(MapPoint.from_geo_point(params.tab.OD.origin, color=Color.green()))
        #
        # if params.tab.OD.destination:
        #     features.append(MapPoint.from_geo_point(params.tab.OD.destination, color=Color.blue(), icon='plus-thick'))

        legend = MapLegend([
            (Color.green(), "Origins"),
            (Color.blue(), "Hospitals"),
        ])

        return MapResult(features, legend=legend)

    @staticmethod
    @memoize
    def run_network(road_type: list[str], poly_coords: list[list[float]], root_dir: str):

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
        modify_network_ini(network_ini, road_type)

        handler = Ra2ceHandler(network=network_ini, analysis=analyses_ini)
        handler.configure()
        handler.run_analysis()

        # analysis_output_folder = root_dir / "output" / "single_link_redundancy"  # specify path to output folder
        # redundancy_gdf = gpd.read_file(analysis_output_folder / "beira_redundancy.gpkg")

        return {}

    @WebView("Single link redundancy", duration_guess=4)
    def single_link_redundancy_map(self, params: Munch, **kwargs):

        root_dir = self.get_working_dir('single_link_redundancy')

        poly = params.tab.network.selection_polygon
        poly_coord = []
        for p in poly.points:
            poly_coord.append([p.lon, p.lat])

        self.run_network(params.tab.network.roadtype_select, poly_coord, str(root_dir))

        analysis_output_folder = root_dir / "output" / "single_link_redundancy"  # specify path to output folder
        redundancy_gdf = gpd.read_file(analysis_output_folder / "beira_redundancy.gpkg")

        if params.tab.single_link_redun.result_type == 'link_redundancy':
            redundancy_gdf['redundancy'] = redundancy_gdf['detour'].astype(str)

            res_map = redundancy_gdf.explore(column='redundancy', tiles="CartoDB positron",
                                             cmap=['red', 'green'])
        elif params.tab.single_link_redun.result_type == 'alt_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='alt_dist', tiles="CartoDB positron", cmap='winter_r')

        elif params.tab.single_link_redun.result_type == 'diff_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='diff_dist', tiles="CartoDB positron", cmap='winter_r')

        else:
            raise UserError("Invalid result type")

        res_map.save("redundant_roads_map.html")

        return WebResult.from_path("redundant_roads_map.html")

    @WebView("Origin Destination", duration_guess=4)
    def origin_destination_map(self, params: Munch, **kwargs):

        root_dir = self.get_working_dir("origin_destionation")
        road_type = params.tab.network.roadtype_select

        poly = params.tab.network.selection_polygon
        poly_coords = []
        for p in poly.points:
            poly_coords.append([p.lon, p.lat])

        root_dir = Path(root_dir)
        output_directories = [
            root_dir / "output" / "multi_link_origin_closest_destination",
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
        modify_network_ini(network_ini, road_type)

        handler = Ra2ceHandler(network=network_ini, analysis=analyses_ini)
        handler.configure()
        handler.run_analysis()

        analysis_output_folder = root_dir / "output" / "multi_link_origin_closest_destination"  # specify path to output folder
        redundancy_gdf = gpd.read_file(analysis_output_folder / "beira_redundancy.gpkg")

        if params.tab.single_link_redun.result_type == 'link_redundancy':
            redundancy_gdf['redundancy'] = redundancy_gdf['detour'].astype(str)

            res_map = redundancy_gdf.explore(column='redundancy', tiles="CartoDB positron",
                                             cmap=['red', 'green'])
        elif params.tab.single_link_redun.result_type == 'alt_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='alt_dist', tiles="CartoDB positron", cmap='winter_r')

        elif params.tab.single_link_redun.result_type == 'diff_dist':
            alt_dist_gpd = redundancy_gdf[redundancy_gdf['detour'] == 1]
            res_map = alt_dist_gpd.explore(column='diff_dist', tiles="CartoDB positron", cmap='winter_r')

        else:
            raise UserError("Invalid result type")

        res_map.save("redundant_roads_map.html")

        return WebResult.from_path("redundant_roads_map.html")



    @staticmethod
    def get_working_dir(analysis: str) -> Path:
        if analysis == "single_link_redundancy":
            root_dir = Path(
                __file__).parent.parent / "examples/data/single_link_redun"  #
        elif analysis == 'origin_destination':
            root_dir = Path(
                __file__).parent.parent / "examples/data/od_no_hazard"
        else:
            raise ValueError("analysis not supported")
        return root_dir


def clean_files(all_directories: list):
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
