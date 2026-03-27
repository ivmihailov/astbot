"""
Обработчики команд и сообщений бота MAX.

Определяет логику реакции на:
- /start — приветствие и инструкция
- /help — справка по командам
- Текстовые сообщения — поиск закупок/контрактов
- «ещё» / «далее» — пагинация (следующая страница)
- Число (1-N) — детали конкретного результата
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

import aiohttp

from formatters import (
    format_card,
    format_contract_detail,
    format_error,
    format_filter_panel,
    format_no_results,
    format_purchase_detail,
    format_search_params,
)
from gigachat_client import GigaChatClient
from gosplan_api import GosplanAPI
from models import Contract, Purchase, ResultType, SearchParams, SearchType
from state import StateManager

logger = logging.getLogger(__name__)

_NEXT_PAGE_PATTERN = re.compile(
    r"^(дальше|далее|ещё|еще|next)$", re.IGNORECASE
)


_ARTICLE_PATTERN = re.compile(
    r"^[A-Za-zА-Яа-яЁё0-9]{1,10}[-.]?[A-Za-zА-Яа-яЁё0-9]+(?:[-/.][A-Za-zА-Яа-яЁё0-9]+)*"
    r"(?:\s*\([A-Za-zА-Яа-яЁё0-9\s./-]+\))?$"
)


def _looks_like_article(text: str) -> bool:
    """Проверить, является ли запрос артикулом/номером детали.

    Артикулы содержат смесь букв, цифр и спецсимволов (-./),
    иногда с пояснением в скобках. Примеры:
        ПР1М-ЭЦК
        ПР1М-ЭЦК (36763-201-00М)
        DN50-PN16
        ГОСТ 12820-80
    """
    stripped = text.strip()
    if not stripped:
        return False
    # Содержит цифры И буквы И хотя бы один спецсимвол (-, ., /)
    has_digits = any(c.isdigit() for c in stripped)
    has_letters = any(c.isalpha() for c in stripped)
    has_special = any(c in "-./(" for c in stripped)
    if has_digits and has_letters and has_special:
        return True
    # Или чисто буквенно-цифровой код длиной <= 20 символов без пробелов
    no_parens = stripped.split("(")[0].strip()
    if len(no_parens) <= 20 and has_digits and has_letters and " " not in no_parens:
        return True
    return False


class Handlers:
    """Обработчики событий бота.

    Получает зависимости (клиенты API, state manager) через конструктор
    и регистрирует обработчики на диспетчере бота MAX.

    Attributes:
        gosplan: Клиент ГосПлан API.
        gigachat: Клиент GigaChat.
        state: Менеджер состояния пользователей.
    """

    # Ограничиваем параллельные запросы к API (защита от таймаутов)
    _api_semaphore = asyncio.Semaphore(3)

    def __init__(
        self,
        gosplan: GosplanAPI,
        gigachat: GigaChatClient,
        state: StateManager,
    ) -> None:
        self.gosplan = gosplan
        self.gigachat = gigachat
        self.state = state

    # ------------------------------------------------------------------
    # Команды
    # ------------------------------------------------------------------

    async def handle_start(self, chat_id: int) -> str:
        """Обработчик команды /start.

        Отправляет приветственное сообщение с описанием возможностей бота.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Текст приветственного сообщения.
        """
        return (
            "Привет! Я бот для поиска государственных закупок и контрактов.\n\n"
            "Просто напишите, что хотите найти, например:\n"
            '- "закупки на поставку компьютеров"\n'
            '- "контракты по нефтепродуктам за месяц"\n'
            '- "тендеры в Астраханской области по 223-ФЗ"\n\n'
            "Я найду актуальные данные на ГосПлан и покажу результаты.\n\n"
            "Команды:\n"
            "/help — справка и примеры запросов"
        )

    async def handle_help(self, chat_id: int) -> str:
        """Обработчик команды /help.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Текст справки по командам бота.
        """
        return (
            "Примеры запросов:\n"
            '- "закупки на цистерны"\n'
            '- "свежие контракты по нефтепродуктам"\n'
            '- "закупки по 223-ФЗ за месяц"\n'
            '- "тендеры в Астраханской области"\n\n'
            "Навигация по результатам:\n"
            "- Отправьте номер (1, 2, 3...) — подробности о результате\n"
            '- Отправьте "дальше" или "ещё" — следующая страница\n\n'
            "Я понимаю естественный язык: указывайте регион, "
            "закон (44-ФЗ / 223-ФЗ), период и тип (закупки или контракты)."
        )

    # ------------------------------------------------------------------
    # Основной обработчик
    # ------------------------------------------------------------------

    async def handle_message(self, chat_id: int, text: str) -> str:
        """Основной обработчик текстовых сообщений.

        Логика:
        1. Если текст — число → показать детали результата по индексу.
        2. Если текст — «ещё» / «далее» → загрузить следующую страницу.
        3. Иначе → распарсить запрос через GigaChat, найти через ГосПлан,
           сформировать ответ через GigaChat.

        Args:
            chat_id: Идентификатор чата.
            text: Текст сообщения от пользователя.

        Returns:
            Текст ответа для отправки в чат.
        """
        stripped = text.strip()

        # Число → детали
        if stripped.isdigit():
            index = int(stripped)
            return await self.handle_detail(chat_id, index)

        # Пагинация
        if _NEXT_PAGE_PATTERN.match(stripped):
            return await self.handle_next_page(chat_id)

        # Новый поиск
        return await self._handle_search(chat_id, stripped)

    # ------------------------------------------------------------------
    # Детали по номеру
    # ------------------------------------------------------------------

    async def handle_detail(self, chat_id: int, index: int) -> str:
        """Показать подробности результата по номеру.

        Достаёт элемент из state, отправляет в GigaChat для
        подробного описания (или fallback через formatters).

        Args:
            chat_id: Идентификатор чата.
            index: Номер результата (1-based).

        Returns:
            Детальная информация о закупке/контракте.
        """
        item = self.state.get_result_by_index(chat_id, index)
        if item is None:
            state = self.state.get_state(chat_id)
            total = len(state.last_results)
            if total == 0:
                return "Сначала выполните поиск, а потом запрашивайте детали по номеру."
            return f"Нет результата с номером {index}. Доступны номера от 1 до {total}."

        try:
            return await self.gigachat.format_single_result(item)
        except Exception as exc:
            logger.warning("GigaChat недоступен для деталей: %s", exc)
            if isinstance(item, Purchase):
                return format_purchase_detail(item)
            return format_contract_detail(item)

    # ------------------------------------------------------------------
    # Пагинация
    # ------------------------------------------------------------------

    async def handle_next_page(self, chat_id: int) -> str:
        """Загрузить следующую страницу результатов.

        Увеличивает skip, повторяет запрос к ГосПлан API
        с теми же параметрами.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Следующая порция результатов или сообщение «больше нет».
        """
        state = self.state.get_state(chat_id)
        if state.last_params is None:
            return "Нет активного поиска. Сначала отправьте запрос."

        params = state.last_params
        skip = self.state.next_page(chat_id)

        try:
            results = await self._do_search(params, skip)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                return "Слишком много запросов. Подождите минуту и попробуйте снова."
            return format_error("Ошибка при обращении к ГосПлан API.")
        except Exception as exc:
            logger.error("Ошибка пагинации: %s", exc)
            return format_error("Не удалось загрузить следующую страницу.")

        if not results:
            return "Больше результатов нет. Попробуйте новый запрос."

        result_type = (
            ResultType.PURCHASES
            if params.search_type == SearchType.PURCHASES
            else ResultType.CONTRACTS
        )
        self.state.save_results(chat_id, results, params, result_type)

        return self.get_current_card(chat_id) or "Ошибка форматирования."

    # ------------------------------------------------------------------
    # Парсинг запроса (для кнопочного flow)
    # ------------------------------------------------------------------

    async def parse_query(self, chat_id: int, text: str) -> SearchParams:
        """Распарсить текст пользователя через GigaChat и сохранить в pending.

        Не выполняет поиск — только парсинг и сохранение в state.

        Args:
            chat_id: Идентификатор чата.
            text: Текст запроса пользователя.

        Returns:
            Распарсенные параметры поиска.
        """
        params = await self.gigachat.parse_user_query(text)
        # Для контрактов active_only не применим
        if params.search_type == SearchType.CONTRACTS:
            params = params.model_copy(update={"active_only": False})
        logger.info("Параметры поиска (pending): %s", params.model_dump_json())
        self.state.save_pending(chat_id, params)
        return params

    def update_filter(
        self, chat_id: int, field: str, value: Any
    ) -> SearchParams | None:
        """Обновить один фильтр в pending_params.

        Args:
            chat_id: Идентификатор чата.
            field: Имя поля SearchParams (days, law, active_only).
            value: Новое значение.

        Returns:
            Обновлённые SearchParams или None.
        """
        params = self.state.get_pending(chat_id)
        if params is None:
            return None
        params = params.model_copy(update={field: value})
        self.state.save_pending(chat_id, params)
        return params

    def get_filter_panel(self, chat_id: int) -> str | None:
        """Получить текст панели фильтров для pending_params.

        Returns:
            Текст панели или None, если нет pending_params.
        """
        params = self.state.get_pending(chat_id)
        if params is None:
            return None
        return format_filter_panel(params)

    async def execute_search(self, chat_id: int, days: int | None = None, limit: int | None = None) -> str:
        """Выполнить поиск по pending_params.

        Args:
            chat_id: Идентификатор чата.
            days: Период поиска (если None — из pending_params).
            limit: Количество результатов (если None — из pending_params).

        Returns:
            Отформатированный текст первой карточки результатов.
        """
        params = self.state.get_pending(chat_id)
        if params is None:
            return "Сначала отправьте поисковый запрос."

        updates: dict[str, Any] = {}
        if days is not None:
            updates["days"] = days
        if limit is not None:
            updates["limit"] = limit
        if updates:
            params = params.model_copy(update=updates)

        header = format_search_params(params)

        try:
            results = await self._do_search(params, skip=0)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                return "Слишком много запросов к ГосПлан API. Подождите минуту и попробуйте снова."
            return format_error("Ошибка при обращении к ГосПлан API.")
        except Exception as exc:
            logger.error("Ошибка поиска в ГосПлан API: %s", exc)
            return format_error("Не удалось выполнить поиск. Попробуйте позже.")

        result_type = (
            ResultType.PURCHASES
            if params.search_type == SearchType.PURCHASES
            else ResultType.CONTRACTS
        )
        # Всегда сохраняем — даже пустой список, чтобы сбросить старые данные
        self.state.save_results(chat_id, results, params, result_type)

        if not results:
            return f"{header}\n\n{format_no_results(params)}"

        body = self.get_current_card(chat_id) or "Ошибка форматирования."
        return f"{header}\n\n{body}"

    async def switch_search_type(self, chat_id: int, new_type: str) -> str:
        """Переключить тип поиска (закупки ↔ контракты) и повторить запрос.

        Использует параметры последнего поиска, меняя только search_type.

        Args:
            chat_id: Идентификатор чата.
            new_type: "purchases" или "contracts".

        Returns:
            Отформатированный текст результатов нового типа.
        """
        st = self.state.get_state(chat_id)
        # pending_params — самый свежий запрос (даже если прошлый поиск был пустым)
        base_params = st.pending_params or st.last_params
        if base_params is None:
            return "Сначала отправьте поисковый запрос."

        search_type = (
            SearchType.PURCHASES if new_type == "purchases"
            else SearchType.CONTRACTS
        )
        params = base_params.model_copy(update={"search_type": search_type})

        header = format_search_params(params)

        try:
            results = await self._do_search(params, skip=0)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                return "Слишком много запросов к ГосПлан API. Подождите минуту и попробуйте снова."
            return format_error("Ошибка при обращении к ГосПлан API.")
        except Exception as exc:
            logger.error("Ошибка поиска (switch): %s", exc)
            return format_error("Не удалось выполнить поиск. Попробуйте позже.")

        result_type = (
            ResultType.PURCHASES
            if search_type == SearchType.PURCHASES
            else ResultType.CONTRACTS
        )
        self.state.save_results(chat_id, results, params, result_type)

        if not results:
            return f"{header}\n\n{format_no_results(params)}"

        body = self.get_current_card(chat_id) or "Ошибка форматирования."
        return f"{header}\n\n{body}"

    # ------------------------------------------------------------------
    # Полный цикл поиска (fallback для текстовых команд)
    # ------------------------------------------------------------------

    async def _handle_search(self, chat_id: int, text: str) -> str:
        """Выполнить полный цикл поиска.

        1. GigaChat парсит текст → SearchParams
        2. ГосПлан API ищет закупки/контракты
        3. Результаты сохраняются в state
        4. GigaChat формирует ответ (или fallback)

        Args:
            chat_id: Идентификатор чата.
            text: Текст запроса пользователя.

        Returns:
            Ответ с результатами поиска.
        """
        # 1. Парсинг запроса
        params = await self.gigachat.parse_user_query(text)
        logger.info("Параметры поиска: %s", params.model_dump_json())

        header = format_search_params(params)

        # 2. Поиск в ГосПлан API
        try:
            results = await self._do_search(params, skip=0)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                return "Слишком много запросов к ГосПлан API. Подождите минуту и попробуйте снова."
            return format_error("Ошибка при обращении к ГосПлан API.")
        except Exception as exc:
            logger.error("Ошибка поиска в ГосПлан API: %s", exc)
            return format_error("Не удалось выполнить поиск. Попробуйте позже.")

        # 3. Сохранение в state (даже пустой список — сбрасывает старые данные)
        result_type = (
            ResultType.PURCHASES
            if params.search_type == SearchType.PURCHASES
            else ResultType.CONTRACTS
        )
        self.state.save_results(chat_id, results, params, result_type)

        if not results:
            return f"{header}\n\n{format_no_results(params)}"

        # 4. Форматирование — первая карточка для карусели
        body = self.get_current_card(chat_id) or "Ошибка форматирования."
        return f"{header}\n\n{body}"

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    def _is_relevant(
        self, item: Purchase | Contract, queries: list[str]
    ) -> bool:
        """Проверить релевантность результата хотя бы одному из запросов.

        Результат считается релевантным, если ВСЕ значимые слова
        хотя бы одного запроса присутствуют в тексте (по первым 4 символам —
        грубый стемминг).

        Пример: queries=["фланец", "фланцы", "арматура фланцевая"]
        Текст "Арматура трубопроводная фланцевая" → "арматура фланцевая" матчит → True
        Текст "Соединение пластиковых труб" → ни один запрос не матчит → False
        """
        if isinstance(item, Purchase):
            text = (item.object_info or "").lower()
        else:
            text = (item.subject or "").lower()

        for query in queries:
            words = query.lower().split()
            # Длинные слова → стемминг (первые 4 символа), короткие → точное вхождение
            checks = []
            for w in words:
                if len(w) >= 4:
                    checks.append(w[:4])
                elif len(w) >= 2:
                    checks.append(w)
            if not checks:
                continue
            if all(c in text for c in checks):
                return True

        return False

    async def _throttled_search(
        self,
        search_fn,
        **kwargs,
    ) -> list[Purchase | Contract]:
        """Выполнить поисковый запрос с ограничением параллелизма."""
        async with self._api_semaphore:
            return await search_fn(**kwargs)

    async def _do_search(
        self, params: SearchParams, skip: int = 0
    ) -> list[Purchase | Contract]:
        """Выполнить запрос к ГосПлан API по параметрам + синонимам.

        Ищет по основному запросу и всем синонимам параллельно
        (с ограничением до 3 одновременных запросов),
        объединяет результаты и убирает дубли.

        Args:
            params: SearchParams с параметрами поиска.
            skip: Offset для пагинации.

        Returns:
            Список Purchase или Contract.
        """
        is_article = _looks_like_article(params.query)

        if not is_article and len(params.query.strip()) < 3:
            logger.warning("Запрос слишком короткий: %r", params.query)
            return []

        # Собираем все варианты запроса: основной + синонимы
        queries = [params.query]

        if is_article:
            # Для артикулов: разбираем на составные части
            # "ПР1М-ЭЦК (36763-201-00М)" → ["ПР1М-ЭЦК (36763-201-00М)", "ПР1М-ЭЦК", "36763-201-00М"]
            parts = re.split(r"[()\s]+", params.query.strip())
            for part in parts:
                part = part.strip(" .,;")
                if len(part) >= 3 and part.lower() != params.query.strip().lower():
                    queries.append(part)
            logger.info("Артикул: %r → варианты поиска: %s", params.query, queries)
        else:
            for s in params.synonyms:
                if s.strip() and s.strip().lower() != params.query.strip().lower():
                    queries.append(s.strip())

        # Лимит на каждый запрос
        per_query_limit = max(params.limit, 20)

        # Параллельные запросы с ограничением через семафор (макс. 3 одновременно)
        tasks = []
        search_fn = (
            self.gosplan.search_contracts
            if params.search_type == SearchType.CONTRACTS
            else self.gosplan.search_purchases
        )
        for q in queries:
            if len(q) < 2:
                continue
            tasks.append(self._throttled_search(
                search_fn,
                query=q, law=params.law, limit=per_query_limit,
                skip=skip, region=params.region, days=params.days,
            ))

        all_results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Объединяем и дедуплицируем
        seen: set[str] = set()
        merged: list[Purchase | Contract] = []
        for result_or_exc in all_results_lists:
            if isinstance(result_or_exc, Exception):
                logger.warning("Ошибка одного из подзапросов: %s", result_or_exc)
                continue
            for item in result_or_exc:
                uid = item.purchase_number if isinstance(item, Purchase) else item.reg_num
                if uid not in seen:
                    seen.add(uid)
                    merged.append(item)

        # Фильтр релевантности — пропускаем для артикулов (они и так специфичные)
        if not is_article:
            merged = [r for r in merged if self._is_relevant(r, queries)]

        # Фильтр активности (только для закупок)
        if params.active_only and params.search_type == SearchType.PURCHASES and merged:
            now = datetime.now()
            active = [
                r for r in merged
                if not r.collecting_finished_at or r.collecting_finished_at >= now
            ]
            if active:
                merged = active
            else:
                # Все просрочены — показываем что есть, логируем
                logger.info("Активных закупок нет, показываем %d завершённых", len(merged))

        # Обрезаем до запрошенного лимита
        return merged[: params.limit]

    def get_current_card(self, chat_id: int) -> str | None:
        """Получить карточку текущего результата.

        Returns:
            Текст карточки или None, если нет результатов.
        """
        st = self.state.get_state(chat_id)
        if not st.last_results or st.result_type is None:
            return None
        idx = st.current_view_index
        return format_card(
            st.last_results[idx], idx, len(st.last_results), st.result_type
        )

    async def navigate(self, chat_id: int, direction: str) -> str | None:
        """Перейти к следующему/предыдущему результату.

        Args:
            chat_id: Идентификатор чата.
            direction: "next" или "prev".

        Returns:
            Текст карточки, "load_next_page" если нужно подгрузить,
            или None если навигация невозможна.
        """
        st = self.state.get_state(chat_id)
        if not st.last_results:
            return None

        if direction == "next":
            if st.current_view_index < len(st.last_results) - 1:
                st.current_view_index += 1
                return self.get_current_card(chat_id)
            # Дошли до конца загруженных — нужна новая страница
            return "load_next_page"

        if direction == "prev":
            if st.current_view_index > 0:
                st.current_view_index -= 1
                return self.get_current_card(chat_id)
            return None  # Уже первый

        return None

    async def load_next_page_and_navigate(self, chat_id: int) -> str | None:
        """Подгрузить следующую страницу из API и показать первый новый результат.

        Returns:
            Текст карточки первого результата новой страницы или сообщение.
        """
        st = self.state.get_state(chat_id)
        if st.last_params is None:
            return None

        params = st.last_params
        skip = self.state.next_page(chat_id)

        try:
            results = await self._do_search(params, skip)
        except Exception as exc:
            logger.error("Ошибка подгрузки страницы: %s", exc)
            return None

        if not results:
            return "end"

        result_type = (
            ResultType.PURCHASES
            if params.search_type == SearchType.PURCHASES
            else ResultType.CONTRACTS
        )
        self.state.save_results(chat_id, results, params, result_type)
        return self.get_current_card(chat_id)
