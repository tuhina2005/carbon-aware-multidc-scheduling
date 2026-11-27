// Building blocks for the CSD493 report: inline markup, citations, numbered figures/tables/equations.
const fs = require("fs");
const path = require("path");
const d = require("docx");

const FONT = "Times New Roman";
const MONO = "Consolas";
// A4; B.Tech format: body margins top/bottom 3 cm, left 4 cm, right 2 cm; cover 4 cm all round (1 cm = 567 DXA)
const PAGE_W = 11906, CM = 567;
const MARGIN = { top: 3 * CM, bottom: 3 * CM, left: 4 * CM, right: 2 * CM };
const COVER_MARGIN = { top: 4 * CM, bottom: 4 * CM, left: 4 * CM, right: 4 * CM };
const TEXT_W = PAGE_W - MARGIN.left - MARGIN.right; // 8504 DXA
const LINE = 360; // 1.5 line spacing

// ---------------------------------------------------------------- citations (IEEE, order of appearance)
const REFS = require("./refs.js");
const order = [];
function cite(keys) {
  const nums = keys.split(",").map((k) => k.trim()).map((k) => {
    if (!REFS[k]) throw new Error(`unknown reference ${k}`);
    if (!order.includes(k)) order.push(k);
    return order.indexOf(k) + 1;
  });
  return `[${nums.join("], [")}]`;
}

// ---------------------------------------------------------------- numbered objects (labels declared up front)
const LABELS = require("./labels.js"); // { fig: {key: "3.1"}, tab: {...}, eq: {...} }
const used = { fig: new Set(), tab: new Set(), eq: new Set() };
function ref(kind, key) {
  const n = LABELS[kind][key];
  if (!n) throw new Error(`unknown ${kind} label ${key}`);
  return { fig: "Fig. ", tab: "Table ", eq: "Eq. (" }[kind] + n + (kind === "eq" ? ")" : "");
}

// ---------------------------------------------------------------- inline markup -> TextRuns
// **bold**  *italic*  `code`  _{sub}  ^{sup}  [cite:a,b]  [fig:x] [tab:x] [eq:x]
function runs(text, base = {}) {
  // keep numbers glued to their % sign and to a preceding comparison sign
  text = text.replace(/ %/g, "\u00A0%").replace(/([≥≤≈]) (?=\d)/g, "$1\u00A0");
  text = text.replace(/\[cite:([^\]]+)\]/g, (_, k) => cite(k))
             .replace(/\[(fig|tab|eq):([^\]]+)\]/g, (_, k, v) => ref(k, v));
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|_\{[^}]*\}|\^\{[^}]*\})/g;
  let last = 0, m;
  const text_ = (t, o) => new d.TextRun({ text: t, font: FONT, ...base, ...o });
  // plain-text URLs become clickable links
  const push = (t, o = {}) => {
    if (!t) return;
    t.split(/(https?:\/\/[^\s)]+[^\s).,;])/).forEach((part, i) => {
      if (!part) return;
      if (i % 2) out.push(new d.ExternalHyperlink({ link: part,
        children: [text_(part, { ...o, color: "1F4E9A", underline: { type: d.UnderlineType.SINGLE } })] }));
      else out.push(text_(part, o));
    });
  };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("`")) push(tok.slice(1, -1), { font: MONO, size: (base.size || 24) - 3 });
    else if (tok.startsWith("_{")) push(tok.slice(2, -1), { subScript: true });
    else if (tok.startsWith("^{")) push(tok.slice(2, -1), { superScript: true });
    else push(tok.slice(1, -1), { italics: true });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return out;
}

const P = (text, opts = {}) => new d.Paragraph({
  children: runs(text, opts.run || {}), alignment: opts.align || d.AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: LINE, ...(opts.spacing || {}) }, indent: opts.indent, keepNext: opts.keepNext,
});

let listInstance = 0; // each numbered list restarts at 1
const bullets = (items, ref = "bullets", instance = 0) => items.map((t) => new d.Paragraph({
  children: runs(t), numbering: { reference: ref, level: 0, instance }, alignment: d.AlignmentType.JUSTIFIED,
  spacing: { after: 80, line: LINE },
}));
const numbered = (items) => bullets(items, "numbers", ++listInstance);

let chapter = 0;
const H1 = (title, { numberless = false } = {}) => {
  if (!numberless) chapter += 1;
  return new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true,
    children: numberless ? [new d.TextRun({ text: title, font: FONT })]
      : [new d.TextRun({ text: `Chapter ${chapter}`, font: FONT, size: 28 }),
         new d.TextRun({ text: title, font: FONT, break: 1 })] });
};
const H2 = (num, title) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_2,
  children: [new d.TextRun({ text: `${num}  ${title}`, font: FONT })] });
const H3 = (title) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_3,
  children: [new d.TextRun({ text: title, font: FONT })] });

