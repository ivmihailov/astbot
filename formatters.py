"""
Форматирование результатов для мессенджера MAX.

Fallback-форматирование (если GigaChat недоступен).
Преобразует объекты Purchase и Contract в текстовые сообщения
с учётом ограничений мессенджера.
"""

from __future__ import annotations

from models import Contract, Purchase, ResultType, SearchParams


# ---------------------------------------------------------------------------
# Краткие строки (одна позиция в списке)
# ---------------------------------------------------------------------------

def format_purchase_short(purchase: Purchase, index: int) -> str:
    """Краткая строка закупки для списка: №, предмет, цена, дата.

    Args:
        purchase: Объект закупки.
        index: Порядковый номер (1-based).

    Returns:
        Однострочное описание закупки.
    """
    name = (purchase.object_info or "—")[:80]
    price = f"{purchase.max_price:,.0f} \u20bd" if purchase.max_price else "—"
    date = purchase.published_at.strftime("%d.%m.%Y") if purchase.published_at else "—"
    return f"{index}. {name}\n   Цена: {price} | Дата: {date}"


def format_contract_short(contract: Contract, index: int) -> str:
    """Краткая строка контракта для списка: №, предмет, цена, дата.

    Args:
        contract: Объект контракта.
        index: Порядковый номер (1-based).

    Returns:
        Однострочное описание контракта.
    """
    name = (contract.subject or "—")[:80]
    price = f"{contract.price:,.0f} \u20bd" if contract.price else "—"
    date = contract.published_at.strftime("%d.%m.%Y") if contract.published_at else "—"
    return f"{index}. {name}\n   Цена: {price} | Дата: {date}"


# ---------------------------------------------------------------------------
# Детальное описание (один объект)
# ---------------------------------------------------------------------------

def format_purchase_detail(purchase: Purchase) -> str:
    """Подробное описание закупки со ссылкой на ЕИС.

    Args:
        purchase: Объект закупки.

    Returns:
        Многострочное подробное описание.
    """
    price = f"{purchase.max_price:,.0f} \u20bd" if purchase.max_price else "—"
    date = purchase.published_at.strftime("%d.%m.%Y") if purchase.published_at else "—"
    deadline = (
        purchase.collecting_finished_at.strftime("%d.%m.%Y")
        if purchase.collecting_finished_at else "—"
    )
    url = (
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/"
        f"common-info.html?regNumber={purchase.purchase_number}"
    )
    return (
        f"Закупка {purchase.purchase_number}\n"
        f"Предмет: {purchase.object_info or '—'}\n"
        f"НМЦ: {price}\n"
        f"Способ: {purchase.purchase_type or '—'}\n"
        f"Регион: {purchase.region or '—'}\n"
        f"Заказчик: {', '.join(purchase.customers) or '—'}\n"
        f"Опубликовано: {date}\n"
        f"Подача заявок до: {deadline}\n"
        f"ЕИС: {url}"
    )


def format_contract_detail(contract: Contract) -> str:
    """Подробное описание контракта со ссылкой на ЕИС.

    Args:
        contract: Объект контракта.

    Returns:
        Многострочное подробное описание.
    """
    price = f"{contract.price:,.0f} \u20bd" if contract.price else "—"
    date = contract.published_at.strftime("%d.%m.%Y") if contract.published_at else "—"
    exe_start = contract.exe_start.strftime("%d.%m.%Y") if contract.exe_start else "—"
    exe_end = contract.exe_end.strftime("%d.%m.%Y") if contract.exe_end else "—"
    url = (
        "https://zakupki.gov.ru/epz/contract/contractCard/"
        f"common-info.html?reestrNumber={contract.reg_num}"
    )
    return (
        f"Контракт {contract.reg_num}\n"
        f"Предмет: {contract.subject or '—'}\n"
        f"Цена: {price}\n"
        f"Заказчик: {contract.customer or '—'}\n"
        f"Поставщик: {', '.join(contract.suppliers) or '—'}\n"
        f"Регион: {contract.region or '—'}\n"
        f"Стадия: {contract.stage or '—'}\n"
        f"Исполнение: {exe_start} — {exe_end}\n"
        f"Опубликовано: {date}\n"
        f"ЕИС: {url}"
    )


# ---------------------------------------------------------------------------
# Карточка (один результат с номером)
# ---------------------------------------------------------------------------


