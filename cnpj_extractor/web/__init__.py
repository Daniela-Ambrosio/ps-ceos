"""
Módulo de Interface Web (cnpj_extractor.web)
===========================================
Contém componentes visuais, formatadores e visualizações nativas do Streamlit.
"""

from .components import (
    formatar_cnpj,
    formatar_data,
    formatar_moeda,
)
from .views import (
    render_app,
    renderizar_busca_cnpj,
    renderizar_busca_filtros,
    renderizar_sidebar,
)

__all__ = [
    "formatar_cnpj",
    "formatar_moeda",
    "formatar_data",
    "renderizar_sidebar",
    "renderizar_busca_cnpj",
    "renderizar_busca_filtros",
    "render_app",
]
