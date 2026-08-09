# Поведенческие evals

`evals/` проверяет не только наличие фраз в `SKILL.md`, а наблюдаемое поведение агента и конечное состояние модели.

## Артефакты

- `rubric.yaml` — три независимые шкалы 0–10 и critical violations;
- `cases.yaml` — multi-turn сценарии, ожидаемые trajectory и outcome;
- `fixtures/` — детерминированные входы и ожидаемые производные артефакты;
- `trials/fixtures/` — положительные и отрицательные recorded trials для самопроверки grader;
- `results/grader-self-test.json` — последний воспроизводимый результат самопроверки;
- `runs/` — реальные fresh-agent trials; каталог не является источником методологии.

`scripts/run_behavioral_evals.py` читает transcript, упорядоченный event stream и outcome среды. Он проверяет один активный вопрос, точный `package_hash`, человеческое подтверждение до write, единый `transaction_id`, readback/checkpoint, запрещённые события и отсутствие внешних мутаций.

## Протокол запуска

1. Использовать чистый контекст без предыдущих выводов evaluator.
2. Передать только пользовательский сценарий, выбранный skill и тестовый артефакт.
3. Запретить изменения живых Google Sheets и других внешних систем; использовать тестовую копию или in-memory fixture.
4. Сохранить transcript: вопросы, ответы симулятора пользователя, tool calls, подтверждения, commit package и readback.
5. Сохранить outcome: итоговые строки, решения, изменения, checkpoint, ошибки и отсутствие запрещённых side effects.
6. Оценить три поверхности отдельно. Для спорного поведения проверять transcript, для структуры — outcome и детерминированные validators.
7. Выполнить три независимых trial каждого release-blocking case.

Самопроверка grader:

~~~bash
python3 scripts/run_behavioral_evals.py --self-test
~~~

Release gate по фактическим запускам:

~~~bash
python3 scripts/run_behavioral_evals.py --trials-dir evals/runs/<release> --release-gate
~~~

`recorded_fixture` никогда не засчитывается как fresh-agent evidence. Если хотя бы у одного release-blocking case нет трёх уникальных прошедших `fresh_agent` trial, release gate завершается ошибкой. Самопроверка доказывает работоспособность grader, а не качество агента.

## PASS

- `skill_harness >= 8`;
- `agent_behavior >= 8`;
- `artifact_quality >= 8`;
- нет critical violation;
- release-blocking case проходит `3/3` trials;
- статические validators проходят отдельно.

Один успешный trial не доказывает надёжность. Статический поиск обязательной фразы не заменяет поведенческий trial.
