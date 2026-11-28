// Chapter-wise numbers of every figure, table and equation (declared so the text can refer ahead).
module.exports = {
  fig: {
    cwm: "2.1",
    timeline: "3.1",
    architecture: "4.1",
    heatmap: "6.1", pareto: "6.2", multidate: "6.3", sensitivity: "6.4",
    variability: "6.5", attenuation: "6.6", holding: "6.7",
  },
  tab: {
    related: "2.1",
    baselines: "4.1",
    regions: "5.1", params: "5.2", studies: "5.3",
    multidate: "6.1", noise: "6.2", substitution: "6.3", stress: "6.4",
    rule: "6.5", hypotheses: "6.6", compare: "6.7",
  },
  eq: {
    arrival: "3.1", objective: "3.2", net: "3.3", loc: "3.4", budget: "3.5", maxsave: "3.6", rule: "3.7",
    gain: "5.1",
  },
  // short titles for the List of Figures / List of Tables
  title: {
    fig: {
      cwm: "How CWM builds a schedule inside one data centre",
      timeline: "The deadline tension",
      architecture: "System architecture of the multi-DC extension",
      heatmap: "What Ours chooses on a single day (17 April 2024)",
      pareto: "Network versus compute carbon of every candidate",
      multidate: "Year-round gain by month and submission hour",
      sensitivity: "Sensitivity to time unit, bandwidth, network energy and forecast error",
      variability: "Clean grids are flat: carbon intensity versus daily swing",
      attenuation: "Longer transfers gain less from waiting",
      holding: "Effect of charging for the time spent waiting",
    },
    tab: {
      related: "Decisions made by related approaches",
      baselines: "Comparison strategies",
      regions: "Carbon-intensity statistics of the five regions (2024)",
      params: "Model parameters",
      studies: "Experimental studies",
      multidate: "Year-round results (192 problems)",
      noise: "Noise control on the year-round winners",
      substitution: "Without a flat clean grid",
      stress: "Stress tests: hardware, queues and data origin",
      rule: "Cheap rule: captured gain and solver calls",
      hypotheses: "Expectations and outcomes",
      compare: "Comparison with results reported in earlier work",
    },
  },
};