def format_card(
    item: Purchase | Contract,
    index: int,
    total: int,
    result_type: ResultType,
) -> str:
    """Одна карточка результата с номером и счётчиком.

    Args:
        item: Закупка или контракт.
        index: Текущий номер (0-based).
        total: Общее количество загруженных результатов.
        result_type: Тип результата.

    Returns:
        Текст карточки вида «[3/20] Закупка ...»
    """
    label = "закупка" if result_type == ResultType.PURCHASES else "контракт"
    header = f"[{index + 1}/{total}] Результат — {label}\n\n"

    if result_type == ResultType.PURCHASES:
        body = format_purchase_detail(item)  # type: ignore[arg-type]
    else:
        body = format_contract_detail(item)  # type: ignore[arg-type]

    return header + body


# ---------------------------------------------------------------------------
# Краткий список результатов + инструкция
# ---------------------------------------------------------------------------

def format_results_list(
    items: list[Purchase | Contract], result_type: ResultType
) -> str:
    """Сформировать текстовый список результатов с инструкцией.

    Args:
        items: Список закупок или контрактов.
        result_type: Тип результатов.

    Returns:
        Отформатированный текст со списком и подсказкой по навигации.
    """
    if not items:
        return "По вашему запросу ничего не найдено."

    lines: list[str] = []
    if result_type == ResultType.PURCHASES:
        lines.append(f"Найдено закупок: {len(items)}\n")
        for i, item in enumerate(items, 1):
            lines.append(format_purchase_short(item, i))  # type: ignore[arg-type]
    else:
        lines.append(f"Найдено контрактов: {len(items)}\n")
        for i, item in enumerate(items, 1):
            lines.append(format_contract_short(item, i))  # type: ignore[arg-type]

    lines.append(
        f"\nОтправьте номер (1-{len(items)}) для подробностей, "
        "или «дальше» для следующей страницы."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Панель фильтров (перед поиском)
# ---------------------------------------------------------------------------


_DAYS_LABELS: dict[int, str] = {7: "за неделю", 30: "за месяц", 90: "за 3 месяца", 365: "за год"}


def format_filter_panel(params: SearchParams) -> str:
    """Сформировать текст панели фильтров для отображения перед поиском.

    Args:
        params: Текущие параметры поиска (pending).

    Returns:
        Многострочный текст с текущими настройками фильтров.
    """
    search_label = "закупки" if params.search_type.value == "purchases" else "контракты"
    law_label = f"{params.law}-ФЗ" if params.law else "все"
    period_label = _DAYS_LABELS.get(params.days, f"за {params.days} дн.")
    region_label = f"регион: {params.region}" if params.region else ""

    okpd2_label = f"ОКПД2: {params.okpd2} — {params.okpd2_name}" if params.okpd2 else ""

    lines = [
        f"Запрос: {params.query}",
    ]
    if okpd2_label:
        lines.append(okpd2_label)
    lines += [
        f"Тип: {search_label}" + (f" | {region_label}" if region_label else ""),
        "",
        f"Период: {period_label}",
        f"Закон: {law_label}",
    ]

    if params.search_type.value == "purchases":
        active_label = "только активные" if params.active_only else "все"
        lines.append(f"Фильтр: {active_label}")

    lines.append("")
    lines.append("Настройте фильтры и нажмите «Искать»:")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Вспомогательные форматтеры
# ---------------------------------------------------------------------------

def format_search_params(params: SearchParams) -> str:
    """Форматировать параметры поиска для отображения пользователю.

    Показывает, как бот интерпретировал запрос.

    Args:
        params: Распознанные параметры поиска.

    Returns:
        Строка вида «Ищу: ... | Закон: 44-ФЗ | ...»
    """
    parts = [f"Ищу: {params.query}"]
    if params.okpd2:
        parts.append(f"ОКПД2 {params.okpd2}")
    search_label = "закупки" if params.search_type.value == "purchases" else "контракты"
    parts.append(search_label)
    if params.law:
        parts.append(f"{params.law}-ФЗ")
    if params.region:
        parts.append(f"регион: {params.region}")
    parts.append(f"за {params.days} дн.")
    return " | ".join(parts)


def format_no_results(params: SearchParams) -> str:
    """Сообщение, если ничего не найдено.

    Args:
        params: Параметры поиска, по которым ничего не нашлось.

    Returns:
        Текст с рекомендациями уточнить запрос.
    """
    return (
        f"По запросу «{params.query}» ничего не найдено.\n\n"
        "Попробуйте:\n"
        "- Упростить запрос (меньше слов)\n"
        "- Увеличить период поиска\n"
        "- Убрать фильтр по региону"
    )


def format_error(error_message: str) -> str:
    """Форматировать сообщение об ошибке для пользователя.

    Args:
        error_message: Техническое описание ошибки.

    Returns:
        Пользователь-дружественное сообщение об ошибке.
    """
    return f"Произошла ошибка: {error_message}\nПопробуйте повторить запрос позже."
