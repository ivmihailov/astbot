"""
Клиент ГосПлан API v2 (https://v2.gosplan.info).

Асинхронный REST-клиент на aiohttp для поиска:
- закупок (извещений) — GET /{law}/purchases
- контрактов — GET /{law}/contracts

API бесплатный до 01.07.2026, авторизация не нужна.
Документация API: https://gosplan.info/api
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from models import Contract, Purchase

logger = logging.getLogger(__name__)

# Маппинг law → префикс пути
_LAW_PREFIX: dict[int, str] = {
    44: "fz44",
    223: "fz223",
    615: "pprf615",
}

_DEFAULT_LAW_PREFIX = "fz44"


class GosplanAPI:
    """Асинхронный клиент для ГосПлан API v2.

    Attributes:
        base_url: Базовый URL API.
        _session: aiohttp-сессия (создаётся в open, закрывается в close).
    """

    def __init__(self, base_url: str = "https://v2.gosplan.info") -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def open(self) -> None:
        """Создать aiohttp-сессию. Вызывать при старте бота."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45),
        )

    async def close(self) -> None:
        """Закрыть aiohttp-сессию. Вызывать при остановке бота."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Публичные методы поиска
    # ------------------------------------------------------------------

    async def search_purchases(
        self,
        query: str,
        law: int | None = 44,
        limit: int = 20,
        skip: int = 0,
        region: str | None = None,
        days: int = 30,
    ) -> list[Purchase]:
        """Поиск закупок (извещений).

        Args:
            query: Текстовый запрос (наименование объекта закупки).
            law: Федеральный закон (44 / 223 / 615). None → 44-ФЗ.
            limit: Максимальное кол-во результатов.
            skip: Offset для пагинации.
            region: Код региона.
            days: За сколько дней искать.

        Returns:
            Список Purchase-объектов.
        """
        prefix = _LAW_PREFIX.get(law, _DEFAULT_LAW_PREFIX) if law else _DEFAULT_LAW_PREFIX
        url = f"{self.base_url}/{prefix}/purchases"
        params = self._build_query_params(
            search_text=query,
            text_param="object_info",
            limit=limit,
            skip=skip,
            region=region,
            days=days,
        )
        data = await self._request(url, params)
        return self._parse_purchases(data)

    async def search_contracts(
        self,
        query: str,
        law: int | None = 44,
        limit: int = 20,
        skip: int = 0,
        region: str | None = None,
        days: int = 30,
    ) -> list[Contract]:
        """Поиск контрактов.

        Args:
            query: Текстовый запрос (предмет контракта).
            law: Федеральный закон (44 / 223 / 615). None → 44-ФЗ.
            limit: Максимальное кол-во результатов.
            skip: Offset для пагинации.
            region: Код региона.
            days: За сколько дней искать.

        Returns:
            Список Contract-объектов.
        """
        prefix = _LAW_PREFIX.get(law, _DEFAULT_LAW_PREFIX) if law else _DEFAULT_LAW_PREFIX
        url = f"{self.base_url}/{prefix}/contracts"
        params = self._build_query_params(
            search_text=query,
            text_param="subject",
            limit=limit,
            skip=skip,
            region=region,
            days=days,
        )
        data = await self._request(url, params)
        return self._parse_contracts(data)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _build_query_params(
        self,
        *,
        search_text: str,
        text_param: str,
        limit: int,
        skip: int,
        region: str | None,
        days: int,
    ) -> dict[str, Any]:
        """Собрать query-параметры для HTTP-запроса.

        Args:
            search_text: Текст поиска.
            text_param: Имя параметра API ("object_info" или "subject").
            limit: Кол-во результатов.
            skip: Offset пагинации.
            region: Код региона.
            days: За сколько дней искать.

        Returns:
            Словарь query-параметров для aiohttp.
        """
        published_after = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        params: dict[str, Any] = {
            text_param: search_text,
            "limit": limit,
            "skip": skip,
            "published_after": published_after,
            "order_by": "-published_at",
        }
        if region:
            params["region"] = region
        return params

    async def _request(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Выполнить GET-запрос к API с обработкой ошибок.

        Returns:
            Список словарей из JSON-ответа или пустой список при ошибке.

        Raises:
            aiohttp.ClientResponseError: При HTTP 429 (rate limit).
        """
        if not self._session:
            raise RuntimeError("Сессия не открыта. Вызовите open() перед запросами.")

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 429:
                    logger.error("ГосПлан API: rate limit (429)")
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=429,
                        message="Rate limit exceeded",
                    )
                if resp.status == 422:
                    body = await resp.text()
                    logger.warning("ГосПлан API: невалидные параметры (422): %s", body)
                    return []

                resp.raise_for_status()
                return await resp.json()

        except asyncio.TimeoutError:
            logger.warning("ГосПлан API: таймаут запроса %s", url)
            return []
        except aiohttp.ClientResponseError:
            raise
        except aiohttp.ClientError as exc:
            logger.warning("ГосПлан API: ошибка сети: %s", exc)
            return []

    def _parse_purchases(self, data: list[dict[str, Any]]) -> list[Purchase]:
        """Распарсить JSON-ответ API в список Purchase."""
        results: list[Purchase] = []
        for item in data:
            try:
                if "region" in item and item["region"] is not None:
                    item["region"] = str(item["region"])
                results.append(Purchase.model_validate(item))
            except Exception as exc:
                logger.warning("Не удалось распарсить закупку: %s", exc)
        return results

    def _parse_contracts(self, data: list[dict[str, Any]]) -> list[Contract]:
        """Распарсить JSON-ответ API в список Contract."""
        results: list[Contract] = []
        for item in data:
            try:
                if "region" in item and item["region"] is not None:
                    item["region"] = str(item["region"])
                results.append(Contract.model_validate(item))
            except Exception as exc:
                logger.warning("Не удалось распарсить контракт: %s", exc)
        return results


if __name__ == "__main__":

    async def main() -> None:
        logging.basicConfig(level=logging.INFO)
        api = GosplanAPI()
        await api.open()
        try:
            purchases = await api.search_purchases("цистерна", law=44)
            print(f"Найдено закупок: {len(purchases)}\n")
            for i, p in enumerate(purchases, 1):
                print(f"{i}. [{p.purchase_number}]")
                print(f"   Объект: {p.object_info}")
                print(f"   Цена: {p.max_price}")
                print(f"   Регион: {p.region}")
                print(f"   Опубликовано: {p.published_at}")
                print()
        finally:
            await api.close()

    asyncio.run(main())
