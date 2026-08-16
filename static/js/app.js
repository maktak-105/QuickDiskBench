let speedChart = null;
let pollTimer = null;
let drivesData = [];
let currentResults = {};
let currentLang = 'ja';  // in-memory only — no localStorage (NavigateToString origin restriction)
let pendingProgressData = null;
let progressFrameScheduled = false;

// Progress messages can arrive faster than the WebView can paint. Keep only
// the newest sample and render at the browser's refresh rate so measurement
// callbacks never turn into a growing UI queue.
function scheduleProgressRender(data) {
  pendingProgressData = data;
  if (progressFrameScheduled) return;
  progressFrameScheduled = true;
  const render = () => {
    progressFrameScheduled = false;
    const latest = pendingProgressData;
    pendingProgressData = null;
    if (latest) updateProgressUI(latest);
  };
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(render);
  else setTimeout(render, 16);
}

function getWebView() {
  try {
    if (typeof window !== 'undefined' && window.chrome && window.chrome.webview) {
      return window.chrome.webview;
    }
  } catch (e) {}
  return null;
}

const I18N = {
  ja: {
    btn_lang: "🌐 English",
    sub1: "Win32 Unbuffered Direct I/O Benchmark Engine",
    btn_csv: "📊 CSV出力",
    btn_help: "❓ ヘルプ",
    lbl_mode: "モード:",
    opt_mode_cdm: "キャッシュあり",
    opt_mode_raw: "キャッシュなし",
    lbl_drive: "ドライブ:",
    opt_detecting: "検出中...",
    lbl_size: "サイズ:",
    lbl_passes: "回数:",
    opt_pass_1: "1 回 (高速)",
    opt_pass_3: "3 回",
    opt_pass_5: "5 回 (標準)",
    opt_pass_9: "9 回 (高精度)",
    btn_start: "テスト開始",
    btn_stop: "停止",
    card_bench_title: "ベンチマーク測定結果 (MB/s & IOPS & 統計)",
    sub_seq_q8: "シーケンシャル 1MB (Q8 同期)",
    sub_seq_q1: "シーケンシャル 1MB (Q1 同期)",
    sub_rnd_q32: "ランダム 4KB (Q32 同期)",
    sub_rnd_q1: "ランダム 4KB (Q1 同期)",
    lbl_read: "READ",
    lbl_write: "WRITE",
    status_idle: "待機中",
    status_completed: "測定完了！すべてのテストが終了しました。",
    status_stopped: "測定が停止されました。",
    card_drive_title: "選択ドライブ情報",
    lbl_mount: "マウント:",
    lbl_vol_label: "ラベル:",
    lbl_fstype: "ファイルシステム:",
    lbl_total_cap: "総容量:",
    lbl_free_cap: "空き容量:",
    lbl_used_pct: "使用率:",
    card_chart_title: "リアルタイム転送速度 (MB/s)",
    modal_title: "QuickDiskBench ヘルプ & バージョン情報",
    csv_alert_empty: "測定結果がありません。ベンチマークを実行してからCSVを出力してください。",
    help_html: `
      <div class="help-box">
        <h3>📌 アプリケーション概要 (QuickDiskBench v1.0.0)</h3>
        <p>Windows Win32 Native Direct I/O (<code>FILE_FLAG_NO_BUFFERING</code>) を用いて、ストレージ (NVMe SSD / SATA SSD / HDD) の限界転送速度を極限精度で測定するベンチマークソフトウェアです。</p>
        <p style="margin-top: 4px; color: var(--accent-cyan);"><strong>GitHub:</strong> <a href="https://github.com/maktak-105" target="_blank" style="color:var(--accent-cyan);">maktak-105</a></p>
      </div>

      <div class="help-box">
        <h3>📊 測定項目の解説</h3>
        <table class="help-table">
          <tr><th>項目名</th><th>ブロック / キュー</th><th>測定対象の特性</th></tr>
          <tr><td><code>SEQ1M Q8T1</code></td><td>1MB / QD8</td><td>大容量ファイル転送の最大持続スループット (動画・ゲーム読込等)</td></tr>
          <tr><td><code>SEQ1M Q1T1</code></td><td>1MB / QD1</td><td>単一スレッドでの連続アクセス速度 (実利用時の基本速度)</td></tr>
          <tr><td><code>RND4K Q32T1</code></td><td>4KB / QD32</td><td>NVMe コマンドキューを活かしたマルチタスク微小I/O応答性能 (IOPS)</td></tr>
          <tr><td><code>RND4K Q1T1</code></td><td>4KB / QD1</td><td>OSやアプリの体感速度に最も直結する単一キューランダムアクセス</td></tr>
        </table>
      </div>

      <div class="help-box">
        <h3>⚙️ 測定モードの違い</h3>
        <p><strong>キャッシュあり:</strong> <code>FILE_FLAG_NO_BUFFERING</code> によりWindowsのOSキャッシュは使わず、ストレージ側のハードウェアキャッシュは使用して測定します。</p>
        <p style="margin-top: 4px;"><strong>キャッシュなし:</strong> OSキャッシュを使わないまま、さらに <code>FILE_FLAG_WRITE_THROUGH</code> を有効化してハードウェアキャッシュの影響も抑える測定です。</p>
      </div>

      <div class="help-box">
        <h3>📈 統計機能 (平均値 ± 標準偏差 σ)</h3>
        <p>複数回の測定 (3回/5回/9回) を指定した場合、単なる最速値ではなく、各パスの実測値から <strong>平均スループット (Mean)</strong> と <strong>ばらつき (標準偏差 ±σ)</strong> を算出して高精度に表示します。</p>
      </div>

      <div class="help-footer">
        <span>QuickDiskBench Version 1.0.0</span>
        <span>Developer: maktak-105</span>
      </div>
    `
  },
  en: {
    btn_lang: "🌐 日本語",
    sub1: "Win32 Unbuffered Direct I/O Benchmark Engine",
    btn_csv: "📊 Export CSV",
    btn_help: "❓ Help",
    lbl_mode: "Mode:",
    opt_mode_cdm: "With Cache",
    opt_mode_raw: "Without Cache",
    lbl_drive: "Drive:",
    opt_detecting: "Detecting...",
    lbl_size: "Size:",
    lbl_passes: "Passes:",
    opt_pass_1: "1 Pass (Fast)",
    opt_pass_3: "3 Passes",
    opt_pass_5: "5 Passes (Default)",
    opt_pass_9: "9 Passes (Accurate)",
    btn_start: "Start Test",
    btn_stop: "Stop",
    card_bench_title: "Benchmark Results (MB/s & IOPS & Statistics)",
    sub_seq_q8: "Sequential 1MB (Q8 Sync)",
    sub_seq_q1: "Sequential 1MB (Q1 Sync)",
    sub_rnd_q32: "Random 4KB (Q32 Sync)",
    sub_rnd_q1: "Random 4KB (Q1 Sync)",
    lbl_read: "READ",
    lbl_write: "WRITE",
    status_idle: "Idle",
    status_completed: "Benchmark Completed! All tests finished successfully.",
    status_stopped: "Benchmark Stopped.",
    card_drive_title: "Selected Drive Info",
    lbl_mount: "Mount:",
    lbl_vol_label: "Label:",
    lbl_fstype: "File System:",
    lbl_total_cap: "Total Capacity:",
    lbl_free_cap: "Free Space:",
    lbl_used_pct: "Used Space:",
    card_chart_title: "Real-time Transfer Speed (MB/s)",
    modal_title: "QuickDiskBench Help & Version Information",
    csv_alert_empty: "No benchmark results to export. Please run a benchmark test first.",
    help_html: `
      <div class="help-box">
        <h3>📌 Overview (QuickDiskBench v1.0.0)</h3>
        <p>A native high-performance storage benchmark application utilizing Win32 Direct I/O (<code>FILE_FLAG_NO_BUFFERING</code>) to measure maximum sustained throughput and responsiveness on NVMe SSDs, SATA SSDs, and HDDs.</p>
        <p style="margin-top: 4px; color: var(--accent-cyan);"><strong>GitHub:</strong> <a href="https://github.com/maktak-105" target="_blank" style="color:var(--accent-cyan);">maktak-105</a></p>
      </div>

      <div class="help-box">
        <h3>📊 Benchmark Metrics Explained</h3>
        <table class="help-table">
          <tr><th>Metric</th><th>Block / Queue</th><th>Characteristics Measured</th></tr>
          <tr><td><code>SEQ1M Q8T1</code></td><td>1MB / QD8</td><td>Peak sustained sequential transfer for large files (videos, games)</td></tr>
          <tr><td><code>SEQ1M Q1T1</code></td><td>1MB / QD1</td><td>Single-thread sequential transfer (baseline everyday speed)</td></tr>
          <tr><td><code>RND4K Q32T1</code></td><td>4KB / QD32</td><td>Deep-queue random small I/O throughput utilizing NVMe queues (IOPS)</td></tr>
          <tr><td><code>RND4K Q1T1</code></td><td>4KB / QD1</td><td>Single-queue random access (most reflective of OS/App responsiveness)</td></tr>
        </table>
      </div>

      <div class="help-box">
        <h3>⚙️ Benchmark Modes</h3>
        <p><strong>With Cache:</strong> Windows OS caching is bypassed with <code>FILE_FLAG_NO_BUFFERING</code>, while the storage device's hardware cache remains available.</p>
        <p style="margin-top: 4px;"><strong>Without Cache:</strong> OS caching remains bypassed, and <code>FILE_FLAG_WRITE_THROUGH</code> is enabled to reduce the effect of the device hardware cache.</p>
      </div>

      <div class="help-box">
        <h3>📈 Multi-Pass Statistics (Mean ± StdDev σ)</h3>
        <p>When running multiple passes (3, 5, or 9 passes), QuickDiskBench calculates and displays the <strong>Mean Throughput</strong> along with the <strong>Standard Deviation (±σ)</strong> to capture real-world performance stability.</p>
      </div>

      <div class="help-footer">
        <span>QuickDiskBench Version 1.0.0</span>
        <span>Developer: maktak-105</span>
      </div>
    `
  }
};

