"""
utils/auth.py
Controle de acesso por e-mail por página.
Masters acessam tudo; cada página tem sua lista de e-mails permitidos.
"""
import streamlit as st


def check_page_access(page_key: str, page_label: str = "este centro de custo") -> bool:
    """
    Verifica se o usuário logado tem acesso à página.
    - Masters (listados em [page_access].master) acessam todas as páginas.
    - Demais usuários precisam estar na lista da página específica.
    Retorna True se autorizado, False caso contrário (e exibe mensagem de erro).
    """
    if st.secrets.get("app_config", {}).get("dev_mode", False):
        return True

    email = getattr(st.user, "email", None) or ""

    page_access = st.secrets.get("page_access", {})
    masters     = [e.lower() for e in page_access.get("master", [])]
    allowed     = [e.lower() for e in page_access.get(page_key, [])]

    email_lower = email.lower()

    if email_lower in masters:
        return True

    if email_lower in allowed:
        return True

    # Sem acesso
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.error(
            f"❌ **{email}** não tem permissão para acessar **{page_label}**.\n\n"
            "Entre em contato com o administrador para solicitar acesso."
        )
    return False
