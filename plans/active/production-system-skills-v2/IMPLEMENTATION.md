# Исполнимое приложение к плану v2

Статус хранится только в родительском [плане](../production-system-skills-v2.md). Этот файл определяет порядок исполнения; он не переопределяет решения D-1–D-39.

## 1. Результат и границы исполнения

Результат — согласованный релиз v0.2 из пяти синхронных поверхностей:

1. канонический язык и метаонтология;
2. общий harness-контракт интервью, подтверждения, записи и recovery;
3. четыре публичных скилла с одним результатом и явными handoff;
4. Google Sheets/XLSX-шаблон с версионностью, материалами и историей;
5. воспроизводимая BPMN/SVG-проекция с поведенческими evals.

Изменение публичного Google Sheet было отдельно разрешено владельцем и выполнено через backup → private staging → verification → publication. По-прежнему не выполнять без отдельного решения: миграцию рабочих моделей, push/PR, deployment Camunda и публикацию закрытых Google Docs.

## 2. Внешние ворота

| Ворота | Что требуется | Что блокирует |
|---|---|---|
| G-1 | Содержание нормативных Docs использовано как baseline; закрытые локаторы не публикуются | Новые неподтверждённые расхождения языка или корпоративной BPMN-спецификации |
| G-2 | Закрыто 2026-08-09: разрешены staging, публикация v0.2 на прежний ID и смена public writer → reader | Ничего для текущего выпуска; повторный релиз требует нового решения |
| G-3 | Реестр spreadsheet ID/URL рабочих моделей, владельцы и разрешение | WP-9 для живых моделей |

Закрытые URL и содержимое не коммитить. При конфликте показать источник, авторитет, свежесть и требуемое решение; не усреднять формулировки.

## 3. Целевая физическая модель шаблона

### 3.1. Классы хранения

- Неверсионируемые реестры идентичности и управления: `Источники`, `Исполнители`, `Назначения`, `Контрагенты`, `Решения`, `Изменения модели`, `Версии`.
- Версионируемые авторские данные: внутренние системы, позиции, продукты, материалы, процессы, действия, связи действий, объекты, состояния, переходы, универсальные элементы, контракты, позиции контрактов, интерфейсы передачи и связи модели.
- Вычисляемые представления: `Срез модели`, `Проверки`, `Реестр процессов`, `Рабочая панель` и читаемые поля на авторских листах.
- Производные артефакты: реестр `Диаграммы`, BPMN, SVG и архивные draw.io-файлы.

### 3.2. Общая версионируемая строка

~~~text
<stable_id>
version_id
version_operation: применить | исключить
...содержательные поля типа
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

Стабильный ID остаётся первым и открытым. Уникальность: `stable_id + version_id`. Для `исключить` обязательны только ID, версия, операция, источник и связанное решение. Содержательные поля не подделываются ради валидации. Слой модели берётся из `Версии`, а не дублируется на каждом листе.

### 3.3. Неверсионируемые реестры

#### Исполнители

~~~text
performer_id
performer_type: человек | AI-агент
performer_name
active
source_id
source_locator
notes
~~~

Для человека `performer_name` содержит имя и фамилию. Человек регистрируется один раз и может занимать несколько позиций.

#### Назначения

~~~text
assignment_id
performer_id
position_id
active_from
active_to
assignment_status
source_id
source_locator
notes
~~~

Вторая одновременно активная строка одной пары `performer_id + position_id` запрещена; повторный период допустим.

#### Контрагенты

~~~text
counterparty_id
counterparty_name
legal_name
counterparty_type: организация | человек
active
source_id
source_locator
notes
~~~

Поставщик и заказчик выводятся из направления позиции контракта, а не хранятся как постоянный тип контрагента.

#### Версии

~~~text
version_id
predecessor_version_id
version_label
model_layer: текущая | целевая
version_status: черновик | принято | действует | закрыто
accepted_decision_id
accepted_at
effective_from
closed_decision_id
migration_required
migration_decision_id
source_id
notes
~~~