function handleNativeMessage(event) {
  try {
    const msg = (typeof event.data === 'string') ? JSON.parse(event.data) : event.data;
    if (!msg) return;

    if (msg.type === 'drives') {
      drivesData = msg.data || [];
      populateDrivesSelect();
    } else if (msg.type === 'progress') {
      scheduleProgressRender(msg.data);
      if (msg.data.status === 'completed' || msg.data.status === 'error' || msg.data.status === 'stopped') {
        setUIRunningState(false);
      }
    }
  } catch (e) {
    console.error('Error handling native message:', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  try {
    initChart();
  } catch (e) { console.error('initChart error:', e); }

  try {
    applyLanguage(currentLang);
  } catch (e) { console.error('applyLanguage error:', e); }

  // Setup WebView2 bridge listener
  const setupBridge = () => {
    const wv = getWebView();
    if (wv) {
      try {
        wv.removeEventListener('message', handleNativeMessage);
        wv.addEventListener('message', handleNativeMessage);
        wv.postMessage({ action: 'get_drives' });
        return true;
      } catch (e) {}
    }
    return false;
  };

  if (!setupBridge()) {
    let checkCount = 0;
    const bridgeTimer = setInterval(() => {
      checkCount++;
      if (setupBridge() || checkCount > 30) {
        clearInterval(bridgeTimer);
        if (checkCount > 30) fetchDrives();
      }
    }, 50);
  }

  // Event Listeners
  const addEv = (id, evt, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(evt, handler);
  };

  addEv('drive-select', 'change', updateDriveInfoDisplay);
  addEv('btn-start', 'click', startBenchmark);
  addEv('btn-stop', 'click', stopBenchmark);
  addEv('btn-lang', 'click', toggleLanguage);
  addEv('btn-csv', 'click', exportCSV);
  addEv('btn-help', 'click', openHelpModal);
  addEv('btn-modal-close', 'click', closeHelpModal);
  addEv('help-modal', 'click', (e) => {
    if (e.target.id === 'help-modal') closeHelpModal();
  });
});

// 言語切替
function toggleLanguage() {
  currentLang = (currentLang === 'ja') ? 'en' : 'ja';
  applyLanguage(currentLang);
}

function applyLanguage(lang) {
  const dict = I18N[lang] || I18N.ja;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) el.textContent = dict[key];
  });

  const langText = document.getElementById('lang-text');
  if (langText) langText.textContent = dict.btn_lang;
  
  const modalContent = document.getElementById('modal-body-content');
  if (modalContent) modalContent.innerHTML = dict.help_html;

  if (drivesData && drivesData.length > 0) {
    populateDrivesSelect();
    updateDriveInfoDisplay();
  }
}

