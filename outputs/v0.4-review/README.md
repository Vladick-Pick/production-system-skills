# Локальная визуальная приёмка v0.4

Этот каталог содержит review-артефакты release candidate v0.4:

- `production-system-model-template-v0.4-review.xlsx` — локальный 37-листовой макет из композиции schema v0.2+v0.3+v0.4;
- пять PNG — представительные строки новых реестров измеримости и экономики;
- `inspection.ndjson` — структурная проверка 37 листов.

Артефакты воспроизводятся командой:

~~~bash
CODEX_ARTIFACT_TOOL_MODULE=/absolute/path/to/@oai/artifact-tool/dist/artifact_tool.mjs node scripts/build_v0_4_review_artifact.mjs
~~~

Это не канонический XLSX-снимок, не данные реальной компании и не вторая реализация Google Sheets builder. Файл проверяет структуру, читаемость, соседство ID/selectors, даты и dropdown; точные formulas, named ranges, protections и `Рабочая панель` задаёт `scripts/build_template_v0_4.py` и нужно проверить в отдельной Google Таблице перед публикацией.
