# streamlit run [app name]

# Depuis une console :
# streamlit run cv.py

# Local URL: http://localhost:8501
# Network URL: http://192.168.0.89:8501


# Chargement des librairies

from streamlit.runtime.state import SessionState, session_state
import flow_functions as ff
import gbif_functions as mf
import geopandas as gpd
import pandas as pd
import streamlit as st
from PIL import Image
from shapely import wkt
import plotly.express as px

# Initial page config

st.set_page_config(
    page_title='GBIF',
    layout="wide",
    initial_sidebar_state="collapsed",
)

def local_css(file_name):
    with open(file_name) as f:
        st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)

#local_css("style.css")

# Initialisation de la variable de session searched_name

# Initialization
if 'genus' not in st.session_state:
    st.session_state['genus'] = 0

if 'species' not in st.session_state:
    st.session_state['species'] = 0

# Chargement des éco-regions

path_to_eco_regions_csv = "data/eco-regions-simplified.csv" 
path_to_cixiidae_flow_csv = "data/cixiidae_flow_countries_tdwg.csv"
path_tdwg_maps = 'data/tdwg'
path_data = 'data/'

# Les features GBIF qu'on va garder 
features_to_keep = ['key', 'basisOfRecord', 'individualCount', 'scientificName', 'acceptedScientificName', 'kingdom', 'phylum',
       'order', 'family', 'genus', 'species', 'genericName', 'specificEpithet',
       'taxonRank', 'taxonomicStatus', 'iucnRedListCategory','decimalLongitude', 'decimalLatitude', 
       'continent', 'stateProvince','year','countryCode',
       'country','coordinateUncertaintyInMeters', 'lifeStage',
       'occurrenceRemarks', 'identificationRemarks']

# Chargement des eco-regions

@st.cache_resource # 👈 Add the caching decorator
def load_eco_regions(path_to_eco_regions_csv):
    eco_regions_df = pd.read_csv(path_to_eco_regions_csv)
    eco_regions_df['geometry'] = eco_regions_df['geometry'].apply(wkt.loads)
    eco_regions_df = gpd.GeoDataFrame(eco_regions_df, crs='epsg:4326')
    return eco_regions_df

# Chargement des phyto-regions

@st.cache_resource # 👈 Add the caching decorator
def load_tdwg_regions(path_tdwg_maps):
    with open(path_tdwg_maps+"\level1.geojson") as geojsonfile :
        tdwg_level1 = gpd.read_file(geojsonfile)
    with open(path_tdwg_maps+"\level2.geojson") as geojsonfile :
        tdwg_level2 = gpd.read_file(geojsonfile)
    with open(path_tdwg_maps+"\level3.geojson") as geojsonfile :
        tdwg_level3 = gpd.read_file(geojsonfile)
    with open(path_tdwg_maps+"/level4.geojson") as geojsonfile :
        tdwg_level4 = gpd.read_file(geojsonfile)
        # Mise en forme du code pour qu'il soit comparable à celui utilisé dans Flow
        tdwg_level4['Level4_cod'] = tdwg_level4['Level3_cod'] + tdwg_level4['Level4_2']
    tdwg_data = dict()
    tdwg_data['tdwg_level1'] = tdwg_level1
    tdwg_data['tdwg_level2'] = tdwg_level2
    tdwg_data['tdwg_level3'] = tdwg_level3
    tdwg_data['tdwg_level4'] = tdwg_level4
    return tdwg_data

@st.cache_resource # 👈 Add the caching decorator
def load_mapping_tdwg_eco_regions(path_data):
    mapping_level4_df = pd.read_csv(path_data+"mapping_tdwg_level4_eco_regions.csv")
    mapping_level3_df = pd.read_csv(path_data+"mapping_tdwg_level3_eco_regions.csv")
    mapping_level2_df = pd.read_csv(path_data+"mapping_tdwg_level2_eco_regions.csv")
    mapping_data = dict()
    mapping_data['tdwg_level2'] = mapping_level2_df
    mapping_data['tdwg_level3'] = mapping_level3_df
    mapping_data['tdwg_level4'] = mapping_level4_df
    return mapping_data


#@st.cache_resource # 👈 Add the caching decorator
def load_flow_data(path_to_cixiidae_flow_csv):
    flow_df = pd.read_csv(path_to_cixiidae_flow_csv)
    df = ff.expand_and_clean_dataset(flow_df)
    return df

eco_regions_df = load_eco_regions(path_to_eco_regions_csv)
flow_df = load_flow_data(path_to_cixiidae_flow_csv)
tdwg_data = load_tdwg_regions(path_tdwg_maps)
mapping_data = load_mapping_tdwg_eco_regions(path_data)
list_genus = list(set(flow_df['genus'].values))

