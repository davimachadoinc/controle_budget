"""pages/3_CX.py"""
import streamlit as st

st.set_page_config(page_title="Customer Experience | Budget", page_icon="💰", layout="wide")

if not st.secrets.get("app_config", {}).get("dev_mode", False) and not st.user.is_logged_in:
    st.error("⛔ Acesso nao autorizado. Faca login na pagina inicial.")
    st.stop()

st.session_state["_page_key"] = "cx"

from utils.style import inject_css
from utils.auth import check_page_access
from utils.page_template import render_page

inject_css()

if not check_page_access("cx", "Customer Experience"):
    st.stop()

render_page("cx")
