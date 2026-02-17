"""
Pytest configuration and fixtures for E2E tests.

Provides browser fixtures using Playwright. Tests are marked with
@pytest.mark.e2e and can be skipped if Playwright is not installed.
"""

import logging
import os
import pytest

logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: mark test as E2E browser test")


@pytest.fixture(scope="session")
def browser_launch_args():
    """Configuration for browser launch."""
    return {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}


@pytest.fixture(scope="session")
def browser_context_args():
    """Configuration for browser context."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def browser():
    """Provide a browser instance for tests.

    Skips test if Playwright is not installed.
    """
    pytest.importorskip("playwright")

    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()
    playwright.stop()


@pytest.fixture(scope="function")
def page(browser):
    """Provide a page instance for tests."""
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()

    # Set timeout for navigation
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(30000)

    yield page

    page.close()
    context.close()


@pytest.fixture
def base_url():
    """Base URL for E2E tests."""
    return os.getenv("E2E_BASE_URL", "http://localhost:3000")


@pytest.fixture
def admin_credentials():
    """Admin user credentials for testing."""
    return {
        "email": os.getenv("TEST_ADMIN_EMAIL", "admin@test.example.com"),
        "password": os.getenv("TEST_ADMIN_PASSWORD", "testpassword123"),
    }


@pytest.fixture
def regular_user_credentials():
    """Regular user credentials for testing."""
    return {
        "email": os.getenv("TEST_USER_EMAIL", "user@test.example.com"),
        "password": os.getenv("TEST_USER_PASSWORD", "testpassword123"),
    }


@pytest.fixture
def authenticated_page(page, base_url, admin_credentials):
    """Provide an authenticated page (logged in as admin)."""
    page.goto(f"{base_url}/login")

    # Fill login form
    page.fill('input[name="email"]', admin_credentials["email"])
    page.fill('input[name="password"]', admin_credentials["password"])

    # Click login button
    page.click('button:has-text("Sign In")')

    # Wait for navigation to complete
    page.wait_for_load_state("networkidle")

    logger.info("Authenticated page ready for user: %s", admin_credentials["email"])

    yield page


@pytest.fixture(autouse=True)
def skip_e2e_if_no_playwright(request):
    """Skip E2E tests if Playwright is not installed."""
    if "e2e" in request.keywords:
        try:
            import playwright  # noqa: F401
        except ImportError:
            pytest.skip("Playwright not installed - skipping E2E tests")
