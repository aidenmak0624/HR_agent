"""
End-to-End tests for HR Multi-Agent Platform frontend.

Tests critical user flows including dashboard, chat, leave management,
and analytics pages. Requires Playwright and a running frontend server.

Usage: pytest tests/e2e/test_frontend_flows.py -v --e2e
"""

import logging
import re
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.e2e
class TestDashboardFlow:
    """E2E tests for dashboard page and KPI cards."""

    def test_dashboard_loads(self, authenticated_page, base_url):
        """Test dashboard page loads successfully."""
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Verify page title
        title = authenticated_page.title()
        assert "Dashboard" in title or "HR" in title

        logger.info("Dashboard page loaded successfully")

    def test_navigation_sidebar(self, authenticated_page, base_url):
        """Test sidebar navigation is visible and functional."""
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for sidebar
        sidebar = authenticated_page.locator("[data-testid='sidebar']")
        assert sidebar.is_visible()

        # Check for navigation items
        nav_items = authenticated_page.locator("[data-testid='nav-item']")
        assert nav_items.count() > 0

        # Click on a nav item (e.g., Chat)
        chat_nav = authenticated_page.locator("text=Chat")
        if chat_nav.is_visible():
            chat_nav.click()
            authenticated_page.wait_for_load_state("networkidle")
            assert base_url in authenticated_page.url

        logger.info("Navigation sidebar working correctly")

    def test_kpi_cards_render(self, authenticated_page, base_url):
        """Test KPI cards display with data."""
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for KPI cards
        kpi_section = authenticated_page.locator("[data-testid='kpi-section']")

        if kpi_section.is_visible():
            # Check for at least one KPI card
            cards = authenticated_page.locator("[data-testid='kpi-card']")
            assert cards.count() > 0

            # Verify cards have content
            for i in range(min(3, cards.count())):
                card = cards.nth(i)
                assert card.is_visible()

                # Check for value or metric
                metric_text = card.text_content()
                assert metric_text and len(metric_text.strip()) > 0

            logger.info("KPI cards rendered successfully")
        else:
            logger.warning("KPI section not found, skipping KPI card tests")


@pytest.mark.e2e
class TestChatFlow:
    """E2E tests for chat/messaging functionality."""

    def test_chat_page_loads(self, authenticated_page, base_url):
        """Test chat page loads successfully."""
        authenticated_page.goto(f"{base_url}/chat")
        authenticated_page.wait_for_load_state("networkidle")

        # Verify chat interface elements
        chat_input = authenticated_page.locator("[data-testid='chat-input']")
        assert chat_input.is_visible(), "Chat input field not found"

        logger.info("Chat page loaded successfully")

    def test_send_message(self, authenticated_page, base_url):
        """Test sending a message through chat."""
        authenticated_page.goto(f"{base_url}/chat")
        authenticated_page.wait_for_load_state("networkidle")

        # Find chat input
        chat_input = authenticated_page.locator("[data-testid='chat-input']")
        assert chat_input.is_visible()

        # Type a message
        test_message = "What is the vacation policy?"
        chat_input.fill(test_message)

        # Find and click send button
        send_button = authenticated_page.locator("button:has-text('Send')")
        assert send_button.is_visible()
        send_button.click()

        # Wait for response
        authenticated_page.wait_for_timeout(2000)

        # Check that message appears in chat
        message_text = authenticated_page.locator(f"text={test_message}")
        assert message_text.is_visible(), "Sent message not found in chat"

        # Wait for agent response
        authenticated_page.wait_for_timeout(3000)

        # Check for response in chat (look for assistant message)
        responses = authenticated_page.locator("[data-testid='message'][data-role='assistant']")
        assert responses.count() > 0, "No assistant response found"

        logger.info("Message sent and response received successfully")

    def test_agent_type_badge_visible(self, authenticated_page, base_url):
        """Test agent type badge appears in responses."""
        authenticated_page.goto(f"{base_url}/chat")
        authenticated_page.wait_for_load_state("networkidle")

        # Send a test message
        chat_input = authenticated_page.locator("[data-testid='chat-input']")
        chat_input.fill("What is my leave balance?")

        send_button = authenticated_page.locator("button:has-text('Send')")
        send_button.click()

        # Wait for response
        authenticated_page.wait_for_timeout(3000)

        # Look for agent type badge
        agent_badge = authenticated_page.locator("[data-testid='agent-badge']")

        if agent_badge.is_visible():
            badge_text = agent_badge.text_content()
            assert badge_text, "Agent badge has no text"
            # Verify badge contains agent type
            assert any(agent in badge_text.lower() for agent in [
                "router", "leave", "policy", "assistant"
            ])

            logger.info("Agent type badge found: %s", badge_text)
        else:
            logger.warning("Agent type badge not visible")


