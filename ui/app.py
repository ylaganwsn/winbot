import os

import requests
import streamlit as st

API_URL = os.environ.get("WINBOT_API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Winbot", layout="wide")
st.title("Winbot")

try:
    requests.get(f"{API_URL}/health", timeout=5).raise_for_status()
    st.success("Connected to the Winbot API.")
except requests.RequestException:
    st.error(f"Cannot reach the Winbot API at {API_URL}.")