"""
Módulo de Interface Web (cnpj_extractor.web)
===========================================
Contém componentes visuais, formatadores e visualizações do Streamlit.
"""

from .components import (
    formatar_cnpj,
    formatar_moeda,
    formatar_data,
    renderizar_badge_situacao,
    injetar_estilos_css,
)
from .views import (
    renderizar_sidebar,
    renderizar_busca_cnpj,
    renderizar_busca_filtros,
    render_app,
)

__all__ = [
    "formatar_cnpj",
    "formatar_moeda",
    "formatar_data",
    "renderizar_badge_situacao",
    "injetar_estilos_css",
    "renderizar_sidebar",
    "renderizar_busca_cnpj",
    "renderizar_busca_filtros",
    "render_app",
]
