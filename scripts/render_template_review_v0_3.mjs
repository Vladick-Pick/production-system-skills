#!/usr/bin/env node
/** Собрать локальный визуальный review-артефакт v0.3 через @oai/artifact-tool.
 *
 * Это не канонический XLSX-снимок. Канонический snapshot экспортируется только
 * из принятой Google Таблицы во время отдельного WP-7.
 */

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "v0.3-review");
const base = JSON.parse(await fs.readFile(path.join(root, "templates", "template-schema-v0.2.json"), "utf8"));
const overlay = JSON.parse(await fs.readFile(path.join(root, "templates", "template-schema-v0.3.json"), "utf8"));

function composeSchema() {
  const schema = structuredClone(base);
  const anchor = schema.sheet_order.indexOf(overlay.insert_after) + 1;
  schema.sheet_order.splice(anchor, 0, ...overlay.sheet_order_additions);
  Object.assign(schema.sheets, structuredClone(overlay.sheets));
  for (const [name, changes] of Object.entries(overlay.sheet_overrides ?? {})) {
    Object.assign(schema.sheets[name], structuredClone(changes));
  }
  Object.assign(schema.enums, structuredClone(overlay.enums));
  schema.schema_version = overlay.schema_version;
  schema.sheet_count = overlay.sheet_count;
  return schema;
}

const schema = composeSchema();
if (schema.sheet_order.length !== 32 || new Set(schema.sheet_order).size !== 32) {
  throw new Error("Review builder expected exactly 32 unique sheets");
}

const COLORS = {
  title: "#DCEAF7",
  section: "#DDEBF7",
  required: "#FFF2CC",
  computed: "#DDEBF7",
  selector: "#EAF4FF",
  helper: "#F2F2F2",
  line: "#D9E2F3",
  text: "#233746",
  muted: "#536B7A",
  good: "#E2F0D9",
  warning: "#FCE4D6",
};

const descriptions = {
  Инструкция: "Как использовать каноническую модель бизнеса v0.3.",
  Система: "Настройки одной модели бизнеса и внутренние производственные системы.",
  Отклонения: "Фактические различия между действующей нормой и работой системы.",
  Гипотезы: "Новые внешние возможности развития системы.",
  Эксперименты: "Ограниченные проверки исправлений и гипотез развития.",
  "Рабочая панель": "Связный обзор выбранных версии, системы и процесса.",
};

const help = {
  Отклонения: "Для подтверждения нужны действующая норма и наблюдаемый факт. Причина не становится гипотезой развития.",
  Гипотезы: "Сформулированная гипотеза начинается с внешнего изменения и проверяемого источника.",
  Эксперименты: "Выберите ровно одно основание: отклонение или гипотезу. Решения подтверждает человек.",
};

function colLetter(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function setValues(sheet, startRow, startCol, rows) {
  if (!rows.length || !rows[0]?.length) return;
  const endRow = startRow + rows.length - 1;
  const endCol = startCol + rows[0].length - 1;
  sheet.getRange(`${colLetter(startCol)}${startRow}:${colLetter(endCol)}${endRow}`).values = rows;
}

function baseSheetStyle(sheet, width = 12) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${colLetter(width - 1)}80`).format = {
    font: { name: "Aptos", size: 10, color: COLORS.text },
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${colLetter(width - 1)}80`).format.rowHeightPx = 22;
}

function styleBand(sheet, range, fill, font = {}) {
  sheet.getRange(range).format = {
    fill,
    font: { color: COLORS.text, bold: true, ...font },
    wrapText: true,
    verticalAlignment: "center",
  };
}

function buildInstruction(sheet) {
  baseSheetStyle(sheet, 8);
  sheet.mergeCells("A1:H1");
  sheet.getRange("A1").values = [["Шаблон канонической модели бизнеса v0.3 — локальный review"]];
  styleBand(sheet, "A1:H1", COLORS.title, { size: 18 });
  sheet.mergeCells("A2:H2");
  sheet.getRange("A2").values = [["Демонстрационный артефакт для визуальной проверки. Это не опубликованный канонический шаблон и не данные компании."]];
  sheet.getRange("A2:H2").format = { fill: COLORS.warning, font: { italic: true, color: COLORS.muted }, wrapText: true };
  const rows = [
    ["Шаг", "Что делать", "Зачем"],
    ["1", "Выберите читаемое значение в selector", "Стабильный ID хранится рядом и остаётся видимым"],
    ["2", "Сначала уточните смысл и связи", "Запись создаётся только после полного пакета и подтверждения"],
    ["3", "Отклонение сравнивайте с действующей нормой", "Разница с будущей целью — не отклонение"],
    ["4", "Гипотезу начинайте с внешней возможности", "Причина отклонения остаётся причиной"],
    ["5", "Эксперимент связывайте с одним основанием", "Проверяется отклонение или гипотеза, не оба сразу"],
    ["6", "Используйте Рабочую панель", "Она связывает процесс, объект, материалы, контракты и контур развития"],
    ["7", "Мигрируйте v0.2 только в отдельную копию", "Исходная книга остаётся точкой rollback"],
  ];
  setValues(sheet, 4, 0, rows);
  styleBand(sheet, "A4:C4", COLORS.required);
  sheet.getRange("A4:C11").format.borders = { preset: "all", style: "thin", color: COLORS.line };
  sheet.getRange("A4:C11").format.wrapText = true;
  sheet.getRange("A:A").format.columnWidthPx = 60;
  sheet.getRange("B:B").format.columnWidthPx = 270;
  sheet.getRange("C:C").format.columnWidthPx = 420;
  sheet.freezePanes.freezeRows(4);
}