// ヘルプモーダル
function openHelpModal() {
  const modal = document.getElementById('help-modal');
  if (modal) modal.classList.add('active');
}

function closeHelpModal() {
  const modal = document.getElementById('help-modal');
  if (modal) modal.classList.remove('active');
}

// Chart.js の初期化
function initChart() {
  const canvas = document.getElementById('speedChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const gradient = ctx.createLinearGradient(0, 0, 0, 90);
  gradient.addColorStop(0, 'rgba(0, 240, 255, 0.4)');
  gradient.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

  speedChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: currentLang === 'ja' ? '転送速度 (MB/s)' : 'Transfer Speed (MB/s)',
        data: [],
        borderColor: '#00f0ff',
        backgroundColor: gradient,
        borderWidth: 1.5,
        fill: true,
        tension: 0.3,
        pointRadius: 1.5,
        pointBackgroundColor: '#00f0ff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: { color: '#9ca3af', font: { size: 9, family: 'Inter' }, maxRotation: 0 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: { color: '#9ca3af', font: { size: 9, family: 'Inter' } }
        }
      },
      plugins: {
        legend: { labels: { color: '#f3f4f6', font: { size: 10 }, boxWidth: 12 } }
      }
    }
  });
}

// ドライブ一覧の描画
function populateDrivesSelect() {
  const select = document.getElementById('drive-select');
  if (!select) return;
  const savedVal = select.value;
  select.innerHTML = '';

  if (!drivesData || drivesData.length === 0) {
    select.innerHTML = `<option value="C:\\">${currentLang === 'ja' ? 'C:\\ (ローカルドライブ)' : 'C:\\ (Local Drive)'}</option>`;
    return;
  }

  drivesData.forEach((drive) => {
    const opt = document.createElement('option');
    opt.value = drive.mountpoint;
    const freeText = currentLang === 'ja' ? '空き' : 'free';
    opt.textContent = `${drive.mountpoint} ${drive.label ? '(' + drive.label + ')' : ''} [${drive.free_gb} GB ${freeText} / ${drive.total_gb} GB]`;
    select.appendChild(opt);
  });

  if (savedVal) select.value = savedVal;
  updateDriveInfoDisplay();
}

