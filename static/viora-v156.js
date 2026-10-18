let v155AgentMessages = [];
try { v155AgentMessages = JSON.parse(localStorage.getItem('viora-agent-chat-v1') || '[]').slice(-60); } catch (_) { v155AgentMessages = []; }
let v155InstallPrompt = null;

function v155NavButton(page, label, path) {
  if (document.querySelector(`.nav [data-page="${page}"]`)) return;
  const button = document.createElement('button');
  button.dataset.page = page;
  button.setAttribute('aria-label', label);
  button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg><span>${label}</span>`;
  button.addEventListener('click', () => setPage(page));
  const anchor = page === 'agent' ? document.querySelector('.nav [data-page="search"]') : document.querySelector('.nav [data-page="playlists"]');
  document.querySelector('.nav').insertBefore(button, anchor || null);
}

function setPage(name) {
  state.page = name;
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  document.querySelectorAll('.nav button').forEach(button => button.classList.toggle('active', button.dataset.page === name));
  const loaders = {home:()=>loadHome(), discover:()=>loadDiscover(), search:()=>loadSearchLanding(), agent:()=>renderAgentPage(), artists:()=>loadArtists(), playlists:()=>loadPlaylists(), queue:()=>loadQueue(), favorites:()=>loadFavorites(), history:()=>loadHistory(), library:()=>loadLibrary(), settings:()=>loadSettings()};
  loaders[name]?.();
}

function renderStatusV155(s) {
  const previous = window.__vioraStatusV154;
  if (typeof previous === 'function') previous(s);
  const hasTrack = !!(s && s.current_track && (s.current_track.id || s.current_track.title));
  $('nowPlaceholder')?.classList.toggle('hidden', hasTrack);
  $('nowArt')?.classList.toggle('hidden', !hasTrack);
  $('nowTitle')?.classList.toggle('idle-title', !hasTrack);
  if (!hasTrack) {
    $('bottomTitle').textContent = 'Nothing playing';
    $('bottomArtist').textContent = 'Your next favorite is waiting';
    $('bottomArt').src = '/static/favicon.svg';
  }
  ['currentFavorite', 'currentPlaylist', 'currentQueue', 'stopCurrent'].forEach(id => { const button = $(id); if (button) button.disabled = !hasTrack; });
  document.querySelectorAll('.bottom-controls button').forEach(button => { button.disabled = !hasTrack; });
}

function row(t) {
  const track = {...t, id:t.track_key || t.track_id || t.id};
  const missing = !!t.missing_file;
  const remove = t.history_id
    ? `<button class="icon-btn" onclick="deleteHistoryEntry(${Number(t.history_id)})" title="Remove from history" aria-label="Remove from history">×</button>`
    : (t.is_downloaded || t.local_path)
      ? `<button class="icon-btn" onclick="deleteLibraryTrack(this)" title="Delete downloaded file" aria-label="Delete downloaded file">×</button>`
      : `<button class="icon-btn" onclick="favoriteTrack(event,'${esc(track.id)}',false)" title="Remove favorite" aria-label="Remove favorite">♥</button>`;
  return `<div class="row" data-track="${esc(JSON.stringify(track))}"><img src="${esc(t.thumbnail||'')}" alt=""><div class="row-main"><b>${esc(t.title||'Unknown')}</b><span>${esc(t.artist||t.channel||'')}${missing?' · Missing file':''}</span></div><div class="row-actions"><button class="icon-btn" onclick="playRow(this)" title="Play" aria-label="Play" ${missing?'disabled':''}>▶</button><button class="icon-btn" onclick="queueRow(this)" title="Add to queue" aria-label="Add to queue" ${missing?'disabled':''}>＋</button><button class="icon-btn" onclick="openPlaylistForRow(this)" title="Save to playlist" aria-label="Save to playlist">▣</button>${t.is_downloaded||t.local_path?'':`<button class="icon-btn" onclick="downloadRow(this)" title="Download" aria-label="Download">↓</button>`}${remove}</div></div>`;
}

function openPlaylistForRow(button) {
  state.modalTrack = getCardTrack(button.closest('.row'));
  loadPlaylistChoices();
  $('playlistModal').classList.add('show');
}

function currentTrack() { return state.lastStatus?.current_track || null; }
async function favoriteCurrent() {
  const track = currentTrack();
  if (!track) return;
  const value=!track.is_favorite;
  await api('/api/track/favorite','POST',{...track,favorite:value});
  track.is_favorite=value;
  toast(value?'Added to favorites':'Removed from favorites');
  if (state.page==='favorites') loadFavorites();
}
async function saveCurrentToPlaylist() {
  const track = currentTrack();
  if (!track) return;
  state.modalTrack = track;
  await loadPlaylistChoices();
  $('playlistModal').classList.add('show');
}
async function queueCurrent() {
  const track = currentTrack();
  if (!track) return;
  const result = await api('/api/queue','POST',{tracks:[track]});
  if (result?.status) renderStatus(result.status);
  if (result?.reply) toast(result.reply);
}

async function clearCurrentPlayback() {
  const result = await api('/api/stop', 'POST', {});
  if (result?.status) renderStatus(result.status);
  if (result?.reply) toast(result.reply);
}

async function openNowPlayingFullscreen() {
  const track = currentTrack();
  if (!track) return toast('Start a song to open the full-screen player.');
  const overlay = $('fullscreenPlayer');
  $('fullscreenArt').src = track.thumbnail || state.lastStatus?.thumbnail || '/static/favicon.svg';
  $('fullscreenTitle').textContent = track.title || state.lastStatus?.now_playing || 'Unknown track';
  $('fullscreenArtist').textContent = track.artist || track.channel || 'Unknown artist';
  overlay.classList.add('show'); overlay.setAttribute('aria-hidden', 'false');
  try { await overlay.requestFullscreen?.(); } catch (_) {}
}

async function closeNowPlayingFullscreen() {
  const overlay = $('fullscreenPlayer');
  overlay.classList.remove('show'); overlay.setAttribute('aria-hidden', 'true');
  if (document.fullscreenElement === overlay) { try { await document.exitFullscreen(); } catch (_) {} }
}

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && $('fullscreenPlayer')?.classList.contains('show')) closeNowPlayingFullscreen();
});

function renderAgentPage() {
  $('page-agent').innerHTML = `<div class="agent-heading"><div class="agent-orb"><img src="/static/viora-agent-mark.svg" alt="Viora Agent mark"></div><div><h1 class="page-title">Viora Agent</h1><p class="page-sub">Ask for a mood, find something familiar, explore beyond your favorites, or control playback.</p></div></div><div class="agent-capability"><b>Grounded in your music</b><span>The local retrieval layer uses your saved tracks, favorites, listening history and taste profile. Track suggestions come from your library or music search.</span></div><div class="agent-chat" id="agentChat">${v155AgentMessages.map(v155MessageHTML).join('')||`<div class="agent-welcome"><h2>What should we listen to?</h2><p>I can find music, explain recommendations, make a playlist from a prompt, or control the player.</p><div class="agent-prompts"><button class="chip" onclick="sendAgentMessage('What have I been listening to?')">Summarize my taste</button><button class="chip" onclick="sendAgentMessage('Recommend 5 songs for a calm evening')">Calm evening</button><button class="chip" onclick="sendAgentMessage('Play something similar to this')">Something similar</button><button class="chip" onclick="sendAgentMessage('Save the current song to a new playlist called Tonight')">Save this song</button></div></div>`}</div><form class="agent-compose" onsubmit="event.preventDefault();sendAgentMessage($('agentInput').value)"><textarea id="agentInput" rows="1" placeholder="Ask Viora to find, play, queue, or save music…" aria-label="Message Viora Agent"></textarea><button class="agent-send" aria-label="Send message" title="Send">➤</button></form><p class="agent-note">Viora’s assistant is local and retrieval-grounded. It does not use a hosted generative AI model.</p>`;
  const chat = $('agentChat'); if (chat) chat.scrollTop = chat.scrollHeight;
  $('agentInput')?.addEventListener('keydown', event => { if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAgentMessage(event.currentTarget.value);} });
}

function v155MessageHTML(message) {
  const sources = message.sources?.length ? `<div class="agent-sources"><small>Retrieved from your music context</small><div class="cards">${message.sources.map((track,index)=>card(track,index)).join('')}</div></div>` : '';
  return `<div class="agent-message ${message.role}"><div class="agent-bubble">${esc(message.text).replace(/\n/g,'<br>')}</div>${sources}</div>`;
}

async function sendAgentMessage(value) {
  const prompt = String(value||'').trim(); if(!prompt) return;
  if($('agentInput')) $('agentInput').value='';
  v155AgentMessages.push({role:'user',text:prompt});
  renderAgentPage();
  const chat=$('agentChat'); if(chat){const pending=document.createElement('div');pending.className='agent-message assistant';pending.id='agentPending';pending.innerHTML='<div class="agent-bubble thinking"><span></span><span></span><span></span></div>';chat.appendChild(pending);chat.scrollTop=chat.scrollHeight;}
  const result=await api('/api/agent','POST',{message:prompt});
  $('agentPending')?.remove();
  if(!result)return;
  v155AgentMessages.push({role:'assistant',text:result.reply||'I could not complete that request.',sources:result.sources||[],sourceLabel:result.intent?.action==='LOCAL_INSIGHT'?'From your local library and listening history':'Songs Viora found'});
  try { localStorage.setItem('viora-agent-chat-v1',JSON.stringify(v155AgentMessages.slice(-60))); } catch (_) {}
  if(result.status)renderStatus(result.status);
  renderAgentPage();
}

async function loadArtists() {
  const artists=await api('/api/artists');
  $('page-artists').innerHTML=`<h1 class="page-title">Artists</h1><p class="page-sub">Your artist map grows from favorites and listening history.</p>${artists?.length?`<div class="artist-grid">${artists.map(item=>`<button class="artist-tile" onclick="doSearch(this.dataset.artist+' songs')" data-artist="${esc(item.artist)}"><span class="artist-avatar">${esc((item.artist||'?').trim().slice(0,1).toUpperCase())}</span><b>${esc(item.artist||'Unknown artist')}</b><small>${Number(item.plays||0)} plays · ${Number(item.skips||0)} skips</small><span class="artist-open">Find tracks →</span></button>`).join('')}</div>`:'<div class="empty">Listen to or favorite a few tracks and your artists will appear here.</div>'}`;
}

async function installViora() {
  if(v155InstallPrompt){v155InstallPrompt.prompt();await v155InstallPrompt.userChoice;v155InstallPrompt=null;return;}
  toast('Use your browser menu and choose Install Viora or Add to Home screen.');
}

function addInstallControl() {
  if(document.querySelector('#installViora')) return;
  const target=$('page-settings'); if(!target) return;
  const panel=document.createElement('div');panel.className='panel';panel.innerHTML='<h3>Install Viora</h3><p>Install this web app from a supported browser for an app-style window and home-screen shortcut.</p><button id="installViora" class="primary-action" onclick="installViora()">Install Viora</button>';
  target.appendChild(panel);
}

function initV155() {
  const favicon='/static/favicon.svg';
  document.querySelectorAll('.brand-logo').forEach(image=>image.src=favicon);
  const icon=document.querySelector('link[rel="icon"]');if(icon)icon.href=favicon;
  v155NavButton('agent','Viora Agent','M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M9 9h6v6H9z');
  v155NavButton('artists','Artists','M4 20V7l7-4v17M4 20h16M11 20V9l9-4v15M7 8v.01M7 11v.01M7 14v.01M15 10v.01M18 9v.01M15 13v.01M18 12v.01M15 16v.01M18 15v.01');
  window.__vioraStatusV154=renderStatus;
  renderStatus=renderStatusV155;
  if(state.lastStatus)renderStatusV155(state.lastStatus);
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();v155InstallPrompt=event;});
  if('serviceWorker' in navigator)navigator.serviceWorker.register('/service-worker.js').catch(()=>{});
  if(state.page==='settings')addInstallControl();
}

const _v155LoadSettings=loadSettings;
loadSettings=async function(){await _v155LoadSettings();addInstallControl();};

const _v155RenderQueue=renderQueue;
renderQueue=function(tracks){
  _v155RenderQueue(tracks);
  if(state.page==='queue') document.querySelectorAll('#page-queue .row').forEach(item=>{
    const actions=item.querySelector('.row-actions');
    if(actions&&!actions.querySelector('[data-save-playlist]')){
      const save=document.createElement('button');save.className='icon-btn';save.dataset.savePlaylist='1';save.title='Save to playlist';save.setAttribute('aria-label','Save to playlist');save.textContent='▣';save.addEventListener('click',()=>openPlaylistForRow(save));actions.appendChild(save);
    }
  });
};

initV155();

// v15.6 product updates: live status, charts, larger artist discovery,
// portable local data and playlist import that continues in the background.
let v156MusicReactive = true;
let v156LastTrackKey = '';
let v156LastHomeRefresh = 0;
let v156Connectivity = null;
state.artistPicks = null;
state.importJobs = state.importJobs || [];

function v156EnsureChartsPage() {
  if (!$('page-charts')) {
    const page = document.createElement('section');
    page.className = 'page'; page.id = 'page-charts';
    document.querySelector('.main')?.appendChild(page);
  }
  v155NavButton('charts', 'Charts', 'M4 19V5m0 14h16M8 15V9m4 6V5m4 10v-4m4 4V7');
}

function setPage(name) {
  state.page = name;
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  document.querySelectorAll('.nav button').forEach(button => button.classList.toggle('active', button.dataset.page === name));
  const loaders = {home:()=>loadHome(), discover:()=>loadDiscover(), search:()=>loadSearchLanding(), agent:()=>renderAgentPage(), artists:()=>loadArtists(), charts:()=>loadCharts(), playlists:()=>loadPlaylists(), queue:()=>loadQueue(), favorites:()=>loadFavorites(), history:()=>loadHistory(), library:()=>loadLibrary(), settings:()=>loadSettings()};
  loaders[name]?.();
}

async function v156SetConnectivity(online) {
  if (v156Connectivity === online) return;
  v156Connectivity = online;
  const result = await api('/api/network', 'POST', {online: !!online});
  v156UpdateStatusLabel(result);
}

function v156UpdateStatusLabel(connection) {
  const pill = $('statusPill'); if (!pill) return;
  const mode = connection?.mode || 'auto';
  if (mode === 'offline') pill.textContent = 'Viora ready · Offline mode';
  else pill.textContent = connection?.online === false ? 'Viora ready · Offline' : 'Viora ready · Online';
  pill.title = 'Viora runs on this device. Online search requires an internet connection.';
}

async function refreshStatus() {
  const status = await api('/status');
  if (!status) return;
  renderStatus(status);
  if (state.page === 'charts' && Date.now() - Number(state.chartLastLoaded||0) >= 86400000) {
    loadCharts(state.chartRegion||'IN', state.chartCategory||'top50', true);
  }
  const online = navigator.onLine !== false;
  if (v156Connectivity !== online) await v156SetConnectivity(online);
  else v156UpdateStatusLabel({online, mode: state.playbackMode || 'auto'});
  const key = status.current_track ? String(status.current_track.id || status.current_track.title || '') : '';
  if (key && key !== v156LastTrackKey) {
    v156LastTrackKey = key;
    state.home = null;
    const now = Date.now();
    if (state.page === 'home' && now - v156LastHomeRefresh > 2500) {
      v156LastHomeRefresh = now; loadHome(true);
    } else if (state.page === 'history') loadHistory();
    else if (state.page === 'playlists' && state.playlist) openPlaylist(state.playlist.id);
  } else if (!key) v156LastTrackKey = '';
}

window.addEventListener('online', () => v156SetConnectivity(true));
window.addEventListener('offline', () => v156SetConnectivity(false));

const v156RenderStatus = renderStatus;
renderStatus = function(status) {
  v156RenderStatus(status);
  const track = status?.current_track;
  const overlay = $('fullscreenPlayer');
  if (track && overlay?.classList.contains('show')) {
    $('fullscreenArt').src = track.thumbnail || status.thumbnail || '/static/favicon.svg';
    $('fullscreenTitle').textContent = track.title || status.now_playing || 'Unknown track';
    $('fullscreenArtist').textContent = track.artist || track.channel || 'Unknown artist';
    $('fullscreenTime').textContent = formatTime(status.time_pos);
    $('fullscreenDuration').textContent = formatTime(status.duration);
    $('fullscreenProgress').style.width = status.duration ? `${Math.min(100,(status.time_pos/status.duration)*100)}%` : '0%';
    $('fullscreenPlay').textContent = status.playing && !status.paused ? 'Ⅱ' : '▶';
  } else if (!track && overlay?.classList.contains('show')) {
    closeNowPlayingFullscreen();
  }
  const playing = !!(status?.playing && !status?.paused);
  const reduceMotion = document.documentElement.dataset.reducedMotion === 'true';
  const reactive = v156MusicReactive && !reduceMotion;
  $('appState')?.setAttribute('data-reactive', String(reactive));
  if (!reactive || !playing) document.documentElement.style.setProperty('--beat-opacity', '0');
};

async function v156LoadAgentChat() {
  const remote = await api('/api/agent-chat');
  if (!remote || !Array.isArray(remote.messages)) return;
  if (remote.messages.length) v155AgentMessages = remote.messages.slice(-60);
  else if (v155AgentMessages.length) await api('/api/agent-chat', 'POST', {messages:v155AgentMessages});
}

const v156SendAgentMessage = sendAgentMessage;
sendAgentMessage = async function(value) {
  await v156SendAgentMessage(value);
  await api('/api/agent-chat', 'POST', {messages:v155AgentMessages.slice(-60)});
};

const v156MessageHTML = v155MessageHTML;
v155MessageHTML = function(message) {
  const html = v156MessageHTML(message);
  return html.replace('Retrieved from your music context', esc(message.sourceLabel || 'Songs Viora found'));
};

const v156AgentRenderer = renderAgentPage;
renderAgentPage = function() {
  v156AgentRenderer();
  $('agentInput')?.setAttribute('placeholder', 'Ask Viora to find, play, queue, or save music…');
};

function v156ArtistCard(item, plays, skips) {
  const image = item.image ? `<img class="artist-photo" src="${esc(item.image)}" alt="" loading="lazy">` : `<span class="artist-avatar">${esc((item.name||'?').trim().slice(0,1).toUpperCase())}</span>`;
  const source = item.source_url ? `<a class="artist-source" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" aria-label="Artist photo source">Image source</a>` : '';
  return `<button class="artist-tile" data-artist-name="${esc(item.name)}" onclick="doSearch(this.dataset.artistName+' songs')">${image}<b>${esc(item.name)}</b><small>${plays != null ? `${Number(plays)} plays · ${Number(skips||0)} skips` : esc(item.region||'Popular worldwide')}</small>${source}<span class="artist-open">Find tracks →</span></button>`;
}

