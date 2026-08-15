let speedChart = null;
let pollTimer = null;
let drivesData = [];

document.addEventListener('DOMContentLoaded', () => {
  initChart();
  fetchDrives();

  document.getElementById('drive-select').addEventListener('change', updateDriveInfoDisplay);
  document.getElementById('btn-start').addEventListener('click', startBenchmark);
  document.getElementById('btn-stop').addEventListener('click', stopBenchmark);
});

// Chart.js の初期化
function initChart() {
  const ctx = document.getElementById('speedChart').getContext('2d');

  const gradient = ctx.createLinearGradient(0, 0, 0, 200);
  gradient.addColorStop(0, 'rgba(0, 240, 255, 0.4)');
  gradient.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

  speedChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: '転送速度 (MB/s)',
        data: [],
        borderColor: '#00f0ff',
        backgroundColor: gradient,
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        pointBackgroundColor: '#00f0ff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { family: 'Inter' } }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { family: 'Inter' } }
        }
      },
      plugins: {
        legend: { labels: { color: '#f3f4f6' } }
      }
    }
  });
}

// ドライブ一覧の取得
async function fetchDrives() {
  try {
    const res = await fetch('/api/drives');
    drivesData = await res.json();
    
    const select = document.getElementById('drive-select');
    select.innerHTML = '';

    if (drivesData.length === 0) {
      select.innerHTML = '<option value="">ドライブが見つかりません</option>';
      return;
    }

    drivesData.forEach((drive, index) => {
      const opt = document.createElement('option');
      opt.value = drive.mountpoint;
      opt.textContent = `${drive.mountpoint} ${drive.label ? '(' + drive.label + ')' : ''} [${drive.free_gb} GB 空き / ${drive.total_gb} GB]`;
      select.appendChild(opt);
    });

    updateDriveInfoDisplay();
  } catch (err) {
    console.error('Failed to fetch drives:', err);
  }
}

// 選択ドライブ情報の表示更新
function updateDriveInfoDisplay() {
  const mountpoint = document.getElementById('drive-select').value;
  const drive = drivesData.find(d => d.mountpoint === mountpoint);

  if (!drive) return;

  document.getElementById('info-mountpoint').textContent = drive.mountpoint;
  document.getElementById('info-label').textContent = drive.label || '(なし)';
  document.getElementById('info-fstype').textContent = drive.fstype;
  document.getElementById('info-total').textContent = `${drive.total_gb} GB`;
  document.getElementById('info-free').textContent = `${drive.free_gb} GB`;
  document.getElementById('info-percent-text').textContent = `${drive.percent}%`;
  
  const fill = document.getElementById('drive-percent-fill');
  fill.style.width = `${drive.percent}%`;
  if (drive.percent > 90) {
    fill.style.background = '#ef4444';
  } else if (drive.percent > 75) {
    fill.style.background = '#f59e0b';
  } else {
    fill.style.background = '#10b981';
  }
}

// ベンチマーク開始
async function startBenchmark() {
  const drive = document.getElementById('drive-select').value;
  const sizeMb = parseInt(document.getElementById('size-select').value);

  if (!drive) {
    alert('測定対象のドライブを選択してください');
    return;
  }

  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drive: drive, file_size_mb: sizeMb })
    });
    const data = await res.json();

    if (data.status === 'ok') {
      setUIRunningState(true);
      resetResultsUI();
      startPolling();
    } else {
      alert('エラー: ' + data.message);
    }
  } catch (err) {
    alert('ベンチマーク開始要求に失敗しました: ' + err);
  }
}

// ベンチマーク停止
async function stopBenchmark() {
  try {
    await fetch('/api/stop', { method: 'POST' });
  } catch (err) {
    console.error('Stop request error:', err);
  }
}

// UI 結果のリセット
function resetResultsUI() {
  document.getElementById('val-seq-read').textContent = '0.00';
  document.getElementById('val-seq-write').textContent = '0.00';
  document.getElementById('val-rnd4k-read').textContent = '0.00';
  document.getElementById('val-rnd4k-write').textContent = '0.00';
  document.getElementById('val-rnd4kq32-read').textContent = '0.00';
  document.getElementById('val-rnd4kq32-write').textContent = '0.00';

  document.getElementById('unit-rnd4k-read').textContent = 'MB/s (0.0 IOPS)';
  document.getElementById('unit-rnd4k-write').textContent = 'MB/s (0.0 IOPS)';
  document.getElementById('unit-rnd4kq32-read').textContent = 'MB/s (0.0 IOPS)';
  document.getElementById('unit-rnd4kq32-write').textContent = 'MB/s (0.0 IOPS)';

  if (speedChart) {
    speedChart.data.labels = [];
    speedChart.data.datasets[0].data = [];
    speedChart.update();
  }
}

