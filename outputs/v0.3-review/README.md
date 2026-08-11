# Локальная визуальная приёмка v0.3

Этот каталог содержит review-артефакты release candidate v0.3:

- `production-system-model-template-v0.3-review.xlsx` — локальный макет всех 32 листов;
- `working-panel.png` — связное состояние выбранного процесса;
- `deviations.png`, `hypotheses.png`, `experiments.png` — представительные строки трёх новых реестров;
- `inspection.ndjson` — структурная проверка имён листов и области панели.

Артефакты воспроизводятся командой:

~~~bash
node scripts/render_template_review_v0_3.mjs
~~~

Скрипт требует `@oai/artifact-tool`. В Codex desktop runtime путь зависимости выдаёт `codex_app__load_workspace_dependencies`.

Это не канонический XLSX-снимок и не данные реальной компании. Файл нужен для проверки структуры, читаемости и пользовательского результата до WP-7. Канонический `templates/production-system-model-template-v0.3.xlsx` можно создать только экспортом принятой Google Таблицы после отдельного разрешения на публикацию.
