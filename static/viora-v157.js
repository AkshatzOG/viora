/* Viora responsive polish, personalized chart shelves, and queue page. */
(function () {
  var charts = [
    {id:'top50',title:'Country Top 50',sub:'Apple Music regional chart',art:0},
    {id:'week',title:'Popular this week',sub:'Current most-played snapshot · refreshed daily',art:1},
    {id:'love',title:'Love',sub:'Romantic song discovery mix',art:2},
    {id:'pop',title:'Pop',sub:'Pop song discovery mix',art:3},
    {id:'english',title:'English',sub:'English-language discovery mix',art:4},
    {id:'hindi',title:'Hindi',sub:'Hindi-language discovery mix',art:5},
    {id:'phonk',title:'Phonk',sub:'Underground bass and drift energy',art:6},
    {id:'hiphop',title:'Hip-hop',sub:'Global rap and hip-hop releases',art:7},
    {id:'afrobeats',title:'Afrobeats',sub:'West African pop and rhythm',art:8},
    {id:'kpop',title:'K-pop',sub:'Korean pop releases',art:9},
    {id:'jpop',title:'J-pop',sub:'Japanese pop discoveries',art:10},
    {id:'workout',title:'Workout',sub:'High-energy training picks',art:11},
    {id:'chill',title:'Chill',sub:'Soft-focus listening',art:0},
    {id:'focus',title:'Focus',sub:'Low-distraction listening',art:1},
    {id:'dance',title:'Dance',sub:'Dance-floor releases',art:2},
    {id:'indie',title:'Indie',sub:'Independent sound and songwriters',art:3},
    {id:'rock',title:'Rock',sub:'Guitar-led discoveries',art:4},
    {id:'rnb',title:'R&B',sub:'Rhythm, soul and contemporary R&B',art:5},
    {id:'latin',title:'Latin',sub:'Latin pop and rhythm',art:6},
    {id:'country',title:'Country',sub:'Country songs and stories',art:7},
    {id:'jazz',title:'Jazz',sub:'Jazz standards and new voices',art:8},
    {id:'metal',title:'Metal',sub:'Heavy riffs and metal releases',art:9},
    {id:'acoustic',title:'Acoustic',sub:'Unplugged and singer-songwriter music',art:10},
    {id:'devotional',title:'Devotional',sub:'Devotional and spiritual music',art:11},
    {id:'punjabi',title:'Punjabi',sub:'Punjabi pop and folk releases',art:0},
    {id:'electronic',title:'Electronic',sub:'Electronic and club discoveries',art:1},
    {id:'throwbacks',title:'Throwbacks',sub:'Classic songs from across eras',art:2}
  ];
  var defaultCharts = ['top50','week','pop','hindi','hiphop','chill'];
  var preferences = defaultCharts.slice();
  var draft = null;
  var customizing = false;
  var regions = [['IN','India'],['US','United States'],['GB','United Kingdom'],['CA','Canada'],['AU','Australia'],['JP','Japan'],['KR','South Korea'],['BR','Brazil'],['MX','Mexico'],['NG','Nigeria'],['ZA','South Africa'],['FR','France'],['DE','Germany'],['ES','Spain'],['ID','Indonesia'],['PH','Philippines'],['AE','United Arab Emirates']];

  var style = document.createElement('link');
  style.rel = 'stylesheet'; style.href = '/static/viora-v157.css'; document.head.appendChild(style);

  function chooseChartSettings(settings) {
    var next = settings && Array.isArray(settings.chart_preferences) ? settings.chart_preferences : defaultCharts;
    next = next.filter(function (id, index) { return charts.some(function (item) { return item.id === id; }) && next.indexOf(id) === index; }).slice(0, 12);
    preferences = next.length >= 3 ? next : defaultCharts.slice();
  }

  function chartPicker() {
    if (!Array.isArray(draft)) draft = preferences.slice();
    return '<div class="chart-picker"><div class="chart-picker-head"><div><b>Choose your chart cards</b><small>Pick 3–12. Chart feeds update daily; genre cards are discovery mixes.</small></div><button class="primary-action" onclick="v157SaveChartPreferences()">Save choices</button></div><div class="chart-option-grid">' + charts.map(function (item) {
      return '<label class="chart-option"><input type="checkbox" value="' + item.id + '" ' + (draft.indexOf(item.id) >= 0 ? 'checked' : '') + ' onchange="v157ToggleChartPreference(\'' + item.id + '\',this.checked)"><span>' + esc(item.title) + '</span></label>';
    }).join('') + '</div><small id="chartPreferenceCount">' + draft.length + ' selected · maximum 12</small></div>';
  }

  function chartCards(region, selected) {
    var visible = charts.filter(function (item) { return preferences.indexOf(item.id) >= 0; }).slice(0, 12);
    var bar = '<div class="chart-customize-bar"><span>' + visible.length + ' of 12 chart cards · ' + charts.length + ' options</span><button class="text-button" onclick="v157ToggleChartCustomize()">' + (customizing ? 'Close' : 'Customize charts') + '</button></div>';
    var picker = customizing ? chartPicker() : '';
    var cardsHtml = visible.map(function (item) {
      var label = item.id === 'top50' ? ((regions.find(function (entry) { return entry[0] === region; }) || [region, region])[1] + ' Top 50') : item.title;
      return '<button class="chart-card chart-art-' + item.art + ' ' + (selected === item.id ? 'selected' : '') + '" onclick="loadCharts(\'' + region + '\',\'' + item.id + '\')" aria-label="Open ' + esc(label) + '"><span class="chart-card-kicker">VIORA CHARTS</span><b>' + esc(label) + '</b><small>' + esc(item.sub) + '</small><span class="chart-card-arrow">↗</span></button>';
    }).join('');
    return bar + picker + '<div class="chart-card-grid">' + cardsHtml + '</div>';
  }

  window.v157ToggleChartCustomize = function () {
    customizing = !customizing; draft = preferences.slice();
    loadCharts(state.chartRegion || 'IN', state.chartCategory || preferences[0] || 'top50');
  };
  window.v157ToggleChartPreference = function (id, checked) {
    if (!Array.isArray(draft)) draft = preferences.slice();
    if (checked && draft.length >= 12) {
      toast('Choose up to 12 charts.');
      Array.from(document.querySelectorAll('.chart-option input')).forEach(function (input) { if (input.value === id) input.checked = false; });
      return;
    }
    draft = checked ? draft.concat([id]) : draft.filter(function (value) { return value !== id; });
    var count = $('chartPreferenceCount'); if (count) count.textContent = draft.length + ' selected · maximum 12';
  };
  window.v157SaveChartPreferences = async function () {
    if (!Array.isArray(draft) || draft.length < 3) return toast('Choose at least 3 charts.');
    var saved = await api('/api/settings', 'POST', {chart_preferences:draft});
    if (!saved || !Array.isArray(saved.chart_preferences)) return;
    chooseChartSettings(saved); draft = preferences.slice(); customizing = false;
    toast('Your chart shelf is saved.');
    loadCharts(state.chartRegion || 'IN', preferences.indexOf(state.chartCategory) >= 0 ? state.chartCategory : preferences[0]);
  };

  window.loadCharts = async function (region, selected, forceRefresh) {
    region = region || 'IN'; selected = selected || preferences[0] || 'top50'; forceRefresh = !!forceRefresh;
    if (!preferences.length) preferences = defaultCharts.slice();
    if (!charts.some(function (item) { return item.id === selected; }) || preferences.indexOf(selected) < 0) selected = preferences[0];
    state.chartRegion = region; state.chartCategory = selected; state.chartLastLoaded = Date.now();
    var page = $('page-charts'); if (!page) return;
    var regionName = (regions.find(function (item) { return item[0] === region; }) || [region, region])[1];
    var regionOptions = regions.map(function (item) { return '<option value="' + item[0] + '" ' + (item[0] === region ? 'selected' : '') + '>' + esc(item[1]) + '</option>'; }).join('');
    var controls = '<div class="chart-controls"><label for="chartRegion">Region</label><select id="chartRegion" class="sort-select" onchange="loadCharts(this.value,state.chartCategory)">' + regionOptions + '</select><button class="icon-btn" onclick="loadCharts($(\'chartRegion\').value,state.chartCategory,true)" title="Refresh from chart source" aria-label="Refresh charts">↻</button></div>';
    var selectedItem = charts.find(function (item) { return item.id === selected; }) || charts[0];
    page.innerHTML = '<h1 class="page-title">Charts</h1><p class="page-sub">Regional charts refresh daily. Genre and mood cards are Viora search mixes, not third-party rankings.</p>' + controls + chartCards(region, selected) + '<div id="chartResults"><div class="empty">Finding ' + esc(selectedItem.title) + '…</div></div>';
    var isMix = selected !== 'top50' && selected !== 'week';
    var data, rows = [], source = '', offline = false;
    if (isMix) {
      data = await api('/api/chart-mix?category=' + encodeURIComponent(selected) + '&region=' + encodeURIComponent(region));
      if (!data) return;
      rows = data.results || []; source = data.source || 'Viora discovery mix'; offline = !!data.offline;
      data.updated_at = new Date().toISOString().slice(0, 10);
    } else {
      data = await api('/api/charts?region=' + encodeURIComponent(region) + '&limit=100' + (forceRefresh ? '&refresh=1' : ''));
      if (!data) return;
      if (data.error) { $('chartResults').innerHTML = '<div class="empty">' + esc(data.error) + '</div>'; return; }
      rows = (data.results || []).slice(0, selected === 'week' ? 20 : 50); source = 'Apple Music · regional most-played feed'; offline = !!data.offline;
    }
    var title = selected === 'top50' ? regionName + ' Top 50' : selected === 'week' ? 'Popular this week' : selectedItem.title;
    var note = selected === 'week' ? 'Current Apple Music most-played list · the source does not publish weekly play-count totals.' : isMix ? 'Viora ranks likely official and artist-managed sources first, followed by community uploads.' : regionName + ' regional songs, ranked by Apple Music.';
    var list = isMix ? rows.map(function (item, index) { return card(item, index); }).join('') : (window.v156AppleChartRows ? v156AppleChartRows(rows) : '');
    var sourceLink = !isMix && data.source_url ? '<a href="' + esc(data.source_url) + '" target="_blank" rel="noopener noreferrer">View Apple chart ↗</a>' : '';
    var empty = offline && !rows.length ? '<div class="empty">You are offline and no saved chart snapshot is available. Your downloaded library is still available in Offline.</div>' : !rows.length ? '<div class="empty">No songs are available in this section right now.</div>' : '';
    $('chartResults').innerHTML = '<div class="chart-results-head"><div><h2>' + esc(title) + '</h2><p>' + esc(note) + '</p></div>' + (isMix ? '<span class="source-pill">Viora mix</span>' : '') + '</div><div class="panel chart-attribution"><span>' + esc(source) + ' · ' + esc(data.updated_at ? 'Feed date: ' + data.updated_at : 'Source refreshes daily') + (data.stale ? ' · showing cached data' : '') + '</span>' + sourceLink + '</div>' + (rows.length ? '<div class="' + (isMix ? 'cards chart-mix-cards' : 'chart-list') + '">' + list + '</div>' : empty);
  };

  var baseQueueRenderer = renderQueue;
  window.renderQueue = function (tracks) {
    tracks = Array.isArray(tracks) ? tracks : [];
    var sidebar = $('sideQueue');
    if (sidebar) sidebar.innerHTML = tracks.length ? tracks.map(function (track, index) {
      return '<div class="queue-item"><span class="queue-num">' + (index + 1) + '</span><img src="' + esc(track.thumbnail || '') + '" alt=""><div class="queue-main" onclick="queuePlayIndex(' + index + ')"><b>' + esc(track.title || 'Unknown') + '</b><span>' + esc(track.artist || track.channel || '') + '</span></div><button class="icon-btn queue-remove" onclick="removeQueueItem(' + index + ')" aria-label="Remove ' + esc(track.title || 'track') + ' from queue">×</button></div>';
    }).join('') : '<div class="queue-empty-mini">Nothing queued yet. Add songs from Search, Discover, or a playlist.</div>';
    if (state.page !== 'queue') return;
    var page = $('page-queue'); if (!page) return;
    var status = state.lastStatus || {}, current = status.current_track;
    var controls = '<div class="queue-tools"><button class="icon-btn" onclick="shuffleQueue()" ' + (!tracks.length ? 'disabled' : '') + ' aria-label="Shuffle queue" title="Shuffle queue">⤨</button><button class="icon-btn" onclick="saveQueue()" ' + (!tracks.length && !current ? 'disabled' : '') + ' aria-label="Save queue as playlist" title="Save queue">▣</button><button class="icon-btn" onclick="clearQueue()" ' + (!tracks.length ? 'disabled' : '') + ' aria-label="Clear queue" title="Clear queue">×</button></div>';
    var currentHtml = current ? '<article class="queue-now"><img src="' + esc(current.thumbnail || status.thumbnail || '/static/favicon.svg') + '" alt=""><div><span>NOW PLAYING</span><b>' + esc(current.title || status.now_playing || 'Unknown') + '</b><small>' + esc(current.artist || current.channel || '') + '</small></div><div class="queue-now-controls"><button class="icon-btn" onclick="previousTrack()" aria-label="Previous">‹</button><button class="icon-btn" onclick="togglePause()" aria-label="Play or pause">' + (status.playing && !status.paused ? 'Ⅱ' : '▶') + '</button><button class="icon-btn" onclick="nextTrack()" aria-label="Next">›</button><button class="icon-btn" onclick="saveCurrentToPlaylist()" aria-label="Save current track to playlist">▣</button></div></article>' : '<article class="queue-now queue-now-idle"><div class="queue-note-mark">♫</div><div><span>READY WHEN YOU ARE</span><b>Your queue starts here</b><small>Choose a track and it will appear here while you listen.</small></div><button class="primary-action" onclick="setPage(\'search\');$(\'searchInput\').focus()">Find music</button></article>';
    var upcoming = tracks.length ? '<div class="list queue-track-list">' + tracks.map(function (track, index) {
      var safeTrack = esc(JSON.stringify(track));
      return '<div class="row" data-track="' + safeTrack + '"><span class="queue-page-number">' + (index + 1) + '</span><img src="' + esc(track.thumbnail || '') + '" alt=""><div class="row-main"><b>' + esc(track.title || 'Unknown') + '</b><span>' + esc(track.artist || track.channel || '') + '</span></div><div class="row-actions"><button class="icon-btn" onclick="queuePlayIndex(' + index + ')" title="Play now" aria-label="Play ' + esc(track.title || 'track') + '">▶</button><button class="icon-btn" onclick="openPlaylistForRow(this)" title="Save to playlist" aria-label="Save ' + esc(track.title || 'track') + ' to playlist">▣</button><button class="icon-btn" onclick="removeQueueItem(' + index + ')" title="Remove from queue" aria-label="Remove ' + esc(track.title || 'track') + ' from queue">×</button></div></div>';
    }).join('') + '</div>' : '<div class="empty queue-empty">Your next songs will show here. Add tracks from <button class="text-button" onclick="setPage(\'discover\')">Discover</button> or <button class="text-button" onclick="setPage(\'search\');$(\'searchInput\').focus()">Search</button>, or start a playlist from <button class="text-button" onclick="setPage(\'playlists\')">Playlists</button>.</div>';
    page.innerHTML = '<div class="section-head queue-page-head"><div><h1 class="page-title">Queue</h1><p class="page-sub">' + tracks.length + ' upcoming ' + (tracks.length === 1 ? 'track' : 'tracks') + ' · changes appear as you play, add, or remove songs.</p></div>' + controls + '</div>' + currentHtml + '<div class="section queue-upcoming"><div class="section-head"><h2>Up next</h2><span>' + tracks.length + ' ' + (tracks.length === 1 ? 'song' : 'songs') + '</span></div>' + upcoming + '</div>';
  };
  window.removeQueueItem = async function (index) { var result = await api('/api/queue/' + index, 'DELETE'); if (result && result.status) renderStatus(result.status); };
  if (typeof baseQueueRenderer !== 'function') console.warn('Queue renderer not found at startup.');

  var oldLoadSettings = loadSettings;
  window.loadSettings = async function () { await oldLoadSettings();
    var panel = $('keyboardHelp');
    if (!panel) { panel = document.createElement('div'); panel.id = 'keyboardHelp'; panel.className = 'panel keyboard-help'; panel.innerHTML = '<h3>Keyboard shortcuts</h3><p><kbd>Space</kbd> play or pause · <kbd>←</kbd> previous track · <kbd>→</kbd> next track. Shortcuts pause while you type in a field.</p>'; $('page-settings').appendChild(panel); }
    var privacyPanel = $('page-settings').querySelector('.panel:has(.backup-label)');
    if (privacyPanel) { var actions=privacyPanel.querySelector('.row-actions'); if(actions) actions.classList.add('backup-actions'); }
  };

  function workStatus(label) {
    var element = document.createElement('div'); element.className = 'viora-work-status'; element.setAttribute('role', 'status'); element.setAttribute('aria-live', 'polite');
    element.innerHTML = '<span class="viora-work-dot"></span><span>' + esc(label) + '</span><i></i>'; document.body.appendChild(element);
    return function () { element.classList.add('leaving'); setTimeout(function () { element.remove(); }, 180); };
  }
  var oldSearch = doSearch;
  window.doSearch = async function (query) { var done=workStatus('Finding songs and checking your library…'); try { return await oldSearch(query); } finally { done(); } };
  var oldPlayPayload = playPayload;
  window.playPayload = async function (track) { var done=workStatus('Preparing playback…'); try { return await oldPlayPayload(track); } finally { done(); } };

  document.addEventListener('keydown', function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.repeat) return;
    var active = document.activeElement;
    if (active && (active.matches('input,textarea,select,button,[contenteditable="true"]') || active.isContentEditable)) return;
    if (event.code === 'Space') { event.preventDefault(); if (state.lastStatus && state.lastStatus.current_track) togglePause(); }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); previousTrack(); }
    else if (event.key === 'ArrowRight') { event.preventDefault(); nextTrack(); }
  });

  var currentLoader = window.loadCharts;
  if (typeof currentLoader !== 'function') console.warn('Chart renderer could not be initialized.');
  api('/api/settings').then(function (settings) { if (settings) chooseChartSettings(settings); });
})();
