# AST Bot

`AST Bot` — бот для MAX, который помогает находить производственные кейсы в электроэнергетике, открывать карточку кейса и проходить шаги внутри диалога.

Текущая версия проекта использует новый доменный слой `case_*`, локальную SQLite-базу и стартовые кейсы для пилота.

## Что уже работает

- `/start` и `/help`
- главное меню в MAX
- поиск по свободному тексту
- раздел «Популярные кейсы»
- карточка кейса
- базовое пошаговое прохождение
- локальный каталог кейсов и шагов в SQLite

Старые файлы про закупки оставлены в репозитории как legacy-контур, но активный сценарий бота сейчас живет в:

- `bot.py`
- `case_models.py`
- `case_repository.py`
- `case_search.py`
- `case_state.py`
- `case_formatters.py`
- `case_handlers.py`

## Быстрый запуск

### 1. Клонировать репозиторий

```powershell
git clone https://github.com/ivmihailov/astbot.git
cd astbot
```

### 2. Создать виртуальное окружение

Если у вас установлен `py`:

```powershell
py -3 -m venv .venv
```

Если `py` недоступен, можно использовать `python`:

```powershell
python -m venv .venv
```

### 3. Активировать окружение

```powershell
.venv\Scripts\Activate.ps1
```

Если PowerShell блокирует выполнение скриптов:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Установить зависимости

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Создать `.env`

```powershell
Copy-Item .env.example .env
```

Минимально нужен только:

- `MAX_BOT_TOKEN`

Опционально, для следующего этапа интеграции с GigaChat:

- `GIGACHAT_CREDENTIALS`
- `GIGACHAT_SCOPE`
- `GIGACHAT_PARSE_MODEL`
- `GIGACHAT_ANSWER_MODEL`

По умолчанию уже подходят:

- `SQLITE_PATH=data/cases.db`
- `MEDIA_DIR=storage/photos`

## Запуск

### Основной способ

```powershell
powershell -ExecutionPolicy Bypass -File .\run_bot.ps1
```

Скрипт сам пытается найти Python в таком порядке:

1. `.venv\Scripts\python.exe`
2. `py -3`
3. системный `python.exe`

### Запуск в отдельном окне

```powershell
.\start_bot.cmd
```

### Проверка статуса и остановка

```powershell
powershell -ExecutionPolicy Bypass -File .\status_bot.ps1
powershell -ExecutionPolicy Bypass -File .\stop_bot.ps1
```

## Данные и логи

- база данных: `data/cases.db`
- основной лог: `logs/bot.log`
- stdout/stderr процесса: `logs/runtime.out`, `logs/runtime.err`

Каталог кейсов и шагов инициализируется автоматически при первом запуске.

## Быстрая проверка

После старта откройте бота в MAX и попробуйте:

1. `/start`
2. `Популярные кейсы`
3. `Найти кейс`
4. запрос `траншея заливается водой`

## Текущее состояние проекта

- аудит и план перестройки: `docs/pilot_rebuild_plan.md`
- фото, постоянная история прохождения, аналитика и нормализация запроса через GigaChat — следующие этапы
- `.env`, логи и локальная SQLite-база не коммитятся в git

## Лицензия

Проект распространяется под `PolyForm Noncommercial 1.0.0`.

Это означает, что использовать код в некоммерческих целях можно по условиям лицензии, а коммерческое использование требует отдельного согласования с правообладателем.
