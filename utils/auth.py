"""
utils/auth.py
Autenticação por senha por página com suporte a senha mestra.
"""
import streamlit as st


def check_page_password(page_key: str, page_label: str = "este centro de custo") -> bool:
    """
    Verifica autenticação da página na sessão atual.
    Aceita senha específica da página OU senha mestra.
    Retorna True se autenticado, False se não.
    """
    session_key = f"page_auth_{page_key}"

    if st.secrets.get("app_config", {}).get("dev_mode", False):
        return True

    if st.session_state.get(session_key):
        return True

    correct = st.secrets.get("page_passwords", {}).get(page_key, "")
    master  = st.secrets.get("page_passwords", {}).get("master", "")

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 40px 0 24px 0;">
              <p style="color:#a0a0a0; font-size:1rem;">
                🔒 Acesso restrito — <strong>{page_label}</strong>
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        pwd = st.text_input(
            "Senha:", type="password",
            key=f"pwd_input_{page_key}",
            placeholder="Digite a senha do centro de custo ou a senha mestra",
        )
        if st.button("Entrar", use_container_width=True, key=f"pwd_btn_{page_key}"):
            if pwd and (pwd == correct or (master and pwd == master)):
                st.session_state[session_key] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")

    return False
