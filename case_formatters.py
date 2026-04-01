"""Текстовые форматтеры для MVP case bot."""

from __future__ import annotations

from html import escape

from case_models import (
    Case,
    CaseRun,
    CaseStep,
    CaseStepEvent,
    CaseSubmission,
    CaseType,
    EventAction,
    SearchMatch,
    SubmissionMediaType,
)

_CASE_TYPE_LABELS = {
    CaseType.PROBLEM: "Проблема",
    CaseType.OPPORTUNITY: "Возможность",
}


def _is_user_case(case: Case) -> bool:
    return case.id.startswith("user-case-")


def _step_detail(case: Case, index: int) -> str:
    if index >= len(case.steps):
        return "—"
    return case.steps[index].help_text or "—"


def _e(value: object) -> str:
    return escape(str(value), quote=False)


def format_welcome() -> str:
    return (
        "<b>Пилотный бот по кейсам в строительстве электроэнергетики.</b>\n\n"
        "<b>Что уже работает в этом каркасе:</b>\n"
        "• поиск по стартовым кейсам из ТЗ;\n"
        "• карточка кейса;\n"
        "• базовое пошаговое прохождение;\n"
        "• прием заявки на новый кейс.\n\n"
        "Выберите действие в меню ниже."
    )


def format_help() -> str:
    return (
        "<b>Как пользоваться MVP:</b>\n\n"
        "1. Нажмите «Найти кейс» и опишите ситуацию свободным текстом.\n\n"
        "2. Выберите один из 1-3 похожих кейсов.\n\n"
        "3. Откройте карточку и запустите прохождение.\n\n"
        "4. Если подходящего кейса нет, используйте «Создать новый кейс».\n\n"
        "Пока это первый вертикальный срез. Фото, комментарии, БД и админка будут подключаться следующими шагами."
    )


def format_matches(query: str, matches: list[SearchMatch]) -> str:
    if not matches:
        return (
            f"По запросу «{_e(query)}» точного кейса пока не нашлось.\n\n"
            "Пожалуйста, переформулируйте запрос."
        )

    lines = [f"<b>По запросу «{_e(query)}» нашел похожие кейсы:</b>\n"]
    for index, match in enumerate(matches, start=1):
        lines.append(f"{index}. <b>{_e(match.case.title)}</b>")
        lines.append(f"   <b>Область:</b> {_e(match.case.area)}")
        lines.append(f"   {_e(match.case.description)}")
        lines.append("")

    lines.append("Выберите кейс кнопкой ниже.")
    return "\n".join(lines)


def format_popular_cases(cases: list[Case]) -> str:
    if not cases:
        return "Популярные кейсы пока не настроены."

    lines = ["<b>Популярные кейсы из базы:</b>\n"]
    for index, case in enumerate(cases, start=1):
        lines.append(f"{index}. <b>{_e(case.title)}</b>")
        lines.append(f"   <b>Область:</b> {_e(case.area)}")
        lines.append(f"   {_e(case.description)}")
        lines.append("")
    lines.append("Откройте нужный кейс кнопкой ниже.")
    return "\n".join(lines)


def format_case_card(case: Case) -> str:
    total_step_media = sum(len(step.media) for step in case.steps)

    if _is_user_case(case):
        sections = [
            f"<b>{_e(case.title)}</b>",
            "Пользовательский кейс из черновой базы.",
            f"<b>Что произошло:</b>\n{_e(case.description)}",
            f"<b>Что сделали:</b>\n{_e(_step_detail(case, 1))}",
            f"<b>Какой получился результат:</b>\n{_e(_step_detail(case, 2))}",
            f"<b>Какие рекомендации оставили:</b>\n{_e(_step_detail(case, 3))}",
            f"<b>Медиа:</b> общих — {len(case.media)}, на шагах — {total_step_media}",
        ]
        return "\n\n".join(sections)

    roles = ", ".join(_e(role) for role in case.roles) if case.roles else "не указаны"
    sections = [
        f"<b>{_e(case.title)}</b>",
        f"<b>Описание:</b> {_e(case.description)}",
        f"<b>Тип:</b> {_e(_CASE_TYPE_LABELS[case.type])}",
        f"<b>Область:</b> {_e(case.area)}",
        f"<b>Последствия:</b> {_e(case.consequences)}",
        f"<b>Ожидаемое время:</b> {_e(case.estimated_time)}",
        f"<b>Роли:</b> {roles}",
        f"<b>Медиа:</b> общих — {len(case.media)}, на шагах — {total_step_media}",
    ]
    return "\n\n".join(sections)


def format_case_step(case: Case, step: CaseStep, run: CaseRun) -> str:
    details_label = "Детали этого блока"
    if _is_user_case(case):
        details_label = "Что написал автор"

    return (
        f"<b>{_e(case.title)}</b>\n\n"
        f"<b>Шаг {step.step_no}/{len(case.steps)}</b>\n\n"
        f"<b>Действие:</b> {_e(step.action_text)}\n"
        f"\n<b>{_e(details_label)}:</b> {_e(step.help_text or '—')}\n"
        f"\n<b>Зачем:</b> {_e(step.why_text or '—')}\n"
        f"\n<b>Обязательный шаг:</b> {'да' if step.required else 'нет'}\n"
        f"\n<b>Медиа на этом шаге:</b> {len(step.media)}"
    )


