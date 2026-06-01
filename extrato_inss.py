"""
extrato_inss.py
Extrai empréstimos ATIVOS + cartões (RMC/RCC) de extrato INSS PDF.
Usa pdfplumber.extract_tables() na pág. 3 para leitura estruturada.
"""

import re, sys, json
from pathlib import Path
import pdfplumber


def extrair_texto_pdf(caminho) -> list[str]:
    with pdfplumber.open(caminho) as pdf:
        return [pg.extract_text() or "" for pg in pdf.pages]


def extrair_tabelas_pdf(caminho) -> list:
    """Retorna tabelas de TODAS as páginas."""
    with pdfplumber.open(caminho) as pdf:
        return [pg.extract_tables() for pg in pdf.pages]


def brl(s: str) -> float:
    s = re.sub(r"[^\d,]", "", s or "0").replace(",", ".")
    return float(s) if s else 0.0


def limpar(s) -> str:
    """Remove \n extras e espaços múltiplos de células de tabela."""
    if not s: return ""
    return re.sub(r"\s+", " ", str(s)).strip()


# ── Dados gerais (pág. 1) ────────────────────────────────────────────────────

def extrair_dados_gerais(paginas):
    p = paginas[0]
    d = {}
    m = re.search(r"EMPRÉSTIMO CONSIGNADO\s+([\w\s]+?)\nBenefício", p)
    if m: d["titular"] = m.group(1).strip()
    for k, pat in [("numero_beneficio", r"Nº Benefício:\s*([\d.\-]+)"),
                   ("agencia",          r"Agência:\s*(\d+)"),
                   ("conta_corrente",   r"Conta Corrente:\s*(\d+)")]:
        m = re.search(pat, p)
        if m: d[k] = m.group(1).strip()
    m = re.search(r"Pago em:\s*(.+?)(?:\s+Não|\n)", p)
    if m: d["banco_pagamento"] = m.group(1).strip()
    return d


# ── Margem financeira (pág. 2) ───────────────────────────────────────────────

def extrair_margem(paginas):
    p = paginas[1]
    mg = {}
    for k, pat in [
        ("base_calculo",           r"BASE DE CÁLCULO\s+(R\$[\d.,]+)"),
        ("max_comprometimento",    r"MÁXIMO DE COMPROMETIMENTO PERMITIDO\s+(R\$[\d.,]+)"),
        ("total_comprometido",     r"TOTAL COMPROMETIDO\s+(R\$[\d.,]+)"),
        ("margem_consignavel_emp", r"MARGEM CONSIGNÁVEL\s+(R\$[\d.,]+)"),
        ("margem_utilizada_emp",   r"MARGEM UTILIZADA\*{0,2}\s+(R\$[\d.,]+)"),
        ("margem_disponivel_emp",  r"MARGEM DISPONÍVEL\*{0,1}\s+(R\$[\d.,]+)"),
        ("margem_extrapolada",     r"MARGEM EXTRAPOLADA\*{0,3}\s+(R\$[\d.,]+)"),
    ]:
        m = re.search(pat, p)
        if m: mg[k] = m.group(1).strip()
    return mg


# ── Empréstimos ATIVOS via extract_tables (pág. 3) ───────────────────────────
#
# Colunas da tabela (índices fixos após cabeçalho duplo de 2 linhas):
#   0=CONTRATO  1=BANCO  2=SITUAÇÃO  3=ORIGEM  4=DATA_INCL
#   5=INÍCIO    6=FIM    7=PARCELAS  8=PARCELA  9=EMPRESTADO
#   10=LIBERADO 11=IOF   12=CET_M   13=CET_A   14=JUROS_M
#   15=JUROS_A  16=PAGO  17=PRIM_DESC ...

COL = {
    "contrato": 0, "banco": 1, "situacao": 2,
    "inicio": 5,   "fim": 6,   "parcelas": 7,
    "parcela": 8,  "emprestado": 9, "liberado": 10,
    "iof": 11,     "cet_m": 12, "cet_a": 13,
    "juros_m": 14, "juros_a": 15, "pago": 16,
}


