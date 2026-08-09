# Шаблон канонической модели

Рабочая версия: [создать отдельную копию в Google Sheets](https://docs.google.com/spreadsheets/d/1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k/copy).

Прямая ссылка на опубликованный владельцем оригинал: [Шаблон канонической модели бизнеса — v0.2](https://docs.google.com/spreadsheets/d/1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k/edit?usp=sharing).

## Что хранится здесь

- `production-system-model-template-v0.2.xlsx` — точный текущий экспорт Google Sheets на дату, указанную в манифесте;
- `production-system-model-template-v0.1.xlsx` — сохранённый исторический снимок до миграции;
- `template-manifest.yaml` — идентификатор источника, версия, контрольная сумма и состав листов.
- `template-schema-v0.2.json` — машиночитаемая логическая и декларативная физическая схема 29 листов;
- `scripts/build_template_v0_2.py` — точные formulas, dropdown ranges, named ranges, protections, filters и formatting;
- `migrations/v0.1-to-v0.2.md` — исполнимый агентный runbook: read-only assessment, классы `copy/derive/split/confirm/new-required/regenerate/archive/drop`, migration dossier, порядок вопросов, bounded batches, reconciliation и rollback.

XLSX — воспроизводимый снимок, а не второй независимо редактируемый шаблон. Если Google Sheets и снимок расходятся, сначала определить принятую версию, затем обновить снимок и манифест одним изменением.

V0.2 опубликован на прежнем `spreadsheet_id`; публичная роль снижена до `reader`, а владельцем и редактором остаётся аккаунт владельца. Manifest и XLSX относятся к этому же текущему оригиналу.

## Безопасное использование

Оригинал открыт как «любой по ссылке — читатель». Всегда переходите по ссылке «создать копию» и наполняйте личную копию; структуру оригинала выпускает только отдельная процедура релиза.
