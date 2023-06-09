# streamlit run [app name]

# Depuis une console :
# streamlit run cv.py

# Local URL: http://localhost:8501
# Network URL: http://192.168.0.89:8501


# Chargement des librairies

import pandas as pd
import geopandas as gpd 
from shapely import wkt
import streamlit as st
import gbif_functions as mf
import flow_functions as ff
from PIL import Image

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


# Chargement des éco-regions

path_to_eco_regions_csv = "data/eco-regions-simplified.csv" 
path_to_cixiidae_flow_csv = "data/cixiidae_flow.csv"
path_tdwg_maps = 'data/tdwg'

features_to_keep = ['key', 'basisOfRecord', 'individualCount', 'scientificName', 'acceptedScientificName', 'kingdom', 'phylum',
       'order', 'family', 'genus', 'species', 'genericName', 'specificEpithet',
       'taxonRank', 'taxonomicStatus', 'iucnRedListCategory','decimalLongitude', 'decimalLatitude', 
       'continent', 'stateProvince','year','countryCode',
       'country','coordinateUncertaintyInMeters', 'lifeStage',
       'occurrenceRemarks', 'identificationRemarks']


@st.cache_resource # 👈 Add the caching decorator
def load_eco_regions(path_to_eco_regions_csv):
    eco_regions_df = pd.read_csv(path_to_eco_regions_csv)
    eco_regions_df['geometry'] = eco_regions_df['geometry'].apply(wkt.loads)
    eco_regions_df = gpd.GeoDataFrame(eco_regions_df, crs='epsg:4326')
    return eco_regions_df


@st.cache_resource # 👈 Add the caching decorator
def load_tdwg_regions(path_tdwg_maps):
    '''with open(path_tdwg_maps+"\level1.geojson") as geojsonfile :
        tdwg_level1 = gpd.read_file(geojsonfile)
    with open(path_tdwg_maps+"\level2.geojson") as geojsonfile :
        tdwg_level2 = gpd.read_file(geojsonfile)
    with open(path_tdwg_maps+"\level3.geojson") as geojsonfile :
        tdwg_level3 = gpd.read_file(geojsonfile)'''
    with open(path_tdwg_maps+"/level4.geojson") as geojsonfile :
        tdwg_level4 = gpd.read_file(geojsonfile)
        tdwg_level4['Level4_cod'] = tdwg_level4['Level3_cod'] + tdwg_level4['Level4_2']
    return tdwg_level4

#@st.cache_resource # 👈 Add the caching decorator
def load_flow_data(path_to_cixiidae_flow_csv):
    flow_df = pd.read_csv(path_to_cixiidae_flow_csv,sep=';')
    # Attention, cette opération destinée au mapping tdwg provoque des doublons des occurences
   # flow_df_expanded =  flow_df.assign(tdwg=flow_df['tdwg'].str.split(',')).explode('tdwg').reset_index(drop=True)
    return flow_df

eco_regions_df = load_eco_regions(path_to_eco_regions_csv)
flow_df = load_flow_data(path_to_cixiidae_flow_csv)
twdg_level4_df = load_tdwg_regions(path_tdwg_maps)

list_genus = set(flow_df['genus'].values)

# Choix du genre
def panel_choix_genus():
    with st.container() :
        selected_genus = st.selectbox(label='Genre', options= list_genus, key='selected_genus')
        return selected_genus