// Equation: centred expression, number right-aligned "(3.1)"
function EQ(key, expr) {
  const n = LABELS.eq[key];
  if (!n) throw new Error(`eq label ${key}`);
  used.eq.add(key);
  return new d.Paragraph({
    tabStops: [{ type: d.TabStopType.CENTER, position: TEXT_W / 2 }, { type: d.TabStopType.RIGHT, position: TEXT_W }],
    spacing: { before: 80, after: 160 },
    children: [new d.TextRun({ text: "\t", font: FONT }), ...runs(expr, { font: "Cambria Math" }),
               new d.TextRun({ text: `\t(${n})`, font: FONT })],
  });
}

// Statement block (proposition / lemma): bold lead + italic body
const STMT = (lead, body) => new d.Paragraph({
  children: [new d.TextRun({ text: lead + " ", bold: true, font: FONT }), ...runs(body, { italics: true })],
  alignment: d.AlignmentType.JUSTIFIED, spacing: { before: 80, after: 120, line: LINE },
  indent: { left: 360, right: 360 },
});

// Short titles (List of Figures / List of Tables); the full caption follows as a description.
function title(kind, key) {
  const t = (LABELS.title || {})[kind] && LABELS.title[kind][key];
  if (!t) throw new Error(`no short title for ${kind} ${key}`);
  return t;
}

// ---------------------------------------------------------------- figures
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function FIG(key, file, caption, widthIn = 6.2) {
  const n = LABELS.fig[key];
  if (!n) throw new Error(`fig label ${key}`);
  used.fig.add(key);
  const { w, h } = pngSize(file);
  const width = Math.round(Math.min(widthIn, TEXT_W / 1440) * 96), height = Math.round((width * h) / w);
  return [
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new d.ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width, height },
        altText: { title: `Fig. ${n}`, description: caption.replace(/[*`_{}^]/g, ""), name: `fig${n}` } })] }),
    new d.Paragraph({ style: "FigCaption", alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { after: 60 },
      children: [new d.TextRun({ text: `Figure ${n}: `, bold: true, font: FONT, size: 22 }), ...runs(title("fig", key), { size: 22, bold: true })] }),
    new d.Paragraph({ alignment: d.AlignmentType.JUSTIFIED, spacing: { after: 240, line: 276 }, indent: { left: 360, right: 360 },
      children: runs(caption, { size: 20 }) }),
  ];
}

// ---------------------------------------------------------------- tables (caption above)
const BORDER = { style: d.BorderStyle.SINGLE, size: 4, color: "999999" };
function TAB(key, caption, header, rows, widths, { fontSize = 18, align = null } = {}) {
  const n = key ? LABELS.tab[key] : null; // key = null: an uncaptioned table (front matter)
  if (key && !n) throw new Error(`tab label ${key}`);
  if (key) used.tab.add(key);
  const total = widths.reduce((a, b) => a + b, 0);
  const scale = TEXT_W / total;
  const cw = widths.map((x) => Math.floor(x * scale));
  cw[cw.length - 1] += TEXT_W - cw.reduce((a, b) => a + b, 0);
  const cell = (t, i, head) => new d.TableCell({
    width: { size: cw[i], type: d.WidthType.DXA },
    borders: { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER },
    shading: head ? { type: d.ShadingType.CLEAR, color: "auto", fill: "E8E7E3" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    // text columns read better left-aligned; short values (numbers, ticks) stay centred
    // explicit per-column alignment ("L"/"C") when given; otherwise text columns left, short values centred
    children: [new d.Paragraph({ alignment: (align ? align[i] === "L" : i === 0 || String(t).replace(/\*\*/g, "").length > 18)
        ? d.AlignmentType.LEFT : d.AlignmentType.CENTER,
      children: runs(String(t), { size: fontSize, bold: head || undefined }) })],
  });
  const captionParas = !key ? [] : [
    new d.Paragraph({ style: "TabCaption", alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 60 },
      children: [new d.TextRun({ text: `Table ${n}: `, bold: true, font: FONT, size: 22 }), ...runs(title("tab", key), { size: 22, bold: true })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, keepNext: true, spacing: { after: 80, line: 276 },
      children: runs(caption, { size: 20 }) }),
  ];
  return [
    ...captionParas,
    new d.Table({ width: { size: TEXT_W, type: d.WidthType.DXA }, columnWidths: cw,
      rows: [new d.TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }),
             ...rows.map((r) => new d.TableRow({ children: r.map((c, i) => cell(c, i, false)) }))] }),
    new d.Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

function references() {
  return order.map((k, i) => new d.Paragraph({
    children: [new d.TextRun({ text: `[${i + 1}]\t`, font: FONT }), ...runs(REFS[k])],
    tabStops: [{ type: d.TabStopType.LEFT, position: 540 }], indent: { left: 540, hanging: 540 },
    spacing: { after: 100, line: LINE }, alignment: d.AlignmentType.LEFT,
  }));
}

function checkLabels() {
  for (const kind of ["fig", "tab", "eq"]) {
    for (const k of Object.keys(LABELS[kind])) if (!used[kind].has(k)) throw new Error(`${kind} ${k} declared but never placed`);
  }
}

module.exports = { d, FONT, TEXT_W, MARGIN, COVER_MARGIN, LINE, PAGE_W, P, bullets, numbered, H1, H2, H3, EQ, STMT, FIG, TAB, runs,
                   references, checkLabels, ref };
