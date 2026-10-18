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
  ['currentFavorite', 'currentPlaylist', 'currentQueue'].forEach(id => { const button = $(id); if (button) button.disabled = !hasTrack; });
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

function renderAgentPage() {
  $('page-agent').innerHTML = `<div class="agent-heading"><div class="agent-orb"><img src="/static/favicon.svg" alt=""></div><div><h1 class="page-title">Viora Agent</h1><p class="page-sub">Ask for a mood, find something familiar, explore beyond your favorites, or control playback.</p></div></div><div class="agent-capability"><b>Grounded in your music</b><span>The local retrieval layer uses your saved tracks, favorites, listening history and taste profile. Track suggestions come from your library or music search.</span></div><div class="agent-chat" id="agentChat">${v155AgentMessages.map(v155MessageHTML).join('')||`<div class="agent-welcome"><h2>What should we listen to?</h2><p>I can find music, explain recommendations, make a playlist from a prompt, or control the player.</p><div class="agent-prompts"><button class="chip" onclick="sendAgentMessage('What have I been listening to?')">Summarize my taste</button><button class="chip" onclick="sendAgentMessage('Recommend 5 songs for a calm evening')">Calm evening</button><button class="chip" onclick="sendAgentMessage('Play something similar to this')">Something similar</button><button class="chip" onclick="sendAgentMessage('Save the current song to a new playlist called Tonight')">Save this song</button></div></div>`}</div><form class="agent-compose" onsubmit="event.preventDefault();sendAgentMessage($('agentInput').value)"><textarea id="agentInput" rows="1" placeholder="Ask Viora to find, play, queue, or save music…" aria-label="Message Viora Agent"></textarea><button class="agent-send" aria-label="Send message" title="Send">➤</button></form><p class="agent-note">Viora’s assistant is local and retrieval-grounded. It does not use a hosted generative AI model.</p>`;
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
  v155AgentMessages.push({role:'assistant',text:result.reply||'I could not complete that request.',sources:result.sources||[]});
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
