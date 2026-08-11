# Шаблон канонической модели

Стабильная публичная версия: [создать отдельную копию v0.3 в Google Sheets](https://docs.google.com/spreadsheets/d/1W9u-t5a4Uuj2pCBLtia3E60qUHn5ZjeFiicNTCv6fR0/copy).

Прямая ссылка на опубликованный владельцем оригинал: [Шаблон канонической модели бизнеса — v0.3](https://docs.google.com/spreadsheets/d/1W9u-t5a4Uuj2pCBLtia3E60qUHn5ZjeFiicNTCv6fR0/edit?usp=sharing).

## Что хранится здесь

- `production-system-model-template-v0.3.xlsx` — точный текущий экспорт Google Sheets на дату, указанную в манифесте;
- `production-system-model-template-v0.2.xlsx` — сохранённый rollback-снимок предыдущего релиза;
- `production-system-model-template-v0.1.xlsx` — сохранённый исторический снимок до миграции;
- `template-manifest.yaml` — идентификатор источника, версия, контрольная сумма и состав листов.
- `template-schema-v0.2.json` — машиночитаемая логическая и декларативная физическая схема 29 листов;
- `template-schema-v0.3.json` — версионный overlay, добавляющий три реестра и новую рабочую панель, а также явно уточняющий словари и компонентные ссылки до итоговых 32 листов;
- `scripts/build_template_v0_2.py` — точные formulas, dropdown ranges, named ranges, protections, filters и formatting;
- `scripts/build_template_v0_3.py` — композиционный builder текущего релиза v0.3;
- `migrations/v0.1-to-v0.2.md` — исполнимый агентный runbook: read-only assessment, классы `copy/derive/split/confirm/new-required/regenerate/archive/drop`, migration dossier, порядок вопросов, bounded batches, reconciliation и rollback.
- `migrations/v0.2-to-v0.3.md` — управляемая миграция: отдельная копия, сохранение stable IDs и референтов, только объявленные семантические преобразования, три пустых реестра и пересборка служебных представлений.

Локальный визуальный макет из `outputs/v0.3-review/` остаётся свидетельством проверки кандидата. Канонический снимок — только `production-system-model-template-v0.3.xlsx`, экспортированный из указанной в manifest Google Таблицы.

XLSX — воспроизводимый снимок, а не второй независимо редактируемый шаблон. Если Google Sheets и снимок расходятся, сначала определить принятую версию, затем обновить снимок и манифест одним изменением.

V0.3 опубликован на отдельном `spreadsheet_id`; публичная роль — `reader`, а владельцем и редактором остаётся аккаунт владельца. Верхний уровень manifest и XLSX относятся к v0.3. Вложенная секция `rollback` фиксирует прежний публичный v0.2 и его неизменяемый XLSX-снимок.

## Безопасное использование

Оригинал открыт как «любой по ссылке — читатель». Всегда переходите по ссылке «создать копию» и наполняйте личную копию; структуру оригинала выпускает только отдельная процедура релиза.
