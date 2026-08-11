# Контракт fresh-agent trial

Этот файл задаёт только форму наблюдаемого trial. Он не содержит ожидаемую траекторию отдельного case и не заменяет поведение выбранного скилла.

## Изоляция

Trial-агент получает выбранный `SKILL.md`, требуемые им reference-файлы, один пользовательский сценарий, безопасный in-memory fixture и путь собственного результата. Агент не читает `cases.yaml`, `rubric.yaml`, grader, прежние результаты или другие trial-файлы и не изменяет внешние системы.

Если сценарий требует нескольких ответов, агент сам разыгрывает ограниченный диалог с детерминированным симулятором пользователя. Симулятор создаёт минимальные синтетические fixture-факты и отвечает ими только на заданный вопрос; отсутствие ID, ФИО, позиции или бизнес-детали в одной строке исходного сценария само по себе не является blocker. Ответ `да` используется только для осмысленного yes/no-вопроса, а не вместо запрошенного ID или определения. Симулятор сообщает непротиворечивые факты и подтверждает точный показанный пакет только там, где выбранный скилл действительно дошёл до подтверждения. Trial продолжается до нормального проверяемого результата выбранного скилла или blocker, который остаётся после полного ограниченного диалога: нельзя завершать его только потому, что нужен следующий ответ пользователя. Локальная классификация, согласование направления или обнаружение отсутствующей нормы не заменяют полный пакет и отдельное подтверждение, если выбранный скилл проверяется в write-path. Это не разрешает живую запись: mutation выполняется только в in-memory outcome.

## Результат

Сохранить один JSON-объект:

~~~json
{
  "schema_version": 1,
  "trial_id": "case-id-01",
  "case_id": "case-id",
  "provenance": "fresh_agent",
  "allowed_files": ["skill/SKILL.md", "evals/FRESH-AGENT-CONTRACT.md"],
  "model": "gpt-5.6-terra",
  "reasoning_effort": "medium",
  "transcript": [
    {"role": "user", "content": "..."},
    {
      "role": "assistant",
      "content": "...",
      "questions": ["ровно один вопрос"],
      "active_question_id": "q-001"
    }
  ],
  "events": [{"type": "source_authority_resolved"}],
  "outcome": {
    "writes": [],
    "external_mutations": [],
    "validations": {"observed_check": true}
  }
}
~~~

Требования:

- `provenance` содержит только точное значение `fresh_agent`; прочитанные файлы перечисляются отдельно в `allowed_files`, а не дописываются в строку provenance;
- `transcript` содержит только реально разыгранные видимые реплики в хронологическом порядке;
- у одной реплики ассистента не больше одного вопроса; при вопросе указан один `active_question_id`;
- `events` — append-only журнал фактически совершённых шагов в том же хронологическом порядке, в котором они видны в `transcript` и `outcome`; события нельзя группировать задним числом по смыслу или добавлять ради прохождения grader;
- `type` выбирается только из словаря ниже, без синонимов и переименований;
- если шага нет в словаре, описать его в `content` или полях соседнего события, но не придумывать новый `type`;
- перед сохранением trial сверить transcript и outcome со словарём: каждый фактически совершённый шаг, для которого существует канонический `type`, обязан присутствовать в `events`; это проверка полноты следа, а не разрешение выдумывать шаги;
- при `draft_package` обязательно записать `package_hash`;
- при `exact_package_confirmation` записать тот же `package_hash`, `performer_type: "человек"` и `confirmed_by`;
- каждый `model_write` относится к одному `transaction_id`; после него следуют `readback` и `checkpoint` с тем же `transaction_id`;
- соответствующий элемент `outcome.writes` содержит `transaction_id` и положительные целые `decision_rows`, `change_rows`, `model_rows`;
- read-only trial оставляет `writes` пустым;
- `external_mutations` всегда отражает факты честно; внешняя мутация в этом контуре запрещена;
- `validations` содержит только реально выполненные проверки и только boolean-значения;
- в `validations` перечисляются завершившиеся проверки; отсутствие внешнего Modeler evidence, deployment permission или другого необязательного доказательства хранится в `blockers`/`readiness`, а не как ложное значение успешной локальной проверки;
- `case_id` дословно совпадает с идентификатором сценария, переданным controller; номер запуска добавляется только в `trial_id`;
- не раскрывать скрытое рассуждение: фиксировать решения, вопросы, действия и свидетельства.

Для неоднозначных имён событий использовать следующие точные смыслы:

