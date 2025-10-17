# Feature Cookbook

Этот конспект дополняет `workflow.md` и помогает быстро свериться со стадиями
фичи. Перед тем как переходить к планированию или реализации, убедитесь, что
исследование завершено и рекомендации приняты командой.

## Idea → Research
- Запустите `/idea-new <slug>` и сразу отвечайте на вопросы аналитика форматом `Ответ N: …`. Агент ведёт журнал в `## Диалог analyst`, поэтому не переходите дальше, пока каждый `Вопрос N` не получил ответ.
- Обновляйте `Status:` (`READY`/`BLOCKED`) и очищайте `## 10. Открытые вопросы` по мере закрытия блокеров.
- После каждой итерации проверяйте результат `claude-workflow analyst-check --feature <slug>` — команда укажет на пропущенные ответы или неверную нумерацию. Если проверка падает, вернитесь к аналитическому диалогу.

## Research → Plan
- Запустите `claude-workflow research --feature <slug>` и уточните области
  анализа (`--paths`, `--keywords`). CLI сформирует `reports/research/<slug>-targets.json`
  и `<slug>-context.json`.
- Через `/researcher <slug>` оформите `docs/research/<slug>.md` по шаблону
  `docs/templates/research-summary.md`; зафиксируйте точки интеграции,
  reuse-компоненты и риски.
- Вставьте ссылку на `docs/research/<slug>.md` в раздел артефактов PRD и
  чеклист `docs/tasklist/<slug>.md`, чтобы команда видела результаты исследования.
- Проставьте `Status: reviewed`, как только вывод согласован, и перенесите
  блокирующие действия в `docs/plan/<slug>.md` и `docs/tasklist/<slug>.md`.

## Plan → Implementation
- Проверяйте, что план покрывает все директории из `reports/research/<slug>-targets.json`.
- Во время реализации держите `reports/research/<slug>-context.json` в актуальном
  состоянии (`claude-workflow research --feature <slug>` без `--dry-run`). Это
  обеспечит прохождение `gate-workflow` и напомнит команде о согласованных
  точках интеграции.
