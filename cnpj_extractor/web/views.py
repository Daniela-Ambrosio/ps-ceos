"""
Visualizações e Telas da Interface Web (cnpj_extractor.web.views)
=================================================================
"""

try:
    import streamlit as st
except ImportError:
    st = None

from ..config import Config
from ..database import DatabaseManager
from .components import (
    formatar_cnpj,
    formatar_moeda,
    formatar_data,
    renderizar_badge_situacao,
    injetar_estilos_css,
)


def get_db_manager() -> DatabaseManager:
    cfg = Config.carregar()
    return DatabaseManager(cfg.db_path)


if st is not None:
    get_db_manager = st.cache_resource(get_db_manager)


def renderizar_sidebar(db: DatabaseManager) -> None:
    if st is None:
        return
    with st.sidebar:
        st.markdown("### 🏢 Base de Dados Local")
        if db.db_path.exists():
            tamanho_mb = db.db_path.stat().st_size / (1024 * 1024)
            st.success(f"Banco Conectado ({tamanho_mb:.1f} MB)")
            try:
                total_emp = db.contar_linhas("empresas")
                total_est = db.contar_linhas("estabelecimentos")
                total_soc = db.contar_linhas("socios")
                st.metric(label="Empresas Cadastradas", value=f"{total_emp:,}")
                st.metric(label="Estabelecimentos", value=f"{total_est:,}")
                st.metric(label="Sócios / Administradores", value=f"{total_soc:,}")
            except Exception:
                st.info("Tabelas em processo de carga.")
        else:
            st.warning(f"Banco de dados não encontrado em `{db.db_path}`.")
            st.info("Execute a ingestão para carregar dados.")
        st.markdown("---")
        st.caption("🔒 Consultas com Prepared Statements seguros contra SQL Injection.")


