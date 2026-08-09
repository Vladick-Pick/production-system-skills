# Миграция шаблона v0.1 → v0.2

Этот mapping преобразует только структуру и явно подтверждённые строки. Он не разрешает угадывать референты, контрагентов, исполнителей, продукты или версии. Любое неоднозначное поле получает `conflict` и выносится в отчёт миграции до записи.

Это не пятый публичный скилл. Документ является исполнимым migration runbook для режимов `migration-assessment` и `migration-write` внутри `maintain-production-system`. Он нужен, когда уже наполненная рабочая книга v0.1 должна быть перенесена в отдельную книгу v0.2 без потери исходника, stable IDs и обнаруженных неизвестных.

## 0. Основной результат и граница

Для каждой исходной книги агент создаёт отдельное `migration dossier`. Досье отвечает на пять вопросов:

1. что реально найдено в v0.1;
2. что можно перенести без смыслового решения;
3. что можно детерминированно вычислить или разложить;
4. каких новых сведений требует v0.2 и кто должен их подтвердить;
5. какими пакетами, проверками и способом отката выполняется перенос.

По умолчанию одна исходная книга становится одной staging-книгой v0.2 и сохраняет собственный `model_id`. Две рабочие книги не объединяются автоматически. Если они описывают один бизнес и должны стать одной книгой, это отдельное решение о границе, конфликтах ID, версиях и источниках; до него агент ведёт два независимых досье.

Исходная v0.1-книга неизменяема в течение миграции. Не перестраивать её листы на месте и не вставлять в неё строки v0.2. Целевая структура создаётся отдельной копией канонического v0.2 через JSON-схему и builder; из v0.1 переносятся только авторские значения и подтверждённые связи, но не старые formulas, validations, formatting или вычисляемые представления.

## 0.1. Режимы

| Режим | Разрешено | Результат |
|---|---|---|
| `migration-assessment` | читать источник, экспорт, структуру и данные; строить досье; задавать один вопрос | read-only досье и список блокеров, без staging-записей |
| `migration-proposal` | уточнять смысл, предлагать version plan и migration batches | полный план переноса с source locators и неизвестными |
| `migration-write` | после подтверждения точного package/hash записать один bounded batch в staging | одна проверенная migration transaction |
| `migration-verify` | перечитать source, transactions, target snapshot, проверки и counts | reconciliation report и readiness следующего batch либо всей миграции |

Наличие доступа на запись не включает `migration-write`. Первый проход всегда `migration-assessment`, если пользователь явно не передал уже проверенное досье и подтверждённый пакет.

## 0.2. Классы переноса

Каждая непустая авторская строка и каждое содержательное поле получают ровно один класс:

| Класс | Что означает | Можно ли писать без вопроса |
|---|---|---|
| `copy` | stable ID и значение имеют тот же смысл и допустимый тип в v0.2 | да, только внутри подтверждённого batch |
| `derive` | значение однозначно вычисляется из подтверждённых данных: selector, `version_operation`, relation row | да, с сохранённым правилом вычисления |
| `split` | одна строка v0.1 должна стать несколькими сущностями v0.2 | только после проверки идентичности частей |
| `confirm` | смысл, граница, идентичность, версия или владелец неоднозначны | нет; задать один решающий вопрос |
| `new-required` | обязательного понятия или значения в v0.1 не было | нет; получить источник либо человеческое решение |
| `regenerate` | лист, формула, selector, срез или представление строится заново из v0.2-контракта | не переносить старое значение |
| `archive` | значение сохраняется только как свидетельство исходника | не переносить как действующую модель |
| `drop` | техническое или устаревшее поле не имеет целевого смысла | не переносить; записать причину в досье |

`copy` не означает немедленную запись. Он означает отсутствие отдельного смыслового вопроса; запись всё равно входит в показанный migration package и подтверждённую transaction.

## 0.3. Что обычно переносится сразу

После выбора target version и проверки ссылочной целостности класс `copy` обычно получают:

