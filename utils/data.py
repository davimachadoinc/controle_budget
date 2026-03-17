"""
utils/data.py
Leitura de arquivos, mapeamento de grupos e helpers de KPI/gráficos.
Fonte de dados: pasta Google Drive (lida via service account em secrets.toml).
"""
import io
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from dateutil.relativedelta import relativedelta

# ID da pasta no Google Drive que contém todas as bases
_FOLDER_ID   = "1BSuJkp8wPxMwCXBxADuyoaNvy8VTJ-sh"
_XLSX_MIME   = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SHEET_MIME  = "application/vnd.google-apps.spreadsheet"
_NOTAS_FILE_ID_KEY = "notas_drive_file_id"   # salvo em session_state


# ─────────────────────────────────────────────
# CAMADA DE ACESSO AO GOOGLE DRIVE
# ─────────────────────────────────────────────

@st.cache_resource
def _drive_service():
    """Retorna cliente autenticado do Google Drive (service account)."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


@st.cache_data(ttl=21600)
def _list_drive_folder() -> list[dict]:
    """Lista todos os arquivos da pasta do Drive (id, name, mimeType). Cache 1h."""
    svc = _drive_service()
    q   = f"'{_FOLDER_ID}' in parents and trashed=false"
    res = svc.files().list(q=q, fields="files(id,name,mimeType)", pageSize=200).execute()
    return res.get("files", [])


@st.cache_data(ttl=21600)
def _download_sheet(file_id: str) -> bytes:
    """Exporta Google Sheet como XLSX bytes (cache 1h)."""
    from googleapiclient.http import MediaIoBaseDownload
    svc     = _drive_service()
    request = svc.files().export_media(fileId=file_id, mimeType=_XLSX_MIME)
    buf     = io.BytesIO()
    dl      = MediaIoBaseDownload(buf, request)
    done    = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


@st.cache_data(ttl=21600)
def _download_sheet_csv(file_id: str) -> str:
    """Exporta Google Sheet como CSV string UTF-8 (cache 1h)."""
    from googleapiclient.http import MediaIoBaseDownload
    svc     = _drive_service()
    request = svc.files().export_media(fileId=file_id, mimeType="text/csv")
    buf     = io.BytesIO()
    dl      = MediaIoBaseDownload(buf, request)
    done    = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue().decode("utf-8", errors="replace")


@st.cache_data(ttl=21600)
def _download_file(file_id: str) -> bytes:
    """Baixa arquivo binário do Drive (CSV, etc.) como bytes (cache 1h)."""
    from googleapiclient.http import MediaIoBaseDownload
    svc     = _drive_service()
    request = svc.files().get_media(fileId=file_id)
    buf     = io.BytesIO()
    dl      = MediaIoBaseDownload(buf, request)
    done    = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


def _find_in_folder(pattern: str, mime: str = None) -> str | None:
    """Retorna o file_id do primeiro arquivo cujo nome bate com o regex pattern na pasta."""
    for f in _list_drive_folder():
        if mime and f["mimeType"] != mime:
            continue
        if re.fullmatch(pattern, f["name"]):
            return f["id"]
    return None


def _sheet_to_df(file_id: str) -> pd.DataFrame:
    """Lê Google Sheet como DataFrame bruto (header=None), via export XLSX."""
    return pd.read_excel(io.BytesIO(_download_sheet(file_id)), header=None)

# ─────────────────────────────────────────────
# GRUPOS DE CENTROS DE CUSTO POR PÁGINA
# ─────────────────────────────────────────────

GROUP_MAP = {
    "administrativo": ["Administrativo", "Business Intelligence", "Financeiro", "Facility"],
    "cx":             ["Client Support", "Customer Success", "Implementação"],
    "diretoria":      ["Diretoria"],
    "educacao":       ["Educação", "Lançamento"],
    "comercial":      ["Field Sales", "Inbound", "Sales", "Outside Sales"],
    "marketing":      ["Marketing"],
    "parcerias":      ["Eventos", "Parceiros"],
    "people":         ["People Happiness"],
    "tech":           ["Tech"],
    "operacoes":      ["Operações & Processos"],
    "outros":         [
        "Inchurch Music", "Design", "InChurch Conference",
        "Key Account", "Meio de Pagamentos", "Outbound", "Produto",
        "Upsell", "inChurch KIDS", "inVolve", "Recorrente",
        "Atos 6", "Chatbot", "Internacional", "Justus",
    ],
}

# Todos os centros de custo (usado pela página Consolidado)
GROUP_MAP["consolidado"] = [c for centros in GROUP_MAP.values() for c in centros]

PAGE_LABELS = {
    "administrativo": "Administrativo",
    "cx":             "Customer Experience",
    "diretoria":      "Diretoria",
    "educacao":       "Educação",
    "comercial":      "Comercial",
    "marketing":      "Marketing",
    "parcerias":      "Parcerias",
    "people":         "People",
    "tech":           "Tech",
    "operacoes":      "Operações",
    "outros":         "Outros",
    "consolidado":    "Consolidado",
}

# Mapeamento de departamentos do arquivo equipe → page_key
EQUIPE_DEPT_MAP = {
    "FINANCEIRO":           "administrativo",
    "BUSINESS INTELLIGENCE":"administrativo",
    "RECURSOS HUMANOS":     "people",
    "EDUCAÇÃO":             "educacao",
    "MARKETING":            "marketing",
    "INBOUND":              "comercial",
    "OUTSIDE":              "comercial",
    "PARCERIAS":            "parcerias",
    "EVENTOS":              "parcerias",
    "IMPLEMENTAÇÃO":        "cx",
    "ONGOING":              "cx",
    "SUPORTE":              "cx",
    "BOT":                  "outros",
    "TECH":                 "tech",
    "DIRETORIA":            "diretoria",
}

# Mapeamento de departamentos do arquivo software → page_key
SOFT_DEPT_MAP = {
    "Support":       "cx",
    "CS":            "cx",
    "FIN":           "administrativo",
    "RH":            "people",
    "Marketing":     "marketing",
    "Processos":     "operacoes",
    "Sales Geral":   "comercial",
    "Inbound":       "comercial",
    "Outbound":      "comercial",
    "Outside Sales": "comercial",
    "Tech":          "tech",
    "Geral":         "administrativo",  # a confirmar com usuário
}

# Tipos especiais de linha no arquivo equipe
EQUIPE_TIPO_LABELS = {
    "reposicao":    "🔄 Reposição",
    "novo":         "🆕 Nova contratação",
    "budget_livre": "📦 Budget Livre",
    "pessoa":       "",
}

# Normalização de nomes do 190B → projeções
CENTRO_NORMALIZACAO = {
    "Loja inteligente": "Loja Inteligente",
}

CATEGORIA_MAP = {
    # Outros Custos/Despesas — unificar
    "------------":                  "Outros Custos/Despesas",
    "Sem classificação":             "Outros Custos/Despesas",
    "Sem Classificação":             "Outros Custos/Despesas",
    "Diferença de budget total":     "Outros Custos/Despesas",
    "Diferença Budget Total":        "Outros Custos/Despesas",
    "Deslocamento e Hospedagem":     "Outros Custos/Despesas",
    # Folha de Pagamento
    "Salarios":                      "Folha de Pagamento",
    "Encargos":                      "Folha de Pagamento",
    "Beneficios":                    "Folha de Pagamento",
}


def _normalize_categoria(series: "pd.Series") -> "pd.Series":
    return series.map(lambda c: CATEGORIA_MAP.get(c, c))


PALETTE = [
    "#6eda2c", "#ffffff", "#57d124", "#a0a0a0",
    "#4c4c4c", "#292929", "#8ae650", "#3ba811", "#cccccc", "#111111",
]


# ─────────────────────────────────────────────
# LEITURA DE DADOS
# ─────────────────────────────────────────────

@st.cache_data(ttl=21600)
def load_190b() -> pd.DataFrame:
    """
    Lê despesas liquidadas. Suporta duas fontes (usa a primeira encontrada):
      1. Google Sheet 'despesas_liquidadas*' — formato: uma linha por alocação de centro
      2. CSV '190B*.csv' — formato legado: múltiplos centros por linha (grupos de 3 colunas)

    Estrutura das linhas (ambos os formatos):
      col  6  : Data de liquidação (DD/MM/YYYY)
      col  8  : Código de natureza
      col  12 : Valor pago (string BR, ex: "-109074,61")
      cols 13+: grupos de 3 — [Centro de custo, Participação (%), Participação ($)]
                (Participação ($) ignorada; valor = valor_pago × pct/100)
    """
    import csv as _csv

    def parse_br_float(s: str) -> float:
        s = s.strip().strip('"').replace(" ", "")
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _iter_rows(content: str):
        """Itera linhas do CSV, tratando formato CSV-in-CSV do Sheets e CSV normal.
        Usa io.StringIO para lidar corretamente com newlines dentro de campos."""
        reader = _csv.reader(io.StringIO(content))
        rows   = [r for r in reader if any(c.strip() for c in r)]
        if not rows:
            return
        # Detecta CSV-in-CSV: linha tem apenas 1 coluna mas contém vírgulas internas
        is_sheet_format = len(rows[0]) == 1 and "," in rows[0][0]
        for row in rows:
            if not row:
                continue
            if is_sheet_format:
                yield next(_csv.reader([row[0]]))
            else:
                yield row

    # ── Localizar arquivo de despesas ─────────────────────────────────────
    # Prioridade: Sheet atualizado > CSV legado
    sheet_id = _find_in_folder(r"despesas_liquidadas.*", mime=_SHEET_MIME)
    if sheet_id:
        content  = _download_sheet_csv(sheet_id)
        is_sheet = True
    else:
        csv_id = _find_in_folder(r"190B.*\.csv")
        if not csv_id:
            st.error("Nenhum arquivo de despesas encontrado na pasta do Drive.")
            return pd.DataFrame(columns=["cod_natureza", "liquidacao", "centro_custo", "valor", "mes"])
        content  = _download_file(csv_id).decode("latin1")
        is_sheet = False

    records = []
    row_iter = _iter_rows(content)
    next(row_iter)  # pula cabeçalho

    for row in row_iter:
            if len(row) < 13:
                continue

            # Detecta deslocamento de coluna: ocorre quando o fornecedor tem
            # vírgula no nome sem aspas (ex: "WHIMSICAL, INC.") — cada vírgula
            # extra desloca todas as colunas seguintes em +1.
            # O Cód. Natureza sempre tem formato "d.d.d" (ex: "2.5.2") — usamos
            # ele para medir o deslocamento real.
            shift = 0
            for _s in range(5):  # testa deslocamentos 0–4
                _val = row[8 + _s].strip() if (8 + _s) < len(row) else ""
                if re.match(r'^\d+\.\d+\.\d+$', _val):
                    shift = _s
                    break

            cod_natureza   = row[8 + shift].strip()
            liquidacao_str = row[6 + shift].strip()
            valor_pago     = parse_br_float(row[12 + shift])

            try:
                liquidacao = pd.to_datetime(liquidacao_str, format="%d/%m/%Y", errors="coerce")
            except Exception:
                liquidacao = pd.NaT

            # Percorre grupos de 3 colunas a partir do índice 13 + shift
            idx = 13 + shift
            while idx + 1 < len(row):
                centro = row[idx].strip().strip('"')
                pct_str = row[idx + 1] if idx + 1 < len(row) else "0"
                try:
                    pct = parse_br_float(pct_str)
                    valor_alocado = valor_pago * (pct / 100.0)
                except Exception:
                    idx += 3
                    continue

                if centro and centro not in ("Centro de custo", "CC Transitório"):
                    records.append({
                        "cod_natureza": cod_natureza,
                        "liquidacao":   liquidacao,
                        "centro_custo": centro,
                        "valor":        valor_alocado,
                    })
                idx += 3

    if not records:
        return pd.DataFrame(columns=["cod_natureza", "liquidacao", "centro_custo", "valor", "mes"])

    df = pd.DataFrame(records)
    df["mes"]          = df["liquidacao"].dt.to_period("M").dt.to_timestamp()
    df["centro_custo"] = df["centro_custo"].replace(CENTRO_NORMALIZACAO)
    df["cod_natureza"] = df["cod_natureza"].astype(str).str.strip()
    return df


@st.cache_data(ttl=21600)
def load_depara() -> pd.DataFrame:
    file_id = _find_in_folder("de_para", mime=_SHEET_MIME)
    if not file_id:
        st.error("Arquivo de_para não encontrado na pasta do Drive.")
        return pd.DataFrame(columns=["cod_natureza", "classificacao"])

    # Lê sem dtype=str para que datas sejam lidas como Timestamps
    raw = pd.read_excel(io.BytesIO(_download_sheet(file_id)), header=None)

    # O Google Sheets converte códigos no formato "D.M.AA" (ex: "2.9.1") para datas
    # porque os interpreta como DD/MM/AA (locale BR). Revertemos:
    #   Timestamp(2001-09-02) → day=2, month=9, year%100=1 → "2.9.1"
    def _ts_to_code(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        # Duck-type: qualquer objeto com day/month/year é uma data
        if hasattr(v, "day") and hasattr(v, "month") and hasattr(v, "year"):
            return f"{v.day}.{v.month}.{v.year % 100}"
        return str(v).strip()

    cod_series   = raw.iloc[:, 0].apply(_ts_to_code)
    # A classificação pode estar na col 2 (com descricao no meio) ou na última coluna
    class_col_idx = 2 if raw.shape[1] >= 3 else raw.shape[1] - 1
    class_series = raw.iloc[:, class_col_idx].astype(str).str.strip()

    dp = pd.DataFrame({"cod_natureza": cod_series, "classificacao": class_series})
    dp = dp[dp["cod_natureza"].notna() & (dp["cod_natureza"] != "None")]
    dp = dp[~dp["classificacao"].isin(["------------", "nan", ""])]
    return dp[["cod_natureza", "classificacao"]].drop_duplicates("cod_natureza")


@st.cache_data(ttl=21600)
def _parse_projecoes(file_id: str) -> pd.DataFrame:
    raw = _sheet_to_df(file_id)

    # Extrair meses da linha onde a coluna 2 é datetime
    months = []
    for i in range(min(20, len(raw))):
        val = raw.iloc[i, 2]
        if pd.notna(val) and isinstance(val, (pd.Timestamp,)) or (
            pd.notna(val) and hasattr(val, "year")
        ):
            months = []
            for j in range(2, min(14, raw.shape[1])):
                m = raw.iloc[i, j]
                if pd.notna(m):
                    months.append(pd.Timestamp(m))
            if len(months) >= 10:
                break

    records = []
    for i in range(len(raw)):
        centro = raw.iloc[i, 0]
        categoria = raw.iloc[i, 1]
        if not isinstance(centro, str) or not isinstance(categoria, str):
            continue
        if "Soma Aberta" in centro:
            continue
        centro = centro.strip()
        categoria = categoria.strip()
        for j, mes in enumerate(months):
            col_idx = j + 2
            val = raw.iloc[i, col_idx] if col_idx < raw.shape[1] else 0
            val = 0 if pd.isna(val) else float(val)
            records.append({
                "centro_custo": centro,
                "categoria": categoria,
                "mes": mes,
                "valor_previsto": abs(val),
            })

    return pd.DataFrame(records)


def get_all_projecoes_files() -> list:
    """Retorna lista de (date, file_id) ordenada por data."""
    files = []
    for f in _list_drive_folder():
        if f["mimeType"] != _SHEET_MIME:
            continue
        m = re.search(r"projecoes_(\d{2})_(\d{2})_(\d{4})", f["name"])
        if m:
            day, month, year = m.groups()
            dt = date(int(year), int(month), int(day))
            files.append((dt, f["id"]))
    return sorted(files)


@st.cache_data(ttl=21600)
def load_all_projecoes() -> dict:
    """Retorna {date_str: df} para todos os arquivos de projeção."""
    result = {}
    for dt, file_id in get_all_projecoes_files():
        key = dt.strftime("%d/%m/%Y")
        result[key] = _parse_projecoes(file_id)
    return result


# ─────────────────────────────────────────────
# DADOS POR GRUPO
# ─────────────────────────────────────────────

def get_realizado(centros: list, exclude_categories: list = None) -> pd.DataFrame:
    df190 = load_190b()
    depara = load_depara()

    df = df190[df190["centro_custo"].isin(centros)].copy()
    df = df.merge(depara, on="cod_natureza", how="left")
    df["classificacao"] = df["classificacao"].fillna("Sem Classificação")
    df["classificacao"] = _normalize_categoria(df["classificacao"])

    # Apenas despesas (valores negativos no sistema)
    df = df[df["valor"] < 0]

    if exclude_categories:
        df = df[~df["classificacao"].isin(exclude_categories)]

    result = (
        df.groupby(["mes", "classificacao"])["valor"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"valor": "valor_realizado", "classificacao": "categoria"})
    )
    return result


def get_previsto(centros: list, proj_df: pd.DataFrame) -> pd.DataFrame:
    df = proj_df[proj_df["centro_custo"].isin(centros)].copy()
    df["categoria"] = _normalize_categoria(df["categoria"])
    result = (
        df.groupby(["mes", "categoria"])["valor_previsto"]
        .sum()
        .reset_index()
    )
    return result


def get_previsto_all(centros: list) -> pd.DataFrame:
    """
    Combina todos os arquivos de projeção: para cada mês usa o arquivo
    mais recente que o cobre.
      - Jan/26 só existe no arquivo de jan → vem de lá
      - Fev/26 existe em jan e fev → usa fev (mais atualizado)
      - Mar/26 em diante → usa o arquivo mais recente
    """
    proj_files = get_all_projecoes_files()
    if not proj_files:
        return pd.DataFrame()

    all_parts = []
    covered_months: set = set()

    for _, file_id in reversed(proj_files):      # mais recente primeiro
        proj_df = _parse_projecoes(file_id)
        new_months = set(proj_df["mes"].unique()) - covered_months
        if new_months:
            part = get_previsto(centros, proj_df)
            part = part[part["mes"].isin(new_months)]
            all_parts.append(part)
            covered_months |= new_months

    if not all_parts:
        return pd.DataFrame()
    return pd.concat(all_parts, ignore_index=True)


def _centros_to_page_keys(centros: list) -> set:
    """Mapeia lista de nomes de centro de custo para os page_keys correspondentes."""
    result = set()
    for pk, cc_list in GROUP_MAP.items():
        if pk == "consolidado":
            continue
        if any(c in centros for c in cc_list):
            result.add(pk)
    return result


def _find_file_by_date(date_str: str, files: list):
    """Retorna o path do arquivo cuja data bate com date_str 'DD/MM/YYYY', ou None."""
    target = pd.to_datetime(date_str, format="%d/%m/%Y").date()
    for dt, fp in files:
        if dt == target:
            return str(fp)
    return None


def get_log_mudancas(centros: list) -> pd.DataFrame:
    """
    Compara arquivos de projeção consecutivos e retorna as mudanças.
    - Normaliza categorias antes de comparar (evita falsos positivos de aliases como
      'Diferença Budget Total' vs 'Sem Classificação').
    - Para mudanças em 'Folha de Pagamento', cruza com arquivo equipe da mesma data
      para identificar qual colaborador causou a variação.
    - Para mudanças em 'Software'/'Servidor', cruza com arquivo software da mesma data.
    """
    all_proj = load_all_projecoes()
    dates = sorted(all_proj.keys(), key=lambda d: pd.to_datetime(d, format="%d/%m/%Y"))

    if len(dates) < 2:
        return pd.DataFrame()

    page_keys    = _centros_to_page_keys(centros)
    equipe_files = get_all_equipe_files()
    soft_files   = get_all_software_files()

    logs = []
    for i in range(1, len(dates)):
        d_antes  = dates[i - 1]
        d_depois = dates[i]

        df_b = all_proj[d_antes][all_proj[d_antes]["centro_custo"].isin(centros)].copy()
        df_a = all_proj[d_depois][all_proj[d_depois]["centro_custo"].isin(centros)].copy()

        # Normalizar e agregar — une aliases como "Diferença Budget Total" → "Sem Classificação"
        df_b["categoria"] = _normalize_categoria(df_b["categoria"])
        df_a["categoria"] = _normalize_categoria(df_a["categoria"])
        df_b = df_b.groupby(["centro_custo", "categoria", "mes"])["valor_previsto"].sum().reset_index()
        df_a = df_a.groupby(["centro_custo", "categoria", "mes"])["valor_previsto"].sum().reset_index()

        merged = df_b.merge(
            df_a, on=["centro_custo", "categoria", "mes"],
            suffixes=("_antes", "_depois"), how="outer"
        ).fillna(0)

        # Só meses >= data do arquivo mais novo (meses anteriores já foram realizados
        # e saem naturalmente da projeção — não é uma mudança de orçamento)
        d_depois_ts = pd.to_datetime(d_depois, format="%d/%m/%Y").to_period("M").to_timestamp()
        merged = merged[merged["mes"] >= d_depois_ts]

        changed = merged[
            abs(merged["valor_previsto_depois"] - merged["valor_previsto_antes"]) > 1
        ].copy()

        if changed.empty:
            continue

        changed["data_alteracao"] = d_depois
        changed["variacao"]       = changed["valor_previsto_depois"] - changed["valor_previsto_antes"]
        changed["detalhe"]        = ""

        # ── Enriquecer mudanças de Folha de Pagamento ───────────────────────
        salary_mask = changed["categoria"] == "Folha de Pagamento"
        if salary_mask.any():
            fp_eq_b = _find_file_by_date(d_antes, equipe_files)
            fp_eq_a = _find_file_by_date(d_depois, equipe_files)
            if fp_eq_b and fp_eq_a:
                eq_b = _parse_equipe(fp_eq_b)
                eq_a = _parse_equipe(fp_eq_a)
                # Filtrar pela página relevante, apenas colaboradores reais
                eq_b = eq_b[eq_b["page_key"].isin(page_keys) & (eq_b["tipo"] == "pessoa")]
                eq_a = eq_a[eq_a["page_key"].isin(page_keys) & (eq_a["tipo"] == "pessoa")]

                cost_b = eq_b.groupby("pessoa")["custo"].sum().reset_index()
                cost_a = eq_a.groupby("pessoa")["custo"].sum().reset_index()

                eq_mg = cost_b.merge(cost_a, on="pessoa", suffixes=("_b", "_a"), how="outer").fillna(0)
                eq_mg["diff"] = eq_mg["custo_a"] - eq_mg["custo_b"]
                eq_ch = eq_mg[abs(eq_mg["diff"]) > 1].sort_values("diff", key=abs, ascending=False)

                if not eq_ch.empty:
                    parts = []
                    for _, er in eq_ch.iterrows():
                        if er["custo_b"] == 0:
                            parts.append(f"{er['pessoa']} (nova entrada)")
                        elif er["custo_a"] == 0:
                            parts.append(f"{er['pessoa']} (saída)")
                        else:
                            sinal = "+" if er["diff"] > 0 else ""
                            parts.append(f"{er['pessoa']} ({sinal}R$ {fmt_brl(er['diff'] / 12, 0)}/mês)")
                    changed.loc[salary_mask, "detalhe"] = "Colaboradores: " + " · ".join(parts)

        # ── Enriquecer mudanças de Software / Servidor ──────────────────────
        soft_mask = changed["categoria"].isin(["Software", "Servidor"])
        if soft_mask.any():
            fp_sw_b = _find_file_by_date(d_antes, soft_files)
            fp_sw_a = _find_file_by_date(d_depois, soft_files)
            if fp_sw_b and fp_sw_a:
                sw_b = _parse_software(fp_sw_b)
                sw_a = _parse_software(fp_sw_a)
                sw_b = sw_b[sw_b["page_key"].isin(page_keys)]
                sw_a = sw_a[sw_a["page_key"].isin(page_keys)]

                cost_b = sw_b.groupby("software")["valor"].sum().reset_index()
                cost_a = sw_a.groupby("software")["valor"].sum().reset_index()

                sw_mg = cost_b.merge(cost_a, on="software", suffixes=("_b", "_a"), how="outer").fillna(0)
                sw_mg["diff"] = sw_mg["valor_a"] - sw_mg["valor_b"]
                sw_ch = sw_mg[abs(sw_mg["diff"]) > 1].sort_values("diff", key=abs, ascending=False)

                if not sw_ch.empty:
                    parts = []
                    for _, sr in sw_ch.iterrows():
                        if sr["valor_b"] == 0:
                            parts.append(f"{sr['software']} (novo)")
                        elif sr["valor_a"] == 0:
                            parts.append(f"{sr['software']} (removido)")
                        else:
                            sinal = "+" if sr["diff"] > 0 else ""
                            parts.append(f"{sr['software']} ({sinal}R$ {fmt_brl(sr['diff'], 0)}/ano)")
                    changed.loc[soft_mask, "detalhe"] = "Softwares: " + " · ".join(parts)

        logs.append(_collapse_log_rows(changed))

    if not logs:
        return pd.DataFrame()

    return pd.concat(logs, ignore_index=True).sort_values("data_alteracao", ascending=False)


def _collapse_log_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Colapsa múltiplas linhas com a mesma mudança (mesmo centro, categoria, valores)
    em uma única linha com um label de intervalo de meses.
    Ex: Fev/26 R$10k→R$11k + Mar/26 R$10k→R$11k + ... → "Fev/26 a Dez/26 R$10k→R$11k"
    """
    if df.empty:
        return df

    group_cols = [
        "data_alteracao", "centro_custo", "categoria",
        "valor_previsto_antes", "valor_previsto_depois", "variacao", "detalhe",
    ]
    result = []
    for keys, grp in df.groupby(group_cols, dropna=False, sort=False):
        months = sorted(grp["mes"].tolist())
        if len(months) == 1:
            mes_label = pd.Timestamp(months[0]).strftime("%b/%y").capitalize()
        elif len(months) == 2:
            a = pd.Timestamp(months[0]).strftime("%b/%y").capitalize()
            b = pd.Timestamp(months[1]).strftime("%b/%y").capitalize()
            mes_label = f"{a} e {b}"
        else:
            a = pd.Timestamp(months[0]).strftime("%b/%y").capitalize()
            b = pd.Timestamp(months[-1]).strftime("%b/%y").capitalize()
            mes_label = f"{a} a {b}"

        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["mes"]       = months[0]   # usado só para ordenação residual
        row["mes_label"] = mes_label
        result.append(row)

    return pd.DataFrame(result)


