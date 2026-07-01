"""Legacy inline HTML fallback served when ``web/index.html`` is absent."""

WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>huntproxy</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#222;padding:0;max-width:1400px;margin:0 auto}
h1{font-size:18px;padding:14px 20px 0}
.sub{color:#888;font-size:12px;padding:0 20px 10px}

.tabs{display:flex;gap:0;border-bottom:2px solid #d0d7de;padding:0 20px;margin-bottom:14px}
.tab{padding:8px 16px;cursor:pointer;color:#656d76;font-weight:500;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .1s}
.tab:hover{color:#222}
.tab.active{color:#0969da;border-bottom-color:#0969da}

.tab-content{display:none;padding:0 20px 20px}
.tab-content.active{display:block}

.row{display:flex;gap:14px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
.card{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:14px;margin-bottom:12px}
.card h2{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;font-weight:600}
.metric{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.metric .v{font-size:22px;font-weight:700}
.metric .l{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:.5px}
.ok{color:#1a7f37} .warn{color:#9a6700} .err{color:#cf222e} .bl{color:#8250df} .run{color:#0969da}

button{font:inherit;cursor:pointer;padding:7px 14px;border:1px solid #d0d7de;border-radius:5px;background:#fff;color:#222}
button:hover{background:#e8eaed}
button:disabled{opacity:.4;cursor:default}
button.primary{background:#0969da;border-color:#0969da;color:#fff;font-weight:600;padding:8px 18px}
button.primary:hover{background:#0550ae}
button.primary.green{background:#1a7f37;border-color:#1a7f37}
button.primary.green:hover{background:#14632a}
button.danger{color:#cf222e;border-color:#cf222e}
button.danger:hover{background:#fff0f0}
.btnbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.phase{display:inline-block;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.phase-idle{background:#e8eaed;color:#656d76}
.phase-downloading{background:#ddf4ff;color:#0969da}
.phase-validating{background:#f4e8ff;color:#8250df}
.phase-health{background:#dafbe1;color:#1a7f37}
.phase-done{background:#dafbe1;color:#1a7f37}
.phase-paused{background:#fff8c5;color:#9a6700}
.bar{height:8px;background:#e8eaed;border-radius:4px;overflow:hidden;margin:8px 0}
.bar .fill{height:100%;background:linear-gradient(90deg,#0969da,#8250df);transition:width .4s}
.last-proxy{font:12px/1.4 Menlo,Consolas,monospace;color:#1a7f37;margin-top:6px;display:flex;align-items:center;gap:6px}
.flag{font-size:16px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:4px 6px;border-bottom:1px solid #d0d7de}
th{color:#656d76;font-weight:500;font-size:10px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0;background:#f6f8fa}
th.sortable{cursor:pointer;user-select:none}th.sortable:hover{color:#0969da}
tbody tr:hover{background:#eef1f5}
.tbl-wrap{max-height:400px;overflow-y:auto;border-radius:6px}
.addr{font-family:Menlo,Consolas,monospace;color:#0969da;max-width:125px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.live{font:11px/1.4 Menlo,Consolas,monospace;max-height:200px;overflow-y:auto;background:#f6f8fa;border:1px solid #d0d7de;border-radius:5px;padding:6px}
.live div{padding:1px 0}
.live-ts{color:#888;margin-right:6px}
input[type=text],input[type=number]{border:1px solid #d0d7de;padding:5px 8px;border-radius:4px;font:13px inherit;width:100%}
input[type=text]:focus,input[type=number]:focus{outline:none;border-color:#0969da;box-shadow:0 0 0 2px #b6d4fe}
.bl-form{display:flex;gap:6px;margin-bottom:8px}
.empty{color:#888;font-style:italic;padding:14px;text-align:center}
.empty.small{padding:6px;font-size:11px}
.score-bar{display:inline-block;width:40px;height:5px;background:#e8eaed;border-radius:3px;vertical-align:middle;overflow:hidden}
.score-bar .s{height:100%;background:linear-gradient(90deg,#0969da,#8250df)}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:#1a7f37;box-shadow:0 0 0 0 rgba(26,127,55,.5);animation:pulse 1.5s infinite;vertical-align:middle}
.pulse.off{background:#bbb;animation:none;box-shadow:none}
.pulse.run{background:#0969da;box-shadow:0 0 0 0 rgba(9,105,218,.5)}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(26,127,55,.4)}70%{box-shadow:0 0 0 8px rgba(26,127,55,0)}100%{box-shadow:0 0 0 0 rgba(26,127,55,0)}}
.status-bar{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:13px;font-weight:500}
.status-bar.on{background:#dafbe1;border:1px solid #b2dfbe;color:#1a7f37}
.status-bar.off{background:#f6f8fa;border:1px solid #d0d7de;color:#656d76}
.port-input{display:flex;align-items:center;gap:6px}
.port-input input{width:80px}
.sel-proxy{padding:0}
.sel-addr{font:16px/1.3 Menlo,Consolas,monospace;font-weight:700;color:#0969da;margin-bottom:8px;word-break:break-all}
.sel-badges{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.sel-badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}
.sel-country{background:#ddf4ff;color:#0969da}
.sel-proto{background:#f4e8ff;color:#8250df}
.sel-stats{display:flex;gap:24px;flex-wrap:wrap}
</style>
</head>
<body>

<h1>huntproxy</h1>
<div class="sub">
  <span class="pulse off" id="live-dot" style="margin-right:8px"></span>
  <span id="last-event">ready</span>
</div>

<div class="tabs">
  <div class="tab active" data-tab="hunt" onclick="switchTab('hunt')">Hunt</div>
  <div class="tab" data-tab="proxy" onclick="switchTab('proxy')">Proxy</div>
</div>

<!-- ========= TAB: HUNT ========= -->
<div class="tab-content active" id="tab-hunt">
<div class="row">
<div class="col" style="min-width:320px">

 <div class="card">
<h2>control</h2>
<div class="btnbar" style="margin-bottom:10px">
<button class="primary" id="btn-start" onclick="huntStart()">&#9654; Start Hunt</button>
<button class="danger" id="btn-stop" onclick="huntStop()" disabled>&#9632; Stop</button>
</div>
<div class="btnbar" style="margin-bottom:10px;font-size:12px;color:#656d76">
<span>Country:</span>
<select id="country-filter" onchange="setCountry(this.value)" style="font:inherit;padding:3px 6px;border:1px solid #d0d7de;border-radius:4px;background:#fff">
<option value="">ALL</option>
<option value="US">US</option>
<option value="RU">RU</option>
<option value="GB">GB</option>
<option value="DE">DE</option>
<option value="FR">FR</option>
<option value="NL">NL</option>
<option value="CA">CA</option>
<option value="JP">JP</option>
<option value="BR">BR</option>
<option value="IN">IN</option>
<option value="UA">UA</option>
<option value="PL">PL</option>
</select>
</div>
<div style="margin-top:12px">
<div class="metric"><div class="v ok" id="m-alive">0</div><div class="l">alive</div></div>
<div class="metric"><div class="v warn" id="m-dead">0</div><div class="l">dead</div></div>
<div class="metric"><div class="v bl" id="m-bl">0</div><div class="l">blacklist</div></div>
<div class="metric"><div class="v" id="m-total">0</div><div class="l">rated</div></div>
</div>
</div>

<div class="card">
<h2>progress</h2>
<div class="metric"><div class="v" id="p-pct" style="min-width:50px">0%</div><div class="l" id="p-detail">idle</div></div>
<div class="bar"><div class="fill" id="p-bar"></div></div>
<div style="display:flex;justify-content:space-between;font-size:12px;color:#656d76;margin-top:6px">
<span>checked: <b id="p-checked">0</b> / <b id="p-total">0</b></span>
<span>working: <b class="ok" id="p-working">0</b></span>
</div>
<div class="last-proxy" id="last-proxy" style="visibility:hidden">
<span class="flag" id="last-flag">&#x1F3F3;</span>
<span id="last-addr">&mdash;</span>
<span style="color:#656d76;font-size:11px" id="last-country-name"></span>
</div>
</div>

<div class="card">
<h2>log</h2>
<div class="live" id="hunt-log"></div>
</div>
</div>

<div class="col" style="min-width:540px">

<div class="card">
 <h2>top rated alive</h2>
<div class="tbl-wrap">
<table>
<thead><tr>
<th>#</th><th class="sortable" onclick="sortTop('address')">proxy</th><th class="sortable" onclick="sortTop('country')">country</th>      <th class="sortable" onclick="sortTop('last_latency')">latency</th><th class="sortable" onclick="sortTop('latency_avg')">avg</th><th class="sortable" onclick="sortTop('speed_avg')" title="KB/s">KB/s</th><th class="sortable" onclick="sortTop('success_rate')">success</th><th class="sortable" onclick="sortTop('checks_ok')">checks</th><th class="sortable" onclick="sortTop('score')">score</th><th class="sortable" onclick="sortTop('supports_connect')">flags</th><th class="sortable" onclick="sortTop('last_ok')" style="width:48px">ok</th><th></th>
</tr></thead>
<tbody id="top-body"></tbody>
</table>
</div>
</div>

<div class="card">
<h2>blacklist</h2>
<div class="bl-form">
<input type="text" id="bl-input" placeholder="ip:port">
<input type="text" id="bl-reason" placeholder="reason">
<button onclick="blAdd()">+</button>
</div>
<div class="tbl-wrap" style="max-height:200px">
<table>
<thead><tr><th>proxy</th><th>reason</th><th>country</th><th></th></tr></thead>
<tbody id="bl-body"></tbody>
</table>
</div>
</div>

</div>
</div>
</div>

 <!-- ========= TAB: PROXY ========= -->
<div class="tab-content" id="tab-proxy">
<div class="row">
<div class="col" style="min-width:320px">

 <div class="card">
<h2>proxy server</h2>
<div class="status-bar off" id="proxy-status-bar">
  <span class="pulse off" id="proxy-dot"></span>
  <span id="proxy-status-text">stopped</span>
</div>
<div class="port-input" style="margin-bottom:10px">
  <span>Port:</span>
  <input type="number" id="proxy-port" value="17277" min="1024" max="65535">
  <button class="primary green" id="btn-proxy-start" onclick="proxyStart()">&#9654; Start</button>
  <button class="danger" id="btn-proxy-stop" onclick="proxyStop()" disabled>&#9632; Stop</button>
</div>
<div style="margin:6px 0;display:flex;align-items:center;gap:8px">
  <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px">
    <input type="checkbox" id="direct-toggle" onchange="toggleDirect(this.checked)">
    <b>direct mode</b> (no upstream)
  </label>
</div>
<div class="metric"><div class="v run" id="proxy-connections">0</div><div class="l">connections</div></div>
</div>

<div class="card" id="selected-card" style="display:none">
<h2>selected upstream &#x2191;</h2>
<div class="sel-proxy" id="sel-proxy">
  <div class="sel-addr" id="sel-addr"></div>
  <div class="sel-badges" id="sel-badges"></div>
  <div class="sel-geo" id="sel-geo" style="font-size:11px;color:#656d76;margin-bottom:8px;line-height:1.6"></div>
  <div class="sel-stats" id="sel-stats">
     <div class="metric"><div class="v" id="sel-score">-</div><div class="l">score</div></div>
     <div class="metric"><div class="v" id="sel-lat">-</div><div class="l">latency</div></div>
     <div class="metric"><div class="v" id="sel-speed">-</div><div class="l">KB/s</div></div>
     <div class="metric"><div class="v" id="sel-sr">-</div><div class="l">success rate</div></div>
     <div class="metric"><div class="v" id="sel-checks">-</div><div class="l">checks</div></div>
   </div>
   <button onclick="recheckProxy()" style="margin-top:6px;font-size:11px">recheck</button>
   <button onclick="proxySelect('')" style="margin-top:6px;font-size:11px">clear selection</button>
</div>
</div>

<div class="card">
<h2>client log</h2>
<div class="live" id="proxy-log" style="max-height:200px"><div class="empty small">proxy not started</div></div>
</div>
</div>

<div class="col" style="min-width:540px">

<div class="card">
<h2>select upstream proxy</h2>
<div class="tbl-wrap" style="max-height:500px">
<table>
 <thead><tr>
<th>#</th><th class="sortable" onclick="sortProxy('address')">proxy</th><th class="sortable" onclick="sortProxy('country')">country</th>      <th class="sortable" onclick="sortProxy('last_latency')">latency</th><th class="sortable" onclick="sortProxy('latency_avg')">avg</th><th class="sortable" onclick="sortProxy('speed_avg')" title="KB/s">KB/s</th><th class="sortable" onclick="sortProxy('success_rate')">success</th><th class="sortable" onclick="sortProxy('score')">score</th><th class="sortable" onclick="sortProxy('supports_connect')">flags</th><th class="sortable" onclick="sortProxy('last_ok')" style="width:48px">ok</th><th></th>
</tr></thead>
<tbody id="proxy-list-body"></tbody>
</table>
</div>
</div>

</div>
</div>
</div>

<script>
let lastEventSeq=0, huntLogLines=[], proxyLogLines=[];

function flag(c){if(!c||c.length!==2)return'\u{1F3F3}';var b=0x1F1E6-'A'.charCodeAt(0);return String.fromCodePoint(b+c.charCodeAt(0),b+c.charCodeAt(1))}
function ccode(n){var m={};'US=United States|GB=United Kingdom|DE=Germany|FR=France|NL=Netherlands|JP=Japan|CA=Canada|RU=Russia|CN=China|BR=Brazil|ES=Spain|IT=Italy|PL=Poland|UA=Ukraine|IN=India|AU=Australia|SG=Singapore|KR=Korea|MX=Mexico|SE=Sweden|NO=Norway|FI=Finland|CH=Switzerland|HK=Hong Kong'.split('|').forEach(function(x){var p=x.split('=');m[p[1]]=p[0]});return m[n]||''}
function shortCountry(n){return n&&n.length>10?n.substring(0,9)+'\u2026':n}
function fmtTime(t){return new Date(t*1e3).toLocaleTimeString()}

async function api(p,m,g){var o={method:m||'GET',headers:{}};if(g){o.headers['Content-Type']='application/json';o.body=JSON.stringify(g)}return(await fetch(p,o)).json()}

function switchTab(name){document.querySelectorAll('.tab,.tab-content').forEach(function(e){e.classList.toggle('active',e.dataset.tab===name||e.id==='tab-'+name)})}

// ---- HUNT ----
async function huntStart(){var r=await api('/api/hunt/start','POST');if(r.error)alert(r.error)}
async function huntStop(){await api('/api/hunt/stop','POST')}

async function blAdd(){var a=document.getElementById('bl-input').value.trim(),r=document.getElementById('bl-reason').value.trim();if(!a)return;await api('/api/blacklist/add','POST',{address:a,reason:r});document.getElementById('bl-input').value='';document.getElementById('bl-reason').value=''}
async function blRemove(a){await api('/api/blacklist/remove','POST',{address:a})}

// ---- PROXY ----
async function proxyStart(){var p=document.getElementById('proxy-port').value;var s=await api('/api/proxy/start?port='+p,'POST');renderProxy(s)}
async function proxyStop(){var s=await api('/api/proxy/stop','POST');renderProxy(s)}

var _selectedAddr=null;
function renderSelected(ap){
  var card=document.getElementById('selected-card');
  if(!ap){card.style.display='none';_selectedAddr=null;return}
  card.style.display='block';_selectedAddr=ap.address;
  document.getElementById('sel-addr').textContent=ap.address;
  var geoT=geoTitle(ap);
  var geoHtml='';
  if(ap.listen_country) geoHtml+='server: '+flag(ccode(ap.listen_country))+ap.listen_country+(ap.listen_city?', '+ap.listen_city:'')+(ap.listen_isp?', '+ap.listen_isp:'')+'<br>';
  if(ap.egress_isp) geoHtml+='isp: '+ap.egress_isp+'<br>';
  if(ap.egress_ip) geoHtml+='exit ip: '+ap.egress_ip;
  document.getElementById('sel-geo').innerHTML=geoHtml||'\u2014';
  var badges='<span class="sel-badge sel-country">'+flag(ap.country_code)+' '+ap.country+'</span><span class="sel-badge sel-proto">'+ap.protocol+'</span>';
  document.getElementById('sel-badges').innerHTML=badges;
  document.getElementById('sel-score').textContent=ap.score.toFixed(0);
  document.getElementById('sel-lat').textContent=(ap.last_latency||0).toFixed(2)+'s';
  document.getElementById('sel-speed').textContent=(ap.speed_avg||0).toFixed(0);
  document.getElementById('sel-sr').textContent=(ap.success_rate*100).toFixed(0)+'%';
  document.getElementById('sel-checks').textContent=ap.checks_ok+'/'+ap.checks_total;
}

async function proxySelect(a){
  await api('/api/proxy/select?address='+encodeURIComponent(a||''),'POST');
  if(!a){document.getElementById('selected-card').style.display='none';_selectedAddr=null}
  else{var ps=await api('/api/proxy/status');renderSelected(ps.active_proxy)}
}

async function recheckProxy(){
  if(!_selectedAddr)return;
  var btn=event.target; btn.disabled=true; btn.textContent='checking...';
  var r=await api('/api/proxy/recheck?address='+encodeURIComponent(_selectedAddr),'POST');
  btn.disabled=false; btn.textContent='recheck';
  if(r && r.ok){var ps=await api('/api/proxy/status');renderSelected(ps.active_proxy)}
}

function toggleDirect(on){fetch('/api/proxy/direct?on='+(on?'true':'false'),{method:'POST'})}

function renderProxy(s){
var bar=document.getElementById('proxy-status-bar'),dot=document.getElementById('proxy-dot'),txt=document.getElementById('proxy-status-text');
if(s.running){bar.className='status-bar on';dot.className='pulse run';txt.textContent='running on :'+s.port}
else{bar.className='status-bar off';dot.className='pulse off';txt.textContent='stopped'}
document.getElementById('proxy-connections').textContent=s.connections||0;
document.getElementById('btn-proxy-start').disabled=s.running;
document.getElementById('btn-proxy-stop').disabled=!s.running;
document.getElementById('direct-toggle').checked=!!s.direct_mode;
if(s.direct_mode){document.getElementById('selected-card').style.display='none';_selectedAddr=null}
else if(s.active_proxy && s.active_proxy.address!==_selectedAddr) renderSelected(s.active_proxy);
if(!s.direct_mode && !s.active_proxy && _selectedAddr){document.getElementById('selected-card').style.display='none';_selectedAddr=null}

var pl=document.getElementById('proxy-log');
if(s.log && s.log.length){
proxyLogLines=s.log.map(function(e){return '<span class="live-ts">'+fmtTime(e.ts)+'</span> '+e.client+' \u2192 '+e.target+' ['+e.status+']'+(e.upstream&&e.upstream!=='direct'&&e.upstream!=='?'?' <span style="color:#8250df">via '+e.upstream+'</span>':'')});
pl.innerHTML=proxyLogLines.join('<br>');
} else if(!s.running) {pl.innerHTML='<div class="empty small">proxy not started</div>'}
}

function ago(ts){if(!ts)return '\u2014';var d=Date.now()/1000-ts;if(d<60)return Math.floor(d)+'s';if(d<3600)return Math.floor(d/60)+'m';if(d<86400)return Math.floor(d/3600)+'h';return Math.floor(d/86400)+'d'}
function geoTitle(p){var a=[],nl='\n';if(p.egress_isp)a.push('isp: '+p.egress_isp);if(p.listen_country)a.push('server: '+p.listen_country+(p.listen_city?', '+p.listen_city:'')+(p.listen_isp?', '+p.listen_isp:''));if(p.egress_ip)a.push('exit ip: '+p.egress_ip);return a.join(nl)}
var topSortKey='score',topSortDir=-1,proxySortKey='score',proxySortDir=-1;
function sortTop(k){if(topSortKey===k)topSortDir*=-1;else{topSortKey=k;topSortDir=k==='score'||k==='success_rate'?-1:1};poll()}
function sortProxy(k){if(proxySortKey===k)proxySortDir*=-1;else{proxySortKey=k;proxySortDir=k==='score'||k==='success_rate'?-1:1};poll()}
function renderHunt(s){
['m-alive','m-dead','m-bl','m-total'].forEach(function(k,i){document.getElementById(k).textContent=[s.counts.alive,s.counts.dead,s.counts.blacklist,s.counts.ratings][i]});
var b=document.getElementById('phase-badge');if(b){b.textContent=s.phase;b.className='phase phase-'+s.phase}
document.getElementById('last-event').textContent=s.last_event||'\u2014';
document.getElementById('live-dot').className=s.running?'pulse':'pulse off';
document.getElementById('btn-start').disabled=s.running;
document.getElementById('btn-stop').disabled=!s.running;
var p=s.progress,t=p.checking_total||p.downloaded,c=p.checked,x=t>0?Math.round(100*c/t):0;
document.getElementById('p-pct').textContent=x+'%';
document.getElementById('p-checked').textContent=c;
document.getElementById('p-total').textContent=t;
document.getElementById('p-working').textContent=p.working;
document.getElementById('p-bar').style.width=x+'%';
document.getElementById('p-detail').textContent=s.phase;
var lp=document.getElementById('last-proxy');
if(p.last_proxy){lp.style.visibility='visible';document.getElementById('last-addr').textContent=p.last_proxy;var found=s.top_proxies.find(function(x){return x.address===p.last_proxy});document.getElementById('last-flag').textContent=flag(found?found.country_code:'');document.getElementById('last-country-name').textContent=p.last_country}

// top table
var tb=document.getElementById('top-body');
var sorted=s.top_proxies.slice().sort(function(a,b){var va=a[topSortKey],vb=b[topSortKey];if(topSortKey==='address'||topSortKey==='country')return topSortDir*va.localeCompare(vb);return topSortDir*(va-vb)});
tb.innerHTML=sorted.length?sorted.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));var flags=[];if(p.ssl_supported||p.protocol==='https')flags.push('<span style="color:#1a7f37;font-weight:600">HTTPS</span>');else flags.push('<span style="color:#656d76">HTTP</span>');if(p.mitm_suspect)flags.push('<span style="color:#cf222e;font-weight:600">MITM!</span>');var proto=p.protocol||'http';return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+shortCountry(p.country)+(p.listen_country&&p.listen_country!==p.country?' \u2192 '+shortCountry(p.listen_country):'')+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.latency_avg.toFixed(2))+'s</td><td>'+(p.speed_avg||0).toFixed(0)+'</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td>'+p.checks_ok+'/'+p.checks_total+'</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td style="font-size:11px"><span style="color:#8250df">'+proto+'</span> '+flags.join(' ')+'</td><td style="font-size:11px;white-space:nowrap">'+ago(p.last_ok)+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+p.address+'\')">bl</button></td></tr>'}).join(''):'<tr><td colspan="12" class="empty">no alive proxies</td></tr>';

// blacklist
var bb=document.getElementById('bl-body');
bb.innerHTML=s.blacklist.length?s.blacklist.map(function(b){return'<tr><td class="addr">'+b.address+'</td><td style="color:#8250df">'+(b.reason||'\u2014')+'</td><td>'+(b.country||'\u2014')+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+b.address+'\')">\u00d7</button></td></tr>'}).join(''):'<tr><td colspan="4" class="empty">no entries</td></tr>';
}

function renderProxyList(alive){
var tb=document.getElementById('proxy-list-body');
var sorted=alive.slice().sort(function(a,b){var va=a[proxySortKey],vb=b[proxySortKey];if(proxySortKey==='address'||proxySortKey==='country')return proxySortDir*va.localeCompare(vb);return proxySortDir*(va-vb)});
tb.innerHTML=sorted.length?sorted.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));var flags=[];if(p.ssl_supported||p.protocol==='https')flags.push('<span style="color:#1a7f37;font-weight:600">HTTPS</span>');else flags.push('<span style="color:#656d76">HTTP</span>');if(p.mitm_suspect)flags.push('<span style="color:#cf222e;font-weight:600">MITM!</span>');var proto=p.protocol||'http';return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+shortCountry(p.country)+(p.listen_country&&p.listen_country!==p.country?' \u2192 '+shortCountry(p.listen_country):'')+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.latency_avg.toFixed(2))+'s</td><td>'+(p.speed_avg||0).toFixed(0)+'</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td style="font-size:11px"><span style="color:#8250df">'+proto+'</span> '+flags.join(' ')+'</td><td style="font-size:11px;white-space:nowrap">'+ago(p.last_ok)+'</td><td><button style="padding:3px 8px;font-size:11px" onclick="proxySelect(\''+p.address+'\')">select</button></td></tr>'}).join(''):'<tr><td colspan="11" class="empty">no proxies available</td></tr>';
}

function renderLog(ev){
ev.forEach(function(e){lastEventSeq=Math.max(lastEventSeq,e.seq);huntLogLines.unshift('<span class="live-ts">'+fmtTime(e.ts)+'</span> '+e.msg);if(huntLogLines.length>200)huntLogLines.length=200});
document.getElementById('hunt-log').innerHTML=huntLogLines.map(function(l){return'<div>'+l+'</div>'}).join('')}

async function poll(){
try{var s=await api('/api/snapshot');renderHunt(s)}catch(e){}
try{var alive=await api('/api/proxy/alive');renderProxyList(alive)}catch(e){}
try{var ps=await api('/api/proxy/status');renderProxy(ps)}catch(e){}
try{var ev=await api('/api/events?since='+lastEventSeq);if(ev.length)renderLog(ev)}catch(e){}}

poll();setInterval(poll,600);
</script>
</body>
</html>"""
