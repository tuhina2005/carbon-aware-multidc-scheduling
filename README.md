# Artifact for the paper: Carbon-Aware Mapping and Scheduling for Deadline-Constrained Workflows

This repository contains the original CWM artifact (`code_cwm/`, `code_cawosched/`) and our
multi-data-centre extension (`cwm_multidc/`).

- `PROJECT_GUIDE.md`: plain-language overview of the extension, results and repository layout.
- `cwm_multidc/README.md`: how to run the extension (model decisions in §5, experiments in §6, studies in §6a).
- `finalized_extension.md`: full technical design, theory and threats to validity.
- `report/CSD493_Final_Report.pdf`: the final report.
- `setup.sh`, `check.sh`, `reproduce.sh`: build and reproduce the original CWM paper's experiments;
  `reproduce_multidc.sh` and `run_chunks.sh` reproduce the extension's results.

## Licenses

- All provided code in this repository is released under MIT License (see `LICENSES/code`). This License holds for both repositories: `code_cawosched` and `code_cwm`.
- All provided data in this repository is released under MIT License (see `LICENSES/data`). If you use the workflow data, please respect the original licenses provided in the `LICENSE/` folder. Each workflow has a corresponding name there. If you use our profile data, please also attribute [Electricity Maps](https://www.electricitymaps.com). If you use our cluster specification, please also attribute [SPEC](https://www.spec.org/products/).