st.session_state['genus'] = 0
st.session_state['species'] = 0


# Choix du genre
def panel_choix_genus(key):
    with st.container() :
        if (st.session_state['genus'] == 0):
            selected_genus = st.selectbox(label='Genre', index=0, options= list_genus, key=key)
        else :
            idx = list_genus.index(st.session_state['genus'])
            selected_genus = st.selectbox(label='Genre', index=idx, options= list_genus, key=key)
        return selected_genus
    
# Choix de l'espèce pour les recherches GBIF
def panel_gbif_choix_species(debug_mode,genus,list_species):
    rank = 'species'
    eco_regions_gbif_found_df = pd.DataFrame()
    tdwg_regions_gbif_found_df = pd.DataFrame()
    gbif_occ_df = pd.DataFrame()
  
    with st.container() :
        with st.form('species gbif selection'):
            if (st.session_state['species'] != 0):
                idx = list_species.index(st.session_state['species'])
            else :
                idx = 0
            searched_gbif_name = st.selectbox(label='Espèce', index = idx,options= list_species, key='searched_gbif_name')
            submitted_gbif = st.form_submit_button("Let's have a look")
            if submitted_gbif :
                st.write('You selected:',  searched_gbif_name) 
                st.session_state['species'] = searched_gbif_name

                name_backbone, dict_results = mf.search_gbif_from_name_and_rank(searched_gbif_name,rank)
                # Construction du geodataframe avec les résultats de la requête au GBIF
                gbif_occ_df = mf.build_geo_df(dict_results, features_to_keep, eco_regions_df.crs)
   
                if (gbif_occ_df.size == 0) :
                    body =  "No occurrence of " + searched_gbif_name + " with coordinates was found in the GBIF database"
                    st.warning(body, icon="😢")
                else : 
                    if debug_mode :
                        st.markdown(set(gbif_occ_df['basisOfRecord']))
                    # On cherche les eco-regions pour les occurrences GBIF
                    eco_regions_gbif_found_df = mf.find_eco_regions(gbif_occ_df, eco_regions_df)
                      # On cherche maintenant les phyto-regions du TDWG level 4
                    tdwg_regions_gbif_found_df = mf.find_phyto_regions(gbif_occ_df, tdwg_data['tdwg_level4'])

                if debug_mode :
                    st.markdown(name_backbone) 
  
        return eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, gbif_occ_df


def panel_flow_choix_species(debug_mode,genus, list_species):
    #list_species = set(flow_df[flow_df['genus'] == genus]['species'].values)
    rank = 'species'
    tdwg_regions_flow=[]
    eco_regions_list=[]
    flow_occ_df = pd.DataFrame()
    with st.container() :
        with st.form('species flow selection'):
            if (st.session_state['species'] != 0):
                    idx = list_species.index(st.session_state['species'])
            else :
                idx = 0
            searched_flow_name = st.selectbox(label='Espèce', index = idx, options= list_species, key='searched_flow_name')
            submitted_flow = st.form_submit_button("Let's have a look")
            if submitted_flow :
                st.write('You selected:',  searched_flow_name) 
                     # Pour flow, on va plutôt se focaliser sur les phyto regions (tdwg)

                tdwg_regions_flow= ff.find_phyto_regions_for_flow_species(searched_flow_name, flow_df)
                st.markdown(tdwg_regions_flow)
                true_columns_dict, eco_regions_list = ff.get_level4_eco_id_list(mapping_data['tdwg_level4'], tdwg_regions_flow)
                liste = set(eco_regions_list)
                st.markdown(liste)
  
        return tdwg_regions_flow, eco_regions_list, flow_occ_df


def panel_gbif_comment(gbif_occ_df,eco_regions_gbif_found_df, tdwg_regions_gbif_found_df):

    heatmap_data = mf.build_heatmap(eco_regions_gbif_found_df[['key','basisOfRecord','ECO_NAME']],
                                    tdwg_regions_gbif_found_df[['key','basisOfRecord','Level_4_Na']])
   

    # On récupère les eco-régions
    eco_regions_found_data = eco_regions_gbif_found_df['ECO_NAME'].value_counts().reset_index(). \
                        rename(columns={'index': 'Name', 'ECO_NAME': 'Number of occurrences'})
    
    line1 = st.session_state['species'] + " has been found "+ str(len(gbif_occ_df)) + " times in the GBIF database"
   # line2 = f"They have been found in {len(eco_regions_found_data['Name'])} eco-region(s)"
   # line3 = eco_regions_found_data['Name'].unique()

    # On récupère le TDWG niveau 4
    tdwg_regions_gbif_found_data = tdwg_regions_gbif_found_df['Level_4_Na'].value_counts().reset_index().\
                        rename(columns={'index': 'Name', 'Level_4_Na': 'Number of occurrences'})
    
    #tdwg_line2 = f"They have been found in {len(tdwg_regions_gbif_found_data['Name'])} TDWG region(s)"
    #tdwg_line3 = tdwg_regions_gbif_found_data['Name'].unique()

    line2 = f"They have been found in {len(eco_regions_found_data['Name'])} eco-region(s) corresponding \
    to {len(tdwg_regions_gbif_found_data['Name'])} TDWG region(s)"

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(line1)
            st.markdown(line2)
      
        with col2:
            for basis_of_record in heatmap_data.keys():
                st.markdown(basis_of_record)
                st.table(heatmap_data[basis_of_record])

    return eco_regions_gbif_found_df,tdwg_regions_gbif_found_df


