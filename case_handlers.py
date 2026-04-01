"""Обработчики MVP-сценариев case bot."""

from __future__ import annotations

import re
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
    format_submission_media_added,
    format_submission_media_prompt,
    format_submission_next,
    format_submission_saved,
    format_welcome,
)
from case_models import (
    CaseStepEvent,
    ConversationScreen,
    EventAction,
    IncomingMedia,
    RunStatus,
    SearchMatch,
    SubmissionMedia,
    SubmissionMediaType,
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

    @staticmethod
    def _parse_step_numbers(text: str | None) -> list[int]:
        if not text:
            return []

        normalized = text.lower()
        if "все" in normalized:
            return [1, 2, 3, 4]

        numbers = [int(number) for number in re.findall(r"\b([1-4])\b", normalized)]
        return sorted(set(numbers))

    @staticmethod
    def _submission_step_numbers_for_screen(screen: ConversationScreen) -> list[int]:
        mapping = {
            ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION: [1],
            ConversationScreen.AWAITING_SUBMISSION_ACTIONS: [2],
            ConversationScreen.AWAITING_SUBMISSION_RESULT: [3],
            ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS: [4],
        }
        return mapping.get(screen, [])

    async def handle_start(self, chat_id: int) -> str:
        self.state.reset(chat_id)
        return format_welcome()

    async def handle_help(self, chat_id: int) -> str:
        self.state.set_screen(chat_id, ConversationScreen.MAIN_MENU)
        return format_help()

    async def handle_menu_action(self, chat_id: int, action: str) -> str:
        if action == "menu":
            self.state.reset(chat_id)
            return format_welcome()

        if action == "find_case":
            self.state.set_screen(chat_id, ConversationScreen.AWAITING_SEARCH_QUERY)
            return "Опишите ситуацию свободным текстом. Например: «траншея заливается водой, что делать?»"

        if action == "new_case":
            self.state.begin_submission(chat_id)
            return format_submission_intro()

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

    async def handle_submission_action(self, chat_id: int, action: str) -> str:
        state = self.state.get_state(chat_id)
        submission = state.draft_submission
        if submission is None:
            return "Нет активной заявки на новый кейс."

        if action == "save":
            return self._finalize_submission(chat_id)

        if action == "skip_media":
            return self._finalize_submission(chat_id)

        return "Неизвестное действие для заявки."

    async def handle_message(
        self,
        chat_id: int,
        text: str | None,
        media_items: list[IncomingMedia],
    ) -> str:
        clean_text = (text or "").strip()
        lower_text = clean_text.lower()

        aliases = {
            "найти кейс": "find_case",
            "создать новый кейс": "new_case",
            "помощь": "help",
            "меню": "menu",
        }
        if clean_text and lower_text in aliases:
            return await self.handle_menu_action(chat_id, aliases[lower_text])

        state = self.state.get_state(chat_id)

        if state.active_run is not None and media_items and state.awaiting_run_media_step_id:
            return self._handle_run_media(chat_id, media_items)

        if state.draft_submission is not None and media_items:
            return self._handle_submission_media(chat_id, clean_text or None, media_items)

        if not clean_text:
            if media_items:
                return "Медиа сейчас принимаются только в сценарии «Создать новый кейс»."
            return "Нужен текст запроса или ответа."

        if lower_text in {"сохранить", "сохранить кейс", "готово", "готов"}:
            if state.screen == ConversationScreen.AWAITING_SUBMISSION_MEDIA:
                return self._finalize_submission(chat_id)

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
            ConversationScreen.AWAITING_SUBMISSION_MEDIA,
        }:
            return self._handle_submission_text(chat_id, clean_text)

        if state.screen == ConversationScreen.IN_RUN:
            if lower_text in {"готово", "медиа готово"}:
                self.state.clear_run_media_mode(chat_id)
                return "Загрузку медиа для шага завершил. Можно продолжать выполнение кейса кнопками."
            return "Для прохождения кейса используйте кнопки под текущим шагом."

        return format_welcome()

    async def handle_text(self, chat_id: int, text: str) -> str:
        return await self.handle_message(chat_id, text, [])

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
        self.repository.create_run(run)
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

        if action != "photo":
            self.state.clear_run_media_mode(chat_id)

        if action == "hint":
            event = CaseStepEvent(
                id=uuid4().hex,
                run_id=run.id,
                step_id=current_step.id,
                action=EventAction.HINT_REQUESTED,
            )
            self.state.append_run_event(chat_id, event)
            self.repository.add_run_event(event)
            return format_step_hint(current_step)

        if action == "comment":
            return "Кнопка комментариев убрана из интерфейса. Если нужно, напишите комментарий отдельным сообщением и затем вернитесь в меню."

        if action == "photo":
            event = CaseStepEvent(
                id=uuid4().hex,
                run_id=run.id,
                step_id=current_step.id,
                action=EventAction.PHOTO_REQUESTED,
            )
            self.state.append_run_event(chat_id, event)
            self.repository.add_run_event(event)
            self.state.enable_run_media_mode(chat_id, current_step.id)
            return (
                "Пришлите фото или видео для текущего шага.\n\n"
                "Можно отправить несколько файлов одним сообщением.\n\n"
                "Когда закончите, продолжайте выполнение кейса кнопками."
            )

        if action == "back":
            if run.current_step <= 1:
                return "Это первый шаг, назад идти уже некуда."

            run.current_step -= 1
            previous_step = case.steps[run.current_step - 1]
            event = CaseStepEvent(
                id=uuid4().hex,
                run_id=run.id,
                step_id=previous_step.id,
                action=EventAction.STEP_BACK,
            )
            self.state.append_run_event(chat_id, event)
            self.repository.add_run_event(event)
            self.repository.update_run(run)
            return format_case_step(case, previous_step, run)

        if action not in {"done", "not_done"}:
            return "Неизвестное действие шага."

        event_action = (
            EventAction.STEP_DONE if action == "done" else EventAction.STEP_BLOCKED
        )
        event = CaseStepEvent(
            id=uuid4().hex,
            run_id=run.id,
            step_id=current_step.id,
            action=event_action,
        )
        self.state.append_run_event(chat_id, event)
        self.repository.add_run_event(event)

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
            self.state.clear_run_media_mode(chat_id)
            self.repository.update_run(run)
            return format_run_summary(case, run, state.run_events)

        run.current_step += 1
        self.repository.update_run(run)
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
            return format_submission_next(
                2,
                "Что произошло?\n\n"
                "Опишите проблему простыми словами: где это случилось, что мешает работе, что вы увидели по факту.",
            )

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION:
            submission.problem_description = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_ACTIONS
            return format_submission_next(
                3,
                "Что вы сделали по факту?\n\n"
                "Перечислите реальные действия в свободной форме. Лучше писать в прошедшем времени.",
            )

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_ACTIONS:
            submission.actions_taken = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_RESULT
            return format_submission_next(
                4,
                "Какой получился результат?\n\n"
                "Напишите, что изменилось после ваших действий, что получилось и что не получилось.",
            )

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_RESULT:
            submission.result = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS
            return format_submission_next(
                5,
                "Какие рекомендации оставить следующему исполнителю?\n\n"
                "Это может быть совет, ограничение, типовая ошибка или важная проверка перед началом работ.",
            )

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS:
            submission.recommendations = text
            state.screen = ConversationScreen.AWAITING_SUBMISSION_MEDIA
            return format_submission_media_prompt(submission)

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_MEDIA:
            return (
                "На этом шаге жду фото или видео. "
                "Если медиа больше не будет, нажмите «Сохранить кейс»."
            )

        return "Не удалось обработать шаг создания нового кейса."

    def _handle_submission_media(
        self,
        chat_id: int,
        text: str | None,
        media_items: list[IncomingMedia],
    ) -> str:
        state = self.state.get_state(chat_id)
        submission = state.draft_submission
        if submission is None:
            return "Сначала откройте сценарий «Создать новый кейс»."

        if state.screen == ConversationScreen.AWAITING_SUBMISSION_MEDIA:
            linked_step_nos = self._parse_step_numbers(text)
        else:
            linked_step_nos = self._submission_step_numbers_for_screen(state.screen)

        normalized_media = [
            SubmissionMedia(
                id=uuid4().hex,
                media_type=media.media_type,
                source_url=media.source_url,
                token=media.token,
                preview_url=media.preview_url,
                linked_step_nos=linked_step_nos or media.linked_step_nos,
                original_payload=media.original_payload,
            )
            for media in media_items
        ]
        self.state.attach_submission_media(chat_id, normalized_media)

        if state.screen != ConversationScreen.AWAITING_SUBMISSION_MEDIA:
            prompt = self._submission_prompt_for_screen(state.screen)
            return (
                f"Медиа сохранил: {len(normalized_media)}.\n\n"
                f"{prompt}"
            )

        return format_submission_media_added(submission, len(normalized_media))

    def _handle_run_media(
        self,
        chat_id: int,
        media_items: list[IncomingMedia],
    ) -> str:
        state = self.state.get_state(chat_id)
        run = state.active_run
        step_id = state.awaiting_run_media_step_id
        if run is None or step_id is None:
            return "Сейчас нет активного шага для загрузки медиа."

        normalized_media = [
            SubmissionMedia(
                id=uuid4().hex,
                media_type=media.media_type,
                source_url=media.source_url,
                token=media.token,
                preview_url=media.preview_url,
                original_payload=media.original_payload,
            )
            for media in media_items
        ]
        persisted_media = self.repository.persist_run_media(
            run.id,
            step_id,
            normalized_media,
        )
        event = CaseStepEvent(
            id=uuid4().hex,
            run_id=run.id,
            step_id=step_id,
            action=EventAction.MEDIA_ADDED,
            photo_ids=[media.storage_path or media.id for media in persisted_media],
        )
        self.state.append_run_event(chat_id, event)
        self.repository.add_run_event(event)
        self.state.clear_run_media_mode(chat_id)

        photo_count = sum(media.media_type == SubmissionMediaType.PHOTO for media in persisted_media)
        video_count = sum(media.media_type == SubmissionMediaType.VIDEO for media in persisted_media)
        return (
            "Медиа для шага сохранены.\n\n"
            f"Фото: {photo_count}\n"
            f"Видео: {video_count}\n\n"
            "Можно продолжать выполнение кейса или снова нажать «Добавить фото/видео»."
        )

    def _submission_prompt_for_screen(self, screen: ConversationScreen) -> str:
        prompts = {
            ConversationScreen.AWAITING_SUBMISSION_TITLE: (
                "Шаг 1/6.\n\n"
                "Пришлите короткое название ситуации.\n\n"
                "Например: «Траншею затопило после дождя»."
            ),
            ConversationScreen.AWAITING_SUBMISSION_DESCRIPTION: (
                "Шаг 2/6.\n\n"
                "Что произошло?\n\n"
                "Опишите проблему простыми словами: где это случилось, что мешает работе, что вы увидели по факту."
            ),
            ConversationScreen.AWAITING_SUBMISSION_ACTIONS: (
                "Шаг 3/6.\n\n"
                "Что вы сделали по факту?\n\n"
                "Перечислите реальные действия в свободной форме. Лучше писать в прошедшем времени."
            ),
            ConversationScreen.AWAITING_SUBMISSION_RESULT: (
                "Шаг 4/6.\n\n"
                "Какой получился результат?\n\n"
                "Напишите, что изменилось после ваших действий, что получилось и что не получилось."
            ),
            ConversationScreen.AWAITING_SUBMISSION_RECOMMENDATIONS: (
                "Шаг 5/6.\n\n"
                "Какие рекомендации оставить следующему исполнителю?\n\n"
                "Это может быть совет, ограничение, типовая ошибка или важная проверка перед началом работ."
            ),
            ConversationScreen.AWAITING_SUBMISSION_MEDIA: "Шаг 6/6. Можно прислать фото или видео, затем сохранить кейс.",
        }
        return prompts.get(screen, "Продолжите заполнение кейса.")

    def _finalize_submission(self, chat_id: int) -> str:
        draft_submission = self.state.save_submission(chat_id)
        if draft_submission is None:
            return "Не удалось сохранить новый кейс. Попробуйте начать заново."

        saved_submission = self.repository.save_submission(draft_submission)
        return format_submission_saved(saved_submission)
