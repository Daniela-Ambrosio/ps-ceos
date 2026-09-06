"""
Visualizações e Telas da Interface Web (cnpj_extractor.web.views)
=================================================================
Interface gráfica nativa do Streamlit para consulta de CNPJs, estabelecimentos
e quadro de sócios (QSA) conectados ao PostgreSQL.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import streamlit as st
except ImportError:
    st = None

from ..config import Config
from ..database import DatabaseManager
from .components import (
    formatar_cnpj,
    formatar_data,
    formatar_moeda,
)


def get_db_manager() -> DatabaseManager:
    cfg = Config.carregar()
    return DatabaseManager(cfg)


if st is not None:
    get_db_manager = st.cache_resource(get_db_manager)


def renderizar_sidebar(db: DatabaseManager) -> None:
    if st is None:
        return
    # Cached statistics for sidebar
    @st.cache_data(ttl=300)
    def get_estatisticas_gerais(_db) -> tuple:
        """Return row counts for empresas, estabelecimentos, socios."""
        return (
            _db.contar_linhas("empresas"),
            _db.contar_linhas("estabelecimentos"),
            _db.contar_linhas("socios"),
        )

    with st.sidebar:
        st.subheader("🏢 Base de Dados PostgreSQL")
        try:
            total_emp, total_est, total_soc = get_estatisticas_gerais(db)
            st.success(f"PostgreSQL Conectado ({db.config.postgres_host}:{db.config.postgres_port})")
            st.metric(label="Empresas Cadastradas", value=f"{total_emp:,}")
            st.metric(label="Estabelecimentos", value=f"{total_est:,}")
            st.metric(label="Sócios / Administradores", value=f"{total_soc:,}")
        except Exception:
            st.warning("Conectando ao PostgreSQL...")
            st.caption(f"Host: {db.config.postgres_host}:{db.config.postgres_port}/{db.config.postgres_db}")
        st.divider()


def renderizar_busca_cnpj(db: DatabaseManager) -> None:
    if st is None:
        return
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        cnpj_input = st.text_input(
            "Digite o CNPJ da empresa:",
            placeholder="Ex: 00.000.000/0001-91 ou números...",
            key="busca_cnpj_input",
        )
    with col_btn:
        st.write("")
        st.write("")
        btn_buscar_cnpj = st.button("Buscar Empresa", type="primary", use_container_width=True)

    if btn_buscar_cnpj and cnpj_input.strip():
        with st.spinner("Consultando dados da empresa no PostgreSQL..."):
            empresa = db.buscar_empresa_detalhada(cnpj_input)

        if not empresa:
            st.warning(f"❌ Nenhuma empresa encontrada com o CNPJ: `{cnpj_input}`.")
        else:
            estabelecimentos = empresa.get("estabelecimentos", [])
            matriz = next(
                (e for e in estabelecimentos if str(e.get("identificador_matriz_filial")) == "1"),
                None,
            )
            if not matriz and estabelecimentos:
                matriz = estabelecimentos[0]

            situacao_texto = matriz.get("situacao_descricao", "Ativa") if matriz else "Ativa"
            razao = empresa.get("razao_social", "Empresa sem Razão Social")
            cnpj_basico_fmt = formatar_cnpj(empresa.get("cnpj_basico", ""))
            nat_desc = (
                empresa.get("natureza_juridica_descricao")
                or empresa.get("codigo_natureza_juridica")
                or "-"
            )
            cap_fmt = formatar_moeda(empresa.get("capital_social"))
            porte_fmt = empresa.get("porte_descricao", "Demais")
            simples_fmt = "Optante" if empresa.get("opcao_simples") == "S" else "Não Optante"
            mei_fmt = "Sim" if empresa.get("opcao_mei") == "S" else "Não"

            # Card Principal da Empresa utilizando componentes nativos
            with st.container(border=True):
                col_titulo, col_status = st.columns([3, 1])
                with col_titulo:
                    st.subheader(razao)
                    st.caption(f"CNPJ Básico: **{cnpj_basico_fmt}** | Natureza Jurídica: **{nat_desc}**")
                with col_status:
                    sit_lower = situacao_texto.lower()
                    if "ativa" in sit_lower:
                        st.success(f"🟢 {situacao_texto}")
                    elif "baixada" in sit_lower:
                        st.error(f"🔴 {situacao_texto}")
                    else:
                        st.warning(f"🟡 {situacao_texto}")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric(label="Capital Social", value=cap_fmt)
                m2.metric(label="Porte da Empresa", value=porte_fmt)
                m3.metric(label="Simples Nacional", value=simples_fmt)
                m4.metric(label="MEI", value=mei_fmt)

            # Abas de detalhamento
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
                        exp_title = (
                            f"🏢 {est['tipo_unidade']} - CNPJ: {est['cnpj_completo']} | "
                            f"{est.get('municipio_nome', '')}-{est.get('uf', '')} ({est['situacao_descricao']})"
                        )
                        with st.expander(exp_title, expanded=(str(est.get("identificador_matriz_filial")) == "1")):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.write(f"**Nome Fantasia:** {est.get('nome_fantasia') or '-'}")
                                st.write(
                                    f"**Situação:** {est['situacao_descricao']} (desde {formatar_data(est.get('data_situacao_cadastral'))})"
                                )
                                st.write(
                                    f"**Data de Abertura:** {formatar_data(est.get('data_inicio_atividade'))}"
                                )
                            with c2:
                                end_str = f"{est.get('tipo_logradouro', '')} {est.get('logradouro', '')}, {est.get('numero', '')} {est.get('complemento', '')}".strip()
                                st.write(f"**Endereço:** {end_str or '-'}")
                                st.write(
                                    f"**Cidade/UF:** {est.get('municipio_nome', '-')}/{est.get('uf', '-')}"
                                )
                                tel = f"({est.get('ddd_1', '')}) {est.get('telefone_1', '')}".strip()
                                st.write(f"**Telefone:** {tel if len(tel) > 3 else '-'}")
                                st.write(f"**E-mail:** {est.get('correio_eletronico') or '-'}")

            with sub_soc:
                socios = empresa.get("socios", [])
                if not socios:
                    st.info("Nenhum sócio registrado.")
                else:
                    for s in socios:
                        nome_s = s.get("nome_socio_razao_social", "")
                        qualif_s = (
                            s.get("qualificacao_socio_descricao")
                            or s.get("qualificacao_socio")
                            or "Sócio"
                        )
                        tipo_s = s.get("tipo_socio_descricao", "Pessoa")
                        doc_s = s.get("cnpj_cpf_socio") or "***"
                        data_ent = formatar_data(s.get("data_entrada_sociedade"))

                        with st.container(border=True):
                            st.markdown(f"**👤 {nome_s}**")
                            st.caption(
                                f"Qualificação: **{qualif_s}** | Tipo: **{tipo_s}** | "
                                f"Documento: **{doc_s}** | Entrada na Sociedade: **{data_ent}**"
                            )

            with sub_cnae:
                if matriz:
                    cnae_cod = matriz.get("cnae_fiscal_principal", "-")
                    cnae_desc = matriz.get("cnae_principal_descricao") or "Não informado"
                    st.subheader("Atividade Econômica Principal (CNAE):")
                    st.info(f"**Código:** `{cnae_cod}` — **Descrição:** {cnae_desc}")


def renderizar_busca_filtros(db: DatabaseManager) -> None:
    if st is None:
        return
    st.write("##### Filtre empresas por Razão Social, Nome Fantasia ou Localidade:")

    # Caching helpers for CNAE and Municípios
    @st.cache_data(ttl=300)
    def get_cnaes() -> List[Tuple[str, str]]:
        return db.listar_cnaes()

    @st.cache_data(ttl=300)
    def get_municipios(uf: Optional[str] = None) -> List[Tuple[str, str]]:
        return db.listar_municipios(uf)

    # First row filters: termo, UF, CNAE, Situação
    c_termo, c_uf, c_cnae, c_sit = st.columns([3, 1, 1, 1])
    with c_termo:
        termo_busca = st.text_input(
            "Razão Social ou Nome Fantasia:",
            placeholder="Ex: BANCO DO BRASIL, COMERCIO...",
            key="termo_filtro",
        )
    with c_uf:
        ufs = [
            "TODOS", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
            "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
            "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        ]
        uf_sel = st.selectbox("Estado (UF):", ufs, index=0)
    with c_cnae:
        cnaes = ["TODOS"] + [f"{c[0]} - {c[1]}" for c in get_cnaes()]
        cnae_sel = st.selectbox("CNAE Principal:", cnaes, index=0)
    with c_sit:
        situacoes = {
            "TODOS": "TODOS",
            "Ativa": "02",
            "Baixada": "08",
            "Inapta": "04",
            "Suspensa": "03",
        }
        sit_sel = st.selectbox("Situação Cadastral:", list(situacoes.keys()), index=0)

    # Second row: Município (depends on UF)
    c_municipio = st.columns([1])
    with c_municipio[0]:
        municipios = ["TODOS"] + [
            f"{m[0]} - {m[1]}" for m in get_municipios(None if uf_sel == "TODOS" else uf_sel)
        ]
        municipio_sel = st.selectbox(
            "Município:",
            municipios,
            index=0,
            key=f"municipio_{uf_sel}",
        )

    btn_filtrar = st.button("🔍 Aplicar Filtros", type="primary")

    if btn_filtrar:
        # Extract codes, ignoring "TODOS"
        cnae_codigo = None if cnae_sel == "TODOS" else cnae_sel.split(" - ")[0]
        municipio_codigo = None if municipio_sel == "TODOS" else municipio_sel.split(" - ")[0]
        with st.spinner("Pesquisando registros no PostgreSQL..."):
            resultados = db.buscar_empresas_por_filtros(
                termo_busca=termo_busca,
                uf=uf_sel,
                situacao=situacoes[sit_sel],
                cnae_codigo=cnae_codigo,
                municipio_codigo=municipio_codigo,
                limite=50,
            )

        if not resultados:
            st.warning("Nenhuma empresa encontrada com os filtros informados.")
        else:
            st.success(f"Encontradas {len(resultados)} empresas:")
            if pd is not None:
                df_exibicao = pd.DataFrame([
                    {
                        "CNPJ": r["cnpj_formatado"],
                        "Razão Social": r["razao_social"],
                        "Nome Fantasia": r.get("nome_fantasia") or "-",
                        "UF": r.get("uf") or "-",
                        "Município": r.get("municipio") or "-",
                        "Situação": r["situacao_texto"],
                        "CNAE Principal": f"{r.get('cnae_fiscal_principal', '')} - {r.get('cnae_descricao', '')}",
                        "Capital Social": formatar_moeda(r.get("capital_social")),
                    }
                    for r in resultados
                ])
                st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
            else:
                st.table(resultados)


def render_app() -> None:
    if st is None:
        raise ImportError("O Streamlit não está instalado neste ambiente. Instale com: pip install streamlit")
    st.set_page_config(
        page_title="Consulta de CNPJ - Receita Federal (PostgreSQL)",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    db = get_db_manager()
    renderizar_sidebar(db)

    st.title("🏢 Consulta de CNPJ - Receita Federal")
    st.caption("Pesquise empresas, filiais e sócios na base oficial integrada ao PostgreSQL.")

    aba_cnpj, aba_filtros = st.tabs(["🔍 Consulta por CNPJ", "🎯 Busca por Nome e Filtros"])
    with aba_cnpj:
        renderizar_busca_cnpj(db)
    with aba_filtros:
        renderizar_busca_filtros(db)