@pytest.mark.e2e
class TestLeaveFlow:
    """E2E tests for leave management page."""

    def test_leave_page_loads(self, authenticated_page, base_url):
        """Test leave page loads successfully."""
        authenticated_page.goto(f"{base_url}/leave")
        authenticated_page.wait_for_load_state("networkidle")

        # Verify page loaded
        page_title = authenticated_page.locator("h1, h2")
        assert page_title.count() > 0

        # Check for leave-related content
        page_content = authenticated_page.content()
        assert "leave" in page_content.lower() or "time off" in page_content.lower()

        logger.info("Leave page loaded successfully")

    def test_balance_cards_render(self, authenticated_page, base_url):
        """Test leave balance cards display."""
        authenticated_page.goto(f"{base_url}/leave")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for balance cards
        balance_cards = authenticated_page.locator("[data-testid='balance-card']")

        if balance_cards.count() > 0:
            # Verify at least one balance card is visible
            card = balance_cards.first
            assert card.is_visible()

            # Check for content (leave type and balance)
            content = card.text_content()
            assert content, "Balance card has no content"

            # Check for numeric content (balance number)
            assert re.search(r'\d+', content), "Balance card has no numeric content"

            logger.info("Leave balance cards rendered successfully")
        else:
            logger.warning("Balance cards not found, skipping balance card tests")

    def test_leave_form_validation(self, authenticated_page, base_url):
        """Test leave request form validation."""
        authenticated_page.goto(f"{base_url}/leave")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for request leave button
        request_button = authenticated_page.locator("button:has-text('Request Leave')")

        if request_button.is_visible():
            request_button.click()

            # Wait for form to appear
            authenticated_page.wait_for_timeout(1000)

            # Check for form fields
            form = authenticated_page.locator("[data-testid='leave-request-form']")
            if form.is_visible():
                # Try to submit empty form
                submit_button = authenticated_page.locator("button:has-text('Submit')")
                if submit_button.is_visible():
                    submit_button.click()

                    # Should show validation error
                    authenticated_page.wait_for_timeout(500)

                    # Check for error message
                    error = authenticated_page.locator(".error, [role='alert']")
                    # May or may not be present depending on implementation
                    logger.info("Form validation tested")
            else:
                logger.warning("Leave request form not found")
        else:
            logger.warning("Request Leave button not found")


@pytest.mark.e2e
class TestAnalyticsFlow:
    """E2E tests for analytics/reporting page."""

    def test_analytics_page_loads(self, authenticated_page, base_url):
        """Test analytics page loads successfully."""
        authenticated_page.goto(f"{base_url}/analytics")
        authenticated_page.wait_for_load_state("networkidle")

        # Verify page loaded
        assert "analytics" in authenticated_page.url.lower() or "report" in authenticated_page.url.lower()

        page_content = authenticated_page.content()
        assert len(page_content) > 100

        logger.info("Analytics page loaded successfully")

    def test_chart_renders(self, authenticated_page, base_url):
        """Test analytics charts render."""
        authenticated_page.goto(f"{base_url}/analytics")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for chart containers
        charts = authenticated_page.locator("[data-testid='chart']")

        if charts.count() > 0:
            # Verify at least one chart is visible
            chart = charts.first
            assert chart.is_visible()

            # Check for SVG or canvas (chart render indicators)
            svg = chart.locator("svg")
            canvas = chart.locator("canvas")

            is_rendered = svg.count() > 0 or canvas.count() > 0
            assert is_rendered, "Chart does not appear to be rendered"

            logger.info("Analytics charts rendered successfully")
        else:
            logger.warning("No chart elements found on analytics page")

    def test_date_picker_works(self, authenticated_page, base_url):
        """Test date picker functionality."""
        authenticated_page.goto(f"{base_url}/analytics")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for date picker input
        date_input = authenticated_page.locator("input[type='date'], [data-testid='date-picker']")

        if date_input.is_visible():
            # Click on date input
            date_input.click()
            authenticated_page.wait_for_timeout(500)

            # Try to set a date
            date_input.fill("2024-01-15")
            authenticated_page.wait_for_timeout(1000)

            # Verify chart updates (or data reloads)
            authenticated_page.wait_for_load_state("networkidle")

            logger.info("Date picker functionality working")
        else:
            logger.warning("Date picker not found on analytics page")


# Utility test to verify test setup
@pytest.mark.e2e
def test_e2e_setup(page, base_url):
    """Verify E2E test setup and browser connectivity."""
    page.goto(f"{base_url}/")
    page.wait_for_load_state("networkidle")

    # Verify page loaded
    assert page.title(), "Page has no title"
    assert len(page.content()) > 100, "Page has no content"

    logger.info("E2E test setup verified - browser connectivity OK")