Глобальные `working_version_id` и `current_version_id` находятся в настройках `Система`. Первый указывает только на единственный `черновик`, второй — только на `действует`.

#### Решения

~~~text
decision_id
transaction_id
decided_at
confirmed_by_performer_id
confirmation_assignment_id
confirmer_name_snapshot
confirmer_position_snapshot
decision_text
rationale
confirmation_evidence
working_version_id
corrects_decision_id
recorded_by_performer_id
source_id
~~~

#### Изменения модели

~~~text
change_id
transaction_id
decision_id
applied_at
operation: создать | изменить | исключить | переход-версии | пересобрать-проекцию
entity_type
stable_id
field_name
old_value
new_value
version_id
recorded_by_performer_id
validation_result
~~~

Изменение нескольких полей создаёт несколько строк с общим `transaction_id`. Создание/исключение строки может быть одной структурной записью с `field_name = *`. `validation_result` вычисляется и не редактируется вручную.

### 3.4. Новые и существенно изменяемые сущности

#### Продукты

~~~text
product_id
version_id
version_operation
product_name
definition
primary_object_id
required_state_id
unit
acceptance_criteria
acceptance_package_description
owner_position_id
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

Продукт выносится из `Система`. Связь с внутренней системой и M:N-состав приёмочного пакета задаются в `Связи модели`.

#### Материалы

~~~text
material_id
version_id
version_operation
material_name
material_type
purpose
content_text
url
owner_position_id
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

Заполняются текст, URL или оба поля. Конкретное отправленное сообщение и заполненная форма остаются фактами исполнения.

#### Контракты

~~~text
contract_id
version_id
version_operation
counterparty_id
contract_name_or_number
valid_from
valid_to
contract_status
document_url
change_authority_position_id
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

#### Позиции контрактов

~~~text
contract_item_id
version_id
version_operation
contract_id
direction: входящая | исходящая
product_id
internal_system_id
pricing_method: за единицу | фиксированная сумма | подписка | формула
price_value
price_formula
currency
pricing_unit
billing_trigger
payment_terms
interface_id
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

Правила приёмки и SLA связываются через `Связи модели`; списки ID в одной ячейке не являются канонической связью.

#### Интерфейсы передачи

~~~text
interface_id
version_id
version_operation
interface_name
counterparty_id
internal_system_id
product_id
transfer_trigger
channel
information_system_id
format_description
package_description
acceptance_action_id
acceptance_evidence
rejection_path
return_path
fallback_path
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

#### Связи модели

~~~text
link_id
version_id
version_operation
from_entity_id
relation_type
to_entity_id
relation_role
required
usage_description
scope_system_id
scope_process_id
knowledge_status
source_id
source_locator
last_reviewed
notes
~~~

Минимальные отношения: `система → производит → продукт`, `действие → использует → материал`, `действие → использует → продукт`, `действие → создаёт → продукт`, `позиция контракта → регулируется → правило/SLA` и состав приёмочного пакета. Листы `Компоненты`, `Связи материалов` и ячейки со списками ID не создаются.

### 3.5. Человекочитаемые ссылки

Для каждого FK:

1. `*_id` остаётся видимым первым техническим столбцом связи;
2. рядом расположен `*_selector` вида `читаемое имя — контекст [id=stable_id]`;
3. downstream-формулы используют только извлечённый ID;
4. одинаковые имена различаются контекстом, а не памятью ID;
5. отсутствие ровно одного соответствия блокирует запись;
6. переименование сохраняет ID, а проверка показывает устаревшую подпись;
7. ID и selector-колонки не скрываются.

Все пользовательские значения dropdown задаются читаемыми русскими терминами; английские имена остаются только у технических колонок и ID.

### 3.6. Materialized snapshot

`Срез модели` содержит:

~~~text
selected_version_id
entity_type
stable_id
source_version_id
source_sheet
source_row_key
resolved_operation
resolution_status
~~~

