# Case Images

В эту папку складываются статические изображения для 15 стартовых кейсов.

Логика подхвата уже встроена в бот:

- `assets/case_images/<case_id>/cover.png` — обложка кейса
- `assets/case_images/<case_id>/step-<n>.png` — изображение для шага `n`
- также поддерживаются `.jpg`, `.jpeg`, `.webp`

Примеры:

- `assets/case_images/flooded-trench/cover.png`
- `assets/case_images/flooded-trench/step-2.png`
- `assets/case_images/work-without-permit/cover.jpg`

Если у кейса есть:

- `cover.*` — бот покажет картинку при открытии карточки кейса
- `step-N.*` — бот покажет картинку при переходе на соответствующий шаг

Промпты для генерации лежат в файле [prompts.json](./prompts.json).
