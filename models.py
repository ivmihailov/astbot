"""
Pydantic-модели данных.

Определяет структуры для:
- SearchParams — параметры поиска, извлечённые из запроса пользователя
- Purchase — закупка (извещение) из ГосПлан API
- Contract — контракт из ГосПлан API
- UserState — состояние диалога с пользователем (пагинация, история)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Параметры поиска
# ---------------------------------------------------------------------------

class SearchType(str, Enum):
    """Тип поиска: закупки (purchases) или контракты (contracts)."""
    PURCHASES = "purchases"
    CONTRACTS = "contracts"


class SearchParams(BaseModel):
    """Параметры поиска, которые GigaChat извлекает из текста пользователя.

    Attributes:
        query: Текстовый запрос (ключевые слова, название товара/услуги).
        search_type: Что ищем — закупки или контракты.
        law: Федеральный закон (44 / 223 / None — оба).
        days: За сколько последних дней искать (по умолчанию 30).
        region: Код региона (ОКАТО) или название.
        limit: Максимальное кол-во результатов на страницу.
        active_only: Только активные закупки (подача заявок не просрочена).
    """
    query: str
    synonyms: list[str] = Field(default_factory=list, description="Синонимы и словоформы для расширенного поиска")
    okpd2: Optional[str] = Field(None, description="Код ОКПД2")
    okpd2_name: Optional[str] = Field(None, description="Название категории ОКПД2")
    search_type: SearchType = SearchType.PURCHASES
    law: Optional[int] = Field(None, description="44 или 223")
    days: int = Field(90, ge=1, le=365)
    region: Optional[str] = None
    limit: int = Field(20, ge=1, le=50)
    active_only: bool = Field(False, description="Только активные (подача заявок не просрочена)")


# ---------------------------------------------------------------------------
# Закупка (извещение)
# ---------------------------------------------------------------------------

class Purchase(BaseModel):
    """Закупка (извещение), полученная из ГосПлан API.

    Attributes:
        purchase_number: Реестровый номер закупки.
        object_info: Описание объекта закупки.
        max_price: Начальная (максимальная) цена контракта.
        purchase_type: Способ определения поставщика (аукцион, конкурс и т.д.).
        region: Регион заказчика.
        customers: Список наименований заказчиков.
        published_at: Дата публикации извещения.
        collecting_finished_at: Дата окончания подачи заявок.
    """
    purchase_number: str
    object_info: Optional[str] = None
    max_price: Optional[float] = None
    purchase_type: Optional[str] = None
    region: Optional[str] = None
    customers: list[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    collecting_finished_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Контракт
# ---------------------------------------------------------------------------

class Contract(BaseModel):
    """Контракт, полученный из ГосПлан API.

    Attributes:
        reg_num: Реестровый номер контракта.
        subject: Предмет контракта.
        price: Цена контракта.
        region: Регион.
        customer: Наименование заказчика.
        suppliers: Список поставщиков.
        exe_start: Дата начала исполнения.
        exe_end: Дата окончания исполнения.
        stage: Стадия контракта (исполнение, завершён и т.д.).
        published_at: Дата публикации.
    """
    reg_num: str
    subject: Optional[str] = None
    price: Optional[float] = None
    region: Optional[str] = None
    customer: Optional[str] = None
    suppliers: list[str] = Field(default_factory=list)
    exe_start: Optional[datetime] = None
    exe_end: Optional[datetime] = None
    stage: Optional[str] = None
    published_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Состояние пользователя
# ---------------------------------------------------------------------------

class ResultType(str, Enum):
    """Тип последних результатов в состоянии пользователя."""
    PURCHASES = "purchases"
    CONTRACTS = "contracts"


class UserState(BaseModel):
    """Состояние диалога с конкретным пользователем.

    Хранит последние результаты поиска для пагинации
    и возможности показать детали по номеру.

    Attributes:
        last_results: Список последних найденных объектов (Purchase или Contract).
        last_params: Параметры последнего поиска (для подгрузки следующей страницы).
        current_skip: Текущий offset для пагинации.
        result_type: Тип последних результатов.
    """
    last_results: list[Purchase | Contract] = Field(default_factory=list)
    last_params: Optional[SearchParams] = None
    pending_params: Optional[SearchParams] = None
    current_skip: int = 0
    current_view_index: int = 0
    result_type: Optional[ResultType] = None