# ─────────────────────────────────────────────
# EQUIPE
# ─────────────────────────────────────────────

@st.cache_data(ttl=21600)
def _parse_equipe(file_id: str) -> pd.DataFrame:
    raw = _sheet_to_df(file_id)

    # Meses na linha onde col 2 é datetime (cols 0-1 são NaN, meses ficam nas cols 2-13)
    months = []
    for i in range(min(15, len(raw))):
        val = raw.iloc[i, 2]
        if pd.notna(val) and hasattr(val, "year"):
            for j in range(2, min(14, raw.shape[1])):
                m = raw.iloc[i, j]
                if pd.notna(m) and hasattr(m, "year"):
                    months.append(pd.Timestamp(m))
            if len(months) >= 10:
                break

    records = []
    for i in range(len(raw)):
        dept   = raw.iloc[i, 0]
        pessoa = raw.iloc[i, 1]
        if not isinstance(dept, str) or not isinstance(pessoa, str):
            continue

        dept   = dept.strip()
        pessoa = pessoa.strip()

        if not dept or not pessoa:
            continue
        if pessoa == "SIMULAÇÃO DE CORTE":
            continue

        if pessoa == "Reposição":
            tipo = "reposicao"
        elif pessoa.upper() == "NOVO":
            tipo = "novo"
        elif pessoa == "Budget Livre":
            tipo = "budget_livre"
        else:
            tipo = "pessoa"

        page_key = EQUIPE_DEPT_MAP.get(dept, "outros")

        for j, mes in enumerate(months):
            col_idx = j + 2
            val = raw.iloc[i, col_idx] if col_idx < raw.shape[1] else 0
            val = 0.0 if pd.isna(val) else float(val)
            records.append({
                "departamento": dept,
                "page_key":     page_key,
                "pessoa":       pessoa,
                "tipo":         tipo,
                "row_idx":      i,   # identifica cada linha original do sheet
                "mes":          mes,
                "custo":        val,
            })

    cols = ["departamento", "page_key", "pessoa", "tipo", "row_idx", "mes", "custo"]
    if not records:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(records)[cols]


