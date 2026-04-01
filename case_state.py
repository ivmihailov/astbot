"""In-memory состояние пользователя для пилотного case bot."""

from __future__ import annotations

from uuid import uuid4

from case_models import (
    CaseRun,
    CaseStepEvent,
    CaseSubmission,
    ConversationScreen,
    SubmissionMedia,
    SearchMatch,
    UserState,
)


class StateManager:
    """Простое in-memory хранилище состояния и заявок."""

    def __init__(self) -> None:
        self._states: dict[int, UserState] = {}

    def get_state(self, chat_id: int) -> UserState:
        if chat_id not in self._states:
            self._states[chat_id] = UserState()
        return self._states[chat_id]

    def reset(self, chat_id: int) -> UserState:
        self._states[chat_id] = UserState()
        return self._states[chat_id]

    def set_screen(self, chat_id: int, screen: ConversationScreen) -> UserState:
        state = self.get_state(chat_id)
        state.screen = screen
        return state

    def save_search(
        self,
        chat_id: int,
        query: str,
        matches: list[SearchMatch],
    ) -> UserState:
        state = self.get_state(chat_id)
        state.last_query = query
        state.last_matches = matches
        state.selected_case_id = None
        state.screen = (
            ConversationScreen.VIEWING_SEARCH_RESULTS
            if matches
            else ConversationScreen.AWAITING_SEARCH_QUERY
        )
        return state

    def select_case(self, chat_id: int, case_id: str) -> UserState:
        state = self.get_state(chat_id)
        state.selected_case_id = case_id
        state.screen = ConversationScreen.VIEWING_CASE
        return state

    def start_run(self, chat_id: int, case_id: str) -> CaseRun:
        state = self.get_state(chat_id)
        state.active_run = CaseRun(
            id=uuid4().hex,
            user_id=str(chat_id),
            case_id=case_id,
        )
        state.run_events = []
        state.awaiting_run_media_step_id = None
        state.screen = ConversationScreen.IN_RUN
        return state.active_run

    def append_run_event(self, chat_id: int, event: CaseStepEvent) -> None:
        self.get_state(chat_id).run_events.append(event)

    def begin_submission(self, chat_id: int) -> CaseSubmission:
        state = self.get_state(chat_id)
        state.draft_submission = CaseSubmission(
            id=uuid4().hex,
            created_by=str(chat_id),
        )
        state.awaiting_run_media_step_id = None
        state.screen = ConversationScreen.AWAITING_SUBMISSION_TITLE
        return state.draft_submission

    def save_submission(self, chat_id: int) -> CaseSubmission | None:
        state = self.get_state(chat_id)
        if state.draft_submission is None:
            return None

        submission = state.draft_submission
        state.draft_submission = None
        state.awaiting_run_media_step_id = None
        state.screen = ConversationScreen.MAIN_MENU
        return submission

    def attach_submission_media(
        self,
        chat_id: int,
        media_items: list[SubmissionMedia],
    ) -> CaseSubmission | None:
        state = self.get_state(chat_id)
        if state.draft_submission is None:
            return None

        state.draft_submission.media.extend(media_items)
        return state.draft_submission

    def enable_run_media_mode(self, chat_id: int, step_id: str) -> None:
        state = self.get_state(chat_id)
        state.awaiting_run_media_step_id = step_id

    def clear_run_media_mode(self, chat_id: int) -> None:
        self.get_state(chat_id).awaiting_run_media_step_id = None
