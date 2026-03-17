"""
pages/0_Diagnostico.py
Página de diagnóstico — visível apenas em dev_mode.
Mostra arquivos no Drive, amostra de dados e resultado do join 190b × de_para.
"""
import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Diagnóstico", page_icon="🔧", layout="wide")

DEV_MODE = st.secrets.get("app_config", {}).get("dev_mode", False)
if not DEV_MODE:
    st.error("Esta página só está disponível em dev_mode.")
    st.stop()

st.session_state["_page_key"] = "diagnostico"
from utils.style import inject_css
from utils.data import (
    _list_drive_folder, _download_sheet_csv, _download_sheet,
    _find_in_folder, load_190b, load_depara, get_all_projecoes_files,
    _parse_projecoes, _SHEET_MIME,
)
inject_css()

st.markdown("<h1>🔧 <span>Diagnóstico</span></h1>", unsafe_allow_html=True)

# ── 1. Arquivos no Drive ───────────────────────────────────────────────
st.subheader("1. Arquivos na pasta do Drive")
files = _list_drive_folder()
if files:
    df_files = pd.DataFrame(files)[["name", "mimeType", "id"]]
    st.dataframe(df_files, hide_index=True, use_container_width=True)
else:
    st.error("Nenhum arquivo encontrado na pasta do Drive.")

st.divider()

# ── 2. Amostra do despesas_liquidadas (190b) ──────────────────────────
st.subheader("2. Amostra — despesas_liquidadas (CSV bruto)")
import csv as _csv

sheet_id = _find_in_folder(r"despesas_liquidadas.*", mime=_SHEET_MIME)
if sheet_id:
    content = _download_sheet_csv(sheet_id)
    reader  = _csv.reader(io.StringIO(content))
    rows_raw = []
    for i, row in enumerate(reader):
        rows_raw.append(row)
        if i >= 4:
            break

    st.write(f"**Total de colunas na linha 0:** {len(rows_raw[0])}")
    st.write(f"**Linhas de amostra:**")
    for i, row in enumerate(rows_raw):
        st.code(f"[{i}] len={len(row)}: {row[:20]}")

    # Detecta CSV-in-CSV
    is_cic = len(rows_raw[0]) == 1 and "," in rows_raw[0][0]
    st.info(f"Formato CSV-in-CSV detectado: **{is_cic}**")

    if is_cic:
        st.write("**Linha 1 decodificada (inner CSV):**")
        if len(rows_raw) > 1:
            inner = next(_csv.reader([rows_raw[1][0]]))
            for j, v in enumerate(inner[:20]):
                st.text(f"  col[{j:02d}] = {repr(v)}")
else:
    st.error("Arquivo despesas_liquidadas não encontrado.")

st.divider()

# ── 3. Amostra do 190b processado ─────────────────────────────────────
st.subheader("3. Amostra — load_190b() processado")
with st.spinner("Carregando 190b..."):
    df190 = load_190b()

if df190.empty:
    st.warning("load_190b() retornou DataFrame vazio.")
else:
    st.write(f"Total de linhas: **{len(df190)}**")
    st.write(f"Cod_natureza únicos: **{df190['cod_natureza'].nunique()}**")
    st.write(f"Centros únicos: **{df190['centro_custo'].nunique()}**")
    st.dataframe(df190.head(20), hide_index=True, use_container_width=True)
    st.write("**Cod_natureza sample:**")
    st.write(df190["cod_natureza"].value_counts().head(20))

st.divider()

# ── 4. De-Para (diagnóstico profundo) ────────────────────────────────
st.subheader("4. De-Para — conteúdo bruto")

depara_id = _find_in_folder("de_para", mime=_SHEET_MIME)
if not depara_id:
    st.error("Arquivo de_para não encontrado na pasta do Drive.")
else:
    # 4a. CSV export — mostra células como texto puro
    st.write("**4a. CSV export (primeiras 6 linhas, colunas brutas):**")
    csv_content = _download_sheet_csv(depara_id)
    import csv as _csv2
    rows_dp = []
    for row in _csv2.reader(io.StringIO(csv_content)):
        rows_dp.append(row)
        if len(rows_dp) >= 6:
            break
    for i, row in enumerate(rows_dp):
        st.code(f"[{i}] len={len(row)}: {row}")

    # 4b. XLSX export — mostra como pandas lê cada coluna
    st.write("**4b. XLSX export (pd.read_excel, header=None, dtype=str) — primeiras 6 linhas:**")
    raw_dp = pd.read_excel(io.BytesIO(_download_sheet(depara_id)), header=None, dtype=str)
    st.write(f"Colunas detectadas: {list(raw_dp.columns)} | Shape: {raw_dp.shape}")
    st.dataframe(raw_dp.head(6), use_container_width=True)

    # 4c. Resultado atual do load_depara
    st.write("**4c. load_depara() atual:**")
    dp = load_depara()
    if dp.empty:
        st.error("load_depara() retornou vazio.")
    else:
        st.write(f"Total: {len(dp)}")
        st.dataframe(dp.head(10), hide_index=True, use_container_width=True)

st.divider()

# ── 5. Join 190b × de_para ────────────────────────────────────────────
st.subheader("5. Resultado do join 190b × de_para")
if not df190.empty and not dp.empty:
    merged = df190.merge(dp, on="cod_natureza", how="left")
    merged["classificacao"] = merged["classificacao"].fillna("NÃO MAPEADO")
    st.write(f"Linhas sem mapeamento: **{(merged['classificacao'] == 'NÃO MAPEADO').sum()}** / {len(merged)}")
    st.write("**Por classificação:**")
    st.write(merged["classificacao"].value_counts())

    # Códigos sem mapeamento
    sem_map = merged[merged["classificacao"] == "NÃO MAPEADO"]["cod_natureza"].value_counts().head(20)
    if not sem_map.empty:
        st.warning("Códigos sem mapeamento:")
        st.write(sem_map)

st.divider()

# ── 6. Arquivos de projeção ───────────────────────────────────────────
st.subheader("6. Arquivos de projeção encontrados")
proj_files = get_all_projecoes_files()
if proj_files:
    for dt, fid in proj_files:
        st.write(f"- {dt.strftime('%d/%m/%Y')} → `{fid}`")
        df_p = _parse_projecoes(fid)
        if df_p.empty:
            st.error(f"  ⚠️ _parse_projecoes retornou vazio para {dt}")
        else:
            meses = sorted(df_p["mes"].unique())
            centros_p = df_p["centro_custo"].nunique()
            st.write(f"  Linhas: {len(df_p)} | Centros: {centros_p} | Meses: {[str(m)[:7] for m in meses]}")
else:
    st.error("Nenhum arquivo de projeção encontrado (padrão: projecoes_DD_MM_YYYY).")
