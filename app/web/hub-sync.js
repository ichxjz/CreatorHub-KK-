(function(){
let timer=null,busy=new Set(),attempted=new Map();
const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function panel(){let p=document.getElementById('kk-hub-sync');if(!p){p=document.createElement('div');p.id='kk-hub-sync';p.className='kk-hub-sync';document.getElementById('hub-acc')?.closest('.card-head')?.after(p);}return p;}
function show(data,id){if(String(HUB_ACC)!==String(id)||CURRENT_TAB!=='hub')return;panel().innerHTML=`<div role="status">${esc(data.step)}</div><button class="ghost sm" onclick="syncHubNow()" ${data.status==='running'?'disabled':''}>重新同步全部</button>${data.results?.length?`<details><summary>同步详情</summary>${data.results.map(r=>`<p>${esc(r.name)}：${esc(r.message)}</p>`).join('')}</details>`:''}`;}
async function poll(id){clearTimeout(timer);try{const d=await api('/api/hub/sync/'+id);show(d,id);if(String(HUB_ACC)!==String(id)||CURRENT_TAB!=='hub')return;await refreshHubSummary();if(d.status==='running'){timer=setTimeout(()=>poll(id),2500);}else{originalRefresh();}}catch(e){show({step:'同步状态读取失败：'+e.message},id);}}
async function ensure(force=false){const id=String(HUB_ACC||'');if(CURRENT_TAB!=='hub'||!id||busy.has(id))return;if(!force&&Date.now()-(attempted.get(id)||0)<600000){poll(id);return;}busy.add(id);attempted.set(id,Date.now());show({status:'running',step:'正在准备自动同步…'},id);try{const d=await api('/api/hub/sync/'+id+(force?'?force=true':''),{method:'POST'});show(d,id);poll(id);}catch(e){show({step:'自动同步未启动：'+e.message},id);}finally{busy.delete(id);}}
window.syncHubNow=()=>ensure(true);
const originalRefresh=window.refreshHubPanel;window.refreshHubPanel=function(){originalRefresh();ensure();};
const populate=window.populateHubAccounts;window.populateHubAccounts=function(){populate();ensure();};
ensure();
})();
