"""
Componentes e Formatadores Visuais da Interface (cnpj_extractor.web.components)
===============================================================================
Funções de formatação segura de CNPJ, valores monetários e datas para exibição.
"""

from typing import Optional


def formatar_cnpj(cnpj_limpo: Optional[str]) -> str:
    """Formata CNPJ básico (8 dígitos) ou completo (14 dígitos)."""
    if not cnpj_limpo:
        return "-"
    d = "".join(filter(str.isdigit, str(cnpj_limpo)))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    elif len(d) == 8:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}"
    return str(cnpj_limpo)


def formatar_moeda(valor: Optional[float]) -> str:
    """Formata valor numérico para padrão monetário brasileiro (R$)."""
    if valor is None:
        return "R$ 0,00"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_data(data_str: Optional[str]) -> str:
    """Formata data no formato AAAAMMDD para DD/MM/AAAA."""
    if not data_str:
        return "-"
    d = str(data_str).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[6:8]}/{d[4:6]}/{d[:4]}"
    return d