async function loadArtists() {
  const [listened, popular] = await Promise.all([api('/api/artists'), api('/api/artist-picks')]);
  const your = (listened||[]).filter(item => Number(item.plays||0) > 0).map(item => ({name:item.artist, plays:item.plays, skips:item.skips}));
  const followed = new Set(your.map(item => String(item.name||'').toLocaleLowerCase()));
  const starters = (popular||[]).filter(item => !followed.has(String(item.name||'').toLocaleLowerCase()));
  $('page-artists').innerHTML = `<h1 class="page-title">Artists</h1><p class="page-sub">Your artists grow from what you play. Explore a worldwide starter set and search for anyone else.</p><input class="artist-filter" id="artistFilter" placeholder="Filter artists…" oninput="filterArtistTiles(this.value)" aria-label="Filter artists">${your.length?`<div class="section"><div class="section-head"><h2>Your listening map</h2><span>Updates from your history and favorites</span></div><div class="artist-grid">${your.map(item=>v156ArtistCard({name:item.name},item.plays,item.skips)).join('')}</div></div>`:'<div class="empty">Artists you listen to will appear here automatically.</div>'}<div class="section"><div class="section-head"><h2>Explore artists</h2><span>Curated discovery picks · not a live popularity ranking</span></div>${starters.length?`<div class="artist-grid">${starters.map(item=>v156ArtistCard(item)).join('')}</div>`:'<div class="empty">Artist picks are unavailable offline. Your listening map remains here.</div>'}</div><p class="artist-attribution">Artist images are linked to their reference pages. Image rights vary by source.</p>`;
}

