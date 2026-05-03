# tests/test_bot_tenant_routing.py
"""Tests for Telegram bot tenant routing via deep linking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from bot.main import (
    _get_user_tenant,
    _parse_deep_link_tenant,
    _validate_tenant_id,
    cmd_start,
    cmd_my_data,
    cmd_delete_account,
    process_delete_account,
)


class TestDeepLinkParsing:
    """Test deep link payload extraction."""

    def test_parse_with_tenant_payload(self) -> None:
        """Should extract tenant_id from /start <payload>."""
        msg = MagicMock(spec=Message)
        msg.text = "/start demo"
        assert _parse_deep_link_tenant(msg) == "demo"  # nosec B101

    def test_parse_without_payload(self) -> None:
        """Should return None for bare /start."""
        msg = MagicMock(spec=Message)
        msg.text = "/start"
        assert _parse_deep_link_tenant(msg) is None  # nosec B101

    def test_parse_with_extra_spaces(self) -> None:
        """Should handle extra whitespace."""
        msg = MagicMock(spec=Message)
        msg.text = "/start   bistro_01  "
        assert _parse_deep_link_tenant(msg) == "bistro_01"  # nosec B101

    def test_parse_none_text(self) -> None:
        """Should return None when message text is missing."""
        msg = MagicMock(spec=Message)
        msg.text = None
        assert _parse_deep_link_tenant(msg) is None  # nosec B101


class TestTenantValidation:
    """Test tenant_id validation."""

    def test_valid_tenant_ids(self) -> None:
        """Common valid tenant identifiers should pass."""
        assert _validate_tenant_id("demo") is True  # nosec B101
        assert _validate_tenant_id("bistro_01") is True  # nosec B101
        assert _validate_tenant_id("myrestaurant") is True  # nosec B101

    def test_invalid_tenant_ids(self) -> None:
        """Invalid identifiers should fail."""
        assert _validate_tenant_id("") is False  # nosec B101
        assert _validate_tenant_id("123-start-with-number") is False  # nosec B101
        assert _validate_tenant_id("invalid with spaces") is False  # nosec B101
        assert _validate_tenant_id("a" * 70) is False  # nosec B101


class TestFSMTenantStorage:
    """Test tenant persistence in FSM state."""

    @pytest.mark.asyncio
    async def test_get_tenant_returns_stored_value(self) -> None:
        """Should retrieve tenant_id previously stored in state."""
        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={"tenant_id": "demo"})
        result = await _get_user_tenant(mock_state)
        assert result == "demo"  # nosec B101

    @pytest.mark.asyncio
    async def test_get_tenant_returns_none_when_missing(self) -> None:
        """Should return None when tenant_id was never stored."""
        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={})
        result = await _get_user_tenant(mock_state)
        assert result is None  # nosec B101


class TestCmdStartTenantRouting:
    """Test /start command with various tenant scenarios."""

    @pytest.fixture
    def message(self) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.from_user.first_name = "Test"
        msg.answer = AsyncMock()
        return msg

    @pytest.fixture
    def state(self) -> FSMContext:
        st = MagicMock(spec=FSMContext)
        st.clear = AsyncMock()
        st.update_data = AsyncMock()
        st.get_data = AsyncMock(return_value={})
        return st

    @pytest.mark.asyncio
    async def test_start_with_tenant_payload(self, message: Message, state: FSMContext) -> None:
        """Deep link /start demo should persist mapping and show menu link with demo."""
        message.text = "/start demo"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                with patch(
                    "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)
                ):
                    await cmd_start(message, state)

        mock_set.assert_awaited_once_with(123, "demo")
        state.update_data.assert_awaited_once_with(tenant_id="demo")
        markup = message.answer.await_args[1]["reply_markup"]  # type: ignore[attr-defined]
        button = markup.inline_keyboard[0][0]
        assert "demo" in button.web_app.url  # nosec B101

    @pytest.mark.asyncio
    async def test_start_without_payload_uses_db_mapping(
        self, message: Message, state: FSMContext
    ) -> None:
        """Bare /start should recover tenant from DB mapping if present."""
        message.text = "/start"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                with patch(
                    "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value="bistro_01")
                ) as mock_get:
                    await cmd_start(message, state)

        mock_get.assert_awaited_once_with(123)
        mock_set.assert_awaited_once_with(123, "bistro_01")
        state.update_data.assert_awaited_once_with(tenant_id="bistro_01")
        markup = message.answer.await_args[1]["reply_markup"]  # type: ignore[attr-defined]
        assert "bistro_01" in markup.inline_keyboard[0][0].web_app.url  # nosec B101

    @pytest.mark.asyncio
    async def test_start_without_payload_no_mapping_no_default(
        self, message: Message, state: FSMContext
    ) -> None:
        """Bare /start without DB mapping and without default tenant should show error."""
        message.text = "/start"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                with patch(
                    "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)
                ):
                    with patch("bot.main.settings.TELEGRAM_BOT_DEFAULT_TENANT_ID", None):
                        await cmd_start(message, state)

        mock_set.assert_not_awaited()
        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Не удалось определить ресторан" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_start_without_payload_with_default(
        self, message: Message, state: FSMContext
    ) -> None:
        """Bare /start with default tenant configured should use it when DB mapping is absent."""
        message.text = "/start"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                with patch(
                    "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)
                ):
                    with patch("bot.main.settings.TELEGRAM_BOT_DEFAULT_TENANT_ID", "demo"):
                        await cmd_start(message, state)

        mock_set.assert_awaited_once_with(123, "demo")
        state.update_data.assert_awaited_once_with(tenant_id="demo")
        markup = message.answer.await_args[1]["reply_markup"]  # type: ignore[attr-defined]
        assert "demo" in markup.inline_keyboard[0][0].web_app.url  # nosec B101

    @pytest.mark.asyncio
    async def test_start_with_invalid_tenant(self, message: Message, state: FSMContext) -> None:
        """Invalid tenant payload should show error without storing anything."""
        message.text = "/start 123-invalid"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                await cmd_start(message, state)

        mock_set.assert_not_awaited()
        state.update_data.assert_not_awaited()  # type: ignore[attr-defined]
        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Некорректная ссылка" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_repeated_start_updates_mapping(
        self, message: Message, state: FSMContext
    ) -> None:
        """Second deep link with different tenant should update DB mapping."""
        message.text = "/start bistro_b"

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.set_tenant_for_telegram_user", AsyncMock()) as mock_set:
                with patch(
                    "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value="bistro_a")
                ):
                    await cmd_start(message, state)

        mock_set.assert_awaited_once_with(123, "bistro_b")
        state.update_data.assert_awaited_once_with(tenant_id="bistro_b")


class TestTenantAwareCommands:
    """Test tenant-aware behaviour of /menu, /cart, /order."""

    @pytest.fixture
    def message(self) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.answer = AsyncMock()
        return msg

    @pytest.fixture
    def state_with_tenant(self) -> FSMContext:
        st = MagicMock(spec=FSMContext)
        st.get_data = AsyncMock(return_value={"tenant_id": "demo"})
        st.set_state = AsyncMock()
        return st

    @pytest.fixture
    def state_without_tenant(self) -> FSMContext:
        st = MagicMock(spec=FSMContext)
        st.get_data = AsyncMock(return_value={})
        return st

    @pytest.mark.asyncio
    async def test_menu_with_tenant_shows_widget_link(
        self, message: Message, state_with_tenant: FSMContext
    ) -> None:
        """/menu with tenant should include widget button with correct tenant."""
        from bot.main import cmd_menu

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_menu(message, state_with_tenant)

        markup = message.answer.await_args[1]["reply_markup"]  # type: ignore[attr-defined]
        button = markup.inline_keyboard[0][0]
        assert "demo" in button.web_app.url  # nosec B101

    @pytest.mark.asyncio
    async def test_menu_without_tenant_shows_error(
        self, message: Message, state_without_tenant: FSMContext
    ) -> None:
        """/menu without tenant should show instruction, not crash."""
        from bot.main import cmd_menu

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)):
                await cmd_menu(message, state_without_tenant)

        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Не удалось определить ресторан" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_cart_with_tenant_shows_tenant_name(
        self, message: Message, state_with_tenant: FSMContext
    ) -> None:
        """/cart with tenant should reference the tenant."""
        from bot.main import cmd_cart

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_cart(message, state_with_tenant)

        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "demo" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_cart_without_tenant_shows_error(
        self, message: Message, state_without_tenant: FSMContext
    ) -> None:
        """/cart without tenant should show instruction."""
        from bot.main import cmd_cart

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)):
                await cmd_cart(message, state_without_tenant)

        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Не удалось определить ресторан" in call_args  # nosec B101

    @pytest.mark.asyncio
    async def test_order_with_tenant_shows_widget_link(
        self, message: Message, state_with_tenant: FSMContext
    ) -> None:
        """/order with tenant should include widget button with correct tenant."""
        from bot.main import cmd_order

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_order(message, state_with_tenant)

        markup = message.answer.await_args[1]["reply_markup"]  # type: ignore[attr-defined]
        button = markup.inline_keyboard[3][0]
        assert "demo" in button.web_app.url  # nosec B101

    @pytest.mark.asyncio
    async def test_order_without_tenant_shows_error(
        self, message: Message, state_without_tenant: FSMContext
    ) -> None:
        """/order without tenant should show instruction."""
        from bot.main import cmd_order

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch("bot.main.get_tenant_for_telegram_user", AsyncMock(return_value=None)):
                await cmd_order(message, state_without_tenant)

        call_args = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Не удалось определить ресторан" in call_args  # nosec B101


class TestTenantPersistenceAcrossCommands:
    """Test that tenant context survives non-start commands."""

    @pytest.mark.asyncio
    async def test_tenant_survives_help_command(self) -> None:
        """/help should clear FSM state but preserve tenant data."""
        from bot.main import cmd_help

        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.set_state = AsyncMock()

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_help(msg, state)

        state.set_state.assert_awaited_once_with(None)
        state.clear.assert_not_awaited()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_tenant_retained_after_text_fallback(self) -> None:
        """Text fallback should clear FSM state but preserve tenant data."""
        from bot.main import handle_text

        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.set_state = AsyncMock()

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await handle_text(msg, state)

        state.set_state.assert_awaited_once_with(None)
        state.clear.assert_not_awaited()  # type: ignore[attr-defined]


class TestTenantAwarePersonalData:
    """Test tenant-aware behaviour of /my_data and /delete_account."""

    @pytest.fixture
    def message(self) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = 123
        msg.answer = AsyncMock()
        return msg

    @pytest.fixture
    def state_with_tenant(self) -> FSMContext:
        st = MagicMock(spec=FSMContext)
        st.get_data = AsyncMock(return_value={"tenant_id": "demo"})
        st.update_data = AsyncMock()
        return st

    @pytest.mark.asyncio
    async def test_my_data_uses_real_tenant_user_data(
        self, message: Message, state_with_tenant: FSMContext
    ) -> None:
        """Should render tenant-specific user data instead of placeholder text."""
        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch(
                "bot.main._get_tenant_user_data",
                AsyncMock(
                    return_value={
                        "id": 10,
                        "name": "Иван",
                        "phone": "+79990000000",
                        "email": "ivan@example.com",
                        "loyalty_points": 42.0,
                        "orders_count": 3,
                        "last_order_at": None,
                    }
                ),
            ):
                await cmd_my_data(message, state_with_tenant)

        text = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Ресторан: demo" in text  # nosec B101
        assert "Иван" in text  # nosec B101
        assert "Баллы: 42.00" in text  # nosec B101
        assert "[name]" not in text  # nosec B101

    @pytest.mark.asyncio
    async def test_my_data_recovers_tenant_from_db_mapping(self, message: Message) -> None:
        """Should recover tenant via telegram_user_tenants mapping when FSM has no tenant."""
        state = MagicMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={})
        state.update_data = AsyncMock()

        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            with patch(
                "bot.main.get_tenant_for_telegram_user", AsyncMock(return_value="bistro_01")
            ):
                with patch("bot.main._get_tenant_user_data", AsyncMock(return_value=None)):
                    await cmd_my_data(message, state)

        state.update_data.assert_awaited_once_with(tenant_id="bistro_01")
        text = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Ресторан: bistro_01" in text  # nosec B101

    @pytest.mark.asyncio
    async def test_delete_account_confirmation_is_tenant_aware(
        self, message: Message, state_with_tenant: FSMContext
    ) -> None:
        """Delete confirmation should include current tenant context."""
        with patch("bot.main.rate_limiter.is_allowed", AsyncMock(return_value=True)):
            await cmd_delete_account(message, state_with_tenant)

        text = message.answer.await_args[0][0]  # type: ignore[attr-defined]
        assert "Ресторан: demo" in text  # nosec B101

    @pytest.mark.asyncio
    async def test_confirm_delete_anonymizes_only_current_tenant(self) -> None:
        """Confirm delete should call tenant-scoped anonymization with current tenant."""
        callback = MagicMock(spec=CallbackQuery)
        callback_message = MagicMock(spec=Message)
        callback_message.answer = AsyncMock()
        callback_message.edit_text = AsyncMock()
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = 123
        callback.message = callback_message
        callback.answer = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.get_data = AsyncMock(return_value={"tenant_id": "demo"})
        state.update_data = AsyncMock()

        with patch("bot.main._anonymize_tenant_user_data", AsyncMock(return_value=True)) as mock_del:
            await process_delete_account(callback, state)  # type: ignore[arg-type]

        mock_del.assert_awaited_once_with("demo", 123)
        text = callback_message.edit_text.await_args[0][0]  # type: ignore[attr-defined]
        assert "Ресторан: demo" in text  # nosec B101
