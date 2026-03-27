"""
Менеджер состояния пользователей (in-memory).

Хранит для каждого chat_id:
- последние результаты поиска (для «покажи подробнее №3»)
- параметры последнего запроса (для пагинации «ещё»)
- текущий offset пагинации
"""

from __future__ import annotations

from models import Contract, Purchase, ResultType, SearchParams, UserState


class StateManager:
    """In-memory хранилище состояний пользователей.

    Ключ — chat_id (int), значение — UserState.
    При перезапуске бота состояние теряется (это нормально для MVP).
    """

    def __init__(self) -> None:
        self._states: dict[int, UserState] = {}

    def get_state(self, chat_id: int) -> UserState:
        """Получить текущее состояние пользователя.

        Если пользователь новый — создаёт пустое состояние.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            UserState с текущими данными.
        """
        if chat_id not in self._states:
            self._states[chat_id] = UserState()
        return self._states[chat_id]

    def save_results(
        self,
        chat_id: int,
        results: list[Purchase | Contract],
        params: SearchParams,
        result_type: ResultType,
    ) -> None:
        """Сохранить результаты поиска для пользователя.

        Перезаписывает предыдущие результаты и сбрасывает skip.

        Args:
            chat_id: Идентификатор чата.
            results: Список найденных закупок или контрактов.
            params: Параметры поиска (для повторного запроса / пагинации).
            result_type: Тип результатов (purchases / contracts).
        """
        state = self.get_state(chat_id)
        state.last_results = results
        state.last_params = params
        state.result_type = result_type
        state.current_skip = 0
        state.current_view_index = 0

    def get_result_by_index(
        self, chat_id: int, index: int
    ) -> Purchase | Contract | None:
        """Получить конкретный результат по порядковому номеру (1-based).

        Args:
            chat_id: Идентификатор чата.
            index: Номер результата (начиная с 1).

        Returns:
            Purchase или Contract, либо None если индекс вне диапазона.
        """
        state = self.get_state(chat_id)
        if index < 1 or index > len(state.last_results):
            return None
        return state.last_results[index - 1]

    def next_page(self, chat_id: int) -> int:
        """Увеличить offset пагинации и вернуть новое значение skip.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            Новое значение skip для следующего запроса к API.
        """
        state = self.get_state(chat_id)
        limit = state.last_params.limit if state.last_params else 5
        state.current_skip += limit
        return state.current_skip

    def save_pending(self, chat_id: int, params: SearchParams) -> None:
        """Сохранить параметры поиска до подтверждения пользователем.

        Args:
            chat_id: Идентификатор чата.
            params: Распарсенные параметры поиска.
        """
        state = self.get_state(chat_id)
        state.pending_params = params

    def get_pending(self, chat_id: int) -> SearchParams | None:
        """Получить ожидающие подтверждения параметры поиска.

        Args:
            chat_id: Идентификатор чата.

        Returns:
            SearchParams или None, если нет ожидающего запроса.
        """
        return self.get_state(chat_id).pending_params

    def clear(self, chat_id: int) -> None:
        """Очистить состояние пользователя.

        Args:
            chat_id: Идентификатор чата.
        """
        if chat_id in self._states:
            del self._states[chat_id]
