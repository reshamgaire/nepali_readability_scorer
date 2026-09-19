(function () {
  "use strict";

  const EXAMPLES = {
    simple:
      "मेरो नाम सानु हो। म कक्षा दुईमा पढ्छु। म बिहान सबेरै उठ्छु र हातमुख धुन्छु। मलाई किताब पढ्न र चित्र कोर्न मन पर्छ। मेरो घर नजिकै एउटा सानो बगैँचा छ। त्यहाँ राम्रा फूलहरू फुल्छन्।",
    complex:
      "सङ्घीय लोकतान्त्रिक गणतन्त्रात्मक शासन व्यवस्थाको सुदृढीकरणका निम्ति राज्यका निर्देशक सिद्धान्त तथा नीतिहरूको निष्ठापूर्वक कार्यान्वयन हुनु अपरिहार्य छ। शक्ति पृथकीकरण, नियन्त्रण र सन्तुलनको लोकतान्त्रिक मान्यताअनुरूप संवैधानिक अङ्गहरूको स्वायत्तता अक्षुण्ण राख्दै उत्तरदायी र पारदर्शी प्रशासनिक संयन्त्रको पुनर्स्थापना गर्नु वर्तमान परिप्रेक्ष्यमा प्रमुख चुनौती बनेको छ।",
  };

  const BAND_COLORS = {
    "Early Primary": "#2f5d62",
    "Middle School": "#3b4f72",
    Secondary: "#d98e2b",
    "Higher Secondary / Advanced": "#a83a32",
  };

  const $ = (id) => document.getElementById(id);

  const passage = $("passage");
  const analyzeBtn = $("analyze-btn");
  const placeholder = $("placeholder");
  const results = $("results");
  const errorBanner = $("error-banner");

  const wSliderIds = ["w1", "w2", "w3"];
  const cSliderIds = ["alpha", "beta", "gamma"];

  function refreshSliderLabels(ids) {
    const raw = ids.map((id) => parseFloat($(id).value) || 0);
    const sum = raw.reduce((a, b) => a + b, 0) || 1;
    ids.forEach((id, i) => {
      $(id + "-val").textContent = Math.round((raw[i] / sum) * 100) + "%";
    });
  }

  [...wSliderIds, ...cSliderIds].forEach((id) => {
    $(id).addEventListener("input", () => {
      refreshSliderLabels(wSliderIds.includes(id) ? wSliderIds : cSliderIds);
    });
  });
  refreshSliderLabels(wSliderIds);
  refreshSliderLabels(cSliderIds);

  document.querySelectorAll("[data-example]").forEach((btn) => {
    btn.addEventListener("click", () => {
      passage.value = EXAMPLES[btn.dataset.example];
    });
  });

  function currentParams() {
    return {
      text: passage.value,
      weights: { w1: parseFloat($("w1").value), w2: parseFloat($("w2").value), w3: parseFloat($("w3").value) },
      cdrs_weights: {
        alpha: parseFloat($("alpha").value),
        beta: parseFloat($("beta").value),
        gamma: parseFloat($("gamma").value),
      },
      threshold: parseFloat($("threshold").value),
      fallback_grade: parseInt($("fallback").value, 10),
    };
  }

  let histogramChart = null;
  let lastResult = null;
  let sortKey = "RDS_w";
  let sortAsc = false;

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.add("visible");
    results.classList.remove("visible");
    placeholder.style.display = "none";
  }

  function clearError() {
    errorBanner.classList.remove("visible");
    errorBanner.textContent = "";
  }

  async function analyze() {
    clearError();
    if (!passage.value.trim()) {
      showError("Please provide some Nepali text to analyze.");
      return;
    }
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing…";
    try {
      const resp = await fetch("/api/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentParams()),
      });
      const data = await resp.json();
      if (!resp.ok) {
        showError(data.error || "Something went wrong while scoring the passage.");
        return;
      }
      lastResult = data;
      renderResult(data);
      placeholder.style.display = "none";
      results.classList.add("visible");
    } catch (err) {
      showError("Could not reach the scoring server. Is app.py still running?");
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Analyze passage";
    }
  }

  analyzeBtn.addEventListener("click", analyze);

  function renderResult(data) {
    const bandColor = BAND_COLORS[data.band.label] || "#3b4f72";

    $("cdrs-number").textContent = data.cdrs.toFixed(1);
    $("cdrs-number").style.color = bandColor;
    $("band-label").textContent = data.band.label;
    $("band-label").style.color = bandColor;
    $("band-grades").textContent = data.band.grades + " · score range " + data.band.range;

    const clampPct = Math.min(Math.max(data.cdrs, 0), 100);
    $("scale-marker").style.left = clampPct + "%";

    $("metric-rds").textContent = data.rds_bar.toFixed(1);
    $("metric-rds-sub").textContent = data.total_words + " words scored";

    $("metric-hwd").textContent = data.hwd.toFixed(1) + "%";
    $("metric-hwd-sub").textContent = data.hard_word_count + " words ≥ τ (" + data.threshold + ")";

    $("metric-asl").textContent = data.asl.toFixed(1);
    $("metric-asl-sub").textContent = data.total_sentences + " sentences · F_ASL " + data.f_asl.toFixed(1);

    renderContributionBar(data);
    renderHistogram(data.words);
    renderTable(data.words);
    $("wordlist-chip").textContent = data.wordlist_size + " words loaded (used for grade lookup)";
  }

  function renderContributionBar(data) {
    const c = data.contributions;
    const w = data.weights_used;
    const total = c.rds_component + c.hwd_component + c.asl_component || 1;
    const bar = $("contribution-bar");
    bar.innerHTML = "";
    const segs = [
      { value: c.rds_component, color: "#3b4f72", label: "α·RDS̄ " + c.rds_component.toFixed(1) },
      { value: c.hwd_component, color: "#d98e2b", label: "β·HWD " + c.hwd_component.toFixed(1) },
      { value: c.asl_component, color: "#a83a32", label: "γ·F_ASL " + c.asl_component.toFixed(1) },
    ];
    segs.forEach((s) => {
      const div = document.createElement("div");
      const pct = Math.max((s.value / total) * 100, 0);
      div.style.width = pct + "%";
      div.style.background = s.color;
      if (pct > 12) div.textContent = s.label;
      div.title = s.label;
      bar.appendChild(div);
    });
  }

  function renderHistogram(words) {
    const bins = { "0–30": 0, "31–60": 0, "61–80": 0, "81–100": 0 };
    const colors = [BAND_COLORS["Early Primary"], BAND_COLORS["Middle School"], BAND_COLORS["Secondary"], BAND_COLORS["Higher Secondary / Advanced"]];
    words.forEach((w) => {
      const v = w.RDS_w;
      if (v <= 30) bins["0–30"]++;
      else if (v <= 60) bins["31–60"]++;
      else if (v <= 80) bins["61–80"]++;
      else bins["81–100"]++;
    });
    const ctx = $("histogram-canvas").getContext("2d");
    if (histogramChart) histogramChart.destroy();
    histogramChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: Object.keys(bins),
        datasets: [{ data: Object.values(bins), backgroundColor: colors, borderRadius: 2 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => "RDS_w " + items[0].label } } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "word count" } },
          x: { title: { display: true, text: "RDS_w band" } },
        },
      },
    });
  }

  function renderTable(words) {
    const body = $("word-table-body");
    const sorted = [...words].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? av - bv : bv - av;
    });
    body.innerHTML = "";
    sorted.forEach((w) => {
      const tr = document.createElement("tr");
      if (w.RDS_w >= (lastResult ? lastResult.threshold : 30)) tr.classList.add("hard");
      tr.innerHTML =
        '<td class="word-cell">' + escapeHtml(w.word) + "</td>" +
        "<td>" + w.grade + (w.in_wordlist ? "" : ' <span class="wordlist-flag">*</span>') + "</td>" +
        "<td>" + w.akshara_count + "</td>" +
        "<td>" + w.F_G.toFixed(1) + "</td>" +
        "<td>" + w.F_C.toFixed(1) + "</td>" +
        "<td>" + w.F_A.toFixed(1) + "</td>" +
        "<td>" + w.RDS_w.toFixed(1) + "</td>";
      body.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  document.querySelectorAll("#word-table th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortAsc = !sortAsc;
      } else {
        sortKey = key;
        sortAsc = false;
      }
      document.querySelectorAll("#word-table th").forEach((h) => h.classList.remove("sorted", "asc"));
      th.classList.add("sorted");
      if (sortAsc) th.classList.add("asc");
      if (lastResult) renderTable(lastResult.words);
    });
  });
})();