function filterArtistTiles(value) {
  const query = String(value||'').trim().toLocaleLowerCase();
  document.querySelectorAll('#page-artists .artist-tile').forEach(tile => tile.hidden = !tile.dataset.artistName.toLocaleLowerCase().includes(query));
}

const v156RenderOnboardBase = renderOnboardV153;
renderOnboardV153 = function() {
  v156RenderOnboardBase();
  if (state.onboard.step !== 1) return;
  if (!Array.isArray(state.artistPicks)) {
    $('onboardBody').insertAdjacentHTML('beforeend', '<div class="artist-pick-loading">Loading artist choices…</div>');
    api('/api/artist-picks').then(items => { if (items && state.onboard.step === 1) { state.artistPicks = items; renderOnboardV153(); } });
    return;
  }
  const chosen = new Set(state.onboard.data.favorite_artists||[]);
  $('onboardBody').innerHTML = `<p class="onboard-helper">Choose any artists you already enjoy, or add your own below.</p><input class="onboard-input" placeholder="Filter artists…" oninput="filterOnboardArtists(this.value)" aria-label="Filter artist choices"><div class="artist-grid onboard-artist-grid">${state.artistPicks.map(item=>`<button class="artist-tile pick-artist ${chosen.has(item.name)?'selected':''}" data-artist-name="${esc(item.name)}" onclick="pickOnboardArtist(this.dataset.artistName)">${item.image?`<img class="artist-photo" src="${esc(item.image)}" alt="" loading="lazy">`:`<span class="artist-avatar">${esc(item.name.slice(0,1))}</span>`}<b>${esc(item.name)}</b><small>${esc(item.region)}</small></button>`).join('')}</div><input id="customChoice" class="onboard-input" style="margin-top:12px" placeholder="Add another artist…"><button class="pick" style="margin-top:8px" onclick="addCustomChoice('favorite_artists')">＋ Add custom</button>`;
};

