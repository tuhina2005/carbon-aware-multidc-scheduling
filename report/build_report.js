// Build the CSD493 final report:  cd report && NODE_PATH=<dir with node_modules/docx> node build_report.js
const fs = require("fs");
const L = require("./lib.js");
const { d, FONT, MARGIN, references, checkLabels } = L;
const A = require("./content_a.js");
const B = require("./content_b.js");

const footer = (fmt) => new d.Footer({ children: [new d.Paragraph({ alignment: d.AlignmentType.CENTER,
  children: [new d.TextRun({ children: [d.PageNumber.CURRENT], font: FONT, size: 20 })] })] });

const page = (fmt, start) => ({
  page: { size: { width: 11906, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
          pageNumbers: start ? { start, formatType: fmt } : { formatType: fmt } },
});

// Build content in document order (citations are numbered by first appearance).
const front = [...A.declaration(), ...A.abstract(), ...A.toc()];
const body = [...A.ch1(), ...A.ch2(), ...A.ch3(), ...B.ch4(), ...B.ch5(), ...B.ch6(), ...B.ch7(), ...B.ch8()];
const refs = [new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true,
  children: [new d.TextRun({ text: "References", font: FONT })] }), ...references()];
const app = B.appendix();
checkLabels();

const doc = new d.Document({
  creator: "CSD493 project", title: A.TITLE, description: "Final project report",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true },
        paragraph: { spacing: { before: 240, after: 240 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true },
        paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
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
    { properties: { ...page(d.NumberFormat.DECIMAL), titlePage: true }, children: A.titlePage() },
    { properties: page(d.NumberFormat.LOWER_ROMAN, 1), footers: { default: footer() }, children: front },
    { properties: page(d.NumberFormat.DECIMAL, 1), footers: { default: footer() }, children: [...body, ...refs, ...app] },
  ],
});

d.Packer.toBuffer(doc).then((buf) => {
  const out = "CSD493_Final_Report.docx";
  fs.writeFileSync(out, buf);
  console.log(`wrote report/${out} (${(buf.length / 1024).toFixed(0)} KB)`);
});
