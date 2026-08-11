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
    "Позиции контрактов": "Отдельно принимаемые и рассчитываемые продукты или материалы внутри контрактов.",
    "Интерфейсы передачи": "Способы и условия передачи продуктов или материалов через внешнюю границу бизнеса.",
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
    "versioned_authoring": "Начните строку со стабильного ID. Версия подставится автоматически; связи выбирайте по понятным названиям. source_locator — читаемая ссылка на исходный документ и точное место в нём.",
    "append_only_governance": "Лист заполняется при подтверждённой записи и не редактируется задним числом.",
    "computed_registry": "Лист собирается автоматически. Чтобы исправить результат, измените исходные данные, а затем пересоберите представление.",
    "derived_artifact_registry": "Одна строка описывает одну проверенную сборку представления, а не отдельную версию бизнес-модели.",
}

HELP_BY_SHEET = {
    "Продукты": "Одна строка = один тип продукта, а не отдельный лид или событие. Внутренний производитель задаётся связью «система → производит → продукт»; внешний поставщик — входящей позицией контракта.",
    "Материалы": "Одна строка = один переиспользуемый материал. Конкретное отправленное сообщение или заполненный документ относится к данным исполнения, а не к этому каталогу.",
    "Позиции контрактов": "Выберите ровно один компонент: продукт или материал. Направление «входящая» означает получение от контрагента; «исходящая» — поставку контрагенту.",
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

HEADER_NOTES = {
    "version_operation": "Применить — добавить или обновить редакцию в этой версии; исключить — убрать элемент из среза этой и следующих версий.",
    "source_locator": "Читаемая ссылка на точное место в источнике: документ, лист и строка или диапазон. Не показывать пользователю внутреннюю служебную строку вместо понятной подписи.",
    "last_reviewed": "Дата последней смысловой проверки записи. Отображается как день.месяц.год.",
}


DASHBOARD_V3_SECTIONS = (
    # title, zero-based row, zero-based column, width, visible table headers
    ("Паспорт системы", 6, 0, 6, ("system_id", "Название", "Назначение", "Владелец", "Статус знания")),
    ("Продукты системы", 17, 0, 6, ("product_id", "Продукт", "Определение", "Критерии приёмки", "Владелец")),
    ("Паспорт процесса", 6, 7, 6, ("process_id", "Процесс", "Цель", "Триггер", "Вход", "Выход")),
    ("Вложенные процессы", 19, 7, 6, ("process_id", "Процесс", "Цель", "Статус исполнения", "Владелец")),
    ("Действия выбранного процесса", 6, 14, 8, ("action_id", "Действие", "Тип", "Назначение", "Вход", "Выход", "Ответственный", "Срок")),
    ("Связи действий", 124, 14, 8, ("edge_id", "Откуда", "Куда", "Тип", "Условие", "Ветка", "По умолчанию", "Приоритет")),
    ("Переходы состояний", 169, 14, 8, ("transition_id", "Действие", "Объект", "До", "После", "Триггер", "Условие", "Свидетельство")),
    ("Основной объект", 6, 23, 8, ("object_id", "Объект", "Тип", "Определение", "Идентичность", "Создание", "Завершение", "Статус")),
    ("Состояния основного объекта", 23, 23, 8, ("state_id", "Состояние", "Определение", "Конечное", "Допустимые действия")),
    ("Материалы процесса", 69, 23, 8, ("Действие", "material_id", "Материал", "Роль", "Как используется")),
    ("Внешние компоненты и контракты", 149, 23, 8, ("Контрагент", "Направление", "Компонент", "Контракт", "Интерфейс", "Документ", "Действие приёмки")),
    ("Проверки", 6, 32, 7, ("check_id", "Категория", "Уровень", "Проверка", "Статус", "Затронуто", "Что сделать")),
    ("BPMN / SVG", 34, 32, 7, ("build_id", "Готовность", "Построено", "Fingerprint", "BPMN", "SVG", "Среда")),
    ("Связано с выбранным процессом", 64, 32, 7, ("Тип", "ID", "Название", "Статус", "Ответственный", "Следующий шаг", "Срок")),
    ("Влияет на систему в целом", 169, 32, 7, ("Тип", "ID", "Название", "Статус", "Ответственный", "Следующий шаг", "Срок")),
)


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


def number_format(sheet_id: int, start_row: int, end_row: int, column: int, pattern: str) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": column,
                "endColumnIndex": column + 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {
                        "type": "DATE_TIME" if "hh" in pattern else "DATE",
                        "pattern": pattern,
                    }
                }
            },
            "fields": "userEnteredFormat.numberFormat",
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


def selector_catalog_formulas(schema: dict[str, Any], sheet_name: str, sheet: dict[str, Any], start_row: int) -> tuple[str, str]:
    kind = sheet.get("kind")
    if kind in {"versioned_authoring", "versioned_authoring_with_settings"}:
        return (
            "=ARRAYFORMULA(IFERROR(FILTER(REGEXREPLACE('Срез модели'!$E$5:$E$1004,"
            '" \\[id=[^\\]]+\\]$",""),'
            f"'Срез модели'!$C$5:$C$1004=\"{sheet_name}\"),\"\"))",
            "=ARRAYFORMULA(IFERROR(FILTER('Срез модели'!$D$5:$D$1004,"
            f"'Срез модели'!$C$5:$C$1004=\"{sheet_name}\"),\"\"))",
        )
    if sheet_name == "Срез модели":
        return (
            '=ARRAYFORMULA(IF($E$5:$E$1004="","",REGEXREPLACE($E$5:$E$1004," \\[id=[^\\]]+\\]$","")))',
            '=ARRAYFORMULA(IF($D$5:$D$1004="","",$D$5:$D$1004))',
        )
    columns = sheet.get("columns", [])
    if not columns:
        return '=\"\"', '=\"\"'
    id_col = column_letter(0)
    label_field = display_field(sheet_name, sheet)
    label_col = column_letter(columns.index(label_field)) if label_field in columns else id_col
    return (
        f"=ARRAYFORMULA(IF(${id_col}${start_row}:${id_col}$1004=\"\",\"\","
        f"${label_col}${start_row}:${label_col}$1004))",
        f"=ARRAYFORMULA(IF(${id_col}${start_row}:${id_col}$1004=\"\",\"\","
        f"${id_col}${start_row}:${id_col}$1004))",
    )


def dashboard_selector_catalog_formulas(schema: dict[str, Any]) -> tuple[str, str, str, str]:
    """Зависимые каталоги: версия → система → процесс для панели v0.3."""
    snapshot_version = field_range(schema, "Срез модели", "selected_version_id")
    snapshot_type = field_range(schema, "Срез модели", "entity_type")
    snapshot_id = field_range(schema, "Срез модели", "stable_id")
    snapshot_label = field_range(schema, "Срез модели", "entity_selector")
    snapshot_status = field_range(schema, "Срез модели", "resolution_status")
    clean_label = f'REGEXREPLACE({snapshot_label}," \\[id=[^\\]]+\\]$","")'
    system_condition = (
        f'({snapshot_version}=$E$3)*({snapshot_type}="Система")*({snapshot_status}="разрешено")'
    )
    system_labels = f'=ARRAYFORMULA(IFERROR(FILTER({clean_label},{system_condition}),""))'
    system_ids = f'=ARRAYFORMULA(IFERROR(FILTER({snapshot_id},{system_condition}),""))'

    process_ids = field_range(schema, "Процессы", "process_id")
    process_systems = field_range(schema, "Процессы", "system_id")
    allowed_process_ids = (
        f'IFERROR(FILTER({process_ids},{process_systems}=$E$4,{resolved_condition(schema, "Процессы")}),"__none__")'
    )
    process_condition = (
        f'({snapshot_version}=$E$3)*({snapshot_type}="Процессы")*'
        f'({snapshot_status}="разрешено")*'
        f'ARRAYFORMULA(ISNUMBER(MATCH({snapshot_id},{allowed_process_ids},0)))'
    )
    process_labels = f'=ARRAYFORMULA(IFERROR(FILTER({clean_label},{process_condition}),""))'
    process_catalog_ids = f'=ARRAYFORMULA(IFERROR(FILTER({snapshot_id},{process_condition}),""))'
    return system_labels, system_ids, process_labels, process_catalog_ids


def selector_source_sheet(target: str) -> str:
    return target.split(".", 1)[0]


def selector_range_names(schema: dict[str, Any], sheet_name: str) -> tuple[str, str]:
    index = schema["sheet_order"].index(sheet_name) + 1
    base = f"selector_{index:02d}"
    return base, f"{base}_ids"


def id_formula(selector_column: int, row_number: int, labels_range: str, ids_range: str) -> str:
    selector = f"{column_letter(selector_column)}{row_number}"
    return f'=IF({selector}="","",XLOOKUP({selector},{labels_range},{ids_range},""))'