def get_all_equipe_files() -> list:
    """Retorna lista de (date, file_id) ordenada por data para arquivos equipe_*."""
    files = []
    for f in _list_drive_folder():
        if f["mimeType"] != _SHEET_MIME:
            continue
        m = re.search(r"equipe_(\d{2})_(\d{2})_(\d{4})", f["name"])
        if m:
            day, month, year = m.groups()
            dt = date(int(year), int(month), int(day))
            files.append((dt, f["id"]))
    return sorted(files)


@st.cache_data(ttl=21600)
def load_all_equipes() -> dict:
    """Retorna {date_str: df} para todos os arquivos de equipe."""
    result = {}
    for dt, file_id in get_all_equipe_files():
        key = dt.strftime("%d/%m/%Y")
        result[key] = _parse_equipe(file_id)
    return result


def get_equipe_for_page(page_key: str) -> pd.DataFrame:
    """Retorna dados de equipe da versão mais recente para o page_key."""
    files = get_all_equipe_files()
    if not files:
        return pd.DataFrame()
    latest = _parse_equipe(files[-1][1])
    if page_key == "consolidado":
        return latest.copy()
    return latest[latest["page_key"] == page_key].copy()


def get_equipe_first_seen(page_key: str) -> tuple:
    """
    Retorna (dict, overall_min) onde:
    - dict: {(pessoa, departamento, tipo): primeiro_mes} olhando todos os arquivos históricos
    - overall_min: menor mês encontrado em qualquer arquivo (referência de "desde o início")
    Usado para mostrar a data real de entrada sem depender do primeiro mês do arquivo atual.
    """
    all_eq = load_all_equipes()
    result = {}
    overall_min = None
    for date_str in sorted(all_eq.keys(), key=lambda d: pd.to_datetime(d, format="%d/%m/%Y")):
        df = all_eq[date_str]
        if page_key != "consolidado":
            df = df[df["page_key"] == page_key]
        for _, row in df[df["custo"] > 0].iterrows():
            key = (row["pessoa"], row["departamento"], row["tipo"])
            month = pd.Timestamp(row["mes"])
            if key not in result or month < result[key]:
                result[key] = month
            if overall_min is None or month < overall_min:
                overall_min = month
    return result, overall_min


