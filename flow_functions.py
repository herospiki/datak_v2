import random

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from folium import Popup
from shapely.geometry import Point, Polygon


def expand_and_clean_dataset(flow_df):
    flow_expanded_df = flow_df.assign(tdwg=flow_df['tdwg'].str.split(
        ',')).explode('tdwg').reset_index(drop=True)
    flow_expanded_df['tdwg_level'] = flow_expanded_df['tdwg_level'].fillna(0)
    flow_expanded_df['tdwg'] = flow_expanded_df['tdwg'].fillna('Unknown')
    flow_expanded_df = flow_expanded_df.drop_duplicates()
    return flow_expanded_df


def random_point_in_bounds(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    x = np.random.uniform(minx, maxx)
    y = np.random.uniform(miny, maxy)
    return x, y


def get_level4_eco_id_list(mapping_df, level4_cod_values):
    true_columns_dict = {}
    all_true_columns = set()  # Set to store all true columns = eco_id_list
    for level4_cod_value in level4_cod_values:
        true_columns = []
        filtered_df = mapping_df[mapping_df['Level4_cod'] == level4_cod_value]
        if not filtered_df.empty:
            row = filtered_df.iloc[0]
            for column in mapping_df.columns[1:]:
                if row[column] == True:
                    true_columns.append(column)
                    all_true_columns.add(column)  # Add column to the set
        true_columns_dict[level4_cod_value] = true_columns
    return true_columns_dict, all_true_columns

# true_columns_dict, all_true_columns = get_true_columns(mapping_level_4_df, level4_cod_values)


def find_phyto_regions_for_flow_species(species, flow_expanded_df):
    # On ne va garder que le niveau 4 du TDWG pour le moment
    df = flow_expanded_df[flow_expanded_df['species']
                          == species].drop_duplicates()
    # On cherche les tdwg et tdwg_level où il y a une présence
    if (len(df) > 0):
        phyto_flow_df = df[(df['species'] == species) & (df['tdwg_level'] == 4)][['genus', 'short', 'species',
                                                                                  'autorite', 'tdwg']].drop_duplicates()
        return list(phyto_flow_df['tdwg'].unique())


def show_map(tdwg_data, eco_regions_df, level4_cod_values, eco_id_list):
    eco_regions_df['ECO_ID'] = eco_regions_df['ECO_ID'].astype('str')
    tdwg_layer = folium.FeatureGroup(name='tdwg', show=False)
    eco_regions_layer = folium.FeatureGroup(name='eco', show=False)
    print(eco_id_list)

    # Plot tdwg
    tdwg_level4 = tdwg_data['tdwg_level4']
    for i, r in tdwg_level4[tdwg_level4['Level4_cod'].isin(level4_cod_values)].iterrows():
        # Convert the Polygon or LineString to geoJSON format
        geo_json = gpd.GeoSeries(r['geometry']).simplify(
            tolerance=0.000001).to_json()
        geo_json = folium.GeoJson(data=geo_json,
                                  style_function=lambda x: {'fillColor': '#ffffff',
                                                            'color': '#000000',
                                                            'fillOpacity': 1,
                                                            'weight': 1},
                                  highlight_function=lambda x: {'fillColor': '#000000',
                                                                'color': '#000000',
                                                                'fillOpacity': 0.50,
                                                                'weight': 0.1},
                              
                                  )
    # Add popup with line description
        Popup(r.Level_4_Na).add_to(geo_json)

    # Add the feature to the appropriate layer
        geo_json.add_to(tdwg_layer)

# Plot eco_regions
    for i, r in eco_regions_df.loc[eco_regions_df['ECO_ID'].isin(eco_id_list)].iterrows():
        # Convert the Polygon or LineString to geoJSON format
        geo_json = gpd.GeoSeries(r['geometry']).simplify(
            tolerance=0.000001).to_json()
        geo_json = folium.GeoJson(data=geo_json,
                                  style_function=lambda x: {'fillColor': '#ffffff',
                                                            'color': '#000000',
                                                            'fillOpacity': 1,
                                                            'weight': 1},
                                  highlight_function=lambda x: {'fillColor': '#000000',
                                                                'color': '#000000',
                                                                'fillOpacity': 0.50,
                                                                'weight': 0.1})
    # Add popup with line description
        folium.Popup(r.ECO_NAME).add_to(geo_json)

    # Add the feature to the appropriate layer
        geo_json.add_to(eco_regions_layer)
        # x, y = random_points_in_bounds(polygon)

    m = folium.Map(location=[0, 0], zoom_start=2)

    # Add all feature layers to the map
    tdwg_layer.add_to(m)
    eco_regions_layer.add_to(m)

    # Add the toggle option for layers
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def find_eco_regions_for_flow_species(flow_df, eco_regions_df):
    flow_df = flow_df.drop_duplicates()
    if (flow_df.size > 0):
        geometry = [Point(xy) for xy in zip(
            flow_df['longitude'], flow_df['latitude'])]
        flow_occ_df = gpd.GeoDataFrame(flow_df,  # specify our data
                                       geometry=geometry, crs=eco_regions_df.crs)  # specify the geometry list we create
    # Trouver les éco-régions auxquelles appartiennent les occurrences (avec leurs coordonnées GPS)
        pointsInEcoregions = gpd.sjoin(
            flow_occ_df, eco_regions_df, predicate="within", how='left')
        pointsInEcoregions['species'] = pointsInEcoregions['species'].fillna(
            'Unknown species')
        pointsInEcoregions['genus'] = pointsInEcoregions['genus'].fillna(
            'Unknown genus')
        pointsInEcoregions['ECO_NAME'] = pointsInEcoregions['ECO_NAME'].fillna(
            'Eco-region not identified')
        pointsInEcoregions['ECO_ID'] = pointsInEcoregions['ECO_ID'].fillna(0)
        df = pointsInEcoregions[['ECO_NAME', 'ECO_ID']].merge(
            eco_regions_df[['ECO_ID', 'geometry']], on='ECO_ID', how='left')
        return pointsInEcoregions, df
