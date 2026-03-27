"""Конфигурация приложения."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Настройки приложения, загружаемые из переменных окружения."""

    # Токен бота MAX (max.ru)
    max_bot_token: str = field(
        default_factory=lambda: os.environ["MAX_BOT_TOKEN"]
    )

    # Авторизационные данные GigaChat пока делаем опциональными:
    # бот должен стартовать уже на этапе минимального каркаса.
    gigachat_credentials: str | None = field(
        default_factory=lambda: os.getenv("GIGACHAT_CREDENTIALS")
    )

    # Scope GigaChat API: GIGACHAT_API_PERS (физлица) / GIGACHAT_API_CORP (юрлица)
    gigachat_scope: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    )

    # Базовый URL ГосПлан API v2
    gosplan_base_url: str = field(
        default_factory=lambda: os.getenv("GOSPLAN_BASE_URL", "https://v2.gosplan.info")
    )

    # Модель GigaChat для парсинга запросов
    gigachat_parse_model: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_PARSE_MODEL", "GigaChat-Pro")
    )

    # Модель GigaChat для генерации ответов (качественная)
    gigachat_answer_model: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_ANSWER_MODEL", "GigaChat-Pro")
    )

    # Будущая локальная БД пилота
    sqlite_path: str = field(
        default_factory=lambda: os.getenv("SQLITE_PATH", "data/cases.db")
    )

    # Будущее локальное хранилище медиа
    media_dir: str = field(
        default_factory=lambda: os.getenv("MEDIA_DIR", "storage/photos")
    )


# Глобальный экземпляр настроек — создаётся при первом импорте
settings = Settings()