def polymorphic_selector_formula(
    schema: dict[str, Any],
    specification: dict[str, Any],
    columns: list[str],
    selector_column: int,
    row_number: int,
) -> tuple[str, str]:
    """Вернуть динамический диапазон dropdown и ID-формулу для выбранного типа."""
    type_field = specification["type_field"]
    type_cell = f"${column_letter(columns.index(type_field))}{row_number}"
    selector_cell = f"{column_letter(selector_column)}{row_number}"
    range_cases: list[str] = []
    id_cases: list[str] = []
    for type_value, target in specification["targets"].items():
        target_sheet = selector_source_sheet(target)
        labels, ids = selector_range_names(schema, target_sheet)
        escaped = str(type_value).replace('"', '""')
        range_cases.extend((f'"{escaped}"', f'"{labels}"'))
        id_cases.extend(
            (
                f'"{escaped}"',
                f'XLOOKUP({selector_cell},{labels},{ids},"")',
            )
        )
    validation_range = f'=INDIRECT(SWITCH({type_cell},{",".join(range_cases)},"selector_empty_v03"))'
    id_value = f'=IF({selector_cell}="","",SWITCH({type_cell},{",".join(id_cases)},""))'
    return validation_range, id_value


def version_id_formula(row_number: int) -> str:
    """Показывать рабочую версию только для начатой authoring-строки."""
    return f'=IF($A{row_number}="","",\'Система\'!$B$4)'


def field_range(schema: dict[str, Any], sheet_name: str, field: str) -> str:
    columns = schema["sheets"][sheet_name]["columns"]
    letter = column_letter(columns.index(field))
    return f"{quoted_sheet(sheet_name)}!${letter}$5:${letter}$1004"


def resolved_condition(
    schema: dict[str, Any],
    sheet_name: str,
    selected_version_ref: str = "$E$3",
) -> str:
    """Google Sheets array-condition: raw revision belongs to selected snapshot."""
    stable = field_range(schema, sheet_name, schema["sheets"][sheet_name]["columns"][0])
    version = field_range(schema, sheet_name, "version_id")
    snapshot_type = field_range(schema, "Срез модели", "entity_type")
    snapshot_id = field_range(schema, "Срез модели", "stable_id")
    snapshot_version = field_range(schema, "Срез модели", "source_version_id")
    snapshot_selected = field_range(schema, "Срез модели", "selected_version_id")
    raw_key = f'"{sheet_name}|"&{stable}&"|"&{version}'
    snapshot_key = f'{snapshot_type}&"|"&{snapshot_id}&"|"&{snapshot_version}'
    return (
        "ARRAYFORMULA(ISNUMBER(MATCH("
        f"{raw_key},IFERROR(FILTER({snapshot_key},{snapshot_selected}={selected_version_ref}),\"__none__\"),0)))"
    )


def dashboard_filter_formula(
    schema: dict[str, Any],
    sheet_name: str,
    fields: tuple[str, ...],
    condition: str,
    limit: int,
    *,
    required_selector: str = "$E$3",
    resolved: bool = True,
) -> str:
    output = ",".join(field_range(schema, sheet_name, field) for field in fields)
    snapshot_condition = resolved_condition(schema, sheet_name) if resolved else "TRUE"
    return (
        f'=IF({required_selector}="","Сначала выберите значение",'
        f'IFERROR(ARRAY_CONSTRAIN(FILTER({{{output}}},{snapshot_condition},{condition}),{limit},{len(fields)}),'
        '"Нет связанных записей"))'
    )


def selected_process_field(schema: dict[str, Any], field: str) -> str:
    value_range = field_range(schema, "Процессы", field)
    process_ids = field_range(schema, "Процессы", "process_id")
    resolved = resolved_condition(schema, "Процессы")
    return f'IFERROR(INDEX(FILTER({value_range},{process_ids}=$E$5,{resolved}),1),"")'


def selected_action_ids(schema: dict[str, Any]) -> str:
    action_ids = field_range(schema, "Действия", "action_id")
    process_ids = field_range(schema, "Действия", "process_id")
    resolved = resolved_condition(schema, "Действия")
    return f'IFERROR(FILTER({action_ids},{process_ids}=$E$5,{resolved}),"__none__")'


def selected_state_ids(schema: dict[str, Any]) -> str:
    state_ids = field_range(schema, "Состояния", "state_id")
    object_ids = field_range(schema, "Состояния", "object_id")
    return (
        f'IFERROR(FILTER({state_ids},{object_ids}={selected_process_field(schema, "work_object_id")},'
        f'{resolved_condition(schema, "Состояния")}),"__none__")'
    )


def selected_product_ids(schema: dict[str, Any]) -> str:
    product_ids = field_range(schema, "Продукты", "product_id")
    primary_objects = field_range(schema, "Продукты", "primary_object_id")
    required_states = field_range(schema, "Продукты", "required_state_id")
    condition = (
        f'(({primary_objects}={selected_process_field(schema, "work_object_id")})+'
        f'ARRAYFORMULA(ISNUMBER(MATCH({required_states},{selected_state_ids(schema)},0))))>0'
    )
    return f'IFERROR(FILTER({product_ids},{condition},{resolved_condition(schema, "Продукты")}),"__none__")'


def selected_material_ids(schema: dict[str, Any]) -> str:
    link_from = field_range(schema, "Связи модели", "from_entity_id")
    link_relation = field_range(schema, "Связи модели", "relation_type")
    link_to = field_range(schema, "Связи модели", "to_entity_id")
    material_ids = field_range(schema, "Материалы", "material_id")
    resolved_materials = f'IFERROR(FILTER({material_ids},{resolved_condition(schema, "Материалы")}),"__none__")'
    return (
        f'IFERROR(FILTER({link_to},{resolved_condition(schema, "Связи модели")},{link_relation}="использует",'
        f'ARRAYFORMULA(ISNUMBER(MATCH({link_from},{selected_action_ids(schema)},0))),'
        f'ARRAYFORMULA(ISNUMBER(MATCH({link_to},{resolved_materials},0)))),"__none__")'
    )


def selected_metric_ids(schema: dict[str, Any]) -> str:
    link_from = field_range(schema, "Связи модели", "from_entity_id")
    link_relation = field_range(schema, "Связи модели", "relation_type")
    link_to = field_range(schema, "Связи модели", "to_entity_id")
    element_ids = field_range(schema, "Элементы модели", "element_id")
    element_types = field_range(schema, "Элементы модели", "element_type")
    metric_ids = (
        f'IFERROR(FILTER({element_ids},{element_types}="показатель",'
        f'{resolved_condition(schema, "Элементы модели")}),"__none__")'
    )
    local_ids = (
        f'{{$E$5;{selected_process_field(schema, "work_object_id")};{selected_action_ids(schema)};'
        f'{selected_state_ids(schema)};{selected_product_ids(schema)};{selected_material_ids(schema)}}}'
    )
    return (
        f'IFERROR(FILTER({link_to},{resolved_condition(schema, "Связи модели")},{link_relation}="измеряется",'
        f'ARRAYFORMULA(ISNUMBER(MATCH({link_from},{local_ids},0))),'
        f'ARRAYFORMULA(ISNUMBER(MATCH({link_to},{metric_ids},0)))),"__none__")'
    )


