"""
Клиент GigaChat API.

Два режима использования:
1. Парсинг (parse) — извлечение параметров поиска из текста пользователя.
   Используется дешёвая модель (GigaChat). temperature=0.1.
2. Генерация ответа (answer) — формирование человекочитаемого ответа
   по результатам поиска. Используется качественная модель (GigaChat-Pro).
   temperature=0.3.

Авторизация: через gigachat SDK (pip install gigachat).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from models import Contract, Purchase, SearchParams, SearchType

logger = logging.getLogger(__name__)

_PARSE_SYSTEM_PROMPT = """\
Ты извлекаешь параметры поиска государственных закупок и контрактов из текста пользователя.

ЗАДАЧА: из текста пользователя извлеки ПРЕДМЕТ ЗАКУПКИ, определи код ОКПД2 и сгенерируй СИНОНИМЫ для расширенного поиска.

Ответь ТОЛЬКО валидным JSON без markdown и пояснений:
{"query": "основной запрос", "okpd2": "код ОКПД2", "okpd2_name": "название категории ОКПД2", "synonyms": ["синоним1", "синоним2", "синоним3"], "search_type": "purchases|contracts", "law": null, "days": null, "region": null, "limit": 20}

ГЛАВНОЕ ПРАВИЛО для query:
- query — это ПРЕДМЕТ/ОБЪЕКТ закупки: товар, услуга или работа
- Извлекай только существительные и прилагательные, описывающие предмет
- УБИРАЙ служебные слова: "найди", "покажи", "хочу", "нужны", "ищу", "дай", "по"

ПРАВИЛА для okpd2 и okpd2_name:
- Определи наиболее подходящий код ОКПД2 (2-4 уровня) для предмета закупки
- okpd2_name — полное официальное название этой категории ОКПД2
- Если не уверен — поставь null для обоих полей
- Примеры: "фланец" → okpd2: "28.14.20", okpd2_name: "Арматура трубопроводная промышленная"
- "бензин" → okpd2: "19.20.21", okpd2_name: "Бензины автомобильные"
- "компьютеры" → okpd2: "26.20.1", okpd2_name: "Компьютеры и периферийное оборудование"

ПРАВИЛА для synonyms (ОБЯЗАТЕЛЬНОЕ ПОЛЕ):
- synonyms — список из 3-7 альтернативных запросов для того же предмета
- ОБЯЗАТЕЛЬНО включи название категории ОКПД2 (okpd2_name) как один из синонимов
- Включай: другие падежи/формы числа, профессиональные термины, сокращения, названия смежных подкатегорий ОКПД2
- НЕ включай слова с другим смыслом
- Пример: "фланец" → ["фланцы", "фланцевый", "арматура трубопроводная", "фланцевое соединение", "арматура фланцевая"]
- Пример: "бензин" → ["бензина", "бензины автомобильные", "топливо моторное", "нефтепродукты", "ГСМ", "АИ-92"]
- Пример: "компьютеры" → ["компьютер", "ЭВМ", "ПЭВМ", "системный блок", "компьютеры и периферийное оборудование"]
- Пример: "трубы" → ["труба", "трубы стальные", "трубопровод", "трубы и фитинги", "трубная продукция"]

search_type:
- "контракт"/"контракты" в тексте → "contracts"
- "закупк"/"тендер"/"аукцион"/"конкурс" → "purchases"
- не указано явно → "purchases"

law: "223-ФЗ" → "223", "615"/"капремонт" → "615", не указано → null
days: "свежие"/"новые" → 7, "за неделю" → 7, "за месяц" → 30, "за 3 месяца" → 90, "за год" → 365, не указано → null
region: Москва → "77", СПб → "78", Астраханская → "30", Краснодарский → "23", Новосибирская → "54", Свердловская → "66", Татарстан → "16", не указано → null

ПРАВИЛА для АРТИКУЛОВ и НОМЕРОВ ДЕТАЛЕЙ:
- Если пользователь ввёл артикул, маркировку, номер детали или ГОСТ (содержит буквы + цифры + спецсимволы: -, ., /):
  - query = артикул КАК ЕСТЬ, без изменений
  - synonyms = [] (пустой список — не придумывай синонимы для артикулов!)
  - okpd2 = null, okpd2_name = null
- Примеры артикулов: "ПР1М-ЭЦК", "36763-201-00М", "DN50-PN16", "ГОСТ 12820-80", "КС7073.000"

