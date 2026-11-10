import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../public/pair.js',import.meta.url),'utf8');
async function setup(){
 const elements=new Map();
 const value={id:'01234567-89AB-CDEF-0123-456789ABCDEF',address:'http://research-mac.local:8765/',alternatives:[],remote:{state:'available',url:'https://research-test.trycloudflare.com'}};
 const element=id=>{if(!elements.has(id))elements.set(id,{listeners:{},attrs:{},textContent:'',addEventListener(n,f){this.listeners[n]=f;},setAttribute(n,v){this.attrs[n]=v;},replaceChildren(){},append(){}});return elements.get(id);};
 const sandbox={URLSearchParams,URL,document:{hidden:false,querySelector:s=>element(s),createElement:()=>({})},location:{replace(){}},setInterval(){},fetch:async()=>({ok:true,status:200,json:async()=>value}),qrcode:()=>({addData(v){sandbox.payload=v;},make(){},createSvgTag(){return '<svg></svg>';}})};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);await new Promise(setImmediate);
 return {elements,sandbox,value,click:id=>element(id).listeners.click(),refresh:async()=>{await vm.runInContext('refresh()',sandbox);}};
}
test('App QR preserves the legacy invitation contract; Safari QR remains a plain HTTPS root',async()=>{
 const c=await setup();
 let qr=new URL(c.sandbox.payload);
 assert.equal(qr.protocol,'embodiedradar:');assert.equal(qr.hostname,'connect');
 assert.equal(qr.searchParams.get('id'),c.value.id);
 assert.equal(qr.searchParams.get('url'),c.value.remote.url+'/');
 assert.deepEqual([...qr.searchParams.keys()].sort(),['id','url']);
 assert.match(c.elements.get('#code-step').textContent,/保存并连接/);
 c.click('#web-qr');assert.equal(c.sandbox.payload,c.value.remote.url+'/');
 c.click('#local-mode');assert.equal(c.sandbox.payload,c.value.address);
 c.click('#app-qr');qr=new URL(c.sandbox.payload);assert.equal(qr.searchParams.get('url'),c.value.address);
});
test('A changed or failed tunnel cannot leave a stale address in the selected QR',async()=>{
 const c=await setup();c.value.remote.url='https://another-tunnel.trycloudflare.com';await c.refresh();
 assert.equal(new URL(c.sandbox.payload).searchParams.get('url'),c.value.remote.url+'/');
 c.value.remote.state='offline';await c.refresh();
 assert.equal(new URL(c.sandbox.payload).searchParams.get('url'),c.value.address);
 assert.equal(c.elements.get('#remote-mode').disabled,true);
});
