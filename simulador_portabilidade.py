"""
simulador_portabilidade.py
Simulador de Portabilidade FACTA com leitura automática de extrato INSS (PDF).
Todas as regras de negócio editáveis estão em config.py.
"""

import re
from datetime import date
import pandas as pd
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from extrato_inss import processar_extrato, brl
from config import (
    FATORES, FATORES_CARENCIA,
    FAIXAS, FAIXAS_CARENCIA,
    BANCOS_BLOQUEADOS, MINIMO_PARCELAS,
    TROCO_MINIMO, DESCONTO_SD_SEM_TAXA,
)

# ═══════════════════════════════════════════════════════════════
# HELPERS — BANCO
# ═══════════════════════════════════════════════════════════════

def extrair_codigo_banco(banco_str: str) -> str:
    m = re.match(r"(\d{3})", (banco_str or "").strip())
    return m.group(1) if m else ""


def _match_banco(cod: str, nome: str, regras: list) -> dict | None:
    cod  = cod.upper().strip()
    nome = nome.upper().strip()
    for regra in regras:
        for c in regra.get("codigos", []):
            if cod == c.upper():
                return regra
        for n in regra.get("nomes", []):
            if n.upper() in nome:
                return regra
    return None


def banco_bloqueado(banco_str: str) -> dict | None:
    cod  = extrair_codigo_banco(banco_str)
    return _match_banco(cod, banco_str, BANCOS_BLOQUEADOS)


def regra_minimo_parcelas(banco_str: str) -> dict:
    cod = extrair_codigo_banco(banco_str)
    for regra in MINIMO_PARCELAS[:-1]:
        if _match_banco(cod, banco_str, [regra]):
            return regra
    return MINIMO_PARCELAS[-1]


# ═══════════════════════════════════════════════════════════════
# HELPERS — PARCELAS E SALDO DEVEDOR
# ═══════════════════════════════════════════════════════════════

def calcular_parcelas_pagas(inicio_desconto: str) -> int:
    """Meses decorridos entre início do desconto e hoje (inclusive)."""
    if not inicio_desconto:
        return 0
    try:
        mes, ano = map(int, inicio_desconto.split("/"))
        hoje = date.today()
        return (hoje.year - ano) * 12 + (hoje.month - mes) + 1
    except Exception:
        return 0


def calcular_saldo_devedor(emp: dict, pagas: int) -> tuple[float, str]:
    """
    Retorna (saldo_devedor, metodo_usado).

    Métodos:
      'price'    — fórmula Price com taxa do extrato (mais preciso)
      'estimado' — PMT × n_restantes × (1 - DESCONTO_SD_SEM_TAXA) (fallback)
    """
    pmt          = brl(emp.get("valor_parcela", "R$0"))
    qtde         = emp.get("qtde_parcelas", 0)
    taxa_str     = emp.get("taxa_juros_mensal", "")
    n_restantes  = max(qtde - pagas, 0)

    if n_restantes == 0:
        return 0.0, "price"

    # ── Tenta fórmula Price se tiver taxa ────────────────────────────────────
    if taxa_str:
        try:
            i  = float(taxa_str.replace(",", ".")) / 100
            sd = pmt * (1 - (1 + i) ** (-n_restantes)) / i
            return round(sd, 2), "price"
        except Exception:
            pass

    # ── Fallback: PMT × n_restantes com desconto médio ───────────────────────
    sd = pmt * n_restantes * (1 - DESCONTO_SD_SEM_TAXA)
    return round(sd, 2), "estimado"


# ═══════════════════════════════════════════════════════════════
# HELPERS — SIMULAÇÃO FACTA
# ═══════════════════════════════════════════════════════════════

def tabelas_disponiveis(bruto: float, faixas: list) -> list:
    for vmin, vmax, tabs in faixas:
        if vmin <= bruto <= vmax:
            return tabs
    return []


