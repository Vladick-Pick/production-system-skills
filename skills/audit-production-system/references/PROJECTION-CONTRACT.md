# Контракт BPMN/SVG-представлений

Реестр, BPMN, SVG, playbook, исполнительский регламент, обучение и спецификация интерфейса являются представлениями точного `version_id` технологического кита. Каноническая модель первична; производный файл не переписывает её молча.

Архитектурное решение и технические основания зафиксированы в `docs/adr/0001-bpmn-toolchain.md`. Закрытый корпоративный документ правил Camunda не публикуется; этот файл содержит принятую из него операционную норму.

## 1. Два синхронизированных слоя

### Канонический слой

Содержит систему, позиции, продукты, процессы, действия, объекты, состояния, материалы, информационные системы, контракты и связи. Он отвечает, что существует и как работает система.

### BPMN-проекция

Содержит pool, lanes, tasks, events, gateways и sequence flows. Она отвечает, как выбранный процесс читается и при достаточной реализации исполняется в Camunda.

Синхронизация односторонняя:

~~~text
подтверждённая модель выбранной версии
→ разрешённый срез
→ projection IR
→ BPMN + SVG
~~~

Ручная правка BPMN создаёт change proposal к модели. Обратный импорт без семантического допуска запрещён.

## 2. Build manifest

Каждая сборка содержит:

- `projection_build_id`;
- `projection_kind`;
- `process_id` и `version_id`;
- `model_fingerprint` canonical JSON IR;
- версию генератора и layout algorithm;
- дату сборки для журнала, но не внутри детерминированных bytes;
- включённые stable IDs и source row keys;
- неполное покрытие и deployment blockers;
- sha256 BPMN и SVG;
- readiness status.

BPMN и SVG одной сборки должны происходить из одного IR и иметь один model fingerprint. Временные метки не должны менять байты повторной сборки одинакового IR.

## 3. Допустимые элементы v0.2

- один participant/pool внутренней системы;
- lanes ответственных позиций;
- user task;
- service task;
- manual task только при явно не поддерживаемой системой ручной работе;
- send/receive task только при явном интерфейсе передачи;
- call activity или embedded subprocess по правилу ADR;
- none start/end events;
- message, timer, error events только при явном типе и параметрах;
- exclusive gateway с FEEL/default;
- parallel split/join;
- sequence flows.

Пока запрещены inclusive/event-based gateways, внешние pools, message flows, visual data objects, associations, artifacts, compensation и произвольные modifiers.

## 4. Правила отображения

### Pool и lanes

Одна BPMN-схема процесса использует один pool моделируемой системы. Lane определяется `position_id`; подпись берётся из разрешённого selector. Действие размещается в lane ответственной позиции.

Информационная система не становится ответственной lane автоматически. Её ID записывается в properties действия. Отдельная system lane допустима только для явно запрошенной технической проекции и маркируется как среда исполнения.

### Действия

Название — операционный глагол + объект/результат. Действие человека, поддерживаемое системой, — user task. Автоматизация/AI — service task. Реализация выбирается из явных полей модели; генератор не угадывает job type, form, assignee или candidate group.

Человеческое решение отображается user task, после которого exclusive gateway маршрутизирует уже зафиксированный результат. Gateway не подменяет действие принятия решения.

Связанный самостоятельный процесс становится call activity только при известном `linked_process_id`. Локальная группировка становится embedded subprocess и имеет один none start.

### События

Обычный trigger создаёт none start. Message/timer start или intermediate event разрешён только когда модель содержит корреляцию сообщения либо timer definition. End event соответствует явному завершению ветки; разные бизнес-исходы получают разные подписи.

### Gateways и потоки

Exclusive gateway имеет условия на всех исходящих flows кроме ровно одного default. Условие для deployment — FEEL, возвращающий boolean. Если условие дано только естественным языком, build не deployment-ready.

Parallel gateway создаётся только из явной семантики одновременности и имеет согласованную пару split/join. Несколько исходящих стрелок сами по себе не доказывают параллельность.

Каждый sequence flow трассируется к `edge_id`. Возврат и исключение остаются sequence flows в ограниченной нотации, но сохраняют relation metadata и читаемую подпись.

### Материалы, продукты и данные

В v0.2 они сохраняются как properties связанных tasks и в manifest coverage. Визуальные data objects и associations не генерируются. Это не теряет связь: stable ID остаётся в IR и BPMN extension metadata.

## 5. Stable IDs

- participant → `system_id`;
- process → `process_id`;
- lane → `position_id`;
- task/call activity → `action_id`;
- sequence flow → `edge_id`;
- gateway → детерминированный ID решения/условия и его исходящих edges;
- events → детерминированный ID `start/end::<process_id>::<outcome>`;
- version/build → `version_id`, `projection_build_id`.

Канонические значения записываются в `modeler:properties`. XML ID выводится детерминированно и остаётся XML-safe. Геометрия не меняет идентичность.

## 6. Readiness и validation

### Готова к просмотру

- выбранный snapshot разрешён без ошибок;
- есть start, хотя бы один достижимый end и связный граф;
- actions/edges/lanes разрешаются по stable ID;
- unsupported элементы отсутствуют;
- BPMN XML парсится, references и DI целостны;
- SVG построен из того же IR;
- повторная сборка даёт те же bytes и hashes.

### Готова к deployment

Дополнительно:

- `isExecutable=true`;
- user tasks используют рекомендованную Camunda user task implementation;
- service/send tasks имеют `zeebe:taskDefinition type`;
- call activities имеют process ID и binding;
- FEEL conditions определены, а exclusive default ровно один;
- forms, assignments, variables и worker contracts заданы там, где обязательны;
- target Camunda version определена;
- актуальный Desktop Modeler или эквивалентный зафиксированный lint не выдаёт блокирующих ошибок.

Отсутствие Modeler в среде фиксируется как непроверенный внешний gate; внутренний XML validator не выдаётся за Modeler validation.

## 7. Актуальность

Представление устарело, если:

- его `version_id` не соответствует заявленной версии;
- изменился любой включённый элемент или relation;
- `model_fingerprint` не совпадает с текущим IR;
- BPMN и SVG относятся к разным build;
- отсутствуют исходные stable IDs;
- из схемы выпали ветки, исключения, возвраты, полномочия или приёмка;
- deployment environment использует другой artifact hash.

Представление принятой, но не действующей версии маркируется предварительным. Оно не подменяет действующие материалы.

## 8. Направление изменения

~~~text
изменить модель
→ принять версию
→ пересобрать BPMN/SVG
→ проверить view/deployment readiness
→ ввести версию
→ отдельно deploy при наличии разрешения
~~~

## 9. Ответственность четырёх скиллов

- `model-production-system` создаёт projection-ready IDs, actions, lanes и flows;
- `maintain-production-system` пересобирает затронутые builds после подтверждённого изменения и не объявляет их действующими до ввода;
- `audit-production-system` сравнивает build manifest, BPMN и SVG с точным snapshot и readiness evidence;
- `resolve-model-element` показывает projection impact, но не распространяет определение до mutation transaction.

## 10. Хранение

Минимальный v0.2 хранит `.bpmn`, `.svg` и build manifest как обычные файлы/URL. Интерактивное хранилище и round-trip editing отложены. Лист `Диаграммы` хранит lineage и ссылки, но не BPMN XML и не SVG bytes.
