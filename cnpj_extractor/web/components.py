"""
Componentes e Formatadores Visuais da Interface (cnpj_extractor.web.components)
===============================================================================
"""

try:
    import streamlit as st
except ImportError:
    st = None


def formatar_cnpj(cnpj_limpo: str) -> str:
    d = "".join(filter(str.isdigit, str(cnpj_limpo)))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    elif len(d) == 8:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}"
    return str(cnpj_limpo)


def formatar_moeda(valor: float) -> str:
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def formatar_data(data_str: str) -> str:
    if data_str and len(str(data_str)) == 8 and str(data_str).isdigit():
        d = str(data_str)
        return f"{d[6:8]}/{d[4:6]}/{d[:4]}"
    return str(data_str) if data_str else "-"


def renderizar_badge_situacao(situacao: str) -> str:
    sit_lower = (situacao or "").lower()
    if "ativa" in sit_lower:
        return f'<span class="badge-ativa">🟢 {situacao}</span>'
    elif "baixada" in sit_lower:
        return f'<span class="badge-baixada">🔴 {situacao}</span>'
    else:
        return f'<span class="badge-inapta">🟡 {situacao}</span>'


def injetar_estilos_css() -> None:
    if st is None:
        return
    st.markdown(
        """
        <style>
        .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0.2rem; }
        .sub-header { font-size: 1rem; color: #64748B; margin-bottom: 1.5rem; }
        .badge-ativa { background-color: #DEF7EC; color: #03543F; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; display: inline-block; }
        .badge-baixada { background-color: #FDE8E8; color: #9B1C1C; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; display: inline-block; }
        .badge-inapta { background-color: #FEF08A; color: #854D0E; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; display: inline-block; }
        .empresa-card { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .metric-title { font-size: 0.8rem; color: #64748B; text-transform: uppercase; font-weight: 600; }
        .metric-value { font-size: 1.1rem; font-weight: 600; color: #0F172A; }
        </style>
        """,
        unsafe_allow_html=True,
    )