- существующие stable IDs систем, позиций, процессов, действий, связей действий, объектов, состояний, переходов, элементов и связей модели;
- названия, определения, цели, входы, выходы, условия, свидетельства, ответственности и примечания, если их смысл не изменился;
- `knowledge_status`, `source_id`, source locator, даты актуализации и разрешённые ссылки на источники;
- существующие FK, если каждый ID однозначно разрешается в выбранном исходном срезе;
- авторские критерии приёмки, правила и SLA как исходные значения, но не их новая классификация или владелец истины.

Агент не задаёт пользователю вопросы по каждому такому полю. Он показывает их сводным блоком с counts, source ranges и перечнем исключений.

## 0.4. Что вычисляется заново

Без отдельного бизнес-решения, но только из подтверждённых исходных значений:

- `*_selector`, dropdown catalogs и соседние технические ID;
- `version_operation = применить` для включённых редакций migration version;
- relation rows, которые однозначно следуют из старой структуры, например `система → производит → продукт`;
- `Срез модели`, `Проверки`, `Реестр процессов`, `Рабочая панель`;
- formulas, protections, formatting, named ranges и validations v0.2;
- BPMN/SVG/manifest после разрешения семантики и точного среза; старый draw.io не является такой сборкой.

## 0.5. Что обязательно уточнить или получить заново

Глобальные блокеры выяснять раньше вопросов по отдельным строкам:

1. точная граница каждой книги и её `model_id`; объединяются ли несколько книг;
2. какой `version_id + model_layer` v0.1 является исходным авторитетным состоянием и как старые версии отображаются в одну линейную цепочку v0.2;
3. какая версия после миграции остаётся `черновик`, какую можно принять и какую отдельно вводить в действие;
4. имя, фамилия и позиция человека, подтверждающего migration packages;
5. подтверждённые личности исполнителей и новые `performer_id`, если в v0.1 есть только имена;
6. для объектов — `identity_rule`, `creation_event`, `closing_event`, когда они не доказаны источником;
7. для встроенных продуктов — определение, основной объект, требуемое состояние, единица, пакет и критерии приёмки;
8. для материалов — самостоятельная identity, тип, назначение, содержимое или URL и владелец;
9. для контрактов — внешняя сторона, направление, отдельные продукты и позиции, цена, валюта, единица, billing trigger и payment terms;
10. для интерфейсов передачи — триггер, канал, формат, пакет, действие и доказательство приёмки, отказ, возврат и fallback;
11. для развилок — точные условия и default branch, если старые данные не позволяют вывести их однозначно;
12. судьба активных экземпляров и готовность обязательных изменений до ввода версии.

Не задавать этот список анкетой. Сначала прочитать всю доступную книгу, сгруппировать одинаковые неизвестные и задать один вопрос с наибольшим downstream-влиянием. После ответа обновить досье, но не писать staging.

## 0.6. Что не переносится как каноническая модель

- старые formulas, formatting, validations, скрытые ID-словари и вычисляемые листы;
- `next_audit` как поле модели;
- row-level `model_layer`, если слой теперь принадлежит версии;
- `Проекция draw.io`, её геометрия и прежний generated fingerprint;
- старые ссылки на диаграммы как доказательство BPMN/SVG build v0.2;
- конкретные исполнения процессов, отправленные сообщения, платежи и другие операционные факты;
- правдоподобные значения, придуманные только для прохождения обязательности или FK.

Такие значения получают `archive`, `drop` либо становятся source evidence для отдельного решения.

## 0.7. Порядок работы агента

### A. Идентифицировать источник без записи

Зафиксировать spreadsheet ID/URL или XLSX-export, title, observed revision/export time, content hash, владельца доступа и backup locator. Рабочая книга с данными не обязана иметь бинарный hash пустого шаблона. Проверяется structural fingerprint: ожидаемые 21 лист v0.1 и их заголовки, обязательные authoring sheets и ID columns, фактический drift и формульные ошибки.

Присвоить источнику один статус:

