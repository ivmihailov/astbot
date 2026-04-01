"""Локальный сервис подбора кейсов с нормализацией и взвешенным ранжированием."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Protocol

from case_models import Case, SearchMatch


class CaseCatalog(Protocol):
    def list_cases(self) -> list[Case]:
        """Вернуть список кейсов для индексации."""


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_NON_WORD_RE = re.compile(r"[^a-zа-яё0-9]+")
_STOP_WORDS = {
    "что",
    "как",
    "если",
    "когда",
    "после",
    "перед",
    "нужно",
    "надо",
    "можно",
    "делать",
    "сделать",
    "работ",
    "работы",
    "объект",
    "объекте",
    "очень",
    "сейчас",
    "пока",
    "вчера",
    "сегодня",
    "через",
    "кейс",
    "найти",
    "поиск",
    "меня",
    "нас",
    "там",
    "тут",
    "еще",
    "ещё",
    "без",
    "пришел",
    "пришла",
    "начал",
    "начала",
    "работать",
}
_SUFFIXES = (
    "ирования",
    "ированиям",
    "ированиях",
    "иями",
    "ями",
    "ами",
    "его",
    "ого",
    "ему",
    "ому",
    "ыми",
    "ими",
    "иях",
    "ией",
    "ия",
    "ие",
    "ий",
    "ый",
    "ой",
    "ая",
    "ое",
    "ые",
    "ов",
    "ев",
    "ам",
    "ям",
    "ах",
    "ях",
    "ом",
    "ем",
    "а",
    "я",
    "ы",
    "и",
    "е",
    "у",
    "ю",
)
_SYNONYM_GROUPS = (
    {"транш", "котлован", "выемк"},
    {"вод", "затоп", "подтоп", "ливн", "дожд"},
    {"кабел", "кл", "линия"},
    {"допуск", "наряд", "разрешен", "оформлен"},
    {"бетон", "смес", "заливк"},
    {"чертеж", "документ", "схем", "исполнительн", "документац"},
    {"поставк", "доставк", "снабжен", "логист"},
    {"поврежден", "бит", "дефект", "некомплект", "комплектац"},
    {"срок", "график", "расписан", "дедлайн", "задерж"},
    {"фото", "сним", "фотограф", "видео"},
)


def _normalize_text(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = _NON_WORD_RE.sub(" ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(_normalize_text(text)):
        if len(raw) < 3 or raw in _STOP_WORDS:
            continue
        tokens.append(_stem(raw))
    return tokens


def _expand_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        for group in _SYNONYM_GROUPS:
            if any(token.startswith(root) or root.startswith(token) for root in group):
                expanded.update(group)
    return expanded


def _field_tokens(parts: list[str]) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        tokens.update(_tokenize(part))
    return _expand_tokens(tokens)


def _fuzzy_bonus(query: str, candidates: list[str]) -> int:
    best_ratio = 0.0
    for candidate in candidates:
        ratio = SequenceMatcher(None, query, _normalize_text(candidate)).ratio()
        if ratio > best_ratio:
            best_ratio = ratio

    if best_ratio >= 0.82:
        return 18
    if best_ratio >= 0.72:
        return 12
    if best_ratio >= 0.62:
        return 8
    if best_ratio >= 0.54:
        return 4
    return 0


class CaseSearchService:
    """Улучшенный локальный поиск по карточкам, фразам и шагам кейса."""

    def __init__(self, repository: CaseCatalog) -> None:
        self.repository = repository

    def find_relevant_cases(self, text: str, limit: int = 3) -> list[SearchMatch]:
        query_text = _normalize_text(text)
        raw_query_tokens = set(_tokenize(text))
        query_tokens = _expand_tokens(raw_query_tokens)
        if not query_text:
            return []

        matches: list[SearchMatch] = []
        for case in self.repository.list_cases():
            title_tokens = _field_tokens([case.title])
            area_tokens = _field_tokens([case.area])
            description_tokens = _field_tokens([case.description, case.consequences])
            role_tokens = _field_tokens(case.roles)
            phrase_tokens = _field_tokens(case.search_phrases)
            step_tokens = _field_tokens(
                [step.action_text for step in case.steps]
                + [step.why_text or "" for step in case.steps]
                + [step.help_text or "" for step in case.steps]
            )

            title_overlap = raw_query_tokens & title_tokens
            area_overlap = raw_query_tokens & area_tokens
            description_overlap = raw_query_tokens & description_tokens
            phrase_overlap = raw_query_tokens & phrase_tokens
            role_overlap = raw_query_tokens & role_tokens
            step_overlap = raw_query_tokens & step_tokens

            score = 0
            score += len(title_overlap) * 12
            score += len(area_overlap) * 8
            score += len(phrase_overlap) * 7
            score += len(description_overlap) * 5
            score += len(step_overlap) * 4
            score += len(role_overlap) * 3

            if query_tokens & title_tokens:
                score += 6
            if query_tokens & phrase_tokens:
                score += 5

            normalized_phrases = [_normalize_text(phrase) for phrase in case.search_phrases]
            normalized_title = _normalize_text(case.title)
            normalized_description = _normalize_text(case.description)

            if query_text in normalized_title:
                score += 16
            if query_text in normalized_description:
                score += 9
            if any(query_text in phrase for phrase in normalized_phrases):
                score += 14

            for phrase in normalized_phrases:
                phrase_token_set = _expand_tokens(set(_tokenize(phrase)))
                if phrase_token_set and phrase_token_set.issubset(query_tokens):
                    score += 10

            title_token_set = _expand_tokens(set(_tokenize(case.title)))
            if title_token_set and title_token_set.issubset(query_tokens):
                score += 8

            score += _fuzzy_bonus(query_text, [case.title, case.description, *case.search_phrases])

            if score <= 0:
                continue

            matched_terms = sorted(
                title_overlap
                | area_overlap
                | phrase_overlap
                | description_overlap
                | role_overlap
                | step_overlap
            )

            matches.append(
                SearchMatch(
                    case=case,
                    score=score,
                    matched_terms=matched_terms[:8],
                )
            )

        matches.sort(
            key=lambda item: (
                -item.score,
                -len(item.matched_terms),
                item.case.title,
            )
        )
        if not matches:
            return []

        best_score = matches[0].score
        min_score = max(12, int(best_score * 0.35))
        filtered = [match for match in matches if match.score >= min_score]
        return filtered[:limit]
