"""
config.py
─────────
Arquivo de configuração do Simulador de Portabilidade FACTA.
Edite aqui fatores, faixas, bancos bloqueados e mínimo de parcelas.
NÃO é necessário alterar nenhum outro arquivo para manutenção das regras.
"""

# ══════════════════════════════════════════════════════════════════════════════
# FATORES DAS TABELAS
# Fator = divisor para calcular o valor bruto a partir da parcela calculada
# Bruto = parcela_calculada / fator
# ══════════════════════════════════════════════════════════════════════════════

FATORES = {
    "Refin Normal": 0.022594,
    "Refin FLEX 0": 0.022424,
    "Refin Flex 1": 0.022169,
    "Refin Flex 2": 0.021999,
    "Refin Flex 3": 0.021746,
    "Refin Flex 4": 0.021495,
    "Refin Flex 5": 0.021328,
    "Refin Flex 6": 0.021246,
}

FATORES_CARENCIA = {
    "Refin Normal": 0.023925,
    "Refin FLEX 0": 0.023730,
    "Refin Flex 1": 0.023439,
    "Refin Flex 2": 0.023246,
    "Refin Flex 3": 0.022958,
    "Refin Flex 4": 0.022672,
    "Refin Flex 5": 0.022482,
    "Refin Flex 6": 0.022293,
    "Refin Flex 7": 0.022093,
}

# ══════════════════════════════════════════════════════════════════════════════
# FAIXAS DE VALOR BRUTO × TABELAS DISPONÍVEIS
#
# Formato de cada entrada:
#   (valor_minimo, valor_maximo, [lista de tabelas disponíveis nessa faixa])
#
# Regra: o bruto calculado deve estar entre valor_minimo e valor_maximo
# para que a tabela correspondente seja exibida na simulação.
# Se o bruto não se encaixar em nenhuma faixa, a tabela é descartada.
# ══════════════════════════════════════════════════════════════════════════════

FAIXAS = [
    # (valor_min, valor_max, [tabelas disponíveis])
    (4000,    5499.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
    ]),
    (5500,    8499.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
    ]),
    (8500,   13999.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
        "Refin Flex 4",
        "Refin Flex 5",
    ]),
    (14000,  100000, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
        "Refin Flex 4",
        "Refin Flex 5",
        "Refin Flex 6",
    ]),
]

FAIXAS_CARENCIA = [
    # (valor_min, valor_max, [tabelas disponíveis com carência])
    (3000,    3999.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
    ]),
    (4000,    5499.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
    ]),
    (5500,    8499.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
    ]),
    (8500,   13999.99, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
        "Refin Flex 4",
        "Refin Flex 5",
        "Refin Flex 6",
    ]),
    (14000,  100000, [
        "Refin Normal",
        "Refin FLEX 0",
        "Refin Flex 1",
        "Refin Flex 2",
        "Refin Flex 3",
        "Refin Flex 4",
        "Refin Flex 5",
        "Refin Flex 6",
        "Refin Flex 7",
    ]),
]

# ══════════════════════════════════════════════════════════════════════════════
# BANCOS QUE NÃO PORTA
#
# Formato de cada entrada:
#   {
#       "codigos": ["NNN", ...],  # códigos COMPE (3 dígitos como string)
#       "nomes":   ["NOME", ...], # fragmentos do nome (busca parcial, maiúsculo)
#       "motivo":  "Texto exibido no tooltip do badge"
#   }
#
# A validação é feita por código OU por nome (redundância).
# Os nomes são comparados em maiúsculo e por substring
# (ex: "PAULISTA" bate em "BANCO PAULISTA S.A.").
# ══════════════════════════════════════════════════════════════════════════════