- `v0.1-compatible` — структура распознана, drift не блокирует inventory;
- `v0.1-with-drift` — структура распознана, отклонения перечислены и требуют mapping;
- `unknown-schema` — источник нельзя безопасно интерпретировать; миграцию остановить.

### B. Построить inventory и version plan

Посчитать непустые authoring rows по каждому листу, уникальные и дублирующиеся stable IDs, неразрешённые FK, значения version/layer/status, внешние ссылки и строки с `knowledge_status = конфликт|неизвестно`. Computed/derived sheets перечислить отдельно: их строки не считаются авторскими данными.

Если v0.1 содержит несколько версий или одновременно текущий и целевой слой, не сворачивать их автоматически в одну root version. Предложить линейный version plan, показать, какие строки попадут в каждый срез, и получить подтверждение. Исторические варианты, которые нельзя доказуемо встроить в цепочку, остаются в backup и migration evidence, а не исчезают молча.

### C. Классифицировать все строки

Для каждой source row сохранить source sheet, row number/range, stable ID, target sheet(s), класс переноса, proposed operation, source/target version, blocker и требуемое решение. Одинаковые механические строки можно группировать диапазоном; `confirm`, `new-required` и `split` перечислять отдельно.

### D. Провести интервью

Следовать `INTERVIEW-CONTRACT.md`: одновременно один `active_question_id`; ответ обновляет только migration dossier. Приоритет вопросов: граница и версии → identity и дедупликация → продукты/материалы → внешние контракты/интерфейсы → активные экземпляры и ввод.

### E. Разбить перенос на bounded batches

Большую модель не обязано переносить одной гигантской transaction. Один migration run объединяется общими source fingerprint, target `model_id`, working version и migration plan, но каждый batch имеет собственные `package_id`, hash, confirmation, decision и transaction.

Рекомендуемый порядок:

1. target skeleton, source, version plan, editor, performers and assignments;
2. systems, positions, objects, states and stable identities;
3. processes, actions, edges, transitions and general model elements;
4. products, materials and semantic relations;
5. counterparties, contracts, contract items and transfer interfaces;
6. final decision/history reconciliation, snapshot, checks and BPMN/SVG.

Batch не должен содержать FK на ещё не созданную сущность. Нерешённый семантический blocker не закрывается placeholder ID. Допустимо подготовить staging с конфликтами, но такая версия не становится `принято` или `действует`.

### F. Записать и проверить каждый batch

В `migration-write` создать или использовать отдельную staging-книгу v0.2. Перед каждой записью показать полный batch, before/after, source locators, все operations, decision/change rows, preconditions, recovery и `package_hash`. После человеческого подтверждения записать одну transaction, выполнить read-back и checkpoint.

После последнего batch создать итоговое migration decision, связать его с version `migration_decision_id`, разрешить срез и выполнить reconciliation. Принятие и ввод версии остаются отдельными решениями; факт успешного переноса строк не доказывает готовность живого исполнения.

## 0.8. Формат migration dossier

Минимальный сохраняемый артефакт:

~~~yaml
migration_id: "mig-..."
state: assessment|clarification|staging|verification|complete|blocked
source:
  spreadsheet_id: "..."
  title: "..."
  schema_status: v0.1-compatible|v0.1-with-drift|unknown-schema
  revision_or_exported_at: "..."
  content_fingerprint: "sha256:..."
  backup_locator: "..."
target:
  spreadsheet_id: "..."      # null до разрешённого staging
  model_id: "..."
  schema_version: "0.2"
  working_version_id: "..."
editor:
  performer_id: "..."
  display_name: "Имя Фамилия"
  assignment_ids: []
version_plan: []
inventory_by_sheet: []
classification_summary: {}
row_mappings: []
open_questions: []
accepted_local_answers: []
batches: []
transactions: []
reconciliation:
  source_ids: 0
  target_ids: 0
  unresolved_ids: []
  checks: []
next_action: "..."
~~~

`classification_summary` содержит counts всех восьми классов. В `row_mappings` обязательны source locator и объяснение класса. Досье является checkpoint и evidence, но не заменяет строки `Решения` и `Изменения модели` после записи.