// 実行中状態の UI 切替
function setUIRunningState(isRunning) {
  const btnStart = document.getElementById('btn-start');
  const btnStop = document.getElementById('btn-stop');
  const driveSelect = document.getElementById('drive-select');
  const sizeSelect = document.getElementById('size-select');

  if (isRunning) {
    btnStart.style.display = 'none';
    btnStop.style.display = 'flex';
    driveSelect.disabled = true;
    sizeSelect.disabled = true;
  } else {
    btnStart.style.display = 'flex';
    btnStop.style.display = 'none';
    driveSelect.disabled = false;
    sizeSelect.disabled = false;
    clearActiveRowHighlight();
  }
}

// アクティブ行の強調表示解除
function clearActiveRowHighlight() {
  document.querySelectorAll('.test-row').forEach(row => row.classList.remove('active'));
}

// ポーリング処理
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
  }, 400);
}

// 進捗状態および数値のリアルタイム更新
function updateProgressUI(data) {
  const currentTest = data.current_test || '';
  document.getElementById('status-text').textContent = currentTest || (data.status === 'completed' ? '測定完了' : '待機中');
  document.getElementById('progress-percent-text').textContent = `${data.progress_percent || 0}%`;
  document.getElementById('progress-bar-fill').style.width = `${data.progress_percent || 0}%`;

  const res = data.results || {};

  // 結果の更新
  if (res.seq_read_mbs !== undefined && res.seq_read_mbs > 0) {
    document.getElementById('val-seq-read').textContent = res.seq_read_mbs.toFixed(2);
  }
  if (res.seq_write_mbs !== undefined && res.seq_write_mbs > 0) {
    document.getElementById('val-seq-write').textContent = res.seq_write_mbs.toFixed(2);
  }

  if (res.rnd4k_read_mbs !== undefined && res.rnd4k_read_mbs > 0) {
    document.getElementById('val-rnd4k-read').textContent = res.rnd4k_read_mbs.toFixed(2);
    document.getElementById('unit-rnd4k-read').textContent = `MB/s (${res.rnd4k_read_iops || 0} IOPS)`;
  }
  if (res.rnd4k_write_mbs !== undefined && res.rnd4k_write_mbs > 0) {
    document.getElementById('val-rnd4k-write').textContent = res.rnd4k_write_mbs.toFixed(2);
    document.getElementById('unit-rnd4k-write').textContent = `MB/s (${res.rnd4k_write_iops || 0} IOPS)`;
  }

  if (res.rnd4k_q32_read_mbs !== undefined && res.rnd4k_q32_read_mbs > 0) {
    document.getElementById('val-rnd4kq32-read').textContent = res.rnd4k_q32_read_mbs.toFixed(2);
    document.getElementById('unit-rnd4kq32-read').textContent = `MB/s (${res.rnd4k_q32_read_iops || 0} IOPS)`;
  }
  if (res.rnd4k_q32_write_mbs !== undefined && res.rnd4k_q32_write_mbs > 0) {
    document.getElementById('val-rnd4kq32-write').textContent = res.rnd4k_q32_write_mbs.toFixed(2);
    document.getElementById('unit-rnd4kq32-write').textContent = `MB/s (${res.rnd4k_q32_write_iops || 0} IOPS)`;
  }

  // アクティブなテスト行のハイライト
  clearActiveRowHighlight();
  if (data.status === 'running') {
    if (currentTest.includes('シーケンシャル')) {
      document.getElementById('row-seq').classList.add('active');
    } else if (currentTest.includes('Q1T1')) {
      document.getElementById('row-rnd4k').classList.add('active');
    } else if (currentTest.includes('Q32T1')) {
      document.getElementById('row-rnd4kq32').classList.add('active');
    }
  }

  // リアルタイムグラフの更新
  if (speedChart && data.status === 'running' && data.current_speed_mbs > 0) {
    const timeLabel = new Date().toLocaleTimeString();
    speedChart.data.labels.push(timeLabel);
    speedChart.data.datasets[0].data.push(data.current_speed_mbs);

    // 最新30個のデータポイントに制限
    if (speedChart.data.labels.length > 30) {
      speedChart.data.labels.shift();
      speedChart.data.datasets[0].data.shift();
    }
    speedChart.update();
  }
}