ПРИМЕРЫ:
"фланец" → {"query": "фланец", "okpd2": "28.14.20", "okpd2_name": "Арматура трубопроводная промышленная", "synonyms": ["фланцы", "фланцевый", "арматура трубопроводная", "фланцевое соединение", "арматура фланцевая"], "search_type": "purchases", "law": null, "days": null, "region": null, "limit": 20}
"найди контракты по бензину" → {"query": "бензин", "okpd2": "19.20.21", "okpd2_name": "Бензины автомобильные", "synonyms": ["бензина", "бензины автомобильные", "топливо моторное", "нефтепродукты", "ГСМ"], "search_type": "contracts", "law": null, "days": null, "region": null, "limit": 20}
"закупки на компьютеры в Москве" → {"query": "компьютеры", "okpd2": "26.20.1", "okpd2_name": "Компьютеры и периферийное оборудование", "synonyms": ["компьютер", "ЭВМ", "ПЭВМ", "системный блок", "компьютеры и периферийное оборудование"], "search_type": "purchases", "law": null, "days": null, "region": "77", "limit": 20}
"медицинское оборудование" → {"query": "медицинское оборудование", "okpd2": "26.60", "okpd2_name": "Оборудование и аппаратура для облучения, медицинские и терапевтические средства", "synonyms": ["медоборудование", "медтехника", "медицинская техника", "медицинские изделия", "медицинские аппараты"], "search_type": "purchases", "law": null, "days": null, "region": null, "limit": 20}
"ПР1М-ЭЦК (36763-201-00М)" → {"query": "ПР1М-ЭЦК (36763-201-00М)", "okpd2": null, "okpd2_name": null, "synonyms": [], "search_type": "purchases", "law": null, "days": null, "region": null, "limit": 20}
"ГОСТ 12820-80" → {"query": "ГОСТ 12820-80", "okpd2": null, "okpd2_name": null, "synonyms": [], "search_type": "purchases", "law": null, "days": null, "region": null, "limit": 20}"""

_FORMAT_LIST_SYSTEM_PROMPT = """\
Ты — помощник по госзакупкам. Сформируй краткий список результатов для мессенджера.
- Общая сводка: сколько найдено, диапазон цен
- Пронумерованный список: номер, предмет (до 80 символов), цена, дата
- В конце: "Отправьте номер (1-N) для подробностей, или «дальше» для следующей страницы"
- Если пусто — предложи расширить поиск
- Формат компактный, для мессенджера, без лишних украшений"""

_FORMAT_SINGLE_PURCHASE_PROMPT = """\
Расскажи подробно об этой закупке.
Укажи: полное наименование, цену, заказчика ИНН, поставщика (если есть), регион, способ, сроки, статус, ссылку на ЕИС.
Не придумывай данные. Формат для мессенджера.
Ссылка на ЕИС: https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={purchase_number}"""

_FORMAT_SINGLE_CONTRACT_PROMPT = """\
Расскажи подробно об этом контракте.
Укажи: полное наименование, цену, заказчика ИНН, поставщика (если есть), регион, способ, сроки, статус, ссылку на ЕИС.
Не придумывай данные. Формат для мессенджера.
Ссылка на ЕИС: https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber={reg_num}"""

_MAX_PARSE_ATTEMPTS = 3


class GigaChatClient:
    """Клиент для GigaChat API (Сбер) через gigachat SDK.

    Attributes:
        _credentials: Base64-строка client_id:client_secret.
        _scope: Scope API (GIGACHAT_API_PERS или GIGACHAT_API_CORP).
        _parse_model: Название модели для парсинга.
        _answer_model: Название модели для генерации ответов.
    """

    def __init__(
        self,
        credentials: str,
        scope: str = "GIGACHAT_API_PERS",
        parse_model: str = "GigaChat",
        answer_model: str = "GigaChat-Pro",
    ) -> None:
        self._credentials = credentials
        self._scope = scope
        self._parse_model = parse_model
        self._answer_model = answer_model

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    async def parse_user_query(self, text: str) -> SearchParams:
        """Извлечь параметры поиска из текста пользователя с помощью GigaChat.

        Отправляет system prompt + user_text в дешёвую модель,
        получает JSON с полями SearchParams. До 3 попыток при невалидном JSON,
        потом возврат дефолтных параметров.

        Args:
            text: Сообщение пользователя на естественном языке.

        Returns:
            SearchParams с извлечёнными параметрами.
        """
        for attempt in range(1, _MAX_PARSE_ATTEMPTS + 1):
            try:
                raw = await self._chat_completion(
                    model=self._parse_model,
                    system_prompt=_PARSE_SYSTEM_PROMPT,
                    user_message=text,
                    temperature=0.1,
                )
                return self._parse_json_to_search_params(raw)
            except Exception as exc:
                logger.warning(
                    "parse_user_query попытка %d/%d не удалась: %s",
                    attempt, _MAX_PARSE_ATTEMPTS, exc,
                )
        logger.error("Все попытки парсинга исчерпаны, возвращаю дефолтные параметры")
        return SearchParams(query=text, search_type=SearchType.PURCHASES, limit=20)

    async def format_results_list(
        self,
        results: list[Purchase | Contract],
        result_type: str,
    ) -> str:
        """Сформировать краткий список результатов для мессенджера.

        Args:
            results: Список закупок или контрактов.
            result_type: "purchases" или "contracts".

        Returns:
            Отформатированный текст для отправки пользователю.
        """
        if not results:
            return "По вашему запросу ничего не найдено. Попробуйте расширить параметры поиска."

        user_message = self._serialize_results(results, result_type)
        try:
            return await self._chat_completion(
                model=self._answer_model,
                system_prompt=_FORMAT_LIST_SYSTEM_PROMPT,
                user_message=user_message,
                temperature=0.3,
            )
        except Exception as exc:
            logger.warning("GigaChat недоступен для форматирования списка: %s", exc)
            return self._fallback_format_list(results, result_type)

    async def format_single_result(self, item: Purchase | Contract) -> str:
        """Сформировать подробное описание одной закупки/контракта.

        Args:
            item: Purchase или Contract.

        Returns:
            Подробный текст для отправки пользователю.
        """
        if isinstance(item, Purchase):
            system_prompt = _FORMAT_SINGLE_PURCHASE_PROMPT.format(
                purchase_number=item.purchase_number,
            )
        else:
            system_prompt = _FORMAT_SINGLE_CONTRACT_PROMPT.format(
                reg_num=item.reg_num,
            )

        user_message = item.model_dump_json(indent=2)
        try:
            return await self._chat_completion(
                model=self._answer_model,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=0.3,
            )
        except Exception as exc:
            logger.warning("GigaChat недоступен для форматирования детали: %s", exc)
            return self._fallback_format_single(item)

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    async def _chat_completion(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
    ) -> str:
        """Отправить запрос к GigaChat через SDK (синхронный вызов в executor).

        Args:
            model: Название модели (GigaChat / GigaChat-Pro).
            system_prompt: Системный промпт.
            user_message: Сообщение пользователя.
            temperature: Температура генерации.

        Returns:
            Текст ответа модели.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._sync_chat,
            model, system_prompt, user_message, temperature,
        )

    def _sync_chat(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
    ) -> str:
        """Синхронный вызов GigaChat SDK."""
        giga = GigaChat(
            credentials=self._credentials,
            scope=self._scope,
            verify_ssl_certs=False,
            model=model,
        )
        response = giga.chat(Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=system_prompt),
                Messages(role=MessagesRole.USER, content=user_message),
            ],
            temperature=temperature,
        ))
        return response.choices[0].message.content

    def _parse_json_to_search_params(self, raw: str) -> SearchParams:
        """Распарсить текст ответа GigaChat в SearchParams.

        Вырезает ```json...``` блоки, делает json.loads(),
        маппит поля в SearchParams.

        Args:
            raw: Сырой текст от GigaChat.

        Returns:
            SearchParams.

        Raises:
            ValueError: Если JSON невалидный.
        """
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = cleaned.strip().rstrip("`")

        data: dict[str, Any] = json.loads(cleaned)

        search_type_raw = data.get("search_type", "purchases")
        if search_type_raw == "contracts":
            search_type = SearchType.CONTRACTS
        else:
            search_type = SearchType.PURCHASES

        law_raw = data.get("law")
        law: int | None = None
        if law_raw is not None:
            try:
                law = int(law_raw)
            except (ValueError, TypeError):
                pass

        days_raw = data.get("days")
        days = 90
        if days_raw is not None:
            try:
                days = int(days_raw)
            except (ValueError, TypeError):
                pass

        region_raw = data.get("region")
        region: str | None = None
        if region_raw is not None:
            region = str(region_raw)

        limit_raw = data.get("limit", 20)
        try:
            limit = int(limit_raw)
        except (ValueError, TypeError):
            limit = 20

        query = data.get("query") or ""

        synonyms_raw = data.get("synonyms") or []
        synonyms: list[str] = []
        if isinstance(synonyms_raw, list):
            synonyms = [str(s) for s in synonyms_raw if s]

        okpd2 = data.get("okpd2") or None
        okpd2_name = data.get("okpd2_name") or None

        return SearchParams(
            query=query,
            synonyms=synonyms,
            okpd2=okpd2,
            okpd2_name=okpd2_name,
            search_type=search_type,
            law=law,
            days=days,
            region=region,
            limit=limit,
        )

    def _serialize_results(
        self,
        results: list[Purchase | Contract],
        result_type: str,
    ) -> str:
        """Сериализовать список результатов в текст для промпта."""
        label = "закупок" if result_type == "purchases" else "контрактов"
        lines = [f"Найдено {len(results)} {label}:\n"]
        for i, item in enumerate(results, 1):
            lines.append(f"--- Результат {i} ---")
            lines.append(item.model_dump_json(indent=2))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Fallback-форматирование (без GigaChat)
    # ------------------------------------------------------------------

    def _fallback_format_list(
        self,
        results: list[Purchase | Contract],
        result_type: str,
    ) -> str:
        """Простое текстовое форматирование списка без ИИ."""
        lines: list[str] = []
        if result_type == "purchases":
            lines.append(f"Найдено закупок: {len(results)}\n")
            for i, item in enumerate(results, 1):
                p: Purchase = item  # type: ignore[assignment]
                name = (p.object_info or "—")[:80]
                price = f"{p.max_price:,.0f} ₽" if p.max_price else "—"
                date = p.published_at.strftime("%d.%m.%Y") if p.published_at else "—"
                lines.append(f"{i}. {name}\n   Цена: {price} | Дата: {date}")
        else:
            lines.append(f"Найдено контрактов: {len(results)}\n")
            for i, item in enumerate(results, 1):
                c: Contract = item  # type: ignore[assignment]
                name = (c.subject or "—")[:80]
                price = f"{c.price:,.0f} ₽" if c.price else "—"
                date = c.published_at.strftime("%d.%m.%Y") if c.published_at else "—"
                lines.append(f"{i}. {name}\n   Цена: {price} | Дата: {date}")

        lines.append(
            "\nОтправьте номер (1-{}) для подробностей, "
            "или «дальше» для следующей страницы.".format(len(results))
        )
        return "\n".join(lines)

    def _fallback_format_single(self, item: Purchase | Contract) -> str:
        """Простое текстовое форматирование одного результата без ИИ."""
        if isinstance(item, Purchase):
            price = f"{item.max_price:,.0f} ₽" if item.max_price else "—"
            date = item.published_at.strftime("%d.%m.%Y") if item.published_at else "—"
            deadline = (
                item.collecting_finished_at.strftime("%d.%m.%Y")
                if item.collecting_finished_at else "—"
            )
            url = (
                "https://zakupki.gov.ru/epz/order/notice/ea20/view/"
                f"common-info.html?regNumber={item.purchase_number}"
            )
            return (
                f"Закупка {item.purchase_number}\n"
                f"Предмет: {item.object_info or '—'}\n"
                f"НМЦ: {price}\n"
                f"Способ: {item.purchase_type or '—'}\n"
                f"Регион: {item.region or '—'}\n"
                f"Заказчик: {', '.join(item.customers) or '—'}\n"
                f"Опубликовано: {date}\n"
                f"Подача заявок до: {deadline}\n"
                f"ЕИС: {url}"
            )
        else:
            price = f"{item.price:,.0f} ₽" if item.price else "—"
            date = item.published_at.strftime("%d.%m.%Y") if item.published_at else "—"
            exe_start = item.exe_start.strftime("%d.%m.%Y") if item.exe_start else "—"
            exe_end = item.exe_end.strftime("%d.%m.%Y") if item.exe_end else "—"
            url = (
                "https://zakupki.gov.ru/epz/contract/contractCard/"
                f"common-info.html?reestrNumber={item.reg_num}"
            )
            return (
                f"Контракт {item.reg_num}\n"
                f"Предмет: {item.subject or '—'}\n"
                f"Цена: {price}\n"
                f"Заказчик: {item.customer or '—'}\n"
                f"Поставщик: {', '.join(item.suppliers) or '—'}\n"
                f"Регион: {item.region or '—'}\n"
                f"Стадия: {item.stage or '—'}\n"
                f"Исполнение: {exe_start} — {exe_end}\n"
                f"Опубликовано: {date}\n"
                f"ЕИС: {url}"
            )


if __name__ == "__main__":
    import sys

    from config import settings

    async def main() -> None:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        client = GigaChatClient(
            credentials=settings.gigachat_credentials,
            scope=settings.gigachat_scope,
            parse_model=settings.gigachat_parse_model,
            answer_model=settings.gigachat_answer_model,
        )
        text = "покажи свежие закупки на цистерны"
        print(f"Запрос: {text!r}\n")
        params = await client.parse_user_query(text)
        print(f"SearchParams:\n{params.model_dump_json(indent=2)}")

    asyncio.run(main())