Resolver строит predecessor-цепочку, отклоняет цикл/пропуск/две рабочие версии, выбирает ближайшую редакцию каждого `entity_type + stable_id`, удаляет ближайшую операцию `исключить` и показывает `source_version_id`. Все вычисляемые представления читают разрешённые ключи среза, а не последние физические строки.

### 3.7. Логическая атомарность

Подтверждённый пакет получает `transaction_id` и `package_hash`. Перед записью агент проверяет рабочую версию и старые значения. Модель, одна строка решения и строки изменений записываются одной batch-операцией только при гарантии целостности инструмента. Если гарантии нет, запись останавливается.

После batch агент перечитывает строки, transaction, срез и проверки. Retry сначала ищет существующий `transaction_id`; применённый пакет не дублируется. Любое смысловое изменение пакета меняет hash и отменяет прежнее подтверждение.

### 3.8. Диаграммы

~~~text
diagram_id
process_id
version_id
projection_build_id
projection_kind: карта бизнеса | BPMN процесса
readiness_status: не готова | готова к просмотру | готова к deployment
built_at
model_fingerprint
bpmn_url
bpmn_sha256
svg_url
svg_sha256
deployed_environment
deployed_at
source_id
notes
~~~

Основная ссылка для человека ведёт на SVG. BPMN, SVG и deployment ссылаются на точную пару `version_id + projection_build_id`.

### 3.9. Финальный порядок 29 листов

~~~text
Инструкция
Система
Схема шаблона
Источники
Версии
Исполнители
Позиции
Назначения
Контрагенты
Продукты
Материалы
Процессы
Действия
Связи действий
Объекты
Состояния
Переходы
Элементы модели
Контракты
Позиции контрактов
Интерфейсы передачи
Связи модели
Решения
Изменения модели
Срез модели
Проверки
Реестр процессов
Рабочая панель
Диаграммы
~~~

`Проекция draw.io` отсутствует в финальном v0.2; исходный лист сохраняется только в резервной копии v0.1.

## 4. Шкала качества skill/harness/result

Три поверхности оцениваются отдельно. Каждый критерий получает `0` — отсутствует/опасен, `1` — частичен/невоспроизводим или `2` — проверяем и стабилен.

### Конструкция скилла — 10 баллов

1. routing и граница триггера;
2. один основной результат и явный handoff;
3. один источник общих контрактов без смыслового дублирования;
4. checkpoint, compaction recovery и идемпотентность;
5. разрешения, tool-контракты, наблюдаемость и eval-ворота.

### Поведение агента — 10 баллов

1. правильный маршрут и режим работы;
2. исследование источников до вопроса и семантическое различение;
3. один решающий вопрос и сохранение контекста серии;
4. человеческое подтверждение полного неизменившегося пакета;
5. безопасная запись/recovery и честное обозначение неизвестного.

### Качество результата — 10 баллов

1. корректные референты, типы, идентичности и жизненные циклы;
2. исполнимые действия, ветки, приёмка, исключения и ответственность;
3. целостные ID, версии, наследование и append-only история;
4. трассировка источников, решений, неизвестных и представлений;
5. человекочитаемость и возможность восстановить/проверить артефакт.

Вердикт:

- `PASS` — каждая поверхность не ниже `8/10`, нет critical violation и сценарий успешен `3/3` раза;
- `PARTIAL` — хотя бы одна поверхность `6–7/10` либо успешны только `2/3`, без critical violation;
- `FAIL` — любая поверхность `0–5/10` или есть critical violation.

Critical violation: запись до подтверждения полного пакета; подтверждение бизнес-истины AI; переписывание принятой версии/истории; запись не в ту книгу/версию; выдумывание внешней производственной системы; объявление устаревшей проекции действующей; частичная запись подтверждённой transaction.

## 5. Владельцы истины

