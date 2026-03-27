"""Обработчики MVP-сценариев case bot."""

from __future__ import annotations

from uuid import uuid4

from case_formatters import (
    format_case_card,
    format_case_step,
    format_help,
    format_matches,
    format_popular_cases,
    format_run_summary,
    format_step_hint,
    format_submission_intro,
    format_submission_next,
    format_submission_saved,
    format_welcome,
)
from case_models import (
    CaseStepEvent,
    ConversationScreen,
    EventAction,
    RunStatus,
    SearchMatch,
    utcnow,
)
from case_repository import SQLiteCaseRepository
from case_search import CaseSearchService
from case_state import StateManager


class Handlers:
    """Бизнес-логика пилотного bot skeleton."""

    def __init__(
        self,
        repository: SQLiteCaseRepository,
        search_service: CaseSearchService,
        state: StateManager,
    ) -> None:
        self.repository = repository
        self.search_service = search_service
        self.state = state

    async def handle_start(self, chat_id: int) -> str:
        self.state.reset(chat_id)
        return format_welcome()

    async def handle_help(self, chat_id: int) -> str:
        self.state.set_screen(chat_id, ConversationScreen.MAIN_MENU)
        return format_help()

    async def handle_menu_action(self, chat_id: int, action: str) -> str:
        if action == "find_case":
            self.state.set_screen(chat_id, ConversationScreen.AWAITING_SEARCH_QUERY)
            return "Опишите ситуацию свободным текстом. Например: «траншея заливается водой, что делать?»"

        if action == "new_case":
            self.state.begin_submission(chat_id)
            return format_submission_intro()

        if action == "recent":
            self.state.set_screen(chat_id, ConversationScreen.MAIN_MENU)
            return "Раздел «Мои последние кейсы» подключим следующим шагом вместе с постоянным хранением истории."

        if action == "popular":
            popular_cases = self.repository.list_popular_cases(limit=5)
            matches = [
                SearchMatch(case=case, score=max(1, 100 - index))
                for index, case in enumerate(popular_cases)
            ]
            self.state.save_search(chat_id, "popular", matches)
            return format_popular_cases(popular_cases)

        if action == "help":
            return await self.handle_help(chat_id)

        self.state.set_screen(chat_id, ConversationScreen.MAIN_MENU)
        return format_welcome()

    async def handle_text(self, chat_id: int, text: str) -> str:
        clean_text = text.strip()
        if not clean_text:
            return "Нужен текст запроса или ответа."

        lower_text = clean_text.lower()
        aliases = {
            "найти кейс": "find_case",
            "создать новый кейс": "new_case",
            "помощь": "help",
            "меню": "menu",
        }
        if lower_text in aliases:
            return await self.handle_menu_action(chat_id, aliases[lower_text])

        state = self.state.get_state(chat_id)

        if state.screen == ConversationScreen.AWAITING_SEARCH_QUERY:
            matches = self.search_service.find_relevant_cases(clean_text, limit=3)
            self.state.save_search(chat_id, clean_text, matches)
            return format_matches(clean_text, matches)

        if state.screen in {
            ConversationScreen.AWAITING_SUBMISSION_TITLE,
            ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION,
            ConversationScreen.AWAITING_SUBMISSION_ACTIONS,
            ConversationScreen.AWAITING_SUBMISSION_RESULT,
            ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS,
        }:
            return self._handle_submission_text(chat_id, clean_text)

        if state.screen == ConversationScreen.IN_RUN:
            return "Для прохождения кейса используйте кнопки под текущим шагом."

        return format_welcome()

    async def handle_case_selected(self, chat_id: int, case_id: str) -> str:
        case = self.repository.get_case(case_id)
        if case is None:
            return "Кейс не найден. Попробуйте выполнить поиск заново."

        self.state.select_case(chat_id, case_id)
        return format_case_card(case)

    async def handle_run_started(self, chat_id: int, case_id: str) -> str:
        case = self.repository.get_case(case_id)
        if case is None:
            return "Не удалось открыть кейс для прохождения."

        run = self.state.start_run(chat_id, case_id)
        first_step = case.steps[0]
        return format_case_step(case, first_step, run)

    async def handle_run_action(self, chat_id: int, action: str) -> str:
        state = self.state.get_state(chat_id)
        run = state.active_run
        if run is None:
            return "Нет активного прохождения кейса."

        case = self.repository.get_case(run.case_id)
        if case is None:
            return "Не удалось загрузить кейс для текущего прохождения."

        current_index = max(run.current_step - 1, 0)
        current_step = case.steps[current_index]

        if action == "hint":
            self.state.append_run_event(
                chat_id,
                CaseStepEvent(
                    id=uuid4().hex,
                    run_id=run.id,
                    step_id=current_step.id,
                    action=EventAction.HINT_REQUESTED,
                ),
            )
            return format_step_hint(current_step)

        if action == "comment":
            self.state.append_run_event(
                chat_id,
                CaseStepEvent(
                    id=uuid4().hex,
                    run_id=run.id,
                    step_id=current_step.id,
                    action=EventAction.COMMENT_REQUESTED,
                ),
            )
            return "Прием комментариев добавим следующим шагом. Сейчас фиксирую точку расширения в каркасе."

        if action == "photo":
            self.state.append_run_event(
                chat_id,
                CaseStepEvent(
                    id=uuid4().hex,
                    run_id=run.id,
                    step_id=current_step.id,
                    action=EventAction.PHOTO_REQUESTED,
                ),
            )
            return "Прием фото будет следующим вертикальным срезом после SQLite и файлового хранилища."

        if action == "back":
            if run.current_step <= 1:
                return "Это первый шаг, назад идти уже некуда."

            run.current_step -= 1
            previous_step = case.steps[run.current_step - 1]
            self.state.append_run_event(
                chat_id,
                CaseStepEvent(
                    id=uuid4().hex,
                    run_id=run.id,
                    step_id=previous_step.id,
                    action=EventAction.STEP_BACK,
                ),
            )
            return format_case_step(case, previous_step, run)

        if action not in {"done", "not_done"}:
            return "Неизвестное действие шага."

        event_action = (
            EventAction.STEP_DONE if action == "done" else EventAction.STEP_BLOCKED
        )
        self.state.append_run_event(
            chat_id,
            CaseStepEvent(
                id=uuid4().hex,
                run_id=run.id,
                step_id=current_step.id,
                action=event_action,
            ),
        )

        if current_index == len(case.steps) - 1:
            run.status = RunStatus.FINISHED
            run.finished_at = utcnow()
            run.summary_json = {
                "done_steps": sum(
                    event.action == EventAction.STEP_DONE
                    for event in state.run_events
                ),
                "blocked_steps": sum(
                    event.action == EventAction.STEP_BLOCKED
                    for event in state.run_events
                ),
            }
            state.screen = ConversationScreen.MAIN_MENU
            return format_run_summary(case, run, state.run_events)

        run.current_step += 1
        next_step = case.steps[run.current_step - 1]
        return format_case_step(case, next_step, run)

    def _handle_submission_text(self, chat_id: int, text: str) -> str:
        state = self.state.get_state(chat_id)
        submission = state.draft_submission
        if submission is None:
            submission = self.state.begin_submission(chat_id)

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_TITLE:
            submission.title = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION
            return format_submission_next(2, "Опишите проблему или ситуацию на объекте.")

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION:
            submission.problem_description = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_ACTIONS
            return format_submission_next(3, "Напишите, что уже сделали по этой ситуации.")

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_ACTIONS:
            submission.actions_taken = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_RESULT
            return format_submission_next(4, "Какой получился результат?")

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_RESULT:
            submission.result = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS
            return format_submission_next(5, "Какие рекомендации вы бы оставили для такого кейса?")

        submission.recommendations = text
        saved_submission = self.state.save_submission(chat_id)
        if saved_submission is None:
            return "Не удалось сохранить новый кейс. Попробуйте начать заново."
        return format_submission_saved(saved_submission)
