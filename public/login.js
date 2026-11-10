'use strict';
document.querySelector('#login-form').addEventListener('submit',async event=>{
 event.preventDefault();
 const button=document.querySelector('#submit'),error=document.querySelector('#error');
 button.disabled=true;error.textContent='';
 try{
  const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.querySelector('#access-code').value})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'暂时无法进入，请重试');
  location.replace('/');
 }catch(e){error.textContent=e.message;}
 finally{button.disabled=false;}
});
