import random

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from folium import Popup
from pygbif import occurrences, species
from shapely import centroid
from shapely.geometry import Point, Polygon

# Fonction de recherche à partir d'un nom d'espèce ou de genre
# rank = species ou genus ou family


def search_gbif_from_name_and_rank(searched_name, rank):
    print(searched_name)
    name_backbone = species.name_backbone(
        searched_name, rank=rank, verbose=True)
    rank_key = rank+"Key"
    if rank_key in name_backbone:
        key_number = name_backbone[rank_key]
        if rank_key == 'speciesKey':
            results = occurrences.search(
                speciesKey=key_number, hasCoordinate=True)
        if rank_key == 'familyKey':
            results = occurrences.search(
                familyKey=key_number, hasCoordinate=True)
        if rank_key == 'genusKey':
            results = occurrences.search(
                genusKey=key_number, hasCoordinate=True)
        return name_backbone, results
    else:
        return name_backbone, "Not Found"


def build_geo_df(dict_results, features_to_keep, crs):
    # build empty dataframe
    if (dict_results == 'Not Found'):
        return pd.DataFrame()
    else:
        df_results = pd.DataFrame(dict_results['results'])
        if df_results.size == 0:
            return pd.DataFrame()
        else:
            # Toutes les colonnes ne sont pas présentes à chaque fois...
            df_results = df_results.reindex(columns=features_to_keep)
            partial_data_df = df_results[features_to_keep]
            partial_data_df = partial_data_df.drop_duplicates()

            # Suppression des coordonnées à (0,0)
            partial_data_df = partial_data_df[(partial_data_df['decimalLongitude'] != 0)
                                              & (partial_data_df['decimalLatitude'] != 0)]
            # Extraire la liste et rajouter une colonne nommée geometry avec les Point pour chaque occurrence
            #  'decimalLongitude', 'decimalLatitude'
            geometry = [Point(xy) for xy in zip(
                partial_data_df['decimalLongitude'], partial_data_df['decimalLatitude'])]
            geo_occ_df = gpd.GeoDataFrame(partial_data_df,  # specify our data
                                          geometry=geometry, crs=crs)  # specify the geometry list we create
            return geo_occ_df


def find_eco_regions(geo_occ_df, eco_regions_df):
    geo_occ_df = geo_occ_df.drop_duplicates()
    if (geo_occ_df.size > 0):
        # Trouver les éco-régions auxquelles appartiennent les occurrences (avec leurs coordonnées GPS)
        # Overlaps ?
        pointsInEcoregions = gpd.sjoin(
            geo_occ_df, eco_regions_df, predicate="within", how='left')
        pointsInEcoregions['species'] = pointsInEcoregions['species'].fillna(
            'Unknown species')
        pointsInEcoregions['genus'] = pointsInEcoregions['genus'].fillna(
            'Unknown genus')
        pointsInEcoregions['ECO_NAME'] = pointsInEcoregions['ECO_NAME'].fillna(
            'Eco-region not identified')
        pointsInEcoregions['ECO_ID'] = pointsInEcoregions['ECO_ID'].fillna(0)
        df = pointsInEcoregions.drop(columns='geometry').merge(
            eco_regions_df[['ECO_ID', 'geometry']], on='ECO_ID', how='left')
        return df

# ISO_Code	Level_4_Na	Level4_cod	Level4_2	Level3_cod	Level2_cod	Level1_cod	geometry


def find_phyto_regions(geo_occ_df, tdwg_level4):
    geo_occ_df = geo_occ_df.drop_duplicates()
    if (geo_occ_df.size > 0):
        # Trouver les zones tdwg auxquelles appartiennent les occurrences (avec leurs coordonnées GPS)
        # Peut-être un problème avec les multipolygones... (c'est sûr même)
        exploded = tdwg_level4.explode(index_parts=False)
        pointsInTDWG = gpd.sjoin(geo_occ_df, exploded,
                                 predicate="within", how='left')
        pointsInTDWG['species'] = pointsInTDWG['species'].fillna(
            'Unknown species')
        pointsInTDWG['genus'] = pointsInTDWG['genus'].fillna('Unknown genus')
        pointsInTDWG['Level_4_Na'] = pointsInTDWG['Level_4_Na'].fillna(
            'TDWG not identified')
        pointsInTDWG['Level4_cod'] = pointsInTDWG['Level4_cod'].fillna('None')
        df = pointsInTDWG.drop(columns='geometry').merge(
            exploded[['Level4_cod', 'geometry']], on='Level4_cod', how='left')
        return df


def build_heatmap(df1, df2):
    merged_df = pd.merge(
        df1, df2, on=['key', 'basisOfRecord']).drop_duplicates()

    heatmap_data = {}
    for basis_of_record in merged_df['basisOfRecord'].unique():
        print(basis_of_record)
        data = merged_df[merged_df['basisOfRecord'] == basis_of_record]
        pivot_table = data.pivot_table(
            index='ECO_NAME', columns='Level_4_Na', aggfunc='size', fill_value=0)
        heatmap_data[basis_of_record] = pivot_table

    return heatmap_data

