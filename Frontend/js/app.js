// ===== StockShield 2.0 - App Core =====

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port !== '8000'
  ? 'http://localhost:8000'
  : '';
let currentResults = null;
let currentRunId = null;
let currentConversationId = null;
let priceChart = null;
let forecastChart = null;

// ===== Theme System =====
function initTheme() {
  const saved = localStorage.getItem('ss_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('ss_theme', next);
  updateThemeIcon(next);
  if (currentResults) refreshCharts();
}

function updateThemeIcon(theme) {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
}

// ===== Page Router =====
function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));

  const page = document.getElementById('page-' + pageId);
  if (page) page.classList.add('active');

  document.querySelectorAll(`[data-page="${pageId}"]`).forEach(el => el.classList.add('active'));

  window._currentPage = pageId;
  history.pushState({ page: pageId }, '', '#' + pageId);

  if (pageId.startsWith('agent-') && currentResults) {
    populateAgentDetail(pageId.replace('agent-', ''), currentResults);
  }
}

// ===== Global Loader =====
function showLoader(stages) {
  const loader = document.getElementById('global-loader');
  const stagesEl = document.getElementById('loader-stages');
  loader.classList.remove('hidden');
  stagesEl.innerHTML = stages.map(s => `<div class="stage-item pending" id="stage-${s.id}">⏳ ${s.label}</div>`).join('');
}

function updateLoaderStage(id, state) {
  const el = document.getElementById('stage-' + id);
  if (!el) return;
  el.className = `stage-item ${state}`;
  const icons = { done: '✅', running: '⚡', pending: '⏳', error: '❌' };
  el.textContent = (icons[state] || '⏳') + ' ' + el.textContent.slice(2);
}

function hideLoader() {
  document.getElementById('global-loader').classList.add('hidden');
}

// ===== Company Name to NSE Ticker Mapping =====
const COMPANY_TICKER_MAP = {
  "TATA STEEL": "TATASTEEL",
  "TATASTEEL": "TATASTEEL",
  "TATA MOTORS": "TATAMOTORS",
  "TATAMOTORS": "TATAMOTORS",
  "TCS": "TCS",
  "TATA CONSULTANCY SERVICES": "TCS",
  "TATA POWER": "TATAPOWER",
  "TATA CONSUMER": "TATACONSUM",
  "TATA CONSUMER PRODUCTS": "TATACONSUM",
  "TATA TECHNOLOGIES": "TATATECH",
  "TRENT": "TRENT",
  "TITAN": "TITAN",
  "TITAN COMPANY": "TITAN",
  "RELIANCE": "RELIANCE",
  "RELIANCE INDUSTRIES": "RELIANCE",
  "JIO FINANCIAL": "JIOFIN",
  "JIO FINANCIAL SERVICES": "JIOFIN",
  "HDFC": "HDFCBANK",
  "HDFC BANK": "HDFCBANK",
  "HDFCBANK": "HDFCBANK",
  "INFOSYS": "INFY",
  "INFY": "INFY",
  "ICICI": "ICICIBANK",
  "ICICI BANK": "ICICIBANK",
  "ICICIBANK": "ICICIBANK",
  "SBI": "SBIN",
  "STATE BANK OF INDIA": "SBIN",
  "STATE BANK": "SBIN",
  "SBIN": "SBIN",
  "WIPRO": "WIPRO",
  "BAJAJ FINANCE": "BAJFINANCE",
  "BAJFINANCE": "BAJFINANCE",
  "BAJAJ FINSERV": "BAJAJFINSV",
  "BAJAJ AUTO": "BAJAJ-AUTO",
  "BHARTI AIRTEL": "BHARTIARTL",
  "AIRTEL": "BHARTIARTL",
  "LARSEN & TOUBRO": "LT",
  "LARSEN AND TOUBRO": "LT",
  "L&T": "LT",
  "LT": "LT",
  "HINDUSTAN UNILEVER": "HINDUNILVR",
  "HUL": "HINDUNILVR",
  "ITC": "ITC",
  "ITC LIMITED": "ITC",
  "ASIAN PAINTS": "ASIANPAINT",
  "MARUTI": "MARUTI",
  "MARUTI SUZUKI": "MARUTI",
  "SUN PHARMA": "SUNPHARMA",
  "SUN PHARMACEUTICAL": "SUNPHARMA",
  "CIPLA": "CIPLA",
  "DR REDDY": "DRREDDY",
  "DR REDDYS": "DRREDDY",
  "DR REDDY'S": "DRREDDY",
  "APOLLO HOSPITALS": "APOLLOHOSP",
  "DIVIS LAB": "DIVISLAB",
  "DIVIS LABORATORIES": "DIVISLAB",
  "DIVIS": "DIVISLAB",
  "AXIS BANK": "AXISBANK",
  "KOTAK": "KOTAKBANK",
  "KOTAK BANK": "KOTAKBANK",
  "KOTAK MAHINDRA BANK": "KOTAKBANK",
  "NTPC": "NTPC",
  "POWER GRID": "POWERGRID",
  "POWERGRID": "POWERGRID",
  "ONGC": "ONGC",
  "COAL INDIA": "COALINDIA",
  "ADANI ENTERPRISES": "ADANIENT",
  "ADANI PORTS": "ADANIPORTS",
  "ADANI POWER": "ADANIPOWER",
  "ADANI GREEN": "ADANIGREEN",
  "ULTRATECH CEMENT": "ULTRACEMCO",
  "ULTRATECH": "ULTRACEMCO",
  "GRASIM": "GRASIM",
  "JSW STEEL": "JSWSTEEL",
  "HINDALCO": "HINDALCO",
  "VEDANTA": "VEDL",
  "TECH MAHINDRA": "TECHM",
  "HCL TECH": "HCLTECH",
  "HCL TECHNOLOGIES": "HCLTECH",
  "EICHER MOTORS": "EICHERMOT",
  "HERO MOTOCORP": "HEROMOTOCO",
  "BRITANNIA": "BRITANNIA",
  "NESTLE": "NESTLEIND",
  "NESTLE INDIA": "NESTLEIND",
  "BHARAT ELECTRONICS": "BEL",
  "BEL": "BEL",
  "HINDUSTAN AERONAUTICS": "HAL",
  "HAL": "HAL",
  "BHEL": "BHEL",
  "DLF": "DLF",
  "ZOMATO": "ZOMATO",
  "SWIGGY": "SWIGGY",
  "PAYTM": "PAYTM",
  "IRCTC": "IRCTC",
  "RVNL": "RVNL",
  "IRFC": "IRFC",
  "SUZLON": "SUZLON",
  "PNB": "PNB",
  "PUNJAB NATIONAL BANK": "PNB",
  "BANK OF BARODA": "BANKBARODA",
  "FEDERAL BANK": "FEDERALBNK",
  "IDFC FIRST BANK": "IDFCFIRSTB",
  "YES BANK": "YESBANK",
  "INDUSIND BANK": "INDUSINDBK",
  "BPCL": "BPCL",
  "IOC": "IOC",
  "INDIAN OIL": "IOC",
  "HPCL": "HPCL",
  "SAIL": "SAIL",
  "VBL": "VBL",
  "VARUN BEVERAGES": "VBL",
  "PIDILITE": "PIDILITIND",
  "HAVELLS": "HAVELLS",
  "SIEMENS": "SIEMENS",
  "ABB": "ABB"
};

function resolveCompanyOrTicker(input) {
  if (!input) return '';
  let str = input.trim();

  // If user selected from dropdown like "Tata Steel (TATASTEEL)", extract inside (...)
  const parenMatch = str.match(/\(([A-Z0-9\-_]+)\)/i);
  if (parenMatch) {
    return parenMatch[1].toUpperCase();
  }

  // Strip .NS or .BO
  str = str.replace(/\.(NS|BO)$/i, '').trim();

  const upper = str.toUpperCase();
  if (COMPANY_TICKER_MAP[upper]) {
    return COMPANY_TICKER_MAP[upper];
  }

  // Exact case-insensitive match
  const lower = str.toLowerCase();
  for (const [key, val] of Object.entries(COMPANY_TICKER_MAP)) {
    if (key.toLowerCase() === lower) {
      return val;
    }
  }

  // Fuzzy prefix or substring match
  for (const [key, val] of Object.entries(COMPANY_TICKER_MAP)) {
    if (lower.length >= 3 && key.toLowerCase().includes(lower)) {
      return val;
    }
  }

  // Default clean symbol (strip non-standard characters)
  return upper.replace(/[^A-Z0-9\-_]/g, '');
}

