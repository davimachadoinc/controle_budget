"""
utils/page_template.py
Template compartilhado por todas as páginas de centro de custo.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.data import (
    GROUP_MAP, PAGE_LABELS, PALETTE, EQUIPE_TIPO_LABELS,
    get_realizado, get_previsto_all, get_log_mudancas,
    get_equipe_for_page, get_equipe_log, get_equipe_first_seen,
    get_software_for_page,
    load_notas, save_nota,
    chart_layout, fmt_brl, no_data,
)

MESES_2026 = pd.date_range("2026-01-01", "2026-12-01", freq="MS")
MESES_LABEL = [m.strftime("%b/%y").capitalize() for m in MESES_2026]

PERIODOS = {
    "Ano Todo":      list(range(1, 13)),
    "── Trimestres ──": None,
    "Q1 — Jan-Mar":  [1, 2, 3],
    "Q2 — Abr-Jun":  [4, 5, 6],
    "Q3 — Jul-Set":  [7, 8, 9],
    "Q4 — Out-Dez":  [10, 11, 12],
    "── Meses ──":   None,
    "Jan/26": [1],  "Fev/26": [2],  "Mar/26": [3],
    "Abr/26": [4],  "Mai/26": [5],  "Jun/26": [6],
    "Jul/26": [7],  "Ago/26": [8],  "Set/26": [9],
    "Out/26": [10], "Nov/26": [11], "Dez/26": [12],
}
_PERIODO_OPTIONS = [k for k, v in PERIODOS.items() if v is not None]


def _month_series(df, col, months):
    if df.empty:
        return [0.0] * len(months)
    # Usa chave string "YYYY-MM" para evitar mismatch de precisão datetime
    # (pandas 2.0+ lê Excel como datetime64[us], pd.date_range gera datetime64[ns])
    months_str = [pd.Timestamp(m).strftime("%Y-%m") for m in months]
    df2 = df.copy()
    df2["_ms"] = pd.to_datetime(df2["mes"]).dt.strftime("%Y-%m")
    lookup = df2.set_index("_ms")[col]
    return [float(lookup.get(m, 0.0)) for m in months_str]


def render_page(page_key: str):
    label   = PAGE_LABELS[page_key]
    centros = GROUP_MAP[page_key]

    st.markdown(f"<h1>{label} <span>Budget</span></h1>", unsafe_allow_html=True)

    # Administrativo: "Outros Custos/Despesas" inclui lançamentos não classificados
    # que são transferências internas — excluir do realizado
    _exclude_cats = ["Outros Custos/Despesas"] if page_key == "administrativo" else None

    with st.spinner("Carregando dados..."):
        df_real_all  = get_realizado(centros, exclude_categories=_exclude_cats)
        df_prev_2026 = get_previsto_all(centros)
        df_log       = get_log_mudancas(centros)
        df_soft      = get_software_for_page(page_key)

    df_real_2026 = df_real_all[df_real_all["mes"].dt.year == 2026].copy() if not df_real_all.empty else pd.DataFrame()

    # Realizado de software = categorias Software + Servidor do 190B
    df_real_soft = pd.DataFrame()
    if not df_real_2026.empty:
        df_real_soft = df_real_2026[df_real_2026["categoria"].isin(["Software", "Servidor"])].copy()

    tab_2026, tab_soft, tab_equipe, tab_log = st.tabs([
        "📊 2026 — Previsto vs Realizado",
        "💻 Software",
        "👥 Equipe",
        "📋 Log de Mudanças",
    ])

    # ── TAB 2026 ─────────────────────────────────────────────────────────────
    with tab_2026:
        # Filtro de período
        col_per, _ = st.columns([2, 8])
        with col_per:
            periodo_sel = st.selectbox(
                "Período", _PERIODO_OPTIONS,
                key=f"periodo_{page_key}",
            )
        meses_sel = PERIODOS[periodo_sel]

        # Filtrar por período
        if periodo_sel == "Ano Todo":
            df_prev_filt = df_prev_2026
            df_real_filt = df_real_2026
            meses_chart  = list(MESES_2026)
            labels_chart = MESES_LABEL
        else:
            df_prev_filt = df_prev_2026[df_prev_2026["mes"].dt.month.isin(meses_sel)].copy() if not df_prev_2026.empty else pd.DataFrame()
            df_real_filt = df_real_2026[df_real_2026["mes"].dt.month.isin(meses_sel)].copy() if not df_real_2026.empty else pd.DataFrame()
            meses_chart  = [m for m in MESES_2026 if m.month in meses_sel]
            labels_chart = [m.strftime("%b/%y").capitalize() for m in meses_chart]

        total_prev = df_prev_filt["valor_previsto"].sum() if not df_prev_filt.empty else 0
        total_real = df_real_filt["valor_realizado"].sum() if not df_real_filt.empty else 0
        desvio     = total_real - total_prev
        pct        = (total_real / total_prev * 100) if total_prev > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Total Previsto 2026", f"R$ {fmt_brl(total_prev, 0)}")
        with k2:
            st.metric("Total Realizado", f"R$ {fmt_brl(total_real, 0)}")
        with k3:
            delta_val = f"{'↑' if desvio > 0 else '↓'} R$ {fmt_brl(abs(desvio), 0)}"
            st.metric("Desvio", f"R$ {fmt_brl(abs(desvio), 0)}", delta=delta_val)
        with k4:
            st.metric("% Executado", f"{pct:.1f}%")

        st.divider()

        # Gráfico: Previsto vs Realizado por mês
        st.subheader("Previsto vs Realizado — Mensal")

        prev_by_month = df_prev_filt.groupby("mes")["valor_previsto"].sum().reset_index() if not df_prev_filt.empty else pd.DataFrame(columns=["mes", "valor_previsto"])
        real_by_month = df_real_filt.groupby("mes")["valor_realizado"].sum().reset_index() if not df_real_filt.empty else pd.DataFrame(columns=["mes", "valor_realizado"])

        prev_vals = _month_series(prev_by_month, "valor_previsto", meses_chart)
        real_vals = _month_series(real_by_month, "valor_realizado", meses_chart)

        # Realizado: verde se dentro do previsto, vermelho se excede
        colors_real = [
            "#e74c3c" if (rv > pv and rv > 0) else PALETTE[0]
            for pv, rv in zip(prev_vals, real_vals)
        ]

        fig = go.Figure()
        fig.add_bar(x=labels_chart, y=prev_vals, name="Previsto",
                    marker_color="#444444", opacity=0.95)
        fig.add_bar(x=labels_chart, y=real_vals, name="Realizado",
                    marker_color=colors_real, opacity=0.9)
        fig.update_layout(barmode="group", xaxis=dict(type="category"))
        st.plotly_chart(chart_layout(fig, height=360, legend_bottom=True), use_container_width=True)

        st.divider()

        # Breakdown por categoria — tabela unificada
        st.subheader("Por Categoria")

        cat_prev = (df_prev_filt.groupby("categoria")["valor_previsto"].sum().reset_index()
                    if not df_prev_filt.empty
                    else pd.DataFrame(columns=["categoria", "valor_previsto"]))
        cat_real = (df_real_filt.groupby("categoria")["valor_realizado"].sum().reset_index()
                    if not df_real_filt.empty
                    else pd.DataFrame(columns=["categoria", "valor_realizado"]))

        cat_merged = pd.merge(cat_prev, cat_real, on="categoria", how="outer").fillna(0)
        cat_merged = cat_merged[(cat_merged["valor_previsto"] > 0) | (cat_merged["valor_realizado"] > 0)]

        if cat_merged.empty:
            no_data("Sem dados para o período selecionado")
        else:
            cat_merged = cat_merged.sort_values("categoria").reset_index(drop=True)
            desvios    = cat_merged["valor_realizado"] - cat_merged["valor_previsto"]

            cat_display = pd.DataFrame({
                "Categoria": cat_merged["categoria"],
                "Previsto":  cat_merged["valor_previsto"].apply(lambda v: f"R$ {fmt_brl(v, 0)}"),
                "Realizado": cat_merged["valor_realizado"].apply(lambda v: f"R$ {fmt_brl(v, 0)}"),
                "Desvio":    desvios.apply(lambda v: f"{'↑' if v > 0 else '↓'} R$ {fmt_brl(abs(v), 0)}"),
            })

            def _color_desvio(val):
                if str(val).startswith("↑"):
                    return "color: #e74c3c; font-weight: 600"
                if str(val).startswith("↓"):
                    return "color: #6eda2c; font-weight: 600"
                return ""

            st.dataframe(
                cat_display.style.map(_color_desvio, subset=["Desvio"]),
                hide_index=True, use_container_width=True,
            )

        st.divider()

        # ── Análise de Desvios ────────────────────────────────────────────
        st.subheader("Análise de Desvios")

        # Meses com realizado acima do previsto
        if not cat_merged.empty:
            acima = cat_merged[desvios > 100].copy()
            acima["desvio_val"] = desvios[desvios > 100]
            acima = acima.sort_values("desvio_val", ascending=False)

            if not acima.empty:
                st.markdown("**Categorias acima do previsto no período selecionado:**")
                for _, row in acima.iterrows():
                    dv = row["desvio_val"]
                    pct = (dv / row["valor_previsto"] * 100) if row["valor_previsto"] > 0 else None
                    pct_str = f" (+{pct:.0f}%)" if pct is not None else ""
                    st.markdown(
                        f"🔴 **{row['categoria']}** — Previsto R$ {fmt_brl(row['valor_previsto'], 0)} "
                        f"· Realizado R$ {fmt_brl(row['valor_realizado'], 0)} "
                        f"· **↑ R$ {fmt_brl(dv, 0)}{pct_str}**"
                    )
            else:
                st.success("Nenhuma categoria acima do previsto no período selecionado.", icon="✅")

        # Campo de anotação por período
        st.divider()
        notas = load_notas()
        mes_nota_key = f"{periodo_sel.replace(' ', '_').replace('—', '').replace('/', '')}_{page_key}"
        nota_existente = notas.get(page_key, {}).get(mes_nota_key, "")

        with st.expander("📝 Adicionar / editar anotação para este período", expanded=bool(nota_existente)):
            nova_nota = st.text_area(
                "Explicação dos desvios",
                value=nota_existente,
                placeholder="Ex: Folha acima do previsto por integração do Outside Sales. Comissões elevadas por performance acima da meta em Field Sales.",
                height=120,
                key=f"nota_{page_key}_{periodo_sel}",
            )
            col_save, col_clear, _ = st.columns([2, 2, 6])
            with col_save:
                if st.button("💾 Salvar", key=f"save_{page_key}_{periodo_sel}", use_container_width=True):
                    save_nota(page_key, mes_nota_key, nova_nota)
                    st.success("Anotação salva!")
                    st.rerun()
            with col_clear:
                if st.button("🗑️ Limpar", key=f"clear_{page_key}_{periodo_sel}", use_container_width=True):
                    save_nota(page_key, mes_nota_key, "")
                    st.rerun()

        # Exibe nota salva com destaque
        if nota_existente:
            st.info(f"📝 **Anotação salva:** {nota_existente}", icon="📌")

    # ── TAB SOFTWARE ─────────────────────────────────────────────────────────
    with tab_soft:
        if df_soft.empty:
            no_data("Sem dados de software para este centro de custo.")
        else:
            MESES_SOFT = sorted(df_soft["mes"].unique())
            labels_soft = [pd.Timestamp(m).strftime("%b/%y").capitalize() for m in MESES_SOFT]

            # KPIs
            total_proj = df_soft["valor"].sum()
            total_real_s = df_real_soft["valor_realizado"].sum() if not df_real_soft.empty else 0
            desvio_s = total_real_s - total_proj
            k1, k2, k3 = st.columns(3)
            with k1:
                st.metric("Total Projetado 2026", f"R$ {fmt_brl(total_proj, 0)}")
            with k2:
                st.metric("Total Realizado (Software + Servidor)", f"R$ {fmt_brl(total_real_s, 0)}")
            with k3:
                delta_s = f"{'↑' if desvio_s > 0 else '↓'} R$ {fmt_brl(abs(desvio_s), 0)}"
                st.metric("Desvio", f"R$ {fmt_brl(abs(desvio_s), 0)}", delta=delta_s)

            st.divider()

            # Gráfico: projetado vs realizado por mês
            st.subheader("Projetado vs Realizado — Mensal")
            proj_by_month = df_soft.groupby("mes")["valor"].sum().reset_index()
            real_by_month = (df_real_soft.groupby("mes")["valor_realizado"].sum().reset_index()
                             if not df_real_soft.empty
                             else pd.DataFrame(columns=["mes", "valor_realizado"]))

            proj_vals_s = _month_series(proj_by_month.rename(columns={"valor": "v"}), "v", MESES_SOFT)
            real_vals_s = _month_series(real_by_month.rename(columns={"valor_realizado": "v"}), "v", MESES_SOFT)

            fig_s = go.Figure()
            fig_s.add_bar(x=labels_soft, y=proj_vals_s, name="Projetado", marker_color=PALETTE[4], opacity=0.85)
            fig_s.add_bar(x=labels_soft, y=real_vals_s, name="Realizado", marker_color=PALETTE[0], opacity=0.9)
            fig_s.update_layout(barmode="overlay", xaxis=dict(type="category"))
            st.plotly_chart(chart_layout(fig_s, height=320, legend_bottom=True), use_container_width=True)

            st.divider()

            # Tabela: software × mês
            st.subheader("Detalhe por Software")

            # Pivô: linha = software, colunas = meses + total
            pivot = (df_soft.groupby(["software", "mes"])["valor"]
                     .sum().reset_index()
                     .pivot(index="software", columns="mes", values="valor")
                     .fillna(0))
            pivot.columns = [pd.Timestamp(c).strftime("%b/%y").capitalize() for c in pivot.columns]
            pivot["Total"] = pivot.sum(axis=1)
            pivot = pivot.sort_values("Total", ascending=False)

            # Formatar como BRL
            pivot_fmt = pivot.copy()
            for col in pivot_fmt.columns:
                pivot_fmt[col] = pivot_fmt[col].apply(
                    lambda v: f"R$ {fmt_brl(v, 0)}" if v > 0 else "—"
                )

            pivot_fmt.index.name = "Software"
            st.dataframe(pivot_fmt, use_container_width=True)

    # ── TAB EQUIPE ───────────────────────────────────────────────────────────
    with tab_equipe:
        df_eq = get_equipe_for_page(page_key)
        df_eq_log = get_equipe_log(page_key)
        first_seen = get_equipe_first_seen(page_key)

        if df_eq.empty:
            no_data("Sem dados de equipe para este centro de custo.")
        else:
            MESES_EQ = sorted(df_eq["mes"].unique())
            labels_eq = [pd.Timestamp(m).strftime("%b/%y").capitalize() for m in MESES_EQ]

            # KPIs equipe
            mes_atual = MESES_EQ[min(2, len(MESES_EQ) - 1)]  # Mar/26 ou último disponível
            df_atual = df_eq[df_eq["mes"] == mes_atual]
            headcount = len(df_atual[df_atual["tipo"] == "pessoa"]["pessoa"].unique())
            custo_total = df_atual[df_atual["tipo"] == "pessoa"]["custo"].sum()
            n_repos = len(df_atual[df_atual["tipo"] == "reposicao"])
            n_novos = len(df_atual[df_atual["tipo"] == "novo"])

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("Headcount", headcount)
            with k2:
                st.metric("Custo Total (mês ref.)", f"R$ {fmt_brl(custo_total, 0)}")
            with k3:
                st.metric("🔄 Reposições previstas", n_repos)
            with k4:
                st.metric("🆕 Novas contratações", n_novos)

            st.divider()

            # Gráfico: custo mensal por tipo
            st.subheader("Custo Mensal da Equipe")
            custo_pessoa = []
            custo_repos  = []
            custo_novo   = []
            for m in MESES_EQ:
                dm = df_eq[df_eq["mes"] == m]
                custo_pessoa.append(dm[dm["tipo"] == "pessoa"]["custo"].sum())
                custo_repos.append(dm[dm["tipo"] == "reposicao"]["custo"].sum())
                custo_novo.append(dm[dm["tipo"] == "novo"]["custo"].sum())

            fig_eq = go.Figure()
            fig_eq.add_bar(x=labels_eq, y=custo_pessoa, name="Colaboradores",    marker_color=PALETTE[0])
            fig_eq.add_bar(x=labels_eq, y=custo_repos,  name="🔄 Reposição",      marker_color=PALETTE[3])
            fig_eq.add_bar(x=labels_eq, y=custo_novo,   name="🆕 Nova contratação", marker_color=PALETTE[1])
            fig_eq.update_layout(barmode="stack", xaxis=dict(type="category"))
            st.plotly_chart(chart_layout(fig_eq, height=340, legend_bottom=True), use_container_width=True)

            st.divider()

            # Tabela de colaboradores
            mes_ref_label = pd.Timestamp(mes_atual).strftime("%b/%y").capitalize()
            st.subheader(f"Colaboradores — {mes_ref_label}")

            last_mes  = pd.Timestamp(MESES_EQ[-1])

            rows = []
            for dept in sorted(df_eq["departamento"].unique()):
                df_dept = df_eq[df_eq["departamento"] == dept]
                # Todos que tiveram custo > 0 em algum mês
                pessoas_com_custo = (
                    df_dept.groupby(["pessoa", "tipo"])["custo"]
                    .sum().reset_index()
                )
                pessoas_com_custo = pessoas_com_custo[pessoas_com_custo["custo"] > 0]

                _TIPO_ORDER = {"pessoa": 0, "budget_livre": 1, "reposicao": 2, "novo": 3}
                pessoas_com_custo = pessoas_com_custo.copy()
                pessoas_com_custo["_ord"] = pessoas_com_custo["tipo"].map(_TIPO_ORDER).fillna(1)
                pessoas_com_custo = pessoas_com_custo.sort_values(["_ord", "pessoa"])

                for _, pt in pessoas_com_custo.iterrows():
                    pessoa = pt["pessoa"]
                    tipo   = pt["tipo"]
                    df_p   = df_dept[(df_dept["pessoa"] == pessoa) & (df_dept["tipo"] == tipo)]

                    meses_c = df_p[df_p["custo"] > 0]["mes"].sort_values()
                    ultimo  = pd.Timestamp(meses_c.iloc[-1])

                    real_first = first_seen.get((pessoa, dept, tipo))
                    inicio_str = real_first.strftime("%b/%y").capitalize() if real_first else "—"
                    fim_str    = ("—" if ultimo >= last_mes
                                  else ultimo.strftime("%b/%y").capitalize())

                    tipo_label = EQUIPE_TIPO_LABELS.get(tipo, "")
                    nome = f"{tipo_label} {pessoa}".strip() if tipo_label else pessoa

                    custo_ref = df_p[df_p["mes"] == mes_atual]["custo"].sum()
                    rows.append({
                        "Departamento": dept,
                        "Colaborador":  nome,
                        f"Custo ({mes_ref_label})": f"R$ {fmt_brl(custo_ref, 0)}" if custo_ref > 0 else "—",
                        "Início":  inicio_str,
                        "Fim":     fim_str,
                    })

            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            # Log de equipe
            if not df_eq_log.empty:
                st.divider()
                st.subheader("Log de Alterações — Equipe")
                ICONES = {"entrada": "🟢", "saida": "🔴", "custo_alterado": "🟡", "reposicao": "🔄"}
                for _, row in df_eq_log.iterrows():
                    icone = ICONES.get(row["evento"], "•")
                    st.markdown(
                        f"{icone} **{row['data']}** · `{row['departamento']}` · "
                        f"**{row['pessoa']}** — {row['detalhe']}"
                    )

    # ── TAB LOG ──────────────────────────────────────────────────────────────
    with tab_log:
        if df_log.empty:
            st.info("Nenhuma alteração registrada ainda. O log aparece quando houver mais de uma versão de projeção.", icon="ℹ️")
        else:
            st.markdown("Alterações identificadas entre versões de projeção:")
            for _, row in df_log.iterrows():
                mes_fmt = row.get("mes_label") or pd.Timestamp(row["mes"]).strftime("%b/%y").capitalize()
                antes   = fmt_brl(row["valor_previsto_antes"], 0)
                depois  = fmt_brl(row["valor_previsto_depois"], 0)
                var     = row["variacao"]
                sinal   = "🔴 ↑" if var > 0 else "🟢 ↓"
                st.markdown(
                    f"**{row['data_alteracao']}** — `{row['centro_custo']}` · "
                    f"**{row['categoria']}** · {mes_fmt}: "
                    f"R$ {antes} → R$ {depois} &nbsp; {sinal} R$ {fmt_brl(abs(var), 0)}",
                    unsafe_allow_html=True,
                )
                detalhe = row["detalhe"] if "detalhe" in row.index and row["detalhe"] else ""
                if detalhe:
                    st.markdown(
                        f"<span style='color:#a0a0a0; font-size:0.83rem; padding-left:1.4rem;'>"
                        f"↳ {detalhe}</span>",
                        unsafe_allow_html=True,
                    )