function buildPanel(sheet) {
  baseSheetStyle(sheet, 39);
  sheet.mergeCells("A1:L1");
  sheet.getRange("A1").values = [["Рабочая панель модели бизнеса v0.3 — демонстрационное состояние"]];
  styleBand(sheet, "A1:L1", COLORS.title, { size: 18 });
  sheet.mergeCells("A2:L2");
  sheet.getRange("A2").values = [["Selector показывает только читаемый текст; технический ID открыт рядом. Ниже — связный срез одного выбранного процесса."]];
  sheet.getRange("A2:L2").format = { font: { italic: true, color: COLORS.muted }, wrapText: true };
  setValues(sheet, 3, 0, [
    ["Версия", "Текущая модель v0.3", "", "selected_version_id", "ver-demo-v0.3"],
    ["Система", "Привлечение", "", "selected_system_id", "ps-demo-attraction"],
    ["Процесс", "Обработка лида", "", "selected_process_id", "prc-demo-lead"],
  ]);
  sheet.getRange("B3:B5").format.fill = COLORS.selector;
  sheet.getRange("D3:E5").format.fill = COLORS.helper;
  sheet.getRange("A3:E5").format.borders = { preset: "all", style: "thin", color: COLORS.line };

  const sections = [
    { row: 7, col: 0, width: 5, title: "Паспорт системы", headers: ["system_id", "система", "назначение", "владелец", "статус"], values: ["ps-demo-attraction", "Привлечение", "Создать квалифицированный спрос", "Владелец ПС", "действует"] },
    { row: 7, col: 6, width: 6, title: "Паспорт процесса", headers: ["process_id", "процесс", "цель", "триггер", "вход", "выход"], values: ["prc-demo-lead", "Обработка лида", "Квалифицировать лид", "Получен лид", "Лид", "Квалифицированный лид"] },
    { row: 12, col: 0, width: 6, title: "Действия и состояния", headers: ["action_id", "действие", "состояние до", "состояние после", "позиция", "срок"], values: ["act-demo-qualify", "Квалифицировать лид", "Новый", "Квалифицирован", "Менеджер", "3 дня"] },
    { row: 12, col: 6, width: 6, title: "Материалы процесса", headers: ["action_id", "действие", "material_id", "материал", "роль", "использование"], values: ["act-demo-qualify", "Квалифицировать лид", "mat-demo-script", "Скрипт квалификации", "инструкция", "Подсказывает вопросы"] },
    { row: 17, col: 0, width: 7, title: "Внешняя цепочка", headers: ["контрагент", "направление", "продукт", "контракт", "интерфейс", "документ", "действие"], values: ["Поставщик лидов", "поставляет", "Лид качества A", "Поставка лидов", "API CRM", "Открыть документ", "Принять лид"] },
    { row: 22, col: 0, width: 6, title: "Связано с выбранным процессом", headers: ["тип", "ID", "название", "статус", "следующий шаг", "срок"], values: ["отклонение", "dev-demo-sla", "Нарушается SLA", "в устранении", "Проверить исправление", "2026-08-20"] },
    { row: 22, col: 6, width: 6, title: "Влияет на систему в целом", headers: ["тип", "ID", "название", "статус", "следующий шаг", "срок"], values: ["гипотеза", "hyp-demo-ai", "Расшифровка звонков", "сформулирована", "Подготовить эксперимент", "2026-08-25"] },
    { row: 27, col: 0, width: 6, title: "Продукты системы", headers: ["product_id", "продукт", "определение", "критерий приёмки", "владелец", "статус"], values: ["prd-demo-qualified-lead", "Квалифицированный лид", "Лид, соответствующий критериям", "Все обязательные поля подтверждены", "Владелец ПС", "действует"] },
    { row: 27, col: 6, width: 6, title: "Вложенные процессы", headers: ["process_id", "процесс", "цель", "статус", "владелец", "просмотр"], values: ["prc-demo-call", "Провести звонок", "Получить данные для квалификации", "действует", "Руководитель продаж", "Выбрать в selector"] },
    { row: 32, col: 0, width: 6, title: "Основной объект и жизненный цикл", headers: ["object_id", "объект", "состояние", "terminal", "разрешённые действия", "источник"], values: ["obj-demo-lead", "Лид", "Квалифицирован", "нет", "Передать в продажи", "Регламент квалификации"] },
    { row: 32, col: 6, width: 6, title: "Проверки и BPMN/SVG", headers: ["тип", "ID", "статус", "fingerprint", "ссылка", "следующий шаг"], values: ["BPMN/SVG", "bld-demo-process", "готова к просмотру", "sha256:demo", "Открыть SVG", "Проверить в Camunda"] },
  ];
  for (const section of sections) {
    const start = colLetter(section.col);
    const end = colLetter(section.col + section.width - 1);
    sheet.mergeCells(`${start}${section.row}:${end}${section.row}`);
    sheet.getRange(`${start}${section.row}`).values = [[section.title]];
    styleBand(sheet, `${start}${section.row}:${end}${section.row}`, COLORS.section);
    setValues(sheet, section.row + 1, section.col, [section.headers, section.values]);
    styleBand(sheet, `${start}${section.row + 1}:${end}${section.row + 1}`, COLORS.required);
    sheet.getRange(`${start}${section.row + 1}:${end}${section.row + 2}`).format.borders = { preset: "all", style: "thin", color: COLORS.line };
    sheet.getRange(`${start}${section.row + 1}:${end}${section.row + 2}`).format.wrapText = true;
    sheet.getRange(`${start}${section.row + 2}:${end}${section.row + 2}`).format.rowHeightPx = 42;
  }
  for (let i = 0; i < 12; i += 1) sheet.getRange(`${colLetter(i)}:${colLetter(i)}`).format.columnWidthPx = 125;
  sheet.getRange("C:C").format.columnWidthPx = 200;
  sheet.getRange("D:D").format.columnWidthPx = 170;
  sheet.getRange("J:J").format.columnWidthPx = 180;
  sheet.freezePanes.freezeRows(5);
}

