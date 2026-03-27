"""Каталог стартовых кейсов и SQLite-репозиторий для пилота."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from case_models import Case, CaseStep, CaseType, ConfirmationType


def _step(
    case_id: str,
    step_no: int,
    action_text: str,
    why_text: str,
    help_text: str,
    *,
    required: bool = True,
    confirmation_type: ConfirmationType = ConfirmationType.BUTTON,
) -> CaseStep:
    return CaseStep(
        id=f"{case_id}-step-{step_no}",
        case_id=case_id,
        step_no=step_no,
        action_text=action_text,
        why_text=why_text,
        required=required,
        confirmation_type=confirmation_type,
        help_text=help_text,
    )


POPULAR_CASE_IDS = {
    "flooded-trench",
    "cable-delivery-delay",
    "as-built-mismatch",
    "work-without-permit",
    "damaged-equipment",
}


SEED_CASES: list[Case] = [
    Case(
        id="cable-delivery-delay",
        title="Срыв поставки кабельной продукции на объект",
        type=CaseType.PROBLEM,
        area="Расписание",
        description="Поставка кабеля задерживается, из-за чего монтажная бригада рискует остаться без фронта работ.",
        consequences="Сдвиг графика, простой бригад и каскадное смещение следующих работ.",
        preconditions=["Есть подтвержденная задержка поставки", "Позиция влияет на ближайшие работы"],
        roles=["Прораб", "ПТО", "Снабжение"],
        estimated_time="15-20 минут",
        search_phrases=[
            "сорвали поставку кабеля",
            "не привезли кабель",
            "задержка кабельной продукции",
            "нет кабеля на объекте",
        ],
        steps=[
            _step(
                "cable-delivery-delay",
                1,
                "Проверьте остатки на объекте и критичность позиции по графику.",
                "Нужно быстро понять, есть ли запас по времени или работы встают сразу.",
                "Сверьте фактические остатки, суточное задание и ближайшие критичные участки монтажа.",
            ),
            _step(
                "cable-delivery-delay",
                2,
                "Уточните у поставщика новый срок и возможные аналоги или перераспределение.",
                "Это помогает найти управленческое решение до того, как простой станет фактом.",
                "Зафиксируйте новый ETA, доступные замены и возможность переброски материалов с другого объекта.",
            ),
            _step(
                "cable-delivery-delay",
                3,
                "Перепланируйте ближайшие работы и уведомите ответственных о корректировке графика.",
                "Команда должна быстро перейти на альтернативный фронт работ без хаоса в коммуникациях.",
                "Отправьте обновленный план прорабу, ПТО и снабжению с понятным новым сроком контроля.",
            ),
        ],
    ),
    Case(
        id="concrete-mismatch",
        title="Несоответствие марки бетона или фактического объема поставки",
        type=CaseType.PROBLEM,
        area="Качество",
        description="На площадку пришел бетон, который не совпадает с заявленными параметрами по марке или объему.",
        consequences="Риск отказа в приемке, переделки и потери времени.",
        roles=["Прораб", "Лаборатория", "ПТО", "Поставщик"],
        estimated_time="15 минут",
        search_phrases=[
            "не та марка бетона",
            "бетон не соответствует",
            "не хватает объема бетона",
            "спорная поставка бетона",
        ],
        steps=[
            _step(
                "concrete-mismatch",
                1,
                "Остановите приемку спорной поставки и выделите ее отдельно.",
                "Так вы не смешаете неподтвержденный материал с принятыми работами.",
                "Не допускайте использование смеси до сверки документов и фактических параметров.",
            ),
            _step(
                "concrete-mismatch",
                2,
                "Сверьте документы, фактический объем и подтвердите отклонение фотофиксацией.",
                "Нужна доказательная база для претензии и последующего решения.",
                "Сфотографируйте документы, замеры, маркировку и саму поставку.",
            ),
            _step(
                "concrete-mismatch",
                3,
                "Уведомите ПТО и поставщика, после чего зафиксируйте решение: замена или согласование.",
                "Без формального решения нельзя безопасно двигаться дальше по работам.",
                "Запишите, кто согласовал дальнейшие действия и на каком основании.",
            ),
        ],
    ),
    Case(
        id="stale-docs",
        title="Нет актуальной версии рабочей документации на площадке",
        type=CaseType.PROBLEM,
        area="Ресурсы",
        description="Бригада работает без подтвержденной актуальной рабочей документации или с устаревшей версией.",
        consequences="Ошибки в производстве работ, переделки и споры с технадзором.",
        roles=["Прораб", "ПТО", "Бригадир"],
        estimated_time="10-15 минут",
        search_phrases=[
            "нет рабочей документации",
            "устаревшая версия чертежей",
            "не выдали актуальную документацию",
            "работаем без актуального комплекта",
        ],
        steps=[
            _step(
                "stale-docs",
                1,
                "Проверьте статус документа и уточните, какая версия считается действующей.",
                "Сначала нужно снять неопределенность, чтобы не останавливать лишние работы.",
                "Сверьте номер ревизии, лист изменений и последнее подтверждение от ПТО.",
            ),
            _step(
                "stale-docs",
                2,
                "Остановите критичные работы по спорному узлу и запросите актуальный комплект у ПТО.",
                "Это снижает риск переделок по самым чувствительным операциям.",
                "Ограничьте только тот фронт, по которому нет подтвержденной документации.",
            ),
            _step(
                "stale-docs",
                3,
                "Доведите изменения до бригады и зафиксируйте получение актуальной версии.",
                "Команда должна работать по одной версии, а не по устным договоренностям.",
                "Зафиксируйте дату, номер комплекта и кому именно выдали обновление.",
            ),
        ],
    ),
    Case(
        id="as-built-mismatch",
        title="Исполнительная схема не совпадает с фактически выполненными работами",
        type=CaseType.PROBLEM,
        area="Качество",
        description="Исполнительная документация не отражает фактическое исполнение на объекте.",
        consequences="Замечания при сдаче, задержка закрытия объемов и повторные обходы.",
        roles=["ПТО", "Исполнитель", "Прораб"],
        estimated_time="20 минут",
        search_phrases=[
            "не сходится исполнительная схема",
            "исполнительная не совпадает с фактом",
            "схема не соответствует выполненным работам",
            "расхождения в исполнительной документации",
        ],
        steps=[
            _step(
                "as-built-mismatch",
                1,
                "Сделайте фото фактического исполнения и зафиксируйте точки расхождения.",
                "Нужно опираться на проверяемый факт, а не на устное описание проблемы.",
                "Отмечайте привязки и элементы, по которым позже будут корректировать схему или работы.",
            ),
            _step(
                "as-built-mismatch",
                2,
                "Привлеките ПТО и исполнителя для решения: корректируем схему или фактическое исполнение.",
                "Сначала нужно определить источник ошибки, иначе исправления пойдут вразнобой.",
                "Разведите ответственность: что меняет ПТО, а что проверяет производственный блок.",
            ),
            _step(
                "as-built-mismatch",
                3,
                "Зафиксируйте исправление и проведите повторную проверку перед закрытием объемов.",
                "Повторная сверка нужна, чтобы проблема не вернулась на этапе сдачи.",
                "Не закрывайте кейс, пока обновленная схема не согласована и не сверена с фактом.",
            ),
        ],
    ),
    Case(
        id="work-without-permit",
        title="Подрядчик приступил к работам без подтвержденного наряда или допуска",
        type=CaseType.PROBLEM,
        area="Коммуникации",
        description="На объекте начались работы без подтвержденного допуска, наряда или разрешения.",
        consequences="Риск нарушения ТБ, остановки работ и инцидентов.",
        roles=["Прораб", "ОТ и ТБ", "Подрядчик"],
        estimated_time="10 минут",
        search_phrases=[
            "работают без допуска",
            "нет наряда на работы",
            "подрядчик вышел без разрешения",
            "начали работы без оформления",
        ],
        steps=[
            _step(
                "work-without-permit",
                1,
                "Немедленно остановите работы и проверьте наличие обязательного допуска.",
                "Это вопрос безопасности и управленческой ответственности.",
                "Остановку лучше фиксировать сразу с указанием времени и участка работ.",
            ),
            _step(
                "work-without-permit",
                2,
                "Сообщите ответственному за производство работ и специалисту по ОТ.",
                "Нужно быстро перевести ситуацию из хаотичной в управляемую.",
                "Передайте, кто работает, на каком участке и чего именно не хватает по оформлению.",
            ),
            _step(
                "work-without-permit",
                3,
                "Возобновляйте работы только после устранения нарушения и фиксации замечания.",
                "Иначе нарушение повторится, а ответственность останется размытой.",
                "Сохраните подтверждение, что допуск оформлен и работы можно продолжать.",
            ),
        ],
    ),
    Case(
        id="damaged-equipment",
        title="Поставка оборудования пришла с повреждениями или неполной комплектацией",
        type=CaseType.PROBLEM,
        area="Закупки",
        description="На входном контроле выявлены повреждения упаковки, дефекты или недокомплект.",
        consequences="Срыв монтажа, претензии по гарантии и повторные поставки.",
        roles=["Склад", "Прораб", "Снабжение"],
        estimated_time="15 минут",
        search_phrases=[
            "оборудование повреждено",
            "неполная комплектация",
            "пришла битая поставка",
            "дефекты оборудования на приемке",
        ],
        steps=[
            _step(
                "damaged-equipment",
                1,
                "Проведите входной контроль и отдельно зафиксируйте упаковку, дефекты и комплектность.",
                "Без первичной фиксации будет сложно доказать момент возникновения проблемы.",
                "Сфотографируйте внешний вид, маркировку и все спорные элементы.",
            ),
            _step(
                "damaged-equipment",
                2,
                "Сверьте фактическую комплектацию со спецификацией и актируйте расхождение.",
                "Нужно перейти от общего ощущения проблемы к конкретному перечню отклонений.",
                "Запишите позиции, которых не хватает, и элементы с повреждениями.",
            ),
            _step(
                "damaged-equipment",
                3,
                "Передайте рекламационный пакет и примите решение: замена, доукомплектация или резерв.",
                "От этого зависит, встанет ли монтаж полностью или удастся продолжить частично.",
                "Зафиксируйте срок ответа поставщика и временный план работ на объекте.",
            ),
        ],
    ),
    Case(
        id="flooded-trench",
        title="Траншея под кабельную линию затоплена водой",
        type=CaseType.PROBLEM,
        area="Расписание",
        description="После осадков или подземного притока вода заполнила траншею под кабельную линию.",
        consequences="Невозможность продолжения работ и риск нарушения технологии укладки.",
        roles=["Прораб", "Геодезист", "Ответственный за производство работ"],
        estimated_time="15 минут",
        search_phrases=[
            "траншея заливается водой",
            "траншею затопило",
            "вода в траншее под кабель",
            "после дождя нельзя продолжать укладку",
        ],
        steps=[
            _step(
                "flooded-trench",
                1,
                "Оцените масштаб подтопления и зафиксируйте состояние траншеи на фото.",
                "Нужно понять, можно ли локально устранить проблему или требуется остановка участка.",
                "Сделайте фото по нескольким точкам и отметьте длину затопленного участка.",
            ),
            _step(
                "flooded-trench",
                2,
                "Организуйте водоотведение или откачку и проверьте состояние основания.",
                "Даже после удаления воды основание может остаться непригодным для укладки.",
                "Проверьте размыв, загрязнение и необходимость досыпки или повторной подготовки.",
            ),
            _step(
                "flooded-trench",
                3,
                "Подтвердите готовность к возобновлению работ после осмотра ответственного.",
                "Возврат к работам должен быть осознанным, а не по принципу 'вроде подсохло'.",
                "Зафиксируйте, кто разрешил продолжение и какие условия были выполнены.",
            ),
        ],
    ),
    Case(
        id="acceptance-delay",
        title="Заказчик затягивает приемку выполненных работ или не подтверждает объемы",
        type=CaseType.PROBLEM,
        area="Заинтересованные стороны",
        description="Объемы выполнены, но приемка и подтверждение со стороны заказчика буксуют.",
        consequences="Кассовый разрыв и сдвиг этапов закрытия.",
        roles=["Руководитель проекта", "ПТО", "Заказчик"],
        estimated_time="20 минут",
        search_phrases=[
            "заказчик не принимает объемы",
            "затягивают приемку",
            "не подтверждают выполненные работы",
            "спор по объемам с заказчиком",
        ],
        steps=[
            _step(
                "acceptance-delay",
                1,
                "Подготовьте полный комплект подтверждающих материалов и сверку объемов.",
                "Сильная позиция в переговорах начинается с доказательной базы.",
                "Соберите акты, фото, схемы и журнал работ по спорному этапу.",
            ),
            _step(
                "acceptance-delay",
                2,
                "Инициируйте встречу или согласование по спорным позициям.",
                "Нужно быстро сузить проблему до конкретных расхождений, а не спорить обо всем сразу.",
                "Перед встречей выделите позиции, которые уже подтверждены, и позиции под обсуждение.",
            ),
            _step(
                "acceptance-delay",
                3,
                "Зафиксируйте протокол решения и новый срок приемки.",
                "Без нового контрольного срока кейс быстро превращается в бесконечную переписку.",
                "Запишите ответственных и следующий дедлайн по каждой спорной позиции.",
            ),
        ],
    ),
    Case(
        id="unmapped-utilities",
        title="Трасса пересекается с неучтенными коммуникациями",
        type=CaseType.PROBLEM,
        area="Содержание",
        description="Во время работ обнаружены коммуникации, которых нет в исходной документации.",
        consequences="Риск аварии, простой и перепроектирование.",
        roles=["Прораб", "Проектировщик", "Заказчик"],
        estimated_time="20 минут",
        search_phrases=[
            "неучтенные коммуникации",
            "пересечение трассы с коммуникациями",
            "на трассе нашли сети",
            "в проекте нет этой коммуникации",
        ],
        steps=[
            _step(
                "unmapped-utilities",
                1,
                "Остановите работы в зоне риска и зафиксируйте координаты с фото.",
                "Главный приоритет — не повредить неизвестную сеть и не усугубить ситуацию.",
                "Отметьте точку обнаружения, глубину и визуальные признаки коммуникации.",
            ),
            _step(
                "unmapped-utilities",
                2,
                "Уведомите проектировщика и заказчика и запросите решение по обходу или корректировке.",
                "Ситуация требует согласованного решения, а не локальной самодеятельности.",
                "Передайте схему участка и кратко опишите, как находка влияет на текущий фронт работ.",
            ),
            _step(
                "unmapped-utilities",
                3,
                "Обновите рабочую документацию и план работ после получения решения.",
                "Важно, чтобы новое решение дошло до площадки в виде документа, а не только слов.",
                "Проверьте, что изменения отражены в рабочем комплекте и доведены до бригады.",
            ),
        ],
    ),
    Case(
        id="missing-crew",
        title="На смену не вышла критичная бригада или специалист",
        type=CaseType.PROBLEM,
        area="Ресурсы",
        description="Ключевые люди не вышли на смену, что ставит под угрозу суточное задание.",
        consequences="Срыв плана и смежных работ.",
        roles=["Прораб", "Подрядчик", "Руководитель участка"],
        estimated_time="10 минут",
        search_phrases=[
            "не вышла бригада",
            "нет людей на смене",
            "критичный специалист отсутствует",
            "срыв сменного задания",
        ],
        steps=[
            _step(
                "missing-crew",
                1,
                "Оцените влияние отсутствия людей на суточный план и критичные работы.",
                "Сначала нужно понять, что именно встанет, а что можно перестроить.",
                "Разделите работы на критичные и альтернативные по доступному ресурсу.",
            ),
            _step(
                "missing-crew",
                2,
                "Перераспределите людей или выберите альтернативный фронт работ.",
                "Даже частичное сохранение темпа лучше полного простоя смены.",
                "Учтите квалификацию людей и ограничения по безопасности.",
            ),
            _step(
                "missing-crew",
                3,
                "Уведомите подрядчика и руководителя, затем зафиксируйте обновленное задание.",
                "Нужна прозрачность причин и нового плана, иначе проблема повторится завтра.",
                "Сохраните, кто именно не вышел и как это было компенсировано по смене.",
            ),
        ],
    ),
    Case(
        id="financial-model",
        title="Использование пообъектной финансовой модели проекта",
        type=CaseType.OPPORTUNITY,
        area="Стоимость",
        description="Проект ведется через пообъектную финансовую модель с регулярным план-факт контролем.",
        consequences="Растет прозрачность расходов и управление приемкой.",
        roles=["Руководитель проекта", "Финансы", "ПТО"],
        estimated_time="10 минут",
        search_phrases=[
            "финансовая модель объекта",
            "план факт по объекту",
            "пообъектный бюджет",
            "контроль доходов и расходов",
        ],
        steps=[
            _step(
                "financial-model",
                1,
                "Ведите оперативную финансовую модель по этапам и видам работ.",
                "Это делает отклонения видимыми до того, как они становятся проблемой месяца.",
                "Разбейте объект на этапы с ответственными и регулярной точкой обновления.",
            ),
            _step(
                "financial-model",
                2,
                "Сопоставляйте план и факт по расходам, выручке и закрытию объемов.",
                "Один только бюджет без факта не помогает принимать решения на площадке.",
                "Подсвечивайте отклонения по сумме, сроку и причине.",
            ),
            _step(
                "financial-model",
                3,
                "Используйте данные модели для управления приемкой, ресурсами и узкими местами.",
                "Финансовая модель должна влиять на операционные решения, а не быть отдельной отчетностью.",
                "Привязывайте управленческие решения к конкретным отклонениям в модели.",
            ),
        ],
    ),
    Case(
        id="photo-reports",
        title="Цифровая фиксация фотоотчетов по этапам прямо в боте",
        type=CaseType.OPPORTUNITY,
        area="Интеграция",
        description="Фото по ключевым этапам собираются не в чатах, а в структурированном сценарии бота.",
        consequences="Снижается потеря информации и ускоряется контроль.",
        roles=["Прораб", "ПТО", "Руководитель проекта"],
        estimated_time="10 минут",
        search_phrases=[
            "фотоотчет в боте",
            "структурированные фото работ",
            "фиксация этапов фото",
            "фото как доказательная база",
        ],
        steps=[
            _step(
                "photo-reports",
                1,
                "Привяжите обязательные фото к ключевым шагам кейса.",
                "Так фото будут не 'вообще по объекту', а в контексте конкретного действия.",
                "Определите, на каких шагах без фото нельзя закрывать прохождение.",
            ),
            _step(
                "photo-reports",
                2,
                "Храните материалы прямо в карточке кейса вместе с комментариями.",
                "Контекст снимка важен не меньше самого изображения.",
                "Привязывайте фото к шагу, дате и краткому пояснению пользователя.",
            ),
            _step(
                "photo-reports",
                3,
                "Используйте собранные материалы как базу для ПТО и руководителя.",
                "Это сокращает повторные запросы 'пришли еще раз ту фотографию'.",
                "Формируйте единый пакет материалов на основе истории прохождения кейса.",
            ),
        ],
    ),
    Case(
        id="escalation-scenario",
        title="Единый сценарий эскалации отклонений через бот",
        type=CaseType.OPPORTUNITY,
        area="Коммуникации",
        description="Критичные отклонения эскалируются по одному сценарию с краткой выжимкой и вложениями.",
        consequences="Сокращается время согласования и меньше хаоса в чатах.",
        roles=["Прораб", "Руководитель проекта", "Куратор"],
        estimated_time="10 минут",
        search_phrases=[
            "эскалация отклонения",
            "поднять проблему руководителю",
            "единый сценарий эскалации",
            "короткая выжимка проблемы",
        ],
        steps=[
            _step(
                "escalation-scenario",
                1,
                "Определите критерии критичности, при которых отклонение уходит на эскалацию.",
                "Иначе эскалация быстро превратится в шум и потеряет ценность.",
                "Зафиксируйте, что считается критичным по сроку, безопасности и стоимости.",
            ),
            _step(
                "escalation-scenario",
                2,
                "Соберите короткую выжимку проблемы с фото и текущим статусом шага.",
                "Руководителю нужен контекст для решения, а не длинная переписка.",
                "В выжимке оставьте только факт, влияние, уже предпринятые действия и что требуется решить.",
            ),
            _step(
                "escalation-scenario",
                3,
                "Направьте пакет нужной роли и зафиксируйте срок обратной связи.",
                "У эскалации должен быть адресат и ожидаемое время ответа.",
                "Проверьте, что получатель понятен и не дублируется в нескольких чатах без владельца.",
            ),
        ],
    ),
    Case(
        id="hidden-works-checklist",
        title="Пошаговый контроль скрытых работ по чек-листу в боте",
        type=CaseType.OPPORTUNITY,
        area="Качество",
        description="Скрытые работы проходят через структурированный чек-лист с обязательными подтверждениями.",
        consequences="Меньше риск пропуска проверок и замечаний при сдаче.",
        roles=["Прораб", "ПТО", "Технадзор"],
        estimated_time="15 минут",
        search_phrases=[
            "контроль скрытых работ",
            "чек лист скрытых работ",
            "обязательные проверки перед закрытием",
            "нельзя завершить без подтверждений",
        ],
        steps=[
            _step(
                "hidden-works-checklist",
                1,
                "Определите обязательные контрольные точки и фото для каждого вида скрытых работ.",
                "Закрывать кейс можно только по заранее понятным правилам.",
                "Выделите минимальный набор подтверждений, без которых этап не принимается.",
            ),
            _step(
                "hidden-works-checklist",
                2,
                "Проводите пошаговую проверку по чек-листу до закрытия этапа.",
                "Так снижается шанс пропустить один критичный пункт в рутине.",
                "Каждую точку лучше подтверждать сразу, а не пытаться восстановить позже.",
            ),
            _step(
                "hidden-works-checklist",
                3,
                "Не завершайте кейс без ключевых подтверждений и итоговой фиксации.",
                "Неполный чек-лист создает ложное ощущение завершенности.",
                "Подчеркните в итоговой сводке, какие пункты были обязательными и как они подтверждены.",
            ),
        ],
    ),
    Case(
        id="two-week-planning",
        title="Планирование ближайших работ и материалов на 7-14 дней через кейс-подсказку",
        type=CaseType.OPPORTUNITY,
        area="Расписание",
        description="Регулярный сценарий планирования снижает риск авральных запросов 'нужно завтра'.",
        consequences="Меньше срывов по материалам, технике и допускам.",
        roles=["Прораб", "Снабжение", "Руководитель участка"],
        estimated_time="15 минут",
        search_phrases=[
            "планирование на две недели",
            "что нужно на 7 дней вперед",
            "дефициты материалов на ближайшие работы",
            "план ближайших работ и допусков",
        ],
        steps=[
            _step(
                "two-week-planning",
                1,
                "Раз в неделю запускайте сценарий планирования по критичным работам и материалам.",
                "Регулярность важнее идеальной детализации для пилота.",
                "Соберите ближайшие этапы, материалы, технику, допуски и узкие места.",
            ),
            _step(
                "two-week-planning",
                2,
                "Отмечайте дефициты и ответственных по их устранению.",
                "Без владельца даже хорошо найденный риск не превращается в действие.",
                "Для каждого дефицита укажите срок закрытия и ответственного.",
            ),
            _step(
                "two-week-planning",
                3,
                "Используйте итог сценария как короткий план работы на 7-14 дней.",
                "Это дает единое основание для коммуникации между площадкой и поддерживающими функциями.",
                "Фиксируйте, что именно контролируется до следующего недельного цикла.",
            ),
        ],
    ),
]


class InMemoryCaseRepository:
    """Простое хранилище кейсов для пилота."""

    def __init__(self, cases: list[Case] | None = None) -> None:
        self._cases = {case.id: case for case in (cases or SEED_CASES)}

    def list_cases(self) -> list[Case]:
        return list(self._cases.values())

    def get_case(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)


class SQLiteCaseRepository:
    """SQLite-репозиторий кейсов и стартовых таблиц пилота."""

    def __init__(self, db_path: str, seed_cases: list[Case] | None = None) -> None:
        self.db_path = Path(db_path)
        self.seed_cases = seed_cases or SEED_CASES

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    area TEXT NOT NULL,
                    description TEXT NOT NULL,
                    consequences TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version TEXT NOT NULL,
                    author TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    estimated_time TEXT NOT NULL,
                    is_popular INTEGER NOT NULL DEFAULT 0,
                    search_phrases_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS case_steps (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                    step_no INTEGER NOT NULL,
                    action_text TEXT NOT NULL,
                    why_text TEXT,
                    required INTEGER NOT NULL DEFAULT 1,
                    confirmation_type TEXT NOT NULL,
                    help_text TEXT,
                    next_rule TEXT
                );

                CREATE TABLE IF NOT EXISTS case_runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    case_id TEXT NOT NULL REFERENCES cases(id),
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    current_step INTEGER NOT NULL,
                    summary_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS case_step_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES case_runs(id) ON DELETE CASCADE,
                    step_id TEXT NOT NULL REFERENCES case_steps(id),
                    action TEXT NOT NULL,
                    comment TEXT,
                    photo_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS new_case_submissions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    problem_description TEXT,
                    actions_taken TEXT,
                    result TEXT,
                    recommendations TEXT,
                    photos_json TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    moderation_status TEXT NOT NULL
                );
                """
            )
            self._seed(conn)

    def list_cases(self) -> list[Case]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM cases
                ORDER BY is_popular DESC, title ASC
                """
            ).fetchall()
            return [self._load_case(conn, row["id"]) for row in rows]

    def list_popular_cases(self, limit: int = 5) -> list[Case]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM cases
                WHERE is_popular = 1
                ORDER BY title ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._load_case(conn, row["id"]) for row in rows]

    def get_case(self, case_id: str) -> Case | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM cases WHERE id = ?",
                (case_id,),
            ).fetchone()
            if row is None:
                return None
            return self._load_case(conn, case_id)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed(self, conn: sqlite3.Connection) -> None:
        for seed_case in self.seed_cases:
            case = seed_case.model_copy(
                update={"is_popular": seed_case.id in POPULAR_CASE_IDS}
            )
            conn.execute(
                """
                INSERT INTO cases (
                    id,
                    title,
                    type,
                    area,
                    description,
                    consequences,
                    preconditions_json,
                    roles_json,
                    status,
                    version,
                    author,
                    updated_at,
                    estimated_time,
                    is_popular,
                    search_phrases_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    type = excluded.type,
                    area = excluded.area,
                    description = excluded.description,
                    consequences = excluded.consequences,
                    preconditions_json = excluded.preconditions_json,
                    roles_json = excluded.roles_json,
                    status = excluded.status,
                    version = excluded.version,
                    author = excluded.author,
                    updated_at = excluded.updated_at,
                    estimated_time = excluded.estimated_time,
                    is_popular = excluded.is_popular,
                    search_phrases_json = excluded.search_phrases_json
                """,
                (
                    case.id,
                    case.title,
                    case.type.value,
                    case.area,
                    case.description,
                    case.consequences,
                    json.dumps(case.preconditions, ensure_ascii=False),
                    json.dumps(case.roles, ensure_ascii=False),
                    case.status.value,
                    case.version,
                    case.author,
                    case.updated_at.isoformat(),
                    case.estimated_time,
                    int(case.is_popular),
                    json.dumps(case.search_phrases, ensure_ascii=False),
                ),
            )
            conn.execute("DELETE FROM case_steps WHERE case_id = ?", (case.id,))
            for step in case.steps:
                conn.execute(
                    """
                    INSERT INTO case_steps (
                        id,
                        case_id,
                        step_no,
                        action_text,
                        why_text,
                        required,
                        confirmation_type,
                        help_text,
                        next_rule
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.id,
                        step.case_id,
                        step.step_no,
                        step.action_text,
                        step.why_text,
                        int(step.required),
                        step.confirmation_type.value,
                        step.help_text,
                        step.next_rule,
                    ),
                )
        conn.commit()

    def _load_case(self, conn: sqlite3.Connection, case_id: str) -> Case:
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ?",
            (case_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Case not found: {case_id}")

        step_rows = conn.execute(
            """
            SELECT *
            FROM case_steps
            WHERE case_id = ?
            ORDER BY step_no ASC
            """,
            (case_id,),
        ).fetchall()

        steps = [
            CaseStep(
                id=step_row["id"],
                case_id=step_row["case_id"],
                step_no=step_row["step_no"],
                action_text=step_row["action_text"],
                why_text=step_row["why_text"],
                required=bool(step_row["required"]),
                confirmation_type=step_row["confirmation_type"],
                help_text=step_row["help_text"],
                next_rule=step_row["next_rule"],
            )
            for step_row in step_rows
        ]

        return Case(
            id=row["id"],
            title=row["title"],
            type=row["type"],
            area=row["area"],
            description=row["description"],
            consequences=row["consequences"],
            preconditions=json.loads(row["preconditions_json"]),
            roles=json.loads(row["roles_json"]),
            status=row["status"],
            version=row["version"],
            author=row["author"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            estimated_time=row["estimated_time"],
            is_popular=bool(row["is_popular"]),
            search_phrases=json.loads(row["search_phrases_json"]),
            steps=steps,
        )
