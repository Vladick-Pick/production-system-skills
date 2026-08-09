# ADR-0001: Детерминированная BPMN/SVG-проекция для Camunda 8

- Статус: принято для реализации v0.2
- Дата: 2026-08-09
- Область: `PROJECTION-CONTRACT.md`, генератор, validator, лист `Диаграммы`

## Контекст

v0.1 хранит отдельную вычисляемую проекцию draw.io. Она создаёт конкурирующую модель геометрии, не гарантирует одинаковое происхождение картинки и исполнимого файла и позволяет зелёной структурной проверке сосуществовать с отсутствующей схемой.

Владелец принял два слоя:

1. каноническая модель производственной системы — объекты, состояния, действия, материалы, системы, продукты и контракты;
2. BPMN-проекция — pool, lanes, tasks, events, gateways и sequence flows для Camunda.

Предоставленный владельцем документ «Правила моделирования обычной схемы процесса в Camunda» проверен 2026-08-09 и используется как корпоративная визуальная норма без публикации закрытой ссылки. Для технического исполнения проверены актуальные первичные документы Camunda 8.9:

- [BPMN primer и XML namespaces](https://docs.camunda.io/docs/components/modeler/bpmn/bpmn-primer/);
- [BPMN coverage](https://docs.camunda.io/docs/components/modeler/bpmn/bpmn-coverage/);
- [User tasks](https://docs.camunda.io/docs/components/modeler/bpmn/user-tasks/);
- [Service tasks](https://docs.camunda.io/docs/components/modeler/bpmn/service-tasks/);
- [Exclusive gateways и default flow](https://docs.camunda.io/docs/components/modeler/bpmn/exclusive-gateways/);
- [Parallel gateways](https://docs.camunda.io/docs/8.8/components/modeler/bpmn/parallel-gateways/);
- [Events](https://docs.camunda.io/docs/components/modeler/bpmn/events/);
- [Embedded subprocess](https://docs.camunda.io/docs/components/modeler/bpmn/embedded-subprocesses/);
- [Call activities](https://docs.camunda.io/docs/components/modeler/bpmn/call-activities/);
- [FEEL](https://docs.camunda.io/docs/components/modeler/feel/what-is-feel/);
- [Desktop Modeler и lint validation](https://docs.camunda.io/docs/components/modeler/desktop-modeler/).

Технические возможности Camunda шире корпоративного словаря. Наличие поддерживаемого BPMN-элемента не разрешает использовать его без принятого правила отображения.

## Варианты

### A. Оставить draw.io канонической проекцией

Плюс: минимум изменений. Минусы: отдельная геометрическая модель, нет исполнимого BPMN, слабая трассировка и невозможность доказать, что картинка соответствует deployment-файлу.

### B. Редактировать BPMN вручную в Desktop Modeler

Плюс: нативный Camunda UX. Минусы: ручная схема становится вторым источником истины; изменения stable ID, версий и представлений расходятся; агент не может воспроизводимо пересобрать результат.

### C. Каноническая модель → разрешённый IR → BPMN и SVG

Плюс: один snapshot и один fingerprint порождают оба артефакта; возможны детерминированные проверки, повторная сборка, version/build lineage и отдельный deployment gate. Минус: нужен собственный ограниченный генератор и validator.

## Решение

Выбран вариант C.

~~~text
authoring rows
→ resolver(version_id)
→ materialized snapshot
→ projection IR
→ ┬→ process.bpmn
  └→ process.svg
→ hashes + build manifest
→ Диаграммы
~~~

IR является промежуточным результатом сборки, а не новым авторским реестром. Он содержит только разрешённые элементы выбранного `version_id`, stable IDs, labels, lanes, flow semantics, implementation metadata и source row keys. BPMN и SVG обязаны иметь один `model_fingerprint`.

## Каноническое отображение

| Канонический смысл | BPMN v0.2 | Условие |
|---|---|---|
| производственная система | один participant/pool | только моделируемая внутренняя система |
| ответственная позиция | lane | lane не заменяет position_id |
| информационная система | lane только в явно технической проекции | не получает ответственность; обычная схема показывает её через task metadata |
| действие человека | user task | `zeebe:userTask`; assignment только из явного deployment mapping |
| автоматизация или AI-исполнение | service task | для deployment обязателен `zeebe:taskDefinition type` |
| человеческое решение | user task + exclusive gateway | task производит решение, gateway только маршрутизирует по данным |
| вычисляемое условие | exclusive gateway | FEEL на каждой ветке кроме одной default |
| независимые одновременные ветки | parallel gateway split/join | пара задаётся явно, не выводится из нескольких стрелок |
| связанный переиспользуемый процесс | call activity | статический process ID и явный binding; иначе не deployment-ready |
| локальная группировка | embedded subprocess | ровно one none start внутри |
| начало/завершение | none start/end по умолчанию | message/timer/error только из явной семантики модели |
| порядок действий | sequence flow | stable edge lineage сохраняется |
| материал, продукт, данные | extension metadata | визуальные data objects/associations пока не разрешены корпоративной нормой |
| внешний контрагент | metadata задачи/интерфейса | отдельный внешний pool и message flow пока не создаются |

Inclusive и event-based gateways, message flows, BPMN artifacts, data associations, compensation и произвольные modifiers в v0.2 запрещены, даже если Camunda поддерживает часть из них. Их добавление требует нового решения, fixture и migration rule.

## Идентификаторы и lineage

- `process_id`, `action_id`, `edge_id`, `position_id`, `version_id` сохраняются в `modeler:properties` каждого соответствующего BPMN-элемента;
- BPMN XML IDs выводятся детерминированно из типа и stable ID и не зависят от геометрии;
- `projection_build_id` уникален для результата сборки, но повторная сборка одинакового IR даёт тот же `model_fingerprint` и одинаковые bytes;
- BPMN и SVG хранят sha256;
- лист `Диаграммы` связывает process, version, build, fingerprint, URL и readiness;
- layout не является бизнес-истиной и может измениться только вместе с версией алгоритма генератора, зафиксированной в build manifest.

## Readiness

`не готова`:

- resolver или semantic validation не прошёл;
- отсутствуют start/end, broken references, ambiguous lanes или неподдерживаемый элемент;
- BPMN и SVG fingerprint расходятся.

`готова к просмотру`:

- IR, BPMN XML и SVG детерминированы и структурно валидны;
- все stable IDs трассируются;
- неизвестные deployment settings явно перечислены.

`готова к deployment`:

- выполнены условия просмотра;
- process `isExecutable=true`;
- все user/service/send/call activities имеют явную поддерживаемую реализацию;
- exclusive branches имеют boolean FEEL и default;
- deployment target/version compatibility установлены;
- файл открыт и прошёл lint в актуальном Desktop Modeler либо эквивалентном зафиксированном validator;
- deployment выполняется отдельным разрешением и не входит в генерацию.

Генератор никогда не повышает readiness на основании одного успешного XML parse.

## Отказы и восстановление

- неизвестный action implementation → build остаётся view-only;
- неизвестная ветка → build fail, условие не выдумывается;
- отсутствующий linked process → call activity fail/view-only согласно типу ошибки;
- timeout записи артефакта → искать build ID/hash и не дублировать;
- несовпадение source fingerprint → пересобрать из нового snapshot, не патчить XML вручную;
- ручная правка BPMN/SVG → новый артефакт считается предложением, а не действующей проекцией, пока не отражён в модели.

## Последствия

- `Проекция draw.io` удаляется из v0.2;
- простейшее хранение — файлы `.bpmn` и `.svg` плюс manifest; интерактивное хранилище отложено;
- одна большая карта бизнеса и детализация процессов могут существовать как разные `projection_kind`, но правило декомпозиции большой системы остаётся отдельным будущим решением;
- запуск в Camunda не обещается, пока отсутствуют worker types, identity mappings, forms, variables и deployment permission.

## Условие пересмотра

ADR пересматривается, если владелец принимает внешние pools/message flows, data objects, inclusive/event-based gateways, интерактивное хранилище, round-trip редактирование в Modeler или автоматический deployment.
