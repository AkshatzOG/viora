/* Viora saved service playlists, transparent charts, and live sound response. */
(function () {
  'use strict';

  var chartOptions = [
    {id:'top50',title:'Apple Music Top 50',sub:'Official regional chart · daily feed',source:'official',kind:'apple',art:0},
    {id:'top100',title:'Apple Music Top 100',sub:'Official regional chart · daily feed',source:'official',kind:'apple100',art:1},
    {id:'week',title:'YouTube Music Weekly Top Songs',sub:'Official weekly songs chart',source:'official',kind:'external',url:'https://charts.youtube.com/charts/TopSongs/global/weekly',art:2},
    {id:'ytdaily',title:'YouTube Music Daily Videos',sub:'Official daily music videos chart',source:'official',kind:'external',url:'https://charts.youtube.com/charts/TopMusicVideos/global/daily',art:3},
    {id:'spotifycharts',title:'Spotify Charts',sub:'Official charts · sign-in may be required',source:'official',kind:'external',url:'https://charts.spotify.com/charts/overview/global',art:4},
    {id:'viora_top',title:'Your most played',sub:'From listening on this device',source:'viora',kind:'local',localKind:'most-played',art:5},
    {id:'viora_favorites',title:'Your favorites',sub:'Your saved Viora favorites',source:'viora',kind:'local',localKind:'favorites',art:6},
    {id:'love',title:'Love',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:7},
    {id:'pop',title:'Pop',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:8},
    {id:'english',title:'English',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:9},
    {id:'hindi',title:'Hindi',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:10},
    {id:'phonk',title:'Phonk',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:11},
    {id:'hiphop',title:'Hip-hop',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:0},
    {id:'afrobeats',title:'Afrobeats',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:1},
    {id:'kpop',title:'K-pop',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:2},
    {id:'jpop',title:'J-pop',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:3},
    {id:'workout',title:'Workout',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:4},
    {id:'chill',title:'Chill',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:5},
    {id:'focus',title:'Focus',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:6},
    {id:'dance',title:'Dance',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:7},
    {id:'indie',title:'Indie',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:8},
    {id:'rock',title:'Rock',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:9},
    {id:'rnb',title:'R&B',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:10},
    {id:'latin',title:'Latin',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:11},
    {id:'country',title:'Country',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:0},
    {id:'jazz',title:'Jazz',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:1},
    {id:'metal',title:'Metal',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:2},
    {id:'acoustic',title:'Acoustic',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:3},
    {id:'devotional',title:'Devotional',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:4},
    {id:'punjabi',title:'Punjabi',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:5},
    {id:'electronic',title:'Electronic',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:6},
    {id:'throwbacks',title:'Throwbacks',sub:'Viora discovery mix · not a measured ranking',source:'viora',kind:'mix',art:7}
  ];
  var defaultCharts = ['top50','week','ytdaily','viora_top','pop','hindi'];
  var chartPreferences = defaultCharts.slice();
  var chartDraft = null;
  var chartCustomizeOpen = false;
  var regions = [['IN','India'],['US','United States'],['GB','United Kingdom'],['CA','Canada'],['AU','Australia'],['JP','Japan'],['KR','South Korea'],['BR','Brazil'],['MX','Mexico'],['NG','Nigeria'],['ZA','South Africa'],['FR','France'],['DE','Germany'],['ES','Spain'],['ID','Indonesia'],['PH','Philippines'],['AE','United Arab Emirates']];

  var style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = '/static/viora-v158.css';
  document.head.appendChild(style);

  var savedExternalPlaylists = [];
  var activeExternalPlayback = null;
  var spotifyApiPromise = null;
  var youtubeApiPromise = null;
  var latestVioraStatus = null;

  function providerIcon(provider) {
    var name = String(provider || '').toLowerCase();
    if (name.indexOf('spotify') >= 0) return '<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="23" fill="#1ed760"/><path d="M11 18c9-3 20-2 27 2M13 24c8-2 17-1 23 2M15 30c6-1 13 0 18 3" fill="none" stroke="#102b18" stroke-width="3" stroke-linecap="round"/></svg>';
    if (name.indexOf('apple') >= 0) return '<svg viewBox="0 0 48 48"><defs><linearGradient id="v158Apple" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ff5a72"/><stop offset="1" stop-color="#a832df"/></linearGradient></defs><rect width="48" height="48" rx="13" fill="url(#v158Apple)"/><path d="M28 10v22.5a6.5 6.5 0 1 1-3-5.5V17l13-3v15.5a6.5 6.5 0 1 1-3-5.5V10z" fill="#fff"/></svg>';
    if (name.indexOf('youtube') >= 0) return '<svg viewBox="0 0 48 48"><rect x="2" y="7" width="44" height="34" rx="11" fill="#ff0033"/><path d="m20 16 13 8-13 8z" fill="#fff"/></svg>';
    if (name.indexOf('amazon') >= 0) return '<svg viewBox="0 0 48 48"><rect width="48" height="48" rx="13" fill="#151b28"/><text x="9" y="32" fill="#fff" font-family="Arial,sans-serif" font-size="25" font-weight="700">a</text><path d="M13 36c8 4 17 4 24-1m0 0-5-1m5 1-1 5" fill="none" stroke="#ffad42" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    if (name.indexOf('tidal') >= 0) return '<svg viewBox="0 0 48 48"><rect width="48" height="48" rx="13" fill="#111"/><g fill="#fff"><path d="m13 15 4 4-4 4-4-4zm11 0 4 4-4 4-4-4zm11 0 4 4-4 4-4-4zM24 26l4 4-4 4-4-4z"/></g></svg>';
    if (name.indexOf('deezer') >= 0) return '<svg viewBox="0 0 48 48"><rect width="48" height="48" rx="13" fill="#17141f"/><path fill="#a238ff" d="M8 25h7v11H8z"/><path fill="#ff4b72" d="M17 20h7v16h-7z"/><path fill="#ffb23d" d="M26 15h7v21h-7z"/><path fill="#21d8a2" d="M35 10h6v26h-6z"/></svg>';
    if (name.indexOf('soundcloud') >= 0) return '<svg viewBox="0 0 48 48"><rect width="48" height="48" rx="13" fill="#ff681f"/><path d="M10 25h2v9h-2zm4-4h2v13h-2zm4-4h2v17h-2zm4-2a10 10 0 0 1 19 6 6 6 0 0 1-1 12H23z" fill="#fff"/></svg>';
    return '<svg viewBox="0 0 48 48"><rect width="48" height="48" rx="13" fill="#7959e8"/><path d="M29 9v21a7 7 0 1 1-4-6.3V16l14-3v17a7 7 0 1 1-4-6.3V9z" fill="#fff"/></svg>';
  }

  function providerIconData(provider) {
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(providerIcon(provider));
  }

  function setChartPreferences(settings) {
    var incoming = settings && Array.isArray(settings.chart_preferences) ? settings.chart_preferences : defaultCharts;
    incoming = incoming.filter(function (id, index) { return chartOptions.some(function (entry) { return entry.id === id; }) && incoming.indexOf(id) === index; }).slice(0, 12);
    chartPreferences = incoming.length >= 3 ? incoming : defaultCharts.slice();
  }

  function renderChartPicker() {
    if (!Array.isArray(chartDraft)) chartDraft = chartPreferences.slice();
    return '<div class="chart-picker v158-chart-picker"><div class="chart-picker-head"><div><b>Choose your chart cards</b><small>Show 3–12 official charts, Viora listening charts, and discovery mixes.</small></div><button class="primary-action" onclick="v158SaveChartPreferences()">Save choices</button></div><div class="chart-option-grid">' + chartOptions.map(function (entry) {
      return '<label class="chart-option"><input type="checkbox" value="' + entry.id + '" ' + (chartDraft.indexOf(entry.id) >= 0 ? 'checked' : '') + ' onchange="v158ToggleChartPreference(\'' + entry.id + '\',this.checked)"><span>' + esc(entry.title) + '</span></label>';
    }).join('') + '</div><small id="chartPreferenceCount">' + chartDraft.length + ' selected · maximum 12</small></div>';
  }

  function renderChartCards(region, selected) {
    var visible = chartOptions.filter(function (entry) { return chartPreferences.indexOf(entry.id) >= 0; }).slice(0, 12);
    var bar = '<div class="chart-customize-bar"><span>' + visible.length + ' of 12 cards · ' + chartOptions.length + ' choices</span><button class="text-button" onclick="v158ToggleChartCustomize()">' + (chartCustomizeOpen ? 'Close' : 'Customize charts') + '</button></div>';
    var cards = visible.map(function (entry) {
      var kicker = entry.source === 'official' ? 'OFFICIAL CHART' : entry.kind === 'mix' ? 'VIORA DISCOVERY' : 'YOUR VIORA CHART';
      var title = entry.id === 'top50' ? ((regions.find(function (row) { return row[0] === region; }) || [region, region])[1] + ' Top 50') : entry.id === 'top100' ? ((regions.find(function (row) { return row[0] === region; }) || [region, region])[1] + ' Top 100') : entry.title;
      return '<button class="chart-card chart-art-' + entry.art + ' v158-chart-card ' + (selected === entry.id ? 'selected' : '') + ' v158-chart-' + entry.source + '" onclick="loadCharts(\'' + region + '\',\'' + entry.id + '\')" aria-label="Open ' + esc(title) + '"><span class="chart-card-kicker">' + kicker + '</span><b>' + esc(title) + '</b><small>' + esc(entry.sub) + '</small><span class="chart-card-arrow">↗</span></button>';
    }).join('');
    return bar + (chartCustomizeOpen ? renderChartPicker() : '') + '<div class="chart-card-grid">' + cards + '</div>';
  }

  window.v158ToggleChartCustomize = function () {
    chartCustomizeOpen = !chartCustomizeOpen;
    chartDraft = chartPreferences.slice();
    loadCharts(state.chartRegion || 'IN', state.chartCategory || chartPreferences[0]);
  };
  window.v158ToggleChartPreference = function (id, checked) {
    if (!Array.isArray(chartDraft)) chartDraft = chartPreferences.slice();
    if (checked && chartDraft.length >= 12) { toast('Choose up to 12 charts.'); loadCharts(state.chartRegion || 'IN', state.chartCategory); return; }
    chartDraft = chartDraft.filter(function (item) { return item !== id; });
    if (checked) chartDraft.push(id);
    var count = $('chartPreferenceCount'); if (count) count.textContent = chartDraft.length + ' selected · maximum 12';
  };
  window.v158SaveChartPreferences = async function () {
    if (!Array.isArray(chartDraft) || chartDraft.length < 3) return toast('Choose at least 3 charts.');
    var result = await api('/api/settings', 'POST', {chart_preferences:chartDraft});
    if (!result || !Array.isArray(result.chart_preferences)) return;
    setChartPreferences(result);
    chartDraft = chartPreferences.slice();
    chartCustomizeOpen = false;
    toast('Your chart cards are saved.');
    loadCharts(state.chartRegion || 'IN', chartPreferences[0]);
  };

  function officialChartPanel(entry, regionName) {
    var description = entry.id === 'week'
      ? 'This chart is maintained by YouTube Music and opens at the official chart source.'
      : entry.id === 'ytdaily'
        ? 'Daily official music-video rankings from YouTube Charts.'
        : 'Spotify publishes global, genre, and city charts. The official site may ask you to sign in.';
    return '<div class="official-chart-panel"><div class="official-chart-mark">' + (entry.id === 'spotifycharts' ? 'S' : '♪') + '</div><div><span>OFFICIAL SOURCE</span><h2>' + esc(entry.title) + '</h2><p>' + esc(description) + '</p><a class="primary-action" href="' + esc(entry.url) + '" target="_blank" rel="noopener noreferrer">Open official chart ↗</a></div></div><div class="panel chart-attribution"><span>Chart rankings and update schedule are provided by the service.</span><span>' + esc(regionName) + ' selection applies to Apple Music charts.</span></div>';
  }

  window.loadCharts = async function (region, selected, forceRefresh) {
    region = region || 'IN';
    selected = selected || chartPreferences[0] || 'top50';
    if (!chartOptions.some(function (entry) { return entry.id === selected; })) selected = chartPreferences[0] || 'top50';
    state.chartRegion = region;
    state.chartCategory = selected;
    var page = $('page-charts');
    if (!page) return;
    var entry = chartOptions.find(function (item) { return item.id === selected; }) || chartOptions[0];
    var regionName = (regions.find(function (row) { return row[0] === region; }) || [region, region])[1];
    var regionOptions = regions.map(function (row) { return '<option value="' + row[0] + '" ' + (row[0] === region ? 'selected' : '') + '>' + esc(row[1]) + '</option>'; }).join('');
    var controls = '<div class="chart-controls"><label for="chartRegion">Region</label><select id="chartRegion" class="sort-select" onchange="loadCharts(this.value,state.chartCategory)">' + regionOptions + '</select><button class="icon-btn" onclick="loadCharts($(\'chartRegion\').value,state.chartCategory,true)" title="Refresh official feed" aria-label="Refresh charts">↻</button></div>';
    page.innerHTML = '<h1 class="page-title">Charts</h1><p class="page-sub">Official chart sources first. Viora’s listening charts use only this device’s play history; discovery mixes are clearly labeled.</p>' + controls + renderChartCards(region, selected) + '<div id="chartResults"><div class="empty">Loading ' + esc(entry.title) + '…</div></div>';
    var results = $('chartResults');
    if (entry.kind === 'external') { results.innerHTML = officialChartPanel(entry, regionName); return; }
    var data, rows = [], source = '';
    if (entry.kind === 'apple' || entry.kind === 'apple100') {
      data = await api('/api/charts?region=' + encodeURIComponent(region) + '&limit=100' + (forceRefresh ? '&refresh=1' : ''));
      if (!data) return;
      if (data.error) { results.innerHTML = '<div class="empty">' + esc(data.error) + '</div>'; return; }
      rows = (data.results || []).slice(0, entry.kind === 'apple' ? 50 : 100);
      source = 'Apple Music · official regional most-played feed';
    } else if (entry.kind === 'local') {
      data = await api('/api/charts/viora?kind=' + encodeURIComponent(entry.localKind));
      if (!data) return;
      rows = data.results || [];
      source = data.source || 'Viora · this device only';
    } else {
      data = await api('/api/chart-mix?category=' + encodeURIComponent(entry.id) + '&region=' + encodeURIComponent(region));
      if (!data) return;
      rows = data.results || [];
      source = data.source || 'Viora discovery mix';
    }
    var heading = entry.id === 'top50' ? regionName + ' Top 50' : entry.id === 'top100' ? regionName + ' Top 100' : entry.title;
    var note = entry.kind === 'apple' || entry.kind === 'apple100' ? 'Ranked by Apple Music in this region. The official feed refreshes daily.' : entry.kind === 'local' ? 'Calculated from this device’s Viora play counts and favorites. Nothing is uploaded or combined with other listeners.' : 'A Viora search mix, ordered by query relevance and likely official-source signals. It is not a measured platform chart.';
    var list = entry.kind === 'apple' || entry.kind === 'apple100'
      ? (window.v156AppleChartRows ? v156AppleChartRows(rows) : '')
      : rows.map(function (item, index) { return card(item, index); }).join('');
    var refreshed = data.updated_at ? 'Updated ' + data.updated_at : 'Refreshed from source';
    var sourceLink = data.source_url ? '<a href="' + esc(data.source_url) + '" target="_blank" rel="noopener noreferrer">View Apple Music chart ↗</a>' : '';
    var empty = data.offline && !rows.length ? '<div class="empty">You are offline and this chart has no saved snapshot yet.</div>' : !rows.length ? '<div class="empty">No tracks are available here yet. Listen on this device to build a personal Viora chart.</div>' : '';
    results.innerHTML = '<div class="chart-results-head"><div><h2>' + esc(heading) + '</h2><p>' + esc(note) + '</p></div><span class="source-pill">' + esc(entry.source === 'official' ? 'Official chart' : entry.kind === 'local' ? 'On this device' : 'Viora mix') + '</span></div><div class="panel chart-attribution"><span>' + esc(source + ' · ' + refreshed + (data.stale ? ' · cached snapshot' : '')) + '</span>' + sourceLink + '</div>' + (rows.length ? '<div class="' + (entry.kind === 'apple' || entry.kind === 'apple100' ? 'chart-list' : 'cards chart-mix-cards') + '">' + list + '</div>' : empty);
  };

  function externalPlaylistPanelMarkup() {
    return '<section class="panel v158-saved-playlists-panel"><div class="v158-panel-heading"><div><span class="v158-eyebrow">YOUR COLLECTION</span><h2>Saved service playlists</h2><p>Keep links from Spotify, Apple Music, YouTube Music, Amazon Music, Tidal, Deezer, and SoundCloud together here.</p></div><span class="v158-link-count" id="externalPlaylistCount">Loading…</span></div><div class="v158-save-link-form"><input id="externalPlaylistName" class="storage-path" maxlength="120" placeholder="Give this playlist a name (optional)" aria-label="Saved playlist name"><textarea id="externalPlaylistSource" class="playlist-source-input" rows="3" placeholder="Paste a playlist link or iframe embed code…" aria-label="Playlist URL or embed code"></textarea><div class="v158-form-actions"><button type="button" class="primary-action" onclick="v158PreviewExternalPlaylist()">Preview link</button><button type="button" class="primary-action" onclick="v158SaveExternalPlaylist()">Save to my collection</button></div><div id="externalPlaylistPreview"></div></div><div id="externalPlaylistList" class="v158-external-playlist-list"><div class="empty">Loading your saved playlist links…</div></div><small class="v158-service-note">Viora saves and previews provider links. It does not access private accounts or copy playlist contents; use the provider player or open the original service.</small></section>';
  }

  function importPanelMarkup() {
    return '<section class="panel import-panel v158-track-import-panel"><h3>Build a Viora playlist from a track list</h3><p>Import song names from a file or paste them below. Viora finds playable matches and shows progress while you keep listening.</p><input id="playlistImportName" class="storage-path" placeholder="Playlist name (optional)" aria-label="Imported playlist name"><form onsubmit="event.preventDefault();startPlaylistImport()"><div class="import-actions"><input id="playlistImportFile" type="file" accept=".csv,.m3u,.m3u8,.json,.txt" required><button class="primary-action">Import file</button></div></form><label class="import-label" for="playlistTracklist">Or paste copied song names · one per line</label><textarea id="playlistTracklist" class="playlist-source-input" rows="4" placeholder="Artist - Song title&#10;Another artist - Another song" aria-label="Track names for playlist import"></textarea><button type="button" class="primary-action" onclick="startPastedPlaylistImport()">Build playlist from pasted tracks</button><div id="playlistImportProgress"></div></section>';
  }

  async function renderExternalPlaylistList(playlists) {
    var box = $('externalPlaylistList'); if (!box) return;
    if (!Array.isArray(playlists)) {
      var data = await api('/api/external-playlists');
      if (!data || !Array.isArray(data.playlists)) {
        var failedCount = $('externalPlaylistCount'); if (failedCount) failedCount.textContent = 'Unavailable';
        box.innerHTML = '<div class="empty">Saved playlists could not be loaded. <button class="text-button" onclick="loadPlaylists()">Try again</button></div>';
        return;
      }
      playlists = data.playlists;
    }
    var items = playlists;
    savedExternalPlaylists = items.slice();
    var count = $('externalPlaylistCount'); if (count) count.textContent = items.length + (items.length === 1 ? ' saved' : ' saved');
    box.innerHTML = items.length ? items.map(function (item) {
      var preview = '<button class="v158-fullscreen-link" onclick="v158OpenExternalFullscreen(\'' + esc(item.id) + '\')">Open playlist full screen ⤢</button>' + (item.embed_supported && item.embed_url ? '' : '<p class="v158-no-embed">This service opens in its own app or website.</p>');
      return '<article class="v158-external-playlist"><div class="v158-service-icon" aria-label="' + esc(item.provider || 'Music service') + ' logo">' + providerIcon(item.provider) + '</div><div class="v158-external-main"><span class="v158-provider-name">' + esc(item.provider || 'Music service') + '</span><h3>' + esc(item.name || 'Saved playlist') + '</h3><a class="v158-open-link" href="' + esc(item.open_url || item.source_url) + '" target="_blank" rel="noopener noreferrer">Open in ' + esc(item.provider || 'service') + ' ↗</a>' + preview + '</div><div class="v158-row-actions"><button class="icon-btn" onclick="v158EditExternalPlaylist(\'' + esc(item.id) + '\')" aria-label="Edit ' + esc(item.name || 'playlist') + '" title="Edit">✎</button><button class="icon-btn" onclick="v158DeleteExternalPlaylist(\'' + esc(item.id) + '\')" aria-label="Delete ' + esc(item.name || 'playlist') + '" title="Delete">×</button></div></article>';
    }).join('') : '<div class="empty">No service playlists saved yet. Add one above to keep it close.</div>';
  }

  window.v158PreviewExternalPlaylist = async function () {
    var source = $('externalPlaylistSource') ? $('externalPlaylistSource').value.trim() : '';
    if (!source) return toast('Paste a playlist link or embed code first.');
    var data = await api('/api/playlist-embed', 'POST', {source:source});
    if (!data) return;
    var box = $('externalPlaylistPreview'); if (!box) return;
    var previewItem = {id:'preview-' + Date.now(), provider:data.provider, name:data.default_name || (data.provider + ' playlist'), source_url:data.open_url, open_url:data.open_url, embed_url:data.embed_url, embed_supported:data.embed_supported};
    if (data.embed_supported) savedExternalPlaylists.unshift(previewItem);
    box.innerHTML = '<div class="v158-preview-card"><div class="v158-preview-brand">' + providerIcon(data.provider) + '<b>' + esc(data.provider) + ' playlist preview</b></div><p>' + esc(data.message) + '</p>' + (data.embed_supported ? '<button class="v158-fullscreen-link" onclick="v158OpenExternalFullscreen(\'' + esc(previewItem.id) + '\')">Open playlist player ⤢</button>' : '<a class="primary-action" href="' + esc(data.open_url) + '" target="_blank" rel="noopener noreferrer">Open in ' + esc(data.provider) + ' ↗</a>') + '</div>';
  };

  window.v158SaveExternalPlaylist = async function () {
    var source = $('externalPlaylistSource') ? $('externalPlaylistSource').value.trim() : '';
    var name = $('externalPlaylistName') ? $('externalPlaylistName').value.trim() : '';
    if (!source) return toast('Paste a playlist link or embed code first.');
    var data = await api('/api/external-playlists', 'POST', {source:source,name:name});
    if (!data) return;
    toast(data.message || 'Playlist link saved.');
    if ($('externalPlaylistSource')) $('externalPlaylistSource').value = '';
    if ($('externalPlaylistName')) $('externalPlaylistName').value = '';
    if ($('externalPlaylistPreview')) $('externalPlaylistPreview').innerHTML = '';
    await renderExternalPlaylistList(data.playlists);
  };

  window.v158EditExternalPlaylist = async function (id) {
    var data = await api('/api/external-playlists');
    var item = (data && data.playlists || []).find(function (row) { return String(row.id) === String(id); });
    if (!item) return toast('Saved playlist link not found.');
    var name = window.prompt('Edit playlist name', item.name || '');
    if (name === null) return;
    var source = window.prompt('Edit playlist URL or paste its iframe embed', item.source_url || '');
    if (source === null) return;
    var result = await api('/api/external-playlists/' + encodeURIComponent(id), 'PUT', {name:name,source:source});
    if (result) { toast(result.message || 'Saved playlist updated.'); await renderExternalPlaylistList(result.playlists); }
  };

  window.v158DeleteExternalPlaylist = async function (id) {
    var data = await api('/api/external-playlists');
    var item = (data && data.playlists || []).find(function (row) { return String(row.id) === String(id); });
    if (!item || !window.confirm('Remove “' + item.name + '” from your saved service playlists?')) return;
    var result = await api('/api/external-playlists/' + encodeURIComponent(id), 'DELETE');
    if (result) { toast('Playlist link removed.'); await renderExternalPlaylistList(result.playlists); }
  };

  function ensureExternalFullscreen() {
    var overlay = document.getElementById('v158ServiceFullscreen');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'v158ServiceFullscreen';
    overlay.className = 'v158-player-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.addEventListener('click', function (event) { if (event.target === overlay) window.v158CloseExternalFullscreen(); });
    document.body.appendChild(overlay);
    return overlay;
  }

  function loadProviderApi(provider) {
    var spotify = String(provider || '').toLowerCase().indexOf('spotify') >= 0;
    var key = spotify ? 'spotifyApiPromise' : 'youtubeApiPromise';
    if (spotify && window.__vioraSpotifyIframeAPI) return Promise.resolve(window.__vioraSpotifyIframeAPI);
    if (!spotify && window.YT && window.YT.Player) return Promise.resolve(window.YT);
    if (spotifyApiPromise && spotify) return spotifyApiPromise;
    if (youtubeApiPromise && !spotify) return youtubeApiPromise;
    var src = spotify ? 'https://open.spotify.com/embed/iframe-api/v1' : 'https://www.youtube.com/iframe_api';
    var callbackName = spotify ? 'onSpotifyIframeApiReady' : 'onYouTubeIframeAPIReady';
    var callback = spotify ? function (api) { window.__vioraSpotifyIframeAPI = api; } : function () {};
    var promise = new Promise(function (resolve) {
      var settled = false;
      var timeout = window.setTimeout(function () { if (!settled) { settled = true; resolve(null); } }, 12000);
      var previous = window[callbackName];
      window[callbackName] = function (api) {
        try { if (typeof previous === 'function') previous(api); } catch (_) {}
        callback(api);
        if (!settled) { settled = true; window.clearTimeout(timeout); resolve(spotify ? api : window.YT); }
      };
      var script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onerror = function () { if (!settled) { settled = true; window.clearTimeout(timeout); resolve(null); } };
      document.head.appendChild(script);
    });
    if (spotify) spotifyApiPromise = promise; else youtubeApiPromise = promise;
    return promise;
  }

  function paintExternalNowPlaying(status) {
    var active = activeExternalPlayback;
    if (!active) return;
    var nativePlaying = !!(status && status.playing && !status.paused && status.current_track);
    if (nativePlaying && active.state !== 'playing' && active.state !== 'paused') return;
    var item = active.item;
    var title = item.name || 'Saved music playlist';
    var provider = item.provider || 'Music service';
    var icon = providerIconData(provider);
    var label = active.state === 'playing' ? 'Playing · ' + provider : active.state === 'manual-playing' ? 'Marked as playing · ' + provider : active.state === 'paused' ? 'Paused · ' + provider : active.state === 'buffering' ? 'Buffering · ' + provider : 'Playlist player open · ' + provider;
    $('nowPlaceholder')?.classList.add('hidden');
    $('nowArt')?.classList.remove('hidden');
    if ($('nowArt')) $('nowArt').src = icon;
    if ($('bottomArt')) $('bottomArt').src = icon;
    if ($('nowTitle')) { $('nowTitle').textContent = title; $('nowTitle').classList.remove('idle-title'); }
    if ($('bottomTitle')) $('bottomTitle').textContent = title;
    if ($('nowArtist')) $('nowArtist').textContent = provider + ' playlist';
    if ($('bottomArtist')) $('bottomArtist').textContent = provider + ' playlist';
    if ($('bottomMeta')) $('bottomMeta').textContent = label;
    if ($('nowTime')) $('nowTime').textContent = formatTime(active.position || 0);
    if ($('nowDuration')) $('nowDuration').textContent = formatTime(active.duration || 0);
    if ($('nowProgress')) $('nowProgress').style.width = active.duration ? Math.min(100, (active.position / active.duration) * 100) + '%' : '0%';
    var canControl = !!(active.controller || active.youtubePlayer);
    if ($('playBtn')) { $('playBtn').textContent = active.state === 'playing' ? 'Ⅱ' : '▶'; $('playBtn').disabled = !canControl; $('playBtn').title = canControl ? 'Play or pause service playlist' : 'Use the service player controls'; }
    document.querySelectorAll('.now-card .transport button').forEach(function (button) { button.disabled = true; });
    ['currentFavorite', 'currentPlaylist', 'currentQueue', 'stopCurrent'].forEach(function (id) { if ($(id)) $(id).disabled = true; });
    var stateLabel = document.getElementById('v158ServiceState');
    if (stateLabel) stateLabel.textContent = label;
    var manualButton = document.getElementById('v158ManualListening');
    if (manualButton) {
      var hasStateApi = !!(active.controller || active.youtubePlayer);
      manualButton.hidden = hasStateApi;
      manualButton.textContent = active.state === 'manual-playing' ? 'Clear Viora listening status' : 'Mark this playlist as playing';
    }
  }

  function setExternalState(nextState, details) {
    if (!activeExternalPlayback) return;
    activeExternalPlayback.state = nextState;
    details = details || {};
    if (Number.isFinite(Number(details.position))) activeExternalPlayback.position = Number(details.position);
    if (Number.isFinite(Number(details.duration))) activeExternalPlayback.duration = Number(details.duration);
    if (details.track) activeExternalPlayback.track = details.track;
    var current = latestVioraStatus || {};
    if ((nextState === 'playing' || nextState === 'manual-playing') && current.playing && !activeExternalPlayback.stoppingNative) {
      activeExternalPlayback.stoppingNative = true;
      api('/api/stop', 'POST').then(function (response) {
        if (response && response.status) window.refreshStatus?.();
      });
    }
    if (typeof window.renderStatus === 'function') window.renderStatus(current);
  }

  function mountExternalIframe(item) {
    var host = document.getElementById('v158ServiceEmbed');
    if (!host) return;
    host.innerHTML = '<iframe title="' + esc((item.provider || 'Music') + ' playlist: ' + (item.name || 'Saved playlist')) + '" src="' + esc(item.embed_url) + '" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>';
    setExternalState('open');
  }

  async function mountSpotify(item) {
    var apiObject = await loadProviderApi('Spotify');
    if (!activeExternalPlayback || !apiObject) { mountExternalIframe(item); return; }
    var host = document.getElementById('v158ServiceEmbed');
    if (!host) return;
    var source = String(item.source_url || item.embed_url || '').replace('open.spotify.com/embed/', 'open.spotify.com/');
    apiObject.createController(host, {url:source, width:'100%', height:560}, function (controller) {
      if (!activeExternalPlayback) { controller.destroy(); return; }
      activeExternalPlayback.controller = controller;
      controller.addListener('ready', function () { setExternalState('open'); });
      controller.addListener('playback_started', function (event) { setExternalState('playing', {track:event?.data?.playingURI}); });
      controller.addListener('playback_update', function (event) {
        var data = event && event.data || {};
        setExternalState(data.isPaused ? 'paused' : data.isBuffering ? 'buffering' : 'playing', {position:(Number(data.position) || 0) / 1000, duration:(Number(data.duration) || 0) / 1000, track:data.playingURI});
      });
    });
  }

  async function mountYouTube(item) {
    var apiObject = await loadProviderApi('YouTube Music');
    if (!activeExternalPlayback || !apiObject || !apiObject.Player) { mountExternalIframe(item); return; }
    var host = document.getElementById('v158ServiceEmbed');
    var playlistId = '';
    try { playlistId = new URL(item.embed_url).searchParams.get('list') || ''; } catch (_) {}
    if (!host || !playlistId) { mountExternalIframe(item); return; }
    activeExternalPlayback.youtubePlayer = new apiObject.Player(host, {
      width:'100%', height:560,
      playerVars:{listType:'playlist', list:playlistId, playsinline:1, origin:location.origin},
      events:{
        onReady:function () { setExternalState('open'); },
        onStateChange:function (event) {
          var player = event.target;
          var state = event.data === 1 ? 'playing' : event.data === 2 ? 'paused' : event.data === 3 ? 'buffering' : 'open';
          setExternalState(state, {position:player.getCurrentTime ? player.getCurrentTime() : 0, duration:player.getDuration ? player.getDuration() : 0});
        }
      }
    });
  }

  window.v158OpenExternalFullscreen = async function (id) {
    var item = savedExternalPlaylists.find(function (row) { return String(row.id) === String(id); });
    if (!item) {
      var response = await api('/api/external-playlists');
      item = (response && response.playlists || []).find(function (row) { return String(row.id) === String(id); });
    }
    if (!item) return toast('Saved playlist link not found.');
    if (activeExternalPlayback) window.v158CloseExternalFullscreen();
    activeExternalPlayback = {item:item, state:'loading', position:0, duration:0, controller:null, youtubePlayer:null};
    var overlay = ensureExternalFullscreen();
    overlay.innerHTML = '<section class="v158-player-shell"><header class="v158-player-header"><div class="v158-player-brand">' + providerIcon(item.provider) + '<div><span>' + esc(item.provider || 'MUSIC SERVICE') + ' PLAYLIST</span><h2>' + esc(item.name || 'Saved playlist') + '</h2><small id="v158ServiceState">Opening service player…</small></div></div><a href="' + esc(item.open_url || item.source_url || '#') + '" target="_blank" rel="noopener noreferrer">Open original ↗</a><button class="icon-btn" onclick="v158CloseExternalFullscreen()" aria-label="Close full-screen playlist" title="Close">×</button></header><div class="v158-player-embed" id="v158ServiceEmbed"></div><div class="v158-manual-state"><span>Some music services do not share playback state with Viora.</span><button id="v158ManualListening" onclick="v158ToggleManualListening()">Mark this playlist as playing</button></div></section>';
    overlay.classList.add('show');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('v158-service-player-open');
    setExternalState('loading');
    if (!item.embed_supported || !item.embed_url) {
      document.getElementById('v158ServiceEmbed').innerHTML = '<div class="v158-provider-unavailable">' + providerIcon(item.provider) + '<b>' + esc(item.provider || 'This service') + ' does not provide an embedded player here.</b><p>Open the playlist in its own app or website to listen.</p><a href="' + esc(item.open_url || item.source_url || '#') + '" target="_blank" rel="noopener noreferrer">Open playlist ↗</a></div>';
      setExternalState('open');
      return;
    }
    if (String(item.provider).toLowerCase().indexOf('spotify') >= 0) await mountSpotify(item);
    else if (String(item.provider).toLowerCase().indexOf('youtube') >= 0) await mountYouTube(item);
    else mountExternalIframe(item);
  };

  window.v158ToggleManualListening = function () {
    if (!activeExternalPlayback) return;
    setExternalState(activeExternalPlayback.state === 'manual-playing' ? 'open' : 'manual-playing');
  };

  window.v158CloseExternalFullscreen = function () {
    var active = activeExternalPlayback;
    activeExternalPlayback = null;
    var overlay = document.getElementById('v158ServiceFullscreen');
    if (active && active.controller) { try { active.controller.pause(); active.controller.destroy(); } catch (_) {} }
    if (active && active.youtubePlayer) { try { active.youtubePlayer.pauseVideo(); active.youtubePlayer.destroy(); } catch (_) {} }
    if (overlay) { overlay.classList.remove('show'); overlay.setAttribute('aria-hidden', 'true'); overlay.innerHTML = ''; }
    document.body.classList.remove('v158-service-player-open');
    if (latestVioraStatus && typeof window.renderStatus === 'function') window.renderStatus(latestVioraStatus);
    window.refreshStatus?.();
  };

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && activeExternalPlayback) window.v158CloseExternalFullscreen();
  });

  var baseRenderStatus = window.renderStatus;
  if (typeof baseRenderStatus === 'function') {
    window.renderStatus = function (status) {
      latestVioraStatus = status || latestVioraStatus;
      baseRenderStatus(status);
      if (status && status.player_error && status.player_error !== window.__vioraLastPlayerError) {
        window.__vioraLastPlayerError = status.player_error;
        toast('MPV playback issue: ' + String(status.player_error).slice(0, 150));
      } else if (status && !status.player_error) window.__vioraLastPlayerError = null;
      if (activeExternalPlayback) paintExternalNowPlaying(status);
    };
  }

  var baseTogglePause = window.togglePause;
  if (typeof baseTogglePause === 'function') {
    window.togglePause = function () {
      if (!activeExternalPlayback) return baseTogglePause();
      if (activeExternalPlayback.controller) return activeExternalPlayback.controller.togglePlay();
      if (activeExternalPlayback.youtubePlayer) {
        return activeExternalPlayback.state === 'playing' ? activeExternalPlayback.youtubePlayer.pauseVideo() : activeExternalPlayback.youtubePlayer.playVideo();
      }
      toast('Use the controls in the ' + (activeExternalPlayback.item.provider || 'service') + ' player.');
    };
  }

  var loadPlaylistsBase = window.loadPlaylists;
  window.loadPlaylists = async function () {
    if (typeof loadPlaylistsBase === 'function') await loadPlaylistsBase();
    var page = $('page-playlists'); if (!page) return;
    var oldPanel = $('playlistImportPanel');
    if (oldPanel) oldPanel.remove();
    var pageIntro = page.querySelector('.page-sub');
    if (pageIntro) pageIntro.insertAdjacentHTML('afterend', externalPlaylistPanelMarkup());
    else page.insertAdjacentHTML('afterbegin', externalPlaylistPanelMarkup());
    page.insertAdjacentHTML('beforeend', importPanelMarkup());
    if (typeof v156RenderImportJobs === 'function') v156RenderImportJobs();
    await renderExternalPlaylistList();
  };

  function selectedValues(items) { return items.length ? items.map(esc).join(' · ') : 'Not selected'; }
  var onboardRendererBase = window.renderOnboardV153;
  if (typeof onboardRendererBase === 'function') {
    window.renderOnboardV153 = function () {
      var step = Number(state.onboard && state.onboard.step || 0);
      var footer = document.querySelector('.onboard-foot');
      if (footer && !$('onboardBack')) {
        var back = document.createElement('button'); back.id = 'onboardBack'; back.type = 'button'; back.className = 'onboard-back'; back.textContent = 'Back';
        footer.insertBefore(back, footer.firstChild);
        back.addEventListener('click', function () { if (state.onboard.step > 0) { state.onboard.step -= 1; renderOnboardV153(); } });
      }
      if (step < 6) {
        onboardRendererBase();
        $('onboardStep').textContent = step === 0 ? 'Your listening profile' : 'Step ' + step + ' of 6';
        $('onboardSkip').textContent = step === 0 ? 'Skip setup' : 'Skip this step';
        $('onboardNext').textContent = step === 0 ? 'Choose my music' : 'Continue';
        if ($('onboardBack')) $('onboardBack').disabled = step === 0;
        return;
      }
      $('onboardStep').textContent = 'Step 6 of 6 · review';
      $('onboardTitle').textContent = 'Your Viora starting point';
      $('onboardDesc').textContent = 'You can change these choices any time in Settings.';
      $('onboardSkip').textContent = 'Close';
      $('onboardNext').textContent = 'Save profile';
      if ($('onboardBack')) $('onboardBack').disabled = false;
      var data = state.onboard.data || {};
      $('onboardBody').innerHTML = '<div class="v158-profile-review"><div><b>Artists</b><p>' + selectedValues(data.favorite_artists || []) + '</p></div><div><b>Genres</b><p>' + selectedValues(data.genres || []) + '</p></div><div><b>Languages</b><p>' + selectedValues(data.languages || []) + '</p></div><div><b>Moods and moments</b><p>' + selectedValues(data.moods || []) + '</p></div><div><b>Discovery</b><p>' + esc(data.discovery_level || 'balanced') + '</p></div><div><b>Listening controls</b><p>' + ((data.hide_heard !== false) ? 'Hide songs already played' : 'Allow songs already played') + ' · ' + (data.show_community !== false ? 'Community uploads below official-looking releases' : 'Community uploads hidden') + '</p></div></div>';
    };
  }
  $('onboardNext').onclick = async function () {
    if (state.onboard.step < 6) { state.onboard.step += 1; renderOnboardV153(); return; }
    await api('/api/onboarding', 'POST', state.onboard.data);
    $('onboardingOverlay').classList.remove('show');
    toast('Your Viora profile is saved.');
    state.home = null; loadHome(true);
  };
  $('onboardSkip').onclick = async function () {
    if (state.onboard.step === 6) { $('onboardingOverlay').classList.remove('show'); return; }
    if (state.onboard.step < 6) { state.onboard.step += 1; renderOnboardV153(); }
  };

  if (typeof window.v155MessageHTML === 'function') {
    var oldAgentMessageRenderer = window.v155MessageHTML;
    window.v155MessageHTML = function (message) {
      return oldAgentMessageRenderer(message).replace(/Matches for your request/gi, 'Songs Viora found');
    };
  }

  var audioRequestPending = false;
  async function refreshReactiveSignal() {
    var shell = $('appState');
    var root = document.documentElement;
    var active = shell && shell.classList.contains('playing') && shell.getAttribute('data-reactive') !== 'false' && root.dataset.reducedMotion !== 'true';
    if (!active) {
      root.style.setProperty('--energy', '1');
      root.style.setProperty('--beat', '1');
      root.style.setProperty('--beat-opacity', '0');
      return;
    }
    if (audioRequestPending) return;
    audioRequestPending = true;
    try {
      var response = await fetch('/api/audio-reactivity', {cache:'no-store'});
      if (!response.ok) return;
      var signal = await response.json();
      var energy = Math.max(0, Math.min(1, Number(signal.audio_energy) || 0));
      var beat = Math.max(0, Math.min(1, Number(signal.audio_beat) || 0));
      var bass = Math.max(0, Math.min(1, Number(signal.audio_bass) || 0));
      root.style.setProperty('--energy', (1 + energy * .62).toFixed(3));
      root.style.setProperty('--beat', (1 + beat * .42).toFixed(3));
      root.style.setProperty('--bass', bass.toFixed(3));
      root.style.setProperty('--beat-opacity', (.04 + beat * .23).toFixed(3));
    } catch (_) {
      // Visual motion is decorative; playback continues if the signal is unavailable.
    } finally { audioRequestPending = false; }
  }
  window.setInterval(refreshReactiveSignal, 110);

  api('/api/settings').then(function (settings) { if (settings) setChartPreferences(settings); });
})();