const newExamples = {
  Отклонения: {
    deviation_id: "dev-demo-sla",
    deviation_title: "Срок обработки превышает SLA",
    deviation_status: "подтверждено",
    deviation_type: "операционное",
    scope_type: "процесс",
    scope_element_id: "prc-demo-lead",
    scope_element_selector: "Обработка лида",
    applicable_version_id: "ver-demo-v0.3",
    applicable_version_selector: "Текущая модель v0.3",
    expected_behavior: "Лид обработан не позднее 3 дней",
    observed_fact: "Один лид обработан за 5 дней",
    evidence_channel: "интерфейс исполнения",
    source_id: "src-demo-crm",
    source_selector: "CRM — журнал лидов",
    source_locator: "lead/demo-42/history",
    next_step: "Проверить причину задержки",
    due_date: new Date("2026-08-20T00:00:00Z"),
  },
  Гипотезы: {
    hypothesis_id: "hyp-demo-transcript",
    hypothesis_title: "Автоматическая расшифровка ускорит квалификацию",
    hypothesis_status: "сформулирована",
    external_change: "Появилась надёжная расшифровка звонков",
    source_id: "src-demo-research",
    source_selector: "Обзор технологии расшифровки",
    source_locator: "public-demo-source#capability",
    new_opportunity: "Разбирать звонок без ручного конспекта",
    scope_type: "процесс",
    scope_element_id: "prc-demo-lead",
    scope_element_selector: "Обработка лида",
    proposed_change: "Добавить расшифровку после звонка",
    mechanism: "Менеджер меньше времени тратит на конспект",
    baseline: "20 минут",
    expected_target: "12 минут",
    next_step: "Подготовить эксперимент",
    due_date: new Date("2026-08-25T00:00:00Z"),
  },
  Эксперименты: {
    experiment_id: "exp-demo-transcript",
    experiment_title: "Проверка расшифровки на 20 звонках",
    experiment_status: "подготовлен",
    basis_type: "гипотеза",
    hypothesis_id: "hyp-demo-transcript",
    hypothesis_selector: "Автоматическая расшифровка ускорит квалификацию",
    base_version_id: "ver-demo-v0.3",
    base_version_selector: "Текущая модель v0.3",
    scope_type: "процесс",
    scope_element_id: "prc-demo-lead",
    scope_element_selector: "Обработка лида",
    temporary_change: "Добавить расшифровку после звонка",
    instances_or_volume: "20 звонков",
    comparison_method: "Сравнить медианное время с baseline",
    baseline: "20 минут",
    success_criterion: "Не более 12 минут без снижения качества",
    stop_condition: "Утечка данных или ухудшение качества",
    rollback_plan: "Отключить расшифровку",
    next_step: "Получить решение о запуске",
    due_date: new Date("2026-08-28T00:00:00Z"),
  },
};

