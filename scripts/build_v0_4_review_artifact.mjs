#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const artifactToolSpecifier = process.env.CODEX_ARTIFACT_TOOL_MODULE
  ? pathToFileURL(process.env.CODEX_ARTIFACT_TOOL_MODULE).href
  : "@oai/artifact-tool";
const { SpreadsheetFile, Workbook } = await import(artifactToolSpecifier);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = path.join(root, "outputs", "v0.4-review");
const outputPath = path.join(outputDir, "production-system-model-template-v0.4-review.xlsx");

const readJson = async (relative) => JSON.parse(await fs.readFile(path.join(root, relative), "utf8"));

function applyOverlay(schema, overlay) {
  const next = structuredClone(schema);
  const additions = overlay.sheet_order_additions ?? [];
  const anchor = next.sheet_order.indexOf(overlay.insert_after);
  if (anchor < 0) throw new Error(`Unknown overlay anchor: ${overlay.insert_after}`);
  next.sheet_order.splice(anchor + 1, 0, ...additions);
  Object.assign(next.sheets, structuredClone(overlay.sheets ?? {}));
  for (const [sheetName, changes] of Object.entries(overlay.sheet_overrides ?? {})) {
    next.sheets[sheetName] = { ...next.sheets[sheetName], ...structuredClone(changes) };
  }
  Object.assign(next.enums, structuredClone(overlay.enums ?? {}));
  for (const [enumName, values] of Object.entries(overlay.enum_overrides ?? {})) {
    next.enums[enumName] = structuredClone(values);
  }
  next.schema_version = overlay.schema_version;
  next.sheet_count = overlay.sheet_count;
  return next;
}

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

const descriptions = {
  "Показатели": "Определения измеримых характеристик: что, зачем и по какому правилу считается.",
  "Привязки показателей": "Версионные контракты получения фактов из систем-владельцев без копирования фактов в карту.",
  "Требования показателей": "Нормативы, цели и планы для принятых показателей, областей и периодов.",
  "Экономические правила": "Ставки, формулы и правила управленческого расчёта, признания и распределения.",
  "Условия назначений": "Применение схем позиции и подтверждённые индивидуальные отличия назначения по периодам.",
};

const help = {
  "Показатели": "Начните с управленческого вопроса. Наблюдения и временные ряды остаются в системе исполнения.",
  "Привязки показателей": "Источник фактов и источник принятого определения — разные поля. Укажите точный locator и покрытие.",
  "Требования показателей": "Одна строка — один норматив, цель или план. Фактическое значение сюда не записывается.",
  "Экономические правила": "Не смешивайте три оси расхода. Распределение требует принятой базы и правила остатка.",
  "Условия назначений": "Не копируйте типовую схему позиции. Фиксируйте применение или индивидуальное отличие.",
};

