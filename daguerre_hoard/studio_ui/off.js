const es=localStorage.getItem('daguerre-lang')==='es';
document.documentElement.dataset.theme=localStorage.getItem('daguerre-theme')||'dark';
document.getElementById('message').textContent=es?'Este módulo está apagado. Actívalo para continuar.':'This module is OFF. Activate it to continue.';
const button=document.getElementById('activate');button.textContent=es?'Activar':'Activate';
button.onclick=async()=>{button.disabled=true;try{const r=await fetch('/api/studio/modules/'+document.body.dataset.module,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true,automatic:false})});if(!r.ok)throw Error((await r.json()).message);location.reload();}catch(e){document.getElementById('error').textContent=e.message;button.disabled=false;}};
