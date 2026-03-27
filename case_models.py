"""Доменные модели пилота по кейсам в электроэнергетике."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Вернуть timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class CaseType(str, Enum):
    """Тип производственного кейса."""

    PROBLEM = "problem"
    OPPORTUNITY = "opportunity"


class CaseStatus(str, Enum):
    """Статус актуальности кейса."""

    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"


class ConfirmationType(str, Enum):
    """Способ подтверждения шага."""

    BUTTON = "button"
    TEXT = "text"
    PHOTO = "photo"


class RunStatus(str, Enum):
    """Статус прохождения кейса."""

    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class EventAction(str, Enum):
    """Событие внутри прохождения кейса."""

    STEP_DONE = "step_done"
    STEP_BLOCKED = "step_blocked"
    HINT_REQUESTED = "hint_requested"
    COMMENT_REQUESTED = "comment_requested"
    PHOTO_REQUESTED = "photo_requested"
    STEP_BACK = "step_back"


class SubmissionStatus(str, Enum):
    """Статус пользовательской заявки на новый кейс."""

    NEW = "new"
    APPROVED = "approved"
    REJECTED = "rejected"


class ConversationScreen(str, Enum):
    """Экран/режим текущего пользователя."""

    MAIN_MENU = "main_menu"
    AWAITING_SEARCH_QUERY = "awaiting_search_query"
    VIEWING_SEARCH_RESULTS = "viewing_search_results"
    VIEWING_CASE = "viewing_case"
    IN_RUN = "in_run"
    AWAITING_SUBMISSION_TITLE = "awaiting_submission_title"
    AWAITING_SUBMISSION_DESCRIPTION = "awaiting_submission_description"
    AWAITING_SUBMISSION_ACTIONS = "awaiting_submission_actions"
    AWAITING_SUBMISSION_RESULT = "awaiting_submission_result"
    AWAITING_SUBMISSION_RECOMMENDATIONS = "awaiting_submission_recommendations"


class CaseStep(BaseModel):
    """Структура одного шага кейса."""

    id: str
    case_id: str
    step_no: int
    action_text: str
    why_text: str | None = None
    required: bool = True
    confirmation_type: ConfirmationType = ConfirmationType.BUTTON
    help_text: str | None = None
    next_rule: str | None = None


class Case(BaseModel):
    """Карточка производственного кейса."""

    id: str
    title: str
    type: CaseType
    area: str
    description: str
    consequences: str
    preconditions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    status: CaseStatus = CaseStatus.ACTIVE
    version: str = "1.0"
    author: str = "pilot-team"
    updated_at: datetime = Field(default_factory=utcnow)
    estimated_time: str = "10-15 минут"
    is_popular: bool = False
    search_phrases: list[str] = Field(default_factory=list)
    steps: list[CaseStep] = Field(default_factory=list)


class CaseRun(BaseModel):
    """История прохождения кейса пользователем."""

    id: str
    user_id: str
    case_id: str
    status: RunStatus = RunStatus.IN_PROGRESS
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    current_step: int = 1
    summary_json: dict[str, Any] = Field(default_factory=dict)


class CaseStepEvent(BaseModel):
    """Событие внутри прохождения шага."""

    id: str
    run_id: str
    step_id: str
    action: EventAction
    comment: str | None = None
    photo_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class CaseSubmission(BaseModel):
    """Пользовательская заявка на новый кейс."""

    id: str
    title: str | None = None
    problem_description: str | None = None
    actions_taken: str | None = None
    result: str | None = None
    recommendations: str | None = None
    photos: list[str] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    moderation_status: SubmissionStatus = SubmissionStatus.NEW


class SearchMatch(BaseModel):
    """Результат подбора кейса."""

    case: Case
    score: int
    matched_terms: list[str] = Field(default_factory=list)


class UserState(BaseModel):
    """Состояние диалога пользователя для MVP."""

    screen: ConversationScreen = ConversationScreen.MAIN_MENU
    last_query: str | None = None
    last_matches: list[SearchMatch] = Field(default_factory=list)
    selected_case_id: str | None = None
    active_run: CaseRun | None = None
    run_events: list[CaseStepEvent] = Field(default_factory=list)
    draft_submission: CaseSubmission | None = None