const sampleRows = {
  "Показатели": {
    indicator_id: "ind-lead-cycle-time",
    version_id: "ver-demo-v0.4",
    version_operation: "применить",
    system_id: "ps-demo",
    system_selector: "Демонстрационная система",
    indicator_name: "Время обработки лида",
    indicator_kind: "операционный",
    management_question: "Укладывается ли обработка лида в принятую норму?",
    measured_characteristic: "Продолжительность от создания лида до завершения квалификации",
    observation_unit_type: "объект",
    observation_unit_id: "obj-lead",
    observation_unit_selector: "Лид",
    single_unit_rule: "Разница между timestamp создания и завершения квалификации",
    aggregation_rule: "Медиана по завершённым лидам периода",
    unit_of_measure: "час",
    time_attribution_rule: "По дате завершения квалификации",
    required_facts: "lead_created_at; qualification_completed_at",
    coverage_rule: "Обе даты присутствуют у всех включённых лидов",
    knowledge_status: "принято",
    source_id: "src-decision",
    source_selector: "Решение владельца",
  },
  "Привязки показателей": {
    binding_id: "bind-lead-cycle-time-primary",
    version_id: "ver-demo-v0.4",
    version_operation: "применить",
    indicator_id: "ind-lead-cycle-time",
    indicator_selector: "Время обработки лида",
    binding_role: "основной источник",
    fact_source_id: "src-execution-system",
    fact_source_selector: "Система исполнения",
    fact_locator_contract: "execution.lead_events by lead_id",
    required_fact_description: "Создание лида и завершение квалификации",
    coverage_rule: "Не менее 95 % завершённых лидов имеют обе даты",
    valid_from: new Date("2026-09-01T00:00:00Z"),
    knowledge_status: "принято",
    source_id: "src-decision",
    source_selector: "Решение владельца",
  },
  "Требования показателей": {
    requirement_id: "req-lead-cycle-time-norm",
    version_id: "ver-demo-v0.4",
    version_operation: "применить",
    indicator_id: "ind-lead-cycle-time",
    indicator_selector: "Время обработки лида",
    requirement_type: "норматив",
    requirement_name: "Обработать лид не более чем за 72 часа",
    scope_type: "производственная система",
    scope_element_id: "ps-demo",
    scope_element_selector: "Демонстрационная система",
    comparison_operator: "не более",
    target_value: 72,
    period_start: new Date("2026-09-01T00:00:00Z"),
    knowledge_status: "принято",
    source_id: "src-decision",
    source_selector: "Решение владельца",
  },
  "Экономические правила": {
    economic_rule_id: "econ-position-compensation",
    version_id: "ver-demo-v0.4",
    version_operation: "применить",
    system_id: "ps-demo",
    system_selector: "Демонстрационная система",
    rule_name: "Типовая фиксированная компенсация позиции",
    rule_kind: "схема компенсации",
    economic_direction: "расход",
    source_scope_type: "позиция",
    source_scope_id: "pos-manager",
    source_scope_selector: "Менеджер",
    calculation_method: "прямой",
    formula_or_rule: "Фиксированная сумма за месяц назначения",
    amount_value: 100000,
    currency: "RUB",
    period_unit: "месяц",
    expense_attribution: "прямой",
    expense_behavior: "постоянный",
    financial_result_position: "операционный расход",
    valid_from: new Date("2026-09-01T00:00:00Z"),
    knowledge_status: "принято",
    source_id: "src-decision",
    source_selector: "Решение владельца",
  },
  "Условия назначений": {
    assignment_condition_id: "cond-manager-demo",
    version_id: "ver-demo-v0.4",
    version_operation: "применить",
    assignment_id: "asg-manager-demo",
    assignment_selector: "Анна Петрова — Менеджер",
    condition_name: "Применение типовой схемы менеджера",
    condition_type: "фиксированная компенсация",
    compensation_scheme_rule_id: "econ-position-compensation",
    compensation_scheme_rule_selector: "Типовая фиксированная компенсация позиции",
    compensation_scheme_rule_version_id: "ver-demo-v0.4",
    compensation_scheme_rule_version_selector: "Демонстрационная v0.4",
    application_mode: "типовая схема",
    amount_basis: "gross",
    storage_mode: "в модели",
    valid_from: new Date("2026-09-01T00:00:00Z"),
    knowledge_status: "принято",
    source_id: "src-decision",
    source_selector: "Решение владельца",
  },
};

const base = await readJson("templates/template-schema-v0.2.json");
const v3 = await readJson("templates/template-schema-v0.3.json");
const v4 = await readJson("templates/template-schema-v0.4.json");
const schema = applyOverlay(applyOverlay(base, v3), v4);
if (schema.sheet_order.length !== 37) throw new Error("Resolved v0.4 schema must have 37 sheets");

const workbook = Workbook.create();
const requiredFill = "#FFF2CC";
const optionalFill = "#D9EAF7";
const titleFill = "#CFE2F3";
const bodyBorder = "#D9E2F3";

