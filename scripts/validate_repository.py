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
    "references/METHODOLOGY-COMPATIBILITY.md",
    "references/INTERVIEW-CONTRACT.md",
    "references/TEMPLATE-CONTRACT.md",
    "references/PROJECTION-CONTRACT.md",
}
PUBLIC_TEMPLATE_ID = "1W9u-t5a4Uuj2pCBLtia3E60qUHn5ZjeFiicNTCv6fR0"
ROLLBACK_TEMPLATE_ID = "1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k"
TEMPLATE_MANIFEST = ROOT / "templates" / "template-manifest.yaml"
TEMPLATE_SNAPSHOT = ROOT / "templates" / "production-system-model-template-v0.3.xlsx"
ROLLBACK_TEMPLATE_SNAPSHOT = ROOT / "templates" / "production-system-model-template-v0.2.xlsx"
TEMPLATE_SCHEMA_V2 = ROOT / "templates" / "template-schema-v0.2.json"
TEMPLATE_SCHEMA_V3 = ROOT / "templates" / "template-schema-v0.3.json"
TEMPLATE_SCHEMA_V4 = ROOT / "templates" / "template-schema-v0.4.json"
MIGRATION_V1_TO_V2 = ROOT / "templates" / "migrations" / "v0.1-to-v0.2.md"
MIGRATION_V2_TO_V3 = ROOT / "templates" / "migrations" / "v0.2-to-v0.3.md"
MIGRATION_V3_TO_V4 = ROOT / "templates" / "migrations" / "v0.3-to-v0.4.md"
BEHAVIORAL_CASES = ROOT / "evals" / "cases.yaml"
FRESH_AGENT_CONTRACT = ROOT / "evals" / "FRESH-AGENT-CONTRACT.md"
PASSPORT = ROOT / "ПАСПОРТ.md"
PROJECT_INTENT = ROOT / "docs" / "PROJECT-INTENT.md"
PACKAGE_SCOPE = ROOT / "docs" / "PACKAGE-SCOPE.md"
PLANS_INDEX = ROOT / "plans" / "README.md"
NEXT_SESSION = ROOT / "NEXT_SESSION.md"
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
_V4_ANCHOR = EXPECTED_V3_SHEETS.index("Элементы модели") + 1
EXPECTED_V4_SHEETS = EXPECTED_V3_SHEETS[:_V4_ANCHOR] + (
    "Показатели",
    "Привязки показателей",
    "Требования показателей",
    "Экономические правила",
    "Условия назначений",
) + EXPECTED_V3_SHEETS[_V4_ANCHOR:]
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
ESSENTIAL_V4_COLUMNS = {
    "Показатели": {
        "indicator_id", "version_id", "system_id", "indicator_name", "indicator_kind",
        "management_question", "measured_characteristic", "observation_unit_type",
        "observation_unit_id", "single_unit_rule", "unit_of_measure",
        "time_attribution_rule", "required_facts", "coverage_rule",
    },
    "Привязки показателей": {
        "binding_id", "version_id", "indicator_id", "binding_role", "fact_source_id",
        "fact_locator_contract", "required_fact_description", "coverage_rule", "valid_from",
    },
    "Требования показателей": {
        "requirement_id", "version_id", "indicator_id", "requirement_type", "scope_type",
        "scope_element_id", "comparison_operator", "period_start",
    },
    "Экономические правила": {
        "economic_rule_id", "version_id", "system_id", "rule_kind", "economic_direction",
        "source_scope_type", "source_scope_id", "calculation_method", "formula_or_rule",
        "valid_from",
    },
    "Условия назначений": {
        "assignment_condition_id", "version_id", "assignment_id", "condition_type",
        "compensation_scheme_rule_id", "compensation_scheme_rule_version_id",
        "application_mode", "storage_mode", "valid_from",
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


def validate_project_context(errors: list[str]) -> None:
    required = (
        ROOT / "AGENTS.md",
        ROOT / "README.md",
        PASSPORT,
        PROJECT_INTENT,
        PACKAGE_SCOPE,
        PLANS_INDEX,
        NEXT_SESSION,
        TEMPLATE_MANIFEST,
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        errors.append(f"нет обязательных точек восстановления контекста: {missing}")
        return

    manifest = TEMPLATE_MANIFEST.read_text(encoding="utf-8")
    version = manifest_value(manifest, "version")
    if not version:
        errors.append("невозможно определить стабильную версию для проверки контекста")
        return
    release = f"v{version}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    passport = PASSPORT.read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    intent = PROJECT_INTENT.read_text(encoding="utf-8")
    package_scope = PACKAGE_SCOPE.read_text(encoding="utf-8")
    plans = PLANS_INDEX.read_text(encoding="utf-8")
    next_session = NEXT_SESSION.read_text(encoding="utf-8")

    if f"Текущий стабильный релиз — **{release}**" not in readme:
        errors.append("README.md расходится с версией template-manifest.yaml")
    if f'stable_release: "{release}"' not in passport:
        errors.append("ПАСПОРТ.md расходится с версией template-manifest.yaml")

    required_links = {
        "README.md": (
            "ПАСПОРТ.md",
            "docs/PACKAGE-SCOPE.md",
            "docs/PROJECT-INTENT.md",
            "plans/README.md",
        ),
        "AGENTS.md": ("ПАСПОРТ.md", "docs/PACKAGE-SCOPE.md", "plans/README.md"),
        "ПАСПОРТ.md": (
            "docs/PACKAGE-SCOPE.md",
            "docs/PROJECT-INTENT.md",
            "plans/README.md",
        ),
        "NEXT_SESSION.md": ("ПАСПОРТ.md", "docs/PACKAGE-SCOPE.md", "plans/README.md"),
    }
    texts = {
        "README.md": readme,
        "AGENTS.md": agents,
        "ПАСПОРТ.md": passport,
        "NEXT_SESSION.md": next_session,
    }
    for name, markers in required_links.items():
        for marker in markers:
            if marker not in texts[name]:
                errors.append(f"{name}: отсутствует ссылка холодного старта {marker}")

    if "business-ontology-platform" not in intent or "не дублируются здесь" not in intent:
        errors.append("PROJECT-INTENT.md не указывает канонического владельца замысла")
    if "Статус: канонический документ назначения и границы" not in package_scope:
        errors.append("PACKAGE-SCOPE.md не объявлен владельцем границы пакета")
    if "## Чем владеет репозиторий" not in package_scope or "## Чем репозиторий не владеет" not in package_scope:
        errors.append("PACKAGE-SCOPE.md не фиксирует положительную и отрицательную границу")

    stale_agent_markers = (
        "Выпущенная v0.2 является стабильной базой",
        "Контур обратной связи v0.2 → v0.3",
        "обобщаемое требование-кандидат v0.3",
    )
    for marker in stale_agent_markers:
        if marker in agents:
            errors.append(f"AGENTS.md содержит устаревший статусный marker {marker!r}")

    active_plans = sorted((ROOT / "plans" / "active").glob("*.md"))
    if not active_plans and "Активного плана реализации сейчас нет" not in plans:
        errors.append("plans/README.md должен явно фиксировать отсутствие активного плана")
    for path in active_plans:
        expected_link = f"active/{path.name}"
        if expected_link not in plans:
            errors.append(f"plans/README.md не индексирует активный план {expected_link}")

    if "не владеет текущей задачей или планом работ" not in next_session:
        errors.append("NEXT_SESSION.md снова стал конкурирующим источником рабочего статуса")


def validate_template(errors: list[str]) -> None:
    if not TEMPLATE_MANIFEST.is_file():
        errors.append("нет templates/template-manifest.yaml")
        return
    if not TEMPLATE_SNAPSHOT.is_file():
        errors.append("нет версионного XLSX-снимка шаблона")
        return
    if not ROLLBACK_TEMPLATE_SNAPSHOT.is_file():
        errors.append("нет rollback XLSX-снимка v0.2")
        return

    manifest = TEMPLATE_MANIFEST.read_text(encoding="utf-8")
    if manifest_value(manifest, "spreadsheet_id") != PUBLIC_TEMPLATE_ID:
        errors.append("template-manifest.yaml содержит неожиданный spreadsheet_id")

    if manifest_value(manifest, "version") != "0.3":
        errors.append("template-manifest.yaml должен объявлять текущую версию 0.3")
    if manifest_value(manifest, "access_observed") != "anyone_with_link_reader":
        errors.append("template-manifest.yaml должен фиксировать публичный доступ reader")

    declared_snapshot = manifest_value(manifest, "snapshot")
    if declared_snapshot != "templates/production-system-model-template-v0.3.xlsx":
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
    if sheet_names != EXPECTED_V3_SHEETS:
        errors.append(
            "состав или порядок листов XLSX не совпадает с контрактом; "
            f"найдено {list(sheet_names)}"
        )
    defined_names = root.findall(f".//{namespace}definedName")
    worksheet_roots = [ElementTree.fromstring(value) for value in worksheet_xml]
    formula_count = sum(len(node.findall(f".//{namespace}f")) for node in worksheet_roots)
    validation_count = sum(
        len(node.findall(f".//{namespace}dataValidation")) for node in worksheet_roots
    )
    conditional_count = sum(
        len(node.findall(f".//{namespace}conditionalFormatting")) for node in worksheet_roots
    )
    combined = b"\n".join(worksheet_xml)
    if len(defined_names) < 100:
        errors.append("XLSX v0.3 не содержит полный набор enum/selector named ranges")
    if formula_count < 1000:
        errors.append("XLSX v0.3 не содержит ожидаемые физические formulas")
    if validation_count < 100:
        errors.append("XLSX v0.3 не содержит ожидаемые dropdown validations")
    if conditional_count != 1:
        errors.append(
            "XLSX v0.3 должен содержать ровно одно conditional formatting: "
            "критические ошибки на листе Проверки, без красной заливки рабочих строк"
        )
    if b"#REF!" in combined:
        errors.append("XLSX v0.3 содержит формулу или диапазон с #REF!")

    release_markers = (
        'schema: templates/template-schema-v0.3.json',
        'base_schema: templates/template-schema-v0.2.json',
        'builder: scripts/build_template_v0_3.py',
        'migration: templates/migrations/v0.2-to-v0.3.md',
        'sheet_count: 32',
        'rollback:',
        '  version: "0.2"',
        f'  spreadsheet_id: {ROLLBACK_TEMPLATE_ID}',
        '  snapshot: templates/production-system-model-template-v0.2.xlsx',
    )
    for marker in release_markers:
        if marker not in manifest:
            errors.append(f"template-manifest.yaml: отсутствует marker релиза {marker!r}")

    rollback_expected_sha = "f80d79722fa34a0759050d8aa5b5d8de587c94f326804e89aa077d7c9c37ba9e"
    rollback_actual_sha = hashlib.sha256(ROLLBACK_TEMPLATE_SNAPSHOT.read_bytes()).hexdigest()
    if rollback_actual_sha != rollback_expected_sha or f"  sha256: {rollback_expected_sha}" not in manifest:
        errors.append("rollback XLSX v0.2 или его manifest sha256 изменён")


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
        errors.append("schema v0.3 должна быть версионным overlay точной schema v0.2")
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
    override_sheets = overlay.get("sheet_overrides", {})
    overrides = set(override_sheets)
    if overrides != {"Позиции контрактов", "Интерфейсы передачи", "Рабочая панель"}:
        errors.append("overlay v0.3 должен менять только компонентные листы и вычисляемую Рабочую панель")
    for sheet_name in ("Позиции контрактов", "Интерфейсы передачи"):
        sheet = override_sheets.get(sheet_name, {})
        columns = set(sheet.get("columns", []))
        if not {"product_id", "product_selector", "material_id", "material_selector"} <= columns:
            errors.append(f"{sheet_name}: v0.3 не задаёт соседние product/material ссылки")
        if "exactly_one_product_or_material" not in sheet.get("constraints", []):
            errors.append(f"{sheet_name}: v0.3 не требует ровно одного компонента")
        if {"product_id", "material_id"} & set(sheet.get("required", [])):
            errors.append(f"{sheet_name}: нельзя требовать заранее выбранный тип компонента")
    enum_overrides = overlay.get("enum_overrides", {})
    if "гипотеза" in enum_overrides.get("knowledge_status", []) or "предположение" not in enum_overrides.get("knowledge_status", []):
        errors.append("v0.3 должна отделять статус знания предположение от Гипотезы развития")
    if set(enum_overrides.get("object_type", [])) != {"объект работы", "данные", "документ", "ресурс"}:
        errors.append("v0.3 должна убрать контекстные роли вход/выход из object_type")
    semantic_migrations = overlay.get("semantic_migrations", {})
    if semantic_migrations.get("knowledge_status", {}).get("гипотеза") != "предположение":
        errors.append("v0.3 не объявляет однозначную миграцию статуса знания")
    if set(semantic_migrations.get("object_type", {}).get("requires_resolution", [])) != {"вход", "выход"}:
        errors.append("v0.3 не объявляет stop-gate для старых ролей вход/выход")
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


def validate_v4_schema(errors: list[str]) -> None:
    if not TEMPLATE_SCHEMA_V4.is_file():
        errors.append("нет templates/template-schema-v0.4.json")
        return
    try:
        overlay = json.loads(
            TEMPLATE_SCHEMA_V4.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        errors.append(f"template-schema-v0.4.json не читается: {exc}")
        return

    if overlay.get("schema_version") != "0.4" or overlay.get("base_schema") != "template-schema-v0.3.json":
        errors.append("schema v0.4 должна быть версионным overlay точной schema v0.3")
    additions = tuple(overlay.get("sheet_order_additions", ()))
    expected_additions = EXPECTED_V4_SHEETS[_V4_ANCHOR:_V4_ANCHOR + 5]
    if overlay.get("sheet_count") != 37 or additions != expected_additions:
        errors.append("schema v0.4 должна добавлять пять принятых реестров и 37 листов")
    if overlay.get("insert_after") != "Элементы модели":
        errors.append("schema v0.4 должна вставлять новые реестры после Элементы модели")
    order = list(EXPECTED_V3_SHEETS)
    anchor = order.index("Элементы модели") + 1
    order[anchor:anchor] = additions
    if tuple(order) != EXPECTED_V4_SHEETS:
        errors.append("итоговый порядок 37 листов v0.4 не соответствует контракту")

    sheets = overlay.get("sheets", {})
    if tuple(sheets) != additions:
        errors.append("overlay v0.4 должен объявлять только пять новых листов в принятом порядке")
    for sheet_name, required_columns in ESSENTIAL_V4_COLUMNS.items():
        sheet = sheets.get(sheet_name, {})
        columns = sheet.get("columns", [])
        missing = required_columns - set(columns)
        if missing:
            errors.append(f"{sheet_name}: отсутствуют обязательные v0.4 колонки {sorted(missing)}")
        if len(columns) != len(set(columns)):
            errors.append(f"{sheet_name}: повторяющиеся колонки v0.4")
        for field, selector in sheet.get("selectors", {}).items():
            if field not in columns or selector not in columns:
                errors.append(f"{sheet_name}: нарушена ID/selector пара {field} → {selector}")
            elif columns.index(selector) != columns.index(field) + 1:
                errors.append(f"{sheet_name}: selector {selector} должен идти сразу после {field}")

    element_types = set(overlay.get("enum_overrides", {}).get("element_type", []))
    if {"показатель", "норматив"} & element_types:
        errors.append("v0.4 должна убрать legacy-показатель и норматив из Элементы модели")
    migrations = overlay.get("semantic_migrations", {}).get("element_type", {})
    if migrations.get("показатель") != "Показатели" or migrations.get("норматив") != "Требования показателей":
        errors.append("v0.4 не объявляет миграцию legacy-показателя и норматива")
    if migrations.get("requires_semantic_resolution") is not True:
        errors.append("v0.4 должна останавливать неоднозначную семантическую миграцию")

    forbidden = {"Наблюдения показателей", "Выполнения расчётов", "Финансовые факты"}
    if forbidden & set(sheets):
        errors.append("schema v0.4 не должна хранить факты территории в канонической книге")
    required_overrides = {"Отклонения", "Гипотезы", "Эксперименты", "Связи модели", "Рабочая панель"}
    if set(overlay.get("sheet_overrides", {})) != required_overrides:
        errors.append("schema v0.4 содержит неожиданный набор sheet overrides")
    deviation = overlay.get("sheet_overrides", {}).get("Отклонения", {})
    if deviation.get("foreign_keys", {}).get("norm_requirement_id") != "Требования показателей.requirement_id":
        errors.append("Отклонения v0.4 должны ссылаться на норматив из Требования показателей")
    for sheet_name in ("Гипотезы", "Эксперименты"):
        foreign_keys = overlay.get("sheet_overrides", {}).get(sheet_name, {}).get("foreign_keys", {})
        if foreign_keys.get("primary_metric_id") != "Показатели.indicator_id":
            errors.append(f"{sheet_name} v0.4 должны ссылаться на Показатели.indicator_id")

    for relative in (
        "scripts/build_template_v0_4.py",
        "scripts/migrate_template_v0_3_to_v0_4.py",
        "scripts/test_template_builder_v0_4.py",
        "scripts/test_migration_v0_3_to_v0_4.py",
        "templates/migrations/v0.3-to-v0.4.md",
    ):
        if not (ROOT / relative).is_file():
            errors.append(f"нет обязательного v0.4 артефакта {relative}")


def validate_version_lifecycle(errors: list[str]) -> None:
    language_path = ROOT / "references" / "LANGUAGE.md"
    metaontology_path = ROOT / "references" / "METAONTOLOGY.md"
    if not language_path.is_file() or not metaontology_path.is_file():
        return

    language = language_path.read_text(encoding="utf-8")
    if "### Продукт производственной системы" in language:
        errors.append("LANGUAGE.md не должен ограничивать реестр продуктов только выходами внутренней системы")
    for marker in (
        "как выходные продукты внутренних производственных систем, так и входящие продукты внешних поставщиков",
        "`целевая` — предлагаемое или предписываемое будущее устройство",
    ):
        if marker not in language:
            errors.append(f"LANGUAGE.md не содержит принятую семантическую формулировку: {marker}")
    if "`целевая` — принятую будущую норму" in language:
        errors.append("LANGUAGE.md смешивает целевой слой с принятием версии")
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
    if not MIGRATION_V3_TO_V4.is_file():
        errors.append("нет templates/migrations/v0.3-to-v0.4.md")
        return
    text_v4 = MIGRATION_V3_TO_V4.read_text(encoding="utf-8")
    for marker in (
        "отдельная книга v0.4 из 37 листов",
        "REQUIRES_INPUT",
        "legacy-показатель",
        "legacy-норматив",
        "SLA не преобразуется автоматически",
        "Экономические правила",
        "source/target fingerprints",
        "migrate_template_v0_3_to_v0_4.py",
    ):
        if marker not in text_v4:
            errors.append(f"v0.3-to-v0.4.md: отсутствует migration marker {marker!r}")


def validate_fresh_agent_contract(errors: list[str]) -> None:
    if not BEHAVIORAL_CASES.is_file() or not FRESH_AGENT_CONTRACT.is_file():
        errors.append("нет cases.yaml или общего FRESH-AGENT-CONTRACT.md")
        return
    cases_text = BEHAVIORAL_CASES.read_text(encoding="utf-8")
    expected_events: set[str] = set()
    for body in re.findall(
        r"^    (?:required_events|forbidden_events): \[(.*?)\]$",
        cases_text,
        re.MULTILINE,
    ):
        expected_events.update(item.strip() for item in body.split(",") if item.strip())
    contract_text = FRESH_AGENT_CONTRACT.read_text(encoding="utf-8")
    vocabulary = re.search(
        r"^## Канонические типы событий\n\n~~~text\n(?P<body>.*?)\n~~~$",
        contract_text,
        re.MULTILINE | re.DOTALL,
    )
    if not vocabulary:
        errors.append("FRESH-AGENT-CONTRACT.md не содержит канонический словарь событий")
        return
    contract_events = {
        line.strip()
        for line in vocabulary.group("body").splitlines()
        if line.strip()
    }
    missing = expected_events - contract_events
    if missing:
        errors.append(
            "FRESH-AGENT-CONTRACT.md не покрывает события cases.yaml: "
            f"{sorted(missing)}"
        )
    for marker in (
        '"provenance": "fresh_agent"',
        '"external_mutations": []',
        "не читает `cases.yaml`, `rubric.yaml`",
        "не переписывает transcript, события или outcome",
    ):
        if marker not in contract_text:
            errors.append(f"FRESH-AGENT-CONTRACT.md: отсутствует marker {marker!r}")


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

    validate_project_context(errors)
    validate_version_lifecycle(errors)
    validate_interview_contract(errors)
    validate_migration_contract(errors)
    validate_template(errors)
    validate_v2_schema(errors)
    validate_v3_schema(errors)
    validate_v4_schema(errors)
    validate_fresh_agent_contract(errors)

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
            "references/METHODOLOGY-COMPATIBILITY.md",
            "references/INTERVIEW-CONTRACT.md",
            "references/TEMPLATE-CONTRACT.md",
        ):
            if reference not in text:
                errors.append(f"{name}: нет обязательной ссылки {reference}")

        for reference_name in (
            "LANGUAGE.md",
            "METAONTOLOGY.md",
            "METHODOLOGY-COMPATIBILITY.md",
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

        bundled_schema_v4 = skill_dir / "references" / "TEMPLATE-SCHEMA-v0.4.json"
        if not bundled_schema_v4.is_file():
            errors.append(f"{name}: нет локальной копии references/TEMPLATE-SCHEMA-v0.4.json")
        elif bundled_schema_v4.read_bytes() != TEMPLATE_SCHEMA_V4.read_bytes():
            errors.append(
                f"{name}: TEMPLATE-SCHEMA-v0.4.json расходится с templates/template-schema-v0.4.json; "
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

        bundled_migration_v4 = skill_dir / "references" / "MIGRATION-v0.3-to-v0.4.md"
        if not bundled_migration_v4.is_file():
            errors.append(f"{name}: нет локальной migration map v0.3-to-v0.4")
        elif bundled_migration_v4.read_bytes() != MIGRATION_V3_TO_V4.read_bytes():
            errors.append(f"{name}: migration map v0.3-to-v0.4 расходится с канонической")

        if name in {"model-production-system", "maintain-production-system", "audit-production-system"}:
            for relative, canonical in (
                ("bpmn/common.py", ROOT / "scripts" / "bpmn" / "common.py"),
                ("bpmn/generate.py", ROOT / "scripts" / "bpmn" / "generate.py"),
                ("bpmn/validate.py", ROOT / "scripts" / "bpmn" / "validate.py"),
                ("versioning/resolve.py", ROOT / "scripts" / "versioning" / "resolve.py"),
                ("build_template_v0_2.py", ROOT / "scripts" / "build_template_v0_2.py"),
                ("build_template_v0_3.py", ROOT / "scripts" / "build_template_v0_3.py"),
                ("build_template_v0_4.py", ROOT / "scripts" / "build_template_v0_4.py"),
                ("migrate_template_v0_2_to_v0_3.py", ROOT / "scripts" / "migrate_template_v0_2_to_v0_3.py"),
                ("migrate_template_v0_3_to_v0_4.py", ROOT / "scripts" / "migrate_template_v0_3_to_v0_4.py"),
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
    if not package_snapshot or package_snapshot.group(1).strip().strip("\"'") != "templates/production-system-model-template-v0.3.xlsx":
        errors.append("skill-package.yaml должен ссылаться на текущий XLSX v0.3")
    package_markers = (
        'version: "0.3.0"',
        'template_schema_base: templates/template-schema-v0.2.json',
        'template_schema_overlay: templates/template-schema-v0.3.json',
        'published_version: "0.3"',
        'migration_v2_to_v3: templates/migrations/v0.2-to-v0.3.md',
        'rollback_version: "0.2"',
    )
    for marker in package_markers:
        if marker not in manifest:
            errors.append(f"skill-package.yaml: отсутствует marker релиза {marker!r}")
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
            if document_type == "spreadsheets" and document_id in {
                PUBLIC_TEMPLATE_ID,
                ROLLBACK_TEMPLATE_ID,
            }:
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
    print("[OK] Паспорт, замысел, стабильный релиз и индекс планов согласованы")
    print("[OK] Frontmatter, UI-метаданные и общие references согласованы")
    print("[OK] Публичный Google Sheets и XLSX v0.3 согласованы; rollback v0.2 сохранён")
    print("[OK] Локальный контракт кандидата v0.4, builder и миграция v0.3→v0.4 согласованы")
    print("[OK] TODO, битые относительные ссылки и типовые секреты не найдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
