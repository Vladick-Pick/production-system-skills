# Шаблон канонической модели

Стабильная публичная версия: [создать отдельную копию v0.2 в Google Sheets](https://docs.google.com/spreadsheets/d/1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k/copy).

Локальный release candidate v0.3 реализован в schema, builder, migration и скиллах, но ещё не опубликован как каноническая Google Таблица. Не используйте локальный review-XLSX как источник production-миграции: канонический XLSX v0.3 появится только после экспорта принятой Google Таблицы.

Прямая ссылка на опубликованный владельцем оригинал: [Шаблон канонической модели бизнеса — v0.2](https://docs.google.com/spreadsheets/d/1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k/edit?usp=sharing).

## Что хранится здесь

- `production-system-model-template-v0.2.xlsx` — точный текущий экспорт Google Sheets на дату, указанную в манифесте;
- `production-system-model-template-v0.1.xlsx` — сохранённый исторический снимок до миграции;
- `template-manifest.yaml` — идентификатор источника, версия, контрольная сумма и состав листов.
- `template-schema-v0.2.json` — машиночитаемая логическая и декларативная физическая схема 29 листов;
- `template-schema-v0.3.json` — additive overlay, добавляющий три реестра и новую рабочую панель до итоговых 32 листов;
- `scripts/build_template_v0_2.py` — точные formulas, dropdown ranges, named ranges, protections, filters и formatting;
- `scripts/build_template_v0_3.py` — композиционный builder release candidate v0.3;
- `migrations/v0.1-to-v0.2.md` — исполнимый агентный runbook: read-only assessment, классы `copy/derive/split/confirm/new-required/regenerate/archive/drop`, migration dossier, порядок вопросов, bounded batches, reconciliation и rollback.
- `migrations/v0.2-to-v0.3.md` — additive migration: отдельная копия, сохранение всех значений и stable IDs, три пустых реестра и замена только служебных представлений.

Локальный визуальный макет из `outputs/v0.3-review/` проверяет структуру и читаемость release candidate. Он намеренно не указан в manifest как канонический снимок и не заменяет экспорт из Google Sheets.

XLSX — воспроизводимый снимок, а не второй независимо редактируемый шаблон. Если Google Sheets и снимок расходятся, сначала определить принятую версию, затем обновить снимок и манифест одним изменением.

V0.2 опубликован на прежнем `spreadsheet_id`; публичная роль снижена до `reader`, а владельцем и редактором остаётся аккаунт владельца. Верхний уровень manifest и XLSX относятся к этому же текущему оригиналу. Секция `candidate` описывает локальную готовность v0.3, но не объявляет её опубликованной.

## Безопасное использование

Оригинал открыт как «любой по ссылке — читатель». Всегда переходите по ссылке «создать копию» и наполняйте личную копию; структуру оригинала выпускает только отдельная процедура релиза.
