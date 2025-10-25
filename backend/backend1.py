# BACKEND 2 - DATA and API's
# -------------------------------------------------------------------------

"""
This module handles connection to API's
Yelp for venues
Skiddle for events
Open Meteo for weather

cleans and will normalise all the external data into a single JSON format

prepares a fallback local dataset (seed.json) with around 50 venues/events in Glasgow, as a precautionary measure incase API fails

adds caching so repeated queries do not trigger repeated API calls

"""
