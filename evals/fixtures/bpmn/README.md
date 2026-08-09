# BPMN fixtures

- `normal-path.json` — один human user task, материалы и информационная система в properties;
- `complex-flow.json` — human decision + exclusive gateway, default отказ, parallel split/join, timer path, возврат, automation, call activity, внешняя передача в одном pool;
- `unknown-connector.json` — валидная view-проекция без `job_type`, которая обязана остаться `готова к просмотру`.

`scripts/run_bpmn_fixtures.py` также проверяет stale version, repeat build byte equality, прямую/обратную трассировку, hashes, SVG fingerprint и отсутствие draw.io в v0.2 schema.

Camunda Desktop Modeler open/lint остаётся отдельной фактической проверкой среды. Если Modeler отсутствует или не имеет headless interface, fixture не объявляет её пройденной.