function pickOnboardArtist(name) {
  const artists = state.onboard.data.favorite_artists;
  const index = artists.indexOf(name);
  if (index >= 0) artists.splice(index, 1); else artists.push(name);
  renderOnboardV153();
}

function filterOnboardArtists(value) {
  const query = String(value||'').toLocaleLowerCase();
  document.querySelectorAll('.onboard-artist-grid .artist-tile').forEach(tile => tile.hidden = !tile.dataset.artistName.toLocaleLowerCase().includes(query));
}

const v156ChartRegions = [['IN','India'],['US','United States'],['GB','United Kingdom'],['CA','Canada'],['AU','Australia'],['JP','Japan'],['KR','South Korea'],['BR','Brazil'],['MX','Mexico'],['NG','Nigeria'],['ZA','South Africa'],['FR','France'],['DE','Germany'],['ES','Spain'],['ID','Indonesia'],['PH','Philippines'],['AE','United Arab Emirates']];
const v156ChartDeck = [
  {id:'top50',title:'Country Top 50',sub:'Apple Music regional chart',art:0},
  {id:'week',title:'Popular this week',sub:'Current most-played snapshot · refreshed daily',art:1},
  {id:'love',title:'Love',sub:'Romantic song discovery mix',art:2},
  {id:'pop',title:'Pop',sub:'Pop song discovery mix',art:3},
  {id:'english',title:'English',sub:'English-language discovery mix',art:4},
  {id:'hindi',title:'Hindi',sub:'Hindi-language discovery mix',art:5},
];

