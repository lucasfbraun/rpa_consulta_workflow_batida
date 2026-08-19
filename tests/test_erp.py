from types import SimpleNamespace

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from rpa_ponto.erp import _open_erp_url


class FakePage:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = []

    def goto(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.failures:
            raise self.failures.pop(0)


class FakeReporter:
    def __init__(self):
        self.steps = []

    def step(self, name, **kwargs):
        self.steps.append((name, kwargs))


def settings(fallback_url="https://erp-alternativo.example"):
    return SimpleNamespace(
        erp_url="https://erp-principal.example",
        erp_fallback_url=fallback_url,
    )


def test_uses_fallback_when_primary_times_out():
    page = FakePage([PlaywrightTimeoutError("timeout")])
    reporter = FakeReporter()

    _open_erp_url(page, settings(), reporter)

    assert [call[0] for call in page.calls] == [
        "https://erp-principal.example",
        "https://erp-alternativo.example",
    ]
    assert reporter.steps[0][0] == "erp_url_principal_timeout"


def test_timeout_is_raised_without_fallback():
    page = FakePage([PlaywrightTimeoutError("timeout")])

    with pytest.raises(PlaywrightTimeoutError):
        _open_erp_url(page, settings(None), None)

    assert len(page.calls) == 1


def test_non_timeout_error_does_not_use_fallback():
    page = FakePage([PlaywrightError("certificate error")])

    with pytest.raises(PlaywrightError):
        _open_erp_url(page, settings(), None)

    assert len(page.calls) == 1