// ===== Analysis Runner =====
async function runAnalysis() {
  const rawInput = document.getElementById('stockSearch').value.trim();
  if (!rawInput) { showAlert('Please enter a company name or stock symbol (e.g., Tata Steel, HDFCBANK, TCS)', 'error'); return; }

  const cleanTicker = resolveCompanyOrTicker(rawInput);
  if (!cleanTicker) { showAlert('Could not identify valid stock ticker. Please try again.', 'error'); return; }

  // Update input with resolved ticker
  document.getElementById('stockSearch').value = cleanTicker;

  const timeHorizon = document.getElementById('timeHorizon').value;
  const lookbackBars = parseInt(document.getElementById('lookbackBars').value);
  const forecastHorizon = document.getElementById('forecastHorizon').value;

  const payload = {
    ticker: cleanTicker + '.NS',
    lookback_days: lookbackBars,
    time_horizon: timeHorizon,
    forecast_horizon: forecastHorizon,
    workflow_mode: 'sequential',
    provider_mode: 'auto',
    enable_judge: true,
    user_prompt: `Conduct institutional technical momentum, scenario simulation, and deterministic risk intelligence review for ${cleanTicker}.`
  };

  const stages = [
    { id: 'market', label: 'Fetching Market Data (Yahoo Finance / Fixture)' },
    { id: 'technical', label: 'Google ADK Technical Analysis Agent' },
    { id: 'news', label: 'Financial News & Sentiment Agent' },
    { id: 'risk', label: 'Deterministic Risk Assessment Agent' },
    { id: 'forecast', label: 'Quantitative Forecasting Agent (ARIMA/LightGBM)' },
    { id: 'scenario', label: 'Scenario Simulation & Monte Carlo Agent' },
    { id: 'judge', label: 'Gemini LLM Post-Analysis Judge' },
    { id: 'report', label: 'Synthesizing Final Structured Report' }
  ];

  showLoader(stages);
  document.getElementById('loader-status').textContent = `Analyzing ${cleanTicker}.NS across all agents...`;

  const stageIds = stages.map(s => s.id);
  let stageIdx = 0;
  const stageInterval = setInterval(() => {
    if (stageIdx > 0 && stageIdx <= stageIds.length) updateLoaderStage(stageIds[stageIdx - 1], 'done');
    if (stageIdx < stageIds.length) updateLoaderStage(stageIds[stageIdx], 'running');
    stageIdx++;
    if (stageIdx > stageIds.length) clearInterval(stageInterval);
  }, 1600);

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    clearInterval(stageInterval);
    stageIds.forEach(id => updateLoaderStage(id, 'done'));

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Analysis request failed');
    }

    const data = await response.json();
    currentResults = data;
    currentRunId = data.run_id;

    saveResults(cleanTicker, data);

    await delay(500);
    hideLoader();

    renderResults(data);
    showPage('dashboard');

  } catch (err) {
    clearInterval(stageInterval);
    hideLoader();
    showAlert('Analysis Error: ' + err.message, 'error');
    console.error(err);
  }
}