def _normalizar_valor(s: str) -> str:
    """'R$1.007 ,61' → 'R$1.007,61'"""
    if not s: return ""
    # juntar vírgula separada: "R$1.007 ,61" → "R$1.007,61"
    s = re.sub(r"\s+,", ",", s)
    # remover espaços internos que não sejam separadores de palavras
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extrair_emprestimos_ativos(paginas, tabelas_por_pag):
    """Usa tabela da página 3; fallback para texto se tabela não encontrada."""
    contratos = []

    # Página 3 (índice 2)
    tabelas_p3 = tabelas_por_pag[2] if len(tabelas_por_pag) > 2 else []
    tabela = None

    for t in tabelas_p3:
        # A tabela de empréstimos tem ≥ 10 colunas e pelo menos 1 linha com "Ativo"
        if not t or len(t[0]) < 10: continue
        if any("Ativo" in str(row[2] or "") for row in t if len(row) > 2):
            tabela = t
            break

    if tabela is None:
        return []  # fallback poderia ser adicionado aqui

    for row in tabela:
        if not row or len(row) < 10: continue
        sit = limpar(row[COL["situacao"]])
        if sit != "Ativo": continue

        c = {"situacao": "Ativo"}

        # Contrato: pode ser "901555\n57752" → juntar sem quebra
        contrato_raw = limpar(row[COL["contrato"]])
        c["contrato"] = contrato_raw.replace(" ", "")

        # Banco: "626 -\nBANCO\nC6\nCONSIG\nNADO S\nA" → limpar
        banco_raw = limpar(row[COL["banco"]])
        c["banco"] = banco_raw

        # Datas
        c["inicio_desconto"] = limpar(row[COL["inicio"]])
        c["fim_desconto"]    = limpar(row[COL["fim"]])

        # Qtde parcelas
        parc_raw = limpar(row[COL["parcelas"]])
        if parc_raw.isdigit():
            c["qtde_parcelas"] = int(parc_raw)

        # Valores
        def pegar_valor(col_idx):
            v = _normalizar_valor(limpar(row[col_idx])) if len(row) > col_idx else ""
            return f"R${re.sub(r'[^\d,]','',v).replace(' ','')}" if re.search(r'\d', v) else None

        for campo, col_idx in [("valor_parcela", COL["parcela"]),
                                ("valor_emprestado", COL["emprestado"]),
                                ("valor_liberado", COL["liberado"]),
                                ("iof", COL["iof"]),
                                ("valor_pago", COL["pago"])]:
            v = pegar_valor(col_idx)
            if v: c[campo] = v

        # Taxas
        for campo, col_idx in [("cet_mensal", COL["cet_m"]),
                                ("cet_anual", COL["cet_a"]),
                                ("taxa_juros_mensal", COL["juros_m"]),
                                ("taxa_juros_anual", COL["juros_a"])]:
            v = limpar(row[col_idx]) if len(row) > col_idx else ""
            if v and re.match(r"^\d{1,2},\d{2}$", v):
                c[campo] = v

        contratos.append(c)

    return contratos


# ── Cartões ATIVOS (RMC / RCC) ───────────────────────────────────────────────

