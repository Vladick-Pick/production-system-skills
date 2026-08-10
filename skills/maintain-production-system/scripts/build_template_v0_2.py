#!/usr/bin/env python3
"""Построить детерминированный Google Sheets batchUpdate для шаблона v0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve()
SCHEMA_CANDIDATES = (
    HERE.parents[1] / "templates" / "template-schema-v0.2.json",
    HERE.parents[1] / "references" / "TEMPLATE-SCHEMA-v0.2.json",
    HERE.parents[2] / "references" / "TEMPLATE-SCHEMA-v0.2.json",
)
SCHEMA_PATH = next((path for path in SCHEMA_CANDIDATES if path.is_file()), SCHEMA_CANDIDATES[0])
FIRST_SHEET_ID = 700_200_000
TEMP_SHEET_TITLE = "__v02_migration__"

DESCRIPTION_BY_KIND = {
    "guide": "Как работать с канонической моделью бизнеса v0.2.",
    "identity_registry": "Неверсионируемый реестр стабильных идентичностей.",
    "governance_registry": "Реестр решений и управления жизненным циклом модели.",
    "relation_registry": "Временные или управленческие связи между идентичностями.",
    "versioned_authoring": "Редактируемый реестр элементов модели с историей по версиям.",
    "versioned_authoring_with_settings": "Настройки книги и внутренние производственные системы по версиям.",
    "append_only_governance": "Неизменяемый журнал подтверждённых решений и изменений.",
    "computed_registry": "Производное представление; вручную не редактировать.",
    "computed_dashboard": "Рабочая панель выбранной версии; редактируются только поля выбора.",
    "derived_artifact_registry": "Реестр производных BPMN/SVG-сборок и их lineage.",
}

DESCRIPTION_BY_SHEET = {
    "Инструкция": "Порядок работы с моделью бизнеса, версиями, проверками и агентом.",
    "Система": "Настройки книги и внутренние производственные системы моделируемого бизнеса.",
    "Схема шаблона": "Связи между листами, полями и правилами проверки шаблона.",
    "Источники": "Документы, интервью и системы, на которых основаны определения модели.",
    "Версии": "Черновые, принятые, действующие и закрытые состояния модели бизнеса.",
    "Исполнители": "Люди и AI-агенты, которые выполняют работу или подтверждают изменения модели.",
    "Позиции": "Устойчивые зоны ответственности внутри производственных систем, независимо от конкретных людей.",
    "Назначения": "Связи исполнителей с позициями и сроки действия этих связей.",
    "Контрагенты": "Внешние люди и организации, с которыми бизнес обменивается продуктами.",
    "Продукты": "Типы результатов, которые внутренние системы бизнеса производят или получают от внешних контрагентов.",
    "Материалы": "Переиспользуемые тексты, скрипты, презентации, инструкции и шаблоны для выполнения действий.",
    "Процессы": "Воспроизводимые цепочки действий с общей целью, триггером, объектом работы и результатом.",
    "Действия": "Наблюдаемые операции внутри процессов с входом, выходом и ответственной позицией.",
    "Связи действий": "Порядок выполнения действий: последовательности, условия, ветвления, исключения и возвраты.",
    "Объекты": "Сущности, идентичность и состояние которых изменяются в ходе процессов.",
    "Состояния": "Устойчивые положения объектов работы и допустимые действия в каждом положении.",
    "Переходы": "Изменения состояния объекта, вызванные действием, условием или решением.",
    "Элементы модели": "Правила, данные, информационные системы, показатели, нормативы, SLA и автоматизации.",
    "Контракты": "Общие договорённости бизнеса с внешними контрагентами.",
    "Позиции контрактов": "Отдельно принимаемые и рассчитываемые продукты внутри контрактов.",
    "Интерфейсы передачи": "Способы и условия передачи продуктов через внешнюю границу бизнеса.",
    "Связи модели": "Использование и другие смысловые связи между элементами модели.",
    "Решения": "Кто, когда и какой полный пакет изменений подтвердил.",
    "Изменения модели": "Какие поля и элементы были созданы, изменены или исключены каждой транзакцией.",
    "Срез модели": "Полная модель выбранной версии, собранная из ближайших редакций элементов.",
    "Проверки": "Ошибки и предупреждения, которые нужно устранить в исходных листах модели.",
    "Реестр процессов": "Сводный список процессов выбранной версии и их готовность.",
    "Рабочая панель": "Связный обзор выбранных версии, системы и процесса.",
    "Диаграммы": "Сборки BPMN/SVG, построенные из точного среза модели.",
}

HELP_BY_KIND = {
    "identity_registry": "Одна реальная сущность получает один стабильный ID. Повторное упоминание не создаёт новую строку.",
    "governance_registry": "Каждая строка фиксирует отдельное состояние или управленческий факт; историю не переписывают задним числом.",
    "relation_registry": "Одна строка связывает две существующие сущности на указанный период.",
    "versioned_authoring": "Начните строку со стабильного ID. Версия подставится автоматически; связи выбирайте по понятным названиям в соседних списках.",
    "append_only_governance": "Лист заполняется при подтверждённой записи и не редактируется задним числом.",
    "computed_registry": "Лист собирается автоматически. Чтобы исправить результат, измените исходные данные, а затем пересоберите представление.",
    "derived_artifact_registry": "Одна строка описывает одну проверенную сборку представления, а не отдельную версию бизнес-модели.",
}

HELP_BY_SHEET = {
    "Продукты": "Одна строка = один тип продукта, а не отдельный лид или событие. Внутренний производитель задаётся связью «система → производит → продукт»; внешний поставщик — входящей позицией контракта.",
    "Материалы": "Одна строка = один переиспользуемый материал. Конкретное отправленное сообщение или заполненный документ относится к данным исполнения, а не к этому каталогу.",
    "Позиции контрактов": "Направление «входящая» означает, что бизнес получает продукт от контрагента; «исходящая» — что бизнес поставляет продукт контрагенту.",
    "Связи модели": "Здесь фиксируется, где элемент используется: например, действие использует материал или система производит продукт.",
}

DISPLAY_FIELD_OVERRIDES = {
    "Источники": "source_name",
    "Версии": "version_label",
    "Исполнители": "performer_name",
    "Назначения": "assignment_id",
    "Контрагенты": "counterparty_name",
    "Решения": "decision_summary",
    "Изменения модели": "change_id",
    "Диаграммы": "projection_build_id",
}


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def column_letter(index: int) -> str:
    """Преобразовать zero-based индекс столбца в A1-буквы."""
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def quoted_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def rgb(hex_value: str) -> dict[str, float]:
    value = hex_value.lstrip("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def cell(value: Any = None, formula: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if formula is not None:
        data["userEnteredValue"] = {"formulaValue": formula}
    elif isinstance(value, bool):
        data["userEnteredValue"] = {"boolValue": value}
    elif isinstance(value, (int, float)):
        data["userEnteredValue"] = {"numberValue": value}
    elif value is not None:
        data["userEnteredValue"] = {"stringValue": str(value)}
    return data


def row(values: Iterable[Any]) -> dict[str, Any]:
    return {"values": [item if isinstance(item, dict) else cell(item) for item in values]}


def update_block(sheet_id: int, start_row: int, start_column: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    width = max((len(item.get("values", [])) for item in rows), default=0)
    padded = []
    for item in rows:
        values = list(item.get("values", []))
        values.extend({} for _ in range(width - len(values)))
        padded.append({"values": values})
    return {
        "updateCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": start_row + len(padded),
                "startColumnIndex": start_column,
                "endColumnIndex": start_column + width,
            },
            "rows": padded,
            "fields": "userEnteredValue",
        }
    }


def repeat_format(sheet_id: int, start_row: int, end_row: int, start_column: int, end_column: int, fmt: dict[str, Any]) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_column,
                "endColumnIndex": end_column,
            },
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat",
        }
    }


def merge_range(sheet_id: int, start_row: int, end_row: int, start_column: int, end_column: int) -> dict[str, Any]:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_column,
                "endColumnIndex": end_column,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def dimension_size(sheet_id: int, dimension: str, start: int, end: int, pixels: int) -> dict[str, Any]:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": dimension,
                "startIndex": start,
                "endIndex": end,
            },
            "properties": {"pixelSize": pixels},
            "fields": "pixelSize",
        }
    }


def visual_format(
    background: str,
    foreground: str = "#263238",
    *,
    size: int = 10,
    bold: bool = False,
    italic: bool = False,
    horizontal: str = "LEFT",
    vertical: str = "MIDDLE",
    borders: bool = False,
) -> dict[str, Any]:
    fmt: dict[str, Any] = {
        "backgroundColor": rgb(background),
        "textFormat": {
            "fontFamily": "Carlito",
            "fontSize": size,
            "foregroundColor": rgb(foreground),
            "bold": bold,
            "italic": italic,
        },
        "horizontalAlignment": horizontal,
        "verticalAlignment": vertical,
        "wrapStrategy": "WRAP",
    }
    if borders:
        border = {"style": "SOLID", "color": rgb("#D9E1E8")}
        fmt["borders"] = {side: border for side in ("top", "bottom", "left", "right")}
    return fmt


def display_field(sheet_name: str, sheet: dict[str, Any]) -> str | None:
    columns = sheet.get("columns", [])
    override = DISPLAY_FIELD_OVERRIDES.get(sheet_name)
    if override in columns:
        return override
    for suffix in ("_name", "_label", "_title"):
        for name in columns:
            if name.endswith(suffix):
                return name
    for name in columns[1:]:
        if name not in {"version_id", "version_operation"} and not name.endswith("_id") and "selector" not in name:
            return name
    return columns[0] if columns else None


def selector_catalog_formula(schema: dict[str, Any], sheet_name: str, sheet: dict[str, Any], start_row: int) -> str:
    kind = sheet.get("kind")
    if kind in {"versioned_authoring", "versioned_authoring_with_settings"}:
        return (
            "=ARRAYFORMULA(IFERROR(FILTER('Срез модели'!$E$5:$E$1004,"
            f"'Срез модели'!$C$5:$C$1004=\"{sheet_name}\"),\"\"))"
        )
    if sheet_name == "Срез модели":
        return "=ARRAYFORMULA(IF($E$5:$E$1004=\"\",\"\",$E$5:$E$1004))"
    columns = sheet.get("columns", [])
    if not columns:
        return "=\"\""
    id_col = column_letter(0)
    label_field = display_field(sheet_name, sheet)
    label_col = column_letter(columns.index(label_field)) if label_field in columns else id_col
    return (
        f"=ARRAYFORMULA(IF(${id_col}${start_row}:${id_col}$1004=\"\",\"\","
        f"${label_col}${start_row}:${label_col}$1004&\" [id=\"&${id_col}${start_row}:${id_col}$1004&\"]\"))"
    )


def selector_source_sheet(target: str) -> str:
    return target.split(".", 1)[0]


def id_formula(selector_column: int, row_number: int) -> str:
    selector = f"{column_letter(selector_column)}{row_number}"
    return f'=IF({selector}="","",IFERROR(REGEXEXTRACT({selector},"\\[id=([^\\]]+)\\]"),""))'


def version_id_formula(row_number: int) -> str:
    """Показывать рабочую версию только для начатой authoring-строки."""
    return f'=IF($A{row_number}="","",\'Система\'!$B$4)'


def width_for(column: str, default: dict[str, Any]) -> int:
    if column.endswith("_selector"):
        return int(default["selector_width"] * 7)
    if column.endswith("_id") or column in {"stable_id", "from_entity_id", "to_entity_id"}:
        return int(default["id_width"] * 7)
    if column.endswith("_at") or column.endswith("_from") or column.endswith("_to") or "date" in column:
        return int(default["date_width"] * 7)
    if any(token in column for token in ("definition", "description", "criteria", "evidence", "notes", "content", "formula", "path", "input", "output", "purpose", "condition")):
        return int(default["long_text_width"] * 7)
    return int(default["short_text_width"] * 7)


def grouped_width_requests(sheet_id: int, columns: list[str], default: dict[str, Any]) -> list[dict[str, Any]]:
    if not columns:
        return []
    widths = [width_for(name, default) for name in columns]
    requests: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(widths) + 1):
        if index < len(widths) and widths[index] == widths[start]:
            continue
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": start,
                        "endIndex": index,
                    },
                    "properties": {"pixelSize": widths[start]},
                    "fields": "pixelSize",
                }
            }
        )
        start = index
    return requests


def contiguous_runs(indices: Iterable[int]) -> list[tuple[int, int]]:
    values = sorted(set(indices))
    if not values:
        return []
    runs: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        runs.append((start, previous + 1))
        start = previous = value
    runs.append((start, previous + 1))
    return runs


def layout_requests(schema: dict[str, Any], sheet_name: str, sheet_id: int) -> list[dict[str, Any]]:
    """Собрать читаемый визуальный контракт, не затрагивая значения и validations."""
    sheet = schema["sheets"][sheet_name]
    default = schema["default_table"]
    columns = sheet.get("columns", [])
    column_count = 8 if sheet_name == "Инструкция" else 14 if sheet_name == "Рабочая панель" else max(1, len(columns))
    row_count = 200 if sheet_name in {"Инструкция", "Рабочая панель"} else int(default["data_end_row"]) + 1
    requests: list[dict[str, Any]] = [
        repeat_format(sheet_id, 0, row_count, 0, column_count, visual_format("#FFFFFF", vertical="TOP")),
    ]

    if sheet_name == "Инструкция":
        requests.extend(
            [
                merge_range(sheet_id, 0, 1, 0, 8),
                merge_range(sheet_id, 1, 2, 0, 8),
                merge_range(sheet_id, 3, 4, 0, 8),
                merge_range(sheet_id, 12, 13, 0, 8),
                merge_range(sheet_id, 17, 18, 1, 8),
                repeat_format(sheet_id, 0, 1, 0, 8, visual_format("#D9EAF7", "#1F4E78", size=16, bold=True)),
                repeat_format(sheet_id, 1, 2, 0, 8, visual_format("#FFFFFF", "#455A64", italic=True)),
                repeat_format(sheet_id, 3, 4, 0, 8, visual_format("#BDD7EE", "#1F4E78", size=11, bold=True)),
                repeat_format(sheet_id, 12, 13, 0, 8, visual_format("#BDD7EE", "#1F4E78", size=11, bold=True)),
                repeat_format(sheet_id, 4, 11, 0, 1, visual_format("#D9EAF7", "#1F4E78", size=11, bold=True, horizontal="CENTER", borders=True)),
                repeat_format(sheet_id, 4, 11, 1, 2, visual_format("#F3F9FD", "#1F4E78", bold=True, borders=True)),
                repeat_format(sheet_id, 4, 11, 2, 8, visual_format("#FFFFFF", vertical="TOP", borders=True)),
                repeat_format(sheet_id, 13, 16, 0, 8, visual_format("#FFFFFF", borders=True)),
                repeat_format(sheet_id, 13, 14, 1, 2, visual_format("#FFF2CC", "#6D4C00", bold=True, borders=True)),
                repeat_format(sheet_id, 14, 15, 1, 2, visual_format("#D9EAF7", "#1F4E78", bold=True, borders=True)),
                repeat_format(sheet_id, 15, 16, 1, 2, visual_format("#F3F9FD", "#1F4E78", bold=True, borders=True)),
                repeat_format(sheet_id, 17, 18, 0, 8, visual_format("#FCE8E6", "#8A1C1C", bold=True, borders=True)),
                dimension_size(sheet_id, "COLUMNS", 0, 1, 55),
                dimension_size(sheet_id, "COLUMNS", 1, 2, 190),
                dimension_size(sheet_id, "COLUMNS", 2, 8, 125),
                dimension_size(sheet_id, "ROWS", 0, 1, 42),
                dimension_size(sheet_id, "ROWS", 1, 2, 42),
                dimension_size(sheet_id, "ROWS", 3, 4, 34),
                dimension_size(sheet_id, "ROWS", 4, 11, 62),
                dimension_size(sheet_id, "ROWS", 12, 13, 34),
                dimension_size(sheet_id, "ROWS", 13, 16, 42),
                dimension_size(sheet_id, "ROWS", 17, 18, 50),
            ]
        )
        requests.extend(merge_range(sheet_id, row_index, row_index + 1, 2, 8) for row_index in range(4, 11))
        requests.extend(merge_range(sheet_id, row_index, row_index + 1, 2, 8) for row_index in range(13, 16))
        return requests

    if sheet_name == "Рабочая панель":
        requests.extend(
            [
                merge_range(sheet_id, 0, 1, 0, 14),
                merge_range(sheet_id, 1, 2, 0, 14),
                merge_range(sheet_id, 6, 7, 0, 14),
                repeat_format(sheet_id, 0, 1, 0, 14, visual_format("#D9EAF7", "#1F4E78", size=16, bold=True)),
                repeat_format(sheet_id, 1, 2, 0, 14, visual_format("#FFFFFF", "#455A64", italic=True)),
                repeat_format(sheet_id, 2, 5, 0, 1, visual_format("#BDD7EE", "#1F4E78", bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 1, 2, visual_format("#F3F9FD", bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 3, 4, visual_format("#F2F2F2", "#546E7A", size=9, bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 4, 5, visual_format("#F5F7F8", "#455A64", borders=True)),
                repeat_format(sheet_id, 6, 7, 0, 14, visual_format("#BDD7EE", "#1F4E78", size=11, bold=True)),
                dimension_size(sheet_id, "COLUMNS", 0, 1, 185),
                dimension_size(sheet_id, "COLUMNS", 1, 2, 330),
                dimension_size(sheet_id, "COLUMNS", 2, 3, 28),
                dimension_size(sheet_id, "COLUMNS", 3, 4, 175),
                dimension_size(sheet_id, "COLUMNS", 4, 5, 190),
                dimension_size(sheet_id, "COLUMNS", 5, 14, 100),
                dimension_size(sheet_id, "ROWS", 0, 1, 42),
                dimension_size(sheet_id, "ROWS", 1, 2, 38),
                dimension_size(sheet_id, "ROWS", 2, 5, 36),
                dimension_size(sheet_id, "ROWS", 6, 7, 34),
            ]
        )
        for row_index in range(7, 24, 2):
            requests.extend(
                [
                    merge_range(sheet_id, row_index, row_index + 1, 0, 14),
                    repeat_format(sheet_id, row_index, row_index + 1, 0, 14, visual_format("#EAF4FB", "#1F4E78", bold=True, borders=True)),
                ]
            )
        return requests

    header_row = int(sheet.get("header_row", default["header_row"])) - 1
    data_start = int(sheet.get("data_start_row", default["data_start_row"])) - 1
    data_end = int(default["data_end_row"])
    requests.extend([merge_range(sheet_id, 0, 1, 0, column_count), merge_range(sheet_id, 1, 2, 0, column_count)])
    if sheet_name != "Система":
        requests.append(merge_range(sheet_id, 2, 3, 0, column_count))
    requests.extend(
        [
            repeat_format(sheet_id, 0, 1, 0, column_count, visual_format("#D9EAF7", "#1F4E78", size=16, bold=True)),
            repeat_format(sheet_id, 1, 2, 0, column_count, visual_format("#FFFFFF", "#455A64", italic=True)),
            dimension_size(sheet_id, "ROWS", 0, 1, 40),
            dimension_size(sheet_id, "ROWS", 1, 2, 34),
            repeat_format(sheet_id, header_row, header_row + 1, 0, column_count, visual_format("#D9EAF7", "#1F4E78", bold=True, horizontal="CENTER", borders=True)),
            dimension_size(sheet_id, "ROWS", header_row, header_row + 1, 56),
            repeat_format(sheet_id, data_start, data_end, 0, column_count, visual_format("#FFFFFF", vertical="TOP", borders=True)),
        ]
    )
    if sheet_name == "Система":
        requests.extend(
            [
                repeat_format(sheet_id, 2, 5, 0, 4, visual_format("#F2F2F2", "#37474F", borders=True)),
                repeat_format(sheet_id, 3, 5, 2, 3, visual_format("#EAF4FB", "#1F4E78", bold=True, borders=True)),
                dimension_size(sheet_id, "ROWS", 2, 5, 32),
            ]
        )
    else:
        requests.extend(
            [
                repeat_format(sheet_id, 2, 3, 0, column_count, visual_format("#F2F2F2", "#546E7A")),
                dimension_size(sheet_id, "ROWS", 2, 3, 38),
            ]
        )

    required_indices = [columns.index(field) for field in sheet.get("required", []) if field in columns]
    for start, end in contiguous_runs(required_indices):
        requests.append(repeat_format(sheet_id, header_row, header_row + 1, start, end, visual_format("#FFF2CC", "#6D4C00", bold=True, horizontal="CENTER", borders=True)))

    selectors = sheet.get("selectors", {})
    selectors = selectors if isinstance(selectors, dict) else {}
    computed_indices = [columns.index(field) for field in selectors if field in columns]
    if sheet.get("kind") in {"versioned_authoring", "versioned_authoring_with_settings"} and "version_id" in columns:
        computed_indices.append(columns.index("version_id"))
    for start, end in contiguous_runs(computed_indices):
        requests.extend(
            [
                repeat_format(sheet_id, header_row, header_row + 1, start, end, visual_format("#D9EAF7", "#1F4E78", bold=True, horizontal="CENTER", borders=True)),
                repeat_format(sheet_id, data_start, data_end, start, end, visual_format("#F5F7F8", "#455A64", vertical="TOP", borders=True)),
            ]
        )
    selector_indices = [columns.index(field) for field in selectors.values() if field in columns]
    for start, end in contiguous_runs(selector_indices):
        requests.extend(
            [
                repeat_format(sheet_id, header_row, header_row + 1, start, end, visual_format("#CFE2F3", "#1F4E78", bold=True, horizontal="CENTER", borders=True)),
                repeat_format(sheet_id, data_start, data_end, start, end, visual_format("#F3F9FD", vertical="TOP", borders=True)),
            ]
        )
    requests.extend(grouped_width_requests(sheet_id, columns, default))
    return requests


def sheet_static_rows(schema: dict[str, Any], sheet_name: str, sheet: dict[str, Any]) -> list[dict[str, Any]]:
    if sheet_name == "Инструкция":
        return [
            row(["Шаблон канонической модели бизнеса v0.2"]),
            row(["Одна книга хранит каноническую модель одного бизнеса: внутренние производственные системы, продукты, ресурсы и внешние контрактные границы."]),
            row([]),
            row(["Как работать с моделью"]),
            row(["1", "Назначение", "Фиксируйте не произвольные слова, а различимые объекты, состояния, действия, материалы, системы, процессы, позиции, продукты и контрактные границы."]),
            row(["2", "Порядок заполнения", "Начните с источников и версии, затем определите системы, позиции, продукты, процессы, действия, объекты, состояния и связи."]),
            row(["3", "Интервью и подтверждение", "Сначала уточните, куда изменение встраивается, от чего зависит, какой эффект создаёт и как корректно сформулировать определение. Записывайте только после подтверждения."]),
            row(["4", "Версии", "Новая версия хранит только изменения. Неизменённые элементы продолжают действовать из предыдущей версии; история принятых определений не стирается."]),
            row(["5", "Человеко-читаемые списки", "В выпадающем списке выбирайте понятную подпись вида «Название [id=…]». Соседний ID вычисляется автоматически и остаётся видимым."]),
            row(["6", "BPMN и SVG", "Диаграмма — производная проекция канонической модели. Исправляйте смысл в таблице, затем перестраивайте изображение."]),
            row(["7", "Проверки и восстановление", "Перед вводом версии проверьте лист «Проверки». Решения и изменения модели сохраняют автора, дату, основание и состав обновления."]),
            row([]),
            row(["Цвета и правила"]),
            row(["", "Обязательное поле", "Жёлтый заголовок: поле должно быть заполнено для принятой записи."]),
            row(["", "Вычисляемое поле", "Голубой заголовок или серое тело: формулу не редактируют вручную."]),
            row(["", "Выбор из списка", "Светло-голубая ячейка: человек выбирает читаемое значение из списка."]),
            row([]),
            row(["Важно", "Не вставляйте значения поверх формульных ID-столбцов. При ошибке сначала проверьте выбранное значение, рабочую версию и лист «Проверки»."]),
        ]
    if sheet_name == "Рабочая панель":
        values = [
            row(["Рабочая панель модели бизнеса v0.2"]),
            row(["Выберите версию, систему и процесс человеко-читаемыми списками. Технический ID рассчитывается рядом и остаётся видимым."]),
            row(["Рабочая версия", "", "", "selected_version_id", cell(formula=id_formula(1, 3))]),
            row(["Система", "", "", "selected_system_id", cell(formula=id_formula(1, 4))]),
            row(["Процесс", "", "", "selected_process_id", cell(formula=id_formula(1, 5))]),
            row([]),
            row(["Сводные представления"]),
        ]
        for section in sheet.get("sections", []):
            values.extend([row([section]), row([])])
        return values
    header_row = int(sheet.get("header_row", schema["default_table"]["header_row"]))
    description = DESCRIPTION_BY_SHEET.get(
        sheet_name,
        DESCRIPTION_BY_KIND.get(sheet.get("kind"), "Лист модели бизнеса v0.2."),
    )
    if sheet_name == "Система":
        rows = [
            row([sheet_name]),
            row([description]),
            row(["model_id", "", "Одна книга = одна модель бизнеса"]),
            row(["working_version_id", cell(formula=id_formula(2, 4)), "", "working_version_selector"]),
            row(["current_version_id", cell(formula=id_formula(2, 5)), "", "current_version_selector"]),
        ]
        while len(rows) < header_row - 1:
            rows.append(row([]))
        rows.append(row(sheet.get("columns", [])))
        return rows
    help_text = HELP_BY_SHEET.get(
        sheet_name,
        HELP_BY_KIND.get(
            sheet.get("kind"),
            "Технические ID остаются видимыми. Связи выбирайте по понятным названиям в соседних выпадающих списках.",
        ),
    )
    rows = [row([sheet_name]), row([description]), row([help_text])]
    while len(rows) < header_row - 1:
        rows.append(row([]))
    rows.append(row(sheet.get("columns", [])))

    return rows


def schema_registry_rows(schema: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sheet_name in schema["sheet_order"]:
        sheet = schema["sheets"][sheet_name]
        required = set(sheet.get("required", []))
        for field, target in sheet.get("foreign_keys", {}).items():
            rows.append(
                row(
                    [
                        f"{sheet_name}.{field}",
                        f"{sheet_name}.{field}",
                        "N:1",
                        target,
                        "обязательно" if field in required else "необязательно",
                        "читаемое значение → стабильный ID; ровно одно соответствие",
                        f"Связь {field} листа {sheet_name} с {target}",
                    ]
                )
            )
    return rows


def check_rows(schema: dict[str, Any], sheet: dict[str, Any]) -> list[dict[str, Any]]:
    columns = sheet["columns"]
    versions = schema["sheets"]["Версии"]["columns"]
    materials = schema["sheets"]["Материалы"]["columns"]
    version_status_col = column_letter(versions.index("version_status"))
    material_content_col = column_letter(materials.index("content_text"))
    material_url_col = column_letter(materials.index("url"))

    def values(check_id: str, category: str, name: str, formula: str, remediation: str) -> dict[str, Any]:
        result = [cell(check_id), cell(category), cell("критично"), cell(name), cell(formula=formula)]
        result.append(cell(formula=f'=IF(E{5 + len(rows)}=0,"OK","ERROR")'))
        result.extend([cell("да"), cell(""), cell(remediation)])
        return row(result)

    rows: list[dict[str, Any]] = []
    rows.append(values("CHK-MODEL-ID", "структура", "model_id заполнен", '=IF(\'Система\'!B3="",1,0)', "Заполнить Система!B3"))
    rows.append(values("CHK-ONE-DRAFT", "версии", "не более одного черновика", f'=MAX(0,COUNTIF(\'Версии\'!{version_status_col}5:{version_status_col}1004,"черновик")-1)', "Закрыть лишний черновик"))
    rows.append(values("CHK-MATERIAL-CONTENT", "материалы", "у материала есть текст или URL", f'=COUNTIFS(\'Материалы\'!A5:A1004,"<>",\'Материалы\'!{material_content_col}5:{material_content_col}1004,"",\'Материалы\'!{material_url_col}5:{material_url_col}1004,"")', "Заполнить content_text или url"))
    rows.append(values("CHK-VERSION-POINTER", "версии", "working_version_id задан", '=IF(\'Система\'!B4="",1,0)', "Выбрать рабочую версию из списка"))
    rows.append(values("CHK-SNAPSHOT", "версии", "срез построен для рабочей версии", '=IF(OR(\'Система\'!B4="",COUNTIF(\'Срез модели\'!A5:A1004,\'Система\'!B4)>0),0,1)', "Запустить scripts/versioning/resolve.py и записать Срез модели"))
    return rows


def choose_sheet_ids(existing_ids: set[int], count: int) -> tuple[int, list[int]]:
    candidate = FIRST_SHEET_ID
    while candidate in existing_ids:
        candidate += 1000
    temp_id = candidate
    result: list[int] = []
    candidate += 1
    while len(result) < count:
        if candidate not in existing_ids:
            result.append(candidate)
        candidate += 1
    return temp_id, result


def build(
    schema: dict[str, Any],
    existing_ids: list[int],
    existing_named_range_ids: list[str],
    title: str,
) -> dict[str, Any]:
    order = schema["sheet_order"]
    temp_id, allocated = choose_sheet_ids(set(existing_ids), len(order))
    sheet_ids = dict(zip(order, allocated, strict=True))
    default = schema["default_table"]
    requests: list[dict[str, Any]] = [
        {
            "updateSpreadsheetProperties": {
                "properties": {
                    "title": title,
                    "locale": schema["physical_contract"]["spreadsheet_locale"],
                    "timeZone": schema["physical_contract"]["time_zone"],
                },
                "fields": "title,locale,timeZone",
            }
        },
        {"addSheet": {"properties": {"sheetId": temp_id, "title": TEMP_SHEET_TITLE, "gridProperties": {"rowCount": 10, "columnCount": 5}}}},
    ]
    # Named ranges are spreadsheet-scoped and survive deletion of their source
    # sheets. Remove them first so an exact rebuild cannot fail on duplicate
    # enum_* / selector_* names or leave dangling #REF catalogs behind.
    requests.extend(
        {"deleteNamedRange": {"namedRangeId": named_range_id}}
        for named_range_id in existing_named_range_ids
    )
    requests.extend({"deleteSheet": {"sheetId": sheet_id}} for sheet_id in existing_ids)

    helper_columns: dict[str, int] = {}
    enum_base = 50
    for index, sheet_name in enumerate(order):
        sheet = schema["sheets"][sheet_name]
        columns = sheet.get("columns", [])
        helper_column = max(len(columns) + 2, 36)
        helper_columns[sheet_name] = helper_column
        required_columns = enum_base + len(schema["enums"]) + 2 if sheet_name == "Система" else helper_column + 2
        row_count = 200 if sheet_name in {"Инструкция", "Рабочая панель"} else int(default["data_end_row"]) + 1
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": sheet_ids[sheet_name],
                        "title": sheet_name,
                        "index": index,
                        "gridProperties": {
                            "rowCount": row_count,
                            "columnCount": max(10, len(columns), required_columns),
                            "frozenRowCount": int(sheet.get("freeze_rows", default["freeze_rows"])) if columns else 0,
                            "hideGridlines": True,
                        },
                    }
                }
            }
        )
    requests.append({"deleteSheet": {"sheetId": temp_id}})

    # Hidden enum registries on Система and named ranges.
    system_id = sheet_ids["Система"]
    for enum_index, (enum_name, enum_values) in enumerate(schema["enums"].items()):
        column = enum_base + enum_index
        requests.append(update_block(system_id, 0, column, [row([enum_name])] + [row([value]) for value in enum_values]))
        requests.append(
            {
                "addNamedRange": {
                    "namedRange": {
                        "name": f"enum_{enum_name}",
                        "range": {"sheetId": system_id, "startRowIndex": 1, "endRowIndex": 1 + len(enum_values), "startColumnIndex": column, "endColumnIndex": column + 1},
                    }
                }
            }
        )
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {"sheetId": system_id, "dimension": "COLUMNS", "startIndex": enum_base, "endIndex": enum_base + len(schema["enums"])},
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }
    )

    selector_names: dict[str, str] = {}
    for index, sheet_name in enumerate(order):
        sheet = schema["sheets"][sheet_name]
        columns = sheet.get("columns", [])
        sheet_id = sheet_ids[sheet_name]
        static_rows = sheet_static_rows(schema, sheet_name, sheet)
        if static_rows:
            requests.append(update_block(sheet_id, 0, 0, static_rows))
        requests.extend(layout_requests(schema, sheet_name, sheet_id))
        if sheet_name == "Схема шаблона":
            rows = schema_registry_rows(schema)
            if rows:
                requests.append(update_block(sheet_id, int(default["data_start_row"]) - 1, 0, rows))
        if sheet_name == "Проверки":
            requests.append(update_block(sheet_id, int(default["data_start_row"]) - 1, 0, check_rows(schema, sheet)))

        if columns:
            header_row = int(sheet.get("header_row", default["header_row"])) - 1
            data_start = int(sheet.get("data_start_row", default["data_start_row"])) - 1
            data_end = int(default["data_end_row"])
            required = set(sheet.get("required", []))
            requests.append({"setBasicFilter": {"filter": {"range": {"sheetId": sheet_id, "startRowIndex": header_row, "endRowIndex": data_end, "startColumnIndex": 0, "endColumnIndex": len(columns)}}}})

            # Empty capacity rows stay visually empty. A started row inherits
            # the selected working version after its stable ID is entered.
            if sheet.get("kind") in {"versioned_authoring", "versioned_authoring_with_settings"} and "version_id" in columns:
                version_column = columns.index("version_id")
                requests.append(
                    {
                        "repeatCell": {
                            "range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": version_column, "endColumnIndex": version_column + 1},
                            "cell": {"userEnteredValue": {"formulaValue": version_id_formula(data_start + 1)}},
                            "fields": "userEnteredValue",
                        }
                    }
                )

            for field, enum_name in sheet.get("enums", {}).items():
                if field not in columns:
                    continue
                column_index = columns.index(field)
                requests.append(
                    {
                        "setDataValidation": {
                            "range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": column_index, "endColumnIndex": column_index + 1},
                            "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"=enum_{enum_name}"}]}, "strict": True, "showCustomUi": True},
                        }
                    }
                )

            if required:
                required_refs = [f"{column_letter(columns.index(name))}{data_start + 1}=\"\"" for name in required if name in columns]
                if required_refs:
                    formula = f"=AND($A{data_start + 1}<>\"\",OR({','.join(required_refs)}))"
                    requests.append(
                        {
                            "addConditionalFormatRule": {
                                "rule": {
                                    "ranges": [{"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": 0, "endColumnIndex": len(columns)}],
                                    "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]}, "format": {"backgroundColor": rgb(default["invalid_fill"])}},
                                },
                                "index": 0,
                            }
                        }
                    )

            if sheet.get("write_mode") == "generated" or sheet.get("kind") == "computed_registry":
                requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": 0, "endColumnIndex": len(columns)}, "description": "generated v0.2 range", "warningOnly": True}}})

        # Build one hidden, named selector catalog per source sheet.
        if columns or sheet_name == "Срез модели":
            helper_column = helper_columns[sheet_name]
            start_row_number = int(sheet.get("data_start_row", default["data_start_row"]))
            formula = selector_catalog_formula(schema, sheet_name, sheet, start_row_number)
            requests.append(update_block(sheet_id, start_row_number - 1, helper_column, [row([cell(formula=formula)])]))
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": helper_column, "endIndex": helper_column + 1}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
            requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": start_row_number - 1, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column, "endColumnIndex": helper_column + 1}, "description": "selector catalog v0.2", "warningOnly": True}}})
            selector_name = f"selector_{index + 1:02d}"
            selector_names[sheet_name] = selector_name
            requests.append({"addNamedRange": {"namedRange": {"name": selector_name, "range": {"sheetId": sheet_id, "startRowIndex": start_row_number - 1, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column, "endColumnIndex": helper_column + 1}}}})

    # Selector dropdowns and formulas are added after all named catalogs are declared.
    for sheet_name in order:
        sheet = schema["sheets"][sheet_name]
        columns = sheet.get("columns", [])
        if not columns:
            continue
        sheet_id = sheet_ids[sheet_name]
        data_start = int(sheet.get("data_start_row", default["data_start_row"])) - 1
        data_end = int(default["data_end_row"])
        for field, selector in sheet.get("selectors", {}).items():
            if field in sheet.get("settings", {}):
                if sheet_name == "Система" and field in {"working_version_id", "current_version_id"}:
                    row_index = 3 if field == "working_version_id" else 4
                    requests.append({"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 2, "endColumnIndex": 3}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={selector_names['Версии']}"}]}, "strict": True, "showCustomUi": True}}})
                continue
            if field not in columns or selector not in columns:
                continue
            target = sheet.get("foreign_keys", {}).get(field)
            if not target:
                if field in sheet.get("polymorphic_foreign_keys", {}):
                    target_sheet = "Срез модели"
                else:
                    continue
            else:
                target_sheet = selector_source_sheet(target)
            source_name = selector_names.get(target_sheet)
            if not source_name:
                continue
            field_column = columns.index(field)
            selector_column = columns.index(selector)
            requests.append({"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": selector_column, "endColumnIndex": selector_column + 1}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={source_name}"}]}, "strict": True, "showCustomUi": True}}})
            requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "cell": {"userEnteredValue": {"formulaValue": id_formula(selector_column, data_start + 1)}}, "fields": "userEnteredValue"}})
            requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "description": f"ID из selector {selector}", "warningOnly": True}}})

    # Dashboard selectors use the same readable catalogs.
    dashboard_id = sheet_ids["Рабочая панель"]
    for row_index, target_sheet in ((2, "Версии"), (3, "Система"), (4, "Процессы")):
        requests.append({"setDataValidation": {"range": {"sheetId": dashboard_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": 2}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={selector_names[target_sheet]}"}]}, "strict": True, "showCustomUi": True}}})
    requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": dashboard_id}, "description": "Рабочая панель: редактировать только selectors B3:B5", "warningOnly": True}}})

    # Visible error styling on Проверки.
    checks = schema["sheets"]["Проверки"]
    checks_id = sheet_ids["Проверки"]
    status_column = checks["columns"].index("status")
    requests.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": checks_id, "startRowIndex": 4, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": 0, "endColumnIndex": len(checks["columns"])}], "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f"=${column_letter(status_column)}5<>\"OK\""}]}, "format": {"backgroundColor": rgb(default["invalid_fill"])}}}, "index": 0}})

    fingerprint = hashlib.sha256(json.dumps(requests, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema_version": schema["schema_version"],
        "spreadsheet_title": title,
        "sheet_ids": sheet_ids,
        "request_count": len(requests),
        "batch_fingerprint": fingerprint,
        "verification_ranges": [f"{quoted_sheet(name)}!A1:{column_letter(max(0, len(schema['sheets'][name].get('columns', [])) - 1))}12" for name in order if schema["sheets"][name].get("columns")],
        "requests": requests,
    }


def validate_batch(payload: dict[str, Any]) -> None:
    requests = payload["requests"]
    for index, request in enumerate(requests):
        if not isinstance(request, dict) or len(request) != 1:
            raise ValueError(f"request[{index}] должен иметь ровно один request-type key")
        if "updateCells" in request:
            body = request["updateCells"]
            grid_range = body["range"]
            rows = body.get("rows", [])
            expected_height = grid_range["endRowIndex"] - grid_range["startRowIndex"]
            expected_width = grid_range["endColumnIndex"] - grid_range["startColumnIndex"]
            if len(rows) != expected_height:
                raise ValueError(f"request[{index}] updateCells height mismatch")
            if any(len(row_data.get("values", [])) != expected_width for row_data in rows):
                raise ValueError(f"request[{index}] updateCells width mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-sheet-ids", default="", help="Список текущих numeric sheetId через запятую")
    parser.add_argument(
        "--existing-named-range-ids",
        default="",
        help="Список текущих namedRangeId через запятую; обязателен для повторной точной сборки v0.2",
    )
    parser.add_argument("--title", default="Шаблон канонической модели бизнеса — v0.2")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", action="store_true", help="Не выводить requests, только параметры сборки")
    parser.add_argument("--request-start", type=int, default=0, help="Первый request для частичного применения")
    parser.add_argument("--request-limit", type=int, help="Число requests для частичного применения")
    parser.add_argument("--only-formulas", action="store_true", help="Вывести только requests, содержащие formulaValue")
    args = parser.parse_args()

    existing_ids = [int(value) for value in args.existing_sheet_ids.split(",") if value.strip()]
    existing_named_range_ids = [
        value.strip()
        for value in args.existing_named_range_ids.split(",")
        if value.strip()
    ]
    payload = build(load_schema(), existing_ids, existing_named_range_ids, args.title)
    validate_batch(payload)
    if args.only_formulas:
        payload["requests"] = [request for request in payload["requests"] if "formulaValue" in json.dumps(request, ensure_ascii=False)]
        payload["formula_request_count"] = len(payload["requests"])
    if args.request_start or args.request_limit is not None:
        start = max(0, args.request_start)
        stop = None if args.request_limit is None else start + max(0, args.request_limit)
        payload["requests"] = payload["requests"][start:stop]
        payload["request_slice"] = {"start": start, "end": start + len(payload["requests"])}
    if args.summary:
        payload = {key: value for key, value in payload.items() if key != "requests"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