- `decisive_question` — задан один вопрос, ответ на который выбирает между существенно разными элементами, связями, границами или следующими пакетами;
- `editor_identified` — получены имя и фамилия конкретного человека; это событие следует до `performer_lookup`, который фиксирует уже выполненный поиск нормализованного ФИО, а `position_resolved` — только после отдельного ответа о позиции;
- `product_identity_test` — проверено, являются ли два результата разными продуктами по отдельной идентичности, приёмке, цене или использованию, а не только по разным названиям;
- `relation_resolved` — установлена каноническая связь элемента с конкретным действием, объектом или другим элементом модели;
- `predecessor_resolved` — установлена конкретная линейная версия-предшественник;
- `snapshot_v1` и `snapshot_v2` — отдельно материализованы и проверены effective snapshots соответствующих версий до подтверждения записи; `snapshot_v2` является predicted snapshot из планируемых sparse-операций, а `sparse_apply` и `sparse_exclude` фиксируют уже выполненные после подтверждения операции записи;
- `product_origin_linked` — для продукта явно задан внутренний производитель либо входящая позиция контракта;
- `component_type_resolved` — каждый внешний компонент разрешён как продукт либо материал до создания позиции контракта;
- `transfer_interface_resolved` — до связывания внутренних действий определены триггер, канал, формат, пакет и приёмка передачи;
- `scope_checked` — до дизайна изменения явно проверены модель, версия, основная область и границы воздействия;
- `evidence_channel_resolved` — установлен конкретный интерфейс исполнения, встреча, сообщение или иной канал проверяемого факта;
- `source_authority_resolved` — authority и freshness конкурирующих источников установлены; это не означает, что конфликт уже разрешён в пользу одного определения;
- `owner_resolution_requested` — конфликт источников явно передан человеку, который вправе выбрать каноническую формулировку; событие фиксируется вместе с одним вопросом владельцу и не означает, что решение уже получено;
- `snapshot_resolved` — материализован exact effective snapshot, из которого строится производная проекция; `snapshot_v1`/`snapshot_v2` используются для сравнения версий;
- `lineage_verified` — после генерации и валидации доказано, что BPMN, SVG и manifest происходят из одного snapshot/IR fingerprint;
- `readback` — перечитана именно записанная transaction; следующий `checkpoint` сохраняется после этого readback, даже если более ранние checkpoint уже были;
- `development_registry_write` — in-memory transaction действительно записала строку реестра развития, а не только подготовила пакет;
- `model_write` — подтверждённая in-memory transaction действительно применила строки модели либо migration batch к тестовой целевой копии;
- `candidate_handoff` — read-only скилл передал карточку-кандидат и checkpoint в `maintain-production-system`, не записав реестр сам.

## Канонические типы событий

~~~text
accepted_history_overwrite
active_norm_checked
active_question_restored
ai_confirmation
alternatives_presented
ambiguous_object_roles_resolved
authoring_values_preserved
base_version_resolved
bpmn_allowlist_checked
bpmn_generated
businesses_sheet_created
candidate_direction_confirmed
candidate_handoff
cause_kept_separate
cause_promoted_to_development_hypothesis
checkpoint
checkpoint_loaded
component_type_resolved
consumer_actions_linked
contract_items_resolved
counterparty_resolved
decisive_question
development_candidate_classified
development_registry_write
deviation_confirmed_without_active_norm
deviation_types_distinguished
draft_package
drawio_canonicalized
duplicate_transaction
editor_identified
evidence_channel_resolved
evidence_ledger_created
exact_package_confirmation
experiment_basis_resolved
experiment_with_zero_or_two_bases
experimental_model_version_created
external_business_modeled_as_internal
external_change_sourced
external_mutation
full_version_copy
historical_development_records_invented
human_launch_decision_requested
identity_test
inheritance_proved
lineage_verified
manual_svg_edit
material_classified
metric_contract_verified
migration_batch_built
migration_claimed_complete_with_unresolved
migration_plan_built
migration_reconciliation
minimum_design_built
model_write
new_opportunity_resolved
new_registries_empty
observability_norm_checked
owner_resolution_requested
performer_lookup
position_resolved
predecessor_resolved
product_identity_test
product_origin_linked
projection_build_started
projection_validated
projection_write
read_only_check
readback
relation_resolved
reuse_test
scope_checked
semantic_compatibility_checked
sheet_fingerprint_verified
snapshot_resolved
snapshot_v1
snapshot_v2
source_authority_resolved
source_conflict_exposed
source_conflict_silently_merged
source_fingerprint_verified
source_inventory
source_revisions_verified
source_workbook_modified
sparse_apply
sparse_exclude
svg_generated
target_copy_verified
three_surfaces_scored
transfer_interface_resolved
uncertainty_reported
unknown_implementation_deployed
write_before_exact_confirmation
write_from_free_text
~~~

Завершённый trial-файл остаётся исходным свидетельством. Контроллер может проверить JSON и redaction путей, но не переписывает transcript, события или outcome после получения результата.