def extrair_cartoes_ativos(paginas, tabelas_por_pag=None):
    """
    Extrai cartões RMC e RCC ativos E suspensos.
    Suspensos (Banco ou INSS) ainda comprometem a margem e devem ser incluídos.
    Usa extract_tables() para leitura estruturada — mais robusto que texto puro,
    pois o pdfplumber fragmenta as colunas em várias linhas no modo texto.
    """
    # Situações que comprometem a margem consignável
    SITUACOES_COMPROME = {"ativo", "suspenso", "suspenso banco", "suspenso inss"}

    rmc, rcc = [], []

    # Identificar páginas que contenham seção de cartão
    paginas_cartao = [i for i, pg in enumerate(paginas) if "CARTÃO DE CRÉDITO" in pg]

    for idx_pg in paginas_cartao:
        if tabelas_por_pag is None or idx_pg >= len(tabelas_por_pag):
            continue
        for tabela in tabelas_por_pag[idx_pg]:
            if not tabela: continue
            # Determinar modalidade: procurar cabeçalho "CARTÃO DE CRÉDITO - RMC/RCC"
            modalidade = None
            for row in tabela:
                celula = " ".join(str(c or "") for c in row).upper()
                if "CARTÃO DE CRÉDITO - RMC" in celula:
                    modalidade = "RMC"; break
                if "CARTÃO DE CRÉDITO - RCC" in celula:
                    modalidade = "RCC"; break

            if not modalidade: continue

            for row in tabela:
                if not row or len(row) < 4: continue
                # Colunas: 0=CONTRATO, 1=TIPO, 2=BANCO, 3=SITUAÇÃO, 4=ORIGEM, 5=DATA, 6=LIMITE, 7=RESERVADO
                contrato_raw = limpar(row[0])
                banco_raw    = limpar(row[2]) if len(row) > 2 else ""
                situacao_raw = limpar(row[3]).lower() if len(row) > 3 else ""

                # Ignorar linhas de cabeçalho e de desconto
                if not contrato_raw or contrato_raw.upper() in ("CONTRATO", "CARTÃO DE CRÉDITO - RMC", "CARTÃO DE CRÉDITO - RCC"):
                    continue
                if "desconto" in limpar(row[1] or "").lower():
                    continue
                # Só contratos que comprometem a margem
                if not any(s in situacao_raw for s in SITUACOES_COMPROME):
                    continue
                # Precisa ter valores monetários
                linha_str = " ".join(str(c or "") for c in row)
                if not re.search(r"R\$[\d.,]+", linha_str):
                    continue

                # Determinar situação legível
                if "suspenso" in situacao_raw:
                    situacao = "Suspenso"
                else:
                    situacao = "Ativo"

                c = {
                    "modalidade": modalidade,
                    "situacao":   situacao,
                    "contrato":   contrato_raw,
                    "banco":      banco_raw,
                }

                # Data de inclusão
                data_raw = limpar(row[5]) if len(row) > 5 else ""
                if re.match(r"\d{2}/\d{2}/\d{2}", data_raw):
                    c["data_inclusao"] = data_raw

                # Limite e reservado
                vals = re.findall(r"R\$[\d.,]+", linha_str)
                if vals:           c["limite_cartao"]        = vals[0]
                if len(vals) >= 2: c["reservado_atualizado"] = vals[1]

                if modalidade == "RMC":
                    rmc.append(c)
                else:
                    rcc.append(c)

    return {"rmc": rmc, "rcc": rcc}


# ── Consolidação ─────────────────────────────────────────────────────────────

def processar_extrato(caminho) -> dict:
    paginas      = extrair_texto_pdf(caminho)
    tabelas      = extrair_tabelas_pdf(caminho)
    dados        = extrair_dados_gerais(paginas)
    margem       = extrair_margem(paginas)
    emprestimos  = extrair_emprestimos_ativos(paginas, tabelas)
    cartoes      = extrair_cartoes_ativos(paginas, tabelas)
    return {
        "dados_gerais":       dados,
        "margem_financeira":  margem,
        "emprestimos_ativos": emprestimos,
        "cartoes_ativos":     cartoes,
        "resumo": {
            "total_emprestimos_ativos": len(emprestimos),
            "total_cartoes_rmc_ativos": len(cartoes["rmc"]),
            "total_cartoes_rcc_ativos": len(cartoes["rcc"]),
        },
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extrato_inss.py <arquivo.pdf>"); sys.exit(1)
    r = processar_extrato(sys.argv[1])
    print(json.dumps(r, ensure_ascii=False, indent=2))