// ドライブ一覧の取得
function fetchDrives() {
  const wv = getWebView();
  if (wv) {
    try {
      wv.postMessage({ action: 'get_drives' });
      return;
    } catch (e) {}
  }

  fetch('/api/drives')
    .then(r => r.json())
    .then(data => {
      drivesData = data || [];
      populateDrivesSelect();
    })
    .catch(err => {
      console.error('Failed to fetch drives:', err);
      drivesData = [{ mountpoint: 'C:\\', label: 'Local Disk', fstype: 'NTFS', total_gb: 512, free_gb: 256, used_gb: 256, percent: 50 }];
      populateDrivesSelect();
    });
}

// 選択ドライブ情報の表示更新
function updateDriveInfoDisplay() {
  const select = document.getElementById('drive-select');
  if (!select) return;
  const mountpoint = select.value || (drivesData.length > 0 ? drivesData[0].mountpoint : 'C:\\');
  const drive = drivesData.find(d => d.mountpoint === mountpoint) || (drivesData.length > 0 ? drivesData[0] : null);

  if (!drive) return;

  const setTxt = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };

  setTxt('info-mountpoint', drive.mountpoint);
  setTxt('info-label', drive.label || (currentLang === 'ja' ? '(なし)' : '(None)'));
  setTxt('info-fstype', drive.fstype);
  setTxt('info-total', `${drive.total_gb} GB`);
  setTxt('info-free', `${drive.free_gb} GB`);
  setTxt('info-percent-text', `${drive.percent}%`);
  
  const fill = document.getElementById('drive-percent-fill');
  if (fill) {
    fill.style.width = `${drive.percent}%`;
    if (drive.percent > 90) fill.style.background = '#ef4444';
    else if (drive.percent > 75) fill.style.background = '#f59e0b';
    else fill.style.background = '#10b981';
  }
}

