const $=id=>document.getElementById(id);
let language=localStorage.getItem('daguerre-lang')||'en';
let photoOffset=0,projectId=null;
const text=(en,es)=>language==='es'?es:en;
function element(tag,label,parent){const n=document.createElement(tag);if(label)n.textContent=label;if(parent)parent.append(n);return n;}
function fail(e){$('error').textContent=e.message;}
async function api(path,method='GET',body){const r=await fetch('/api/studio/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const result=await r.json();if(!r.ok)throw Error(result.message||result.error||r.statusText);return result;}
async function modules(){const result=await api('modules');$('modules').replaceChildren();for(const m of result.modules){const row=element('div',null,$('modules'));element('strong',m.id==='photos'?text('Photos, Layers and Develop','Fotos, Layers y Develop'):text('Vector illustration','Ilustración vectorial'),row);element('span',({off:text('Off','Apagado'),on:text('On','Encendido'),starting:text('Starting','Arrancando'),stopping:text('Stopping','Apagando')})[m.phase]||m.phase,row);const check=document.createElement('input');check.type='checkbox';check.checked=m.automatic;if(m.id==='photos'){const label=element('label',null,row);label.append(check,text(' Allow automatic maintenance',' Permitir mantenimiento automático'));}const button=element('button',m.phase==='stopping'?text('Retry stop','Reintentar apagado'):m.enabled?text('Stop','Apagar'):text('Activate','Activar'),row);button.onclick=async()=>{button.disabled=true;try{await api('modules/'+m.id,'PUT',{enabled:m.phase==='stopping'?false:!m.enabled,automatic:check.checked});await modules();}catch(e){fail(e);button.disabled=false;}};const link=element('a',text('Open','Abrir'),row);link.href=m.url;}}
async function openProject(id){
  if(projectId!==id){photoOffset=0;projectId=id;}
  const project=await api('projects/'+id),native=await api('objects?offset='+photoOffset),area=$('project');area.replaceChildren();element('h3',project.title,area);
  for(const [kind,rows] of [['photo',native.photos],['export',native.vector]]){
    const form=element('form',null,area),label=element('label',kind==='photo'?text('Photo to edit','Foto para editar'):text('Vector result to Photos','Resultado vectorial a Fotos'),form),select=element('select',null,label);select.required=true;
    element('option',text('Select','Selecciona'),select).value='';
    for(const row of rows){const option=element('option',row.title||row.path.split(/[\\/]/).pop(),select);option.value=row.id;}
    element('button',kind==='photo'?text('Open editable vector','Abrir vector editable'):text('Export and add photo','Exportar y añadir foto'),form);
    if(kind==='photo')for(const [step,label] of [[-50,text('Previous photos','Fotos anteriores')],[50,text('More photos','Más fotos')]]){
      const button=element('button',label,form);button.type='button';button.disabled=step<0?photoOffset===0:rows.length<50;
      button.onclick=()=>{photoOffset=Math.max(0,photoOffset+step);openProject(id).catch(fail);};
    }
    form.onsubmit=async event=>{event.preventDefault();try{await api('projects/'+id+'/'+kind,'POST',kind==='photo'?{photo_id:select.value}:{illustration:select.value});await openProject(id);}catch(e){fail(e);}};
  }
  for(const object of project.objects){const link=element('a',object.module+' · '+object.native_id,area);link.href=object.route;element('p',text('Revision ','Revisión ')+object.revision.slice(0,12),area);}
  for(const transfer of project.transfers){const link=element('a',text('Download retained result','Descargar resultado conservado'),area);link.href='/api/studio/artifacts/'+id+'/'+transfer.receipt.sha256;}
}
async function projects(){const rows=await api('projects');$('projects').replaceChildren();for(const p of rows){const b=element('button',p.title,$('projects'));b.onclick=()=>openProject(p.id).catch(fail);}}
function translate(){document.documentElement.lang=language;for(const node of document.querySelectorAll('[data-en]'))node.textContent=node.dataset[language]||node.dataset.en;$('language').textContent=language==='es'?'EN':'ES';Promise.all([modules(),projects()]).catch(fail);}
$('language').onclick=()=>{language=language==='es'?'en':'es';localStorage.setItem('daguerre-lang',language);translate();};
$('theme').onclick=()=>{const theme=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=theme;localStorage.setItem('daguerre-theme',theme);};
document.documentElement.dataset.theme=localStorage.getItem('daguerre-theme')||'dark';
$('create').onsubmit=async event=>{event.preventDefault();try{await api('projects','POST',{title:new FormData(event.target).get('title')});event.target.reset();await projects();}catch(e){fail(e);}};
translate();
fetch('/api/health').then(r=>r.json()).then(health=>{if(health.demo){const button=element('button',text('Prepare synthetic demo','Preparar demo sintética'),document.querySelector('main section'));button.onclick=()=>api('demo','POST',{}).then(()=>{location.href='/photos/';}).catch(fail);}}).catch(fail);
