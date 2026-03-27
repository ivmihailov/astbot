"""Текстовые форматтеры для MVP case bot."""

from __future__ import annotations

from case_models import (
    Case,
    CaseRun,
    CaseStep,
    CaseStepEvent,
    CaseSubmission,
    CaseType,
    EventAction,
    SearchMatch,
)

_CASE_TYPE_LABELS = {
    CaseType.PROBLEM: "Проблема",
    CaseType.OPPORTUNITY: "Возможность",
}


def format_welcome() -> str:
    return (
        "Пилотный бот по кейсам в строительстве электроэнергетики.\n\n"
        "Что уже работает в этом каркасе:\n"
        "• поиск по стартовым кейсам из ТЗ;\n"
        "• карточка кейса;\n"
        "• базовое пошаговое прохождение;\n"
        "• прием заявки на новый кейс.\n\n"
        "Выберите действие в меню ниже."
    )


def format_help() -> str:
    return (
        "Как пользоваться MVP:\n"
        "1. Нажмите «Найти кейс» и опишите ситуацию свободным текстом.\n"
        "2. Выберите один из 1-3 похожих кейсов.\n"
        "3. Откройте карточку и запустите прохождение.\n"
        "4. Если подходящего кейса нет, используйте «Создать новый кейс».\n\n"
        "Пока это первый вертикальный срез. Фото, комментарии, БД и админка будут подключаться следующими шагами."
    )


def format_matches(query: str, matches: list[SearchMatch]) -> str:
    if not matches:
        return (
            f"По запросу «{query}» точного кейса пока не нашлось.\n\n"
            "Это честный fallback из ТЗ: сейчас лучше либо переформулировать запрос, "
            "либо сразу создать новый кейс через меню."
        )

    lines = [f"По запросу «{query}» нашел похожие кейсы:"]
    for index, match in enumerate(matches, start=1):
        lines.append(f"{index}. {match.case.title}")
        lines.append(f"   Область: {match.case.area}")
        lines.append(f"   {match.case.description}")
        if match.matched_terms:
            lines.append(f"   Совпадения: {', '.join(match.matched_terms)}")

    lines.append("")
    lines.append("Выберите кейс кнопкой ниже.")
    return "\n".join(lines)


def format_popular_cases(cases: list[Case]) -> str:
    if not cases:
        return "Популярные кейсы пока не настроены."

    lines = ["Популярные кейсы из базы:"]
    for index, case in enumerate(cases, start=1):
        lines.append(f"{index}. {case.title}")
        lines.append(f"   Область: {case.area}")
        lines.append(f"   {case.description}")

    lines.append("")
    lines.append("Откройте нужный кейс кнопкой ниже.")
    return "\n".join(lines)


def format_case_card(case: Case) -> str:
    return (
        f"{case.title}\n\n"
        f"Тип: {_CASE_TYPE_LABELS[case.type]}\n"
        f"Область: {case.area}\n"
        f"Описание: {case.description}\n"
        f"Последствия: {case.consequences}\n"
        f"Ожидаемое время: {case.estimated_time}\n"
        f"Роли: {', '.join(case.roles) if case.roles else 'не указаны'}"
    )


def format_case_step(case: Case, step: CaseStep, run: CaseRun) -> str:
    return (
        f"{case.title}\n"
        f"Шаг {step.step_no}/{len(case.steps)}\n\n"
        f"Действие: {step.action_text}\n"
        f"Зачем: {step.why_text or '—'}\n"
        f"Обязательный шаг: {'да' if step.required else 'нет'}"
    )


def format_step_hint(step: CaseStep) -> str:
    return (
        f"Подсказка по шагу {step.step_no}\n\n"
        f"Зачем: {step.why_text or '—'}\n"
        f"Как действовать: {step.help_text or 'Подсказка пока не заполнена.'}"
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
        f"Кейс завершен: {case.title}\n\n"
        f"Старт: {run.started_at.strftime('%d.%m.%Y %H:%M UTC')}\n"
        f"Финиш: {run.finished_at.strftime('%d.%m.%Y %H:%M UTC') if run.finished_at else '—'}\n"
        f"Шагов выполнено: {done_count}\n"
        f"Шагов с отметкой «Не сделано»: {blocked_count}\n"
        f"Запросов подсказки: {hint_count}\n\n"
        "Дальше можно вернуться в меню, запустить новый поиск или оформить новый кейс."
    )


def format_submission_intro() -> str:
    return (
        "Создаем новый кейс.\n\n"
        "Шаг 1/5. Пришлите краткое название ситуации."
    )


def format_submission_next(step_no: int, prompt: str) -> str:
    return f"Шаг {step_no}/5. {prompt}"


def format_submission_saved(submission: CaseSubmission) -> str:
    return (
        "Новый кейс сохранен в черновой базе на модерацию.\n\n"
        f"Название: {submission.title or '—'}\n"
        f"Описание проблемы: {submission.problem_description or '—'}\n"
        f"Что сделали: {submission.actions_taken or '—'}\n"
        f"Результат: {submission.result or '—'}\n"
        f"Рекомендации: {submission.recommendations or '—'}\n\n"
        "Следующим шагом подключим отдельный просмотр таких заявок для администратора."
    )
