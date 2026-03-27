"""Точка входа пилотного case bot для MAX."""

from __future__ import annotations

import asyncio
import logging
import signal
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from maxapi import Bot, Dispatcher
from maxapi.types import BotStarted, CallbackButton, MessageCreated
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from case_handlers import Handlers
from case_models import ConversationScreen, SearchMatch
from case_repository import SQLiteCaseRepository
from case_search import CaseSearchService
from case_state import StateManager
from config import settings

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 4000

bot = Bot(token=settings.max_bot_token)
dp = Dispatcher()

repository = SQLiteCaseRepository(settings.sqlite_path)
search_service = CaseSearchService(repository)
state = StateManager()
handlers = Handlers(
    repository=repository,
    search_service=search_service,
    state=state,
)


def _split_message(text: str) -> list[str]:
    if len(text) <= _MAX_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= _MAX_MESSAGE_LENGTH:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, _MAX_MESSAGE_LENGTH)
        if cut <= 0:
            cut = _MAX_MESSAGE_LENGTH
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def _send_response(
    chat_id: int,
    text: str,
    keyboard: InlineKeyboardBuilder | None = None,
) -> None:
    logger.info("→ chat_id=%s:\n%s", chat_id, text)
    chunks = _split_message(text)
    for index, chunk in enumerate(chunks):
        attachments = None
        if keyboard is not None and index == len(chunks) - 1:
            attachments = [keyboard.as_markup()]

        if attachments:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                attachments=attachments,
            )
        else:
            await bot.send_message(chat_id=chat_id, text=chunk)


def _build_main_menu_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="Найти кейс", payload="menu:find_case"),
        CallbackButton(text="Создать новый кейс", payload="menu:new_case"),
    )
    kb.row(
        CallbackButton(text="Мои последние кейсы", payload="menu:recent"),
        CallbackButton(text="Популярные кейсы", payload="menu:popular"),
    )
    kb.row(CallbackButton(text="Помощь", payload="menu:help"))
    return kb


def _build_matches_keyboard(matches: list[SearchMatch]) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for index, match in enumerate(matches, start=1):
        kb.row(
            CallbackButton(
                text=f"{index}. {match.case.title[:50]}",
                payload=f"case:open:{match.case.id}",
            )
        )
    kb.row(CallbackButton(text="Вернуться в меню", payload="menu:menu"))
    return kb


def _build_case_card_keyboard(case_id: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="Начать прохождение", payload=f"case:start:{case_id}"))
    kb.row(
        CallbackButton(text="Новый поиск", payload="menu:find_case"),
        CallbackButton(text="Вернуться в меню", payload="menu:menu"),
    )
    return kb


def _build_step_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="Сделано", payload="run:done"),
        CallbackButton(text="Не сделано", payload="run:not_done"),
        CallbackButton(text="Нужна подсказка", payload="run:hint"),
    )
    kb.row(
        CallbackButton(text="Добавить комментарий", payload="run:comment"),
        CallbackButton(text="Добавить фото", payload="run:photo"),
    )
    kb.row(
        CallbackButton(text="Назад", payload="run:back"),
        CallbackButton(text="Меню", payload="menu:menu"),
    )
    return kb


def _keyboard_for_chat(chat_id: int) -> InlineKeyboardBuilder | None:
    user_state = state.get_state(chat_id)
    if user_state.screen == ConversationScreen.MAIN_MENU:
        return _build_main_menu_keyboard()
    if (
        user_state.screen == ConversationScreen.VIEWING_SEARCH_RESULTS
        and user_state.last_matches
    ):
        return _build_matches_keyboard(user_state.last_matches)
    if (
        user_state.screen == ConversationScreen.VIEWING_CASE
        and user_state.selected_case_id
    ):
        return _build_case_card_keyboard(user_state.selected_case_id)
    if user_state.screen == ConversationScreen.IN_RUN and user_state.active_run:
        return _build_step_keyboard()
    return None


@dp.on_started()
async def on_startup() -> None:
    repository.initialize()
    logger.info("Case bot skeleton запущен и готов к приему сообщений")


@dp.bot_started()
async def on_bot_started(event: BotStarted) -> None:
    text = await handlers.handle_start(event.chat_id)
    await _send_response(event.chat_id, text, _build_main_menu_keyboard())


@dp.message_created()
async def on_text_message(event: MessageCreated) -> None:
    body = event.message.body
    if not body or not body.text:
        return

    chat_id = event.message.recipient.chat_id
    text = body.text.strip()
    logger.info("Сообщение от chat_id=%s: %s", chat_id, text[:120])

    try:
        lowered = text.lower()
        if lowered in {"/start", "start"}:
            reply = await handlers.handle_start(chat_id)
        elif lowered in {"/help", "help"}:
            reply = await handlers.handle_help(chat_id)
        else:
            reply = await handlers.handle_text(chat_id, text)
    except Exception:
        logger.exception("Ошибка обработки текстового сообщения, chat_id=%s", chat_id)
        reply = "Во время обработки сообщения произошла ошибка. Попробуйте еще раз."

    await _send_response(chat_id, reply, _keyboard_for_chat(chat_id))


@dp.message_callback()
async def on_callback(event: MessageCallback) -> None:
    payload = event.callback.payload or ""
    chat_id = event.message.recipient.chat_id if event.message else None
    if not chat_id:
        return

    try:
        if payload.startswith("menu:"):
            action = payload.split(":", 1)[1]
            reply = await handlers.handle_menu_action(chat_id, action)
        elif payload.startswith("case:open:"):
            case_id = payload.split(":", 2)[2]
            reply = await handlers.handle_case_selected(chat_id, case_id)
        elif payload.startswith("case:start:"):
            case_id = payload.split(":", 2)[2]
            reply = await handlers.handle_run_started(chat_id, case_id)
        elif payload.startswith("run:"):
            action = payload.split(":", 1)[1]
            reply = await handlers.handle_run_action(chat_id, action)
        else:
            return

        await event.answer(notification="Обновляю…", raise_if_not_exists=False)
        await _send_response(chat_id, reply, _keyboard_for_chat(chat_id))
    except Exception:
        logger.exception("Ошибка callback, chat_id=%s, payload=%s", chat_id, payload)
        await bot.send_message(
            chat_id=chat_id,
            text="Не удалось обработать нажатие. Попробуйте еще раз.",
        )


def main() -> None:
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        log_dir / "bot.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(handler)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(dp.stop_polling()),
                )
            except NotImplementedError:
                logger.debug("Signal handlers are not available on this platform")
                break

        await dp.start_polling(bot, skip_updates=True)

    asyncio.run(run())


if __name__ == "__main__":
    main()