def simular(parcela_calc: float, saldo_devedor: float,
            faixas: list, fatores: dict) -> pd.DataFrame:
    rows = []
    for tabela, fator in fatores.items():
        bruto = parcela_calc / fator if fator else 0
        if tabela not in tabelas_disponiveis(bruto, faixas):
            continue
        troco = bruto - saldo_devedor
        if troco > TROCO_MINIMO:
            rows.append({"Tabela": tabela, "Bruto": bruto, "Troco": troco})
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════
# HELPERS — UI
# ═══════════════════════════════════════════════════════════════

def fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def card(label, valor, cor="#1a4a8c", bg="#eef3fb", borda="#1a4a8c"):
    return f"""
    <div style="background:{bg};border-left:5px solid {borda};
        padding:.65rem 1rem;border-radius:8px;margin-bottom:.3rem">
        <div style="font-size:.75rem;color:#555;margin-bottom:2px">{label}</div>
        <div style="font-size:1.1rem;font-weight:700;color:{cor}">{valor}</div>
    </div>"""


BADGE_STYLES = {
    "ok":        ("#198754", "#f0fff4", "#19875466"),
    "negativo":  ("#dc3545", "#fff0f0", "#dc354566"),
    "aviso":     ("#b45309", "#fff8e1", "#b4530966"),
    "bloqueado": ("#6c757d", "#f5f5f5", "#6c757d66"),
}


def badge(icone: str, texto: str, tooltip: str, tipo: str = "ok") -> str:
    cor, bg, borda = BADGE_STYLES.get(tipo, BADGE_STYLES["ok"])
    return f"""
    <span title="{tooltip}"
          style="background:{bg};color:{cor};border:1px solid {borda};
                 padding:4px 12px;border-radius:20px;font-size:.82rem;
                 font-weight:700;cursor:help;white-space:nowrap">
        {icone} {texto}
    </span>"""


def exibir_df(df: pd.DataFrame):
    if df.empty:
        st.info(f"Nenhuma tabela com troco acima de {fmt(TROCO_MINIMO)}.")
        return
    d = df.copy()
    d["Bruto"] = d["Bruto"].apply(fmt)
    d["Troco"] = d["Troco"].apply(fmt)
    st.dataframe(
        d, use_container_width=True, hide_index=True,
        column_config={
            "Tabela": st.column_config.TextColumn("Tabela",     width="medium"),
            "Bruto":  st.column_config.TextColumn("Bruto (R$)", width="medium"),
            "Troco":  st.column_config.TextColumn("Troco (R$)", width="medium"),
        },
    )


# ═══════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO DOS CONTRATOS
# ═══════════════════════════════════════════════════════════════

PRIORIDADE = {"viavel": 0, "sem_troco": 1, "parcelas": 2, "bloqueado": 3}