## 1. Preconditions

- исходная книга имеет сохранённый content fingerprint и распознанный structural fingerprint v0.1; drift перечислен отдельно;
- сохранена резервная копия исходной книги и spreadsheet ID;
- выбран `model_id` и идентифицирован человек, подтверждающий migration package;
- подтверждён version plan и создана либо подготовлена корневая версия v0.2-миграции со ссылкой на источник v0.1;
- для мигрируемой рабочей модели создана отдельная staging-копия и подтверждено право её изменять;
- целевые листы и колонки построены из `template-schema-v0.2.json`;
- значения рабочей модели не переносятся в публичный шаблон; публичный оригинал используется только как структура для копии.

## 2. Правила преобразования

- строки подтверждённого исходного среза получают `version_id` соответствующей migration version и `version_operation = применить`; разные старые версии или слои не схлопываются без version plan;
- старый `model_layer` переносится в соответствующую `Версии.model_layer`, а не дублируется в строках;
- `next_audit` удаляется из физической строки; следующая проверка планируется внешним операционным контуром;
- каждый FK получает соседний `*_selector`, вычисленный после resolver;
- продукты, материалы, исполнители, контрагенты и contract items получают собственные stable ID;
- старая строка не считается подтверждением правильной идентичности; сомнение помечается `knowledge_status = конфликт`;
- каждый bounded batch журналируется одной transaction, а old/new значения — в `Изменения модели`; итоговое migration decision связывает завершённый набор batch с версией.

## 3. Карта листов

| v0.1 | v0.2 | Операция |
|---|---|---|
| Инструкция | Инструкция | regenerate |
| Система: производственные системы | Система | map + version |
| Система: продукты | Продукты + Связи модели | split |
| Система: словари | JSON enums + validations | regenerate |
| Система: скрытые ID V:AL | selectors + Срез модели | drop/regenerate |
| Система: draw.io dictionaries | PROJECTION-CONTRACT/generator | drop |
| Схема шаблона | Схема шаблона | regenerate from schema |
| Источники | Источники | map |
| Версии | Версии | transform lifecycle |
| Позиции | Позиции | map + version |
| Назначения | Исполнители + Назначения | split/dedupe |
| Процессы | Процессы | map + version |
| Действия | Действия | map + version |
| Связи действий | Связи действий | map + version |
| Объекты | Объекты | map + enrich identity |
| Состояния | Состояния | map + version |
| Переходы | Переходы | map + version |
| Элементы модели: материал | Материалы | split |
| Элементы модели: остальные типы | Элементы модели | map + version |
| Контракты | Контрагенты + Контракты + Позиции контрактов + Интерфейсы передачи | decompose/conflict |
| Связи модели | Связи модели | map + version |
| Проверки | Проверки | regenerate |
| Реестр процессов | Реестр процессов | regenerate |
| Рабочая панель | Рабочая панель | regenerate |
| Диаграммы | Диаграммы | map metadata; do not claim build |
| Проекция draw.io | резервная копия v0.1 | drop from v0.2 |
| — | Решения | create migration decision |
| — | Изменения модели | create append-only log |
| — | Срез модели | resolve |

## 4. Карта колонок

Обозначения: `copy` — прямой перенос; `derive` — детерминированное вычисление; `conflict` — требуется смысловое решение; `drop` — не переносить; `split` — одна старая строка создаёт несколько целевых сущностей.

### Система

| v0.1 | v0.2 | Правило |
|---|---|---|
| system_id | system_id | copy |
| system_name | system_name | copy |
| org_tag | org_tag | copy |
| purpose | purpose | copy |
| owner_position_id | owner_position_id + selector | copy + derive selector |
| current_version_id | Система.current_version_id setting | conflict: должен указывать на `действует` |
| knowledge_status | knowledge_status | copy |
| source_id | source_id + selector | copy + derive selector |
| last_reviewed | last_reviewed | copy |
| next_audit | — | drop |
| active | version_operation | `да → применить`; `нет → conflict`, не считать автоматически `исключить` |