// ベンチマーク開始
function startBenchmark() {
  const select = document.getElementById('drive-select');
  let drive = select ? select.value : 'C:\\';
  const sizeMb = parseInt(document.getElementById('size-select').value) || 1024;
  const profile = document.getElementById('profile-select').value || 'cdm';
  const passes = parseInt(document.getElementById('count-select').value) || 5;

  if (!drive) {
    if (select && select.options.length > 0 && select.options[0].value) {
      drive = select.options[0].value;
      select.value = drive;
    } else {
      drive = 'C:\\';
    }
  }

  setUIRunningState(true);
  resetResultsUI();

  const wv = getWebView();
  if (wv) {
    try {
      wv.postMessage({
        action: 'start',
        drive: drive,
        file_size_mb: sizeMb,
        profile: profile,
        passes: passes
      });
      return;
    } catch (e) {
      console.error('WebView postMessage failed:', e);
    }
  }

  fetch('/api/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drive: drive, file_size_mb: sizeMb, profile: profile, passes: passes })
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'ok') {
      startPolling();
    } else {
      alert('Error: ' + data.message);
      setUIRunningState(false);
    }
  })
  .catch(err => {
    alert('Failed to start benchmark: ' + err);
    setUIRunningState(false);
  });
}

// ベンチマーク停止
function stopBenchmark() {
  const wv = getWebView();
  if (wv) {
    try {
      wv.postMessage({ action: 'stop' });
      return;
    } catch (e) {}
  }

  fetch('/api/stop', { method: 'POST' }).catch(err => {
    console.error('Stop request error:', err);
  });
}

// UI 結果のリセット
function resetResultsUI() {
  currentResults = {};
  const setTxt = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };

  setTxt('val-seq-q8-read', '0.00');
  setTxt('val-seq-q8-write', '0.00');
  setTxt('val-seq-read', '0.00');
  setTxt('val-seq-write', '0.00');
  setTxt('val-rnd4kq32-read', '0.00');
  setTxt('val-rnd4kq32-write', '0.00');
  setTxt('val-rnd4k-read', '0.00');
  setTxt('val-rnd4k-write', '0.00');

  setTxt('stats-seq-q8-read', '');
  setTxt('stats-seq-q8-write', '');
  setTxt('stats-seq-read', '');
  setTxt('stats-seq-write', '');
  setTxt('stats-rnd4kq32-read', '');
  setTxt('stats-rnd4kq32-write', '');
  setTxt('stats-rnd4k-read', '');
  setTxt('stats-rnd4k-write', '');

  setTxt('unit-rnd4kq32-read', 'MB/s (0 IOPS)');
  setTxt('unit-rnd4kq32-write', 'MB/s (0 IOPS)');
  setTxt('unit-rnd4k-read', 'MB/s (0 IOPS)');
  setTxt('unit-rnd4k-write', 'MB/s (0 IOPS)');

  if (speedChart) {
    speedChart.data.labels = [];
    speedChart.data.datasets[0].data = [];
    speedChart.update('none');
  }
}

