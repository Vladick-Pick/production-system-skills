#!/usr/bin/env python3
"""Детерминированная проверка публичного пакета из четырёх скиллов."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "resolve-model-element",
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
}
REQUIRED_REFERENCES = {
    "references/LANGUAGE.md",
    "references/METAONTOLOGY.md",
    "references/INTERVIEW-CONTRACT.md",
    "references/TEMPLATE-CONTRACT.md",
    "references/PROJECTION-CONTRACT.md",
}
PUBLIC_TEMPLATE_ID = "1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k"
TEMPLATE_MANIFEST = ROOT / "templates" / "template-manifest.yaml"
TEMPLATE_SNAPSHOT = ROOT / "templates" / "production-system-model-template-v0.2.xlsx"
TEMPLATE_SCHEMA_V2 = ROOT / "templates" / "template-schema-v0.2.json"
TEMPLATE_SCHEMA_V3 = ROOT / "templates" / "template-schema-v0.3.json"
TEMPLATE_REVIEW_V3 = ROOT / "outputs" / "v0.3-review" / "production-system-model-template-v0.3-review.xlsx"
MIGRATION_V1_TO_V2 = ROOT / "templates" / "migrations" / "v0.1-to-v0.2.md"
MIGRATION_V2_TO_V3 = ROOT / "templates" / "migrations" / "v0.2-to-v0.3.md"
EXPECTED_V2_SHEETS = (
    "Инструкция",
    "Система",
    "Схема шаблона",
    "Источники",
    "Версии",
    "Исполнители",
    "Позиции",
    "Назначения",
    "Контрагенты",
    "Продукты",
    "Материалы",
    "Процессы",
    "Действия",
    "Связи действий",
    "Объекты",
    "Состояния",
    "Переходы",
    "Элементы модели",
    "Контракты",
    "Позиции контрактов",
    "Интерфейсы передачи",
    "Связи модели",
    "Решения",
    "Изменения модели",
    "Срез модели",
    "Проверки",
    "Реестр процессов",
    "Рабочая панель",
    "Диаграммы",
)
EXPECTED_V3_SHEETS = EXPECTED_V2_SHEETS[:24] + (
    "Отклонения",
    "Гипотезы",
    "Эксперименты",
) + EXPECTED_V2_SHEETS[24:]
EXPECTED_VERSION_STATUSES = {
    "черновик",
    "принято",
    "действует",
    "закрыто",
}
EXPECTED_VERSION_TRANSITIONS = {
    "черновик → принято",
    "черновик → закрыто",
    "принято → действует",
    "принято → закрыто",
    "действует → закрыто",
}
EXPECTED_INTERVIEW_STATES = {
    "orient",
    "investigate",
    "resolve",
    "draft",
    "confirm",
    "commit",
    "verify",
    "checkpoint",
}
ESSENTIAL_V2_COLUMNS = {
    "Версии": {
        "version_id",
        "predecessor_version_id",
        "version_status",
        "accepted_decision_id",
        "closed_decision_id",
        "successor_version_id",
        "migration_decision_id",
    },
    "Исполнители": {"performer_id", "performer_type", "performer_name"},
    "Назначения": {"assignment_id", "performer_id", "position_id", "active_from", "active_to"},
    "Контрагенты": {"counterparty_id", "counterparty_name"},
    "Продукты": {"product_id", "primary_object_id", "required_state_id", "acceptance_criteria"},
    "Материалы": {"material_id", "material_type", "content_text", "url"},
    "Позиции контрактов": {"contract_item_id", "contract_id", "product_id", "pricing_method", "interface_id"},
    "Интерфейсы передачи": {"interface_id", "product_id", "acceptance_action_id", "rejection_path", "fallback_path"},
    "Решения": {"decision_id", "transaction_id", "package_id", "package_hash", "confirmation_id", "confirmed_by_performer_id"},
    "Изменения модели": {"change_id", "transaction_id", "decision_id", "stable_id", "old_value", "new_value"},
    "Срез модели": {"selected_version_id", "stable_id", "source_version_id", "resolved_operation", "resolution_status"},
    "Диаграммы": {"projection_build_id", "model_fingerprint", "bpmn_sha256", "svg_sha256", "readiness_status"},
}
ESSENTIAL_V3_COLUMNS = {
    "Отклонения": {
        "deviation_id",
        "deviation_status",
        "deviation_type",
        "scope_element_id",
        "applicable_version_id",
        "norm_element_id",
        "norm_source_id",
        "observed_fact",
        "source_id",
        "correction",
        "cause",
        "system_change",
        "verification_status",
        "confirmation_decision_id",
        "closure_decision_id",
    },
    "Гипотезы": {
        "hypothesis_id",
        "hypothesis_status",
        "external_change",
        "source_id",
        "new_opportunity",
        "base_version_id",
        "scope_element_id",
        "proposed_change",
        "mechanism",
        "primary_metric_id",
        "support_criterion",
        "refutation_criterion",
        "inconclusive_criterion",
        "evidence_result",
        "owner_decision",
    },
    "Эксперименты": {
        "experiment_id",
        "experiment_status",
        "basis_type",
        "deviation_id",
        "hypothesis_id",
        "base_version_id",
        "scope_element_id",
        "temporary_change",
        "comparison_method",
        "primary_metric_id",
        "success_criterion",
        "stop_condition",
        "rollback_plan",
        "launch_decision_id",
        "conclusion",
        "implementation_decision",
    },
}


def reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"повторяющийся JSON-ключ {key!r}")
        result[key] = value
    return result


def frontmatter(text: str) -> tuple[dict[str, str], int]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("файл не начинается с YAML frontmatter")
    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError("frontmatter не закрыт") from exc

    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([a-z][a-z0-9-]*):\s*(.+)$", line)
        if not match:
            raise ValueError(f"неподдерживаемая строка frontmatter: {line!r}")
        key, value = match.groups()
        result[key] = value.strip().strip('"').strip("'")
    return result, end


def markdown_links(path: Path) -> list[Path]:
    result: list[Path] = []
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        result.append((path.parent / clean).resolve())
    return result


def text_files() -> list[Path]:
    allowed = {".json", ".md", ".yaml", ".yml", ".py", ".mjs", ".txt"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed and ".git" not in path.parts
    ]


def manifest_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def validate_template(errors: list[str]) -> None:
    if not TEMPLATE_MANIFEST.is_file():
        errors.append("нет templates/template-manifest.yaml")
        return
    if not TEMPLATE_SNAPSHOT.is_file():
        errors.append("нет версионного XLSX-снимка шаблона")
        return

    manifest = TEMPLATE_MANIFEST.read_text(encoding="utf-8")
    if manifest_value(manifest, "spreadsheet_id") != PUBLIC_TEMPLATE_ID:
        errors.append("template-manifest.yaml содержит неожиданный spreadsheet_id")

    if manifest_value(manifest, "version") != "0.2":
        errors.append("template-manifest.yaml должен объявлять текущую версию 0.2")
    if manifest_value(manifest, "access_observed") != "anyone_with_link_reader":
        errors.append("template-manifest.yaml должен фиксировать публичный доступ reader")

    declared_snapshot = manifest_value(manifest, "snapshot")
    if declared_snapshot != "templates/production-system-model-template-v0.2.xlsx":
        errors.append("template-manifest.yaml содержит неожиданный путь snapshot")

    expected_sha = manifest_value(manifest, "sha256")
    actual_sha = hashlib.sha256(TEMPLATE_SNAPSHOT.read_bytes()).hexdigest()
    if not expected_sha or expected_sha != actual_sha:
        errors.append(
            "контрольная сумма XLSX не совпадает с templates/template-manifest.yaml"
        )

    if not zipfile.is_zipfile(TEMPLATE_SNAPSHOT):
        errors.append("снимок шаблона не является корректным XLSX ZIP-контейнером")
        return

    with zipfile.ZipFile(TEMPLATE_SNAPSHOT) as archive:
        names = set(archive.namelist())
        if "xl/vbaProject.bin" in names:
            errors.append("XLSX-шаблон не должен содержать VBA-макросы")
        if any(name.startswith("xl/externalLinks/") for name in names):
            errors.append("XLSX-шаблон содержит внешние бинарные связи")
        try:
            workbook_xml = archive.read("xl/workbook.xml")
        except KeyError:
            errors.append("в XLSX-шаблоне отсутствует xl/workbook.xml")
            return
        worksheet_xml = [
            archive.read(name)
            for name in names
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        ]

    root = ElementTree.fromstring(workbook_xml)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheet_names = tuple(
        node.attrib["name"] for node in root.findall(f".//{namespace}sheet")
    )
    if sheet_names != EXPECTED_V2_SHEETS:
        errors.append(
            "состав или порядок листов XLSX не совпадает с контрактом; "
            f"найдено {list(sheet_names)}"
        )
    defined_names = root.findall(f".//{namespace}definedName")
    if len(defined_names) < 40:
        errors.append("XLSX v0.2 не содержит полный набор enum/selector named ranges")
    combined = b"\n".join(worksheet_xml)
    if combined.count(b"<f") < 100:
        errors.append("XLSX v0.2 не содержит ожидаемые физические formulas")
    if combined.count(b"<dataValidation") < 20:
        errors.append("XLSX v0.2 не содержит ожидаемые dropdown validations")
    conditional_count = combined.count(b"<conditionalFormatting")
    if conditional_count != 1:
        errors.append(
            "XLSX v0.2 должен содержать ровно одно conditional formatting: "
            "критические ошибки на листе Проверки, без красной заливки рабочих строк"
        )
    if b"#REF!" in combined:
        errors.append("XLSX v0.2 содержит формулу или диапазон с #REF!")

    candidate_markers = (
        'candidate:',
        '  version: "0.3"',
        '  status: local_release_candidate',
        '  schema: templates/template-schema-v0.3.json',
        '  builder: scripts/build_template_v0_3.py',
        '  migration: templates/migrations/v0.2-to-v0.3.md',
        '  review_artifact: outputs/v0.3-review/production-system-model-template-v0.3-review.xlsx',
        '  publication: pending_owner_acceptance_and_release_gate',
        '  sheet_count: 32',
    )
    for marker in candidate_markers:
        if marker not in manifest:
            errors.append(f"template-manifest.yaml: отсутствует marker release candidate {marker!r}")
    if not TEMPLATE_REVIEW_V3.is_file() or not zipfile.is_zipfile(TEMPLATE_REVIEW_V3):
        errors.append("нет корректного локального XLSX review-артефакта v0.3")
    else:
        with zipfile.ZipFile(TEMPLATE_REVIEW_V3) as archive:
            review_workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            review_worksheet_xml = [
                archive.read(name)
                for name in archive.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            ]
        review_names = tuple(
            node.attrib["name"]
            for node in review_workbook.findall(f".//{namespace}sheet")
        )
        if review_names != EXPECTED_V3_SHEETS:
            errors.append("локальный XLSX review-артефакт не содержит точный порядок 32 листов v0.3")
        review_roots = [ElementTree.fromstring(value) for value in review_worksheet_xml]
        review_defined_names = review_workbook.findall(f".//{namespace}definedName")
        review_formula_count = sum(len(root.findall(f".//{namespace}f")) for root in review_roots)
        review_validation_count = sum(len(root.findall(f".//{namespace}dataValidation")) for root in review_roots)
        review_conditional_count = sum(len(root.findall(f".//{namespace}conditionalFormatting")) for root in review_roots)
        review_combined = b"\n".join(review_worksheet_xml)
        if len(review_defined_names) < 40:
            errors.append("локальный XLSX v0.3 не содержит enum и selector named ranges")
        if review_formula_count < 4:
            errors.append("локальный XLSX v0.3 остаётся статическим: нет ожидаемых formulas")
        if review_validation_count < 15:
            errors.append("локальный XLSX v0.3 не содержит dropdown validations новых реестров")
        if review_conditional_count != 1:
            errors.append("локальный XLSX v0.3 должен иметь одно красное правило только для ERROR")
        if b"#REF!" in review_combined:
            errors.append("локальный XLSX v0.3 содержит #REF!")


def validate_v2_schema(errors: list[str]) -> None:
    if not TEMPLATE_SCHEMA_V2.is_file():
        errors.append("нет templates/template-schema-v0.2.json")
        return

    try:
        schema = json.loads(
            TEMPLATE_SCHEMA_V2.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        errors.append(f"template-schema-v0.2.json не читается: {exc}")
        return

    order = tuple(schema.get("sheet_order", ()))
    sheets = schema.get("sheets", {})
    if schema.get("schema_version") != "0.2":
        errors.append("template-schema-v0.2.json имеет неожиданный schema_version")
    if schema.get("sheet_count") != 29 or order != EXPECTED_V2_SHEETS:
        errors.append("schema v0.2 должна задавать ровно 29 листов в принятом порядке")
    if tuple(sheets) != EXPECTED_V2_SHEETS:
        errors.append("порядок объектов sheets не совпадает с sheet_order v0.2")
    if "Проекция draw.io" in order:
        errors.append("schema v0.2 не должна содержать лист Проекция draw.io")

    default_table = schema.get("default_table", {})
    if default_table.get("technical_ids_visible") is not True:
        errors.append("schema v0.2 должна оставлять technical IDs видимыми")

    physical = schema.get("physical_contract", {})
    expected_physical = {
        "builder",
        "spreadsheet_locale",
        "time_zone",
        "formula_language",
        "selector_encoding",
        "foreign_key_write_path",
        "selector_catalogs",
        "enum_catalogs",
        "generated_ranges",
        "conditional_formatting",
        "filtering",
        "rebuild_semantics",
    }
    missing_physical = expected_physical - set(physical)
    if missing_physical:
        errors.append(f"schema v0.2: неполный physical_contract {sorted(missing_physical)}")
    builder = ROOT / str(physical.get("builder", ""))
    if not builder.is_file():
        errors.append("schema v0.2 ссылается на отсутствующий physical builder")

    for sheet_name, required_columns in ESSENTIAL_V2_COLUMNS.items():
        actual_columns = set(sheets.get(sheet_name, {}).get("columns", []))
        missing = required_columns - actual_columns
        if missing:
            errors.append(f"{sheet_name}: отсутствуют обязательные v0.2 колонки {sorted(missing)}")

    version_columns = set(sheets.get("Версии", {}).get("columns", []))
    if "close_reason" in version_columns:
        errors.append("Версии: обязательный close_reason отложен решением владельца")

    enums = schema.get("enums", {})
    for sheet_name, sheet in sheets.items():
        columns = sheet.get("columns", [])
        if len(columns) != len(set(columns)):
            errors.append(f"{sheet_name}: в schema v0.2 есть повторяющиеся колонки")
        for group in ("required", "computed"):
            values = sheet.get(group, [])
            if values == ["all_non_selector_cells"]:
                continue
            unknown = set(values) - set(columns)
            if unknown:
                errors.append(
                    f"{sheet_name}: {group} ссылается на неизвестные колонки {sorted(unknown)}"
                )
        for field, enum_name in sheet.get("enums", {}).items():
            if field not in columns or enum_name not in enums:
                errors.append(
                    f"{sheet_name}: enum {field} → {enum_name} не разрешается"
                )
        for field, target in sheet.get("foreign_keys", {}).items():
            if field not in columns:
                errors.append(f"{sheet_name}: FK-поле {field} отсутствует в columns")
                continue
            if "." not in target:
                errors.append(f"{sheet_name}: FK {field} имеет некорректную цель {target}")
                continue
            target_sheet, target_column = target.split(".", 1)
            target_columns = sheets.get(target_sheet, {}).get("columns", [])
            target_settings = sheets.get(target_sheet, {}).get("settings", {})
            if target_sheet not in sheets or (
                target_column not in target_columns and target_column not in target_settings
            ):
                errors.append(f"{sheet_name}: FK {field} указывает на неизвестное {target}")
        selectors = sheet.get("selectors", {})
        if isinstance(selectors, dict):
            settings = sheet.get("settings", {})
            for field, selector in selectors.items():
                if field in settings:
                    if selector not in settings:
                        errors.append(
                            f"{sheet_name}: selector настройки {field} → {selector} отсутствует"
                        )
                    continue
                if field not in columns or selector not in columns:
                    errors.append(
                        f"{sheet_name}: selector {field} → {selector} отсутствует в columns"
                    )
                elif columns.index(selector) != columns.index(field) + 1:
                    errors.append(
                        f"{sheet_name}: selector {selector} должен идти сразу после {field}"
                    )
        if sheet.get("kind") in {"versioned_authoring", "versioned_authoring_with_settings"}:
            expected_prefix = [columns[0], "version_id", "version_operation"] if columns else []
            if columns[:3] != expected_prefix:
                errors.append(
                    f"{sheet_name}: версионная строка должна начинаться stable_id, version_id, version_operation"
                )
            if not columns or not columns[0].endswith("_id"):
                errors.append(f"{sheet_name}: первый открытый столбец должен быть stable ID")

        foreign_keys = set(sheet.get("foreign_keys", {}))
        selector_fields = set(selectors) if isinstance(selectors, dict) else set()
        missing_selectors = foreign_keys - selector_fields - {"version_id"}
        if missing_selectors:
            errors.append(
                f"{sheet_name}: FK без человекочитаемого selector {sorted(missing_selectors)}"
            )

    required_relations = {
        "производит",
        "использует",
        "создаёт",
        "регулируется",
        "входит в приёмочный пакет",
    }
    actual_relations = set(sheets.get("Связи модели", {}).get("relation_types", []))
    if not required_relations <= actual_relations:
        errors.append("Связи модели не содержат минимальный словарь отношений v0.2")


def validate_v3_schema(errors: list[str]) -> None:
    if not TEMPLATE_SCHEMA_V3.is_file():
        errors.append("нет templates/template-schema-v0.3.json")
        return
    try:
        overlay = json.loads(
            TEMPLATE_SCHEMA_V3.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        base = json.loads(TEMPLATE_SCHEMA_V2.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        errors.append(f"template-schema-v0.3.json не читается: {exc}")
        return
    if overlay.get("schema_version") != "0.3" or overlay.get("base_schema") != "template-schema-v0.2.json":
        errors.append("schema v0.3 должна быть additive overlay точной schema v0.2")
    additions = tuple(overlay.get("sheet_order_additions", ()))
    if overlay.get("sheet_count") != 32 or additions != ("Отклонения", "Гипотезы", "Эксперименты"):
        errors.append("schema v0.3 должна добавлять ровно три принятых реестра и 32 листа")
    order = list(base.get("sheet_order", []))
    try:
        anchor = order.index(overlay.get("insert_after")) + 1
    except ValueError:
        errors.append("schema v0.3 содержит неизвестную точку вставки")
        return
    order[anchor:anchor] = additions
    if tuple(order) != EXPECTED_V3_SHEETS:
        errors.append("итоговый порядок 32 листов v0.3 не соответствует контракту")
    sheets = overlay.get("sheets", {})
    if tuple(sheets) != additions:
        errors.append("overlay v0.3 должен объявлять только три новых листа в принятом порядке")
    overrides = set(overlay.get("sheet_overrides", {}))
    if overrides != {"Рабочая панель"}:
        errors.append("overlay v0.3 может менять только вычисляемую Рабочую панель v0.2")
    enums = overlay.get("enums", {})
    expected_scope_types = {
        "действие", "процесс", "производственная система", "объект",
        "состояние", "продукт", "материал", "показатель",
    }
    if set(enums.get("development_scope_type", [])) != expected_scope_types:
        errors.append("development_scope_type должен покрывать все принятые типы области развития")
    for sheet_name, required_columns in ESSENTIAL_V3_COLUMNS.items():
        sheet = sheets.get(sheet_name, {})
        if sheet.get("freeze_columns") != 3:
            errors.append(f"{sheet_name}: первые три колонки должны быть закреплены для длинного реестра")
        columns = sheet.get("columns", [])
        missing = required_columns - set(columns)
        if missing:
            errors.append(f"{sheet_name}: отсутствуют обязательные v0.3 колонки {sorted(missing)}")
        if len(columns) != len(set(columns)):
            errors.append(f"{sheet_name}: повторяющиеся колонки v0.3")
        selectors = sheet.get("selectors", {})
        for field, selector in selectors.items():
            if field not in columns or selector not in columns:
                errors.append(f"{sheet_name}: нарушена ID/selector пара {field} → {selector}")
            elif columns.index(selector) != columns.index(field) + 1:
                errors.append(f"{sheet_name}: selector {selector} должен идти сразу после {field}")
        for field, enum_name in sheet.get("enums", {}).items():
            if field not in columns or enum_name not in enums:
                errors.append(f"{sheet_name}: enum {field} → {enum_name} не разрешается в overlay")
        scope_spec = sheet.get("polymorphic_foreign_keys", {}).get("scope_element_id")
        if not isinstance(scope_spec, dict) or scope_spec.get("type_field") != "scope_type":
            errors.append(f"{sheet_name}: scope_element_id не имеет типизированного polymorphic contract")
        elif set(scope_spec.get("targets", {})) != expected_scope_types:
            errors.append(f"{sheet_name}: scope_element_id не разрешает все типы области")
    experiment = sheets.get("Эксперименты", {})
    if experiment.get("computed") != ["basis_type"] or "exactly_one_basis" not in experiment.get("constraints", []):
        errors.append("Эксперименты должны вычислять basis_type и требовать ровно одно основание")
    if "{row}" not in str(experiment.get("computed_formulas", {}).get("basis_type", "")):
        errors.append("formula basis_type должна быть копируемой по строкам")
    if not (ROOT / "scripts" / "build_template_v0_3.py").is_file():
        errors.append("нет scripts/build_template_v0_3.py")


def validate_version_lifecycle(errors: list[str]) -> None:
    language_path = ROOT / "references" / "LANGUAGE.md"
    metaontology_path = ROOT / "references" / "METAONTOLOGY.md"
    if not language_path.is_file() or not metaontology_path.is_file():
        return

    language = language_path.read_text(encoding="utf-8")
    status_section = re.search(
        r"^### Статус версии\n(?P<body>.*?)^### Слой модели и статус версии",
        language,
        re.MULTILINE | re.DOTALL,
    )
    statuses = (
        set(
            re.findall(
                r"^#### [^\n]+ \(`([^`]+)`\)$",
                status_section.group("body"),
                re.MULTILINE,
            )
        )
        if status_section
        else set()
    )
    if statuses != EXPECTED_VERSION_STATUSES:
        errors.append(
            "LANGUAGE.md должен определять ровно четыре статуса версии; "
            f"найдено {sorted(statuses)}"
        )

    metaontology = metaontology_path.read_text(encoding="utf-8")
    transitions = set(
        re.findall(
            r"^\| `([^`]+ → [^`]+)` \|",
            metaontology,
            re.MULTILINE,
        )
    )
    if transitions != EXPECTED_VERSION_TRANSITIONS:
        errors.append(
            "METAONTOLOGY.md содержит неожиданный граф переходов версии; "
            f"найдено {sorted(transitions)}"
        )


def validate_interview_contract(errors: list[str]) -> None:
    path = ROOT / "references" / "INTERVIEW-CONTRACT.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    states = set(
        re.findall(
            r"^\| `([a-z]+)` \|",
            text,
            re.MULTILINE,
        )
    )
    if states != EXPECTED_INTERVIEW_STATES:
        errors.append(
            "INTERVIEW-CONTRACT.md содержит неожиданные состояния; "
            f"найдено {sorted(states)}"
        )
    for marker in (
        "package_hash",
        "transaction_id",
        "Одновременно активно ровно одно состояние и не более одного вопроса",
        "ИИ-агент может быть исполнителем и регистратором транзакции, но не подтверждающим лицом",
        "До retry искать `transaction_id`",
    ):
        if marker not in text:
            errors.append(f"INTERVIEW-CONTRACT.md: отсутствует harness marker {marker!r}")


def validate_migration_contract(errors: list[str]) -> None:
    if not MIGRATION_V1_TO_V2.is_file():
        errors.append("нет templates/migrations/v0.1-to-v0.2.md")
        return
    text = MIGRATION_V1_TO_V2.read_text(encoding="utf-8")
    for marker in (
        "migration-assessment",
        "migration dossier",
        "v0.1-compatible",
        "new-required",
        "bounded batches",
        "исходная v0.1-книга не изменена",
        "один `active_question_id`",
    ):
        if marker not in text:
            errors.append(f"v0.1-to-v0.2.md: отсутствует migration marker {marker!r}")
    if not MIGRATION_V2_TO_V3.is_file():
        errors.append("нет templates/migrations/v0.2-to-v0.3.md")
        return
    text_v3 = MIGRATION_V2_TO_V3.read_text(encoding="utf-8")
    for marker in (
        "Отдельная копия v0.3",
        "stable IDs",
        "Отклонения",
        "Гипотезы",
        "Эксперименты",
        "source/target reconciliation",
        "исходную неизменённую v0.2",
        "migrate_template_v0_2_to_v0_3.py",
    ):
        if marker not in text_v3:
            errors.append(f"v0.2-to-v0.3.md: отсутствует migration marker {marker!r}")


def validate() -> list[str]:
    errors: list[str] = []
    skills_root = ROOT / "skills"
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    if actual != EXPECTED_SKILLS:
        errors.append(
            "папки skills должны содержать ровно четыре скилла; "
            f"ожидалось {sorted(EXPECTED_SKILLS)}, найдено {sorted(actual)}"
        )

    for relative in sorted(REQUIRED_REFERENCES):
        if not (ROOT / relative).is_file():
            errors.append(f"нет обязательного reference: {relative}")

    validate_version_lifecycle(errors)
    validate_interview_contract(errors)
    validate_migration_contract(errors)
    validate_template(errors)
    validate_v2_schema(errors)
    validate_v3_schema(errors)

    for name in sorted(EXPECTED_SKILLS):
        skill_dir = skills_root / name
        skill_path = skill_dir / "SKILL.md"
        agent_path = skill_dir / "agents" / "openai.yaml"

        if not skill_path.is_file():
            errors.append(f"{name}: нет SKILL.md")
            continue
        if not agent_path.is_file():
            errors.append(f"{name}: нет agents/openai.yaml")
            continue

        text = skill_path.read_text(encoding="utf-8")
        try:
            meta, _ = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue

        if set(meta) != {"name", "description"}:
            errors.append(
                f"{name}: frontmatter должен содержать только name и description, найдено {sorted(meta)}"
            )
        if meta.get("name") != name:
            errors.append(f"{name}: поле name не совпадает с именем папки")
        description = meta.get("description", "")
        if len(description) < 80:
            errors.append(f"{name}: description недостаточно подробно задаёт функцию и триггер")
        if not re.search(r"[А-Яа-яЁё]", description):
            errors.append(f"{name}: description должен быть на русском языке")
        if len(text.splitlines()) > 500:
            errors.append(f"{name}: SKILL.md превышает 500 строк")
        for marker in ("TODO", "Structuring This Skill", "[TODO"):
            if marker in text:
                errors.append(f"{name}: найден шаблонный маркер {marker!r}")

        for reference in (
            "references/LANGUAGE.md",
            "references/METAONTOLOGY.md",
            "references/INTERVIEW-CONTRACT.md",
            "references/TEMPLATE-CONTRACT.md",
        ):
            if reference not in text:
                errors.append(f"{name}: нет обязательной ссылки {reference}")

        for reference_name in (
            "LANGUAGE.md",
            "METAONTOLOGY.md",
            "INTERVIEW-CONTRACT.md",
            "TEMPLATE-CONTRACT.md",
            "PROJECTION-CONTRACT.md",
        ):
            canonical = ROOT / "references" / reference_name
            bundled = skill_dir / "references" / reference_name
            if not bundled.is_file():
                errors.append(f"{name}: нет локальной копии references/{reference_name}")
            elif bundled.read_bytes() != canonical.read_bytes():
                errors.append(
                    f"{name}: references/{reference_name} расходится с корневым контрактом; "
                    "запустите scripts/sync_references.py"
                )

        bundled_schema = skill_dir / "references" / "TEMPLATE-SCHEMA-v0.2.json"
        if not bundled_schema.is_file():
            errors.append(f"{name}: нет локальной копии references/TEMPLATE-SCHEMA-v0.2.json")
        elif bundled_schema.read_bytes() != TEMPLATE_SCHEMA_V2.read_bytes():
            errors.append(
                f"{name}: TEMPLATE-SCHEMA-v0.2.json расходится с templates/template-schema-v0.2.json; "
                "запустите scripts/sync_references.py"
            )

        bundled_schema_v3 = skill_dir / "references" / "TEMPLATE-SCHEMA-v0.3.json"
        if not bundled_schema_v3.is_file():
            errors.append(f"{name}: нет локальной копии references/TEMPLATE-SCHEMA-v0.3.json")
        elif bundled_schema_v3.read_bytes() != TEMPLATE_SCHEMA_V3.read_bytes():
            errors.append(
                f"{name}: TEMPLATE-SCHEMA-v0.3.json расходится с templates/template-schema-v0.3.json; "
                "запустите scripts/sync_references.py"
            )

        bundled_migration = skill_dir / "references" / "MIGRATION-v0.1-to-v0.2.md"
        canonical_migration = ROOT / "templates" / "migrations" / "v0.1-to-v0.2.md"
        if not bundled_migration.is_file():
            errors.append(f"{name}: нет локальной migration map")
        elif bundled_migration.read_bytes() != canonical_migration.read_bytes():
            errors.append(f"{name}: migration map расходится с канонической")

        bundled_migration_v3 = skill_dir / "references" / "MIGRATION-v0.2-to-v0.3.md"
        if not bundled_migration_v3.is_file():
            errors.append(f"{name}: нет локальной migration map v0.2-to-v0.3")
        elif bundled_migration_v3.read_bytes() != MIGRATION_V2_TO_V3.read_bytes():
            errors.append(f"{name}: migration map v0.2-to-v0.3 расходится с канонической")

        if name in {"model-production-system", "maintain-production-system", "audit-production-system"}:
            for relative, canonical in (
                ("bpmn/common.py", ROOT / "scripts" / "bpmn" / "common.py"),
                ("bpmn/generate.py", ROOT / "scripts" / "bpmn" / "generate.py"),
                ("bpmn/validate.py", ROOT / "scripts" / "bpmn" / "validate.py"),
                ("versioning/resolve.py", ROOT / "scripts" / "versioning" / "resolve.py"),
                ("build_template_v0_2.py", ROOT / "scripts" / "build_template_v0_2.py"),
                ("build_template_v0_3.py", ROOT / "scripts" / "build_template_v0_3.py"),
                ("migrate_template_v0_2_to_v0_3.py", ROOT / "scripts" / "migrate_template_v0_2_to_v0_3.py"),
            ):
                bundled = skill_dir / "scripts" / relative
                if not bundled.is_file():
                    errors.append(f"{name}: нет self-contained runtime scripts/{relative}")
                elif bundled.read_bytes() != canonical.read_bytes():
                    errors.append(f"{name}: runtime scripts/{relative} расходится с каноническим")

        agent = agent_path.read_text(encoding="utf-8")
        if "$" + name not in agent:
            errors.append(f"{name}: default_prompt не упоминает навык через знак доллара")
        short_match = re.search(r'short_description:\s*"([^"]+)"', agent)
        if not short_match:
            errors.append(f"{name}: нет short_description")
        elif not 25 <= len(short_match.group(1)) <= 64:
            errors.append(f"{name}: short_description должен иметь 25–64 символа")

    manifest = (ROOT / "skill-package.yaml").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\s{2}- ([a-z0-9-]+)$", manifest, re.MULTILINE))
    if listed != EXPECTED_SKILLS:
        errors.append(
            f"skill-package.yaml перечисляет {sorted(listed)}, ожидалось {sorted(EXPECTED_SKILLS)}"
        )
    package_snapshot = re.search(r"^\s{2}snapshot:\s*([^\n]+)$", manifest, re.MULTILINE)
    if not package_snapshot or package_snapshot.group(1).strip().strip("\"'") != "templates/production-system-model-template-v0.2.xlsx":
        errors.append("skill-package.yaml должен ссылаться на текущий XLSX v0.2")
    package_markers = (
        'version: "0.3.0-rc.1"',
        'template_schema_base: templates/template-schema-v0.2.json',
        'template_schema_overlay: templates/template-schema-v0.3.json',
        'published_version: "0.2"',
        'candidate_version: "0.3"',
        'candidate_status: local_release_candidate',
        'migration_v2_to_v3: templates/migrations/v0.2-to-v0.3.md',
    )
    for marker in package_markers:
        if marker not in manifest:
            errors.append(f"skill-package.yaml: отсутствует marker release candidate {marker!r}")
    if "identified_assigned_human:" in manifest:
        errors.append("skill-package.yaml не должен трактовать assignment как permission")
    if "assignment: фиксирует атрибуцию, но не является permission или RBAC" not in manifest:
        errors.append("skill-package.yaml должен фиксировать attribution-only смысл assignment")

    for path in text_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        secret_patterns = {
            "GitHub token": r"\bgh[opsu]_[A-Za-z0-9]{20,}\b",
            "GitHub fine-grained token": r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
            "OpenAI key": r"\bsk-[A-Za-z0-9]{20,}\b",
            "private key": r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY",
            "private Notion page": r"app\.notion\.com/p/",
        }
        for label, pattern in secret_patterns.items():
            if re.search(pattern, text):
                errors.append(f"{relative}: обнаружен потенциальный секрет или закрытая ссылка ({label})")

        for match in re.finditer(
            r"docs\.google\.com/(document|spreadsheets)/d/([A-Za-z0-9_-]+)", text
        ):
            document_type, document_id = match.groups()
            if document_type == "spreadsheets" and document_id == PUBLIC_TEMPLATE_ID:
                continue
            errors.append(
                f"{relative}: обнаружена Google-ссылка вне публичного шаблона"
            )

        if path.suffix == ".md":
            for target in markdown_links(path):
                if not target.exists():
                    errors.append(f"{relative}: не существует относительная ссылка {target}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("[FAIL] Репозиторий не прошёл проверку:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] Ровно 4 скилла")
    print("[OK] Frontmatter, UI-метаданные и общие references согласованы")
    print("[OK] Публичные Google Sheets и XLSX v0.2 согласованы; локальный review v0.3 содержит 32 листа")
    print("[OK] TODO, битые относительные ссылки и типовые секреты не найдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