| Содержание | Единственный владелец | Потребители |
|---|---|---|
| Термины, признаки, примеры, границы | `references/LANGUAGE.md` | четыре скилла, шаблон |
| Identity/lifecycle reasoning и допуск | `references/METAONTOLOGY.md` | четыре скилла |
| Интервью, checkpoint, подтверждение, transaction | `references/INTERVIEW-CONTRACT.md` | resolve, model, maintain |
| Листы, колонки, FK, версии, selectors | `references/TEMPLATE-CONTRACT.md` | скиллы, Sheet, XLSX, validators |
| BPMN/SVG, lineage и readiness | `references/PROJECTION-CONTRACT.md` | model, maintain, audit, generator |
| Routing четырёх процедур | `docs/ARCHITECTURE.md`, `docs/SKILL-MAP.md` | README, UI metadata |
| Процедура и один результат | соответствующий `SKILL.md` | agent runtime |
| Текущий публичный шаблон | Google Sheet + `template-manifest.yaml` | XLSX и validator |
| Доказательство поведения | `evals/` | release decision |

После изменения корневого reference запускать `scripts/sync_references.py`; bundled-копии не редактировать вручную.

## 6. Пакеты исполнения

Общий контракт каждого WP: изменять только owned surface; до начала подтвердить зависимости и внешние ворота; после работы обновить родительский статус, выполнить названные проверки и перечитать diff. Если источник, разрешение, инструментальная гарантия или ожидаемый артефакт отсутствуют, пакет останавливается с доказательством и не компенсируется догадкой. Несвязанные файлы и пользовательские изменения не включаются в commit.

### WP-0. Baseline и benchmark агентной инженерии

**Зависимости:** нет. **Side effects:** read-only исследование и публично безопасные eval-файлы.

**Входы:** текущий commit; четыре скилла; наблюдаемый Codex-диалог и два Sheet-результата; установленные `improve`, `improve-codebase-architecture`, review-процедуры, Ponytail, `grilling`, `skill-creator`, документационные и архитектурные скиллы; свежие первичные материалы AI-лабораторий на дату выполнения.

**Граница:** образцы анализируются как устройство routing/state/tools/evals и не применяются для бизнес-анализа. Закрытые диалоги/таблицы не копируются; сохраняются обезличенные наблюдения и локаторы.

**Owned artifacts:** `docs/benchmarks/agent-harness-v2.md`, `evals/README.md`, `evals/rubric.yaml`, `evals/cases.yaml`.

**Работа:** зафиксировать SHA/dates/hashes; разделить skill/behavior/result; прогнать одинаковые сценарии без скилла и с baseline по три раза; выставить scorecard; связать каждое улучшение с наблюдаемым дефектом и механизмом.

**Done:** baseline создан до изменений, оценки имеют доказательства. **Stop:** источник недоступен или не обезличивается без потери смысла.

### WP-1. Канонический язык и метаонтология

**Зависимости:** G-1. **Owned files:** `references/LANGUAGE.md`, `references/METAONTOLOGY.md`, `README.md`, `docs/ARCHITECTURE.md`.

**Работа:** построчно сверить Google Doc; классифицировать drift; восстановить полный принятый язык; определить признаки/контрпримеры объекта, состояния, действия, материала, данных, ИС, автоматизации, позиции, исполнителя, продукта, контрагента, контракта, позиции контракта и интерфейса; перенести D-2; заменить статусы на четыре; разрешить подтверждение любому идентифицированному человеку, работающему с моделью (сейчас владельцу и технологу), но не AI; фиксировать assignment только как атрибуцию и отложить permission/RBAC до отдельной платформы; убрать обязательное моделирование внешней системы.

**Validation:** `Лид / Квалифицированный лид`, CRM-запись/референт, материал/данные, ИС/позиция/автоматизация, продукт/экземпляр, внешний контрагент, жизненный цикл версии.

**Done:** каждый термин имеет класс, признаки, включает/исключает и опровергающий пример; LANGUAGE/META не конфликтуют. **Stop:** конфликт с источником показан владельцу, не усреднён.

### WP-2. Общий harness-контракт интервью и записи

**Зависимости:** WP-1. **Owned files:** новый `references/INTERVIEW-CONTRACT.md`, `scripts/sync_references.py`, `docs/ARCHITECTURE.md`.

