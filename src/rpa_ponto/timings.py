"""Tempos individuais das ações do ERP.

Use ``None`` para herdar ``RPA_GLOBAL_DELAY_MS``. Informe um número em
milissegundos para deixar uma ação específica mais rápida ou mais lenta.
"""

ACTION_DELAYS_MS: dict[str, int | None] = {
    # Login
    "preencher_usuario": 300,
    "preencher_senha": 500,
    "clicar_acessar": 300,
    "selecionar_sessao_ativa": None,
    "continuar_sessao_ativa": None,
    "confirmar_encerramento_sessao": None,
    "fechar_aviso_sessao": None,
    # Abertura do programa
    "abrir_menu": 300,
    "pesquisar_sms": 500,
    "confirmar_pesquisa_sms": 300,
    "preencher_programa": 500,
    "abrir_programa": 1000,
    # Formulário: use valores diferentes se algum campo responder mais devagar.
    "confirmar_campo_12": 400,
    "confirmar_campo_13": 400,
    "confirmar_campo_14": 600,
    "confirmar_campo_15": 600,
    "confirmar_campo_16": 600,
    # Arquivo e processamento
    "selecionar_arquivo": 2000,
    "validar_arquivo": 5000,
    "fechar_validacao": 10000,
    "abrir_tipo_importacao": 3000,
    "selecionar_tipo_importacao": 3000,
    "processar_importacao": 10000,
    "fechar_resultado": 300,
    # Logout
    "clicar_logout": 2000,
    "confirmar_logout": 2000,
}


def delay_for(action: str, global_delay_ms: int) -> int:
    configured = ACTION_DELAYS_MS.get(action)
    return global_delay_ms if configured is None else configured