# Ici les fonctions pour l'affichage des cartes


def get_center_coordinate(coordinates):

    # Calculate the average latitude and longitude of the two points
    latitude = (coordinates[0][0] + coordinates[1][0]) / 2
    longitude = (coordinates[0][1] + coordinates[1][1]) / 2

    return latitude, longitude


def get_triangle_center(vertices):

    # Calculate the average latitude and longitude of the vertices
    avg_latitude = sum(point[0] for point in vertices) / len(vertices)
    avg_longitude = sum(point[1] for point in vertices) / len(vertices)

    return avg_latitude, avg_longitude


def get_map_center(points):
    # Extract (latitude, longitude) tuples from dataframe
    lat_lon_list = list(
        zip(points['decimalLatitude'].tolist(), points['decimalLongitude'].tolist()))
    if len(lat_lon_list) == 1:
        return lat_lon_list[0]
    if len(lat_lon_list) == 2:
        return get_center_coordinate(lat_lon_list)
    if len(lat_lon_list) == 3:
        return get_triangle_center(lat_lon_list)
    else:
        # Return a random element
        random_center = random.choice(lat_lon_list)
        return random_center[1], random_center[0]

# Le mieux est de laisser l'année de côté pour le moment, et plutôt de compter les occurrences
# suivant le basisOfrecord une fois qu'on a les zones
def color_producer(basisOfrecord):
    if basisOfrecord == 'HUMAN_OBSERVATION':
        return 'green'
    elif basisOfrecord == 'OCCURRENCE':
        return 'blue'
    elif basisOfrecord == 'PRESERVED_SPECIMEN':
        return 'red'
    elif basisOfrecord == 'MATERIAL_SAMPLE':
        return 'black'
    else : 
        return 'gray'



def create_map_for_gbif_occurrences(tdwg_regions_gbif_found_df, eco_regions_found_df, geo_occ_df):

    tdwg_regions = tdwg_regions_gbif_found_df[['Level_4_Na','Level4_cod','geometry']]
   
    # centrer la carte d'emblée
    lat,long =  get_map_center(geo_occ_df)
    print(geo_occ_df['basisOfRecord'].unique())

    geo_occ_df['year'] = geo_occ_df['year'].fillna('year unknown')  # Année non documentée
    # lat,long =  get_map_center(geo_occ_df)
   # min_year = geo_occ_df['year'].min()
    #max_year = geo_occ_df['year'].max()
    map = folium.Map(location=[lat, long], zoom_start=4)
    #map = folium.Map(location=[0, 0], zoom_start=2)

    # Add a GeoJson layer with the polygons : list of eco-regions['ECO_NAME','geometry']

    #colormap = cm.LinearColormap(colors=['red', 'yellow', 'green'],
    #                             vmin=min_year, vmax=max_year)
    #colormap_records = cm.StepColormap
  
    #  Occurrences 
     
    for row in geo_occ_df.itertuples(index=False):
    
        folium.Circle(radius=200,
                    location=(row.decimalLatitude, row.decimalLongitude),
                    popup=Popup(row.species + " "+row.country + " " + row.basisOfRecord + " "+ str(row.year)),
                    color= color_producer(row.basisOfRecord),
                    fill=True).add_to(map)


     # TDWG 
    tdwg_layer = folium.FeatureGroup(name='TDWG regions', show=False) 
    eco_regions_layer = folium.FeatureGroup(name='WWF eco-regions', show=False)
    # Plot tdwg
   
    for i,row in tdwg_regions.iterrows():
        print(row)
     
        tdwg_geo = folium.GeoJson(row.geometry,
                                  style_function=lambda x: {'fillColor': '#99adc2',
                                                            'color': '#000000',
                                                            'fillOpacity': 0.5,
                                                            'weight': 1},
                                  highlight_function=lambda x: {'fillColor': '#ececec',
                                                                'color': '#000000',
                                                                'fillOpacity': 0.50,
                                                                'weight': 0.1}
                              
                                  )
    # Add popup with line description
        Popup(row.Level_4_Na).add_to(tdwg_geo)

        # Add the feature to the appropriate layer
        tdwg_geo.add_to(tdwg_layer)
        
    for row in eco_regions_found_df.itertuples():
        if row.geometry != None:
            eco_geo = folium.GeoJson(row.geometry, 
                           name=row.ECO_NAME,
                           style_function=lambda x: {'fillColor': '#17a86c',
                                                    'color': '#000000',
                                                    'fillOpacity': 0.5,
                                                    'weight': 1},
                            highlight_function=lambda x: {'fillColor': '#ececec',
                                                        'color': '#000000',
                                                        'fillOpacity': 0.50,
                                                        'weight': 0.1}
                                                        )
            Popup(row.ECO_NAME).add_to(eco_geo)

            eco_geo.add_to(eco_regions_layer)
  
    tdwg_layer.add_to(map)
    eco_regions_layer.add_to(map)
    folium.LayerControl(collapsed=False).add_to(map)
    return map