def get_equipe_log(page_key: str) -> pd.DataFrame:
    """Compara versões consecutivas do arquivo equipe e retorna mudanças."""
    all_eq = load_all_equipes()
    dates  = sorted(all_eq.keys(), key=lambda d: pd.to_datetime(d, format="%d/%m/%Y"))

    if len(dates) < 2:
        return pd.DataFrame()

    logs = []
    for i in range(1, len(dates)):
        d_antes  = dates[i - 1]
        d_depois = dates[i]
        if page_key == "consolidado":
            df_b = all_eq[d_antes]
            df_a = all_eq[d_depois]
        else:
            df_b = all_eq[d_antes][all_eq[d_antes]["page_key"] == page_key]
            df_a = all_eq[d_depois][all_eq[d_depois]["page_key"] == page_key]

        # Pessoas que apareceram (entradas)
        pessoas_antes  = set(df_b[df_b["tipo"] == "pessoa"]["pessoa"].unique())
        pessoas_depois = set(df_a[df_a["tipo"] == "pessoa"]["pessoa"].unique())

        for p in pessoas_depois - pessoas_antes:
            logs.append({"data": d_depois, "evento": "entrada", "pessoa": p,
                         "departamento": df_a[df_a["pessoa"] == p]["departamento"].iloc[0],
                         "detalhe": "Nova entrada na equipe"})

        for p in pessoas_antes - pessoas_depois:
            logs.append({"data": d_depois, "evento": "saida", "pessoa": p,
                         "departamento": df_b[df_b["pessoa"] == p]["departamento"].iloc[0],
                         "detalhe": "Saiu da equipe"})

        # Mudanças de custo — compara apenas meses presentes nos dois arquivos.
        # Meses que sumiram por terem sido realizados não estão nos dois → sem falso positivo.
        # Meses com custo diferente nos dois arquivos → mudança real → aparece no log.
        meses_comuns = set(df_b["mes"].unique()) & set(df_a["mes"].unique())
        pessoas_b = df_b[(df_b["tipo"] == "pessoa") & (df_b["mes"].isin(meses_comuns))]
        pessoas_a = df_a[(df_a["tipo"] == "pessoa") & (df_a["mes"].isin(meses_comuns))]
        merged = (
            pessoas_b.groupby(["pessoa", "departamento"])["custo"].sum()
            .reset_index()
            .merge(
                pessoas_a.groupby(["pessoa", "departamento"])["custo"].sum()
                .reset_index(),
                on=["pessoa", "departamento"], suffixes=("_antes", "_depois")
            )
        )
        changed = merged[abs(merged["custo_depois"] - merged["custo_antes"]) > 1]
        for _, row in changed.iterrows():
            logs.append({
                "data":          d_depois,
                "evento":        "custo_alterado",
                "pessoa":        row["pessoa"],
                "departamento":  row["departamento"],
                "detalhe":       f"Custo: R$ {fmt_brl(row['custo_antes'], 0)} → R$ {fmt_brl(row['custo_depois'], 0)}",
            })

        # Reposições — mesma interseção de meses
        rep_antes  = len(df_b[(df_b["tipo"] == "reposicao") & (df_b["mes"].isin(meses_comuns))])
        rep_depois = len(df_a[(df_a["tipo"] == "reposicao") & (df_a["mes"].isin(meses_comuns))])
        if rep_depois != rep_antes:
            dept = df_a[df_a["tipo"] == "reposicao"]["departamento"].mode()
            dept_str = dept.iloc[0] if not dept.empty else "—"
            logs.append({"data": d_depois, "evento": "reposicao",
                         "pessoa": "Reposição", "departamento": dept_str,
                         "detalhe": f"Linhas de reposição: {rep_antes} → {rep_depois}"})

    if not logs:
        return pd.DataFrame()
    return pd.DataFrame(logs).sort_values("data", ascending=False)