### Встроенные продукты Системы

| v0.1 | v0.2 | Правило |
|---|---|---|
| product_id | Продукты.product_id | copy |
| system_id | Связи модели `система → производит → продукт` | derive relation row |
| product_name | product_name | copy |
| recipient_system_id | — | conflict: внешний получатель становится контрагентом, внутренний остаётся системой |
| recipient_position_id | — | conflict: сохранить только если получатель внутренний |
| recipient_description | Контрагенты.counterparty_name либо notes | conflict |
| acceptance_criteria | acceptance_criteria | copy |
| output_state_id | required_state_id | copy |
| contract_id | Контракты/Позиции контрактов | link after decomposition |
| knowledge_status/source_id/last_reviewed/notes | одноимённые | copy |

### Источники

Все одноимённые поля переносятся. `owner_position_id` получает selector. `url` сохраняется только если разрешено публиковать/переносить ссылку в целевую книгу. `active` остаётся boolean.

### Версии

| v0.1 | v0.2 | Правило |
|---|---|---|
| version_id | version_id | copy |
| system_id | — | drop: модель имеет `model_id`, systems versioned внутри неё |
| version_type | — | drop/conflict: больше не смешивать тип артефакта со статусом версии |
| version_label | version_label | copy |
| model_layer | model_layer | copy |
| version_status | version_status | `черновик/принято/действует` copy; `заменено/выведено → закрыто`; решение о миграции фиксируется отдельно, обязательного классификатора причины нет |
| effective_from | effective_from | copy |
| accepted_by_position_id + acceptance_evidence | accepted_decision_id | conflict: создать решение с конкретным человеком, не только позицией |
| predecessor_version_id | predecessor_version_id | copy; validate chain |
| migration_required | migration_required | copy |
| source_id/notes | одноимённые | copy |
| — | closed_decision_id, successor_version_id, migration_decision_id | derive only from explicit decisions |

### Позиции

Одноимённые поля переносятся. Добавляются `version_id`, `version_operation`, selectors и `source_locator`. `model_layer` не добавляется. `next_audit` удаляется.

### Назначения и Исполнители

| v0.1 | v0.2 | Правило |
|---|---|---|
| performer_name + performer_type | Исполнители.performer_name/type | dedupe by confirmed identity, never by name alone |
| — | performer_id | new stable ID after human confirmation |
| assignment_id | Назначения.assignment_id | copy |
| position_id | position_id + selector | copy + derive selector |
| performer_id | performer_id + selector | link to deduped registry |
| active_from/active_to | одноимённые | copy |
| assignment_status | assignment_status | map `назначен → активно`, `завершён → завершено`, other → conflict |
| source_id/notes | одноимённые | copy |

### Процессы

Прямо переносятся `process_id`, `system_id`, `parent_process_id`, `flow_tag`, `process_name`, `goal`, `work_object_id`, `trigger`, `process_input`, `process_output`, `entry_state_id`, `exit_state_id`, `owner_position_id`, `execution_status`, `knowledge_status`, `source_id`, `last_reviewed`, `notes`. Добавляются version fields и selectors. `produced_product_id` превращается в `Связи модели: процесс/система → создаёт/производит → продукт` после проверки смысла. `model_layer` берётся из версии. `next_audit` удаляется.

### Действия

Все одноимённые поля переносятся с version fields и selectors. `model_layer` удаляется, `next_audit` удаляется. `исполнитель_mode = ИИ-агент` маппится в `AI-агент`. `execution_element_id` разрешается только к типу, допустимому для реализации действия. Материалы из текста входа не извлекаются автоматически.

### Связи действий

Все одноимённые поля переносятся с version fields и selectors. `model_layer` удаляется, `next_audit` удаляется. Для каждой развилки проверяются `condition_text`, `branch_label` и ровно один `is_default`; отсутствие — conflict, а не автозаполнение.

### Объекты

Одноимённые поля переносятся. Добавляются version fields, selectors, `identity_rule`, `creation_event`, `closing_event`. Эти три поля не генерируются из названия: при отсутствии доказательств ставится `conflict`. `next_audit` удаляется.

