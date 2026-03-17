"""
app.py
Autenticação nativa Streamlit via Google OIDC (st.login / st.user).
"""
import streamlit as st
from utils.style import inject_css

st.set_page_config(
    page_title="Controle de Budget",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

DEV_MODE = st.secrets.get("app_config", {}).get("dev_mode", False)


def check_allowed(email: str) -> bool:
    allowed = st.secrets.get("app_config", {}).get("allowed_emails", [])
    return email in allowed


if not DEV_MODE and not st.user.is_logged_in:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            """
            <div style="text-align:center; padding: 60px 0 32px 0;">
              <h1 style="font-size:2.4rem; margin-bottom:4px;">
                Controle de <span>Budget</span>
              </h1>
              <p style="color:#a0a0a0; font-size:1rem; margin-top:0;">
                Gestão de Orçamento por Centro de Custo
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🔐  Entrar com Google", use_container_width=True):
            st.login()
    st.stop()

user_email = "dev@local" if DEV_MODE else st.user.email
user_name  = "Dev Local"  if DEV_MODE else getattr(st.user, "name", user_email)

if not DEV_MODE and not check_allowed(user_email):
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.error(
            f"❌ O e-mail **{user_email}** não tem permissão de acesso.\n\n"
            "Entre em contato com o administrador."
        )
        if st.button("↩️  Sair", use_container_width=True):
            st.logout()
    st.stop()

with st.sidebar:
    st.markdown(
        f"<p style='color:#a0a0a0; font-size:0.82rem; margin-bottom:2px;'>👤 {user_name}</p>"
        f"<p style='color:#4c4c4c; font-size:0.75rem; margin-bottom:16px;'>{user_email}</p>",
        unsafe_allow_html=True,
    )
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.logout()

st.markdown(
    """
    <div style="text-align:center; padding: 80px 0;">
      <h1>Controle de <span>Budget</span></h1>
      <p style="color:#a0a0a0; font-size:1.1rem; margin-top:8px;">
        Selecione um centro de custo no menu lateral.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