def development_rows_formula(schema: dict[str, Any], *, system_wide: bool, limit: int) -> str:
    action_ids = selected_action_ids(schema)
    process_object = selected_process_field(schema, "work_object_id")
    state_ids = selected_state_ids(schema)
    product_ids = selected_product_ids(schema)
    material_ids = selected_material_ids(schema)
    metric_ids = selected_metric_ids(schema)

    def block(
        sheet_name: str,
        kind: str,
        id_field: str,
        title_field: str,
        status_field: str,
        responsible_field: str,
        next_field: str,
        due_field: str,
        closed_values: tuple[str, ...],
    ) -> str:
        row_ids = field_range(schema, sheet_name, id_field)
        scope_type = field_range(schema, sheet_name, "scope_type")
        scope_id = field_range(schema, sheet_name, "scope_element_id")
        status = field_range(schema, sheet_name, status_field)
        if system_wide:
            scope = f'({scope_type}="производственная система")*({scope_id}=$E$4)'
        else:
            scope = (
                f'((({scope_type}="процесс")*({scope_id}=$E$5))+'
                f'(({scope_type}="объект")*({scope_id}={process_object}))+'
                f'(({scope_type}="действие")*ARRAYFORMULA(ISNUMBER(MATCH({scope_id},{action_ids},0))))+'
                f'(({scope_type}="состояние")*ARRAYFORMULA(ISNUMBER(MATCH({scope_id},{state_ids},0))))+'
                f'(({scope_type}="продукт")*ARRAYFORMULA(ISNUMBER(MATCH({scope_id},{product_ids},0))))+'
                f'(({scope_type}="материал")*ARRAYFORMULA(ISNUMBER(MATCH({scope_id},{material_ids},0))))+'
                f'(({scope_type}="показатель")*ARRAYFORMULA(ISNUMBER(MATCH({scope_id},{metric_ids},0)))))>0'
            )
        if closed_values:
            pattern = "|".join(re.escape(value) for value in closed_values)
            open_condition = f'NOT(REGEXMATCH({status},"^({pattern})$"))'
        else:
            open_condition = f'{status}<>""'
        columns = ",".join(
            (
                f'IF({row_ids}<>"","{kind}","")',
                row_ids,
                field_range(schema, sheet_name, title_field),
                status,
                field_range(schema, sheet_name, responsible_field),
                field_range(schema, sheet_name, next_field),
                field_range(schema, sheet_name, due_field),
            )
        )
        return f'IFERROR(FILTER({{{columns}}},{row_ids}<>"",{scope},{open_condition}),{{"","","","","","",""}})'

    blocks = (
        block("Отклонения", "Отклонение", "deviation_id", "deviation_title", "deviation_status", "responsible_position_selector", "next_step", "due_date", ("закрыто", "не подтверждено")),
        block("Гипотезы", "Гипотеза", "hypothesis_id", "hypothesis_title", "hypothesis_status", "responsible_position_selector", "next_step", "due_date", ("закрыта",)),
        block("Эксперименты", "Эксперимент", "experiment_id", "experiment_title", "experiment_status", "responsible_position_selector", "next_step", "due_date", ("завершён", "остановлен")),
    )
    required = "$E$4" if system_wide else "$E$5"
    stacked = ";".join(blocks)
    return (
        f'=IF({required}="","Сначала выберите значение",'
        f'IFERROR(ARRAY_CONSTRAIN(QUERY({{{stacked}}},"select * where Col2 is not null",0),{limit},7),'
        '"Нет связанных записей"))'
    )


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
    dashboard_v3 = sheet_name == "Рабочая панель" and schema.get("schema_version") == "0.3"
    column_count = 8 if sheet_name == "Инструкция" else 39 if dashboard_v3 else 14 if sheet_name == "Рабочая панель" else max(1, len(columns))
    row_count = 260 if dashboard_v3 else 200 if sheet_name in {"Инструкция", "Рабочая панель"} else int(default["data_end_row"]) + 1
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

    if dashboard_v3:
        requests.extend(
            [
                merge_range(sheet_id, 0, 1, 0, 39),
                merge_range(sheet_id, 1, 2, 0, 39),
                repeat_format(sheet_id, 0, 1, 0, 39, visual_format("#D9EAF7", "#1F4E78", size=16, bold=True)),
                repeat_format(sheet_id, 1, 2, 0, 39, visual_format("#FFFFFF", "#455A64", italic=True)),
                repeat_format(sheet_id, 2, 5, 0, 1, visual_format("#BDD7EE", "#1F4E78", bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 1, 2, visual_format("#F3F9FD", bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 3, 4, visual_format("#F2F2F2", "#546E7A", size=9, bold=True, borders=True)),
                repeat_format(sheet_id, 2, 5, 4, 5, visual_format("#F5F7F8", "#455A64", borders=True)),
                dimension_size(sheet_id, "ROWS", 0, 1, 42),
                dimension_size(sheet_id, "ROWS", 1, 2, 38),
                dimension_size(sheet_id, "ROWS", 2, 5, 36),
            ]
        )
        for _title, section_row, section_column, section_width, headers in DASHBOARD_V3_SECTIONS:
            requests.extend(
                [
                    merge_range(sheet_id, section_row, section_row + 1, section_column, section_column + section_width),
                    repeat_format(sheet_id, section_row, section_row + 1, section_column, section_column + section_width, visual_format("#BDD7EE", "#1F4E78", size=11, bold=True, borders=True)),
                    repeat_format(sheet_id, section_row + 1, section_row + 2, section_column, section_column + len(headers), visual_format("#EAF4FB", "#1F4E78", size=9, bold=True, horizontal="CENTER", borders=True)),
                    repeat_format(sheet_id, section_row + 2, row_count, section_column, section_column + len(headers), visual_format("#FFFFFF", vertical="TOP", borders=True)),
                    dimension_size(sheet_id, "ROWS", section_row, section_row + 1, 32),
                    dimension_size(sheet_id, "ROWS", section_row + 1, section_row + 2, 42),
                ]
            )
        for start, end, pixels in (
            (0, 6, 150),
            (6, 7, 24),
            (7, 13, 150),
            (13, 14, 24),
            (14, 22, 145),
            (22, 23, 24),
            (23, 31, 145),
            (31, 32, 24),
            (32, 39, 145),
        ):
            requests.append(dimension_size(sheet_id, "COLUMNS", start, end, pixels))
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
    computed_indices.extend(columns.index(field) for field in sheet.get("computed", []) if field in columns)
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


def dashboard_v3_rows(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Связная панель v0.3; формулы используют только выбранный resolved snapshot."""
    width = 39
    height = 260
    grid: list[list[dict[str, Any]]] = [[cell() for _ in range(width)] for _ in range(height)]

    def put(row_index: int, column_index: int, value: Any = None, *, formula: str | None = None) -> None:
        grid[row_index][column_index] = cell(value, formula=formula)

    version_labels, version_ids = selector_range_names(schema, "Версии")
    if schema.get("schema_version") == "0.3":
        system_labels, system_ids = "dashboard_system_labels_v03", "dashboard_system_ids_v03"
        process_labels, process_ids = "dashboard_process_labels_v03", "dashboard_process_ids_v03"
    else:
        system_labels, system_ids = selector_range_names(schema, "Система")
        process_labels, process_ids = selector_range_names(schema, "Процессы")
    put(0, 0, "Рабочая панель модели бизнеса v0.3")
    put(1, 0, "Выберите версию, систему и процесс. Ниже показан единый связный срез; ID остаются открытыми рядом с читаемыми названиями.")
    put(2, 0, "Версия")
    put(2, 1, "")
    put(2, 3, "selected_version_id")
    put(2, 4, formula=id_formula(1, 3, version_labels, version_ids))
    put(3, 0, "Система")
    put(3, 1, "")
    put(3, 3, "selected_system_id")
    put(3, 4, formula=id_formula(1, 4, system_labels, system_ids))
    put(4, 0, "Процесс")
    put(4, 1, "")
    put(4, 3, "selected_process_id")
    put(4, 4, formula=id_formula(1, 5, process_labels, process_ids))

    for title, section_row, section_column, _section_width, headers in DASHBOARD_V3_SECTIONS:
        put(section_row, section_column, title)
        for offset, header in enumerate(headers):
            put(section_row + 1, section_column + offset, header)

    system_condition = f'{field_range(schema, "Система", "system_id")}=$E$4'
    put(
        8,
        0,
        formula=dashboard_filter_formula(
            schema,
            "Система",
            ("system_id", "system_name", "purpose", "owner_position_selector", "knowledge_status"),
            system_condition,
            7,
            required_selector="$E$4",
        ),
    )

    link_from = field_range(schema, "Связи модели", "from_entity_id")
    link_relation = field_range(schema, "Связи модели", "relation_type")
    link_to = field_range(schema, "Связи модели", "to_entity_id")
    resolved_links = resolved_condition(schema, "Связи модели")
    produced_product_ids = (
        f'IFERROR(FILTER({link_to},{link_from}=$E$4,{link_relation}="производит",{resolved_links}),"__none__")'
    )
    product_condition = (
        f'ARRAYFORMULA(ISNUMBER(MATCH({field_range(schema, "Продукты", "product_id")},'
        f'{produced_product_ids},0)))'
    )
    put(
        19,
        0,
        formula=dashboard_filter_formula(
            schema,
            "Продукты",
            ("product_id", "product_name", "definition", "acceptance_criteria", "owner_position_selector"),
            product_condition,
            230,
            required_selector="$E$4",
        ),
    )

    process_condition = f'{field_range(schema, "Процессы", "process_id")}=$E$5'
    put(
        8,
        7,
        formula=dashboard_filter_formula(
            schema,
            "Процессы",
            ("process_id", "process_name", "goal", "trigger", "process_input", "process_output"),
            process_condition,
            9,
            required_selector="$E$5",
        ),
    )
    nested_condition = f'{field_range(schema, "Процессы", "parent_process_id")}=$E$5'
    put(
        21,
        7,
        formula=dashboard_filter_formula(
            schema,
            "Процессы",
            ("process_id", "process_name", "goal", "execution_status", "owner_position_selector"),
            nested_condition,
            228,
            required_selector="$E$5",
        ),
    )

    action_condition = f'{field_range(schema, "Действия", "process_id")}=$E$5'
    put(
        8,
        14,
        formula=dashboard_filter_formula(
            schema,
            "Действия",
            ("action_id", "action_name", "action_type", "purpose", "action_input", "action_output", "responsible_position_selector", "expected_duration"),
            action_condition,
            114,
            required_selector="$E$5",
        ),
    )
    edge_condition = f'{field_range(schema, "Связи действий", "process_id")}=$E$5'
    put(
        126,
        14,
        formula=dashboard_filter_formula(
            schema,
            "Связи действий",
            ("edge_id", "from_action_selector", "to_action_selector", "link_type", "condition_text", "branch_label", "is_default", "priority"),
            edge_condition,
            40,
            required_selector="$E$5",
        ),
    )
    transition_condition = f'{field_range(schema, "Переходы", "process_id")}=$E$5'
    put(
        171,
        14,
        formula=dashboard_filter_formula(
            schema,
            "Переходы",
            ("transition_id", "action_selector", "object_selector", "from_state_selector", "to_state_selector", "trigger_type", "condition_text", "evidence"),
            transition_condition,
            87,
            required_selector="$E$5",
        ),
    )

    process_object = selected_process_field(schema, "work_object_id")
    object_condition = f'{field_range(schema, "Объекты", "object_id")}={process_object}'
    put(
        8,
        23,
        formula=dashboard_filter_formula(
            schema,
            "Объекты",
            ("object_id", "object_name", "object_type", "definition", "identity_rule", "creation_event", "closing_event", "knowledge_status"),
            object_condition,
            12,
            required_selector="$E$5",
        ),
    )
    states_condition = f'{field_range(schema, "Состояния", "object_id")}={process_object}'
    put(
        25,
        23,
        formula=dashboard_filter_formula(
            schema,
            "Состояния",
            ("state_id", "state_name", "definition", "terminal", "allowed_actions_summary"),
            states_condition,
            41,
            required_selector="$E$5",
        ),
    )

    action_ids = selected_action_ids(schema)
    link_action_condition = f'ARRAYFORMULA(ISNUMBER(MATCH({link_from},{action_ids},0)))'
    material_ids = field_range(schema, "Материалы", "material_id")
    link_material_condition = (
        f'ARRAYFORMULA(ISNUMBER(MATCH({link_to},IFERROR(FILTER({material_ids},{resolved_condition(schema, "Материалы")}),"__none__"),0)))'
    )
    material_output = ",".join(
        (
            field_range(schema, "Связи модели", "from_entity_selector"),
            link_to,
            field_range(schema, "Связи модели", "to_entity_selector"),
            field_range(schema, "Связи модели", "relation_role"),
            field_range(schema, "Связи модели", "usage_description"),
        )
    )
    put(
        71,
        23,
        formula=(
            '=IF($E$5="","Сначала выберите процесс",'
            f'IFERROR(ARRAY_CONSTRAIN(FILTER({{{material_output}}},{resolved_links},{link_relation}="использует",'
            f'{link_action_condition},{link_material_condition}),75,5),"Нет связанных записей"))'
        ),
    )

    item_contract = field_range(schema, "Позиции контрактов", "contract_id")
    item_direction = field_range(schema, "Позиции контрактов", "direction")
    item_product = field_range(schema, "Позиции контрактов", "product_selector")
    item_material = field_range(schema, "Позиции контрактов", "material_selector")
    item_component = f'ARRAYFORMULA(IF({item_product}<>"",{item_product},{item_material}))'
    item_interface = field_range(schema, "Позиции контрактов", "interface_id")
    item_interface_selector = field_range(schema, "Позиции контрактов", "interface_selector")
    item_system = field_range(schema, "Позиции контрактов", "internal_system_id")
    resolved_items = resolved_condition(schema, "Позиции контрактов")
    contract_ids = field_range(schema, "Контракты", "contract_id")
    contract_counterparty = field_range(schema, "Контракты", "counterparty_selector")
    contract_selector = field_range(schema, "Позиции контрактов", "contract_selector")
    contract_document = field_range(schema, "Контракты", "document_url")
    resolved_contracts = resolved_condition(schema, "Контракты")
    interface_ids = field_range(schema, "Интерфейсы передачи", "interface_id")
    interface_action_id = field_range(schema, "Интерфейсы передачи", "acceptance_action_id")
    interface_action_selector = field_range(schema, "Интерфейсы передачи", "acceptance_action_selector")
    resolved_interfaces = resolved_condition(schema, "Интерфейсы передачи")
    contract_lookup_ids = f'IFERROR(FILTER({contract_ids},{resolved_contracts}),"__none__")'
    interface_lookup_ids = f'IFERROR(FILTER({interface_ids},{resolved_interfaces}),"__none__")'
    acceptance_ids = (
        f'ARRAYFORMULA(XLOOKUP({item_interface},{interface_lookup_ids},'
        f'IFERROR(FILTER({interface_action_id},{resolved_interfaces}),""),""))'
    )
    external_output = ",".join(
        (
            f'ARRAYFORMULA(XLOOKUP({item_contract},{contract_lookup_ids},IFERROR(FILTER({contract_counterparty},{resolved_contracts}),""),""))',
            item_direction,
            item_component,
            contract_selector,
            item_interface_selector,
            f'ARRAYFORMULA(XLOOKUP({item_contract},{contract_lookup_ids},IFERROR(FILTER({contract_document},{resolved_contracts}),""),""))',
            f'ARRAYFORMULA(XLOOKUP({item_interface},{interface_lookup_ids},IFERROR(FILTER({interface_action_selector},{resolved_interfaces}),""),""))',
        )
    )
    acceptance_in_process = f'ARRAYFORMULA(ISNUMBER(MATCH({acceptance_ids},{action_ids},0)))'
    put(
        151,
        23,
        formula=(
            '=IF($E$5="","Сначала выберите процесс",'
            f'IFERROR(ARRAY_CONSTRAIN(FILTER({{{external_output}}},{resolved_items},{item_system}=$E$4,'
            f'{acceptance_in_process}),105,7),"Нет связанных записей"))'
        ),
    )

    checks = schema["sheets"]["Проверки"]["columns"]
    check_output = ",".join(
        field_range(schema, "Проверки", field)
        for field in ("check_id", "category", "severity", "check_name", "status", "affected_ids", "remediation")
    )
    check_status = field_range(schema, "Проверки", "status")
    put(
        8,
        32,
        formula=f'=IFERROR(ARRAY_CONSTRAIN(FILTER({{{check_output}}},{check_status}<>"OK"),23,7),"Нет ошибок и предупреждений")',
    )
    diagram_condition = (
        f'({field_range(schema, "Диаграммы", "process_id")}=$E$5)*'
        f'({field_range(schema, "Диаграммы", "version_id")}=$E$3)'
    )
    put(
        36,
        32,
        formula=dashboard_filter_formula(
            schema,
            "Диаграммы",
            ("projection_build_id", "readiness_status", "built_at", "model_fingerprint", "bpmn_url", "svg_url", "deployed_environment"),
            diagram_condition,
            25,
            required_selector="$E$5",
            resolved=False,
        ),
    )
    put(66, 32, formula=development_rows_formula(schema, system_wide=False, limit=100))
    put(171, 32, formula=development_rows_formula(schema, system_wide=True, limit=87))

    return [{"values": values} for values in grid]


def sheet_static_rows(schema: dict[str, Any], sheet_name: str, sheet: dict[str, Any]) -> list[dict[str, Any]]:
    schema_version = schema.get("schema_version", "0.2")
    if sheet_name == "Инструкция":
        values = [
            row([f"Шаблон канонической модели бизнеса v{schema_version}"]),
            row(["Одна книга хранит каноническую модель одного бизнеса: внутренние производственные системы, продукты, ресурсы и внешние контрактные границы."]),
            row([]),
            row(["Как работать с моделью"]),
            row(["1", "Назначение", "Фиксируйте не произвольные слова, а различимые объекты, состояния, действия, материалы, системы, процессы, позиции, продукты и контрактные границы."]),
            row(["2", "Порядок заполнения", "Начните с источников и версии, затем определите системы, позиции, продукты, процессы, действия, объекты, состояния и связи."]),
            row(["3", "Интервью и подтверждение", "Сначала уточните, куда изменение встраивается, от чего зависит, какой эффект создаёт и как корректно сформулировать определение. Записывайте только после подтверждения."]),
            row(["4", "Версии", "Новая версия хранит только изменения. Неизменённые элементы продолжают действовать из предыдущей версии; история принятых определений не стирается."]),
            row(["5", "Человеко-читаемые списки", "В выпадающем списке выбирайте только понятное название. Соседний технический ID вычисляется автоматически и остаётся видимым."]),
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
        if schema_version == "0.3":
            values.insert(
                11,
                row(["8", "Развитие системы", "Отклонения возвращают систему к действующей норме, гипотезы используют новые внешние возможности, а эксперименты проверяют изменение до принятия как нормы."]),
            )
        return values
    if sheet_name == "Рабочая панель":
        if schema_version == "0.3":
            return dashboard_v3_rows(schema)
        version_labels, version_ids = selector_range_names(schema, "Версии")
        system_labels, system_ids = selector_range_names(schema, "Система")
        process_labels, process_ids = selector_range_names(schema, "Процессы")
        values = [
            row([f"Рабочая панель модели бизнеса v{schema_version}"]),
            row(["Выберите версию, систему и процесс человеко-читаемыми списками. Технический ID рассчитывается рядом и остаётся видимым."]),
            row(["Рабочая версия", "", "", "selected_version_id", cell(formula=id_formula(1, 3, version_labels, version_ids))]),
            row(["Система", "", "", "selected_system_id", cell(formula=id_formula(1, 4, system_labels, system_ids))]),
            row(["Процесс", "", "", "selected_process_id", cell(formula=id_formula(1, 5, process_labels, process_ids))]),
            row([]),
            row(["Сводные представления"]),
        ]
        for section in sheet.get("sections", []):
            values.extend([row([section]), row([])])
        return values
    header_row = int(sheet.get("header_row", schema["default_table"]["header_row"]))
    description = DESCRIPTION_BY_SHEET.get(
        sheet_name,
        DESCRIPTION_BY_KIND.get(sheet.get("kind"), f"Лист модели бизнеса v{schema_version}."),
    )
    if sheet_name == "Система":
        version_labels, version_ids = selector_range_names(schema, "Версии")
        rows = [
            row([sheet_name]),
            row([description]),
            row(["model_id", "", "Одна книга = одна модель бизнеса"]),
            row(["working_version_id", cell(formula=id_formula(2, 4, version_labels, version_ids)), "", "working_version_selector"]),
            row(["current_version_id", cell(formula=id_formula(2, 5, version_labels, version_ids)), "", "current_version_selector"]),
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

    def values(
        check_id: str,
        category: str,
        name: str,
        formula: str,
        remediation: str,
        *,
        severity: str = "критично",
        blocks_release: str = "да",
        failure_status: str = "ERROR",
    ) -> dict[str, Any]:
        result = [cell(check_id), cell(category), cell(severity), cell(name), cell(formula=formula)]
        result.append(cell(formula=f'=IF(E{5 + len(rows)}=0,"OK","{failure_status}")'))
        result.extend([cell(blocks_release), cell(""), cell(remediation)])
        return row(result)

    rows: list[dict[str, Any]] = []
    rows.append(values("CHK-MODEL-ID", "структура", "model_id заполнен", '=IF(\'Система\'!B3="",1,0)', "Заполнить Система!B3"))
    rows.append(values("CHK-ONE-DRAFT", "версии", "не более одного черновика", f'=MAX(0,COUNTIF(\'Версии\'!{version_status_col}5:{version_status_col}1004,"черновик")-1)', "Закрыть лишний черновик"))
    rows.append(values("CHK-MATERIAL-CONTENT", "материалы", "у материала есть текст или URL", f'=COUNTIFS(\'Материалы\'!A5:A1004,"<>",\'Материалы\'!{material_content_col}5:{material_content_col}1004,"",\'Материалы\'!{material_url_col}5:{material_url_col}1004,"")', "Заполнить content_text или url"))
    rows.append(values("CHK-VERSION-POINTER", "версии", "working_version_id задан", '=IF(\'Система\'!B4="",1,0)', "Выбрать рабочую версию из списка"))
    rows.append(values("CHK-SNAPSHOT", "версии", "срез построен для рабочей версии", '=IF(OR(\'Система\'!B4="",COUNTIF(\'Срез модели\'!A5:A1004,\'Система\'!B4)>0),0,1)', "Запустить scripts/versioning/resolve.py и записать Срез модели"))
    if schema.get("schema_version") == "0.3":
        deviations = schema["sheets"]["Отклонения"]["columns"]
        hypotheses = schema["sheets"]["Гипотезы"]["columns"]
        experiments = schema["sheets"]["Эксперименты"]["columns"]

        def col(items: list[str], field: str) -> str:
            return column_letter(items.index(field))

        contract_items = schema["sheets"]["Позиции контрактов"]["columns"]
        interfaces = schema["sheets"]["Интерфейсы передачи"]["columns"]
        item_id = col(contract_items, "contract_item_id")
        item_operation = col(contract_items, "version_operation")
        item_product = col(contract_items, "product_id")
        item_material = col(contract_items, "material_id")
        item_interface = col(contract_items, "interface_id")
        interface_id = col(interfaces, "interface_id")
        interface_operation = col(interfaces, "version_operation")
        interface_product = col(interfaces, "product_id")
        interface_material = col(interfaces, "material_id")
        rows.append(
            values(
                "CHK-CONTRACT-ITEM-COMPONENT",
                "контракты",
                "позиция контракта содержит ровно один компонент",
                f'=SUMPRODUCT(N(\'Позиции контрактов\'!{item_id}5:{item_id}1004<>""),N(\'Позиции контрактов\'!{item_operation}5:{item_operation}1004="применить"),N(((\'Позиции контрактов\'!{item_product}5:{item_product}1004<>"")+(\'Позиции контрактов\'!{item_material}5:{item_material}1004<>""))<>1))',
                "Выбрать продукт или материал, но не оба компонента",
            )
        )
        rows.append(
            values(
                "CHK-INTERFACE-COMPONENT",
                "контракты",
                "интерфейс передачи содержит ровно один компонент",
                f'=SUMPRODUCT(N(\'Интерфейсы передачи\'!{interface_id}5:{interface_id}1004<>""),N(\'Интерфейсы передачи\'!{interface_operation}5:{interface_operation}1004="применить"),N(((\'Интерфейсы передачи\'!{interface_product}5:{interface_product}1004<>"")+(\'Интерфейсы передачи\'!{interface_material}5:{interface_material}1004<>""))<>1))',
                "Выбрать продукт или материал, но не оба компонента",
            )
        )

        resolved_interfaces = resolved_condition(schema, "Интерфейсы передачи", "'Система'!$B$4")
        resolved_contract_items = resolved_condition(schema, "Позиции контрактов", "'Система'!$B$4")
        interface_ids = f"'Интерфейсы передачи'!{interface_id}5:{interface_id}1004"
        interface_products = f"'Интерфейсы передачи'!{interface_product}5:{interface_product}1004"
        interface_materials = f"'Интерфейсы передачи'!{interface_material}5:{interface_material}1004"
        item_interfaces = f"'Позиции контрактов'!{item_interface}5:{item_interface}1004"
        item_products = f"'Позиции контрактов'!{item_product}5:{item_product}1004"
        item_materials = f"'Позиции контрактов'!{item_material}5:{item_material}1004"
        linked_interface_product = (
            f'IFERROR(XLOOKUP({item_interfaces},FILTER({interface_ids},{resolved_interfaces}),'
            f'FILTER({interface_products},{resolved_interfaces}),""),"")'
        )
        linked_interface_material = (
            f'IFERROR(XLOOKUP({item_interfaces},FILTER({interface_ids},{resolved_interfaces}),'
            f'FILTER({interface_materials},{resolved_interfaces}),""),"")'
        )
        rows.append(
            values(
                "CHK-CONTRACT-INTERFACE-COMPONENT",
                "контракты",
                "позиция контракта и интерфейс передают один компонент",
                f'=SUMPRODUCT(N(\'Позиции контрактов\'!{item_id}5:{item_id}1004<>""),N({resolved_contract_items}),N({item_interfaces}<>""),N((({item_products}<>{linked_interface_product})+({item_materials}<>{linked_interface_material}))>0))',
                "Выбрать в позиции и связанном интерфейсе один и тот же продукт либо материал",
            )
        )

        snapshot_selected = field_range(schema, "Срез модели", "selected_version_id")
        snapshot_type = field_range(schema, "Срез модели", "entity_type")
        snapshot_id = field_range(schema, "Срез модели", "stable_id")
        snapshot_status = field_range(schema, "Срез модели", "resolution_status")
        link_to = field_range(schema, "Связи модели", "to_entity_id")
        link_from = field_range(schema, "Связи модели", "from_entity_id")
        link_relation = field_range(schema, "Связи модели", "relation_type")
        resolved_links = resolved_condition(schema, "Связи модели", "'Система'!$B$4")
        item_product_range = field_range(schema, "Позиции контрактов", "product_id")
        item_direction_range = field_range(schema, "Позиции контрактов", "direction")
        resolved_items = resolved_condition(schema, "Позиции контрактов", "'Система'!$B$4")
        resolved_products = (
            f'FILTER({snapshot_id},{snapshot_selected}=\'Система\'!$B$4,'
            f'{snapshot_type}="Продукты",{snapshot_status}="разрешено")'
        )
        resolved_systems = (
            f'IFERROR(FILTER({snapshot_id},{snapshot_selected}=\'Система\'!$B$4,'
            f'{snapshot_type}="Система",{snapshot_status}="разрешено"),"__none__")'
        )
        internal_producer = f'ISNUMBER(MATCH({link_from},{resolved_systems},0))'
        rows.append(
            values(
                "CHK-PRODUCT-ORIGIN",
                "продукты",
                "у каждого продукта явно указан хотя бы один источник происхождения",
                f'=IFERROR(SUM(MAP({resolved_products},LAMBDA(p,IF(SUMPRODUCT(N({link_to}=p),N({link_relation}="производит"),N({internal_producer}),N({resolved_links}))+SUMPRODUCT(N({item_product_range}=p),N({item_direction_range}="входящая"),N({resolved_items}))=0,1,0)))),0)',
                "Связать продукт хотя бы с одной внутренней системой-производителем или входящей позицией контракта; несколько и смешанные источники допустимы",
            )
        )

        def metric_contract_formula(
            sheet_name: str,
            status_column: str,
            base_version_column: str,
            metric_column: str,
            active_statuses: str,
        ) -> str:
            element = lambda field: field_range(schema, "Элементы модели", field)
            snapshot_version = field_range(schema, "Срез модели", "selected_version_id")
            snapshot_type = field_range(schema, "Срез модели", "entity_type")
            snapshot_id = field_range(schema, "Срез модели", "stable_id")
            snapshot_source_version = field_range(schema, "Срез модели", "source_version_id")
            source_revision = (
                f'IFERROR(XLOOKUP(v&"|"&m,FILTER({snapshot_version}&"|"&{snapshot_id},'
                f'{snapshot_type}="Элементы модели"),FILTER({snapshot_source_version},'
                f'{snapshot_type}="Элементы модели"),""),"")'
            )
            required_ranges = (
                (element("element_type"), '"показатель"'),
                (element("definition"), '"<>"'),
                (element("owner_position_id"), '"<>"'),
                (element("formula_or_rule"), '"<>"'),
                (element("unit_or_format"), '"<>"'),
                (element("source_id"), '"<>"'),
            )
            count_args = [element("element_id"), "m", element("version_id"), "mv", element("version_operation"), '"применить"']
            for item_range, criterion in required_ranges:
                count_args.extend((item_range, criterion))
            status = f"{quoted_sheet(sheet_name)}!${status_column}$5:${status_column}$1004"
            base_version = f"{quoted_sheet(sheet_name)}!${base_version_column}$5:${base_version_column}$1004"
            metric = f"{quoted_sheet(sheet_name)}!${metric_column}$5:${metric_column}$1004"
            return (
                f'=SUM(MAP({status},{base_version},{metric},LAMBDA(s,v,m,'
                f'IF(NOT(REGEXMATCH(s,"{active_statuses}")),0,IF(OR(v="",m=""),0,'
                f'LET(mv,{source_revision},IF(COUNTIFS({",".join(count_args)})=1,0,1)))))))'
            )

        def scope_resolution_formula(
            sheet_name: str,
            status_column: str,
            version_column: str,
            scope_type_column: str,
            scope_id_column: str,
            active_statuses: str,
        ) -> str:
            snapshot_version = field_range(schema, "Срез модели", "selected_version_id")
            snapshot_type = field_range(schema, "Срез модели", "entity_type")
            snapshot_id = field_range(schema, "Срез модели", "stable_id")
            snapshot_status = field_range(schema, "Срез модели", "resolution_status")
            type_cases = (
                '"действие","Действия","процесс","Процессы",'
                '"производственная система","Система","объект","Объекты",'
                '"состояние","Состояния","продукт","Продукты",'
                '"материал","Материалы","показатель","Элементы модели"'
            )
            prefix = quoted_sheet(sheet_name)
            status = f"{prefix}!${status_column}$5:${status_column}$1004"
            version = f"{prefix}!${version_column}$5:${version_column}$1004"
            scope_type = f"{prefix}!${scope_type_column}$5:${scope_type_column}$1004"
            scope_id = f"{prefix}!${scope_id_column}$5:${scope_id_column}$1004"
            return (
                f'=SUM(MAP({status},{version},{scope_type},{scope_id},LAMBDA(s,v,t,i,'
                f'IF(NOT(REGEXMATCH(s,"{active_statuses}")),0,IF(OR(v="",t="",i=""),0,'
                f'IF(COUNTIFS({snapshot_version},v,{snapshot_type},SWITCH(t,{type_cases},""),'
                f'{snapshot_id},i,{snapshot_status},"разрешено")=1,0,1))))))'
            )

        dev_status = col(deviations, "deviation_status")
        dev_type = col(deviations, "deviation_type")
        dev_scope = col(deviations, "scope_element_id")
        dev_version = col(deviations, "applicable_version_id")
        dev_norm = col(deviations, "norm_element_id")
        dev_norm_source = col(deviations, "norm_source_id")
        dev_expected = col(deviations, "expected_behavior")
        dev_responsible = col(deviations, "responsible_position_id")
        dev_decision = col(deviations, "confirmation_decision_id")
        dev_verify = col(deviations, "verification_status")
        dev_close_decision = col(deviations, "closure_decision_id")
        dev_closed_at = col(deviations, "closed_at")
        confirmed_states = r'"^(подтверждено|в устранении|проверяется|закрыто)$"'
        rows.append(
            values(
                "CHK-DEVIATION-CONFIRMED",
                "отклонения",
                "подтверждённое отклонение имеет норму, область и решение",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Отклонения\'!{dev_status}5:{dev_status}1004,{confirmed_states})),N(((\'Отклонения\'!{dev_type}5:{dev_type}1004="")+(\'Отклонения\'!{dev_type}5:{dev_type}1004="не определено")+(\'Отклонения\'!{dev_scope}5:{dev_scope}1004="")+(\'Отклонения\'!{dev_version}5:{dev_version}1004="")+(((\'Отклонения\'!{dev_norm}5:{dev_norm}1004="")*(\'Отклонения\'!{dev_norm_source}5:{dev_norm_source}1004="")))+(\'Отклонения\'!{dev_expected}5:{dev_expected}1004="")+(\'Отклонения\'!{dev_responsible}5:{dev_responsible}1004="")+(\'Отклонения\'!{dev_decision}5:{dev_decision}1004=""))>0))',
                "Заполнить действующую норму, область, тип, ответственного и человеческое решение",
            )
        )
        rows.append(
            values(
                "CHK-DEVIATION-SCOPE",
                "отклонения",
                "тип области соответствует элементу применимой версии",
                scope_resolution_formula("Отклонения", dev_status, dev_version, col(deviations, "scope_type"), dev_scope, "^(подтверждено|в устранении|проверяется|закрыто)$"),
                "Выбрать тип и элемент области из одной применимой версии",
            )
        )
        rows.append(
            values(
                "WARN-DEVIATION-CLOSE-EVIDENCE",
                "отклонения",
                "закрытие без подтверждённой результативности явно видно",
                f'=COUNTIFS(\'Отклонения\'!{dev_status}5:{dev_status}1004,"закрыто",\'Отклонения\'!{dev_verify}5:{dev_verify}1004,"<>подтверждено")+COUNTIFS(\'Отклонения\'!{dev_status}5:{dev_status}1004,"закрыто",\'Отклонения\'!{dev_close_decision}5:{dev_close_decision}1004,"")+COUNTIFS(\'Отклонения\'!{dev_status}5:{dev_status}1004,"закрыто",\'Отклонения\'!{dev_closed_at}5:{dev_closed_at}1004,"")',
                "Показать владельцу отсутствие доказательства и сохранить решение с обоснованием",
                severity="предупреждение",
                blocks_release="нет",
                failure_status="WARN",
            )
        )

        hyp_status = col(hypotheses, "hypothesis_status")
        hyp_base_version = col(hypotheses, "base_version_id")
        hyp_metric = col(hypotheses, "primary_metric_id")
        hyp_required = [
            col(hypotheses, field)
            for field in (
                "external_change",
                "source_id",
                "source_locator",
                "new_opportunity",
                "base_version_id",
                "scope_element_id",
                "proposed_change",
                "mechanism",
                "primary_metric_id",
                "baseline",
                "expected_target",
                "effect_horizon",
                "support_criterion",
                "refutation_criterion",
                "inconclusive_criterion",
                "responsible_position_id",
            )
        ]
        missing_hypothesis = "+".join(f'(\'Гипотезы\'!{letter}5:{letter}1004="")' for letter in hyp_required)
        rows.append(
            values(
                "CHK-HYPOTHESIS-FORMULATED",
                "гипотезы",
                "сформулированная гипотеза имеет источник и контракт показателя",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Гипотезы\'!{hyp_status}5:{hyp_status}1004,"^(сформулирована|проверяется|проверена|закрыта)$")),N(({missing_hypothesis})>0))',
                "Заполнить внешнее изменение, источник, механизм и полный контракт основного показателя",
            )
        )
        rows.append(
            values(
                "CHK-HYPOTHESIS-SCOPE",
                "гипотезы",
                "тип области соответствует элементу базовой версии",
                scope_resolution_formula("Гипотезы", hyp_status, hyp_base_version, col(hypotheses, "scope_type"), col(hypotheses, "scope_element_id"), "^(сформулирована|проверяется|проверена|закрыта)$"),
                "Выбрать тип и элемент области из базовой версии гипотезы",
            )
        )
        rows.append(
            values(
                "CHK-HYPOTHESIS-METRIC",
                "гипотезы",
                "основной показатель имеет полный контракт в базовой версии",
                metric_contract_formula("Гипотезы", hyp_status, hyp_base_version, hyp_metric, "^(сформулирована|проверяется|проверена|закрыта)$"),
                "Определить показатель, формулу, единицу, владельца и источник в базовой версии",
            )
        )
        hyp_evidence = col(hypotheses, "evidence_result")
        hyp_owner_decision = col(hypotheses, "owner_decision")
        hyp_owner_decision_id = col(hypotheses, "owner_decision_id")
        hyp_resulting_version = col(hypotheses, "resulting_version_id")
        hyp_closed_at = col(hypotheses, "closed_at")
        rows.append(
            values(
                "CHK-HYPOTHESIS-RESULT",
                "гипотезы",
                "проверенная гипотеза имеет результат свидетельств",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Гипотезы\'!{hyp_status}5:{hyp_status}1004,"^(проверена|закрыта)$")),N(\'Гипотезы\'!{hyp_evidence}5:{hyp_evidence}1004=""))',
                "Зафиксировать поддержана, опровергнута или неопределённо отдельно от решения владельца",
            )
        )
        rows.append(
            values(
                "CHK-HYPOTHESIS-CLOSURE",
                "гипотезы",
                "закрытая гипотеза имеет решение владельца и дату",
                f'=SUMPRODUCT(N(\'Гипотезы\'!{hyp_status}5:{hyp_status}1004="закрыта"),N(((\'Гипотезы\'!{hyp_owner_decision}5:{hyp_owner_decision}1004="")+(\'Гипотезы\'!{hyp_owner_decision_id}5:{hyp_owner_decision_id}1004="")+(\'Гипотезы\'!{hyp_closed_at}5:{hyp_closed_at}1004="")+((\'Гипотезы\'!{hyp_owner_decision}5:{hyp_owner_decision}1004="внедрить")*(\'Гипотезы\'!{hyp_resulting_version}5:{hyp_resulting_version}1004="")))>0))',
                "Записать решение владельца, decision_id и дату; для внедрения связать созданную версию",
            )
        )

        exp_id = col(experiments, "experiment_id")
        exp_status = col(experiments, "experiment_status")
        exp_dev = col(experiments, "deviation_id")
        exp_hyp = col(experiments, "hypothesis_id")
        exp_base_version = col(experiments, "base_version_id")
        exp_metric = col(experiments, "primary_metric_id")
        exp_launch_decision = col(experiments, "launch_decision_id")
        exp_actual_start = col(experiments, "actual_start")
        exp_actual_end = col(experiments, "actual_end")
        exp_result_channel = col(experiments, "result_channel")
        exp_result_source = col(experiments, "result_source_id")
        exp_result_locator = col(experiments, "result_source_locator")
        exp_actual_result = col(experiments, "actual_result")
        exp_conclusion = col(experiments, "conclusion")
        exp_implementation = col(experiments, "implementation_decision")
        exp_implementation_id = col(experiments, "implementation_decision_id")
        exp_resulting_version = col(experiments, "resulting_version_id")
        rows.append(
            values(
                "CHK-EXPERIMENT-ONE-BASIS",
                "эксперименты",
                "у эксперимента ровно одно основание",
                f'=SUMPRODUCT(N(\'Эксперименты\'!{exp_id}5:{exp_id}1004<>""),N(((\'Эксперименты\'!{exp_dev}5:{exp_dev}1004<>"")+(\'Эксперименты\'!{exp_hyp}5:{exp_hyp}1004<>""))<>1))',
                "Выбрать отклонение либо гипотезу, но не оба основания",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-SCOPE",
                "эксперименты",
                "тип области соответствует элементу базовой версии",
                scope_resolution_formula("Эксперименты", exp_status, exp_base_version, col(experiments, "scope_type"), col(experiments, "scope_element_id"), "^(подготовлен|разрешён|выполняется|завершён|остановлен)$"),
                "Выбрать тип и элемент области из базовой версии эксперимента",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-METRIC",
                "эксперименты",
                "основной показатель имеет полный контракт в базовой версии",
                metric_contract_formula("Эксперименты", exp_status, exp_base_version, exp_metric, "^(подготовлен|разрешён|выполняется|завершён|остановлен)$"),
                "Определить показатель, формулу, единицу, владельца и источник в базовой версии",
            )
        )
        prepared_fields = [
            col(experiments, field)
            for field in (
                "base_version_id",
                "scope_element_id",
                "temporary_change",
                "instances_or_volume",
                "comparison_method",
                "primary_metric_id",
                "baseline",
                "success_criterion",
                "planned_start",
                "planned_end",
                "responsible_position_id",
                "stop_condition",
                "rollback_plan",
            )
        ]
        missing_experiment = "+".join(f'(\'Эксперименты\'!{letter}5:{letter}1004="")' for letter in prepared_fields)
        rows.append(
            values(
                "CHK-EXPERIMENT-DESIGN",
                "эксперименты",
                "подготовленный эксперимент имеет минимальный дизайн",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Эксперименты\'!{exp_status}5:{exp_status}1004,"^(подготовлен|разрешён|выполняется|завершён|остановлен)$")),N(({missing_experiment})>0))',
                "Заполнить базовую версию, область, изменение, сравнение, показатель, срок, stop-условие и возврат",
            )
        )
        rows.append(
            values(
                "CHK-HYPOTHESIS-EXPERIMENTS",
                "гипотезы",
                "статус проверки гипотезы подтверждён связанными экспериментами",
                f'=SUM(MAP(\'Гипотезы\'!{hyp_status}5:{hyp_status}1004,\'Гипотезы\'!A5:A1004,LAMBDA(s,h,IF(s="проверяется",IF(COUNTIFS(\'Эксперименты\'!{exp_hyp}5:{exp_hyp}1004,h,\'Эксперименты\'!{exp_status}5:{exp_status}1004,"разрешён")+COUNTIFS(\'Эксперименты\'!{exp_hyp}5:{exp_hyp}1004,h,\'Эксперименты\'!{exp_status}5:{exp_status}1004,"выполняется")=0,1,0),IF(REGEXMATCH(s,"^(проверена|закрыта)$"),IF(COUNTIFS(\'Эксперименты\'!{exp_hyp}5:{exp_hyp}1004,h,\'Эксперименты\'!{exp_status}5:{exp_status}1004,"завершён")+COUNTIFS(\'Эксперименты\'!{exp_hyp}5:{exp_hyp}1004,h,\'Эксперименты\'!{exp_status}5:{exp_status}1004,"остановлен")=0,1,0),0)))))',
                "Связать проверяемую гипотезу с разрешённым/выполняемым экспериментом, а проверенную — с завершённым или остановленным",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-LAUNCH",
                "эксперименты",
                "разрешённый эксперимент имеет человеческое решение о запуске",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Эксперименты\'!{exp_status}5:{exp_status}1004,"^(разрешён|выполняется|завершён|остановлен)$")),N(\'Эксперименты\'!{exp_launch_decision}5:{exp_launch_decision}1004=""))',
                "Связать решение владельца о запуске до начала исполнения",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-ACTUAL-START",
                "эксперименты",
                "начатый эксперимент имеет фактическую дату начала",
                f'=SUMPRODUCT(N(REGEXMATCH(\'Эксперименты\'!{exp_status}5:{exp_status}1004,"^(выполняется|завершён|остановлен)$")),N(\'Эксперименты\'!{exp_actual_start}5:{exp_actual_start}1004=""))',
                "Зафиксировать actual_start при начале исполнения",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-COMPLETION",
                "эксперименты",
                "завершённый эксперимент имеет источник, результат и вывод",
                f'=SUMPRODUCT(N(\'Эксперименты\'!{exp_status}5:{exp_status}1004="завершён"),N(((\'Эксперименты\'!{exp_actual_end}5:{exp_actual_end}1004="")+(\'Эксперименты\'!{exp_result_channel}5:{exp_result_channel}1004="")+(\'Эксперименты\'!{exp_result_source}5:{exp_result_source}1004="")+(\'Эксперименты\'!{exp_result_locator}5:{exp_result_locator}1004="")+(\'Эксперименты\'!{exp_actual_result}5:{exp_actual_result}1004="")+(\'Эксперименты\'!{exp_conclusion}5:{exp_conclusion}1004=""))>0))',
                "Заполнить actual_end, проверяемый источник результата, фактический результат и человеческий вывод",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-STOP",
                "эксперименты",
                "остановленный эксперимент имеет дату и причину остановки",
                f'=SUMPRODUCT(N(\'Эксперименты\'!{exp_status}5:{exp_status}1004="остановлен"),N(((\'Эксперименты\'!{exp_actual_end}5:{exp_actual_end}1004="")+(\'Эксперименты\'!{exp_conclusion}5:{exp_conclusion}1004="")+((\'Эксперименты\'!{exp_actual_result}5:{exp_actual_result}1004<>"")*((\'Эксперименты\'!{exp_result_channel}5:{exp_result_channel}1004="")+(\'Эксперименты\'!{exp_result_source}5:{exp_result_source}1004="")+(\'Эксперименты\'!{exp_result_locator}5:{exp_result_locator}1004=""))))>0))',
                "Зафиксировать actual_end и причину; если есть фактический результат, указать его проверяемый источник",
            )
        )
        rows.append(
            values(
                "CHK-EXPERIMENT-IMPLEMENTATION",
                "эксперименты",
                "решение по внедрению связано с человеческим решением и версией",
                f'=SUMPRODUCT(N(\'Эксперименты\'!{exp_implementation}5:{exp_implementation}1004<>""),N(((\'Эксперименты\'!{exp_implementation_id}5:{exp_implementation_id}1004="")+((\'Эксперименты\'!{exp_implementation}5:{exp_implementation}1004="внедрить")*(\'Эксперименты\'!{exp_resulting_version}5:{exp_resulting_version}1004="")))>0))',
                "Связать implementation decision; для внедрения создать и указать обычную версию модели",
            )
        )
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
        dashboard_v3 = sheet_name == "Рабочая панель" and schema.get("schema_version") == "0.3"
        if dashboard_v3:
            required_columns = max(required_columns, 44)
        row_count = int(default["data_end_row"]) + 1 if dashboard_v3 else 200 if sheet_name in {"Инструкция", "Рабочая панель"} else int(default["data_end_row"]) + 1
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
                            "frozenColumnCount": int(sheet.get("freeze_columns", 0)) if columns else 0,
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
    if schema.get("schema_version") == "0.3":
        empty_column = enum_base + len(schema["enums"]) + 1
        requests.append(
            {
                "addNamedRange": {
                    "namedRange": {
                        "name": "selector_empty_v03",
                        "range": {
                            "sheetId": system_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": empty_column,
                            "endColumnIndex": empty_column + 1,
                        },
                    }
                }
            }
        )

    selector_names: dict[str, str] = {}
    selector_id_names: dict[str, str] = {}
    for index, sheet_name in enumerate(order):
        sheet = schema["sheets"][sheet_name]
        columns = sheet.get("columns", [])
        sheet_id = sheet_ids[sheet_name]
        static_rows = sheet_static_rows(schema, sheet_name, sheet)
        if static_rows:
            requests.append(update_block(sheet_id, 0, 0, static_rows))
        requests.extend(layout_requests(schema, sheet_name, sheet_id))
        if columns:
            header_row = int(sheet.get("header_row", default["header_row"])) - 1
            for field, note in HEADER_NOTES.items():
                if field not in columns:
                    continue
                column = columns.index(field)
                requests.append(
                    {
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": header_row,
                                "endRowIndex": header_row + 1,
                                "startColumnIndex": column,
                                "endColumnIndex": column + 1,
                            },
                            "rows": [{"values": [{"note": note}]}],
                            "fields": "note",
                        }
                    }
                )
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

            computed_fields = set(sheet.get("computed", []))
            for field, enum_name in sheet.get("enums", {}).items():
                if field not in columns:
                    continue
                if field in computed_fields:
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

            for field, field_type in sheet.get("types", {}).items():
                if field not in columns or field_type not in {"date", "datetime"}:
                    continue
                pattern = "dd.mm.yyyy hh:mm" if field_type == "datetime" else "dd.mm.yyyy"
                requests.append(number_format(sheet_id, data_start, data_end, columns.index(field), pattern))

            for field, formula_template in sheet.get("computed_formulas", {}).items():
                if field not in columns:
                    continue
                formula = str(formula_template).replace("{row}", str(data_start + 1))
                column = columns.index(field)
                requests.append(
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": data_start,
                                "endRowIndex": data_end,
                                "startColumnIndex": column,
                                "endColumnIndex": column + 1,
                            },
                            "cell": {"userEnteredValue": {"formulaValue": formula}},
                            "fields": "userEnteredValue",
                        }
                    }
                )
                requests.append(
                    {
                        "addProtectedRange": {
                            "protectedRange": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": data_start,
                                    "endRowIndex": data_end,
                                    "startColumnIndex": column,
                                    "endColumnIndex": column + 1,
                                },
                                "description": f"Вычисляемое поле {field} v{schema.get('schema_version', '0.2')}",
                                "warningOnly": True,
                            }
                        }
                    }
                )

            if sheet.get("write_mode") == "generated" or sheet.get("kind") == "computed_registry":
                requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": 0, "endColumnIndex": len(columns)}, "description": f"generated v{schema.get('schema_version', '0.2')} range", "warningOnly": True}}})

        # Build one hidden, named selector catalog per source sheet.
        if columns or sheet_name == "Срез модели":
            helper_column = helper_columns[sheet_name]
            start_row_number = int(sheet.get("data_start_row", default["data_start_row"]))
            labels_formula, ids_formula = selector_catalog_formulas(schema, sheet_name, sheet, start_row_number)
            requests.append(update_block(sheet_id, start_row_number - 1, helper_column, [row([cell(formula=labels_formula), cell(formula=ids_formula)])]))
            requests.append({"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": helper_column, "endIndex": helper_column + 2}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
            requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": start_row_number - 1, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column, "endColumnIndex": helper_column + 2}, "description": f"selector label/id catalogs v{schema.get('schema_version', '0.2')}", "warningOnly": True}}})
            selector_name, selector_id_name = selector_range_names(schema, sheet_name)
            selector_names[sheet_name] = selector_name
            selector_id_names[sheet_name] = selector_id_name
            requests.append({"addNamedRange": {"namedRange": {"name": selector_name, "range": {"sheetId": sheet_id, "startRowIndex": start_row_number - 1, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column, "endColumnIndex": helper_column + 1}}}})
            requests.append({"addNamedRange": {"namedRange": {"name": selector_id_name, "range": {"sheetId": sheet_id, "startRowIndex": start_row_number - 1, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column + 1, "endColumnIndex": helper_column + 2}}}})

    if schema.get("schema_version") == "0.3":
        dashboard_id = sheet_ids["Рабочая панель"]
        helper_column = 40
        helper_row = 4
        dependent_formulas = dashboard_selector_catalog_formulas(schema)
        requests.append(update_block(dashboard_id, helper_row, helper_column, [row([cell(formula=formula) for formula in dependent_formulas])]))
        requests.append({"updateDimensionProperties": {"range": {"sheetId": dashboard_id, "dimension": "COLUMNS", "startIndex": helper_column, "endIndex": helper_column + 4}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
        requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": dashboard_id, "startRowIndex": helper_row, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column, "endColumnIndex": helper_column + 4}, "description": "Зависимые каталоги версии, системы и процесса v0.3", "warningOnly": True}}})
        for offset, name in enumerate(("dashboard_system_labels_v03", "dashboard_system_ids_v03", "dashboard_process_labels_v03", "dashboard_process_ids_v03")):
            requests.append({"addNamedRange": {"namedRange": {"name": name, "range": {"sheetId": dashboard_id, "startRowIndex": helper_row, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": helper_column + offset, "endColumnIndex": helper_column + offset + 1}}}})

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
            polymorphic = sheet.get("polymorphic_foreign_keys", {}).get(field)
            if not target:
                if isinstance(polymorphic, dict):
                    validation_range, formula = polymorphic_selector_formula(
                        schema,
                        polymorphic,
                        columns,
                        columns.index(selector),
                        data_start + 1,
                    )
                    field_column = columns.index(field)
                    selector_column = columns.index(selector)
                    requests.append({"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": selector_column, "endColumnIndex": selector_column + 1}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": validation_range}]}, "strict": True, "showCustomUi": True}}})
                    requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "cell": {"userEnteredValue": {"formulaValue": formula}}, "fields": "userEnteredValue"}})
                    requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "description": f"ID из зависимого selector {selector}", "warningOnly": True}}})
                    continue
                elif polymorphic:
                    target_sheet = "Срез модели"
                else:
                    continue
            else:
                target_sheet = selector_source_sheet(target)
            source_name = selector_names.get(target_sheet)
            source_id_name = selector_id_names.get(target_sheet)
            if not source_name or not source_id_name:
                continue
            field_column = columns.index(field)
            selector_column = columns.index(selector)
            requests.append({"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": selector_column, "endColumnIndex": selector_column + 1}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={source_name}"}]}, "strict": True, "showCustomUi": True}}})
            requests.append({"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "cell": {"userEnteredValue": {"formulaValue": id_formula(selector_column, data_start + 1, source_name, source_id_name)}}, "fields": "userEnteredValue"}})
            requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": sheet_id, "startRowIndex": data_start, "endRowIndex": data_end, "startColumnIndex": field_column, "endColumnIndex": field_column + 1}, "description": f"ID из selector {selector}", "warningOnly": True}}})

    # Dashboard selectors use the same readable catalogs.
    dashboard_id = sheet_ids["Рабочая панель"]
    dashboard_ranges = (
        (2, selector_names["Версии"]),
        (3, "dashboard_system_labels_v03" if schema.get("schema_version") == "0.3" else selector_names["Система"]),
        (4, "dashboard_process_labels_v03" if schema.get("schema_version") == "0.3" else selector_names["Процессы"]),
    )
    for row_index, source_range in dashboard_ranges:
        requests.append({"setDataValidation": {"range": {"sheetId": dashboard_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": 2}, "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"={source_range}"}]}, "strict": True, "showCustomUi": True}}})
    requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": dashboard_id}, "description": "Рабочая панель: редактировать только selectors B3:B5", "warningOnly": True}}})

    # Visible error styling on Проверки.
    checks = schema["sheets"]["Проверки"]
    checks_id = sheet_ids["Проверки"]
    status_column = checks["columns"].index("status")
    requests.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": checks_id, "startRowIndex": 4, "endRowIndex": int(default["data_end_row"]), "startColumnIndex": 0, "endColumnIndex": len(checks["columns"])}], "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f"=${column_letter(status_column)}5=\"ERROR\""}]}, "format": {"backgroundColor": rgb(default["invalid_fill"])}}}, "index": 0}})

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