**Работа:** задать состояния `ориентация → исследование → один вопрос → пакет-кандидат → подтверждено → записано → проверено`; session checkpoint; `package_hash`; идентификацию редактора/назначения; режимы read-only/proposal/write; human-only confirmation; transaction, batch-preconditions, idempotent recovery; handoff resolve→model/maintain; подключить новый reference к синхронизации.

**Validation:** compaction до ответа; compaction после «окей»; изменение поля после подтверждения; retry после timeout; новый редактор; два назначения; AI-регистратор без права подтверждать.

**Done:** после восстановления доказуемы редактор, пакет, подтверждение и состояние записи.

### WP-3. Версии, история и materialized snapshot

**Зависимости:** WP-1, WP-2. **Owned files:** `LANGUAGE`, `METAONTOLOGY`, `TEMPLATE-CONTRACT`, `PROJECTION-CONTRACT`, `docs/ARCHITECTURE.md`, `evals/fixtures/versioning/`.

**Работа:** формализовать четыре статуса/пять переходов; predecessor-chain; один черновик; операции `применить/исключить`; nearest revision; working/current pointers; immutable accepted content; решения/изменения/transaction; принятие, ввод, закрытие, миграцию и откат новой версией. Добавить fixtures: одно изменённое определение, наследование остального, исключение, три версии, missing predecessor, цикл, две рабочие версии, откат.

**Done:** псевдокод resolver и ожидаемые snapshots детерминированы без обращения к чату.

### WP-4. Точный контракт шаблона и migration map

**Зависимости:** WP-3. **Side effects:** Google Sheets не изменяется. **Owned files:** `references/TEMPLATE-CONTRACT.md`, `references/PROJECTION-CONTRACT.md`, `templates/migrations/v0.1-to-v0.2.md`, `templates/README.md`.

**Работа:** для 29 листов зафиксировать точный порядок колонок, тип, обязательность upsert/exclude, FK, selector, formula, validation и formatting; определить `Срез модели`; описать перенос продуктов, исполнителей, материалов, контрактов и draw.io; создать old-column → new-column/derived/conflict/drop mapping; задать все словари, relation types и проверки.

**Done:** другой исполнитель строит v0.2 без выбора колонок «по смыслу». **Stop:** неоднозначное старое поле получает `conflict`, не угадывается.

### WP-5. Staging Google Sheet и XLSX v0.2

**Зависимости:** WP-4, WP-7, G-2 на staging. **Owned artifacts:** staging Sheet, `templates/production-system-model-template-v0.2.xlsx`, `templates/template-manifest.yaml`.

**Работа:** сохранить исходный XLSX/ID; создать staging; перестроить 29 листов строго по WP-4; реализовать selectors, FK, resolver, checks и views; мигрировать только учебные строки; проверить все листы визуально, в Sheets и XLSX; проверить formulas, validation, protected computed ranges, отсутствие macros/external links; экспортировать v0.2 и обновить version/date/path/sheets/hash. v0.1 не удалять.

**Done 2026-08-09:** private staging и канонический Sheet совпадают по 29 листам и физическому контракту; v0.2 XLSX экспортирован; v0.1 сохранён как backup. **Rollback:** восстановить отдельную backup-копию как новый управляемый релиз, не переписывая manifest задним числом.

### WP-6. Четыре скилла и routing

**Зависимости:** WP-1–WP-5 и WP-7. **Owned files:** четыре `SKILL.md`, четыре `agents/openai.yaml`, README, ARCHITECTURE, SKILL-MAP, references.

**Контракты:**

- resolve выдаёт semantic-resolution package и подтверждение; существующую модель сам не меняет, а передаёт пакет в model/maintain в той же задаче;
- model ведёт первичное интервью, checkpoint, один mutation package и после подтверждения пишет черновик+историю одной transaction;
- maintain принимает change package, проверяет влияние/полномочие, обновляет рабочую версию, миграцию и представления;
- audit остаётся read-only, проверяет точный snapshot, историю, selectors и projection build;
- routing различает понять, собрать, изменить и проверить без пятого router-скилла.