for (const sheetName of schema.sheet_order) {
  const spec = schema.sheets[sheetName];
  const columns = spec.columns ?? [];
  const width = Math.max(columns.length, 6);
  const last = columnName(width - 1);
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  sheet.getRange(`A1:${last}1`).merge();
  sheet.getRange(`A2:${last}2`).merge();
  sheet.getRange(`A3:${last}3`).merge();
  sheet.getRange("A1").values = [[sheetName]];
  sheet.getRange("A2").values = [[descriptions[sheetName] ?? `Раздел канонической модели v0.4: ${sheetName}.`]];
  sheet.getRange("A3").values = [[help[sheetName] ?? "ID открыты; читаемые selectors находятся рядом. Запись — только после подтверждения полного пакета."]];
  sheet.getRange(`A1:${last}1`).format = {
    fill: titleFill,
    font: { bold: true, color: "#1F4E78", size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${last}3`).format = {
    fill: "#F7F9FC",
    font: { color: "#44546A", italic: true, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange(`A4:${last}4`).values = [columns.length ? columns : Array.from({ length: width }, (_, i) => `field_${i + 1}`)];
  sheet.getRange(`A4:${last}4`).format = {
    fill: optionalFill,
    font: { bold: true, color: "#1F4E78", size: 10 },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: bodyBorder },
  };
  for (const required of spec.required ?? []) {
    const index = columns.indexOf(required);
    if (index >= 0) sheet.getRange(`${columnName(index)}4`).format.fill = requiredFill;
  }
  if (columns.length) {
    sheet.getRange(`A5:${last}24`).format = {
      font: { color: "#263238", size: 10 },
      wrapText: true,
      verticalAlignment: "top",
      borders: { preset: "all", style: "thin", color: bodyBorder },
    };
    const sample = sampleRows[sheetName];
    if (sample) {
      sheet.getRange(`A5:${last}5`).values = [columns.map((column) => sample[column] ?? null)];
    }
    for (const [field, enumName] of Object.entries(spec.enums ?? {})) {
      const index = columns.indexOf(field);
      const values = schema.enums[enumName];
      if (index >= 0 && Array.isArray(values) && values.length <= 50) {
        sheet.getRange(`${columnName(index)}5:${columnName(index)}24`).dataValidation = {
          rule: { type: "list", values },
        };
      }
    }
    for (const [field, fieldType] of Object.entries(spec.types ?? {})) {
      const index = columns.indexOf(field);
      if (index >= 0 && (fieldType === "date" || fieldType === "datetime")) {
        sheet.getRange(`${columnName(index)}5:${columnName(index)}24`).setNumberFormat(
          fieldType === "date" ? "yyyy-mm-dd" : "yyyy-mm-dd hh:mm"
        );
      }
    }
  }
  sheet.getRange(`A1:${last}24`).format.autofitRows();
  sheet.getRange(`A1:${last}24`).format.autofitColumns();
  for (let i = 0; i < columns.length; i += 1) {
    const name = columns[i];
    const target = sheet.getRange(`${columnName(i)}:${columnName(i)}`);
    if (name.endsWith("_id") || name === "version_id") target.format.columnWidthPx = 150;
    else if (name.endsWith("_selector")) target.format.columnWidthPx = 210;
    else if (/formula|rule|description|question|boundary|facts|locator|notes/.test(name)) target.format.columnWidthPx = 260;
    else target.format.columnWidthPx = 140;
  }
  sheet.freezePanes.freezeRows(4);
  if (columns.length > 4) sheet.freezePanes.freezeColumns(Math.min(3, columns.length));
}

await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

const previewSheets = [
  "Показатели",
  "Привязки показателей",
  "Требования показателей",
  "Экономические правила",
  "Условия назначений",
];
for (const sheetName of previewSheets) {
  const preview = await workbook.render({
    sheetName,
    range: "A1:P8",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(outputDir, `${sheetName.replaceAll(" ", "-").toLowerCase()}.png`),
    new Uint8Array(await preview.arrayBuffer())
  );
}

const inspection = await workbook.inspect({
  kind: "workbook,sheet,region",
  maxChars: 12000,
  tableMaxRows: 6,
  tableMaxCols: 16,
  tableMaxCellChars: 100,
});
await fs.writeFile(path.join(outputDir, "inspection.ndjson"), inspection.ndjson ?? String(inspection));
await fs.writeFile(
  path.join(outputDir, "README.md"),
  `# Локальная визуальная приёмка v0.4\n\n` +
    `Этот каталог содержит review-артефакты release candidate v0.4:\n\n` +
    `- \`production-system-model-template-v0.4-review.xlsx\` — локальный 37-листовой макет из композиции schema v0.2+v0.3+v0.4;\n` +
    `- пять PNG — представительные строки новых реестров измеримости и экономики;\n` +
    `- \`inspection.ndjson\` — структурная проверка 37 листов.\n\n` +
    `Артефакты воспроизводятся командой:\n\n` +
    `~~~bash\n` +
    `CODEX_ARTIFACT_TOOL_MODULE=/absolute/path/to/@oai/artifact-tool/dist/artifact_tool.mjs node scripts/build_v0_4_review_artifact.mjs\n` +
    `~~~\n\n` +
    `Это не канонический XLSX-снимок, не данные реальной компании и не вторая реализация Google Sheets builder. ` +
    `Файл проверяет структуру, читаемость, соседство ID/selectors, даты и dropdown; точные formulas, named ranges, protections и \`Рабочая панель\` задаёт \`scripts/build_template_v0_4.py\` и нужно проверить в отдельной Google Таблице перед публикацией.\n`
);

process.stdout.write(`${outputPath}\n`);