def panel_choix_species(debug_mode,genus):
    list_species = set(flow_df[flow_df['genus'] == genus]['species'].values)
    rank = 'species'
    eco_regions_gbif_found_df = pd.DataFrame()
    tdwg_regions_gbif_found_df = pd.DataFrame()
    eco_regions_flow_found_df = pd.DataFrame()
    geo_occ_df = pd.DataFrame()
    flow_occ_df = pd.DataFrame()
    with st.container() :
        with st.form('species selection'):
            searched_name = st.selectbox(label='Espèce', options= list_species, key='searched_name')
            submitted = st.form_submit_button('Submit')
            if submitted :
                st.write('You selected:',  searched_name) 
                searched_name = 0 if st.session_state.searched_name == '0' else st.session_state.searched_name
                name_backbone, dict_results = mf.search_gbif_from_name_and_rank(searched_name,rank)
                # Construction du geodataframe avec les résultats de la requête au GBIF
                geo_occ_df = mf.build_geo_df(dict_results, features_to_keep, eco_regions_df.crs)
                # Pour flow, on va plutôt se focaliser sur les phyto regions (tdwg)
                flow_occ_df, eco_regions_flow_found_df = ff.find_eco_regions_for_flow_species(flow_df[flow_df['species']== searched_name], eco_regions_df)
                
                if (geo_occ_df.size == 0) :
                    body =  "No occurrence of " + searched_name + " with coordinates was found in the GBIF database"
                    st.warning(body, icon="😢")
                    print(flow_occ_df)
                else : 
                    # On cherche les eco-regions pour les occurrences GBIF
                    eco_regions_gbif_found_df = mf.find_eco_regions(geo_occ_df, eco_regions_df)
                    # On cherche maintenant les phyto-regions du TDWG
                    tdwg_regions_gbif_found_df = mf.find_phyto_regions(geo_occ_df, twdg_level4_df)
                if debug_mode :
                    st.markdown(name_backbone) 
        return eco_regions_flow_found_df, eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, geo_occ_df, flow_occ_df

def panel_gbif_comment(eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, geo_occ_df):
    eco_regions_found_data = eco_regions_gbif_found_df['ECO_NAME'].value_counts().reset_index(). \
                        rename(columns={'index': 'Name', 'ECO_NAME': 'Number of occurrences'})
    line1 = st.session_state.searched_name + " has been found "+ str(eco_regions_gbif_found_df.shape[0]) + " times in the GBIF database"
    line2 = f"They have been found in {len(eco_regions_found_data['Name'])} eco-regions "
    line3 = eco_regions_found_data['Name'].unique()
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
           st.markdown(line1)
           st.markdown(line2)
           st.markdown(line3)
    
        with col2:
             st.bar_chart(eco_regions_found_data, x = 'Name', y ='Number of occurrences', width=400, height=400, use_container_width= False)
    
    tdwg_regions_gbif_found_data = tdwg_regions_gbif_found_df['Level_4_Na'].value_counts().reset_index().\
                        rename(columns={'index': 'Name', 'Level_4_Na': 'Number of occurrences'})
    
    tdwg_line2 = f"They have been found in {len(tdwg_regions_gbif_found_data['Name'])} TDWG regions"
    tdwg_line3 = tdwg_regions_gbif_found_data['Name'].unique()
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
           st.markdown(tdwg_line2)
           st.markdown(tdwg_line3)
    
        with col2:
             st.bar_chart(tdwg_regions_gbif_found_data, x = 'Name', y ='Number of occurrences', width=400, height=400, use_container_width= False)


    return eco_regions_gbif_found_df,geo_occ_df, tdwg_regions_gbif_found_df


def panel_flow_comment(eco_regions_flow_found_df):
    eco_regions_flow_found_df = eco_regions_flow_found_df.drop_duplicates()
    eco_regions_found_data = eco_regions_flow_found_df['ECO_NAME'].value_counts().reset_index(). \
                        rename(columns={'index': 'Name', 'ECO_NAME': 'Number of occurrences'})
    line1 = st.session_state.searched_name + " has been found "+ str(eco_regions_flow_found_df.shape[0]) + " times in the FLOW database"
    line2 = f"They have been found in {len(eco_regions_found_data['Name'])} eco-regions "
    line3 = eco_regions_found_data['Name'].unique()

    with st.container():
        st.markdown("Dans la base FLOW")
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
        ["Where are they ?", "Chatbox"])
    with tab1:
        genus = panel_choix_genus()
        eco_regions_flow_found_df, eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, geo_occ_df,flow_occ_df = panel_choix_species(debug_mode,genus)
        if (eco_regions_gbif_found_df.size != 0) : 
            panel_gbif_comment(eco_regions_gbif_found_df, tdwg_regions_gbif_found_df, geo_occ_df)
            show_gbif_map(eco_regions_gbif_found_df, geo_occ_df)
        if (eco_regions_flow_found_df.size != 0): 
            panel_flow_comment(eco_regions_flow_found_df)

    with tab2:
        ### Ici 
        st.markdown('TBC')


def main():
    hc_sidebar()
    hc_header()
    hc_body()


# Run main()

if __name__ == '__main__':
    main()