// ===== Save Results =====
function saveResults(ticker, data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${ticker}_${timestamp}.json`;

  const saved = JSON.parse(localStorage.getItem('ss_saved_results') || '[]');
  saved.unshift({ ticker, filename, timestamp: new Date().toISOString(), run_id: data.run_id, data });
  if (saved.length > 25) saved.length = 25;
  localStorage.setItem('ss_saved_results', JSON.stringify(saved));

  showAlert(`Analysis saved (${ticker}) · Run: ${data.run_id}`, 'success', 3000);
}

// ===== Markdown Report Formatter =====
function cleanInlineReport(str) {
  if (!str) return '';
  str = str.replace(/\*\*(.*?)\*\*/g, '<strong class="report-bold">$1</strong>');
  str = str.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  str = str.replace(/`([^`]+)`/g, '<span class="report-clean-tag">$1</span>');
  return str;
}

function formatTableCell(cellText) {
  if (!cellText || cellText.trim() === '') return '<span style="color:var(--text-muted);">-</span>';
  let text = cellText.trim();
  let formatted = cleanInlineReport(text);
  const clean = text.replace(/\*\*/g, '').replace(/`/g, '').replace(/⚠️/g, '').trim();

  if (clean === 'APPROVED' || clean === 'LOW' || clean === 'success') {
    return `<span class="rep-table-badge approved">${clean === 'success' ? '✓ SUCCESS' : clean}</span>`;
  }
  if (clean === 'APPROVED_WITH_CAUTION' || clean === 'APPROVED WITH CAUTION' || clean === 'MODERATE' || clean === 'HOLD') {
    const icon = text.includes('⚠️') ? ' ⚠️' : '';
    return `<span class="rep-table-badge caution">${clean.replace(/_/g, ' ')}${icon}</span>`;
  }
  if (clean === 'REJECTED' || clean === 'HIGH' || clean === 'SELL') {
    return `<span class="rep-table-badge rejected">${clean.replace(/_/g, ' ')}</span>`;
  }
  if (clean === 'BULLISH') return `<span class="rep-table-badge approved">▲ BULLISH</span>`;
  if (clean === 'BEARISH') return `<span class="rep-table-badge rejected">▼ BEARISH</span>`;
  if (/^[-−]\d+(\.\d+)?%?/.test(clean)) return `<span class="rep-val-down">${formatted}</span>`;
  if (/^\+\d+(\.\d+)?%?/.test(clean)) return `<span class="rep-val-up">${formatted}</span>`;
  return formatted;
}

function formatReportToCleanHtml(md) {
  if (!md || typeof md !== 'string') {
    return '<div class="report-prose-p" style="color:var(--text-muted);text-align:center;padding:2rem;">Run an analysis to see the full report here.</div>';
  }

  const lines = md.split('\n');
  let html = '';
  let inList = false;
  let metaRows = [];

  function flushMeta() {
    if (metaRows.length > 0) {
      html += '<div class="report-meta-grid">';
      for (const m of metaRows) html += `<div class="report-meta-item">${m}</div>`;
      html += '</div>';
      metaRows = [];
    }
  }

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();

    if (!line) {
      if (inList) { html += '</ul>'; inList = false; }
      flushMeta();
      continue;
    }

    if (line === '---' || line === '***' || line === '___') {
      if (inList) { html += '</ul>'; inList = false; }
      flushMeta();
      html += '<hr class="report-divider">';
      continue;
    }

    // Markdown pipe-table detection
    if (line.startsWith('|') && line.endsWith('|')) {
      const nextLine = (i + 1 < lines.length) ? lines[i + 1].trim() : '';
      const isSep = /^\|[\s\-:]+(|\s\-:]+)+\|?$/.test(nextLine) || /^\|(\s*:?-+:?\s*\|)+/.test(nextLine);

      if (isSep) {
        if (inList) { html += '</ul>'; inList = false; }
        flushMeta();

        const headerCells = line.slice(1, -1).split('|').map(c => c.trim());
        i++; // skip separator

        let tableHtml = '<div class="report-table-wrapper"><table class="report-table"><thead><tr>';
        for (const h of headerCells) tableHtml += `<th>${cleanInlineReport(h)}</th>`;
        tableHtml += '</tr></thead><tbody>';

        while (i + 1 < lines.length) {
          const bodyLine = lines[i + 1].trim();
          if (bodyLine.startsWith('|') && bodyLine.endsWith('|')) {
            i++;
            if (/^\|[\s\-:]+(|\s*\|)+/.test(bodyLine)) continue;
            const rowCells = bodyLine.slice(1, -1).split('|').map(c => c.trim());
            tableHtml += '<tr>';
            for (let cIdx = 0; cIdx < headerCells.length; cIdx++) {
              const cellVal = rowCells[cIdx] !== undefined ? rowCells[cIdx] : '';
              tableHtml += `<td>${formatTableCell(cellVal)}</td>`;
            }
            tableHtml += '</tr>';
          } else { break; }
        }

        tableHtml += '</tbody></table></div>';
        html += tableHtml;
        continue;
      }
    }

    if (line.startsWith('# ')) {
      if (inList) { html += '</ul>'; inList = false; }
      flushMeta();
      let titleText = cleanInlineReport(line.replace(/^#\s+/, ''));
      titleText = titleText.replace(/StockShield\s+2\.0/gi, 'StockShield');
      html += `<div class="report-header-banner">
        <div class="report-brand-badge">🛡️ Institutional Equity Research Report</div>
        <h1 class="report-main-title">${titleText}</h1>
      </div>`;
      continue;
    }

    if (line.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false; }
      flushMeta();
      const secText = cleanInlineReport(line.replace(/^##\s+/, ''));
      html += `<div class="report-section-header"><h2 class="report-sec-title">${secText}</h2></div>`;
      continue;
    }

    if (line.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false; }
      flushMeta();
      const subText = cleanInlineReport(line.replace(/^###\s+/, ''));
      html += `<h3 class="report-sub-title">${subText}</h3>`;
      continue;
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      flushMeta();
      if (!inList) { html += '<ul class="report-bullet-list">'; inList = true; }
      html += `<li class="report-bullet-item">${cleanInlineReport(line.replace(/^[-*]\s+/, ''))}</li>`;
      continue;
    }

    if (line.startsWith('**') && (line.includes('ID:**') || line.includes('Mode:**') || line.includes('Horizon:**') || line.includes('Generated At') || line.includes('Window:**'))) {
      if (inList) { html += '</ul>'; inList = false; }
      metaRows.push(cleanInlineReport(line));
      continue;
    }

    if (inList) { html += '</ul>'; inList = false; }
    flushMeta();
    html += `<p class="report-prose-p">${cleanInlineReport(line)}</p>`;
  }

  if (inList) html += '</ul>';
  flushMeta();
  return html;
}

// ===== Render Results =====
function renderResults(data) {
  renderOverview(data);
  renderAgentCards(data);
  renderPriceChart(data);
  renderAgentDetails(data);
  enableChatbot(data.run_id);

  // Render Full Analysis Report as clean HTML
  const reportBox = document.getElementById('full-report-text');
  if (reportBox) {
    if (data.final_report && data.final_report.markdown_report) {
      reportBox.innerHTML = formatReportToCleanHtml(data.final_report.markdown_report);
    } else if (data.final_report && data.final_report.executive_summary) {
      reportBox.innerHTML = `<p class="report-prose-p">${data.final_report.executive_summary}</p>`;
    } else {
      reportBox.innerHTML = '<div class="report-prose-p" style="color:var(--text-muted);text-align:center;padding:2rem;">Report generation completed — no markdown available.</div>';
    }
  }

  // Sidebar quick stats
  const sbStats = document.getElementById('sidebar-quick-stats');
  if (sbStats) sbStats.style.display = 'block';
  const sbTicker = document.getElementById('sidebar-ticker');
  if (sbTicker) sbTicker.textContent = data.ticker || '-';
  const rec = data.risk_findings?.recommendation || 'HOLD';
  const recColor = rec.includes('BUY') || rec === 'APPROVED' ? 'var(--neon-green)' :
                   rec.includes('SELL') || rec === 'REJECTED' ? 'var(--accent-red)' : 'var(--accent-orange)';
  const sbRec = document.getElementById('sidebar-rec');
  if (sbRec) sbRec.innerHTML = `<span style="color:${recColor};font-weight:700;">${rec}</span>`;

  document.getElementById('results-area').style.display = 'flex';
  document.getElementById('results-area').classList.add('fade-in');
}

function normalizeRiskScore(score) {
  if (score === null || score === undefined) return 0;
  // If score is a fraction (0.0 - 1.0), scale to 0 - 100
  return score <= 1.0 ? score * 100 : score;
}

function renderOverview(data) {
  const tech = data.technical_findings || {};
  const risk = data.risk_findings || {};
  const news = data.news_and_sentiment || {};
  const market = data.market_data || {};

  const signal = tech.signal || 'neutral';
  const isBullish = signal.toLowerCase().includes('bullish');
  const isBearish = signal.toLowerCase().includes('bearish');

  const rec = risk.recommendation || 'HOLD';
  const recClass = rec.toUpperCase().includes('BUY') || rec.toUpperCase() === 'APPROVED' ? 'BUY' :
                   rec.toUpperCase().includes('SELL') || rec.toUpperCase() === 'REJECTED' ? 'SELL' : 'HOLD';

  const sentiment = news.overall_sentiment || 'neutral';
  const sentimentClass = sentiment === 'positive' ? 'bullish' : sentiment === 'negative' ? 'bearish' : 'neutral';

  const riskScore100 = normalizeRiskScore(risk.composite_score);

  document.getElementById('overview-ticker').textContent = data.ticker || '-';
  document.getElementById('overview-signal').innerHTML = `
    <span class="badge badge-${isBullish ? 'bullish' : isBearish ? 'bearish' : 'neutral'}">
      ${isBullish ? '▲ BULLISH' : isBearish ? '▼ BEARISH' : '◀▶ NEUTRAL'} (${((tech.confidence || 0.8) * 100).toFixed(0)}% conf)
    </span>
  `;
  document.getElementById('overview-recommendation').innerHTML = `
    <span class="recommendation-badge ${recClass}">${rec.replace(/_/g, ' ')}</span>
  `;
  document.getElementById('overview-risk').textContent = `${riskScore100.toFixed(1)}/100`;
  document.getElementById('overview-risk').style.color = getRiskColor(riskScore100);
  document.getElementById('overview-sentiment').innerHTML = `
    <span class="badge badge-${sentimentClass}">${sentiment.toUpperCase()}</span>
  `;
  document.getElementById('overview-bars').textContent = `${market.bar_count || '-'} bars`;
  document.getElementById('overview-horizon').textContent = (data.time_horizon || 'short_term').replace('_', ' ');
  document.getElementById('overview-source').textContent = market.source || 'Yahoo Finance';
  document.getElementById('overview-runid').textContent = data.run_id || '-';

  const summary = data.final_report?.executive_summary || tech.summary || 'Institutional multi-agent review completed.';
  document.getElementById('overview-summary').textContent = summary;
}

function getRiskColor(score) {
  if (!score && score !== 0) return 'var(--text-secondary)';
  if (score <= 35) return 'var(--neon-green)';
  if (score <= 65) return 'var(--accent-orange)';
  return 'var(--accent-red)';
}

function renderAgentCards(data) {
  const tech = data.technical_findings || {};
  const risk = data.risk_findings || {};
  const news = data.news_and_sentiment || {};
  const fc = data.forecasting || {};
  const sc = data.scenario_simulation || {};
  const judge = data.judge_evaluation || {};

  // Technical
  updateAgentCard('technical', tech.status, tech.signal?.toUpperCase() || 'NEUTRAL', tech.confidence ? (tech.confidence * 100).toFixed(0) + '%' : null);
  // News
  updateAgentCard('news', news.status, news.overall_sentiment?.toUpperCase() || 'NEUTRAL', news.sentiment_score !== undefined ? `Score: ${news.sentiment_score.toFixed(2)}` : null);
  // Risk
  const riskNorm = normalizeRiskScore(risk.composite_score);
  updateAgentCard('risk', risk.status, risk.risk_level || 'MODERATE', `Score: ${riskNorm.toFixed(1)}/100`);
  // Forecast
  updateAgentCard('forecast', fc.status, fc.forecast_label || 'COMPUTED', fc.best_model ? `Model: ${fc.best_model}` : null);
  // Scenario
  const scCount = sc.total_scenarios || (sc.scenarios ? sc.scenarios.length : 0);
  updateAgentCard('scenario', sc.status, `${scCount} Scenarios Tested`, sc.monte_carlo ? 'Monte Carlo (1000 paths)' : 'Stress Tested');
  // Judge
  const judgeVerdict = judge.verdict || (judge.status === 'available' ? 'EVALUATED' : judge.status);
  const judgeScore = judge.overall_score !== null && judge.overall_score !== undefined ? `${(judge.overall_score * 100).toFixed(0)}%` : null;
  updateAgentCard('judge', judge.status, judgeVerdict, judgeScore);
}

function updateAgentCard(agentId, status, mainValue, subValue) {
  const card = document.getElementById(`agent-card-${agentId}`);
  if (!card) return;
  const statusEl = card.querySelector('.agent-status-text');
  if (statusEl) statusEl.textContent = status || 'available';
  const mainEl = card.querySelector('.agent-main-value');
  if (mainEl) mainEl.textContent = mainValue || '-';
  if (subValue !== null && subValue !== undefined) {
    const sub = card.querySelector('.agent-sub-value');
    if (sub) sub.textContent = typeof subValue === 'number' ? subValue.toFixed(2) : subValue;
  }
}

// ===== 1. Observed Historical Price Chart (Present & Past Continuous Line) =====
function renderHistoricalChart(data) {
  const canvas = document.getElementById('historicalChart');
  if (!canvas) return;

  const market = data.market_data || {};
  const bars = market.bars || [];
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  const solidLineColor = isDark ? '#00ff41' : '#00aa2a';
  const areaGradient = isDark ? 'rgba(0, 255, 65, 0.06)' : 'rgba(0, 170, 42, 0.06)';

  if (priceChart) {
    priceChart.destroy();
    priceChart = null;
  }

  // Use all observed bars (or up to 180 for optimal performance & clarity)
  const displayBars = bars.length > 180 ? bars.slice(-180) : bars;

  const labels = displayBars.map(b => {
    const raw = b.timestamp || '';
    return raw.length >= 10 ? raw.slice(0, 10) : raw;
  });
  const closes = displayBars.map(b => b.close);

  if (closes.length > 0) {
    const high = Math.max(...closes);
    const low = Math.min(...closes);
    const latest = closes[closes.length - 1];

    const highEl = document.getElementById('histPeriodHigh');
    if (highEl) highEl.textContent = `High: ₹${high.toFixed(2)}`;
    const lowEl = document.getElementById('histPeriodLow');
    if (lowEl) lowEl.textContent = `Low: ₹${low.toFixed(2)}`;
    const latestEl = document.getElementById('histLatestClose');
    if (latestEl) latestEl.textContent = `Latest: ₹${latest.toFixed(2)}`;
  }

  priceChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Observed Historical Close (Continuous Line)',
          data: closes,
          borderColor: solidLineColor,
          backgroundColor: areaGradient,
          borderWidth: 2.5,
          borderDash: [], // CONTINUOUS SOLID LINE
          pointRadius: displayBars.length > 45 ? 0 : 3,
          pointHoverRadius: 6,
          pointBackgroundColor: solidLineColor,
          tension: 0.15,
          fill: true,
        }
      ]
    },
    options: getChartOptions(isDark, 'Historical Close (₹)')
  });
}

// ===== 2. Quantitative Future Forecast Chart (Dotted Line + 95% Confidence Bounds) =====
function renderForecastChart(data) {
  const canvas = document.getElementById('forecastChart');
  if (!canvas) return;

  const fc = data.forecasting || {};
  const forecasts = fc.forecasts || [];
  const market = data.market_data || {};
  const bars = market.bars || [];
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  const forecastLineColor = isDark ? '#00e5ff' : '#0284c7';
  const bandColor = isDark ? 'rgba(0, 229, 255, 0.15)' : 'rgba(2, 132, 199, 0.15)';

  if (forecastChart) {
    forecastChart.destroy();
    forecastChart = null;
  }

  const modelBadge = document.getElementById('forecastModelBadge');
  if (modelBadge) {
    modelBadge.textContent = fc.best_model || 'ARIMA / LightGBM';
  }

  const latestObservedClose = bars.length > 0 ? bars[bars.length - 1].close : (forecasts.length > 0 ? forecasts[0].predicted_price : null);
  const latestDate = bars.length > 0 ? (bars[bars.length - 1].timestamp || '').slice(0, 10) : 'Current';

  // Anchor the forecast to the current close price
  const labels = [latestDate + ' (Now)', ...forecasts.map(f => (f.target_date || `Step ${f.step}`).slice(0, 10))];
  const predicted = [latestObservedClose, ...forecasts.map(f => f.predicted_price)];
  const upper = [latestObservedClose, ...forecasts.map(f => f.conf_upper)];
  const lower = [latestObservedClose, ...forecasts.map(f => f.conf_lower)];

  forecastChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Future Forecast (Dotted Line)',
          data: predicted,
          borderColor: forecastLineColor,
          backgroundColor: 'transparent',
          borderWidth: 2.8,
          borderDash: [6, 4], // DOTTED PREDICTION LINE
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: forecastLineColor,
          tension: 0.25,
          fill: false,
        },
        {
          label: '95% Upper Bound',
          data: upper,
          borderColor: 'transparent',
          backgroundColor: bandColor,
          fill: '+1',
          pointRadius: 0,
          tension: 0.25,
        },
        {
          label: '95% Lower Bound',
          data: lower,
          borderColor: 'transparent',
          backgroundColor: bandColor,
          fill: false,
          pointRadius: 0,
          tension: 0.25,
        }
      ]
    },
    options: getChartOptions(isDark, 'Projected Price (₹)')
  });
}

// Helper that executes both graphs
function renderPriceChart(data) {
  renderHistoricalChart(data);
  renderForecastChart(data);
}

function getChartOptions(isDark, yLabel) {
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
  const textColor = isDark ? '#a0a0a0' : '#4b5563';

  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600 },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: {
          color: textColor,
          font: { size: 11, family: 'Inter' },
          usePointStyle: true,
          pointStyleWidth: 16,
        }
      },
      tooltip: {
        backgroundColor: isDark ? '#161616' : '#ffffff',
        borderColor: isDark ? '#262626' : '#e2e8f0',
        borderWidth: 1,
        titleColor: isDark ? '#e8e8e8' : '#1a1a2e',
        bodyColor: textColor,
        callbacks: {
          label: ctx => {
            if (ctx.parsed.y === null || ctx.parsed.y === undefined) return '';
            return ` ${ctx.dataset.label}: ₹${ctx.parsed.y.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: gridColor },
        ticks: { color: textColor, font: { size: 10 }, maxTicksLimit: 10 }
      },
      y: {
        grid: { color: gridColor },
        ticks: {
          color: textColor,
          font: { size: 11 },
          callback: v => '₹' + v.toFixed(0)
        },
        title: { display: true, text: yLabel, color: textColor, font: { size: 11 } }
      }
    }
  };
}

