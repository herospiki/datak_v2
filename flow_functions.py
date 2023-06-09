from shapely.geometry import Polygon, Point
import folium
from folium import Popup
import branca.colormap as cm
import pandas as pd
import geopandas as gpd
import numpy as np
import random

def clean_dataset(flow_df):
    flow_expanded_df =  flow_df.assign(flow_df['tdwg'].str.split(',')).explode('tdwg').reset_index(drop=True)
    flow_expanded_df['tdwg_level'] = flow_expanded_df['tdwg_level'].fillna(0)
    flow_expanded_df['tdwg'] = flow_expanded_df['tdwg'].fillna('Unknown')
    clean_data_df = flow_expanded_df
    return clean_data_df

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

def find_phyto_regions_for_flow_species(species, flow_expanded_df):
    df = flow_expanded_df[flow_expanded_df['species'] == species].drop_duplicates()
    # On cherche les tdwg et tdwg_level où il y a une présence
    if (df.size > 0) :
        new_df = df[df['species'] == species][['genus','short','species','autorite','tdwg_level','tdwg']].drop_duplicates()
        return 