BANCOS_BLOQUEADOS = [
    
    {
        "codigos": ["611"],
        "nomes":   ["PAULISTA"],
        "motivo":  "Banco Paulista não é portável pela FACTA.",
    },
    {
        "codigos": [],
        "nomes":   ["ZEMA", "FINANCEIRA ZEMA"],
        "motivo":  "Zema não é portável pela FACTA.",
    },
    {
        "codigos": ["643"],
        "nomes":   ["PINE"],
        "motivo":  "Banco Pine não é portável pela FACTA.",
    },
    {
        "codigos": ["183"],
        "nomes":   ["SOCRED"],
        "motivo":  "Socred não é portável pela FACTA.",
    },
    {
        "codigos": ["012"],
        "nomes":   ["INBURS", "INBURSA"],
        "motivo":  "Banco Inbursa não é portável pela FACTA.",
    },
    {
        "codigos": ["260"],
        "nomes":   ["NUBANK", "NU PAGAMENTOS"],
        "motivo":  "Nubank não é portável pela FACTA.",
    },
    {
        "codigos": ["753"],
        "nomes":   ["NBC BANK", "NBC"],
        "motivo":  "NBC Bank não é portável pela FACTA.",
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# MÍNIMO DE PARCELAS PAGAS POR BANCO
#
# Formato de cada entrada:
#   {
#       "codigos": ["NNN", ...],  # códigos COMPE
#       "nomes":   ["NOME", ...], # fragmentos do nome (busca parcial, maiúsculo)
#       "minimo":  N,             # mínimo de parcelas pagas exigido
#   }
#
# A última entrada (sem códigos e sem nomes) é a regra padrão
# aplicada a qualquer banco não listado acima.
#
# A validação é por código OU nome (redundância), igual aos bloqueados.
# Parcelas pagas = meses entre início do desconto e hoje (calculado automaticamente).
# ══════════════════════════════════════════════════════════════════════════════

MINIMO_PARCELAS = [
    {
        "codigos": ["121"],
        "nomes":   ["AGIBANK", "AGIBAN"],
        "minimo":  15,
    },
    {
        "codigos": ["318"],
        "nomes":   ["BMG"],
        "minimo":  12,
    },
    {
        "codigos": ["336", "626"],
        "nomes":   ["C6", "C6 CONSIG"],
        "minimo":  12,
    },
    {
        "codigos": ["707"],
        "nomes":   ["DAYCOVAL"],
        "minimo":  24,
    },
    {
        "codigos": ["623"],
        "nomes":   ["BANCO PAN", "PANAMERICANO"],
        "minimo":  30,
    },
    {
        "codigos": ["254"],
        "nomes":   ["PARANA", "PARANÁ"],
        "minimo":  15,
    },
    {
        "codigos": ["033", "169"],
        "nomes":   ["SANTANDER", "OLÉ", "OLE CONSIG"],
        "minimo":  12,
    },
    # ── Regra padrão (demais bancos) — mantenha sempre como último item ──
    {
        "codigos": [],
        "nomes":   [],
        "minimo":  0,
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# TROCO MÍNIMO
# Valor mínimo de troco para uma tabela ser considerada viável.
# ══════════════════════════════════════════════════════════════════════════════

TROCO_MINIMO = 50.00

# ══════════════════════════════════════════════════════════════════════════════
# SALDO DEVEDOR — CÁLCULO AUTOMÁTICO
#
# Quando a taxa de juros NÃO está disponível no extrato, o saldo devedor é
# estimado como:
#   SD = (PMT × parcelas_restantes) × (1 - DESCONTO_SD_SEM_TAXA)
#
# O desconto compensa os juros embutidos nas parcelas futuras.
# Valor sugerido: 0.15 (15%) — compatível com taxas típicas de consignado
# entre 1,6% e 2,2% ao mês em tabela Price.
#
# Quando a taxa de juros ESTÁ disponível, o cálculo usa a fórmula Price exata:
#   SD = PMT × [1 - (1 + i)^(-n_restantes)] / i
# ══════════════════════════════════════════════════════════════════════════════

DESCONTO_SD_SEM_TAXA = 0.15   # 15% de desconto sobre PMT × n_restantes