// 実行中状態の UI 切替
function setUIRunningState(isRunning) {
  const btnStart = document.getElementById('btn-start');
  const btnStop = document.getElementById('btn-stop');
  const driveSelect = document.getElementById('drive-select');
  const sizeSelect = document.getElementById('size-select');
  const profileSelect = document.getElementById('profile-select');
  const countSelect = document.getElementById('count-select');

  if (isRunning) {
    if (btnStart) btnStart.style.display = 'none';
    if (btnStop) btnStop.style.display = 'flex';
    if (driveSelect) driveSelect.disabled = true;
    if (sizeSelect) sizeSelect.disabled = true;
    if (profileSelect) profileSelect.disabled = true;
    if (countSelect) countSelect.disabled = true;
  } else {
    if (btnStart) btnStart.style.display = 'flex';
    if (btnStop) btnStop.style.display = 'none';
    if (driveSelect) driveSelect.disabled = false;
    if (sizeSelect) sizeSelect.disabled = false;
    if (profileSelect) profileSelect.disabled = false;
    if (countSelect) countSelect.disabled = false;
    clearActiveRowHighlight();
  }
}

// アクティブ行の強調表示解除
function clearActiveRowHighlight() {
  document.querySelectorAll('.test-row').forEach(row => row.classList.remove('active'));
}

// ポーリング処理 (HTTP API 用)
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      updateProgressUI(data);

      if (data.status === 'completed' || data.status === 'idle' || data.status === 'error' || data.status === 'stopped') {
        clearInterval(pollTimer);
        setUIRunningState(false);
      }
    } catch (err) {
      console.error('Polling error:', err);
    }
  }, 350);
}

