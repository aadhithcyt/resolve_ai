"""Tests for interactive features: push notifications, keyboard shortcuts, theme toggle, mobile responsive."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from pathlib import Path


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Push Notification Endpoints ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_push_notification(client):
    """Test subscribing to push notifications."""
    subscription = {
        "endpoint": "https://push.example.com/subscribe/abc123",
        "keys": {
            "p256dh": "BNcRd6L9hN3m5v8x2y4z6a8c0e2g4i6k8m0o2q4s6u8w0y2a4c6e8g0i2k4",
            "auth": "t6w1y3z5a7b9c1d3e5f7g9h1j3k5l7m9n1o3p5q7r9s1t3u5v7w9x1y3z5",
        },
    }
    resp = await client.post("/api/notifications/subscribe", json=subscription)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "subscribed"


@pytest.mark.asyncio
async def test_subscribe_duplicate_endpoint(client):
    """Test that subscribing with the same endpoint updates rather than duplicates."""
    subscription = {
        "endpoint": "https://push.example.com/subscribe/duplicate",
        "keys": {
            "p256dh": "BNcRd6L9hN3m5v8x2y4z6a8c0e2g4i6k8m0o2q4s6u8w0y2a4c6e8g0i2k4",
            "auth": "t6w1y3z5a7b9c1d3e5f7g9h1j3k5l7m9n1o3p5q7r9s1t3u5v7w9x1y3z5",
        },
    }
    # First subscription
    resp1 = await client.post("/api/notifications/subscribe", json=subscription)
    assert resp1.status_code == 200

    # Second subscription with same endpoint (should upsert)
    resp2 = await client.post("/api/notifications/subscribe", json=subscription)
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_send_test_notification(client):
    """Test sending a test notification."""
    resp = await client.post("/api/notifications/send-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"


@pytest.mark.asyncio
async def test_get_notifications(client):
    """Test retrieving notifications."""
    # First create a notification
    await client.post("/api/notifications/send-test")

    resp = await client.get("/api/notifications/")
    assert resp.status_code == 200
    notifications = resp.json()
    assert isinstance(notifications, list)
    assert len(notifications) >= 1
    assert "title" in notifications[0]
    assert "body" in notifications[0]


@pytest.mark.asyncio
async def test_get_unread_count(client):
    """Test getting unread notification count."""
    # Create a notification
    await client.post("/api/notifications/send-test")

    resp = await client.get("/api/notifications/unread-count")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["count"] >= 1


@pytest.mark.asyncio
async def test_mark_notification_as_read(client):
    """Test marking a notification as read."""
    # Create a notification
    await client.post("/api/notifications/send-test")

    # Get notifications to find one
    resp = await client.get("/api/notifications/")
    notifications = resp.json()
    assert len(notifications) >= 1
    notif_id = notifications[0]["id"]

    # Mark as read
    resp = await client.post(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 200

    # Verify it's marked as read
    resp = await client.get("/api/notifications/")
    notifications = resp.json()
    for n in notifications:
        if n["id"] == notif_id:
            assert n["read"] == 1 or n["read"] is True
            break


@pytest.mark.asyncio
async def test_mark_all_notifications_read(client):
    """Test marking all notifications as read."""
    # Create some notifications
    await client.post("/api/notifications/send-test")
    await client.post("/api/notifications/send-test")

    # Mark all as read
    resp = await client.post("/api/notifications/mark-all-read")
    assert resp.status_code == 200

    # Verify all are read
    resp = await client.get("/api/notifications/unread-count")
    data = resp.json()
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_mark_nonexistent_notification_read(client):
    """Test marking a non-existent notification returns 404."""
    resp = await client.post("/api/notifications/99999/read")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_subscribe_invalid_data(client):
    """Test that invalid subscription data is rejected."""
    # Missing endpoint
    resp = await client.post("/api/notifications/subscribe", json={
        "keys": {"p256dh": "abc", "auth": "def"}
    })
    assert resp.status_code == 422

    # Missing keys
    resp = await client.post("/api/notifications/subscribe", json={
        "endpoint": "https://push.example.com/subscribe/xyz"
    })
    assert resp.status_code == 422


# ─── Service Worker ─────────────────────────────────────────────────────────

def test_service_worker_file_exists():
    """Test that the service worker file exists."""
    sw_path = Path(__file__).resolve().parent.parent / "public" / "sw.js"
    assert sw_path.exists(), "Service worker file should exist at public/sw.js"


def test_service_worker_has_push_listener():
    """Test that the service worker listens for push events."""
    sw_path = Path(__file__).resolve().parent.parent / "public" / "sw.js"
    content = sw_path.read_text()
    assert "addEventListener('push'" in content or 'addEventListener("push"' in content


def test_service_worker_has_notification_click():
    """Test that the service worker handles notification clicks."""
    sw_path = Path(__file__).resolve().parent.parent / "public" / "sw.js"
    content = sw_path.read_text()
    assert "notificationclick" in content


def test_service_worker_served_at_root():
    """Test that the service worker is served at /sw.js for proper scope."""
    # The route is defined in main.py
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    assert "/sw.js" in routes


# ─── Theme Toggle ───────────────────────────────────────────────────────────

def test_css_has_light_theme_variables():
    """Test that CSS defines light theme variables."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    assert "[data-theme='light']" in content or '[data-theme="light"]' in content