# ─────────────────────────────────────────────
# NOTAS DE DESVIO (armazenadas no Drive como JSON)
# ─────────────────────────────────────────────

_NOTAS_FILENAME = "notas_desvios.json"


def _get_or_create_notas_file() -> str:
    """Retorna o file_id do arquivo de notas no Drive, criando-o se não existir."""
    import json
    svc = _drive_service()
    # Procura na pasta
    q = f"'{_FOLDER_ID}' in parents and name='{_NOTAS_FILENAME}' and trashed=false"
    res = svc.files().list(q=q, fields="files(id)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    # Cria arquivo vazio
    from googleapiclient.http import MediaInMemoryUpload
    meta   = {"name": _NOTAS_FILENAME, "parents": [_FOLDER_ID], "mimeType": "application/json"}
    media  = MediaInMemoryUpload(b"{}", mimetype="application/json")
    f      = svc.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


def load_notas() -> dict:
    """Carrega notas salvas no Drive. Retorna {} se não existir."""
    import json
    try:
        svc = _drive_service()
        q   = f"'{_FOLDER_ID}' in parents and name='{_NOTAS_FILENAME}' and trashed=false"
        res = svc.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        if not files:
            return {}
        raw = _download_file(files[0]["id"])
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def save_nota(page_key: str, mes_str: str, texto: str) -> None:
    """Salva/atualiza nota no arquivo JSON no Drive."""
    import json
    from googleapiclient.http import MediaInMemoryUpload
    notas = load_notas()
    if page_key not in notas:
        notas[page_key] = {}
    if texto.strip():
        notas[page_key][mes_str] = texto.strip()
    else:
        notas[page_key].pop(mes_str, None)

    content = json.dumps(notas, ensure_ascii=False, indent=2).encode("utf-8")
    svc      = _drive_service()
    file_id  = _get_or_create_notas_file()
    media    = MediaInMemoryUpload(content, mimetype="application/json")
    svc.files().update(fileId=file_id, media_body=media).execute()
    # Invalida cache do arquivo de notas
    _download_file.clear()


# ─────────────────────────────────────────────
# SOFTWARE
# ─────────────────────────────────────────────

@st.cache_data(ttl=21600)
def _parse_software(file_id: str) -> pd.DataFrame:
    raw = _sheet_to_df(file_id)

    # Meses na linha onde col 2 é datetime (mesmo padrão do equipe)
    months = []
    for i in range(min(10, len(raw))):
        val = raw.iloc[i, 2]
        if pd.notna(val) and hasattr(val, "year"):
            for j in range(2, min(14, raw.shape[1])):
                m = raw.iloc[i, j]
                if pd.notna(m) and hasattr(m, "year"):
                    months.append(pd.Timestamp(m))
            if len(months) >= 10:
                break

    records = []
    current_dept = None
    for i in range(len(raw)):
        dept_raw = raw.iloc[i, 0]
        nome     = raw.iloc[i, 1]

        if isinstance(dept_raw, str) and dept_raw.strip():
            current_dept = dept_raw.strip()

        # Pula linhas sem nome de software (totais ou vazias)
        if not isinstance(nome, str) or not nome.strip():
            continue
        if current_dept is None:
            continue

        nome = nome.strip()
        page_key = SOFT_DEPT_MAP.get(current_dept, "outros")

        for j, mes in enumerate(months):
            col_idx = j + 2
            val = raw.iloc[i, col_idx] if col_idx < raw.shape[1] else None
            if pd.isna(val):
                continue
            val = abs(float(val))
            if val == 0:
                continue
            records.append({
                "departamento": current_dept,
                "page_key":     page_key,
                "software":     nome,
                "mes":          mes,
                "valor":        val,
            })

    cols = ["departamento", "page_key", "software", "mes", "valor"]
    if not records:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(records)[cols]


def get_all_software_files() -> list:
    files = []
    for f in _list_drive_folder():
        if f["mimeType"] != _SHEET_MIME:
            continue
        m = re.search(r"software_(\d{2})_(\d{2})_(\d{4})", f["name"])
        if m:
            day, month, year = m.groups()
            dt = date(int(year), int(month), int(day))
            files.append((dt, f["id"]))
    return sorted(files)


def get_software_for_page(page_key: str) -> pd.DataFrame:
    files = get_all_software_files()
    if not files:
        return pd.DataFrame()
    latest = _parse_software(files[-1][1])
    if page_key == "consolidado":
        return latest.copy()
    return latest[latest["page_key"] == page_key].copy()


# ─────────────────────────────────────────────
# HELPERS DE LAYOUT / GRÁFICOS
# ─────────────────────────────────────────────

def chart_layout(fig: go.Figure, height: int = 380, legend_bottom: bool = False) -> go.Figure:
    legend_cfg = dict(bgcolor="rgba(0,0,0,0)", font=dict(family="Outfit", size=12, color="#a0a0a0"))
    if legend_bottom:
        legend_cfg.update(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5)
    fig.update_layout(
        height=height, template="plotly_dark",
        margin=dict(l=4, r=4, t=32, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, sans-serif", color="#ffffff", size=13),
        legend=legend_cfg,
        xaxis=dict(showgrid=True, gridcolor="#292929", gridwidth=1, zeroline=False, title=""),
        yaxis=dict(showgrid=True, gridcolor="#292929", gridwidth=1, zeroline=False, title=""),
        hoverlabel=dict(bgcolor="#141414", bordercolor="#292929", font_size=13,
                        font_family="Outfit, sans-serif", font_color="#ffffff"),
    )
    return fig


def fmt_brl(value, decimals=2) -> str:
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def no_data(label="Dados não disponíveis"):
    st.info(label, icon="ℹ️")