function buildRegistry(sheet, name, definition) {
  const columns = definition.columns ?? [];
  const width = Math.max(columns.length, 8);
  baseSheetStyle(sheet, width);
  const end = colLetter(width - 1);
  const introEnd = colLetter(Math.min(width, 12) - 1);
  sheet.mergeCells(`A1:${introEnd}1`);
  sheet.getRange("A1").values = [[name]];
  styleBand(sheet, `A1:${introEnd}1`, COLORS.title, { size: 16 });
  sheet.mergeCells(`A2:${introEnd}2`);
  sheet.getRange("A2").values = [[descriptions[name] ?? `Лист канонической модели v0.3: ${name}.`]];
  sheet.getRange(`A2:${introEnd}2`).format = { font: { italic: true, color: COLORS.muted }, wrapText: true };
  sheet.mergeCells(`A3:${introEnd}3`);
  sheet.getRange("A3").values = [[help[name] ?? "ID остаются видимыми; читаемые selectors находятся рядом. Запись — только после подтверждения полного пакета."]];
  sheet.getRange(`A3:${introEnd}3`).format = { fill: COLORS.helper, font: { color: COLORS.muted }, wrapText: true };
  sheet.getRange("1:1").format.rowHeightPx = 34;
  sheet.getRange("2:2").format.rowHeightPx = 30;
  sheet.getRange("3:3").format.rowHeightPx = 38;
  setValues(sheet, 4, 0, [columns]);
  const required = new Set(definition.required ?? []);
  const computed = new Set(definition.computed ?? []);
  for (let i = 0; i < columns.length; i += 1) {
    const fill = computed.has(columns[i]) ? COLORS.computed : required.has(columns[i]) ? COLORS.required : COLORS.section;
    styleBand(sheet, `${colLetter(i)}4`, fill);
    const widthPx = columns[i].endsWith("_id") ? 145 : columns[i].endsWith("_selector") ? 240 : columns[i].includes("title") ? 260 : 175;
    sheet.getRange(`${colLetter(i)}:${colLetter(i)}`).format.columnWidthPx = widthPx;
  }
  const example = newExamples[name];
  if (example) {
    setValues(sheet, 5, 0, [columns.map((column) => example[column] ?? null)]);
    sheet.getRange(`A5:${end}5`).format = { fill: "#FFFFFF", wrapText: true, borders: { preset: "all", style: "thin", color: COLORS.line } };
    sheet.getRange("5:5").format.rowHeightPx = 56;
    for (let i = 0; i < columns.length; i += 1) {
      if ((definition.types ?? {})[columns[i]] === "date") sheet.getRange(`${colLetter(i)}5`).format.numberFormat = "yyyy-mm-dd";
      if ((definition.types ?? {})[columns[i]] === "datetime") sheet.getRange(`${colLetter(i)}5`).format.numberFormat = "yyyy-mm-dd hh:mm";
    }
  }
  sheet.getRange(`A4:${end}12`).format.borders = { preset: "all", style: "thin", color: COLORS.line };
  sheet.getRange(`A4:${end}12`).format.wrapText = true;
  sheet.freezePanes.freezeRows(4);
}

const workbook = Workbook.create();
for (const name of schema.sheet_order) workbook.worksheets.add(name);

for (const name of schema.sheet_order) {
  const sheet = workbook.worksheets.getItem(name);
  if (name === "Инструкция") buildInstruction(sheet);
  else if (name === "Рабочая панель") buildPanel(sheet);
  else buildRegistry(sheet, name, schema.sheets[name]);
}

await fs.mkdir(outputDir, { recursive: true });
const sheetsInspection = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 8000 });
const panelInspection = await workbook.inspect({ kind: "region", sheetId: "Рабочая панель", range: "A1:L30", maxChars: 10000 });
await fs.writeFile(path.join(outputDir, "inspection.ndjson"), `${sheetsInspection.ndjson}\n${panelInspection.ndjson}\n`, "utf8");

for (const [sheetName, range, fileName] of [
  ["Рабочая панель", "A1:L39", "working-panel.png"],
  ["Отклонения", "A1:P6", "deviations.png"],
  ["Гипотезы", "A1:P6", "hypotheses.png"],
  ["Эксперименты", "A1:P6", "experiments.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, "production-system-model-template-v0.3-review.xlsx"));
console.log(JSON.stringify({
  status: "ok",
  sheet_count: schema.sheet_order.length,
  output_dir: outputDir,
  workbook: "production-system-model-template-v0.3-review.xlsx",
  previews: ["working-panel.png", "deviations.png", "hypotheses.png", "experiments.png"],
}, null, 2));
