"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
import yaml
from hunt.constants import CONFIG_PATH, DATA_DIR, STATIC_MIME, WEB_DIR, logger
from hunt.geo import country_code_from_name, country_flag, country_name_from_code
from hunt.models import ProxyRating
from hunt.proxy_runner import ProxyRunner
from hunt.socks5_runner import Socks5Runner
from hunt.state import HuntState
from typing import Optional
from urllib.parse import unquote, urlparse

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

def _qs(path: str) -> dict:
    params = {}
    if "?" in path:
        for p in path.split("?", 1)[1].split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = unquote(v)
    return params

class HuntServer:
    def __init__(self, state: HuntState, host: str, port: int):
        self.state = state
        self.host = host
        self.port = port
        self.proxy = ProxyRunner(state, host)
        self.socks5 = Socks5Runner(state, host)
        if hasattr(state, '_socks5_port'):
            self.socks5.port = state._socks5_port
        self._server: Optional[asyncio.AbstractServer] = None
        if hasattr(state, '_proxy_direct_mode'):
            self.proxy.direct_mode = state._proxy_direct_mode
        if hasattr(state, '_proxy_active_addr') and state._proxy_active_addr:
            self.proxy.active_proxy_addr = state._proxy_active_addr

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle, self.host, self.port)
        addr = self._server.sockets[0].getsockname()
        logger.info(f"Hunt web UI: http://{addr[0]}:{addr[1]}/")
        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        await self.proxy.stop()
        await self.socks5.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
        except Exception:
            writer.close(); return
        if not line:
            writer.close(); return
        try:
            parts = line.split()
            if len(parts) < 2:
                writer.close(); return
            method = parts[0].decode().upper()
            raw_path = parts[1].decode()
            path = raw_path.split("?", 1)[0]
        except Exception:
            writer.close(); return

        headers = {}
        while True:
            try:
                hl = await asyncio.wait_for(reader.readline(), timeout=5)
            except Exception:
                break
            if hl in (b"\r\n", b"\n", b""):
                break
            if b":" in hl:
                k, v = hl.decode(errors="replace").split(":", 1)
                headers[k.strip().lower()] = v.strip()

        cl = int(headers.get("content-length", 0))
        body = b""
        if cl > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(cl), timeout=10)
            except Exception:
                pass

        response, status, ct = await self._route(method, path, raw_path, body)
        await self._write(writer, status, response, ct)
        try:
            writer.close()
        except Exception:
            pass

    async def _write(self, writer, status, body, ct="application/json", cache_control=None):
        if isinstance(body, str):
            body = body.encode()
        if cache_control is None:
            if ct.startswith("image/") or ct == "image/x-icon" or ct == "application/manifest+json" or ct.startswith("text/css") or ct.startswith("application/javascript"):
                cache_control = "public, max-age=86400"
            else:
                cache_control = "no-store"
        resp = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: {ct}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cache-Control: {cache_control}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body
        writer.write(resp)
        try:
            await writer.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, path: str):
        if not WEB_DIR.exists():
            return None
        safe = path.lstrip("/")
        if ".." in safe or safe.startswith("/"):
            return None
        target = WEB_DIR / safe
        try:
            target.resolve().relative_to(WEB_DIR.resolve())
        except ValueError:
            return None
        if not target.exists() or not target.is_file():
            return None
        data = target.read_bytes()
        ext = target.suffix.lower()
        ct = STATIC_MIME.get(ext, "application/octet-stream")
        return data, 200, ct

    async def _route(self, method, path, raw_path, body):
        if path.startswith("/css/") or path.startswith("/js/") or path.startswith("/img/") or path.startswith("/assets/") or path.startswith("/locales/"):
            static = self._serve_static(path)
            if static:
                return static

        if path == "/legacy":
            return WEB_HTML, 200, "text/html; charset=utf-8"

        if path == "/favicon.ico":
            return self._serve_static("assets/favicon.ico")

        if path == "/" or path.startswith("/index"):
            if WEB_DIR.exists() and (WEB_DIR / "index.html").exists():
                return self._serve_static("index.html")
            return WEB_HTML, 200, "text/html; charset=utf-8"

        if path == "/api/snapshot":
            return json.dumps(self.state.get_snapshot()), 200, "application/json"

        if path.startswith("/api/events"):
            qs = _qs(raw_path)
            since = int(qs.get("since", 0))
            events = self.state.events
            new = [e for e in events if e["seq"] > since]
            if not new:
                # short wait for new events
                try:
                    async with self.state._cond:
                        await asyncio.wait_for(self.state._cond.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
                new = [e for e in self.state.events if e["seq"] > since]
            return json.dumps(new), 200, "application/json"

        if path == "/api/hunt/start" and method == "POST":
            ok = self.state.start_hunt()
            self.state._log_action("hunt.start", "ok" if ok else "already-running")
            return json.dumps({"ok": ok, "error": None if ok else "already running"}), 200, "application/json"

        if path == "/api/hunt/stop" and method == "POST":
            self.state._log_action("hunt.stop")
            self.state.stop_hunt()
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/hunt/pause" and method == "POST":
            ok = self.state.pause_hunt(manual=True)
            self.state._log_action("hunt.pause", "ok" if ok else "not-running")
            return json.dumps({"ok": ok, "error": None if ok else "not running or already paused"}), 200, "application/json"

        if path == "/api/hunt/resume" and method == "POST":
            ok = self.state.resume_hunt(manual=True)
            self.state._log_action("hunt.resume", "ok" if ok else "not-paused")
            return json.dumps({"ok": ok, "error": None if ok else "not paused or manual pause requires manual resume"}), 200, "application/json"

        if path == "/api/hunt/skip" and method == "POST":
            ok = self.state.skip_phase()
            self.state._log_action("hunt.skip", "ok" if ok else "not-skippable")
            return json.dumps({"ok": ok, "error": None if ok else "nothing to skip right now"}), 200, "application/json"

        if path == "/api/blacklist/add" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            addr = data.get("address", "")
            self.state.blacklist_add(addr, data.get("reason", ""))
            self.state._log_action("blacklist.add", addr)
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/blacklist/remove" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            addr = data.get("address", "")
            self.state.blacklist_remove(addr)
            self.state._log_action("blacklist.remove", addr)
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/favorites/add" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            addr = data.get("address", "")
            self.state.favorite_add(addr)
            self.state._log_action("favorites.add", addr)
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/favorites/remove" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            addr = data.get("address", "")
            self.state.favorite_remove(addr)
            self.state._log_action("favorites.remove", addr)
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/favorites" and method == "GET":
            favs = [r for r in self.state.ratings.values() if r.is_favorite]
            favs.sort(key=lambda r: r.score, reverse=True)
            return json.dumps([r.to_dict() for r in favs]), 200, "application/json"

        # === Proxy routes ===
        if path == "/api/proxy/status":
            return json.dumps(self.proxy.get_status()), 200, "application/json"

        if path == "/api/proxy/alive":
            # IP-blacklisted proxies are no longer a hard sentence: they can be
            # selected as upstream but with a reduced score. Only operator-curated
            # manual blacklists are excluded here.
            ratings = [r for r in self.state.ratings.values()
                       if r.last_status == "ok" and not r.in_blacklist]
            ratings.sort(key=lambda r: r.score, reverse=True)
            ip_bl_total = len(self.state.get_ip_blacklist_sources())
            result = []
            for r in ratings:
                d = r.to_dict()
                d["ip_blacklist_sources_total"] = ip_bl_total
                result.append(d)
            return json.dumps(result), 200, "application/json"

        if path.startswith("/api/proxy/start"):
            qs = _qs(raw_path)
            port = int(qs.get("port", 17277))
            self.state._log_action("proxy.start", str(port))
            await self.proxy.start(port)
            return json.dumps(self.proxy.get_status()), 200, "application/json"

        if path == "/api/proxy/stop":
            self.state._log_action("proxy.stop")
            await self.proxy.stop()
            self.state._save_state()
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/socks5/status":
            return json.dumps(self.socks5.get_status()), 200, "application/json"

        if path.startswith("/api/socks5/start"):
            qs = _qs(raw_path)
            port = int(qs.get("port", 17278))
            self.state._socks5_port = port
            self.state._save_state()
            self.state._log_action("socks5.start", str(port))
            await self.socks5.start(port)
            return json.dumps(self.socks5.get_status()), 200, "application/json"

        if path == "/api/socks5/stop":
            self.state._log_action("socks5.stop")
            await self.socks5.stop()
            return json.dumps({"ok": True}), 200, "application/json"

        if path.startswith("/api/proxy/select"):
            qs = _qs(raw_path)
            address = qs.get("address") or None
            self.proxy.select(address)
            self.state._proxy_active_addr = self.proxy.active_proxy_addr
            self.state._proxy_direct_mode = self.proxy.direct_mode
            self.state._save_state()
            self.state._log_action("proxy.select", address or "none")
            return json.dumps({"ok": True, "address": address}), 200, "application/json"

        if path == "/api/proxy/next":
            alive = [r for r in self.state.ratings.values()
                     if r.last_status == "ok" and not r.in_blacklist]
            alive.sort(key=lambda r: r.score, reverse=True)
            current = self.proxy.active_proxy_addr
            next_proxy = None
            for r in alive:
                if r.address != current:
                    next_proxy = r
                    break
            if next_proxy:
                self.proxy.select(next_proxy.address)
                self.state._proxy_active_addr = self.proxy.active_proxy_addr
                self.state._save_state()
                self.state._log_action("proxy.next", next_proxy.address)
                return json.dumps({"ok": True, "address": next_proxy.address}), 200, "application/json"
            self.state._log_action("proxy.next", "no-other")
            return json.dumps({"ok": False, "error": "no other alive proxy"}), 200, "application/json"

        if path.startswith("/api/proxy/recheck"):
            qs = _qs(raw_path)
            address = qs.get("address", "").strip()
            self.state._log_action("proxy.recheck", address or "no-addr")
            if address:
                host, port_str = address.rsplit(":", 1)
                port = int(port_str)
                is_socks = port in (1080, 10808, 9050, 4145)
                http_task = asyncio.create_task(self.state._check_proxy(address))
                ssl_task = asyncio.create_task(self.state._check_ssl(address))
                results = await asyncio.gather(http_task, ssl_task, return_exceptions=True)
                if isinstance(results[0], Exception):
                    ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                else:
                    ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                if isinstance(results[1], Exception):
                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
                else:
                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = results[1]
                if not ok and ssl_ok:
                    ok = True
                    country = ssl_country
                    cc = ssl_cc
                    egress = ssl_egress
                    http_latency = ssl_latency
                    supports_connect = ssl_supports_connect
                elif ok and ssl_ok:
                    if not egress and ssl_egress:
                        egress = ssl_egress
                    if not supports_connect and ssl_supports_connect:
                        supports_connect = ssl_supports_connect
                speed = 0.0
                if ok:
                    use_ssl = ssl_ok and not is_socks
                    try:
                        speed = await self.state._measure_speed(host, port, is_socks, use_ssl=use_ssl, supports_connect=supports_connect)
                    except Exception:
                        speed = 0.0
                self.state._update_rating(address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                self.state._save_state()
                self.state._save_working_file()
                return json.dumps({"ok": ok, "address": address}), 200, "application/json"
            return json.dumps({"ok": False, "error": "no address"}), 400, "application/json"

        if path.startswith("/api/proxy/direct"):
            qs = _qs(raw_path)
            en = qs.get("on", "true").lower() != "false"
            self.proxy.direct_mode = en
            if en:
                self.proxy.active_proxy_addr = None
            self.state._proxy_direct_mode = en
            self.state._proxy_active_addr = self.proxy.active_proxy_addr
            self.state._emit(f"Direct mode: {'ON' if en else 'OFF'}", "info")
            self.state._save_state()
            return json.dumps({"ok": True, "direct_mode": en}), 200, "application/json"

        if path.startswith("/api/settings/country_filter") and method == "POST":
            qs = _qs(raw_path)
            code = qs.get("code", "").upper()
            self.state.country_filter = code
            self.state._save_state()
            self.state._emit(f"Country filter set to: {code or 'ALL'}", "info")
            return json.dumps({"ok": True, "country_filter": self.state.country_filter}), 200, "application/json"

        # === Overview / Dashboard endpoints ===
        if path == "/api/countries":
            return json.dumps(self.state.get_countries()), 200, "application/json"

        if path.startswith("/api/system"):
            return json.dumps(self.state._get_system()), 200, "application/json"

        if path.startswith("/api/activity"):
            qs = _qs(raw_path)
            limit = int(qs.get("limit", 10))
            return json.dumps(self.state.get_activity(limit)), 200, "application/json"

        if path.startswith("/api/actions"):
            qs = _qs(raw_path)
            limit = int(qs.get("limit", 100))
            return json.dumps(self.state.get_actions(limit)), 200, "application/json"

        if path.startswith("/api/history"):
            qs = _qs(raw_path)
            last = qs.get("last", "1h")
            return json.dumps(self.state.get_history(last)), 200, "application/json"

        # === Proxies ===
        if path.startswith("/api/proxies"):
            qs = _qs(raw_path)
            status = qs.get("status", "")
            page = int(qs.get("page", 1))
            limit = int(qs.get("limit", 20))
            mode = qs.get("mode", "")
            all_proxies = list(self.state.ratings.values())
            if mode == "grouped":
                sources_map = {}
                for s in self.state.get_proxy_sources():
                    sources_map[s["id"]] = s.get("name", s["id"])
                groups = {}
                if qs.get("group_by") == "source":
                    for r in all_proxies:
                        src_ids = self.state._addr_sources.get(r.address, [])
                        if not src_ids:
                            key = "_unknown"
                            label = "Unknown source"
                        else:
                            key = src_ids[0]
                            label = sources_map.get(key, key)
                        if key not in groups:
                            groups[key] = {"key": key, "label": label, "total": 0, "alive": 0, "dead": 0}
                        groups[key]["total"] += 1
                        if r.last_status == "ok" and not r.in_blacklist:
                            groups[key]["alive"] += 1
                        else:
                            groups[key]["dead"] += 1
                elif qs.get("group_by") == "protocol":
                    for r in all_proxies:
                        proto = r.protocol or "http"
                        if proto in ("socks5", "socks4"):
                            key = proto
                        elif proto == "https" or r.ssl_supported:
                            key = "https"
                        else:
                            key = "http"
                        labels = {"http": "HTTP", "https": "HTTPS", "socks4": "SOCKS4", "socks5": "SOCKS5"}
                        if key not in groups:
                            groups[key] = {"key": key, "label": labels.get(key, key.upper()), "total": 0, "alive": 0, "dead": 0}
                        groups[key]["total"] += 1
                        if r.last_status == "ok" and not r.in_blacklist:
                            groups[key]["alive"] += 1
                        else:
                            groups[key]["dead"] += 1
                else:
                    for r in all_proxies:
                        cc = r.country_code or country_code_from_name(r.country) or "??"
                        if cc not in groups:
                            groups[cc] = {"key": cc, "label": f"{country_flag(cc)} {country_name_from_code(cc)}", "total": 0, "alive": 0, "dead": 0}
                        groups[cc]["total"] += 1
                        if r.last_status == "ok" and not r.in_blacklist:
                            groups[cc]["alive"] += 1
                        else:
                            groups[cc]["dead"] += 1
                result = []
                for g in groups.values():
                    g["alive_pct"] = round(g["alive"] / g["total"] * 100, 1) if g["total"] else 0
                    if status == "alive" and g["alive"] == 0:
                        continue
                    elif status == "dead" and g["dead"] == 0:
                        continue
                    result.append(g)
                result.sort(key=lambda g: g["alive"], reverse=True)
                return json.dumps({"groups": result, "total": len(all_proxies)}), 200, "application/json"
            if mode == "group-proxies":
                group_key = qs.get("group_key", "")
                group_by = qs.get("group_by", "country")
                group_status = qs.get("status", "")
                all_ratings = list(self.state.ratings.values())
                sources_map = {}
                for s in self.state.get_proxy_sources():
                    sources_map[s["id"]] = s.get("name", s["id"])
                if group_by == "source":
                    filtered = [r for r in all_ratings if (
                        (self.state._addr_sources.get(r.address, []) or ["_unknown"])[0] == group_key
                    )]
                elif group_by == "protocol":
                    def _proto_key(r):
                        proto = r.protocol or "http"
                        if proto in ("socks5", "socks4"):
                            return proto
                        if proto == "https" or r.ssl_supported:
                            return "https"
                        return "http"
                    filtered = [r for r in all_ratings if _proto_key(r) == group_key]
                else:
                    filtered = [r for r in all_ratings if (r.country_code or country_code_from_name(r.country) or "??") == group_key]
                if group_status == "alive":
                    filtered = [r for r in filtered if r.last_status == "ok" and not r.in_blacklist]
                elif group_status == "dead":
                    filtered = [r for r in filtered if r.last_status == "failed"]
                elif group_status == "blacklisted":
                    filtered = [r for r in filtered if r.is_blacklisted]
                filtered.sort(key=lambda r: r.score, reverse=True)
                return json.dumps({"proxies": [r.to_dict() for r in filtered]}), 200, "application/json"
            filtered_proxies = all_proxies
            if status == "alive":
                filtered_proxies = [r for r in filtered_proxies if r.last_status == "ok" and not r.in_blacklist]
            elif status == "dead":
                filtered_proxies = [r for r in filtered_proxies if r.last_status == "failed"]
            elif status == "blacklisted":
                filtered_proxies = [r for r in filtered_proxies if r.is_blacklisted]
            total = len(filtered_proxies)
            start = (page - 1) * limit
            end = start + limit
            page_data = filtered_proxies[start:end]
            proxy_list = []
            for r in page_data:
                d = r.to_dict()
                d["source_ids"] = self.state._addr_sources.get(r.address, [])
                proxy_list.append(d)
            return json.dumps({
                "total": total,
                "page": page,
                "limit": limit,
                "proxies": proxy_list,
            }), 200, "application/json"

        if path.startswith("/api/proxy-checks/") and method == "GET":
            addr = path[len("/api/proxy-checks/"):]
            addr = unquote(addr)
            qs = _qs(raw_path)
            limit = int(qs.get("limit", 30))
            data = self.state.get_proxy_checks(addr, limit)
            return json.dumps(data), 200, "application/json"

        if path.startswith("/api/proxy-heatmap") and method == "GET":
            qs = _qs(raw_path)
            hours = int(qs.get("hours", 72))
            data = self.state.get_proxy_heatmap(hours)
            return json.dumps(data), 200, "application/json"

        if path.startswith("/api/proxy/") and method == "GET":
            addr = path[len("/api/proxy/"):]
            addr = unquote(addr)
            r = self.state.ratings.get(addr)
            if r:
                d = r.to_dict()
                d["source_ids"] = self.state._addr_sources.get(r.address, [])
                total_sources = len(self.state.get_proxy_sources())
                d["sources_total"] = total_sources
                d["ip_blacklist_sources_total"] = len(self.state.get_ip_blacklist_sources())
                return json.dumps(d), 200, "application/json"
            return json.dumps({"error": "not found"}), 404, "application/json"

        # === Blacklist ===
        if path.startswith("/api/blacklist"):
            qs = _qs(raw_path)
            page = int(qs.get("page", 1))
            limit = int(qs.get("limit", 20))
            bl = self.state._blacklist_view()
            total = len(bl)
            start = (page - 1) * limit
            end = start + limit
            return json.dumps({
                "total": total,
                "page": page,
                "limit": limit,
                "blacklist": bl[start:end],
            }), 200, "application/json"

        # === Actions ===
        if path.startswith("/api/clear_dead") and method == "POST":
            dead_addrs = [a for a, r in self.state.ratings.items()
                          if r.last_status == "failed" and not r.is_favorite and not r.in_grace]
            for a in dead_addrs:
                del self.state.ratings[a]
            self.state._emit(f"Cleared {len(dead_addrs)} dead proxies", "warn")
            self.state._save_state()
            self.state._save_working_file()
            self.state._log_action("clear_dead", f"{len(dead_addrs)} proxies")
            return json.dumps({"ok": True, "cleared": len(dead_addrs)}), 200, "application/json"

        if path.startswith("/api/export") and method == "POST":
            alive = [r for r in self.state.ratings.values()
                     if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
            alive.sort(key=lambda r: r.score, reverse=True)
            data = "\n".join(f"{r.address}  {r.country}  {r.last_latency:.3f}" for r in alive)
            return json.dumps({"ok": True, "data": data}), 200, "application/json"

        if path.startswith("/api/import") and method == "POST":
            try:
                data = json.loads(body or b"{}")
                lines = data.get("proxies", [])
                mark_favorite = bool(data.get("favorite", False))
                added = 0
                favorited = 0
                for line in lines:
                    line = line.strip() if isinstance(line, str) else str(line).strip()
                    if not line or line.startswith("#"):
                        continue
                    # working.txt / export format: "address  country  latency"
                    # — take only the first whitespace-separated token.
                    addr = line.split()[0] if line.split() else ""
                    if not addr or ":" not in addr:
                        continue
                    is_new = addr not in self.state.ratings and addr not in self.state.blacklist
                    if is_new:
                        self.state.ratings[addr] = ProxyRating(
                            address=addr, first_seen=time.time(),
                            last_check=time.time(), checks_total=1, checks_ok=1,
                            last_status="ok")
                        added += 1
                    if mark_favorite and addr not in self.state.favorites:
                        self.state.favorite_add(addr)
                        favorited += 1
                msg = f"Imported {added} proxies"
                if mark_favorite:
                    msg += f", favorited {favorited}"
                self.state._emit(msg, "info")
                self.state._save_state()
                self.state._save_working_file()
                result = {"ok": True, "added": added}
                if mark_favorite:
                    result["favorited"] = favorited
                return json.dumps(result), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        if path.startswith("/api/health/start") and method == "POST":
            try:
                if self.state._health_running:
                    self.state._log_action("health.start", "already-running")
                    return json.dumps({"ok": False, "error": "already_running"}), 409, "application/json"
                self.state._log_action("health.start", "recheck-all")
                self.state._health_task = asyncio.create_task(self.state._health_check(manual=True))
                return json.dumps({"ok": True}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

        if path.startswith("/api/health/stop") and method == "POST":
            try:
                if not self.state._health_running:
                    return json.dumps({"ok": False, "error": "not_running"}), 409, "application/json"
                self.state._log_action("health.stop", "abort-recheck")
                self.state.stop_health()
                return json.dumps({"ok": True}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

        # === Settings ===
        if path.startswith("/api/settings") and method == "GET":
            if not CONFIG_PATH.exists():
                return json.dumps({"error": "config not found"}), 404, "application/json"
            with open(CONFIG_PATH) as f:
                cfg = yaml.safe_load(f)
            return json.dumps(cfg or {}), 200, "application/json"

        if path.startswith("/api/settings") and method == "POST":
            try:
                data = json.loads(body or b"{}")
                with open(CONFIG_PATH, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                self.state._emit("Settings updated", "info")
                return json.dumps({"ok": True}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        # === Logs ===
        if path.startswith("/api/logs"):
            qs = _qs(raw_path)
            limit = int(qs.get("limit", 200))
            event_type = qs.get("type", "")
            events = self.state.get_events(limit, event_type or None)
            return json.dumps({"events": events}), 200, "application/json"

        # === Downloads ===
        if path.startswith("/api/downloads/count") and method == "GET":
            counts = self.state.get_download_counts()
            return json.dumps(counts), 200, "application/json"

        if path.startswith("/api/download/"):
            filename = path[len("/api/download/"):]
            filename = unquote(filename)
            allowed = ("working.txt", "blacklist.txt", "ip_blacklist.txt", "ratings.json", "config.yaml")
            if filename not in allowed:
                return json.dumps({"error": "forbidden"}), 403, "application/json"
            try:
                data = self.state.generate_download(filename)
            except FileNotFoundError:
                return json.dumps({"error": "not found"}), 404, "application/json"
            except Exception as e:
                return json.dumps({"error": str(e)}), 500, "application/json"
            ct = "application/octet-stream"
            if filename.endswith(".txt"):
                ct = "text/plain; charset=utf-8"
            elif filename.endswith(".json"):
                ct = "application/json"
            elif filename.endswith(".yaml"):
                ct = "text/yaml"
            return data, 200, ct

        # === Backup / Restore ===
        if path.startswith("/api/backup/groups") and method == "GET":
            return json.dumps({"groups": self.state.get_backup_groups()}), 200, "application/json"

        if path.startswith("/api/backup") and method == "POST":
            try:
                payload = json.loads(body or b"{}")
                groups = payload.get("groups", [])
                if not groups:
                    return json.dumps({"error": "no groups selected"}), 400, "application/json"
                data = self.state.create_backup(groups)
                self.state._log_action("backup", f"groups: {','.join(groups)}")
                ts = time.strftime("%Y%m%d_%H%M%S")
                return data, 200, "application/json"
            except Exception as e:
                return json.dumps({"error": str(e)}), 500, "application/json"

        if path.startswith("/api/restore") and method == "POST":
            try:
                payload = json.loads(body or b"{}")
                groups = payload.get("groups", [])
                backup_data = payload.get("data", "")
                if not groups:
                    return json.dumps({"error": "no groups selected"}), 400, "application/json"
                if not backup_data:
                    return json.dumps({"error": "no backup data"}), 400, "application/json"
                result = self.state.restore_backup(
                    backup_data.encode() if isinstance(backup_data, str) else backup_data,
                    groups,
                )
                if result.get("ok"):
                    self.state._log_action("restore", f"groups: {','.join(groups)}")
                return json.dumps(result), 200 if result.get("ok") else 400, "application/json"
            except Exception as e:
                return json.dumps({"error": str(e)}), 500, "application/json"

        # === Proxy Control / Traffic stubs (Phase 2) ===
        if path.startswith("/api/traffic/live"):
            return json.dumps(self.state.get_live_traffic()), 200, "application/json"

        if path.startswith("/api/traffic"):
            return json.dumps({"points": self.state.get_history("24h")}), 200, "application/json"

        if path.startswith("/api/requests"):
            mem = list(self.proxy.log)[-50:]
            try:
                conn = self.state._stats_db()
                rows = conn.execute("SELECT ts, client, target, status, upstream, bytes_in, bytes_out, duration FROM traffic_log ORDER BY id DESC LIMIT 50").fetchall()
                conn.close()
                db_reqs = [dict(r) for r in rows]
            except Exception:
                db_reqs = []
            reqs = db_reqs if db_reqs else mem
            return json.dumps({"requests": reqs}), 200, "application/json"

        if path.startswith("/api/clients"):
            clients = {}
            try:
                conn = self.state._stats_db()
                rows = conn.execute("SELECT client, COUNT(*) as requests, MAX(ts) as last_seen FROM traffic_log GROUP BY client ORDER BY requests DESC LIMIT 20").fetchall()
                conn.close()
                for r in rows:
                    clients[r["client"]] = {"client": r["client"], "requests": r["requests"], "last_seen": r["last_seen"]}
            except Exception:
                for entry in self.proxy.log:
                    c = entry.get("client", "?")
                    if c not in clients:
                        clients[c] = {"client": c, "requests": 0, "last_seen": entry.get("ts", 0)}
                    clients[c]["requests"] += 1
                    clients[c]["last_seen"] = max(clients[c]["last_seen"], entry.get("ts", 0))
            return json.dumps({"clients": sorted(clients.values(), key=lambda x: x["requests"], reverse=True)[:20]}), 200, "application/json"

        if path.startswith("/api/domains"):
            domains = {}
            try:
                conn = self.state._stats_db()
                rows = conn.execute("SELECT target, COUNT(*) as requests FROM traffic_log WHERE client != '?' GROUP BY target ORDER BY requests DESC LIMIT 50").fetchall()
                conn.close()
                for r in rows:
                    t = r["target"]
                    try:
                        h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                    except Exception:
                        h = t
                    if not h:
                        continue
                    if h not in domains:
                        domains[h] = {"domain": h, "requests": 0}
                    domains[h]["requests"] += r["requests"]
            except Exception:
                for entry in self.proxy.log:
                    t = entry.get("target", "")
                    try:
                        h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                    except Exception:
                        h = t
                    if not h:
                        continue
                    if h not in domains:
                        domains[h] = {"domain": h, "requests": 0}
                    domains[h]["requests"] += 1
            top = sorted(domains.values(), key=lambda x: x["requests"], reverse=True)[:10]
            total = sum(d["requests"] for d in top) or 1
            for d in top:
                d["pct"] = round(d["requests"] / total * 100, 1)
            return json.dumps({"domains": top}), 200, "application/json"

        if path.startswith("/api/errors"):
            errors = {"timeout": 0, "connect_failed": 0, "4xx": 0, "5xx": 0, "other": 0}
            try:
                conn = self.state._stats_db()
                rows = conn.execute("SELECT status, COUNT(*) as cnt FROM traffic_log WHERE status != 'ok' GROUP BY status").fetchall()
                conn.close()
                for r in rows:
                    st = r["status"]
                    cnt = r["cnt"]
                    if "timeout" in st.lower():
                        errors["timeout"] += cnt
                    elif "connect" in st.lower() or "fail" in st.lower():
                        errors["connect_failed"] += cnt
                    elif st.startswith("4"):
                        errors["4xx"] += cnt
                    elif st.startswith("5") or st.startswith("502") or st.startswith("503"):
                        errors["5xx"] += cnt
                    else:
                        errors["other"] += cnt
            except Exception:
                for entry in self.proxy.log:
                    st = entry.get("status", "")
                    if "timeout" in st.lower():
                        errors["timeout"] += 1
                    elif "connect" in st.lower() or "fail" in st.lower():
                        errors["connect_failed"] += 1
                    elif st.startswith("4"):
                        errors["4xx"] += 1
                    elif st.startswith("5") or st.startswith("502") or st.startswith("503"):
                        errors["5xx"] += 1
                    else:
                        errors["other"] += 1
            total = sum(errors.values()) or 1
            result = []
            for k, v in errors.items():
                if v:
                    result.append({"type": k, "count": v, "pct": round(v / total * 100, 1)})
            return json.dumps({"errors": result, "total": total}), 200, "application/json"

        if path.startswith("/api/traffic/routes"):
            routes = {}
            try:
                conn = self.state._stats_db()
                cutoff = time.time() - 86400
                rows = conn.execute(
                    "SELECT upstream, COUNT(*) as cnt, "
                    "COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout, "
                    "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) as ok, "
                    "COALESCE(AVG(duration),0) as avg_dur "
                    "FROM traffic_log WHERE ts > ? GROUP BY upstream ORDER BY cnt DESC",
                    (cutoff,)
                ).fetchall()
                conn.close()
                for r in rows:
                    up = r["upstream"] or "unknown"
                    rtype = "other"
                    if up == "direct" or up.startswith("direct"):
                        rtype = "direct"
                    elif up.startswith("proxy:"):
                        rtype = "proxy"
                    elif up.startswith("pool:"):
                        rtype = "pool"
                    elif up.startswith("custom:"):
                        rtype = "custom"
                    if rtype not in routes:
                        routes[rtype] = {"type": rtype, "requests": 0, "bytes_in": 0, "bytes_out": 0, "ok": 0, "avg_duration": 0, "_dur_sum": 0, "upstreams": []}
                    rt = routes[rtype]
                    rt["requests"] += r["cnt"]
                    rt["bytes_in"] += r["bin"]
                    rt["bytes_out"] += r["bout"]
                    rt["ok"] += r["ok"]
                    rt["_dur_sum"] += r["avg_dur"] * r["cnt"]
                    rt["upstreams"].append({"upstream": up, "requests": r["cnt"]})
            except Exception:
                pass
            result = []
            for rt in routes.values():
                cnt = rt["requests"] or 1
                result.append({
                    "type": rt["type"],
                    "requests": rt["requests"],
                    "bytes_in": rt["bytes_in"],
                    "bytes_out": rt["bytes_out"],
                    "success_rate": round(rt["ok"] / cnt * 100, 1),
                    "avg_duration": round(rt["_dur_sum"] / cnt, 3),
                    "upstreams": sorted(rt["upstreams"], key=lambda x: x["requests"], reverse=True)[:5],
                })
            result.sort(key=lambda x: x["requests"], reverse=True)
            return json.dumps({"routes": result}), 200, "application/json"

        if path.startswith("/api/bandwidth"):
            try:
                conn = self.state._stats_db()
                row = conn.execute(
                    "SELECT COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout "
                    "FROM traffic_log WHERE ts > ?",
                    (time.time() - 86400,)
                ).fetchone()
                conn.close()
                upload = row["bin"] if row else 0    # bytes_in  = client→upstream = upload
                download = row["bout"] if row else 0  # bytes_out = upstream→client = download
            except Exception:
                upload = 0
                download = 0
            return json.dumps({
                "download": download,
                "upload": upload,
                "total": download + upload,
            }), 200, "application/json"

        if path.startswith("/api/traffic/summary"):
            periods = {"day": 86400, "week": 604800, "month": 2592000}
            result = {}
            try:
                conn = self.state._stats_db()
                now = time.time()
                for name, secs in periods.items():
                    cutoff = now - secs
                    row = conn.execute(
                        "SELECT COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout, "
                        "COUNT(*) as reqs, "
                        "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) as ok "
                        "FROM traffic_log WHERE ts > ?",
                        (cutoff,)
                    ).fetchone()
                    download = int(row["bout"] or 0)
                    upload = int(row["bin"] or 0)
                    total = download + upload
                    reqs = int(row["reqs"] or 0)
                    ok = int(row["ok"] or 0)
                    result[name] = {
                        "download": download,
                        "upload": upload,
                        "total": total,
                        "requests": reqs,
                        "success": ok,
                        "failed": reqs - ok,
                        "success_rate": round(ok / reqs * 100, 1) if reqs else 0,
                    }
                    # Per-route breakdown for this period
                    route_rows = conn.execute(
                        "SELECT upstream, COUNT(*) as cnt, "
                        "COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout "
                        "FROM traffic_log WHERE ts > ? GROUP BY upstream ORDER BY cnt DESC LIMIT 5",
                        (cutoff,)
                    ).fetchall()
                    routes = []
                    for rr in route_rows:
                        up = rr["upstream"] or "unknown"
                        rtype = "other"
                        if up == "direct" or up.startswith("direct"): rtype = "direct"
                        elif up.startswith("proxy:"): rtype = "proxy"
                        elif up.startswith("pool:"): rtype = "pool"
                        elif up.startswith("custom:"): rtype = "custom"
                        routes.append({
                            "type": rtype,
                            "upstream": up,
                            "requests": int(rr["cnt"]),
                            "bytes": int(rr["bout"] or 0) + int(rr["bin"] or 0),
                        })
                    result[name]["top_routes"] = routes
                conn.close()
            except Exception as e:
                logger.error("traffic/summary: %s", e)
                for name in periods:
                    if name not in result:
                        result[name] = {"download": 0, "upload": 0, "total": 0, "requests": 0, "success": 0, "failed": 0, "success_rate": 0, "top_routes": []}
            return json.dumps(result), 200, "application/json"

        # === Routing API ===
        if path == "/api/routing/status":
            return json.dumps(self.state.get_routing_status()), 200, "application/json"

        if path == "/api/routing/enable" and method == "POST":
            self.state.routing_enable()
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/routing/disable" and method == "POST":
            self.state.routing_disable()
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/routing/default" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            route = data.get("default_route", "direct")
            self.state.routing_set_default(route)
            return json.dumps({"ok": True, "default_route": route}), 200, "application/json"

        if path == "/api/routing/reorder" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            order = data.get("order", [])
            if order:
                self.state.reorder_domain_lists(order)
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/routing/test" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            domain = data.get("domain", "").strip()
            if not domain:
                return json.dumps({"error": "domain is required"}), 400, "application/json"
            result = self.state.routing_test(domain)
            return json.dumps(result), 200, "application/json"

        # === Domain Lists API ===
        if path == "/api/domain-lists" and method == "GET":
            lists = self.state.get_domain_lists()
            return json.dumps({"lists": lists}), 200, "application/json"

        if path == "/api/domain-lists" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = self.state.create_domain_list(data)
            if result:
                return json.dumps({"ok": True, "list": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "id and name are required"}), 400, "application/json"

        if path.startswith("/api/domain-lists/") and not path.endswith("/toggle"):
            list_id = unquote(path[len("/api/domain-lists/"):])
            if method == "GET":
                result = self.state.get_domain_list(list_id)
                if result:
                    return json.dumps(result), 200, "application/json"
                return json.dumps({"error": "not found"}), 404, "application/json"
            elif method == "POST":
                try:
                    data = json.loads(body or b"{}")
                except Exception:
                    data = {}
                result = self.state.update_domain_list(list_id, data)
                if result:
                    return json.dumps({"ok": True, "list": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            elif method == "DELETE":
                ok = self.state.delete_domain_list(list_id)
                if ok:
                    return json.dumps({"ok": True}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/toggle") and path.startswith("/api/domain-lists/"):
            list_id = unquote(path[len("/api/domain-lists/"):-len("/toggle")])
            if method == "POST":
                result = self.state.toggle_domain_list(list_id)
                if result:
                    return json.dumps({"ok": True, "list": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        # === Proxy Sources API ===
        if path == "/api/proxy-sources" and method == "GET":
            sources = self.state.get_proxy_sources()
            return json.dumps({"sources": sources}), 200, "application/json"

        if path == "/api/proxy-sources" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = self.state.create_proxy_source(data)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

        if path == "/api/proxy-sources/fetch" and method == "POST":
            if getattr(self.state, '_fetching_sources', False):
                return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
            self.state._fetching_sources = True
            try:
                seen = await self.state._download_sources()
                self.state._update_source_stats()
                sources = self.state.get_proxy_sources()
                results = []
                for s in sources:
                    if not s.get("enabled"):
                        continue
                    results.append({
                        "id": s["id"],
                        "name": s.get("name", s["id"]),
                        "status": s.get("last_fetch_status", ""),
                        "count": s.get("last_fetch_count", 0),
                        "error": s.get("last_fetch_error", ""),
                    })
                return json.dumps({"ok": True, "total_addresses": len(seen), "sources": results}), 200, "application/json"
            except Exception as e:
                logger.error("proxy-sources/fetch: %s", e)
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"
            finally:
                self.state._fetching_sources = False

        if path == "/api/proxy-sources/progress" and method == "GET":
            return json.dumps({"progress": self.state.get_proxy_source_fetch_progress()}), 200, "application/json"

        if path.startswith("/api/proxy-sources/") and not path.endswith("/toggle"):
            source_id = unquote(path[len("/api/proxy-sources/"):])
            if method == "GET":
                result = self.state.get_proxy_source(source_id)
                if result:
                    return json.dumps(result), 200, "application/json"
                return json.dumps({"error": "not found"}), 404, "application/json"
            elif method == "POST":
                try:
                    data = json.loads(body or b"{}")
                except Exception:
                    data = {}
                result = self.state.update_proxy_source(source_id, data)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            elif method == "DELETE":
                ok = self.state.delete_proxy_source(source_id)
                if ok:
                    return json.dumps({"ok": True}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/toggle") and path.startswith("/api/proxy-sources/"):
            source_id = unquote(path[len("/api/proxy-sources/"):-len("/toggle")])
            if method == "POST":
                result = self.state.toggle_proxy_source(source_id)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        # === IP Blacklist Sources API ===
        if path == "/api/ip-blacklists" and method == "GET":
            sources = self.state.get_ip_blacklist_sources()
            return json.dumps({"sources": sources}), 200, "application/json"

        if path == "/api/ip-blacklists" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = self.state.create_ip_blacklist_source(data)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

        if path == "/api/ip-blacklists/fetch" and method == "POST":
            if getattr(self.state, '_fetching_ip_blacklists', False):
                return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
            self.state._fetching_ip_blacklists = True
            try:
                results = await self.state._download_ip_blacklists()
                total = sum(results.values())
                return json.dumps({"ok": True, "total_entries": total, "sources": [{"id": k, "count": v} for k, v in results.items()]}), 200, "application/json"
            except Exception as e:
                logger.error("ip-blacklists/fetch: %s", e)
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"
            finally:
                self.state._fetching_ip_blacklists = False

        if path == "/api/ip-blacklists/progress" and method == "GET":
            return json.dumps({"progress": self.state.get_ip_blacklist_fetch_progress()}), 200, "application/json"

        if path.startswith("/api/ip-blacklists/") and not path.endswith("/toggle") and not path.endswith("/fetch"):
            source_id = unquote(path[len("/api/ip-blacklists/"):])
            if method == "GET":
                result = self.state.get_ip_blacklist_source(source_id)
                if result:
                    return json.dumps(result), 200, "application/json"
                return json.dumps({"error": "not found"}), 404, "application/json"
            elif method == "POST":
                try:
                    data = json.loads(body or b"{}")
                except Exception:
                    data = {}
                result = self.state.update_ip_blacklist_source(source_id, data)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            elif method == "DELETE":
                ok = self.state.delete_ip_blacklist_source(source_id)
                if ok:
                    return json.dumps({"ok": True}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/toggle") and path.startswith("/api/ip-blacklists/"):
            source_id = unquote(path[len("/api/ip-blacklists/"):-len("/toggle")])
            if method == "POST":
                result = self.state.toggle_ip_blacklist_source(source_id)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path == "/api/ip-blacklist/entries" and method == "GET":
            qs = _qs(raw_path)
            page = int(qs.get("page", 1))
            limit = int(qs.get("limit", 50))
            entries = sorted(self.state.ip_blacklist_entries.items())
            total = len(entries)
            start = (page - 1) * limit
            end = start + limit
            page_entries = []
            for entry, metas in entries[start:end]:
                for meta in metas:
                    page_entries.append({
                        "entry": entry,
                        "source_id": meta.get("source_id"),
                        "source_name": meta.get("source_name"),
                        "reason": meta.get("reason", ""),
                    })
            return json.dumps({"total": total, "page": page, "limit": limit, "entries": page_entries}), 200, "application/json"

        if path == "/api/ip-blacklist/matches" and method == "GET":
            matches = self.state.get_ip_blacklist_matches()
            return json.dumps({"matches": matches, "total": len(matches)}), 200, "application/json"

        # === Country Blocklists API ===
        if path == "/api/blocklists" and method == "GET":
            sources = self.state.get_blocklist_sources()
            return json.dumps({"sources": sources}), 200, "application/json"

        if path == "/api/blocklists" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = self.state.create_blocklist_source(data)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

        if path == "/api/blocklists/fetch" and method == "POST":
            if getattr(self.state, '_fetching_blocklists', False):
                return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
            try:
                results = await self.state._download_blocklists()
                total = sum(results.values())
                return json.dumps({"ok": True, "total_entries": total, "sources": [{"id": k, "count": v} for k, v in results.items()]}), 200, "application/json"
            except Exception as e:
                logger.error("blocklists/fetch: %s", e)
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

        if path == "/api/blocklists/progress" and method == "GET":
            return json.dumps({"progress": self.state.get_blocklist_fetch_progress()}), 200, "application/json"

        if path.startswith("/api/blocklists/") and not path.endswith("/toggle") and not path.endswith("/fetch"):
            source_id = unquote(path[len("/api/blocklists/"):])
            if method == "GET":
                result = self.state.get_blocklist_source(source_id)
                if result:
                    return json.dumps(result), 200, "application/json"
                return json.dumps({"error": "not found"}), 404, "application/json"
            elif method == "POST":
                try:
                    data = json.loads(body or b"{}")
                except Exception:
                    data = {}
                result = self.state.update_blocklist_source(source_id, data)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            elif method == "DELETE":
                ok = self.state.delete_blocklist_source(source_id)
                if ok:
                    return json.dumps({"ok": True}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/toggle") and path.startswith("/api/blocklists/"):
            source_id = unquote(path[len("/api/blocklists/"):-len("/toggle")])
            if method == "POST":
                result = self.state.toggle_blocklist_source(source_id)
                if result:
                    return json.dumps({"ok": True, "source": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        # === Custom Proxies API ===
        if path == "/api/custom-proxies" and method == "GET":
            proxies = self.state.get_custom_proxies()
            return json.dumps({"proxies": proxies}), 200, "application/json"

        if path == "/api/custom-proxies" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = self.state.create_custom_proxy(data)
            if result:
                return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "id, name, host and port are required"}), 400, "application/json"

        if path == "/api/custom-proxies/test-direct" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            result = await self.state.test_proxy_direct(data)
            return json.dumps(result), 200, "application/json"

        if path.startswith("/api/custom-proxies/") and not path.endswith("/toggle") and not path.endswith("/test") and path != "/api/custom-proxies/test-direct":
            proxy_id = unquote(path[len("/api/custom-proxies/"):])
            if method == "GET":
                result = self.state.get_custom_proxy(proxy_id)
                if result:
                    return json.dumps(result), 200, "application/json"
                return json.dumps({"error": "not found"}), 404, "application/json"
            elif method == "POST":
                try:
                    data = json.loads(body or b"{}")
                except Exception:
                    data = {}
                result = self.state.update_custom_proxy(proxy_id, data)
                if result:
                    return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            elif method == "DELETE":
                ok = self.state.delete_custom_proxy(proxy_id)
                if ok:
                    return json.dumps({"ok": True}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/toggle") and path.startswith("/api/custom-proxies/"):
            proxy_id = unquote(path[len("/api/custom-proxies/"):-len("/toggle")])
            if method == "POST":
                result = self.state.toggle_custom_proxy(proxy_id)
                if result:
                    return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

        if path.endswith("/test") and path.startswith("/api/custom-proxies/"):
            proxy_id = unquote(path[len("/api/custom-proxies/"):-len("/test")])
            if method == "POST":
                result = await self.state.test_custom_proxy(proxy_id)
                return json.dumps(result), 200, "application/json"

        # === Scheduler ===
        if path == "/api/schedules" and method == "GET":
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"schedules": [], "status": {"running": False, "paused": False, "running_tasks": []}}), 200, "application/json"
            return json.dumps({"schedules": sched.list_schedules(), "status": sched.get_status()}), 200, "application/json"

        if path == "/api/schedules" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            try:
                result = await sched.add_schedule(
                    sid=data.get("id", ""),
                    name=data.get("name", ""),
                    task_type=data.get("task_type", ""),
                    interval_sec=int(data.get("interval_sec", 3600)),
                    config=data.get("config", {}),
                    enabled=data.get("enabled", True),
                )
                self.state._log_action("schedule.add", data.get("id", ""))
                return json.dumps({"ok": True, "schedule": result}), 200, "application/json"
            except ValueError as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        if path.startswith("/api/schedules/status") and method == "GET":
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"running": False, "paused": False, "running_tasks": []}), 200, "application/json"
            return json.dumps(sched.get_status()), 200, "application/json"

        if path == "/api/schedules/pause" and method == "POST":
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            sched.pause_all()
            self.state._log_action("schedule.pause_all")
            return json.dumps({"ok": True, "paused": True}), 200, "application/json"

        if path == "/api/schedules/resume" and method == "POST":
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            sched.resume_all()
            self.state._log_action("schedule.resume_all")
            return json.dumps({"ok": True, "paused": False}), 200, "application/json"

        if path.startswith("/api/schedules/") and path.endswith("/toggle") and method == "POST":
            sid = path[len("/api/schedules/"):-len("/toggle")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            result = await sched.toggle_schedule(sid)
            if result is None:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.toggle", sid)
            return json.dumps({"ok": True, "enabled": result["enabled"]}), 200, "application/json"

        if path.startswith("/api/schedules/") and path.endswith("/run") and method == "POST":
            sid = path[len("/api/schedules/"):-len("/run")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            ok = await sched.trigger_now(sid)
            if not ok:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.run_now", sid)
            return json.dumps({"ok": True}), 200, "application/json"

        if path.startswith("/api/schedules/") and method == "POST":
            sid = path[len("/api/schedules/"):]
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            try:
                result = await sched.update_schedule(sid, **data)
                if result is None:
                    return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
                self.state._log_action("schedule.update", sid)
                return json.dumps({"ok": True, "schedule": result}), 200, "application/json"
            except ValueError as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        if path.startswith("/api/schedules/") and method == "DELETE":
            sid = path[len("/api/schedules/"):]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            ok = await sched.delete_schedule(sid)
            if ok:
                self.state._log_action("schedule.delete", sid)
            return json.dumps({"ok": ok}), 200, "application/json"

        if path.startswith("/api/schedules/") and path.endswith("/run") and method == "POST":
            sid = path[len("/api/schedules/"):-len("/run")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            ok = await sched.trigger_now(sid)
            if not ok:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.run_now", sid)
            return json.dumps({"ok": True}), 200, "application/json"

        # === Canary / Internet Connectivity ===
        if path == "/api/canary/status" and method == "GET":
            result = self.state.get_canary_status()
            asyncio.ensure_future(self.state._check_canary())
            return json.dumps(result), 200, "application/json"

        if path.startswith("/api/canary/history") and method == "GET":
            qs = _qs(raw_path)
            hours = int(qs.get("hours", "24"))
            result = self.state.get_canary_history(hours)
            return json.dumps(result), 200, "application/json"

        if path == "/api/canary/hosts" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            hosts = data.get("canary_hosts", [])
            if hosts:
                self.state.set_canary_hosts(hosts)
            return json.dumps({"ok": True, "canary_hosts": self.state.canary_hosts}), 200, "application/json"

        return json.dumps({"error": "not found"}), 404, "application/json"