// 進捗状態および数値のリアルタイム更新
function updateProgressUI(data) {
  const dict = I18N[currentLang] || I18N.ja;
  const currentTest = data.current_test || '';
  
  let displayStatus = currentTest;
  if (data.status === 'completed') displayStatus = dict.status_completed;
  else if (data.status === 'stopped') displayStatus = dict.status_stopped;
  else if (data.status === 'idle') displayStatus = dict.status_idle;

  const setTxt = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };

  setTxt('status-text', displayStatus);
  setTxt('progress-percent-text', `${data.progress_percent || 0}%`);
  
  const pBar = document.getElementById('progress-bar-fill');
  if (pBar) pBar.style.width = `${data.progress_percent || 0}%`;

  const res = data.results || {};
  currentResults = res;
  currentResults._meta = {
    drive: document.getElementById('drive-select') ? document.getElementById('drive-select').value : 'C:\\',
    size: document.getElementById('size-select') ? document.getElementById('size-select').value : '1024',
    passes: document.getElementById('count-select') ? document.getElementById('count-select').value : '5',
    profile: document.getElementById('profile-select') ? document.getElementById('profile-select').value : 'cdm',
    timestamp: new Date().toISOString()
  };

  const isMultiPass = (data.passes && data.passes > 1);

  function formatStats(std, n) {
    if (!isMultiPass || std === undefined) return '';
    return `±${std.toFixed(2)} (n=${n || data.passes})`;
  }

  // 1. SEQ1M Q8T1
  if (res.seq_q8_read_mbs !== undefined && res.seq_q8_read_mbs > 0) {
    setTxt('val-seq-q8-read', res.seq_q8_read_mbs.toFixed(2));
    setTxt('stats-seq-q8-read', formatStats(res.seq_q8_read_std, data.passes));
  }
  if (res.seq_q8_write_mbs !== undefined && res.seq_q8_write_mbs > 0) {
    setTxt('val-seq-q8-write', res.seq_q8_write_mbs.toFixed(2));
    setTxt('stats-seq-q8-write', formatStats(res.seq_q8_write_std, data.passes));
  }

  // 2. SEQ1M Q1T1
  if (res.seq_read_mbs !== undefined && res.seq_read_mbs > 0) {
    setTxt('val-seq-read', res.seq_read_mbs.toFixed(2));
    setTxt('stats-seq-read', formatStats(res.seq_read_std, data.passes));
  }
  if (res.seq_write_mbs !== undefined && res.seq_write_mbs > 0) {
    setTxt('val-seq-write', res.seq_write_mbs.toFixed(2));
    setTxt('stats-seq-write', formatStats(res.seq_write_std, data.passes));
  }

  // 3. RND4K Q32T1
  if (res.rnd4k_q32_read_mbs !== undefined && res.rnd4k_q32_read_mbs > 0) {
    setTxt('val-rnd4kq32-read', res.rnd4k_q32_read_mbs.toFixed(2));
    setTxt('unit-rnd4kq32-read', `MB/s (${Math.round(res.rnd4k_q32_read_iops || 0)} IOPS)`);
    setTxt('stats-rnd4kq32-read', formatStats(res.rnd4k_q32_read_std, data.passes));
  }
  if (res.rnd4k_q32_write_mbs !== undefined && res.rnd4k_q32_write_mbs > 0) {
    setTxt('val-rnd4kq32-write', res.rnd4k_q32_write_mbs.toFixed(2));
    setTxt('unit-rnd4kq32-write', `MB/s (${Math.round(res.rnd4k_q32_write_iops || 0)} IOPS)`);
    setTxt('stats-rnd4kq32-write', formatStats(res.rnd4k_q32_write_std, data.passes));
  }

  // 4. RND4K Q1T1
  if (res.rnd4k_read_mbs !== undefined && res.rnd4k_read_mbs > 0) {
    setTxt('val-rnd4k-read', res.rnd4k_read_mbs.toFixed(2));
    setTxt('unit-rnd4k-read', `MB/s (${Math.round(res.rnd4k_read_iops || 0)} IOPS)`);
    setTxt('stats-rnd4k-read', formatStats(res.rnd4k_read_std, data.passes));
  }
  if (res.rnd4k_write_mbs !== undefined && res.rnd4k_write_mbs > 0) {
    setTxt('val-rnd4k-write', res.rnd4k_write_mbs.toFixed(2));
    setTxt('unit-rnd4k-write', `MB/s (${Math.round(res.rnd4k_write_iops || 0)} IOPS)`);
    setTxt('stats-rnd4k-write', formatStats(res.rnd4k_write_std, data.passes));
  }

  // アクティブなテスト行のハイライト
  clearActiveRowHighlight();
  if (data.status === 'running') {
    if (currentTest.includes('Q8T1')) {
      const el = document.getElementById('row-seq-q8');
      if (el) el.classList.add('active');
    } else if (currentTest.includes('SEQ1M Q1T1')) {
      const el = document.getElementById('row-seq');
      if (el) el.classList.add('active');
    } else if (currentTest.includes('Q32T1')) {
      const el = document.getElementById('row-rnd4kq32');
      if (el) el.classList.add('active');
    } else if (currentTest.includes('RND4K Q1T1')) {
      const el = document.getElementById('row-rnd4k');
      if (el) el.classList.add('active');
    }
  }

  // リアルタイムグラフの更新
  if (speedChart && data.status === 'running' && data.current_speed_mbs > 0) {
    const timeLabel = new Date().toLocaleTimeString();
    speedChart.data.labels.push(timeLabel);
    speedChart.data.datasets[0].data.push(data.current_speed_mbs);

    if (speedChart.data.labels.length > 30) {
      speedChart.data.labels.shift();
      speedChart.data.datasets[0].data.shift();
    }
    speedChart.update('none');
  }
}