function v156ChartCards(region, selected) {
  return `<div class="chart-card-grid">${v156ChartDeck.map(item=>`<button class="chart-card chart-art-${item.art} ${selected===item.id?'selected':''}" onclick="loadCharts('${region}','${item.id}')"><span class="chart-card-kicker">VIORA CHARTS</span><b>${item.id==='top50'?`${v156ChartRegions.find(row=>row[0]===region)?.[1]||region} Top 50`:item.title}</b><small>${item.sub}</small><span class="chart-card-arrow">↗</span></button>`).join('')}</div>`;
}

function v156AppleChartRows(items) {
  return items.map(item=>`<div class="chart-row"><span class="chart-position">${Number(item.position)}</span><img src="${esc(item.artwork||'')}" alt="" loading="lazy"><div class="chart-main"><b>${esc(item.title)}</b><span>${esc(item.artist)}${item.album?` · ${esc(item.album)}`:''}</span></div><button class="icon-btn" data-query="${esc(`${item.title} ${item.artist}`)}" onclick="doSearch(this.dataset.query)" title="Find a playable version in Viora" aria-label="Find ${esc(item.title)} in Viora">⌕</button><a class="icon-btn chart-link" href="${esc(item.apple_url)}" target="_blank" rel="noopener noreferrer" title="Open Apple Music chart entry" aria-label="Open Apple Music entry">↗</a></div>`).join('');
}

