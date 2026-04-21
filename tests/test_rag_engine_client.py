# tests/test_rag_engine_client.py
"""Tests for YandexGPT client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.rag_engine import YandexGPTClient


class TestYandexGPTClient:
    """Test YandexGPT API client."""

    @pytest.fixture
    def client(self) -> YandexGPTClient:
        return YandexGPTClient()

    @pytest.mark.asyncio
    async def test_embed_returns_list(self, client: YandexGPTClient) -> None:
        """embed should return embedding vector list."""
        mock_resp = AsyncMock()
        mock_resp.json = MagicMock(return_value={"embedding": [0.1, 0.2, 0.3]})

        with patch.object(client, "_get_iam_token", AsyncMock(return_value="token123")):
            with patch.object(client.client, "post", AsyncMock(return_value=mock_resp)):
                result = await client.embed("test query")
        assert result == [0.1, 0.2, 0.3]  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, client: YandexGPTClient) -> None:
        """generate should return generated text."""
        mock_resp = AsyncMock()
        mock_resp.json = MagicMock(
            return_value={"result": {"alternatives": [{"message": {"text": "Hello"}}]}}
        )

        with patch.object(client, "_get_iam_token", AsyncMock(return_value="token123")):
            with patch.object(client.client, "post", AsyncMock(return_value=mock_resp)):
                result = await client.generate("sys", "user")
        assert result == "Hello"  # nosec B101
