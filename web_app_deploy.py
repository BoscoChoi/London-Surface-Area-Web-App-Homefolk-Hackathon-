"""
LONDON OUTPUT AREA SURFACE ANALYSIS
------------------------------------
Postcode → Output Area → Surface Breakdown + Opportunity Mapping

Priority Order:
1. Buildings
2. Car Park
3. Greenspace
4. Remaining = Opportunity (likely paved)

All data loaded from /data folder
"""

# =====================================================
# IMPORT LIBRARIES
# =====================================================

import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
from shapely.ops import unary_union
from shapely.geometry import GeometryCollection
import requests
from io import BytesIO
import gc


# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(page_title="London Surface Opportunity Tool", layout="wide")
st.title("London Surface Opportunity Tool")
st.write("Identify potential infill opportunity areas within Output Areas.")


# =====================================================
# USER INPUT
# =====================================================

postcode_input = st.text_input("Enter London Postcode").upper().strip()
postcode_input = postcode_input.replace(" ", "")


# =====================================================
# MAIN LOGIC
# =====================================================

if postcode_input:

    # =====================================================
    # LOAD DATA (CACHED FOR PERFORMANCE)
    # =====================================================

    # @st.cache_data
    def load_postcode_lookup():
        df = pd.read_csv(
            "https://raw.githubusercontent.com/BoscoChoi/London-Surface-Area-Web-App-Homefolk-Hackathon-/main/data/london_postcode_to_oa21_2025.csv"
        )
        df["pcds"] = df["pcds"].str.upper().str.strip()
        df["pcds"] = df["pcds"].str.replace(" ", "")
        return df


    def load_parquet_from_url(url):
        response = requests.get(url)
        response.raise_for_status()
        return gpd.read_parquet(BytesIO(response.content))


    url = "https://raw.githubusercontent.com/BoscoChoi/London-Surface-Area-Web-App-Homefolk-Hackathon-/main/data/osm_buildings.parquet"


    # @st.cache_data
    def load_spatial_layers():
        oa = gpd.read_file(
            "https://raw.githubusercontent.com/BoscoChoi/London-Surface-Area-Web-App-Homefolk-Hackathon-/main/data/oa_2021_london.gpkg"
        )
        greenspace = gpd.read_file(
            "https://raw.githubusercontent.com/BoscoChoi/London-Surface-Area-Web-App-Homefolk-Hackathon-/main/data/OS_Greenspace_Ldn.gpkg"
        )
        buildings = load_parquet_from_url(url)
        carpark = gpd.read_file(
            "https://raw.githubusercontent.com/BoscoChoi/London-Surface-Area-Web-App-Homefolk-Hackathon-/main/data/osm_traffic.gpkg"
        )
        return oa, greenspace, buildings, carpark


    postcode_lookup = load_postcode_lookup()
    oa_layer, greenspace_layer, buildings_layer, carpark_layer = load_spatial_layers()

    # -----------------------------------------
    # STEP 1: POSTCODE → OA LOOKUP
    # -----------------------------------------
    match = postcode_lookup[postcode_lookup["pcds"] == postcode_input]

    if match.empty:
        st.error("Postcode not found.")
        st.stop()

    oa_code = match.iloc[0]["oa21"]
    st.success(f"Matched Output Area: {oa_code}")

    # -----------------------------------------
    # STEP 2: EXTRACT OA BOUNDARY
    # -----------------------------------------
    oa_boundary = oa_layer[oa_layer["OA21CD"] == oa_code]

    if oa_boundary.empty:
        st.error("Output Area geometry not found.")
        st.stop()

    # Reproject everything to metric CRS for area calculation
    oa_boundary = oa_boundary.to_crs(epsg=3857)
    greenspace_layer_metric = greenspace_layer.to_crs(epsg=3857)
    buildings_layer_metric = buildings_layer.to_crs(epsg=3857)
    carpark_layer_metric = carpark_layer.to_crs(epsg=3857)

    # -----------------------------------------
    # STEP 3: CLIP LAYERS TO OA
    # -----------------------------------------
    buildings = gpd.overlay(buildings_layer_metric, oa_boundary, how="intersection")
    carpark = gpd.overlay(carpark_layer_metric, oa_boundary, how="intersection")
    greenspace = gpd.overlay(greenspace_layer_metric, oa_boundary, how="intersection")

    # -----------------------------------------
    # STEP 4: APPLY PRIORITY RULES
    # -----------------------------------------

    building_union = unary_union(buildings.geometry) if not buildings.empty else GeometryCollection()

    # Remove building overlap from car park
    carpark["geometry"] = carpark.geometry.difference(building_union)
    carpark_union = unary_union(carpark.geometry) if not carpark.empty else GeometryCollection()

    # Remove building + car park overlap from greenspace
    combined_union = unary_union([building_union, carpark_union])
    greenspace["geometry"] = greenspace.geometry.difference(combined_union)
    greenspace_union = unary_union(greenspace.geometry) if not greenspace.empty else GeometryCollection()

    # -----------------------------------------
    # STEP 5: CALCULATE OPPORTUNITY AREA
    # -----------------------------------------

    classified_union = unary_union([
        building_union,
        carpark_union,
        greenspace_union
    ])

    opportunity_geom = oa_boundary.geometry.iloc[0].difference(classified_union)

    # -----------------------------------------
    # STEP 6: AREA CALCULATIONS
    # -----------------------------------------

    total_area = oa_boundary.geometry.area.iloc[0]

    building_area = building_union.area if not building_union.is_empty else 0
    carpark_area = carpark_union.area if not carpark_union.is_empty else 0
    greenspace_area = greenspace_union.area if not greenspace_union.is_empty else 0
    opportunity_area = opportunity_geom.area if not opportunity_geom.is_empty else 0

    building_pct = (building_area / total_area) * 100
    carpark_pct = (carpark_area / total_area) * 100
    greenspace_pct = (greenspace_area / total_area) * 100
    opportunity_pct = (opportunity_area / total_area) * 100

    # -----------------------------------------
    # STEP 7: DISPLAY RESULTS TABLE
    # -----------------------------------------

    st.subheader("Surface Breakdown")

    results_df = pd.DataFrame({
        "Surface Type": [
            "Buildings",
            "Car Park",
            "Greenspace",
            "Opportunity (Likely Paved)"
        ],
        "Area (m²)": [
            building_area,
            carpark_area,
            greenspace_area,
            opportunity_area
        ],
        "Percentage (%)": [
            building_pct,
            carpark_pct,
            greenspace_pct,
            opportunity_pct
        ]
    })

    # Optional: format numbers for readability
    results_df["Area (m²)"] = results_df["Area (m²)"].apply(lambda x: f"{x:,.0f}")
    results_df["Percentage (%)"] = results_df["Percentage (%)"].apply(lambda x: f"{x:.1f}%")

    st.dataframe(results_df)

    # -----------------------------------------
    # STEP 8: PREPARE MAP DISPLAY
    # -----------------------------------------

    def to_wgs84(geom):
        if geom.is_empty:
            return None
        return gpd.GeoSeries([geom], crs=3857).to_crs(epsg=4326).iloc[0]

    building_display = to_wgs84(building_union)
    carpark_display = to_wgs84(carpark_union)
    greenspace_display = to_wgs84(greenspace_union)
    opportunity_display = to_wgs84(opportunity_geom)
    oa_display = oa_boundary.to_crs(epsg=4326)

    layers = []

    # Buildings (Red)
    if building_display:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                gpd.GeoSeries([building_display]).__geo_interface__,
                filled=True,
                get_fill_color=[200, 0, 0, 180],
                pickable=True,
            )
        )

    # Car Park (Purple)
    if carpark_display:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                gpd.GeoSeries([carpark_display]).__geo_interface__,
                filled=True,
                get_fill_color=[150, 0, 200, 180],
                pickable=True,
            )
        )

    # Greenspace (Green)
    if greenspace_display:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                gpd.GeoSeries([greenspace_display]).__geo_interface__,
                filled=True,
                get_fill_color=[0, 180, 0, 180],
                pickable=True,
            )
        )

    # Opportunity (Blue)
    if opportunity_display:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                gpd.GeoSeries([opportunity_display]).__geo_interface__,
                filled=True,
                get_fill_color=[0, 100, 255, 160],
                pickable=True,
            )
        )

    # OA Boundary (Yellow Outline)
    layers.append(
        pdk.Layer(
            "GeoJsonLayer",
            oa_display.__geo_interface__,
            filled=False,
            stroked=True,
            get_line_color=[255, 215, 0],
            line_width_min_pixels=3,
        )
    )

    view_state = pdk.ViewState(
        latitude=oa_display.geometry.centroid.y.iloc[0],
        longitude=oa_display.geometry.centroid.x.iloc[0],
        zoom=15,
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
    )

    col1, col2 = st.columns([4, 1])

    with col1:
        st.subheader("Surface Classification Map")
        st.pydeck_chart(deck)

    # -----------------------------------------
    # STEP 9: LEGEND
    # -----------------------------------------

    legend_html = """
    <div style="display: flex; flex-direction: column; gap: 8px; font-size: 16px;">
      <div style="display: flex; align-items: center;">
        <div style="width: 20px; height: 20px; background-color: rgb(200,0,0); margin-right: 10px;"></div>
        Buildings
      </div>
      <div style="display: flex; align-items: center;">
        <div style="width: 20px; height: 20px; background-color: rgb(150,0,200); margin-right: 10px;"></div>
        Car Park
      </div>
      <div style="display: flex; align-items: center;">
        <div style="width: 20px; height: 20px; background-color: rgb(0,180,0); margin-right: 10px;"></div>
        Greenspace
      </div>
      <div style="display: flex; align-items: center;">
        <div style="width: 20px; height: 20px; background-color: rgb(0,100,255); margin-right: 10px;"></div>
        Opportunity (Likely Paved)
      </div>
      <div style="display: flex; align-items: center;">
        <div style="width: 20px; height: 20px; border: 3px solid rgb(255,215,0); margin-right: 10px;"></div>
        Output Area Boundary
      </div>
    </div>
    """

    with col2:
        st.subheader("Legend")
        st.markdown(legend_html, unsafe_allow_html=True)

    # =====================================================
    # step 10: clear memory between runs
    # =====================================================


    del oa_layer, buildings_layer, greenspace_layer, carpark_layer
    gc.collect()