async function loadCharts(region='IN', selected='top50', forceRefresh=false) {
  state.chartRegion=region; state.chartCategory=selected; state.chartLastLoaded=Date.now();
  const page = $('page-charts');
  if (!v156ChartDeck.some(item=>item.id===selected)) selected='top50';
  const regionName = v156ChartRegions.find(item=>item[0]===region)?.[1]||region;
  const control = `<div class="chart-controls"><label for="chartRegion">Region</label><select id="chartRegion" class="sort-select" onchange="loadCharts(this.value,'top50')">${v156ChartRegions.map(([code,name])=>`<option value="${code}" ${code===region?'selected':''}>${name}</option>`).join('')}</select><button class="icon-btn" onclick="loadCharts($('chartRegion').value,'${selected}',true)" title="Refresh from chart source" aria-label="Refresh charts">↻</button></div>`;
  page.innerHTML = `<h1 class="page-title">Charts</h1><p class="page-sub">Find current regional hits and themed song mixes. The Top 50 uses Apple Music's chart feed; other shelves are Viora search mixes, not third-party rankings.</p>${control}${v156ChartCards(region,selected)}<div id="chartResults"><div class="empty">Loading ${esc(v156ChartDeck.find(item=>item.id===selected).title)}…</div></div>`;
  const chartData = await api(`/api/charts?region=${encodeURIComponent(region)}&limit=100${forceRefresh?'&refresh=1':''}`);
  if (!chartData) return;
  if (chartData.error) { $('chartResults').innerHTML=`<div class="empty">${esc(chartData.error)}</div>`; return; }
  const selectedCard = v156ChartDeck.find(item=>item.id===selected);
  let rows = [], isMix = !['top50','week'].includes(selected), offline = !!chartData.offline;
  let source = 'Apple Music · regional most-played feed';
  if (isMix) {
    const mix = await api(`/api/chart-mix?category=${encodeURIComponent(selected)}&region=${encodeURIComponent(region)}`);
    if (!mix) return;
    rows = mix.results||[]; offline = !!mix.offline; source = mix.source||'Viora discovery mix';
  } else {
    rows = (chartData.results||[]).slice(0,selected==='week'?20:50);
  }
  const refreshed = chartData.updated_at ? `Feed date: ${esc(chartData.updated_at)}` : 'Source refreshes daily';
  const note = selected==='week' ? 'Current Apple Music most-played list · refreshed daily; exact weekly play-count totals are not published in this feed.' : '';
  const list = isMix ? rows.map((item,index)=>card(item,index)).join('') : v156AppleChartRows(rows);
  $('chartResults').innerHTML = `<div class="chart-results-head"><div><h2>${esc(selected==='top50'?`${regionName} Top 50`:selected==='week'?'Popular this week':selectedCard.title)}</h2><p>${esc(isMix?'Official and likely-official source signals are ranked first. Community posts remain lower priority.':note||`${regionName} regional songs, ranked by Apple Music.`)}</p></div>${isMix?'<span class="source-pill">Viora mix</span>':''}</div><div class="panel chart-attribution"><span>${esc(source)} · ${refreshed}${chartData.stale?' · showing cached data':''}</span>${!isMix&&chartData.source_url?`<a href="${esc(chartData.source_url)}" target="_blank" rel="noopener noreferrer">View Apple chart ↗</a>`:''}</div>${offline&&!rows.length?'<div class="empty">You are offline and no saved chart snapshot is available. Your downloaded library is still available in Offline.</div>':''}${rows.length?`<div class="${isMix?'cards chart-mix-cards':'chart-list'}">${list}</div>`:offline?'':`<div class="empty">No songs are available in this section right now.</div>`}`;
}

