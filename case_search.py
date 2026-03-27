"""Простой локальный сервис подбора 1-3 кейсов для MVP."""

from __future__ import annotations

import re
from typing import Protocol

from case_models import Case, SearchMatch


class CaseCatalog(Protocol):
    def list_cases(self) -> list[Case]:
        """Вернуть список кейсов для индексации."""

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
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
}
_SUFFIXES = (
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


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text.lower()):
        if len(raw) < 3 or raw in _STOP_WORDS:
            continue
        tokens.append(_stem(raw))
    return tokens


def _index_text(case: Case) -> str:
    parts = [
        case.title,
        case.area,
        case.description,
        case.consequences,
        *case.search_phrases,
        *[step.action_text for step in case.steps],
    ]
    return " ".join(parts)


class CaseSearchService:
    """Гибридный локальный поиск по карточкам и поисковым фразам."""

    def __init__(self, repository: CaseCatalog) -> None:
        self.repository = repository

    def find_relevant_cases(self, text: str, limit: int = 3) -> list[SearchMatch]:
        query_tokens = set(_tokenize(text))
        if not query_tokens:
            return []

        matches: list[SearchMatch] = []
        for case in self.repository.list_cases():
            case_tokens = set(_tokenize(_index_text(case)))
            matched_terms = sorted(query_tokens & case_tokens)

            phrase_bonus = 0
            for phrase in case.search_phrases:
                phrase_tokens = set(_tokenize(phrase))
                if phrase_tokens and phrase_tokens.issubset(query_tokens):
                    phrase_bonus += 5

            title_tokens = set(_tokenize(case.title))
            if title_tokens and title_tokens.issubset(query_tokens):
                phrase_bonus += 3

            score = len(matched_terms) * 4 + phrase_bonus
            if score <= 0:
                continue

            matches.append(
                SearchMatch(
                    case=case,
                    score=score,
                    matched_terms=matched_terms[:6],
                )
            )

        matches.sort(key=lambda item: (-item.score, item.case.title))
        return matches[:limit]
