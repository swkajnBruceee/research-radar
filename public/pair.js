'use strict';
let pairing, mode, chosen = false, qrTarget = 'app';
const remoteButton = document.querySelector('#remote-mode');
const localButton = document.querySelector('#local-mode');
const appQRButton = document.querySelector('#app-qr');
const webQRButton = document.querySelector('#web-qr');
const remoteReady = value => value.remote?.state === 'available' && /^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/.test(value.remote.url);
function render() {
 const available = remoteReady(pairing);
 remoteButton.disabled = !available;
 if (!chosen || (mode === 'remote' && !available)) mode = available ? 'remote' : 'local';
 const address = mode === 'remote' ? pairing.remote.url + '/' : pairing.address;
 remoteButton.setAttribute('aria-pressed',String(mode === 'remote'));
 localButton.setAttribute('aria-pressed',String(mode === 'local'));
 const link = document.querySelector('#address'); link.textContent = address; link.href = address;
 const invitation = 'embodiedradar://connect?' + new URLSearchParams({url:address,id:pairing.id});
 document.querySelector('#invitation').href = invitation;
 appQRButton.setAttribute('aria-pressed',String(qrTarget === 'app'));
 webQRButton.setAttribute('aria-pressed',String(qrTarget === 'web'));
 document.querySelector('#qr').setAttribute('aria-label',qrTarget === 'app' ? '研究台 App 配对二维码' : 'Safari 网页二维码');
 document.querySelector('#scan-step').textContent = qrTarget === 'app' ? '在 App 的“连接设置”中扫码，识别后会填入地址。' : '用 iPhone 相机扫描，以 Safari 打开网页。';
 document.querySelector('#code-step').textContent = qrTarget === 'app' ? '输入这台 Mac 上的访问码，再点“保存并连接”。扫码不会自动登录。' : '输入这台 Mac 上的访问码，即可开始阅读。';
 document.querySelector('#status').textContent = mode === 'remote' ? 'HTTPS 已连接 · 手机可使用蜂窝网络或其他 Wi-Fi' : '同网连接 · 需要手机与 Mac 可以互访';
 document.querySelector('#connection-note').textContent = mode === 'remote' ? 'Mac 需保持在线。这是临时通道，重建后地址会变化；最新地址以此页为准。' : '校园网可能屏蔽设备互访。' + (available ? '可切换上方 HTTPS 连接。' : (pairing.remote?.message || '可尝试同一个个人热点。'));
 const alternatives = document.querySelector('#alternatives'); alternatives.replaceChildren(); alternatives.hidden = mode !== 'local';
 for (const address of pairing.alternatives) { const p=document.createElement('p');p.textContent='备用 IP：'+address;alternatives.append(p); }
 const qr=qrcode(0,'M');qr.addData(qrTarget === 'app' ? invitation : address);qr.make();document.querySelector('#qr').innerHTML=qr.createSvgTag(6,3);
}
async function refresh() {
 try {
  const response=await fetch('/api/pairing');
  if(response.status===401){location.replace('/login');return;}
  if(!response.ok)throw new Error('连接信息读取失败，请稍后刷新');
  pairing=await response.json();render();
 } catch(e) { document.querySelector('#status').textContent=e.message; }
}
remoteButton.addEventListener('click',()=>{mode='remote';chosen=true;render();});
localButton.addEventListener('click',()=>{mode='local';chosen=true;render();});
appQRButton.addEventListener('click',()=>{qrTarget='app';if(pairing)render();});
webQRButton.addEventListener('click',()=>{qrTarget='web';if(pairing)render();});
refresh();setInterval(()=>{if(!document.hidden)refresh();},15000);
document.querySelector('#show-code').addEventListener('click',async()=>{
 const el=document.querySelector('#code');
 if(!el.hidden){el.hidden=true;el.textContent='';return;}
 try{const r=await fetch('/api/pairing/access-code');const v=await r.json();el.textContent=r.ok?'访问码：'+(v.code||'当前为本机模式，校园网模式才需要访问码'):v.error;el.hidden=false;}catch{el.textContent='未能读取，请打开 data/access-code.txt';el.hidden=false;}
});