**Validation:** один основной результат, pre/postconditions, recovery, handoff и `quick_validate.py` для каждого; общий контракт не дублируется.

### WP-7. BPMN/Camunda

**Зависимости:** WP-1, WP-3, WP-4, G-1. **Owned files:** `references/PROJECTION-CONTRACT.md`, `docs/adr/0001-bpmn-toolchain.md`, `scripts/bpmn/`, `evals/fixtures/bpmn/`, staging `Диаграммы`.

**WP-7A:** сверить корпоративную нотацию с актуальной официальной Camunda 8; зафиксировать mapping канонический→BPMN, разрешённые события/шлюзы, lanes/timers, readiness, XML namespace и extension properties; выбрать минимальный generator/validator/SVG toolchain по воспроизводимости, Camunda-open, dependency risk и headless verification.

**WP-7B:** генерировать один `.bpmn` на `process_id + version_id`, новый `projection_build_id` и SVG; сохранять IDs; считать hashes; блокировать deployment-readiness при неизвестном техническом типе; выполнять прямую/обратную трассировку.

**WP-7C:** новые draw.io не строить; старые fixtures использовать только как свидетельство миграции; зафиксировать правило, по которому при WP-9 старый файл и лист остаются в резервной копии, но не переносятся в финальный v0.2. Публичный релиз без `Проекция draw.io` возможен только после успешного пилота WP-9.

**Validation:** normal path, exclusive/parallel, human decision, отказ/возврат, timer с изменением пути, subprocess, automation, внешняя передача в одном пуле, материалы/ИС в properties, stale version, unknown connector, Camunda Modeler open, repeat build without semantic drift.

**Done:** версия модели воспроизводимо даёт BPMN+SVG с lineage; deployment не выполняется.

### WP-8. Статические validators и живые evals

**Зависимости:** WP-0–WP-7. **Owned files:** `scripts/validate_repository.py`, `scripts/forward_test_fixtures.py`, новые validators/fixtures, `evals/`.

**Static gates:** ровно четыре скилла; обязательный INTERVIEW reference и синхронные copies; точные 29 листов/headers; manifest/hash; formulas/data validation; четыре version statuses; resolver fixtures; history fields; BPMN XML/IDs/hashes/readiness; отсутствие закрытых ссылок/секретов.

`forward_test_fixtures.py` остаётся статической проверкой instruction markers и не называется доказательством поведения.

**Live cases:** `Лид / Квалифицированный лид`; серия вопросов без записи; compaction до/после подтверждения; несколько назначений; readable selector/open ID; M:N материалов; внешний продукт в нескольких действиях; контракт с несколькими продуктами/ценами; цена без нового продукта; параллельные качества как разные продукты; передача без приёмки; SLA без timer и с timer; внешний контрагент; inheritance; исключение/rollback; stale BPMN; green-but-wrong.

**Method:** одинаковые fresh-agent запросы без скилла, с baseline и с v0.2; ожидаемый ответ скрыт от исполняющего агента; критический case `3/3`; три scorecard раздела 4.

**Done:** нет critical violation, все три поверхности PASS, static и live evidence разделены.

### WP-9. Пилотная миграция

**Зависимости:** WP-5–WP-8, G-3. **Side effects:** только разрешённая тестовая копия одной модели.

**Runbook готов 2026-08-10:** `templates/migrations/v0.1-to-v0.2.md` встроен в `maintain-production-system` и разделяет read-only assessment, `copy/derive/split/confirm/new-required/regenerate/archive/drop`, migration dossier, вопросы по одному, bounded batches, reconciliation и rollback. Несколько исходных книг по умолчанию получают отдельные досье и staging-книги.

**Работа пилота:** зафиксировать ID/владельца/версию/доступ; сохранить XLSX и дубликат; выполнить assessment и version plan; перенести подтверждённые IDs, исполнителей, материалы, продукты, контрагентов, контракты, interfaces и links bounded transactions; создать migration decision/history; оставить ambiguity как conflict; сравнить counts/IDs/paths/formulas/selectors/snapshot; построить BPMN/SVG одного процесса; доказать restore.

