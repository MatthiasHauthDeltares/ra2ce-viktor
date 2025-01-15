import configparser
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
from viktor.result import SetParamsResult
from viktor.views import WebResult, WebView, MapResult, MapLegend, MapPolygon, MapView, MapPolyline
import geopandas as gpd

from constants import color_osm_dict, map_legend_osm
from parametrization_new import Parametrization
from rasterio.warp import calculate_default_transform, reproject
from rasterio.enums import Resampling


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
            root_dir / "output" / "damages",
            root_dir / "static" / "hazard"
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

        root_dir = self.get_work_dir()
        static_path = root_dir.joinpath("static")
        output_graph_path = root_dir.joinpath("static", "output_graph")
        output_path = root_dir.joinpath("output")
        hazard_path = root_dir.joinpath("static", "hazard")

        clean_hazard_overlay(output_graph_path, hazard_path)

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
            # Specify the new CRS (e.g., EPSG:4326 for WGS84)

        input_tif = hazard_file
        new_crs = 'EPSG:4326'  # Replace with the desired CRS
        output_tif = hazard_path.joinpath("hazard_new_crs.tif")
        modify_crs(input_tif, output_tif, new_crs)

        _hazard = HazardSection(
            hazard_map=[output_tif],  # [Path(geotiff_files[0])],
            hazard_field_name=['waterdepth'],
            aggregate_wl=AggregateWlEnum.MAX,
            hazard_crs='EPSG:4326'
        )

        # pass the specified sections as arguments for configuration

        _network_config_data = NetworkConfigData(
            root_path=root_dir,
            static_path=static_path,
            output_path=output_path,
            hazard=_hazard,
            network=_network_section,
        )
        # progress_message("Overlaying the hazard map on the network ... Depending on the size of the hazard, this can take up to a few minutes.")
        progress_message(f"{hazard_file}Overlaying the hazard map on the network ... Depending on the size of the hazard, this can take up to a few minutes.")
        handler = Ra2ceHandler.from_config(_network_config_data, None)
        handler.configure()



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


        # Copy hazard file to static/hazard
        hazard_file = hazard_path.joinpath("hazard_new_crs.tif")
        # with open(hazard_file, 'wb') as f:
        #     f.write(data.getvalue())

        _hazard = HazardSection(
            hazard_map=[hazard_file],  # [Path(geotiff_files[0])],
            # hazard_map=[],  # [Path(geotiff_files[0])],
            hazard_field_name=['waterdepth'],
            aggregate_wl=AggregateWlEnum.MAX,
            hazard_crs='EPSG:4326'
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
        try:
            _analysis_config_data = AnalysisConfigData(analyses=_section_damage, root_path=root_dir,
                                                       output_path=output_path)

            handler = Ra2ceHandler.from_config(_network_config_data, _analysis_config_data)
            # handler.configure()
            handler.run_analysis()
        except:
            raise UserError("failed with no configure")




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
            raise UserError("Damages analysis has not been run.")


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
        if not directory_path.exists():
            directory_path.mkdir(parents=True, exist_ok=True)

        # Iterate through the files and delete files created after the code start time
        for file in directory_path.iterdir():
            file.unlink()

def clean_hazard_overlay(output_graph_path: Path, hazard_path: Path):
    for file in output_graph_path.iterdir():
        filename = file.name
        if 'hazard' in filename:
            file.unlink()

    for file in hazard_path.iterdir():
        file.unlink()


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

def modify_crs(input_tif, output_tif, new_crs):
    # Open the input TIFF file
    with rasterio.open(input_tif) as src:
        # Get the current CRS, transform, width, and height of the source image

        from rasterio.crs import CRS
        new_crs = CRS().from_string("+proj=longlat +datum=WGS84 +no_defs")
        transform, width, height = calculate_default_transform(
            src.crs, new_crs, src.width, src.height, *src.bounds)

        # Create metadata for the new file
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': new_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        # Open the output TIFF file
        with rasterio.open(output_tif, 'w', **kwargs) as dst:
            # Reproject and write each band of the image
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=new_crs,
                    resampling=Resampling.nearest
                )