def classificar_contrato(emp: dict, saldo_margem: float,
                          aplicar_abate: bool,
                          saldo_devedor_manual: float | None = None,
                          parcela_override: float | None = None) -> dict:
    """
    Retorna dict com:
        status           : 'viavel' | 'sem_troco' | 'parcelas' | 'bloqueado'
        motivo           : str (tooltip do badge)
        parcela_calc     : float
        saldo_devedor    : float (calculado automaticamente)
        metodo_sd        : str ('price' | 'estimado')
        parcelas_pagas   : int
        minimo_exigido   : int
        df_normal        : DataFrame
        df_carencia      : DataFrame
    """
    banco_str    = emp.get("banco", "")
    parcela_orig = brl(emp.get("valor_parcela", "R$0"))
    # Usa parcelas pagas efetivas se o usuário editou parcelas restantes
    if "_pagas_efetivas" in emp:
        pagas = emp["_pagas_efetivas"]
    else:
        pagas = calcular_parcelas_pagas(emp.get("inicio_desconto", ""))
    sd_auto, metodo = calcular_saldo_devedor(emp, pagas)

    # Saldo devedor: usa o manual se fornecido, senão o calculado
    sd = saldo_devedor_manual if saldo_devedor_manual is not None else sd_auto

    base = {
        "parcelas_pagas": pagas,
        "saldo_devedor":  sd_auto,
        "metodo_sd":      metodo,
        "parcela_calc":   0.0,
        "df_normal":      pd.DataFrame(),
        "df_carencia":    pd.DataFrame(),
    }

    # ── 1. Banco bloqueado ───────────────────────────────────────────────────
    bloqueio = banco_bloqueado(banco_str)
    if bloqueio:
        return {**base, "status": "bloqueado",
                "motivo": bloqueio["motivo"], "minimo_exigido": 0}

    # ── 2. Parcelas insuficientes ────────────────────────────────────────────
    regra_p = regra_minimo_parcelas(banco_str)
    minimo  = regra_p["minimo"]
    if pagas < minimo:
        return {**base, "status": "parcelas", "minimo_exigido": minimo,
                "motivo": f"Parcelas insuficientes: {pagas} pagas de {minimo} necessárias."}

    # ── 3. Parcela calculada ─────────────────────────────────────────────────
    if parcela_override is not None:
        parcela_calc = parcela_override
    elif saldo_margem >= 0 or not aplicar_abate:
        parcela_calc = parcela_orig
    else:
        parcela_calc = max(parcela_orig + saldo_margem, 0.0)

    # ── 4. Simulação FACTA ───────────────────────────────────────────────────
    df_normal   = simular(parcela_calc, sd, FAIXAS, FATORES)
    df_carencia = simular(parcela_calc, sd, FAIXAS_CARENCIA, FATORES_CARENCIA)
    viavel      = not df_normal.empty or not df_carencia.empty

    if not viavel:
        return {**base, "status": "sem_troco", "minimo_exigido": minimo,
                "parcela_calc": parcela_calc,
                "motivo": (
                    f"Nenhuma tabela FACTA gerou troco acima de {fmt(TROCO_MINIMO)} "
                    f"com parcela de {fmt(parcela_calc)} "
                    f"e saldo devedor de {fmt(sd)}."
                )}

    return {**base, "status": "viavel", "motivo": "",
            "minimo_exigido": minimo,
            "parcela_calc": parcela_calc,
            "df_normal": df_normal,
            "df_carencia": df_carencia}


# ═══════════════════════════════════════════════════════════════
# APP STREAMLIT
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Portabilidade FACTA — INSS",
    page_icon="🏦",
    layout="wide",
)

st.markdown("""
<style>
:root { --azul:#1a4a8c; --laranja:#f47920; }
.sec {
    font-size:.95rem; font-weight:700; color:var(--azul);
    border-bottom:2px solid var(--laranja);
    padding-bottom:4px; margin:1rem 0 .8rem;
}
.sep { border:none; border-top:1px dashed #ccd; margin:1.5rem 0; }
.sd-aviso {
    font-size:.72rem; color:#b45309;
    background:#fff8e1; border:1px solid #b4530944;
    padding:2px 8px; border-radius:4px; display:inline-block; margin-top:2px;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color:var(--laranja) !important;
    border-bottom-color:var(--laranja) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho ────────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;padding:.3rem 0 .1rem">
  <span style="font-size:1.2rem;font-weight:700;color:#1a4a8c">
    Simulador de Portabilidade FACTA
  </span>
  <div style="font-size:.8rem;color:#888;margin-top:2px">
    Análise automática via extrato INSS (PDF)
  </div>
  <hr style="margin:.4rem 0 0;border-color:#f47920">
</div>
""", unsafe_allow_html=True)

# ── Upload ───────────────────────────────────────────────────────────────────

st.markdown('<div class="sec">📄 Extrato INSS</div>', unsafe_allow_html=True)
arquivo = st.file_uploader(
    "Envie o PDF do Histórico de Empréstimo Consignado do INSS",
    type=["pdf"], label_visibility="collapsed",
)
if not arquivo:
    # Limpa cache se usuário removeu o arquivo
    st.session_state.pop("extrato_cache", None)
    st.session_state.pop("extrato_file_id", None)
    st.session_state.pop("sd_manual", None)
    st.session_state.pop("rest_manual", None)
    st.session_state.pop("abate_manual", None)
    st.info("Faça upload do extrato em PDF para iniciar a simulação.")
    st.stop()