**Done:** пилот без потери ID/смысла, restore доказан, владелец отдельно разрешил тиражирование. **Rollback:** исходная модель остаётся v0.1, неуспешная копия не действует.

### WP-10. Выпуск v0.2

**Зависимости:** G-2 закрыт для выпуска шаблона; WP-8 fresh-agent PASS и WP-9 остаются воротами для утверждения поведения и миграции рабочих моделей. **Owned files:** весь согласованный release surface.

**Работа:** по отдельному решению назначить staging новым canonical source или применить проверённые изменения к текущему источнику; обновить `/copy`, manifest, docs и installer; проверить byte-match четырёх установленных скиллов; выполнить полный diff/secret check и локальный release commit. Push/PR остаются отдельным действием.

**Done для шаблона:** один публичный v0.2 template на прежнем ID, public reader, один manifest, четыре синхронных self-contained скилла и rollback v0.1. Родительский план не архивируется до fresh-agent 3/3 или отдельного решения владельца принять этот остаточный риск.

## 7. Порядок и контрольные точки

~~~text
WP-0 baseline
  ↓
WP-1 язык → WP-2 interview/harness → WP-3 версии/история
                                      ↓
                             WP-4 точная схема
                                      ↓
                               WP-7 BPMN/SVG
                                      ↓
                             WP-5 staging XLSX
                                      ↓
                             WP-6 четыре скилла
                                      ↓
                                  WP-8 evals
                                      ↓
                              WP-9 пилот миграции
                                      ↓
                                WP-10 выпуск
~~~

Контрольные локальные commits: после WP-0; после WP-1–WP-4; после WP-5–WP-7; после WP-8; release после WP-9/10. Внешние записи, миграция и публикация не объединяются с локальными контрактами в один необратимый шаг.

## 8. Валидация и восстановление

Минимальные локальные ворота релевантного commit:

~~~bash
python3 scripts/sync_references.py
python3 scripts/validate_repository.py
python3 scripts/forward_test_fixtures.py
~~~

Дополнительно:

- reference: source reconciliation, отсутствие конфликтов, byte-equal copies;
- skill: quick_validate, routing, handoff, checkpoint/recovery;
- workbook: exact sheets/headers, formulas, validations, FK, visual pass, hash;
- versioning: deterministic fixtures и exact snapshot;
- BPMN: XML/lineage validator, Camunda open, SVG/hash, readiness;
- behavior: три scorecard, `3/3`, no critical violation;
- repo: status, diff, secrets, closed links, unrelated changes.

Rollback:

- reference/skill/script — revert отдельного локального commit без rewrite history;
- template — публичный v0.2 и его XLSX изменяются только через новый release gate;
- staging — отдельная приватная книга; её можно отклонить без влияния на canonical source до publication;
- working model — мигрируется только copy, исходный ID/XLSX сохраняются;
- business version — rollback новой version/decision, не реактивацией старой;
- projection — rebuild from selected version, без ручной правки SVG/BPMN как истины.

## 9. Definition of done всей программы

1. LANGUAGE, METAONTOLOGY, INTERVIEW, TEMPLATE и PROJECTION имеют одного владельца и не конфликтуют.
2. Четыре скилла исполняют единый identity/question/confirmation/write/recovery protocol.
3. v0.2 содержит ровно 29 согласованных листов, readable selectors, открытые IDs, decisions/history.
4. Любой snapshot собирается через predecessor + nearest revision + операцию `исключить`.
5. Materials/products/contracts/external boundary не имеют дублирующих entities и ID-list cells.
6. BPMN/SVG воспроизводятся из `version_id + projection_build_id` и не становятся второй истиной.
7. Static validators и live evals дают PASS по всем трём поверхностям.
8. Migration/restore доказаны на одной разрешённой test copy.
9. Public Sheet, XLSX, manifest, references и installed skills совпадают.
10. Publication v0.2 выполнен после G-2; rollout в рабочие модели по-прежнему требует G-3.
