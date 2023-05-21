from shapely.geometry import Polygon, Point
from shapely import centroid
from pygbif import occurrences
from pygbif import species
import folium
from folium import Popup
import branca.colormap as cm
import pandas as pd
import geopandas as gpd
import numpy as np

# Fonction de recherche à partir d'un nom d'espèce ou de genre
# rank = species ou genus ou family

def search_gbif_from_name_and_rank(searched_name, rank):
    print(searched_name)
    name_backbone = species.name_backbone(searched_name, rank=rank, verbose=True) 
    rank_key = rank+"Key"
    if rank_key in name_backbone :
        key_number = name_backbone[rank_key]
        if rank_key == 'speciesKey' :
            results = occurrences.search(speciesKey = key_number, hasCoordinate=True)
        if rank_key == 'familyKey' :
            results = occurrences.search(familyKey = key_number, hasCoordinate=True)
        if rank_key == 'genusKey' :
            results = occurrences.search(genusKey = key_number, hasCoordinate=True)  
        return name_backbone, results
    else : 
        return name_backbone, "Not Found"


def build_geo_df(dict_results, features_to_keep, crs):
    # build empty dataframe
    if (dict_results == 'Not Found') : 
         return pd.DataFrame()
    else : 
        df_results = pd.DataFrame(dict_results['results'])
        if df_results.size == 0 :
             return pd.DataFrame()
        else :
             # Toutes les colonnes ne sont pas présentes à chaque fois...
            df_results = df_results.reindex(columns=features_to_keep)
            partial_data_df = df_results[features_to_keep]
             # Suppression des duplicats
            partial_data_df = partial_data_df.set_index('key').drop_duplicates()
             # Suppression des coordonnées à (0,0)
            partial_data_df = partial_data_df[(partial_data_df['decimalLongitude'] != 0)  
                                               &  (partial_data_df['decimalLatitude']!= 0)]
             # Extraire la liste et rajouter une colonne nommée geometry avec les Point pour chaque occurrence
            #  'decimalLongitude', 'decimalLatitude'
            geometry = [Point(xy) for xy in zip(partial_data_df['decimalLongitude'], partial_data_df['decimalLatitude'])]
            geo_occ_df = gpd.GeoDataFrame(partial_data_df, #specify our data
                        geometry=geometry, crs=crs) #specify the geometry list we create
            return geo_occ_df
                    
def find_eco_regions(geo_occ_df, eco_regions_df):
    geo_occ_df = geo_occ_df.drop_duplicates()
    if (geo_occ_df.size > 0) :
    # Trouver les éco-régions auxquelles appartiennent les occurrences (avec leurs coordonnées GPS)
        pointsInEcoregions = gpd.sjoin(geo_occ_df, eco_regions_df, predicate="within", how='left')
        pointsInEcoregions['species'] = pointsInEcoregions['species'].fillna('Unknown species')
        pointsInEcoregions['genus'] = pointsInEcoregions['genus'].fillna('Unknown genus')
        pointsInEcoregions['ECO_NAME'] = pointsInEcoregions['ECO_NAME'].fillna('Eco-region not identified')
        pointsInEcoregions['ECO_ID'] = pointsInEcoregions['ECO_ID'].fillna(0)
        df = pointsInEcoregions[['ECO_NAME', 'ECO_ID']].merge(eco_regions_df[['ECO_ID','geometry']], on='ECO_ID', how='left')
        return df

def find_eco_regions_for_flow_species(flow_df, eco_regions_df):
    flow_df = flow_df.drop_duplicates()
    if (flow_df.size > 0) :
        geometry = [Point(xy) for xy in zip(flow_df['longitude'], flow_df['latitude'])]
        flow_occ_df = gpd.GeoDataFrame(flow_df, #specify our data
                        geometry=geometry, crs=eco_regions_df.crs) #specify the geometry list we create
    # Trouver les éco-régions auxquelles appartiennent les occurrences (avec leurs coordonnées GPS)
        pointsInEcoregions = gpd.sjoin( flow_occ_df, eco_regions_df, predicate="within", how='left')
        pointsInEcoregions['species'] = pointsInEcoregions['species'].fillna('Unknown species')
        pointsInEcoregions['genus'] = pointsInEcoregions['genus'].fillna('Unknown genus')
        pointsInEcoregions['ECO_NAME'] = pointsInEcoregions['ECO_NAME'].fillna('Eco-region not identified')
        pointsInEcoregions['ECO_ID'] = pointsInEcoregions['ECO_ID'].fillna(0)
        df = pointsInEcoregions[['ECO_NAME', 'ECO_ID']].merge(eco_regions_df[['ECO_ID','geometry']], on='ECO_ID', how='left')
        return pointsInEcoregions, df

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

def get_centroid(points):  
    # Extract (latitude, longitude) tuples from dataframe
    lat_lon_list = list(zip(points['decimalLatitude'].tolist(), points['decimalLongitude'].tolist()))
    if len(lat_lon_list) == 1 :
        return lat_lon_list[0]
    if len(lat_lon_list) == 2 :
        return get_center_coordinate(lat_lon_list)
    if len(lat_lon_list) == 3 :
        return get_triangle_center(lat_lon_list)   
    else : 
        poly = Polygon(lat_lon_list)
        print(centroid(poly))
        return centroid(poly).y, centroid(poly).x


def create_map_eco_regions(df, geo_occ_df):
    # Adapter le code pour le cas où on a des milliers d'occurrences...

    # Calculer le centroïde des points pour centrer la carte d'emblée 
    lat,long =  get_centroid(geo_occ_df)
    min_year = geo_occ_df['year'].min()
    max_year = geo_occ_df['year'].max()
    map = folium.Map(location=[lat, long], zoom_start=4)

    style_function = lambda x: {'fillColor': '#ffffff', 
                            'color':'#000000', 
                            'fillOpacity': 1, 
                            'weight': 1}
    highlight_function = lambda x: {'fillColor': '#000000', 
                                'color':'#000000', 
                                'fillOpacity': 0.50, 
                                'weight': 0.1}
    # Add a GeoJson layer with the polygons : list of eco-regions['ECO_NAME','geometry']

    colormap = cm.LinearColormap(colors=['red','yellow','green'],
                               vmin=min_year, vmax=max_year)
    for row in df.itertuples():
           if row.geometry != None :
             folium.GeoJson(row.geometry, name= row.ECO_NAME,
                          style_function=style_function, 
                          highlight_function=highlight_function, 
                          popup=Popup(row.ECO_NAME)).add_to(map)
           
    for row in geo_occ_df.itertuples(index=False):
        if (row.year != np.nan) : 
            #print(row)
    # Add a Marker layer with the points
            folium.Circle(radius=200,
                 location=(row.decimalLatitude,row.decimalLongitude),
                 popup=Popup(row.species + " " + str(row.year) + " " + row.country),
                 color = colormap(row.year),
                 legend_name='year',
                 fill=True).add_to(map)
            
        else :
             folium.Circle(radius=200,
             location=(row.decimalLatitude,row.decimalLongitude),
             popup=Popup(row.species),
             color = 'blue',
             fill=True).add_to(map)
             
    colormap.caption = 'Year of occurrence'
    colormap.add_to(map)
    return map
