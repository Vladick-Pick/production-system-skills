# Поведенческие evals

`evals/` проверяет не только наличие фраз в `SKILL.md`, а наблюдаемое поведение агента и конечное состояние модели.

## Артефакты

- `rubric.yaml` — три независимые шкалы 0–10 и critical violations;
- `cases.yaml` — multi-turn сценарии, ожидаемые trajectory и outcome;
- `FRESH-AGENT-CONTRACT.md` — единая изолированная форма transcript, event stream и outcome без подсказки ожидаемой траектории case;
- `fixtures/` — детерминированные входы и ожидаемые производные артефакты;
- `trials/fixtures/` — положительные и отрицательные recorded trials для самопроверки grader;
- `results/grader-self-test.json` — последний воспроизводимый результат самопроверки;
- `runs/` — реальные fresh-agent trials; каталог не является источником методологии.

`scripts/run_behavioral_evals.py` читает transcript, event stream и outcome среды. `required_events` задают полноту поведения; отдельные hard-order цепочки проверяют только причинно значимый порядок. Grader также проверяет один активный вопрос, точный `package_hash`, человеческое подтверждение до write, единый `transaction_id`, readback с последующим checkpoint, запрещённые события и отсутствие внешних мутаций.

## Протокол запуска

1. Использовать чистый контекст без предыдущих выводов evaluator.
2. Передать только пользовательский сценарий, выбранный skill, тестовый артефакт и общий `FRESH-AGENT-CONTRACT.md`; не передавать case-specific rubric или expected trajectory.
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

## Доказательство релиза v0.3

11 августа 2026 года release gate прошёл полностью: `48/48` выбранных fresh-agent trials, то есть 16 release-blocking сценариев по три уникальных запуска. Все выбранные прогоны выполнены на `gpt-5.6-terra` с reasoning effort `medium`; у каждого три оценки равны `10.0`, critical violations и внешние мутации отсутствуют.

Машинный отчёт: `results/v0.3-terra-medium-release-gate.json`. Исходные trial-файлы, включая неудачные попытки, сохранены в `runs/`: они показывают реальную вариативность траекторий и не переписывались контроллером. В release gate вошли только уникальные PASS; recorded fixtures и одинаковые `trial_id` из разных каталогов не засчитывались повторно.