function v156ImportPanel() {
  if (!$('page-playlists') || $('playlistImportPanel')) return;
  const panel = document.createElement('div'); panel.id='playlistImportPanel'; panel.className='panel import-panel';
  panel.innerHTML = `<h3>Build a Viora playlist from a track list</h3><p>Import song names from a file or paste them below. Viora finds playable matches in the background.</p><input id="playlistImportName" class="storage-path" placeholder="Playlist name (optional)" aria-label="Imported playlist name"><form onsubmit="event.preventDefault();startPlaylistImport()"><div class="import-actions"><input id="playlistImportFile" type="file" accept=".csv,.m3u,.m3u8,.json,.txt" required><button class="primary-action">Import file</button></div></form><label class="import-label" for="playlistTracklist">Or paste copied song names · one per line</label><textarea id="playlistTracklist" class="playlist-source-input" rows="4" placeholder="Artist - Song title&#10;Another artist - Another song" aria-label="Track names for playlist import"></textarea><button type="button" class="primary-action" onclick="startPastedPlaylistImport()">Build playlist from pasted tracks</button><small>Viora does not read playlist track lists from provider players. Import a CSV, M3U, JSON, or text track list, or paste copied song names; check unmatched tracks afterward.</small><div id="playlistImportProgress"></div>`;
  $('page-playlists').appendChild(panel);
}

const v156LoadPlaylists = loadPlaylists;
loadPlaylists = async function() { await v156LoadPlaylists(); v156ImportPanel(); v156RenderImportJobs(); };

async function startPlaylistImport() {
  const file = $('playlistImportFile')?.files?.[0]; if (!file) return toast('Choose a playlist file first.');
  await v156BeginPlaylistImport(file);
}

async function startPastedPlaylistImport() {
  const text = String($('playlistTracklist')?.value||'').trim();
  if (!text) return toast('Paste at least one track title first.');
  const name = String($('playlistImportName')?.value||'').trim()||'Pasted playlist';
  await v156BeginPlaylistImport(new File([text], `${name}.txt`, {type:'text/plain'}));
}

async function v156BeginPlaylistImport(file) {
  const form = new FormData(); form.append('file',file); form.append('name',$('playlistImportName')?.value||'');
  try {
    const response = await fetch('/api/playlist-import',{method:'POST',body:form});
    const data = await response.json();
    if (!response.ok) return toast(data.error||'Playlist import could not start.');
    state.importJobs.push(data.job_id); toast(data.message||'Playlist matching started in the background.');
    v156RenderImportJobs(); v156PollImport(data.job_id);
  } catch (_) { toast('The local Viora app could not start this import.'); }
}

function v156RenderImportJobs() {
  const box=$('playlistImportProgress'); if(!box)return;
  box.innerHTML=(state.importJobData||[]).map(job=>`<div class="import-progress"><b>${esc(job.playlist_name||'Playlist import')}</b><span>${esc(job.message||'Matching…')}</span><progress max="${Number(job.total||1)}" value="${Number(job.completed||0)}"></progress>${job.missed?.length?`<small>${job.missed.length} song(s) could not be matched. Open the playlist to review it.</small>`:''}</div>`).join('');
}

async function v156PollImport(jobId) {
  for (;;) {
    await new Promise(resolve=>setTimeout(resolve,1800));
    let response, job;
    try { response=await fetch(`/api/playlist-import/${encodeURIComponent(jobId)}`); job=await response.json(); } catch (_) { return; }
    if (!response.ok) return;
    state.importJobData=state.importJobData||[];
    const index=state.importJobData.findIndex(item=>item.id===jobId);
    if(index<0)state.importJobData.push(job);else state.importJobData[index]=job;
    v156RenderImportJobs();
    if(job.status==='complete') { toast(job.message||'Playlist import finished.'); if(state.page==='playlists')await loadPlaylists(); return; }
    if(job.status==='error') { toast(job.message||'Playlist import stopped.'); return; }
  }
}