def format_step_hint(step: CaseStep) -> str:
    return (
        f"<b>Подсказка по шагу {step.step_no}</b>\n\n"
        f"<b>Зачем:</b> {_e(step.why_text or '—')}\n"
        f"<b>Как действовать:</b> {_e(step.help_text or 'Подсказка пока не заполнена.')}"
    )


def format_run_summary(
    case: Case,
    run: CaseRun,
    events: list[CaseStepEvent],
) -> str:
    done_count = sum(event.action == EventAction.STEP_DONE for event in events)
    blocked_count = sum(event.action == EventAction.STEP_BLOCKED for event in events)
    hint_count = sum(event.action == EventAction.HINT_REQUESTED for event in events)

    return (
        f"<b>Кейс завершен:</b> {_e(case.title)}\n\n"
        f"<b>Старт:</b> {_e(run.started_at.strftime('%d.%m.%Y %H:%M UTC'))}\n"
        f"<b>Финиш:</b> {_e(run.finished_at.strftime('%d.%m.%Y %H:%M UTC') if run.finished_at else '—')}\n"
        f"<b>Шагов выполнено:</b> {done_count}\n"
        f"<b>Шагов с отметкой «Не сделано»:</b> {blocked_count}\n"
        f"<b>Запросов подсказки:</b> {hint_count}\n\n"
        "Дальше можно вернуться в меню, запустить новый поиск или оформить новый кейс."
    )


def format_submission_intro() -> str:
    return (
        "<b>Создаем новый кейс.</b>\n\n"
        "Ваши ответы потом попадут в карточку кейса и в поиск.\n\n"
        "Поэтому лучше писать коротко, по делу и без лишних вводных.\n\n"
        "<b>Шаг 1/6.</b> Пришлите короткое название.\n\n"
        "Например: «Траншею затопило после дождя»."
    )


def format_submission_next(step_no: int, prompt: str) -> str:
    return f"<b>Шаг {step_no}/6.</b>\n\n{prompt}"


def format_submission_media_prompt(submission: CaseSubmission) -> str:
    photo_count = sum(
        media.media_type == SubmissionMediaType.PHOTO
        for media in submission.media
    )
    video_count = sum(
        media.media_type == SubmissionMediaType.VIDEO
        for media in submission.media
    )
    return (
        "<b>Шаг 6/6.</b> Можно приложить фото и видео к новому кейсу.\n\n"
        f"<b>Сейчас приложено:</b> фото — {photo_count}, видео — {video_count}.\n\n"
        "Пришлите одно или несколько медиа сообщениям в чат.\n\n"
        "Если хотите привязать файл к шагу, добавьте в подпись текст вроде "
        "«шаг 1» или «шаги 1,3».\n\n"
        "Если шаг не указан, медиа будет показано на уровне карточки кейса.\n\n"
        "Когда закончите, нажмите кнопку «Сохранить кейс»."
    )


def format_submission_media_added(
    submission: CaseSubmission,
    added_count: int,
) -> str:
    photo_count = sum(
        media.media_type == SubmissionMediaType.PHOTO
        for media in submission.media
    )
    video_count = sum(
        media.media_type == SubmissionMediaType.VIDEO
        for media in submission.media
    )
    return (
        f"<b>Добавил медиа:</b> {added_count}.\n\n"
        f"<b>Всего в заявке:</b> фото — {photo_count}, видео — {video_count}.\n\n"
        "Можно прислать еще файлы, указать шаги в подписи или нажать «Сохранить кейс»."
    )


def format_submission_saved(submission: CaseSubmission) -> str:
    photo_count = sum(
        media.media_type == SubmissionMediaType.PHOTO
        for media in submission.media
    )
    video_count = sum(
        media.media_type == SubmissionMediaType.VIDEO
        for media in submission.media
    )
    return (
        "<b>Новый кейс сохранен в черновой базе.</b>\n\n"
        "Он сразу будет виден в поиске как пользовательский кейс.\n\n"
        f"<b>Название:</b> {_e(submission.title or '—')}\n"
        f"\n<b>Описание проблемы:</b> {_e(submission.problem_description or '—')}\n"
        f"\n<b>Что сделали:</b> {_e(submission.actions_taken or '—')}\n"
        f"\n<b>Результат:</b> {_e(submission.result or '—')}\n"
        f"\n<b>Рекомендации:</b> {_e(submission.recommendations or '—')}\n\n"
        f"<b>Медиа:</b> фото — {photo_count}, видео — {video_count}\n\n"
        "Заявка и медиа сохранены локально в SQLite и временное хранилище для демонстрации."
    )