def renderizar_busca_cnpj(db: DatabaseManager) -> None:
    if st is None:
        return
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        cnpj_input = st.text_input("Digite o CNPJ da empresa:", placeholder="Ex: 00.000.000/0001-91 ou números...", key="busca_cnpj_input")
    with col_btn:
        st.write("")
        st.write("")
        btn_buscar_cnpj = st.button("Buscar Empresa", type="primary", use_container_width=True)

    if (btn_buscar_cnpj or cnpj_input) and cnpj_input.strip():
        with st.spinner("Consultando dados da empresa..."):
            empresa = db.buscar_empresa_detalhada(cnpj_input)

        if not empresa:
            st.warning(f"❌ Nenhuma empresa encontrada com o CNPJ: `{cnpj_input}`.")
        else:
            estabelecimentos = empresa.get("estabelecimentos", [])
            matriz = next((e for e in estabelecimentos if e.get("identificador_matriz_filial") == "1"), None)
            if not matriz and estabelecimentos:
                matriz = estabelecimentos[0]

            situacao_texto = matriz.get("situacao_descricao", "Ativa") if matriz else "Ativa"
            badge_html = renderizar_badge_situacao(situacao_texto)

            razao = empresa.get("razao_social", "")
            cnpj_basico_fmt = formatar_cnpj(empresa.get("cnpj_basico", ""))
            nat_desc = empresa.get("natureza_juridica_descricao") or empresa.get("codigo_natureza_juridica") or "-"
            cap_fmt = formatar_moeda(empresa.get("capital_social", 0.0))
            porte_fmt = empresa.get("porte_descricao", "Demais")
            simples_fmt = "✅ Optante" if empresa.get("opcao_simples") == "S" else "❌ Não Optante"
            mei_fmt = "✅ Sim" if empresa.get("opcao_mei") == "S" else "❌ Não"

            st.markdown(
                f"""
                <div class="empresa-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h2 style="margin: 0; color: #0F172A;">{razao}</h2>
                        {badge_html}
                    </div>
                    <p style="color: #64748B; margin-top: 4px; margin-bottom: 16px;">
                        CNPJ Básico: <strong>{cnpj_basico_fmt}</strong> &nbsp;|&nbsp; 
                        Natureza: <strong>{nat_desc}</strong>
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                        <div><div class="metric-title">Capital Social</div><div class="metric-value">{cap_fmt}</div></div>
                        <div><div class="metric-title">Porte da Empresa</div><div class="metric-value">{porte_fmt}</div></div>
                        <div><div class="metric-title">Simples Nacional</div><div class="metric-value">{simples_fmt}</div></div>
                        <div><div class="metric-title">MEI</div><div class="metric-value">{mei_fmt}</div></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            sub_est, sub_soc, sub_cnae = st.tabs([
                f"📍 Estabelecimentos ({len(estabelecimentos)})",
                f"👥 Quadro Societário ({len(empresa.get('socios', []))})",
                "📊 Atividades Econômicas (CNAE)",
            ])

            with sub_est:
                if not estabelecimentos:
                    st.info("Nenhum estabelecimento registrado.")
                else:
                    for est in estabelecimentos:
                        with st.expander(f"🏢 {est['tipo_unidade']} - CNPJ: {est['cnpj_completo']} | {est.get('municipio_nome', '')}-{est.get('uf', '')} ({est['situacao_descricao']})", expanded=(est.get("identificador_matriz_filial") == "1")):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown(f"**Nome Fantasia:** {est.get('nome_fantasia') or '-'}")
                                st.markdown(f"**Situação:** {est['situacao_descricao']} (desde {formatar_data(est.get('data_situacao_cadastral'))})")
                                st.markdown(f"**Data de Abertura:** {formatar_data(est.get('data_inicio_atividade'))}")
                            with c2:
                                end_str = f"{est.get('tipo_logradouro', '')} {est.get('logradouro', '')}, {est.get('numero', '')} {est.get('complemento', '')}".strip()
                                st.markdown(f"**Endereço:** {end_str or '-'}")
                                st.markdown(f"**Cidade/UF:** {est.get('municipio_nome', '-')}/{est.get('uf', '-')}")
                                tel = f"({est.get('ddd_1', '')}) {est.get('telefone_1', '')}".strip()
                                st.markdown(f"**Telefone:** {tel if len(tel) > 3 else '-'}")
                                st.markdown(f"**E-mail:** {est.get('correio_eletronico') or '-'}")

            with sub_soc:
                socios = empresa.get("socios", [])
                if not socios:
                    st.info("Nenhum sócio registrado.")
                else:
                    for s in socios:
                        nome_s = s.get("nome_socio_razao_social", "")
                        qualif_s = s.get("qualificacao_socio_descricao") or s.get("qualificacao_socio") or "Sócio"
                        tipo_s = s.get("tipo_socio_descricao", "Pessoa")
                        doc_s = s.get("cnpj_cpf_socio") or "***"
                        data_ent = formatar_data(s.get("data_entrada_sociedade"))
                        st.markdown(
                            f"""
                            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;">
                                <div style="font-weight: 600; font-size: 1.05rem; color: #1E293B;">👤 {nome_s}</div>
                                <div style="color: #64748B; font-size: 0.9rem; margin-top: 4px;">
                                    Qualificação: <strong>{qualif_s}</strong> &nbsp;|&nbsp;
                                    Tipo: <strong>{tipo_s}</strong> &nbsp;|&nbsp;
                                    Doc: <strong>{doc_s}</strong> &nbsp;|&nbsp;
                                    Entrada: <strong>{data_ent}</strong>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

            with sub_cnae:
                if matriz:
                    cnae_cod = matriz.get("cnae_fiscal_principal", "-")
                    cnae_desc = matriz.get("cnae_principal_descricao") or "Não informado"
                    st.markdown("### Atividade Principal (CNAE):")
                    st.info(f"**Código:** `{cnae_cod}` — **Descrição:** {cnae_desc}")


def renderizar_busca_filtros(db: DatabaseManager) -> None:
    if st is None:
        return
    st.markdown("##### Filtre empresas por Razão Social, Nome Fantasia ou Localidade:")
    c_termo, c_uf, c_sit = st.columns([3, 1, 1])
    with c_termo:
        termo_busca = st.text_input("Razão Social ou Nome Fantasia:", placeholder="Ex: BANCO DO BRASIL, COMERCIO...", key="termo_filtro")
    with c_uf:
        ufs = ["TODOS", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
        uf_sel = st.selectbox("Estado (UF):", ufs, index=0)
    with c_sit:
        situacoes = {"TODOS": "TODOS", "Ativa": "02", "Baixada": "08", "Inapta": "04", "Suspensa": "03"}
        sit_sel = st.selectbox("Situação Cadastral:", list(situacoes.keys()), index=0)

    btn_filtrar = st.button("🔍 Aplicar Filtros", type="primary")

    if btn_filtrar or termo_busca:
        with st.spinner("Pesquisando registros..."):
            resultados = db.buscar_empresas_por_filtros(termo_busca=termo_busca, uf=uf_sel, situacao=situacoes[sit_sel], limite=50)

        if not resultados:
            st.warning("Nenhuma empresa encontrada.")
        else:
            st.success(f"Encontradas {len(resultados)} empresas:")
            import pandas as pd
            df_exibicao = pd.DataFrame([
                {
                    "CNPJ": r["cnpj_formatado"],
                    "Razão Social": r["razao_social"],
                    "Nome Fantasia": r.get("nome_fantasia") or "-",
                    "UF": r.get("uf") or "-",
                    "Município": r.get("municipio") or "-",
                    "Situação": r["situacao_texto"],
                    "CNAE Principal": f"{r.get('cnae_fiscal_principal', '')} - {r.get('cnae_descricao', '')}",
                    "Capital Social": formatar_moeda(r.get("capital_social", 0.0)),
                }
                for r in resultados
            ])
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)


def render_app() -> None:
    if st is None:
        raise ImportError("O Streamlit não está instalado neste ambiente. Instale com: pip install streamlit")
    st.set_page_config(
        page_title="Consulta de CNPJ - Receita Federal",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    injetar_estilos_css()
    db = get_db_manager()
    renderizar_sidebar(db)

    st.markdown('<div class="main-header">Consulta de CNPJ - Receita Federal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Pesquise empresas, filiais e sócios na base oficial.</div>', unsafe_allow_html=True)

    aba_cnpj, aba_filtros = st.tabs(["🔍 Consulta por CNPJ", "🎯 Busca por Nome e Filtros"])
    with aba_cnpj:
        renderizar_busca_cnpj(db)
    with aba_filtros:
        renderizar_busca_filtros(db)
