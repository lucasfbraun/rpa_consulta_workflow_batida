from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    expect,
    sync_playwright,
)

from .config import Settings
from .timings import delay_for


class ErpAutomationError(RuntimeError):
    pass


def import_into_erp(settings: Settings, import_file: Path) -> None:
    if not import_file.is_file():
        raise FileNotFoundError(f"Arquivo para importação não encontrado: {import_file}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings.headless)
        context = browser.new_context(ignore_https_errors=not settings.erp_verify_tls)
        try:
            page = context.new_page()
            page.set_default_timeout(20_000)
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(settings.erp_url, wait_until="domcontentloaded")
            _erp_steps(page, import_file.resolve(), settings)
        except PlaywrightError as exc:
            raise ErpAutomationError(
                f"Falha ao operar o ERP: {exc.__class__.__name__}"
            ) from exc
        finally:
            context.close()
            browser.close()


def _erp_steps(page: Page, import_file: Path, settings: Settings) -> None:
    _login(page, settings, close_active_sessions=settings.erp_close_active_sessions)
    _open_import_program(page, settings)
    _prepare_import_form(page, settings)
    page.locator('input[type="file"]').set_input_files(str(import_file))
    _pause_after(page, settings, "selecionar_arquivo")
    _process_file(page, settings)
    _logout(page, settings)


def _login(page: Page, settings: Settings, *, close_active_sessions: bool) -> None:
    if not settings.erp_username or not settings.erp_password:
        raise ValueError("Preencha ERP_USERNAME e ERP_PASSWORD no .env.")

    user = page.get_by_role("textbox", name="Usuário")
    password = page.get_by_role("textbox", name="Senha")
    expect(user).to_be_visible()
    user.fill(settings.erp_username)
    _pause_after(page, settings, "preencher_usuario")
    password.fill(settings.erp_password)
    _pause_after(page, settings, "preencher_senha")
    page.get_by_role("button", name="Acessar").click()
    _pause_after(page, settings, "clicar_acessar")

    home_heading = page.get_by_role("heading", name=re.compile(r"Olá,", re.IGNORECASE))
    continue_button = page.get_by_role("button", name="Continuar")
    expect(home_heading.or_(continue_button)).to_be_visible(timeout=30_000)

    if continue_button.is_visible():
        if not close_active_sessions:
            raise ErpAutomationError(
                "O ERP informou que já existe uma sessão ativa. Encerre-a manualmente "
                "ou defina ERP_CLOSE_ACTIVE_SESSIONS=true no .env para a conta exclusiva do RPA."
            )
        session_item = page.get_by_text(
            re.compile(r"ID da Sessão", re.IGNORECASE)
        ).first
        session_item.click()
        _pause_after(page, settings, "selecionar_sessao_ativa")
        expect(continue_button).to_be_enabled()
        continue_button.click()
        _pause_after(page, settings, "continuar_sessao_ativa")
        confirmation = page.get_by_role(
            "button", name="Estou ciente e desejo prosseguir"
        )
        expect(confirmation).to_be_visible()
        confirmation.click()
        _pause_after(page, settings, "confirmar_encerramento_sessao")
        _click_if_visible(
            page,
            settings,
            page.get_by_role("button", name="Ok"),
            "fechar_aviso_sessao",
        )

    expect(home_heading).to_be_visible(timeout=30_000)


def _open_import_program(page: Page, settings: Settings) -> None:
    search = page.get_by_role(
        "textbox", name=re.compile(r"Digite o código ou o nome do", re.IGNORECASE)
    )
    if not search.is_visible():
        # Se o menu lateral estiver recolhido, este é o ícone registrado no ERP.
        page.locator("i").nth(5).click()
        _pause_after(page, settings, "abrir_menu")
        expect(search).to_be_visible()

    search.fill("sms")
    _pause_after(page, settings, "pesquisar_sms")
    search.press("Enter")
    _pause_after(page, settings, "confirmar_pesquisa_sms")

    program = page.locator(".ui.mini.right > input")
    expect(program).to_be_visible()
    program.fill(settings.erp_program_code)
    _pause_after(page, settings, "preencher_programa")
    program.press("Enter")
    _pause_after(page, settings, "abrir_programa")
    expect(page.get_by_role("button", name="Selecionar Arquivo")).to_be_visible(
        timeout=30_000
    )


def _prepare_import_form(page: Page, settings: Settings) -> None:
    # Estes Enter confirmam os valores padrão dos cinco campos anteriores ao upload,
    # conforme a sessão gravada no ERP.
    form = page.locator(".csw_form:visible").last
    selectors = tuple(
        form.locator(f":scope > div:nth-child({position}) input:visible")
        for position in range(12, 17)
    )
    for position, field in zip(range(12, 17), selectors):
        expect(field).to_be_visible()
        field.press("Enter")
        _pause_after(page, settings, f"confirmar_campo_{position}")


def _process_file(page: Page, settings: Settings) -> None:
    process = page.get_by_role("button", name="Processar")
    process.click()
    _pause_after(page, settings, "validar_arquivo")

    # A primeira execução valida o arquivo e abre uma mensagem de retorno.
    _click_if_visible(
        page,
        settings,
        page.get_by_role("button", name="Sair"),
        "fechar_validacao",
    )

    import_selector = page.get_by_role("alert")
    expect(import_selector).to_be_visible()
    import_selector.click()
    _pause_after(page, settings, "abrir_tipo_importacao")
    page.get_by_role("option", name=settings.erp_import_kind).click()
    _pause_after(page, settings, "selecionar_tipo_importacao")

    process.click()
    _pause_after(page, settings, "processar_importacao")
    _click_if_visible(
        page,
        settings,
        page.get_by_role("button", name="Sair"),
        "fechar_resultado",
    )


def _logout(page: Page, settings: Settings) -> None:
    logout = page.locator(".red").first
    expect(logout).to_be_visible()
    logout.click()
    _pause_after(page, settings, "clicar_logout")
    confirmation = page.get_by_role("button", name="Sim")
    expect(confirmation).to_be_visible()
    confirmation.click()
    _pause_after(page, settings, "confirmar_logout")


def _click_if_visible(page: Page, settings: Settings, locator, action: str) -> None:
    try:
        locator.wait_for(state="visible", timeout=10_000)
        locator.click()
        _pause_after(page, settings, action)
    except PlaywrightTimeoutError:
        pass


def _wait(page: Page, milliseconds: int) -> None:
    if milliseconds:
        page.wait_for_timeout(milliseconds)


def _pause_after(page: Page, settings: Settings, action: str) -> None:
    _wait(page, delay_for(action, settings.global_delay_ms))
