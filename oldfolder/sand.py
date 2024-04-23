from pathlib import Path
import geopandas as gpd
from ra2ce.ra2ce_handler import Ra2ceHandler


r"""
This scripts runs with no issues using the ra2ce native environment (version 0.9.1) and creates the files simple_to_complex.json

However this script returns an error with the environment created in this viktor project:
linkin_tables is None because: endpoints = {n for n in G.nodes if _is_endpoint(G, n, endpoint_attrs)} fails


Also, I noticed that during viktor-install, GDAL wheel is no longer built:
Building wheels for collected packages: ra2ce
  Building wheel for ra2ce (pyproject.toml): started
  Building wheel for ra2ce (pyproject.toml): finished with status 'done'
  Created wheel for ra2ce: filename=ra2ce-0.9.1-py3-none-any.whl size=229987 sha256=af16b3e14aa4b7427e0c28428a175167f6b3b546d1180f759753775bccd97c37
  Stored in directory: C:\Users\hauth\AppData\Local\Temp\pip-ephem-wheel-cache-vdt3zyad\wheels\02\8e\dd\e34c80b397858dca945f7c4000d4ec423c397b989884e59d93
Successfully built ra2ce


It used to say: Building wheels for collected packages: ra2ce, GDAL
But not anymore


## PROBLEM IDENTIFIED ??? ###
This seems to be a problem originated from gdal version 3.8.2 which is incompatible with ra2ce 0.9.1
- Either try find the GDAL wheel 3.5.1
- Or revert the fork to ra2ce version 0.7.0
"""
root_dir = Path(r"C:\Users\hauth\bitbucket\ra2ce-viktor\working_directory\single_link_redun")
# root_dir = Path(r"C:\Users\hauth\bitbucket\ra2ce\examples\data\single_link_redun")
output_directories = [
    root_dir / "output" / "single_link_redundancy",
    root_dir / "static" / "output_graph",
    root_dir / "static" / "network",
]

_network_ini_name = "network.ini"  # set the name for the network.ini settings file
_analyses_ini_name = "analyses.ini"  # set the name for the analysis.ini
network_ini = root_dir / _network_ini_name  # set path to network.ini
analyses_ini = root_dir / _analyses_ini_name  # set path to analysis.ini



handler = Ra2ceHandler(network=network_ini, analysis=analyses_ini)

handler.configure()
handler.run_analysis()

analysis_output_folder = root_dir / "output" / "single_link_redundancy"  # specify path to output folder
redundancy_gdf = gpd.read_file(analysis_output_folder / "beira_redundancy.gpkg")

redundancy_gdf['redundancy'] = redundancy_gdf['detour'].astype(str)
print(redundancy_gdf)

res_map = redundancy_gdf.explore(column='redundancy', tiles="CartoDB positron",
                                     cmap=['red', 'green'])
print(type(res_map))
res_map.save("redundant_roads_map1234.html")
res_map.save("redundant_roads_map1234.png")