### Состояния и Переходы

Одноимённые поля переносятся с version fields и selectors. `model_layer` удаляется, `next_audit` удаляется. Переход блокируется, если `from_state_id` и `to_state_id` принадлежат разным объектам. Свободный `condition_text` не переводится в FEEL автоматически.

### Элементы модели и Материалы

| v0.1 | v0.2 | Правило |
|---|---|---|
| element_type = материал | Материалы | split by explicit material identity |
| element_name | material_name | copy |
| definition | purpose | copy if describes use; otherwise conflict |
| formula_or_rule | content_text | copy only when it is actual reusable content |
| unit_or_format | material_type | conflict/map by controlled vocabulary |
| canonical_source_element_id | — | preserve via Связи модели if needed |
| прочие element_type | Элементы модели | copy with version fields/selectors |
| model_layer/next_audit | — | drop |

### Контракты

Старая строка не переносится один-к-одному, потому что смешивает документ, стороны, продукт, интерфейс и приёмку.

| v0.1 | v0.2 | Правило |
|---|---|---|
| contract_id | Контракты.contract_id | copy |
| supplier_system_id/customer_system_id | counterparty_id + direction + internal_system_id | conflict: определить, какая сторона внешняя |
| product_id | Позиции контрактов.product_id | copy |
| delivery_trigger | Интерфейсы передачи.transfer_trigger | copy |
| delivery_format | channel/format_description | split |
| data_package | package_description | copy |
| acceptance_criteria | Продукты.acceptance_criteria или связанное правило | conflict: выбрать владельца истины |
| SLA_element_id | Связи модели `позиция контракта → регулируется → SLA` | derive relation |
| return_or_exception_path | rejection_path/return_path/fallback_path | split/conflict |
| change_authority_position_id | Контракты.change_authority_position_id | copy |
| model_layer | — | drop |
| knowledge/source/review/notes | целевые одноимённые | copy |

Цена и платёжные условия отсутствуют в v0.1 и не выдумываются. Позиция контракта остаётся `conflict`, пока не определены direction, pricing method, currency, unit, billing trigger и payment terms.

### Связи модели

Одноимённые поля переносятся с version fields, selectors, `relation_role`, `required`, `usage_description`, `source_locator`, `last_reviewed`. Старые `потребляет/поставляет` нормализуются только после определения направления контракта; иначе conflict.

### Диаграммы и draw.io

Старые `diagram_id`, `process_id`, `version_id`, `source_id` можно использовать как provenance. `drawio_file_url`, `sync_status`, `generated_fingerprint` и даты не доказывают наличие v0.2 build. Для v0.2 создаются новые `projection_build_id`, `model_fingerprint`, BPMN/SVG hash и readiness. Если build не выполнялся, статус `не готова`; ссылки не переносятся как действующие.

## 5. Postconditions

- target содержит ровно 29 листов в точном порядке;
- исходная v0.1-книга не изменена, её fingerprint и backup locator сохранены;
- все authoring rows имеют version fields и разрешаются в срез;
- старое определение остаётся воспроизводимо через backup/source version;
- в `Исполнители` нет дублей по одному подтверждённому человеку;
- каждый assignment ссылается на performer и position;
- продукты удалены из встроенной зоны `Система` и связаны relation rows;
- материалы вынесены из универсальных элементов;
- внешние системы не созданы без решения;
- контракты декомпозированы, а неизвестные цены не придуманы;
- `Решения` и `Изменения модели` содержат решения и изменения каждого migration batch;
- migration dossier связывает source locators, classifications, packages, transactions и reconciliation;
- `Проекция draw.io` отсутствует;
- все unresolved rows перечислены в migration report и блокируют принятие версии.

## 6. Rollback

Для конкретной рабочей модели rollback означает отклонить staging и продолжить использовать сохранённую v0.1-копию. Публичный шаблон уже выпущен как v0.2; его последующий откат оформляется новым релизом, а manifest и бинарные снимки не переписываются задним числом.
