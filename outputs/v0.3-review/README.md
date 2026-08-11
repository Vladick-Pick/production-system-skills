# Локальная визуальная приёмка v0.3

Этот каталог содержит review-артефакты release candidate v0.3:

- `production-system-model-template-v0.3-review.xlsx` — локальный технический макет всех 32 листов с демонстрационными formulas, named ranges, dropdown validations и правилом ошибки;
- `working-panel.png` — связное состояние выбранного процесса;
- `deviations.png`, `hypotheses.png`, `experiments.png` — представительные строки трёх новых реестров;
- `inspection.ndjson` — структурная проверка имён листов и области панели.

Артефакты воспроизводятся командой:

~~~bash
CODEX_ARTIFACT_TOOL_MODULE=file:///absolute/path/to/@oai/artifact-tool/dist/artifact_tool.mjs \
  node scripts/render_template_review_v0_3.mjs
~~~

Скрипт требует `@oai/artifact-tool`. В Codex desktop runtime путь зависимости выдаёт `codex_app__load_workspace_dependencies`.

Это не канонический XLSX-снимок и не данные реальной компании. Технические контракты внутри файла доказывают, что артефакт не является статической картинкой, но не подменяют Google Sheets builder. Файл нужен для проверки структуры, читаемости и пользовательского результата до WP-7. Канонический `templates/production-system-model-template-v0.3.xlsx` можно создать только экспортом принятой Google Таблицы после отдельного разрешения на публикацию.