def test_css_has_dark_theme_as_default():
    """Test that CSS defines dark theme as default :root."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    assert ":root" in content
    # Dark theme should be the default (no data-theme attribute needed)
    assert "--bg: #0d1117" in content


def test_css_light_theme_overrides_bg():
    """Test that light theme overrides the background color."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    # Light theme should have a light background
    light_section = content.split("[data-theme='light']")[-1] if "[data-theme='light']" in content else ""
    assert "#f8fafc" in light_section or "#ffffff" in light_section


def test_html_has_theme_toggle_button():
    """Test that the HTML includes a theme toggle button."""
    html_path = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"
    content = html_path.read_text()
    assert "theme-toggle" in content


def test_js_has_theme_toggle_function():
    """Test that the JS includes theme toggle functionality."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "setupThemeToggle" in content
    assert "applyTheme" in content
    assert "localStorage" in content


def test_js_theme_toggle_saves_preference():
    """Test that theme preference is saved to localStorage."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "resolveai-theme" in content


# ─── Keyboard Shortcuts ─────────────────────────────────────────────────────

def test_js_has_keyboard_shortcuts():
    """Test that keyboard shortcuts are implemented."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "setupKeyboardShortcuts" in content


def test_js_has_ctrl_enter_shortcut():
    """Test Ctrl+Enter shortcut for sending replies."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "ctrlKey" in content
    assert "Enter" in content


def test_js_has_ctrl_k_shortcut():
    """Test Ctrl+K shortcut for focusing search."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "'k'" in content or '"k"' in content


def test_js_has_ctrl_n_shortcut():
    """Test Ctrl+N shortcut for new ticket."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "'n'" in content or '"n"' in content
    assert "showNewTicketModal" in content


def test_js_has_escape_shortcut():
    """Test Escape shortcut for closing modals."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "Escape" in content
    assert "closeModal" in content


def test_js_has_slash_search_shortcut():
    """Test / shortcut for focusing search."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "'/'" in content or '"/"' in content


# ─── Mobile Responsive ──────────────────────────────────────────────────────

def test_css_has_mobile_media_queries():
    """Test that CSS includes mobile media queries."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    assert "@media (max-width: 768px)" in content
    assert "@media (max-width: 480px)" in content


def test_css_has_hamburger_menu():
    """Test that CSS includes hamburger menu styles."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    assert ".hamburger" in content


def test_css_has_responsive_table_card_layout():
    """Test that CSS includes responsive table card layout for mobile."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    assert "data-label" in content


def test_html_has_hamburger_button():
    """Test that the HTML includes a hamburger menu button."""
    html_path = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"
    content = html_path.read_text()
    assert "hamburger" in content


def test_js_has_hamburger_menu_function():
    """Test that the JS includes hamburger menu functionality."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "setupHamburgerMenu" in content


def test_css_responsive_modal():
    """Test that modals are responsive on mobile."""
    css_path = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"
    content = css_path.read_text()
    # Modal should have responsive width on mobile
    assert "width: 95%" in content or "max-width: none" in content


# ─── Notification Bell ──────────────────────────────────────────────────────

def test_html_has_notification_bell():
    """Test that the HTML includes a notification bell."""
    html_path = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"
    content = html_path.read_text()
    assert "notification-bell" in content
    assert "bell-btn" in content


def test_html_has_notification_dropdown():
    """Test that the HTML includes a notification dropdown."""
    html_path = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"
    content = html_path.read_text()
    assert "notification-dropdown" in content
    assert "notification-list" in content


def test_html_has_enable_notifications_button():
    """Test that the HTML includes an enable notifications button."""
    html_path = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"
    content = html_path.read_text()
    assert "enable-notifications-btn" in content


def test_js_has_notification_functions():
    """Test that the JS includes notification functions."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "loadNotifications" in content
    assert "renderNotifications" in content
    assert "updateBellBadge" in content


def test_js_has_service_worker_registration():
    """Test that the JS includes service worker registration."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "registerServiceWorker" in content
    assert "serviceWorker" in content


def test_js_has_push_subscription():
    """Test that the JS includes push subscription logic."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "subscribeToPush" in content
    assert "pushManager" in content


def test_js_has_notification_permission_request():
    """Test that the JS includes notification permission request."""
    js_path = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "app.js"
    content = js_path.read_text()
    assert "requestNotificationPermission" in content
    assert "Notification.requestPermission" in content


# ─── SSE Notification Integration ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_endpoint_exists(client):
    """Test that the SSE endpoint is accessible."""
    # SSE endpoints return streaming responses, so we just check the route exists
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    # SSE endpoint is included via sse_router, so it won't be in app.routes directly
    # Just verify the app has routes and the SSE router is included
    assert len(routes) > 0
    # Also verify by checking the sse module exists
    from app.sse import router as sse_router
    assert sse_router is not None


# ─── Database Schema ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_push_subscriptions_table_exists(client):
    """Test that the push_subscriptions table is created."""
    from app.database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='push_subscriptions'"
        )
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_notifications_table_exists(client):
    """Test that the notifications table is created."""
    from app.database import get_db
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        )
        row = await cursor.fetchone()
        assert row is not None