const v156LoadSettings = loadSettings;
loadSettings = async function() {
  await v156LoadSettings();
  const appText = [...document.querySelectorAll('#page-settings p')].find(node=>node.textContent.includes('Viora v'));
  if (appText) appText.textContent='Viora · local-first music discovery';
  const settings = await api('/api/settings');
  if(settings){v156MusicReactive=settings.music_reactive!==false;state.playbackMode=settings.playback_mode||'auto';}
  const panel=document.createElement('div');panel.className='panel';panel.innerHTML=`<h3>Sound and movement</h3><div class="pref-row"><div><b>Music-reactive background</b><small>Let the color field respond to playback. It never uses your microphone.</small></div><button class="switch ${v156MusicReactive?'on':''}" role="switch" aria-checked="${v156MusicReactive}" aria-label="Music-reactive background" onclick="updatePreference('music_reactive',!${v156MusicReactive})"></button></div>`;
  $('page-settings').appendChild(panel);
  const privacy=document.createElement('div');privacy.className='panel';privacy.innerHTML=`<h3>Move or protect your library</h3><p>Back up or restore your playlists, taste, favorites, history, settings, and Agent conversation. Audio files stay in your offline folder; copy that folder separately.</p><div class="row-actions"><button class="icon-btn" style="width:auto;padding:0 12px" onclick="downloadVioraBackup()">Download backup</button><label class="icon-btn backup-label">Restore backup<input type="file" accept=".db,.sqlite,.sqlite3" onchange="restoreVioraBackup(this)" hidden></label></div><small>Back up before moving Viora to another browser or app build.</small>`;
  $('page-settings').appendChild(privacy);
  const community=document.createElement('div');community.className='panel';community.innerHTML=`<h3>Viora community</h3><p>Share ideas and report issues in the Viora Telegram community.</p><a class="primary-action community-link" href="https://t.me/+A-WF1i2q7aJhMzQ9" target="_blank" rel="noopener noreferrer">Open community ↗</a>`;
  $('page-settings').appendChild(community);
};

function updatePreference(key,value) {
  api('/api/settings','POST',{[key]:value}).then(async result=>{
    if(!result)return;
    document.documentElement.dataset.reducedMotion=String(!!result.reduced_motion);
    if(key==='music_reactive')v156MusicReactive=!!result.music_reactive;
    if(key==='playback_mode')state.playbackMode=result.playback_mode;
    if(key==='hide_heard'||key==='show_community'){state.home=null;await loadHome(true);}
    await loadSettings();
  });
}

async function setPlaybackMode(value) {
  const result=await api('/api/settings','POST',{playback_mode:value});
  if(!result)return;
  state.playbackMode=result.playback_mode;
  toast(`Playback mode: ${result.playback_mode}`);
  state.home=null;
  await loadHome(true);
  if(state.page==='discover')await loadDiscover();
  if(state.page==='settings')await loadSettings();
}

async function downloadVioraBackup() {
  try {
    const response=await fetch('/api/backup');
    if(!response.ok){const data=await response.json();return toast(data.error||'Backup failed.');}
    const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download='viora-library-backup.db';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Viora library backup downloaded.');
  } catch (_) { toast('Viora could not download a backup.'); }
}

async function restoreVioraBackup(input) {
  const file=input.files?.[0];if(!file)return;
  if(!confirm('Restore this Viora backup? It replaces the current library, profile, playlists and history.')){input.value='';return;}
  const form=new FormData();form.append('file',file);
  try {
    const response=await fetch('/api/backup',{method:'POST',body:form}),data=await response.json();
    if(!response.ok)return toast(data.error||'Backup restore failed.');
    state.home=null;toast(data.message||'Viora backup restored.');await v156LoadAgentChat();await refreshPageData();await loadSettings();
  } catch (_) { toast('Viora could not restore this backup.'); }
  finally { input.value=''; }
}

const v156InitBase = init;
init = async function() {
  v156EnsureChartsPage();
  await v156LoadAgentChat();
  await v156InitBase();
  const settings=await api('/api/settings');
  if(settings){v156MusicReactive=settings.music_reactive!==false;state.playbackMode=settings.playback_mode||'auto';}
  await v156SetConnectivity(navigator.onLine!==false);
  await refreshStatus();
};

v156EnsureChartsPage();

const v156RenderQueueBase = renderQueue;
renderQueue = function(tracks) {
  v156RenderQueueBase(tracks);
  if (state.page === 'queue' && !tracks?.length) {
    const empty = $('page-queue')?.querySelector('.list .empty');
    if (empty) empty.innerHTML = `Keep the next song close. Add a track from <button class="text-button" onclick="setPage('discover')">Discover</button> or <button class="text-button" onclick="setPage('search');$('searchInput').focus()">Search</button>, or create a playlist for later.`;
  }
};

(async function v156Boot() {
  await init();
})();