# ── Cache do extrato: só relê o PDF quando o arquivo muda ────────────────────
# Usa file_id do Streamlit como chave — muda apenas quando um novo arquivo
# é carregado, não a cada interação do usuário na página.
file_id = arquivo.file_id

if st.session_state.get("extrato_file_id") != file_id:
    with st.spinner("Lendo o extrato..."):
        extrato = processar_extrato(arquivo)
    st.session_state["extrato_cache"]   = extrato
    st.session_state["extrato_file_id"] = file_id
    st.session_state["sd_manual"]       = {}   # reseta ao trocar arquivo
    st.session_state["rest_manual"]     = {}   # reseta ao trocar arquivo
    st.session_state["abate_manual"]    = {}   # reseta ao trocar arquivo

extrato     = st.session_state["extrato_cache"]
dg          = extrato["dados_gerais"]
mg          = extrato["margem_financeira"]
emprestimos = extrato["emprestimos_ativos"]
cartoes     = extrato["cartoes_ativos"]

# ── Dados do cliente ─────────────────────────────────────────────────────────

st.markdown('<div class="sec">👤 Dados do Cliente</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.markdown(card("Titular",       dg.get("titular", "—")),          unsafe_allow_html=True)
c2.markdown(card("Nº Benefício",  dg.get("numero_beneficio", "—")), unsafe_allow_html=True)
c3.markdown(card("Banco Pagamento", dg.get("banco_pagamento", "—")), unsafe_allow_html=True)
c4.markdown(card("Agência / CC",
    f"{dg.get('agencia','—')} / {dg.get('conta_corrente','—')}"),   unsafe_allow_html=True)

# ── Margem financeira ────────────────────────────────────────────────────────

st.markdown('<div class="sec">💰 Margem Financeira</div>', unsafe_allow_html=True)

margem_cons = brl(mg.get("margem_consignavel_emp", "R$0"))
util_emp    = brl(mg.get("margem_utilizada_emp",   "R$0"))
util_rmc    = sum(brl(c.get("reservado_atualizado", "R$0"))
                  for c in cartoes.get("rmc", []) if c.get("reservado_atualizado"))
util_rcc    = sum(brl(c.get("reservado_atualizado", "R$0"))
                  for c in cartoes.get("rcc", []) if c.get("reservado_atualizado"))
util_cartao  = util_rmc + util_rcc
total_comp   = util_emp + util_cartao
saldo_margem = margem_cons - total_comp
cliente_neg  = saldo_margem < 0
abate        = max(0.0, -saldo_margem)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.markdown(card("Base de Cálculo",
    fmt(brl(mg.get("base_calculo", "R$0")))), unsafe_allow_html=True)
m2.markdown(card("Margem Consignável (40%)", fmt(margem_cons)), unsafe_allow_html=True)
m3.markdown(card("Utilizado (Empréstimos)",  fmt(util_emp)),    unsafe_allow_html=True)
m4.markdown(card("Reservado (Cartões)",      fmt(util_cartao)), unsafe_allow_html=True)
m5.markdown(card("Total Comprometido",       fmt(total_comp)),  unsafe_allow_html=True)

cor_s = "#dc3545" if cliente_neg else "#198754"
bg_s  = "#fff0f0" if cliente_neg else "#f0fff4"
m6.markdown(card("Saldo de Margem", fmt(saldo_margem),
    cor=cor_s, bg=bg_s, borda=cor_s), unsafe_allow_html=True)

if cliente_neg:
    st.markdown(
        badge("⚠️", f"Margem negativa em {fmt(abate)}",
              f"Empréstimos ({fmt(util_emp)}) + Cartões ({fmt(util_cartao)}) "
              f"excedem a margem consignável ({fmt(margem_cons)}). "
              f"O abate de {fmt(abate)} será aplicado no contrato selecionado.",
              "negativo"),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        badge("✅", f"Margem OK — saldo disponível: {fmt(saldo_margem)}",
              "Cliente sem margem negativa. Nenhum abate necessário.", "ok"),
        unsafe_allow_html=True,
    )

# ── State: saldo devedor e parcelas restantes editáveis por contrato ────────
# Inicializados uma vez por extrato (resetados ao trocar arquivo).
# sd_manual    : saldo devedor (float) por contrato
# rest_manual  : parcelas restantes (int) por contrato

if "sd_manual" not in st.session_state:
    st.session_state["sd_manual"] = {}
if "rest_manual" not in st.session_state:
    st.session_state["rest_manual"] = {}

for emp in emprestimos:
    chave = emp.get("contrato", "?")
    pagas_auto = calcular_parcelas_pagas(emp.get("inicio_desconto", ""))
    qtde       = emp.get("qtde_parcelas", 0)
    rest_auto  = max(qtde - pagas_auto, 0)

    if chave not in st.session_state["rest_manual"]:
        st.session_state["rest_manual"][chave] = rest_auto

    if chave not in st.session_state["sd_manual"]:
        # Usa parcelas restantes do state (pode já ter sido editado)
        rest = st.session_state["rest_manual"].get(chave, rest_auto)
        sd_auto, _ = calcular_saldo_devedor(emp, qtde - rest)
        st.session_state["sd_manual"][chave] = sd_auto

# ── Seleção do abate ─────────────────────────────────────────────────────────
#
# Lógica em duas passadas:
#   1. Sem abate  → descobre quais já são viáveis (não precisam do abate)
#   2. Com abate  → descobre quais se tornam viáveis SOMENTE com o abate
#
# O radio só mostra contratos da segunda categoria:
# inviáveis sem abate, mas viáveis com abate.
# Contratos já viáveis sem abate não precisam do abate → ficam fora do radio.

def _sd_atual(chave, emp):
    """Saldo devedor mais recente: widget > sd_manual > recalculado."""
    return st.session_state.get(f"sd_{chave}",
           st.session_state["sd_manual"].get(chave))

def _rest_atual(chave, emp):
    """Parcelas restantes mais recentes: widget > rest_manual > automático."""
    return int(st.session_state.get(f"rest_{chave}",
               st.session_state["rest_manual"].get(
                   chave,
                   max(emp.get("qtde_parcelas", 0)
                       - calcular_parcelas_pagas(emp.get("inicio_desconto", "")), 0)
               )))

def _emp_com_overrides(emp):
    """Retorna cópia do emp com parcelas_pagas e qtde_parcelas ajustados pelo state."""
    chave     = emp.get("contrato", "?")
    qtde      = emp.get("qtde_parcelas", 0)
    rest      = _rest_atual(chave, emp)
    pagas_eff = qtde - rest
    e = dict(emp)
    e["_pagas_efetivas"] = max(pagas_eff, 0)
    return e

def _classificar_todos(aplicar_abate_em: str | None) -> list:
    resultado = []
    for emp in emprestimos:
        chave   = emp.get("contrato", "?")
        aplicar = cliente_neg and (chave == aplicar_abate_em)
        sd_man  = _sd_atual(chave, emp)
        e_ov    = _emp_com_overrides(emp)
        cl      = classificar_contrato(e_ov, saldo_margem,
                                       aplicar_abate=aplicar,
                                       saldo_devedor_manual=sd_man)
        resultado.append((emp, cl))
    return resultado

# ── Identificar candidatos ao abate (contratos que absorvem o negativo) ──────
#
# Candidato = viavel COM abate E nao bloqueado por banco/parcelas.
# Inclui contratos ja viaveis sem abate (ex: parcela grande que sobrevive ao corte).

candidatos_abate = []

if cliente_neg:
    pre_sem_abate = _classificar_todos(None)
    for emp, cl_sem in pre_sem_abate:
        if cl_sem["status"] in ("bloqueado", "parcelas"):
            continue
        chave  = emp.get("contrato", "?")
        sd_man = _sd_atual(chave, emp)
        e_ov   = _emp_com_overrides(emp)
        cl_com = classificar_contrato(e_ov, saldo_margem,
                                      aplicar_abate=True,
                                      saldo_devedor_manual=sd_man)
        if cl_com["status"] == "viavel":
            candidatos_abate.append(emp.get("contrato", "?"))

# ── Inicializar abate_manual por contrato no session_state ───────────────────
# Candidatos ao abate → começa com |saldo_margem|
# Demais             → começa com 0
# Bloqueados         → 0 (desabilitado)

if "abate_manual" not in st.session_state:
    st.session_state["abate_manual"] = {}

for emp in emprestimos:
    chave = emp.get("contrato", "?")
    if chave not in st.session_state["abate_manual"]:
        if cliente_neg and chave in candidatos_abate:
            st.session_state["abate_manual"][chave] = round(abate, 2)
        else:
            st.session_state["abate_manual"][chave] = 0.0

# ── Classificação final usando abate_manual por contrato ─────────────────────

def _calcular_max_abate(emp, sd: float) -> float:
    """
    Maior abate que ainda gera troco > TROCO_MINIMO em pelo menos uma tabela.
    Busca binária: decrementa a parcela até nao gerar mais troco.
    """
    parc = brl(emp.get("valor_parcela", "R$0"))
    # Menor parcela viavel: aquela cujo bruto minimo ainda gera troco > TROCO_MINIMO
    # bruto_min = sd + TROCO_MINIMO + 1 centavo
    # parcela_min = bruto_min * fator_menor (fator maior → menor parcela necessária)
    fator_max = max(FATORES.values())
    fator_max_car = max(FATORES_CARENCIA.values())
    fator_ref = max(fator_max, fator_max_car)
    bruto_min = sd + TROCO_MINIMO + 0.01
    parcela_min = bruto_min * fator_ref
    max_abate = parc - parcela_min
    # Validar se realmente gera troco com esse abate
    if max_abate <= 0:
        return 0.0
    pc = max(parc - max_abate, 0)
    dfn = simular(pc, sd, FAIXAS, FATORES)
    dfc = simular(pc, sd, FAIXAS_CARENCIA, FATORES_CARENCIA)
    if dfn.empty and dfc.empty:
        return 0.0
    return round(max_abate, 2)


def _classificar_com_abate_manual(aplicar_abate_em=None) -> list:
    """Classifica todos os contratos usando o abate_manual do session_state."""
    resultado = []
    for emp in emprestimos:
        chave      = emp.get("contrato", "?")
        abate_val  = float(st.session_state.get(f"abate_{chave}",
                     st.session_state["abate_manual"].get(chave, 0.0)))
        sd_man     = _sd_atual(chave, emp)
        e_ov       = _emp_com_overrides(emp)
        # Parcela calculada = parcela_orig - abate_val
        parc_orig  = brl(emp.get("valor_parcela", "R$0"))
        parc_calc  = max(parc_orig - abate_val, 0.0)
        cl         = classificar_contrato(e_ov, 0.0,   # saldo_margem=0: abate já embutido
                                          aplicar_abate=False,
                                          saldo_devedor_manual=sd_man,
                                          parcela_override=parc_calc)
        resultado.append((emp, cl, abate_val))
    return resultado

classificados_raw = _classificar_com_abate_manual()

# Ordenação: contrato com abate > 0 primeiro (quando há abate aplicado),
# depois por status normal
def _sort_key(item):
    emp, cl, abate_val = item
    tem_abate = 1 if abate_val > 0 else 0
    return (-tem_abate, PRIORIDADE[cl["status"]])

classificados_raw.sort(key=_sort_key)
# Compatibilidade: manter formato (emp, cl) para o loop de renderização
classificados = [(emp, cl) for emp, cl, _ in classificados_raw]
abate_por_contrato = {emp.get("contrato","?"): abate_val
                      for emp, cl, abate_val in classificados_raw}

# ── Box de sugestão (cliente negativo) ───────────────────────────────────────

if cliente_neg:
    nomes_cand = []
    for emp in emprestimos:
        if emp.get("contrato","?") in candidatos_abate:
            nomes_cand.append(f"**{emp.get('banco','?')} ({emp.get('contrato','?')})**")

    if nomes_cand:
        st.markdown(
            f'<div style="background:#fff8e1;border-left:4px solid #f47920;'
            f'padding:.7rem 1rem;border-radius:8px;margin-bottom:.8rem;'
            f'font-size:.9rem;color:#1a1a1a">'
            f'⚠️ <strong>Margem negativa de {fmt(abate)}.</strong> '
            f'Contratos que conseguem absorver o abate: {", ".join(nomes_cand)}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:#fff0f0;border-left:4px solid #dc3545;'
            f'padding:.7rem 1rem;border-radius:8px;margin-bottom:.8rem;'
            f'font-size:.9rem;color:#1a1a1a">'
            f'⛔ <strong>Margem negativa de {fmt(abate)}.</strong> '
            f'Nenhum contrato consegue absorver o abate com os valores atuais.'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Variável de compatibilidade (sem aguardando_selecao) ─────────────────────
aguardando_selecao = False

# ── Simulação por contrato ────────────────────────────────────────────────────

st.markdown('<div class="sec">🔄 Simulação de Portabilidade por Contrato</div>',
            unsafe_allow_html=True)

if not emprestimos:
    st.warning("Nenhum empréstimo ativo encontrado no extrato.")
    st.stop()

for i, (emp, cl) in enumerate(classificados):
    banco_nome   = emp.get("banco", f"Contrato {emp.get('contrato','?')}")
    contrato_n   = emp.get("contrato", "?")
    parcela_orig = brl(emp.get("valor_parcela", "R$0"))
    status       = cl["status"]
    pagas        = cl["parcelas_pagas"]
    minimo       = cl["minimo_exigido"]
    parcela_calc = cl["parcela_calc"]
    sd_auto      = cl["saldo_devedor"]
    metodo_sd    = cl["metodo_sd"]
    bloqueado    = status in ("bloqueado", "parcelas")
    abate_atual  = abate_por_contrato.get(contrato_n, 0.0)

    # Header
    hc1, hc2 = st.columns([6, 1])
    with hc1:
        st.markdown(
            f"**{banco_nome}** &nbsp;·&nbsp; `{contrato_n}` &nbsp;·&nbsp; "
            f"{emp.get('inicio_desconto','?')} → {emp.get('fim_desconto','?')}"
            f" &nbsp;·&nbsp; {emp.get('qtde_parcelas','?')}x {emp.get('valor_parcela','?')}"
            f" &nbsp;·&nbsp; {pagas} parc. pagas",
            unsafe_allow_html=True,
        )
    with hc2:
        if status == "viavel":
            st.markdown(badge("✅", "Viável",
                "Contrato com viabilidade de portabilidade pela FACTA.", "ok"),
                unsafe_allow_html=True)
        elif status == "sem_troco":
            st.markdown(badge("❌", "Sem troco", cl["motivo"], "negativo"),
                unsafe_allow_html=True)
        elif status == "parcelas":
            st.markdown(badge("⏳", "Parcelas insuficientes", cl["motivo"], "aviso"),
                unsafe_allow_html=True)
        else:
            st.markdown(badge("🔒", "Banco não portável", cl["motivo"], "bloqueado"),
                unsafe_allow_html=True)

    # Métricas + campos editáveis
    cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)

    cc1.markdown(card("Parcela Original", fmt(parcela_orig)), unsafe_allow_html=True)
    cc2.markdown(card("Juros Mensal",
        f"{emp.get('taxa_juros_mensal','—')}%" if emp.get("taxa_juros_mensal") else "—"),
        unsafe_allow_html=True)

    # Parcelas restantes
    with cc3:
        rest_key = f"rest_{contrato_n}"
        rest_val = int(st.session_state["rest_manual"].get(
                       contrato_n,
                       max(emp.get("qtde_parcelas", 0) - pagas, 0)))

        def _sync_rest(key=rest_key, contrato=contrato_n, emp_ref=emp):
            novo_rest = int(st.session_state[key])
            st.session_state["rest_manual"][contrato] = novo_rest
            qtde = emp_ref.get("qtde_parcelas", 0)
            pagas_eff = max(qtde - novo_rest, 0)
            sd_novo, _ = calcular_saldo_devedor(emp_ref, pagas_eff)
            st.session_state["sd_manual"][contrato] = sd_novo

        st.number_input("Parc. Restantes",
            min_value=0, max_value=emp.get("qtde_parcelas", 999),
            value=rest_val, step=1, key=rest_key,
            on_change=_sync_rest, disabled=bloqueado)

    # Saldo devedor
    with cc4:
        label_sd = "Saldo Devedor (Price)" if metodo_sd == "price" else "Saldo Devedor (Est.)"
        sd_key   = f"sd_{contrato_n}"

        def _sync_sd(key=sd_key, contrato=contrato_n):
            st.session_state["sd_manual"][contrato] = st.session_state[key]

        st.number_input(label_sd,
            min_value=0.0,
            value=float(st.session_state["sd_manual"].get(contrato_n, sd_auto)),
            step=10.0, format="%.2f", key=sd_key,
            on_change=_sync_sd, disabled=bloqueado)
        if metodo_sd == "estimado" and not bloqueado:
            st.markdown('<div class="sd-aviso">⚠ Estimado — taxa nao disponivel</div>',
                unsafe_allow_html=True)

    # Abate editável com tooltip de máximo
    with cc5:
        abate_key = f"abate_{contrato_n}"
        sd_atual_val = float(st.session_state["sd_manual"].get(contrato_n, sd_auto))
        max_ab = _calcular_max_abate(emp, sd_atual_val) if not bloqueado else 0.0
        tooltip_abate = (
            f"Maximo de abate viavel: {fmt(max_ab)}"
            if max_ab > 0 else "Sem viabilidade de abate neste contrato"
        )

        def _sync_abate(key=abate_key, contrato=contrato_n):
            st.session_state["abate_manual"][contrato] = float(st.session_state[key])

        st.number_input("Abate",
            min_value=0.0,
            value=float(st.session_state["abate_manual"].get(contrato_n, abate_atual)),
            step=10.0, format="%.2f", key=abate_key,
            on_change=_sync_abate, disabled=bloqueado,
            help=tooltip_abate)

    # Parcela p/ portabilidade + tabelas FACTA
    if status == "viavel":
        cc6.markdown(card("Parcela p/ Portabilidade", fmt(parcela_calc),
            cor="#f47920", bg="#fff7f0", borda="#f47920"), unsafe_allow_html=True)
        t1, t2 = st.tabs(["Sem Carência", "Com Carência"])
        with t1:
            exibir_df(cl["df_normal"])
        with t2:
            exibir_df(cl["df_carencia"])
    else:
        cc6.markdown(card("Parcela p/ Portabilidade", "—"), unsafe_allow_html=True)

    if i < len(classificados) - 1:
        st.markdown('<hr class="sep">', unsafe_allow_html=True)

# ── Rodapé ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "Saldo devedor calculado via fórmula Price quando a taxa está disponível no extrato. "
    f"Quando não disponível, estimado como PMT × parcelas restantes × "
    f"{int((1 - DESCONTO_SD_SEM_TAXA) * 100)}% "
    f"(desconto de {int(DESCONTO_SD_SEM_TAXA * 100)}% sobre valor nominal). "
    "O campo de saldo devedor é editável — insira o valor real do extrato bancário se disponível. "
    f"Troco mínimo exibido: {fmt(TROCO_MINIMO)}."
)