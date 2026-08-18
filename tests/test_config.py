import pytest

from rpa_ponto.config import Settings, _as_bool, _as_milliseconds


@pytest.mark.parametrize("value", ["true", "1", "sim", "YES", "on"])
def test_true_values(value):
    assert _as_bool(value, default=False) is True


@pytest.mark.parametrize("value", ["false", "0", "não", "NO", "off"])
def test_false_values(value):
    assert _as_bool(value, default=True) is False


def test_invalid_boolean():
    with pytest.raises(ValueError):
        _as_bool("talvez", default=True)


def test_milliseconds(monkeypatch):
    monkeypatch.setenv("TEST_DELAY_MS", "750")
    assert _as_milliseconds("TEST_DELAY_MS") == 750


def test_negative_milliseconds(monkeypatch):
    monkeypatch.setenv("TEST_DELAY_MS", "-1")
    with pytest.raises(ValueError):
        _as_milliseconds("TEST_DELAY_MS")


def test_erp_locale_defaults_to_brazilian_portuguese(monkeypatch):
    monkeypatch.setattr("rpa_ponto.config.load_dotenv", lambda **_kwargs: None)
    monkeypatch.setenv("PONTO_API_URL", "https://ponto.example")
    monkeypatch.setenv("PONTO_USERNAME", "usuario")
    monkeypatch.setenv("PONTO_PASSWORD", "senha")
    monkeypatch.setenv("ERP_URL", "https://erp.example")
    monkeypatch.delenv("ERP_LOCALE", raising=False)
    monkeypatch.delenv("CLOUDFLARE_PAGES_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.erp_locale == "pt-BR"
