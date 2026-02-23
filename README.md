# London Surface Area Web App - Hackathon

This is a web app developed during a one day hackathon organised by UCLSU and the social enterprise Homefolk. The app allows users to input a postcode in London, and returns the breakdown of paved, non-paved and building footprint surface area breakdown in the neighbourhood around the postcode. It is currently still at a prototype stage. Ultimately, it aims to support Homefolk's vision in identifying opportunity areas for infill tiny housing.

Other contributors
- Fiona Pacolli
- Alicia Grassby
- Ziyi Lin

[View the app](https://london-surface-area.streamlit.app/)

Caveat: The app currently suffers from easily exceeding usage limits of Streamlit because of loading an entire buildings geoparaquet file for Greater London from OSM. The code in accessing this spatial layer will have to be modified later.
