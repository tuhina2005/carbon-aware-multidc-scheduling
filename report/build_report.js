// Build the CSD493 final report:  cd report && NODE_PATH=<dir with node_modules/docx> node build_report.js
const fs = require("fs");
const L = require("./lib.js");
const { d, FONT, MARGIN, COVER_MARGIN, LINE, references, checkLabels } = L;
const A = require("./content_a.js");
const B = require("./content_b.js");

const footer = (fmt) => new d.Footer({ children: [new d.Paragraph({ alignment: d.AlignmentType.CENTER,
  children: [new d.TextRun({ children: [d.PageNumber.CURRENT], font: FONT, size: 20 })] })] });

const page = (fmt, start, margin = MARGIN) => ({
  page: { size: { width: 11906, height: 16838 }, margin,
          pageNumbers: start ? { start, formatType: fmt } : { formatType: fmt } },
});

// Build content in document order (citations are numbered by first appearance).
// Order required by the B.Tech format: cover, declaration, acknowledgements, contents, list of tables,
// list of figures, symbols and abbreviations, abstract (no project certificate page).
const front = [...A.declaration(), ...A.acknowledgements(), ...A.toc(), ...A.listOfTables(), ...A.listOfFigures(),
               ...A.abbreviations(), ...A.abstract()];
const body = [...A.ch1(), ...A.ch2(), ...A.ch3(), ...B.ch4(), ...B.ch5(), ...B.ch6(), ...B.ch7(), ...B.ch8(), ...B.ch9()];
const refs = [new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true,
  children: [new d.TextRun({ text: "References", font: FONT })] }), ...references()];
checkLabels();

const doc = new d.Document({
  creator: "CSD493 project", title: A.TITLE, description: "Final project report",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 36, bold: true },
        paragraph: { spacing: { before: 240, after: 360, line: LINE }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true },
        paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
      // caption styles feed the List of Figures / List of Tables
      { id: "FigCaption", name: "FigCaption", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22 }, paragraph: { alignment: d.AlignmentType.CENTER } },
      { id: "TabCaption", name: "TabCaption", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22 }, paragraph: { alignment: d.AlignmentType.CENTER } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, italics: true },
        paragraph: { spacing: { before: 160, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: d.LevelFormat.BULLET, text: "•", alignment: d.AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: d.LevelFormat.DECIMAL, text: "%1.", alignment: d.AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [
    { properties: { ...page(d.NumberFormat.DECIMAL, undefined, COVER_MARGIN), titlePage: true }, children: A.titlePage() },
    { properties: page(d.NumberFormat.LOWER_ROMAN, 1), footers: { default: footer() }, children: front },
    { properties: page(d.NumberFormat.DECIMAL, 1), footers: { default: footer() }, children: [...body, ...refs] },
  ],
});

d.Packer.toBuffer(doc).then((buf) => {
  const out = "CSD493_Final_Report.docx";
  fs.writeFileSync(out, buf);
  console.log(`wrote report/${out} (${(buf.length / 1024).toFixed(0)} KB)`);
});
