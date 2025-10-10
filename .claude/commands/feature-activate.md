---
description: "Установить активную фичу для гейтов (docs/.active_feature)"
argument-hint: "<slug>"
allowed-tools: Bash(*),Read,Write
---
Создай/перезапиши файл `docs/.active_feature` значением `$1`:
!`mkdir -p docs && printf "%s" "$1" > docs/.active_feature && echo "active feature: $1"`