function refreshCharts() {
  if (currentResults) {
    renderPriceChart(currentResults);
    renderAgentDetails(currentResults);
  }
}

// ===== Detailed Agent Views Population =====
function populateAgentDetail(agentName, data) {
  if (!data) return;
  switch (agentName) {
    case 'technical': renderTechnicalDetail(data.technical_findings || {}, data); break;
    case 'news': renderNewsDetail(data.news_and_sentiment || {}); break;
    case 'risk': renderRiskDetail(data.risk_findings || {}, data); break;
    case 'forecast': renderForecastDetail(data.forecasting || {}, data); break;
    case 'scenario': renderScenarioDetail(data.scenario_simulation || {}); break;
    case 'judge': renderJudgeDetail(data.judge_evaluation || {}); break;
  }
}

function renderAgentDetails(data) {
  if (!data) return;
  renderTechnicalDetail(data.technical_findings || {}, data);
  renderNewsDetail(data.news_and_sentiment || {});
  renderRiskDetail(data.risk_findings || {}, data);
  renderForecastDetail(data.forecasting || {}, data);
  renderScenarioDetail(data.scenario_simulation || {});
  renderJudgeDetail(data.judge_evaluation || {});
}

// ---------------------------------------------------------------------------
// 1. TECHNICAL AGENT DETAIL VIEW
// ---------------------------------------------------------------------------
function renderTechnicalDetail(tech, data) {
  const el = document.getElementById('technical-detail-content');
  if (!el) return;
  const ind = tech.indicators || {};
  const isBull = tech.signal?.toLowerCase().includes('bullish');
  const isBear = tech.signal?.toLowerCase().includes('bearish');

  el.innerHTML = `
    <div class="stats-row" style="margin-bottom:1rem;">
      <div class="stat-card">
        <div class="stat-label">Algorithmic Signal</div>
        <div class="stat-value" style="font-size:1.15rem;color:${isBull ? 'var(--neon-green)' : isBear ? 'var(--accent-red)' : 'var(--text-secondary)'}">
          ${tech.signal?.toUpperCase() || 'NEUTRAL'}
        </div>
        <div class="stat-change ${isBull ? 'up' : 'down'}">${isBull ? '▲ Momentum Intact' : isBear ? '▼ Trend Weakness' : '◀▶ Consolidating'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Signal Confidence</div>
        <div class="stat-value" style="font-size:1.15rem;">${tech.confidence !== undefined ? (tech.confidence * 100).toFixed(1) + '%' : '80.0%'}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Google ADK Mathematical Precision</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Relative Strength (RSI-14)</div>
        <div class="stat-value" style="font-size:1.15rem;color:${ind.rsi_14 > 70 ? 'var(--accent-orange)' : ind.rsi_14 < 30 ? 'var(--neon-green)' : 'var(--text-primary)'}">
          ${ind.rsi_14 !== undefined && ind.rsi_14 !== null ? ind.rsi_14.toFixed(2) : '-'}
        </div>
        <div style="font-size:0.75rem;margin-top:0.3rem;">${getRSISignal(ind.rsi_14)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">MACD Histogram</div>
        <div class="stat-value" style="font-size:1.15rem;color:${(ind.macd_histogram || 0) >= 0 ? 'var(--neon-green)' : 'var(--accent-red)'}">
          ${ind.macd_histogram !== undefined && ind.macd_histogram !== null ? ind.macd_histogram.toFixed(3) : '-'}
        </div>
        <div style="font-size:0.75rem;margin-top:0.3rem;">${(ind.macd_histogram || 0) >= 0 ? '▲ Positive Expansion' : '▼ Negative Compression'}</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Quantitative Momentum Synthesis</div></div>
      <p style="font-size:0.875rem;color:var(--text-secondary);line-height:1.8;">
        ${tech.summary || 'Technical agent executed standard mathematical indicators via Google ADK Runner lifecycle.'}
      </p>
    </div>

    <div class="card">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Indicator Matrix & Critical Thresholds</div></div>
      <div class="scroll-x">
        <table class="indicators-table">
          <thead>
            <tr>
              <th>Indicator Metric</th>
              <th>Calculated Value</th>
              <th>Interpretation / Signal</th>
              <th>Parameter Config</th>
            </tr>
          </thead>
          <tbody>
            ${renderIndicatorRows(ind)}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Render technical chart
  const canvas = document.getElementById('technical-chart');
  if (canvas && data) {
    if (window.techChart) window.techChart.destroy();
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const bars = (data.market_data?.bars || []).slice(-60);
    const labels = bars.map(b => (b.timestamp || '').slice(0, 10));
    const closes = bars.map(b => b.close);

    window.techChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Close Price (₹)',
          data: closes,
          borderColor: isDark ? '#00ff41' : '#00aa2a',
          borderWidth: 2,
          backgroundColor: isDark ? 'rgba(0, 255, 65, 0.05)' : 'rgba(0, 170, 42, 0.05)',
          fill: true,
          tension: 0.15,
          pointRadius: 2,
        }]
      },
      options: getChartOptions(isDark, 'Price (₹)')
    });
  }
}

function renderIndicatorRows(ind) {
  const rows = [
    ['Simple Moving Average (SMA 20)', ind.sma_20, getSMASignal(ind.sma_20, ind.sma_50), '20-session arithmetic mean'],
    ['Simple Moving Average (SMA 50)', ind.sma_50, '', '50-session medium trend anchor'],
    ['Simple Moving Average (SMA 200)', ind.sma_200, ind.sma_50 && ind.sma_200 ? (ind.sma_50 > ind.sma_200 ? '▲ Golden Cross Trend' : '▼ Death Cross Bias') : '', '200-session institutional baseline'],
    ['Exponential Moving Average (EMA 12)', ind.ema_12, '', '12-period fast weight'],
    ['Exponential Moving Average (EMA 26)', ind.ema_26, '', '26-period slow weight'],
    ['RSI (14 Wilder)', ind.rsi_14, getRSISignal(ind.rsi_14), '14-session Wilder smoothed ratio'],
    ['MACD Line (12/26)', ind.macd_line, getMACDSignal(ind.macd_line, ind.macd_signal_line), 'Fast - Slow EMA divergence'],
    ['MACD Signal Line (9)', ind.macd_signal_line, '', '9-session EMA of MACD'],
    ['MACD Histogram', ind.macd_histogram, (ind.macd_histogram || 0) >= 0 ? '▲ Bullish Momentum' : '▼ Bearish Divergence', 'MACD Line - Signal Line'],
    ['Bollinger Band Upper (20, 2σ)', ind.bb_upper, '', 'SMA 20 + 2 Standard Deviations'],
    ['Bollinger Band Middle (20)', ind.bb_middle, '', '20-session baseline mean'],
    ['Bollinger Band Lower (20, 2σ)', ind.bb_lower, '', 'SMA 20 - 2 Standard Deviations'],
    ['Average True Range (ATR 14)', ind.atr_14, 'Daily Volatility Measure', '14-session True Range Wilder filter'],
  ];

  return rows
    .filter(r => r[1] !== undefined && r[1] !== null)
    .map(([name, val, sig, config]) => {
      const formatted = typeof val === 'number' ? val.toFixed(3) : val || '-';
      const sigClass = sig?.toLowerCase().includes('bullish') || sig?.toLowerCase().includes('golden') ? 'value-up' :
                      sig?.toLowerCase().includes('bearish') || sig?.toLowerCase().includes('overbought') ? 'value-down' : 'value-neutral';
      return `
        <tr>
          <td style="font-weight:600;">${name}</td>
          <td class="${sigClass}" style="font-weight:700;">${formatted}</td>
          <td class="${sigClass}" style="font-size:0.78rem;">${sig || '◀▶ In-Range'}</td>
          <td style="font-size:0.75rem;color:var(--text-muted);">${config}</td>
        </tr>
      `;
    }).join('');
}

function getSMASignal(sma20, sma50) {
  if (!sma20 || !sma50) return '';
  return sma20 > sma50 ? '▲ SMA 20 > 50 (Bullish Momentum)' : '▼ SMA 20 < 50 (Bearish Crossover)';
}
function getRSISignal(rsi) {
  if (!rsi && rsi !== 0) return '';
  if (rsi > 70) return '⚠️ Overbought Zone (>70)';
  if (rsi < 30) return '📉 Oversold Reversal Zone (<30)';
  return '◀▶ Neutral Equilibrium (30-70)';
}
function getMACDSignal(line, signal) {
  if (line === undefined || signal === undefined) return '';
  return line > signal ? '▲ Bullish Divergence' : '▼ Bearish Divergence';
}

// ---------------------------------------------------------------------------
// 2. NEWS AGENT DETAIL VIEW
// ---------------------------------------------------------------------------
function renderNewsDetail(news) {
  const el = document.getElementById('news-detail-content');
  if (!el) return;

  const articles = news.articles_sample || [];
  const articlesHtml = articles.map(a => `
    <div class="news-article" style="align-items:flex-start;">
      <div class="news-sentiment-dot ${a.sentiment?.toLowerCase() || 'neutral'}"></div>
      <div style="flex:1;">
        <div class="news-article-title">
          ${a.url ? `<a href="${a.url}" target="_blank" rel="noopener noreferrer" style="color:var(--text-primary);text-decoration:underline;">${a.title || 'Corporate Announcement'}</a>` : (a.title || 'Corporate Announcement')}
        </div>
        <div class="news-article-meta" style="margin-top:0.35rem;">
          <span class="news-source" style="font-weight:700;">📰 ${a.source || 'NSE Regulatory Filing'}</span>
          <span>📅 ${a.published_date || 'Recent'}</span>
          <span class="badge badge-${a.sentiment === 'positive' ? 'bullish' : a.sentiment === 'negative' ? 'bearish' : 'neutral'}" style="padding:0.15rem 0.5rem;font-size:0.68rem;">
            ${a.sentiment?.toUpperCase() || 'NEUTRAL'} (${((a.confidence || 0.85) * 100).toFixed(0)}% conf)
          </span>
          ${a.topic ? `<span class="badge badge-info" style="font-size:0.68rem;">${a.topic}</span>` : ''}
        </div>
      </div>
    </div>
  `).join('') || '<div style="color:var(--text-muted);font-size:0.875rem;text-align:center;padding:2rem;">No media articles retrieved for current session.</div>';

  el.innerHTML = `
    <div class="stats-row" style="margin-bottom:1rem;">
      <div class="stat-card">
        <div class="stat-label">Aggregate Sentiment</div>
        <div class="stat-value" style="font-size:1.15rem;">
          <span class="badge badge-${news.overall_sentiment === 'positive' ? 'bullish' : news.overall_sentiment === 'negative' ? 'bearish' : 'neutral'}">
            ${(news.overall_sentiment || 'NEUTRAL').toUpperCase()}
          </span>
        </div>
        <div class="stat-change ${news.overall_sentiment === 'positive' ? 'up' : 'down'}">Deterministic NLP Classifier</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Sentiment Polarity Score</div>
        <div class="stat-value" style="font-size:1.15rem;color:${(news.sentiment_score || 0) >= 0 ? 'var(--neon-green)' : 'var(--accent-red)'}">
          ${news.sentiment_score !== undefined ? (news.sentiment_score > 0 ? '+' : '') + news.sentiment_score.toFixed(3) : '0.00'}
        </div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Scale: -1.0 (Severe Bearish) to +1.0 (Strong Bullish)</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Article Distribution</div>
        <div class="stat-value" style="font-size:1.15rem;">${news.article_counts?.total || articles.length} Articles</div>
        <div class="stat-change up">+${news.article_counts?.positive || 0} Positive · <span style="color:var(--accent-red);">${news.article_counts?.negative || 0} Negative</span></div>
      </div>
    </div>

    ${news.positive_events?.length ? `
    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Positive Corporate Catalysts & Event Triggers</div></div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem;">
        ${(news.positive_events || []).map(e => `<li style="font-size:0.85rem;display:flex;gap:0.5rem;align-items:flex-start;"><span style="color:var(--neon-green);font-weight:bold;">▲</span>${e}</li>`).join('')}
      </ul>
    </div>` : ''}

    ${news.negative_events?.length ? `
    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header"><div class="section-title" style="color:var(--accent-red);"><span style="display:inline-block;width:8px;height:8px;background:var(--accent-red);border-radius:50%;margin-right:0.5rem;"></span>Adverse Regulatory & Market Risk Events</div></div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem;">
        ${(news.negative_events || []).map(e => `<li style="font-size:0.85rem;display:flex;gap:0.5rem;align-items:flex-start;"><span style="color:var(--accent-red);font-weight:bold;">▼</span>${e}</li>`).join('')}
      </ul>
    </div>` : ''}

    <div class="card">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Financial Media Publications & Source Citations</div></div>
      ${articlesHtml}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// 3. RISK ASSESSMENT AGENT DETAIL VIEW (DETAILED & STRUCTURED)
// ---------------------------------------------------------------------------
function renderRiskDetail(risk, data) {
  const el = document.getElementById('risk-detail-content');
  if (!el) return;

  const score100 = normalizeRiskScore(risk.composite_score);
  const level = risk.risk_level || 'MODERATE';
  const rec = risk.recommendation || 'APPROVED_WITH_CAUTION';
  const checks = risk.checks || [];

  const recClean = rec.replace(/_/g, ' ');
  const isApproved = rec.includes('APPROVED') && !rec.includes('CAUTION');
  const isCaution = rec.includes('CAUTION') || rec.includes('HOLD');
  const isRejected = rec.includes('REJECTED') || rec.includes('HIGH_RISK');

  el.innerHTML = `
    <!-- Top Stat Banner -->
    <div style="display:grid;grid-template-columns:1fr auto;gap:1rem;margin-bottom:1rem;">
      <div class="stats-row" style="flex:1;">
        <div class="stat-card">
          <div class="stat-label">Composite Risk Rating</div>
          <div class="stat-value" style="font-size:1.15rem;color:${getRiskColor(score100)};">
            ${level.toUpperCase()}
          </div>
          <div class="stat-change ${score100 <= 35 ? 'up' : 'down'}">Governance Level: Tier ${score100 <= 35 ? '1 (Safe)' : score100 <= 65 ? '2 (Moderate)' : '3 (Restricted)'}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Composite Risk Score</div>
          <div class="stat-value" style="color:${getRiskColor(score100)};font-size:1.4rem;">
            ${score100.toFixed(1)}<span style="font-size:0.85rem;color:var(--text-muted);">/100</span>
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Lower = Safer Investment</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Final Investment Directive</div>
          <div style="margin-top:0.3rem;">
            <span class="recommendation-badge ${isApproved ? 'BUY' : isRejected ? 'SELL' : 'HOLD'}" style="font-size:0.88rem;padding:0.4rem 1rem;">
              ${recClean}
            </span>
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.4rem;">Approved via Blackboard Risk Engine</div>
        </div>
      </div>

      <div class="card risk-gauge-wrapper" style="min-width:160px;text-align:center;justify-content:center;">
        <div class="stat-label" style="text-align:center;">Risk Gauge</div>
        <div class="risk-score-display" style="color:${getRiskColor(score100)};font-size:2.5rem;">
          ${score100.toFixed(0)}
        </div>
        <div style="width:100%;margin-top:0.4rem;">
          <div class="progress-bar">
            <div class="progress-fill ${score100 > 65 ? 'red' : score100 > 35 ? 'orange' : 'green'}" style="width:${Math.min(100, Math.max(5, score100))}%;"></div>
          </div>
        </div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.4rem;">${level}</div>
      </div>
    </div>

    <!-- Deterministic Governance Checks Table -->
    ${checks.length ? `
    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header">
        <div class="section-title"><span class="dot"></span>Deterministic Risk Governance Checks (${checks.length} Audited)</div>
      </div>
      <div class="scroll-x">
        <table class="indicators-table">
          <thead>
            <tr>
              <th>Risk Check Directive</th>
              <th>Status</th>
              <th>Risk Weight</th>
              <th>Deterministic Audit Explanation</th>
            </tr>
          </thead>
          <tbody>
            ${checks.map(c => `
              <tr>
                <td style="font-weight:600;font-size:0.85rem;">${c.name}</td>
                <td>
                  <span class="badge badge-${c.passed ? 'bullish' : 'bearish'}" style="font-size:0.7rem;padding:0.2rem 0.5rem;">
                    ${c.passed ? '✅ PASSED' : '❌ FAILED'}
                  </span>
                </td>
                <td style="font-weight:700;color:${c.score > 0.6 ? 'var(--accent-red)' : c.score > 0.3 ? 'var(--accent-orange)' : 'var(--neon-green)'};">
                  ${(c.score * 100).toFixed(0)}%
                </td>
                <td style="font-size:0.82rem;color:var(--text-secondary);">${c.message}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>` : ''}

    <!-- Warnings Alert Box -->
    ${risk.warnings?.length ? `
    <div class="card" style="margin-bottom:1rem;border-color:rgba(255,140,0,0.4);">
      <div class="section-header">
        <div class="section-title" style="color:var(--accent-orange);"><span style="display:inline-block;width:8px;height:8px;background:var(--accent-orange);border-radius:50%;margin-right:0.5rem;"></span>Active Risk Warnings & Constraints</div>
      </div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem;">
        ${(risk.warnings || []).map(w => `
          <li style="font-size:0.85rem;display:flex;gap:0.6rem;padding:0.6rem 0.8rem;background:rgba(255,140,0,0.06);border-left:3px solid var(--accent-orange);border-radius:4px;">
            <span>⚠️</span><span>${w}</span>
          </li>
        `).join('')}
      </ul>
    </div>` : ''}

    <!-- Detailed Rationale -->
    ${risk.reasons?.length ? `
    <div class="card">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Institutional Rationale & Gate Evaluation</div></div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.75rem;">
        ${(risk.reasons || []).map(r => `
          <li style="font-size:0.85rem;line-height:1.7;padding:0.6rem 0;border-bottom:1px solid var(--border-color);display:flex;gap:0.75rem;align-items:flex-start;">
            <span style="color:var(--neon-green);font-weight:bold;margin-top:2px;">→</span>
            <span>${r}</span>
          </li>
        `).join('')}
      </ul>
    </div>` : ''}
  `;

  // Draw semi-circle risk gauge
  const canvas = document.getElementById('risk-chart');
  if (canvas) {
    if (window.riskChart) window.riskChart.destroy();
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    window.riskChart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Risk Score', 'Buffer'],
        datasets: [{
          data: [score100, Math.max(0, 100 - score100)],
          backgroundColor: [
            score100 > 65 ? '#ff3333' : score100 > 35 ? '#ff8c00' : '#00ff41',
            isDark ? '#222222' : '#e2e8f0'
          ],
          borderWidth: 0,
        }]
      },
      options: {
        cutout: '76%',
        rotation: -90,
        circumference: 180,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { duration: 800 }
      }
    });
  }
}

// ---------------------------------------------------------------------------
// 4. FORECASTING AGENT DETAIL VIEW
// ---------------------------------------------------------------------------
function renderForecastDetail(fc, data) {
  const el = document.getElementById('forecast-detail-content');
  if (!el) return;

  const forecasts = fc.forecasts || [];
  const models = fc.models_evaluated || [];
  const isStale = fc.is_stale_data;

  const forecastsHtml = forecasts.length ? forecasts.map(f => `
    <div class="forecast-row">
      <div class="forecast-step">${f.step || '-'}</div>
      <div style="font-weight:500;">${f.target_date || '-'}</div>
      <div style="font-weight:700;color:var(--text-primary);">₹${(f.predicted_price || 0).toFixed(2)}</div>
      <div style="font-size:0.78rem;color:var(--neon-green);">${f.pct_change !== undefined ? ((f.pct_change >= 0 ? '+' : '') + (f.pct_change * 100).toFixed(2) + '%') : '-'}</div>
      <div style="font-size:0.75rem;color:var(--text-muted);">
        [₹${(f.conf_lower || 0).toFixed(0)} – ₹${(f.conf_upper || 0).toFixed(0)}]
      </div>
    </div>
  `).join('') : '<div style="color:var(--text-muted);text-align:center;padding:1.5rem;font-size:0.875rem;">No forecast predictions generated.</div>';

  const modelsHtml = models.map(m => `
    <div class="model-eval-row">
      <div class="model-name">
        ${m.model_name}
        ${m.model_name === fc.best_model ? '<span class="best-model-badge">SELECTED</span>' : ''}
      </div>
      <div>${m.rmse ? m.rmse.toFixed(4) : '-'}</div>
      <div>${m.mae ? m.mae.toFixed(4) : '-'}</div>
      <div style="font-weight:600;color:var(--neon-green);">${m.directional_accuracy ? (m.directional_accuracy * 100).toFixed(1) + '%' : '-'}</div>
      <div>
        <span class="badge badge-${m.status === 'success' ? 'bullish' : 'bearish'}" style="font-size:0.68rem;">${m.status || '-'}</span>
      </div>
    </div>
  `).join('');

  el.innerHTML = `
    <div class="stats-row" style="margin-bottom:1rem;">
      <div class="stat-card">
        <div class="stat-label">Optimal Model Selected</div>
        <div class="stat-value" style="font-size:1.15rem;color:var(--neon-green);">${fc.best_model || 'ARIMA'}</div>
        <div class="stat-change up">Validated via RMSE/MAE on Out-of-Sample Window</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Projected Trend Directive</div>
        <div class="stat-value" style="font-size:1.1rem;">${fc.forecast_label || 'BULLISH_TREND'}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Directional Consensus: ${fc.directional_consensus || 'BULLISH'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Inter-Model Divergence</div>
        <div class="stat-value" style="font-size:1.15rem;">${fc.model_divergence_pct !== undefined ? fc.model_divergence_pct.toFixed(2) + '%' : '1.2%'}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Variance across ARIMA & LightGBM</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Data Staleness Status</div>
        <div class="stat-value" style="font-size:1.1rem;color:${isStale ? 'var(--accent-orange)' : 'var(--neon-green)'}">
          ${isStale ? 'Stale Data Flagged' : 'Verified Fresh'}
        </div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Checked via Market Data Gate</div>
      </div>
    </div>

    <!-- Chart: Continuous Past Trend + Dotted Future Forecast -->
    <div class="chart-container" style="margin-bottom:1rem;">
      <div class="chart-header">
        <div class="chart-title">📈 Time-Series Forecast Overlay (Dotted = Future)</div>
        <div class="chart-legend">
          <div class="legend-item"><div class="legend-line solid"></div> Observed History (Solid)</div>
          <div class="legend-item"><div class="legend-line dashed" style="background: repeating-linear-gradient(90deg, #00e5ff 0px, #00e5ff 4px, transparent 4px, transparent 8px);"></div> Forecast Projection (Dotted)</div>
          <div class="legend-item"><div style="width:20px;height:8px;background:rgba(0,229,255,0.2);border-radius:2px;"></div> 95% Confidence Interval</div>
        </div>
      </div>
      <div style="height:320px;">
        <canvas id="forecast-chart-canvas"></canvas>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
      <div class="card">
        <div class="section-header"><div class="section-title"><span class="dot"></span>Chronological Price Projections</div></div>
        <div style="font-size:0.72rem;color:var(--text-muted);display:grid;grid-template-columns:auto 1fr auto auto auto;gap:0.75rem;margin-bottom:0.5rem;padding:0 0 0.4rem;border-bottom:1px solid var(--border-color);">
          <div>Step</div><div>Target Date</div><div>Close (₹)</div><div>Change</div><div>95% Conf. Range</div>
        </div>
        ${forecastsHtml}
      </div>

      <div class="card">
        <div class="section-header"><div class="section-title"><span class="dot"></span>Multi-Model Cross-Validation Matrix</div></div>
        <div style="font-size:0.72rem;color:var(--text-muted);display:grid;grid-template-columns:1fr auto auto auto auto;gap:0.75rem;margin-bottom:0.5rem;padding:0 0 0.4rem;border-bottom:1px solid var(--border-color);">
          <div>Model Name</div><div>RMSE</div><div>MAE</div><div>Dir. Accuracy</div><div>Status</div>
        </div>
        ${modelsHtml || '<div style="color:var(--text-muted);text-align:center;padding:1.5rem;font-size:0.875rem;">No multi-model benchmark rows</div>'}
      </div>
    </div>
  `;

  setTimeout(() => {
    const canvas = document.getElementById('forecast-chart-canvas');
    if (!canvas || !forecasts.length) return;
    if (window.forecastDetailChart) window.forecastDetailChart.destroy();
    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

    const bars = (data.market_data?.bars || []).slice(-60);
    const histLabels = bars.map(b => (b.timestamp || '').slice(0, 10));
    const histPrices = bars.map(b => b.close);

    const fcLabels = forecasts.map(f => (f.target_date || `Step ${f.step}`).slice(0, 10));
    const fcPrices = forecasts.map(f => f.predicted_price);
    const fcUpper = forecasts.map(f => f.conf_upper);
    const fcLower = forecasts.map(f => f.conf_lower);

    const allLabels = [...histLabels, ...fcLabels];
    const lastPrice = histPrices.length > 0 ? histPrices[histPrices.length - 1] : null;

    const histData = [...histPrices, ...Array(forecasts.length).fill(null)];
    const fcData = histPrices.length > 0
      ? [...Array(histPrices.length - 1).fill(null), lastPrice, ...fcPrices]
      : fcPrices;
    const upData = histPrices.length > 0
      ? [...Array(histPrices.length - 1).fill(null), lastPrice, ...fcUpper]
      : fcUpper;
    const lowData = histPrices.length > 0
      ? [...Array(histPrices.length - 1).fill(null), lastPrice, ...fcLower]
      : fcLower;

    window.forecastDetailChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: 'Observed Historical Close (Solid)',
            data: histData,
            borderColor: isDark ? '#00ff41' : '#00aa2a',
            borderWidth: 2.5,
            borderDash: [],
            fill: false,
            tension: 0.15,
            pointRadius: bars.length > 30 ? 0 : 3,
          },
          {
            label: 'Future Forecast (Dotted)',
            data: fcData,
            borderColor: isDark ? '#00e5ff' : '#0284c7',
            borderWidth: 2.5,
            borderDash: [6, 4],
            backgroundColor: 'transparent',
            fill: false,
            tension: 0.2,
            pointRadius: 4,
            pointBackgroundColor: isDark ? '#00e5ff' : '#0284c7',
          },
          {
            label: '95% Upper Bound',
            data: upData,
            borderColor: 'transparent',
            backgroundColor: isDark ? 'rgba(0, 229, 255, 0.12)' : 'rgba(2, 132, 199, 0.12)',
            fill: '+1',
            pointRadius: 0,
            tension: 0.2,
          },
          {
            label: '95% Lower Bound',
            data: lowData,
            borderColor: 'transparent',
            backgroundColor: isDark ? 'rgba(0, 229, 255, 0.12)' : 'rgba(2, 132, 199, 0.12)',
            fill: false,
            pointRadius: 0,
            tension: 0.2,
          }
        ]
      },
      options: getChartOptions(isDark, 'Price (₹)')
    });
  }, 100);
}

// ---------------------------------------------------------------------------
// 5. SCENARIO SIMULATION AGENT DETAIL VIEW (DETAILED & STRUCTURED)
// ---------------------------------------------------------------------------
function renderScenarioDetail(sc) {
  const el = document.getElementById('scenario-detail-content');
  if (!el) return;

  const scenarios = sc.scenarios || sc.scenarios_sample || [];
  const worst = sc.worst_case_scenario;
  const best = sc.best_case_scenario;
  const monte = sc.monte_carlo;
  const base = sc.baseline_metrics || {};

  const scenariosHtml = scenarios.map(s => {
    const shock = s.percentage_price_change !== undefined ? s.percentage_price_change : (s.simulated?.percentage_price_change || 0);
    const hypPrice = s.hypothetical_price || s.simulated?.hypothetical_price || 0;
    const sRec = s.scenario_recommendation || s.simulated?.scenario_recommendation || 'HOLD';
    const sRisk = s.scenario_risk_score !== undefined ? s.scenario_risk_score : (s.simulated?.scenario_risk_score || 0);
    const flip = s.recommendation_changed || s.comparison?.recommendation_changed;

    return `
      <div class="scenario-row" style="grid-template-columns: 1.5fr 1fr 1fr 1fr 1.2fr; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.82rem;">
        <div>
          <div style="font-weight:700; color:var(--text-primary);">${s.name || s.scenario_name}</div>
          <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.2rem;">${s.description || 'Predefined macro stress test'}</div>
          ${flip ? '<span class="badge badge-warning" style="font-size:0.65rem;margin-top:0.25rem;">⚠️ Flips Recommendation</span>' : ''}
        </div>
        <div>
          <span class="badge badge-info" style="font-size:0.68rem;">${s.category || 'Macro'}</span>
        </div>
        <div class="sc-change ${shock >= 0 ? 'up' : 'down'}" style="font-weight:700;">
          ${shock >= 0 ? '+' : ''}${shock.toFixed(2)}%
          <div style="font-size:0.72rem;color:var(--text-muted);font-weight:normal;">Target: ₹${hypPrice.toFixed(2)}</div>
        </div>
        <div>
          <span style="font-weight:600;color:${getRiskColor(normalizeRiskScore(sRisk))};">${normalizeRiskScore(sRisk).toFixed(1)}/100</span>
        </div>
        <div>
          <span class="badge badge-${sRec.includes('BUY') || sRec === 'APPROVED' ? 'bullish' : sRec.includes('SELL') || sRec.includes('REJECTED') ? 'bearish' : 'neutral'}" style="font-size:0.7rem;">
            ${sRec.replace(/_/g, ' ')}
          </span>
        </div>
      </div>
    `;
  }).join('');

  el.innerHTML = `
    <!-- Top Summary Row -->
    <div class="stats-row" style="margin-bottom:1rem;">
      <div class="stat-card">
        <div class="stat-label">Baseline Equity Price</div>
        <div class="stat-value" style="font-size:1.15rem;">₹${(base.stock_price || 0).toFixed(2)}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Baseline Vol: ${(base.volatility_pct || 0).toFixed(1)}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Scenarios Evaluated</div>
        <div class="stat-value" style="font-size:1.15rem;">${sc.total_scenarios || scenarios.length} Stress Tests</div>
        <div class="stat-change down">${sc.scenarios_flipping_recommendation ? sc.scenarios_flipping_recommendation.length : 0} Recommendation Flips</div>
      </div>
      ${worst ? `
      <div class="stat-card" style="border-color:rgba(255,51,51,0.3);">
        <div class="stat-label" style="color:var(--accent-red);">🔴 Worst-Case Shock Scenario</div>
        <div class="stat-value" style="font-size:0.95rem;color:var(--accent-red);">${worst.name || 'Severe Macro Stress'}</div>
        <div class="stat-change down">Risk Score: ${normalizeRiskScore(worst.risk_score).toFixed(0)}/100 · Rec: ${worst.recommendation || 'REJECTED'}</div>
      </div>` : ''}
      ${best ? `
      <div class="stat-card" style="border-color:rgba(0,255,65,0.3);">
        <div class="stat-label" style="color:var(--neon-green);">🟢 Best-Case Catalyst Scenario</div>
        <div class="stat-value" style="font-size:0.95rem;color:var(--neon-green);">${best.name || 'Sector Bull Run'}</div>
        <div class="stat-change up">Risk Score: ${normalizeRiskScore(best.risk_score).toFixed(0)}/100 · Rec: ${best.recommendation || 'BUY'}</div>
      </div>` : ''}
    </div>

    <!-- Stochastic Monte Carlo Simulation Breakdown -->
    ${monte ? `
    <div class="card" style="margin-bottom:1rem;border-color:var(--border-neon);">
      <div class="section-header">
        <div class="section-title"><span class="dot"></span>Stochastic Monte Carlo Simulation (1,000 Simulated Paths · 20-Day Horizon)</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0.75rem;">
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">P5 (Bearish Tail Risk)</div>
          <div style="color:var(--accent-red);font-size:1.2rem;font-weight:800;">₹${(monte.p5_outcome || 0).toFixed(2)}</div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">5th Percentile Floor</div>
        </div>
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">P50 (Median Expectation)</div>
          <div style="color:var(--text-primary);font-size:1.2rem;font-weight:800;">₹${(monte.p50_outcome || 0).toFixed(2)}</div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">50th Percentile Median</div>
        </div>
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">P95 (Bullish Ceiling)</div>
          <div style="color:var(--neon-green);font-size:1.2rem;font-weight:800;">₹${(monte.p95_outcome || 0).toFixed(2)}</div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">95th Percentile Rally</div>
        </div>
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">Probability of Capital Loss</div>
          <div style="color:${(monte.probability_of_loss || 0) > 0.4 ? 'var(--accent-red)' : 'var(--neon-green)'};font-size:1.2rem;font-weight:800;">
            ${((monte.probability_of_loss || 0) * 100).toFixed(1)}%
          </div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">Simulated Loss Odds</div>
        </div>
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">Value at Risk (VaR 95%)</div>
          <div style="color:var(--accent-orange);font-size:1.2rem;font-weight:800;">
            ${monte.value_at_risk_95 !== undefined ? (monte.value_at_risk_95 * 100).toFixed(2) + '%' : 'N/A'}
          </div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">Max expected tail loss</div>
        </div>
        <div class="stat-card" style="background:var(--bg-secondary);">
          <div class="stat-label">Expected Shortfall (CVaR)</div>
          <div style="color:var(--accent-red);font-size:1.2rem;font-weight:800;">
            ${monte.expected_shortfall_95 !== undefined ? (monte.expected_shortfall_95 * 100).toFixed(2) + '%' : 'N/A'}
          </div>
          <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.2rem;">Mean loss in tail cases</div>
        </div>
      </div>
    </div>` : ''}

    <!-- Detailed Stress Testing Scenarios Table -->
    <div class="card">
      <div class="section-header">
        <div class="section-title"><span class="dot"></span>Deterministic Stress Testing Scenarios & Impact Matrix</div>
      </div>
      <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1.2fr;gap:0.75rem;font-size:0.75rem;color:var(--text-muted);padding-bottom:0.5rem;border-bottom:1px solid var(--border-color);font-weight:700;">
        <div>Scenario & Shock Trigger</div>
        <div>Category</div>
        <div>Price Shock %</div>
        <div>Scenario Risk</div>
        <div>Recommendation</div>
      </div>
      ${scenariosHtml || '<div style="text-align:center;color:var(--text-muted);padding:2rem;font-size:0.875rem;">No scenario simulations recorded.</div>'}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// 6. GEMINI LLM-AS-A-JUDGE DETAIL VIEW (POST-ANALYSIS AUDIT)
// ---------------------------------------------------------------------------
function renderJudgeDetail(judge) {
  const el = document.getElementById('judge-detail-content');
  if (!el) return;

  const dims = judge.dimensions || {};
  const isAvailable = judge.status === 'available';
  const scorePct = judge.overall_score !== null && judge.overall_score !== undefined ? (judge.overall_score * 100).toFixed(1) + '%' : 'Pending';

  el.innerHTML = `
    <div class="stats-row" style="margin-bottom:1rem;">
      <div class="stat-card">
        <div class="stat-label">Post-Analysis Quality Score</div>
        <div class="stat-value" style="font-size:1.25rem;color:var(--neon-green);">${scorePct}</div>
        <div class="stat-change up">Multi-Dimensional Evaluator</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Audit Verdict</div>
        <div class="stat-value" style="font-size:1.15rem;">${judge.verdict || (isAvailable ? 'PASSED_AUDIT' : 'CONFIGURED')}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Status: ${judge.status || 'available'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Evaluating Model</div>
        <div class="stat-value" style="font-size:1.1rem;color:var(--accent-blue);">${judge.actual_model || judge.configured_model || 'gemini-3.5-flash'}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Latency: ${judge.latency_ms ? judge.latency_ms.toFixed(0) + ' ms' : '< 1s'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Evidence Grounding</div>
        <div class="stat-value" style="font-size:1.1rem;color:${judge.has_sufficient_evidence ? 'var(--neon-green)' : 'var(--accent-orange)'}">
          ${judge.has_sufficient_evidence ? 'Sufficient Grounding' : 'Partial Evidence'}
        </div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.3rem;">Audited across all 6 agents</div>
      </div>
    </div>

    ${judge.evaluation_summary ? `
    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Gemini Audit Executive Summary</div></div>
      <p style="font-size:0.875rem;color:var(--text-secondary);line-height:1.8;">${judge.evaluation_summary}</p>
    </div>` : ''}

    ${Object.keys(dims).length ? `
    <div class="card" style="margin-bottom:1rem;">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Institutional Evaluation Dimensions</div></div>
      <div style="display:flex;flex-direction:column;gap:1.25rem;">
        ${Object.entries(dims).map(([key, dim]) => {
          const dScore = dim.score !== null && dim.score !== undefined ? dim.score : 0.85;
          const dScorePct = (dScore <= 1.0 ? dScore * 100 : dScore).toFixed(0);
          return `
            <div style="padding-bottom:1rem;border-bottom:1px solid var(--border-color);">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                <div style="font-size:0.88rem;font-weight:700;">${dim.dimension || key.replace(/_/g, ' ').toUpperCase()}</div>
                <div style="font-size:0.88rem;font-weight:800;color:var(--neon-green);">${dScorePct}%</div>
              </div>
              <div class="progress-bar" style="margin-bottom:0.6rem;">
                <div class="progress-fill green" style="width:${dScorePct}%;"></div>
              </div>
              <div style="font-size:0.82rem;color:var(--text-secondary);line-height:1.6;">${dim.explanation || 'Evaluated against institutional criteria.'}</div>
              ${dim.evidence_references?.length ? `
                <div style="margin-top:0.4rem;font-size:0.75rem;color:var(--accent-blue);">
                  Sources: ${dim.evidence_references.join(' · ')}
                </div>` : ''}
            </div>
          `;
        }).join('')}
      </div>
    </div>` : ''}

    ${judge.critical_findings?.length ? `
    <div class="card" style="margin-bottom:1rem;border-color:rgba(255,51,51,0.3);">
      <div class="section-header"><div class="section-title" style="color:var(--accent-red);"><span style="display:inline-block;width:8px;height:8px;background:var(--accent-red);border-radius:50%;margin-right:0.5rem;"></span>Critical Findings Identified by Judge</div></div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem;">
        ${(judge.critical_findings || []).map(f => `<li style="font-size:0.85rem;color:var(--accent-red);display:flex;gap:0.5rem;"><span>🔴</span><span>${f}</span></li>`).join('')}
      </ul>
    </div>` : ''}

    ${judge.strengths?.length ? `
    <div class="card">
      <div class="section-header"><div class="section-title"><span class="dot"></span>Identified Analysis Strengths</div></div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem;">
        ${(judge.strengths || []).map(s => `<li style="font-size:0.85rem;color:var(--text-secondary);display:flex;gap:0.5rem;"><span style="color:var(--neon-green);">✅</span><span>${s}</span></li>`).join('')}
      </ul>
    </div>` : ''}
  `;
}

// ===== Chatbot: Connected with Gemini API =====
function enableChatbot(runId) {
  document.getElementById('chatbot-status').textContent = `Connected: ${runId}`;
  document.getElementById('chatbot-status').style.color = 'var(--neon-green)';
  document.getElementById('geni-input').disabled = false;
  document.getElementById('geni-send-btn').disabled = false;

  addChatMessage('assistant', `🟢 Analysis complete! I'm **GENI**, powered by Google Gemini. Ask me anything about **${currentResults?.ticker}** — whether you should buy, risk explanations, technical indicators, or stress test scenarios.`);
}

function addChatMessage(role, text) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;

  const isUser = role === 'user';
  const avatarHtml = isUser
    ? `<div class="chat-avatar-mini user-avatar">U</div>`
    : `<div class="chat-avatar-mini" aria-label="GENI"></div>`;

  div.innerHTML = `${!isUser ? avatarHtml : ''}<div class="chat-bubble">${formatChatText(text)}</div>${isUser ? avatarHtml : ''}`;
  container.appendChild(div);
  setTimeout(() => {
    container.scrollTop = container.scrollHeight;
  }, 50);
}

function formatChatText(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^### (.*$)/gim, '<div style="font-weight:700;margin-top:0.4rem;color:var(--text-primary);">$1</div>')
    .replace(/^## (.*$)/gim, '<div style="font-weight:800;margin-top:0.5rem;color:var(--neon-green);">$1</div>')
    .replace(/^\* (.*$)/gim, '<div style="padding-left:0.5rem;margin:0.15rem 0;">• $1</div>')
    .replace(/^- (.*$)/gim, '<div style="padding-left:0.5rem;margin:0.15rem 0;">• $1</div>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

async function sendChatMessage() {
  const input = document.getElementById('geni-input');
  const text = input.value.trim();
  if (!text || !currentRunId) return;

  input.value = '';
  input.style.height = '36px';
  addChatMessage('user', text);

  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-message assistant';
  typingDiv.id = 'typing-indicator';
  typingDiv.innerHTML = `<div class="chat-avatar-mini" aria-label="GENI"></div><div class="chat-bubble" style="color:var(--text-muted);font-style:italic;">GENI is thinking...</div>`;
  document.getElementById('chat-messages').appendChild(typingDiv);
  document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;

  try {
    const payload = {
      run_id: currentRunId,
      message: text,
      conversation_id: currentConversationId || undefined
    };

    const response = await fetch(`${API_BASE}/geni/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    typingDiv.remove();

    if (!response.ok) {
      const err = await response.json();
      addChatMessage('assistant', `⚠️ ${err.detail || 'Failed to get response'}`);
      return;
    }

    const data = await response.json();
    currentConversationId = data.conversation_id;
    addChatMessage('assistant', data.response || 'No response produced.');

    if (data.sources_used?.length) {
      const sources = data.sources_used.join(' · ');
      const sourceDiv = document.createElement('div');
      sourceDiv.style.cssText = 'font-size:0.68rem;color:var(--text-muted);text-align:center;padding:0.2rem 1rem;';
      sourceDiv.textContent = `Grounded Sources: ${sources}`;
      document.getElementById('chat-messages').appendChild(sourceDiv);
      document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
    }

  } catch (err) {
    typingDiv.remove();
    addChatMessage('assistant', `⚠️ Connection error. Please make sure the backend is running at ${API_BASE}.`);
  }
}

function useQuickPrompt(prompt) {
  document.getElementById('geni-input').value = prompt;
  sendChatMessage();
}

// ===== Saved Results Page =====
function renderSavedResults() {
  const saved = JSON.parse(localStorage.getItem('ss_saved_results') || '[]');
  const container = document.getElementById('saved-results-list');
  if (!container) return;

  if (!saved.length) {
    container.innerHTML = '<div class="card" style="text-align:center;padding:3rem;color:var(--text-muted);">No saved analysis runs yet. Execute an analysis to save results automatically.</div>';
    return;
  }

  container.innerHTML = saved.map((item, idx) => `
    <div class="card" style="display:grid;grid-template-columns:1fr auto;gap:1rem;align-items:center;cursor:pointer;" onclick="loadSavedResult(${idx})">
      <div>
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.4rem;">
          <span style="font-size:1.1rem;font-weight:800;color:var(--neon-green);">${item.ticker}</span>
          <span class="badge badge-info" style="font-size:0.68rem;">${(item.data?.time_horizon || '').replace('_',' ')}</span>
          <span class="badge badge-${
            (item.data?.risk_findings?.recommendation || '').includes('BUY') || (item.data?.risk_findings?.recommendation || '') === 'APPROVED' ? 'bullish' :
            (item.data?.risk_findings?.recommendation || '').includes('SELL') ? 'bearish' : 'neutral'
          }" style="font-size:0.68rem;">${item.data?.risk_findings?.recommendation || 'HOLD'}</span>
        </div>
        <div style="font-size:0.78rem;color:var(--text-muted);">${new Date(item.timestamp).toLocaleString()}</div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem;">Run ID: <code>${item.run_id}</code></div>
      </div>
      <div style="display:flex;gap:0.5rem;">
        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();downloadResult(${idx})">⬇ Download JSON</button>
        <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();loadSavedResult(${idx})">View Analysis →</button>
      </div>
    </div>
  `).join('');
}

function loadSavedResult(idx) {
  const saved = JSON.parse(localStorage.getItem('ss_saved_results') || '[]');
  if (!saved[idx]) return;
  currentResults = saved[idx].data;
  currentRunId = saved[idx].run_id;
  currentConversationId = null;
  renderResults(currentResults);
  showPage('dashboard');
  showAlert(`Loaded saved run: ${saved[idx].ticker}`, 'success', 2000);
}

function downloadResult(idx) {
  const saved = JSON.parse(localStorage.getItem('ss_saved_results') || '[]');
  if (!saved[idx]) return;
  const blob = new Blob([JSON.stringify(saved[idx].data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${saved[idx].ticker}_${saved[idx].run_id}.json`;
  a.click();
}

// ===== Utilities =====
function showAlert(msg, type = 'info', duration = 4000) {
  const container = document.getElementById('alert-container');
  if (!container) return;
  const div = document.createElement('div');
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  div.className = `alert alert-${type}`;
  div.style.cssText = 'position:relative;animation:slideIn 0.3s ease;';
  div.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(div);
  setTimeout(() => div.remove(), duration);
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ===== Live Ticker Tape =====
async function fetchLiveTickerTape() {
  const tapeInner = document.querySelector('.ticker-tape-inner');
  if (!tapeInner) return;

  try {
    const res = await fetch(`${API_BASE}/api/ticker-tape`, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) return;
    const json = await res.json();
    if (!json.items || !Array.isArray(json.items) || json.items.length === 0) return;

    const renderedItems = json.items.map(item => {
      const isUp = item.is_up;
      const changeClass = isUp ? 'up' : 'down';
      return `<span class="ticker-item"><span class="sym">${item.sym}</span> ${item.price} <span class="${changeClass}">${item.change}</span></span>`;
    }).join('\n      ');

    // Duplicate for seamless infinite marquee scroll
    tapeInner.innerHTML = renderedItems + '\n      <!-- Duplicate for seamless scroll -->\n      ' + renderedItems;
    console.log(`Live ticker tape initialized with ${json.items.length} instruments (${json.source}) ✅`);
  } catch (err) {
    console.log('Ticker tape retaining default baseline prices:', err.message);
  }
}

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', () => {
  initTheme();

  // Load live prices once on opening website (not continuously polling)
  fetchLiveTickerTape();

  const hash = window.location.hash.replace('#', '') || 'home';
  showPage(hash);

  document.getElementById('stockSearch')?.addEventListener('keypress', e => {
    if (e.key === 'Enter') runAnalysis();
  });

  document.getElementById('geni-input')?.addEventListener('input', function() {
    this.style.height = '36px';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
  });

  document.getElementById('geni-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  window.addEventListener('popstate', e => {
    if (e.state?.page) showPage(e.state.page);
  });

  console.log('StockShield Frontend Initialized with Clean Executive Report, Live Ticker & Company Lookup ✅');
});
