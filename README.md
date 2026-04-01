# AST Bot

`AST Bot` — бот для MAX, который помогает искать производственные кейсы, открывать карточки кейсов и проходить пошаговые сценарии внутри диалога.

Текущий runtime работает на новом доменном слое `case_*`, использует SQLite для пилота и локальное файловое хранилище для медиа.

## Что уже работает

- `/start` и главное меню
- поиск по кейсам свободным текстом
- раздел `Популярные кейсы`
- карточка кейса с форматированием
- пошаговое прохождение кейса
- создание нового кейса
- сохранение пользовательских кейсов в SQLite
- прикрепление фото и видео
- локальные изображения для стартовых кейсов из `assets/case_images`

## Структура активного контура

Основной код бота:

- `bot.py`
- `case_models.py`
- `case_repository.py`
- `case_search.py`
- `case_state.py`
- `case_formatters.py`
- `case_handlers.py`

Старые закупочные файлы оставлены как legacy-слой и не используются в текущем runtime.

## Docker: локальный запуск

Это основной способ запуска проекта.

### Что установить

Нужно:

- `git`
- `docker`
- `docker compose`

Для Ubuntu:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

После добавления пользователя в группу Docker нужно перелогиниться.

### Подготовка

```bash
git clone https://github.com/ivmihailov/astbot.git
cd astbot
cp .env.example .env
```

Минимально нужно заполнить только:

- `MAX_BOT_TOKEN`

Остальные переменные можно оставить по умолчанию:

- `SQLITE_PATH=data/cases.db`
- `MEDIA_DIR=storage/photos`

### Сборка и запуск

```bash
docker compose build astbot
docker compose up -d astbot
docker compose ps
docker compose logs -f astbot
```

Остановка:

```bash
docker compose down
```

## Docker: выгрузка образа на сервер

В проекте есть два сценария:

- `docker-compose.yml` — локальная сборка и запуск
- `docker-compose.server.yml` — запуск уже загруженного образа на сервере

### 1. Собрать образ локально

```bash
docker compose build astbot
```

После сборки образ имеет тег:

```bash
astbot:0.1.0
```

### 2. Сохранить образ в tar

```bash
mkdir -p output/deploy
docker save astbot:0.1.0 -o output/deploy/astbot-0.1.0.tar
```

### 3. Передать на сервер

Передайте на сервер:

- `astbot-0.1.0.tar`
- `.env`
- `docker-compose.server.yml`

Если сохраняли образ в `output/deploy`, передавайте файл `output/deploy/astbot-0.1.0.tar`.

Если проект уже склонирован на сервере, достаточно передать только tar и `.env`.

## Разворот на Linux-сервере через docker load

На сервере:

```bash
mkdir -p /home/admin/astbot
cd /home/admin/astbot
```

Положите туда:

- `astbot-0.1.0.tar`
- `.env`
- `docker-compose.server.yml`

Создайте каталоги под данные:

```bash
mkdir -p data logs storage
```

Загрузите образ:

```bash
docker load -i astbot-0.1.0.tar
```

Запустите контейнер:

```bash
docker compose -f docker-compose.server.yml up -d
```

Проверьте:

```bash
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f astbot
```

Остановка:

```bash
docker compose -f docker-compose.server.yml down
```

## Что хранится на хосте

И локальный compose, и серверный compose монтируют данные на хост:

- `./data -> /app/data`
- `./logs -> /app/logs`
- `./storage -> /app/storage`

Там лежат:

- SQLite-база
- логи
- локальные медиа

## Что важно для стабильности

- Бот работает через `long polling`, поэтому ему не нужен HTTP-порт.
- Для MVP используется SQLite, поэтому держать нужно один экземпляр бота, а не несколько одновременно.
- При старте контейнер сам создает `data`, `logs` и `storage/photos`, если их еще нет.
- Логи пишутся и в stdout контейнера, и в `logs/bot.log`.

## Быстрая проверка после старта

Откройте бота в MAX и проверьте:

1. `/start`
2. `Популярные кейсы`
3. `Найти кейс`
4. запрос вроде `траншею затопило водой`

## Лицензия

Проект распространяется под `PolyForm Noncommercial 1.0.0`.

Коммерческое использование требует отдельного согласования с правообладателем.