// CSV エクスポート機能
function exportCSV() {
  const dict = I18N[currentLang] || I18N.ja;
  
  if (!currentResults || (!currentResults.seq_q8_read_mbs && !currentResults.seq_read_mbs)) {
    alert(dict.csv_alert_empty);
    return;
  }

  const meta = currentResults._meta || {};
  const drive = meta.drive || (document.getElementById('drive-select') ? document.getElementById('drive-select').value : 'C:\\');
  const sizeMb = meta.size || (document.getElementById('size-select') ? document.getElementById('size-select').value : '1024');
  const passes = meta.passes || (document.getElementById('count-select') ? document.getElementById('count-select').value : '5');
  const profile = meta.profile || (document.getElementById('profile-select') ? document.getElementById('profile-select').value : 'cdm');
  const now = new Date();
  const dateStr = now.toISOString().replace(/T/, ' ').replace(/\..+/, '');

  let csv = 'App,QuickDiskBench,Version,v1.0.0,Author,maktak-105\r\n';
  csv += `Date,${dateStr},Target Drive,${drive},Size,${sizeMb} MB,Passes,${passes},Profile,${profile}\r\n\r\n`;
  csv += 'Test Item,Read (MB/s),Read StdDev (+-sigma),Read IOPS,Write (MB/s),Write StdDev (+-sigma),Write IOPS\r\n';

  csv += `SEQ1M Q8T1,${(currentResults.seq_q8_read_mbs || 0).toFixed(2)},${(currentResults.seq_q8_read_std || 0).toFixed(2)},${Math.round((currentResults.seq_q8_read_mbs || 0))},${(currentResults.seq_q8_write_mbs || 0).toFixed(2)},${(currentResults.seq_q8_write_std || 0).toFixed(2)},${Math.round((currentResults.seq_q8_write_mbs || 0))}\r\n`;
  csv += `SEQ1M Q1T1,${(currentResults.seq_read_mbs || 0).toFixed(2)},${(currentResults.seq_read_std || 0).toFixed(2)},${Math.round((currentResults.seq_read_mbs || 0))},${(currentResults.seq_write_mbs || 0).toFixed(2)},${(currentResults.seq_write_std || 0).toFixed(2)},${Math.round((currentResults.seq_write_mbs || 0))}\r\n`;
  csv += `RND4K Q32T1,${(currentResults.rnd4k_q32_read_mbs || 0).toFixed(2)},${(currentResults.rnd4k_q32_read_std || 0).toFixed(2)},${Math.round(currentResults.rnd4k_q32_read_iops || 0)},${(currentResults.rnd4k_q32_write_mbs || 0).toFixed(2)},${(currentResults.rnd4k_q32_write_std || 0).toFixed(2)},${Math.round(currentResults.rnd4k_q32_write_iops || 0)}\r\n`;
  csv += `RND4K Q1T1,${(currentResults.rnd4k_read_mbs || 0).toFixed(2)},${(currentResults.rnd4k_read_std || 0).toFixed(2)},${Math.round(currentResults.rnd4k_read_iops || 0)},${(currentResults.rnd4k_write_mbs || 0).toFixed(2)},${(currentResults.rnd4k_write_std || 0).toFixed(2)},${Math.round(currentResults.rnd4k_write_iops || 0)}\r\n`;

  // Trigger download with BOM for Excel compatibility
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const fileDate = now.getFullYear() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + '_' +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  link.setAttribute('href', url);
  link.setAttribute('download', `QuickDiskBench_Benchmark_${fileDate}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
