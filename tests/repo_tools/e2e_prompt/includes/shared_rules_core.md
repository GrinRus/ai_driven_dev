## 4) Ключевые правила

- R0: Первый запуск каждого stage (кроме `idea-new`) — только `ticket`.
- R0.1: Для `idea-new` используется только `ticket + IDEA_NOTE`; `slug_hint` генерируется внутри команды.
- R1: Для `full` разрешена ровно одна ручная пара `implement -> review` перед auto-loop.
- R2: Никаких ручных правок runtime-артефактов.
- R3: Не читать/не печатать секреты (`.env`, keys, tokens).
- R4: Только Python runtime surfaces (`skills/*/runtime/*.py`), без shell wrappers.
- R4.1: Если canonical runtime из install/cache path (`$PLUGIN_DIR/skills/*/runtime/*.py` или `<plugin_cache>/skills/*/runtime/*.py`) падает с `ModuleNotFoundError: No module named 'aidd_runtime'`, классифицировать как `flow bug (runtime_bootstrap_missing)`; это не `ENV_BLOCKER`.
- R5: Stage-chain orchestration должны быть включены:
- R6: Все slash stage-команды запускать только из `PROJECT_DIR`.
- R6.1: Если `STAGE_OUTPUT_MODE=stream-json`, запускать `claude -p` только с `--verbose` (иначе CLI вернёт ошибку формата вывода).
- R6.2: Для `claude -p` stage-команд обязательно добавлять `--plugin-dir "$PLUGIN_DIR"`.
- R7: Перед первым stage-run обязателен plugin-load healthcheck (см. Шаг 1). Если плагин не загружен — это `ENV_BLOCKER` и аудит останавливается.
- R8: `Unknown skill: feature-dev-aidd:*` классифицируется как `ENV_BLOCKER(plugin_not_loaded)`; **не** классифицировать как `flow bug`.
- R8.1: Если в UI/операторском выводе встречается unprefixed alias (`/idea-new` и т.п.), но в `init.slash_commands` присутствуют `feature-dev-aidd:*`, фиксировать `INFO(prefix_alias_display_only)`; использовать canonical prefixed команды.
- R9: Python fallback разрешён только после успешного plugin-load healthcheck и только для `blocked/hang/killed`. Python fallback запрещён как recovery для `Unknown skill`.
- R10: Ошибка `refusing to use plugin repository as workspace root` классифицируется как `ENV_MISCONFIG(cwd_wrong)`; исправь `cwd` на `PROJECT_DIR` и повтори ровно 1 раз.
- R11: Для шага 7 (Auto-loop через Python runtime) runner должен быть non-interactive:
  - перед запуском установить `AIDD_LOOP_RUNNER="claude --dangerously-skip-permissions"`;
  - если в stream `init` видно `permissionMode=default` и дальше идут `requires approval`, классифицировать как `ENV_MISCONFIG(loop_runner_permissions)` (не как flow bug).
- R12: В `stream-json` режиме liveness проверяется по двум источникам одновременно:
  - `AUDIT_DIR/<step>_run<N>.log` (main log),
  - stream-файлы (`*.stream.jsonl` и `*.stream.log`) из header/метаданных.
  Стагнация только main log при растущем stream не является `silent stall`.
- R12.1: Извлечение stream-путей обязано поддерживать абсолютные и относительные пути из `init/header/metadata`; относительные пути нормализуются относительно `PROJECT_DIR` и сохраняются в нормализованном виде.
- R12.1a: Primary extraction разрешён только из `system/init` JSON payload и control-header строк (`==> streaming enabled ... stream=... log=...`); любые `tool_result`/artifact excerpts/prose строки исключаются из extraction.
- R12.2: Если stream-пути не извлеклись из main log/metadata, обязателен fallback discovery в `aidd/reports/loops/<ticket>/` (по `*.stream.jsonl` и `*.stream.log`) с выбором самых свежих файлов; этот fallback фиксируется в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- R12.3: После нормализации stream-путей оставлять в liveness-множестве только пути внутри `PROJECT_DIR`, которые физически существуют на момент проверки; абсолютные пути вне workspace (например, `/reports/...`) фиксировать как `stream_path_invalid`, отсутствующие пути внутри workspace фиксировать как `stream_path_missing`, оба типа исключать из расчёта stall.
- R12.4: Если primary extraction дал только `stream_path_invalid`/`stream_path_missing` или пустой валидный набор, обязателен fallback discovery; отсутствие fallback при таком случае — `prompt-exec issue (stream_path_resolution_incomplete)`.