def panel_flow_comment(eco_regions_flow_found_df):
    eco_regions_flow_found_df = eco_regions_flow_found_df.drop_duplicates()
    eco_regions_found_data = eco_regions_flow_found_df['ECO_NAME'].value_counts().reset_index(). \
                        rename(columns={'index': 'Name', 'ECO_NAME': 'Number of occurrences'})
    line1 = st.session_state.searched_name + " has been found "+ str(eco_regions_flow_found_df.shape[0]) + " times in the FLOW database"
    line2 = f"They have been found in {len(eco_regions_found_data['Name'])} eco-regions "
    line3 = eco_regions_found_data['Name'].unique()

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
           st.markdown(line1)
           st.markdown(line2)
           st.markdown(line3)
    
        with col2:
             st.bar_chart(eco_regions_found_data, x = 'Name', y ='Number of occurrences', width=400, height=400, 
                          use_container_width= False)
    return eco_regions_flow_found_df


def show_gbif_map(eco_regions_found_df,geo_occ_df):
    map = mf.create_map_eco_regions(eco_regions_found_df,geo_occ_df)
    with st.container():
        map_html = map._repr_html_()
        st.components.v1.html(map_html, height=900, width=1000)


def show_flow_map(level4_cod_values, eco_id_list):
    map = ff.show_map(tdwg_data, eco_regions_df, level4_cod_values, eco_id_list)
    with st.container():
        map_html = map._repr_html_()
        st.components.v1.html(map_html, height=900, width=1000)


def hc_header():
    
    st.header('GBIF | Global Biodiversity Information Facility occurrences and WWF eco-regions')
    st.header('Animalia | Arthropoda | Insecta | Hemiptera | Cixiidae')
    #st.image()
    st.markdown('**Data For Good**')
    st.write('-----------------')

    #https://www.gbif.org/occurrence/map?has_coordinate=true&has_geospatial_issue=false&taxon_key=8470

    #GBIF.org (19 May 2023) GBIF Occurrence Download https://doi.org/10.15468/dl.86cbu4 

def hc_sidebar():
    st.sidebar.header('Cixiidae')
    image = Image.open('images/cixiidae.png')
    st.sidebar.image(image)
    st.sidebar.markdown('Data For Good')
    st.sidebar.markdown(
        '''Link to Streamlit doc :  https://docs.streamlit.io/''')
    
def hc_body():
    debug_mode = st.checkbox('debug mode')
    tab1, tab2 = st.tabs(
        ["Ask GBIF ", "Ask Flow"])
    with tab1:
     
        genus = panel_choix_genus('selected_gif_genus')
        st.session_state['genus'] = genus
        list_species = list(set(flow_df[flow_df['genus'] == genus]['species'].values))
        eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, geo_gbif_occ_df = \
            panel_gbif_choix_species(debug_mode,genus,list_species)
        if (eco_regions_gbif_found_df.size != 0) : 
            panel_gbif_comment(geo_gbif_occ_df, eco_regions_gbif_found_df, tdwg_regions_gbif_found_df)
            show_gbif_map(eco_regions_gbif_found_df, geo_gbif_occ_df)

    with tab2:
        ### Ici 
        genus = panel_choix_genus('selected_flow_genus')
        tdwg_regions_flow, eco_regions_list, flow_occ_df = panel_flow_choix_species(debug_mode,genus, list_species)
        if (len(tdwg_regions_flow)!=0):
            show_flow_map(tdwg_regions_flow, eco_regions_list)

       # if (eco_regions_flow_found_df.size != 0): 
        #    panel_flow_comment(eco_regions_flow_found_df)


def main():
    hc_sidebar()
    hc_header()
    hc_body()


# Run main()

if __name__ == '__main__':
    main()