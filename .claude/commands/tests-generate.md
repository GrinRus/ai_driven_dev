---
description: "Сгенерировать тесты к изменённому коду"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(./gradlew:*),Bash(gradle:*)
---
Вызови саб-агента **qa-author**. Цели:
1) Создать/обновить юнит-тесты для изменённого кода (по `git diff`).
2) При необходимости — добавить интеграционные тесты (mock/stub) для внешних взаимодействий.
3) Сохранить короткие сценарии ручной проверки в `docs/test/$1-manual.md`.
4) Запустить `/test-changed`.
