"""
utils/auth.py
Autenticação por senha por página com suporte a senha mestra.
A autenticação é persistida em cookie do navegador por 30 dias.
"""
import streamlit as st
from streamlit_cookies_controller import CookieController

_COOKIE_TTL_DAYS = 30
_controller = None


def _get_controller():
    global _controller
    if _controller is None:
        _controller = CookieController()
    return _controller


def check_page_password(page_key: str, page_label: str = "este centro de custo") -> bool:
    """
    Verifica autenticação da página.
    Aceita senha específica da página OU senha mestra.
    Persiste autenticação em cookie por 30 dias.
    Retorna True se autenticado, False caso contrário.
    """
    if st.secrets.get("app_config", {}).get("dev_mode", False):
        return True

    session_key = f"page_auth_{page_key}"
    cookie_key  = f"budget_auth_{page_key}"

    # 1. Já autenticado nesta sessão
    if st.session_state.get(session_key):
        return True

    # 2. Cookie válido do navegador
    try:
        controller = _get_controller()
        cookie_val = controller.get(cookie_key)
        if cookie_val == "ok":
            st.session_state[session_key] = True
            return True
    except Exception:
        pass

    # 3. Formulário de senha
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
                try:
                    controller = _get_controller()
                    controller.set(
                        cookie_key, "ok",
                        max_age=_COOKIE_TTL_DAYS * 86400,
                    )
                except Exception:
                    pass
                st.rerun()
            else:
                st.error("Senha incorreta.")

    return False
