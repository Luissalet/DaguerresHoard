const $=id=>document.getElementById(id);
let language=localStorage.getItem('daguerre-lang')||'en';
let photoOffset=0,projectId=null,projectRead=0,moduleState={};
const text=(en,es)=>language==='es'?es:en;
function element(tag,label,parent){const n=document.createElement(tag);if(label)n.textContent=label;if(parent)parent.append(n);return n;}
function fail(e){$('error').textContent=e.message;}
async function api(path,method='GET',body){const r=await fetch('/api/studio/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const result=await r.json();if(!r.ok)throw Error(result.message||result.error||r.statusText);return result;}
async function modules(){const result=await api('modules');moduleState=Object.fromEntries(result.modules.map(m=>[m.id,m.phase]));$('modules').replaceChildren();for(const m of result.modules){const row=element('div',null,$('modules'));element('strong',m.id==='photos'?text('Photos, Layers and Develop','Fotos, Layers y Develop'):text('Vector illustration','Ilustración vectorial'),row);element('span',({off:text('Off','Apagado'),on:text('On','Encendido'),starting:text('Starting','Arrancando'),stopping:text('Stopping','Apagando')})[m.phase]||m.phase,row);const check=document.createElement('input');check.type='checkbox';check.checked=m.automatic;if(m.id==='photos'){const label=element('label',null,row);label.append(check,text(' Allow automatic maintenance',' Permitir mantenimiento automático'));}const button=element('button',m.phase==='stopping'?text('Retry stop','Reintentar apagado'):m.enabled?text('Stop','Apagar'):text('Activate','Activar'),row);button.onclick=async()=>{button.disabled=true;try{await api('modules/'+m.id,'PUT',{enabled:m.phase==='stopping'?false:!m.enabled,automatic:check.checked});await modules();}catch(e){fail(e);button.disabled=false;}};const link=element('a',text('Open','Abrir'),row);link.href=m.url;}updateFigureTargets();}

function updateFigureTargets(){
  for(const button of document.querySelectorAll('[data-figure-module]')) button.disabled=button.dataset.busy==='true'||moduleState[button.dataset.figureModule]!=='on';
}

function originLink(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;}catch{return null;}}

function inspectFigure(item,opener){
  const dialog=element('dialog',null,document.body);dialog.className='figure-dialog';dialog.setAttribute('aria-label',text('Inspect figure','Inspeccionar figura'));
  const actions=element('div',null,dialog);actions.className='figure-actions';
  element('button',text('Close','Cerrar'),actions).onclick=()=>dialog.close();
  const area=element('div',null,dialog);area.className='figure-pan';area.tabIndex=0;area.setAttribute('aria-label',text('Capture; scroll to explore','Captura; desplázate para explorar'));
  const image=element('img',null,area);image.alt=item.snapshot.title||text('Retained diagram','Diagrama conservado');let scale=1;
  const resize=()=>{image.style.width=scale==='fit'?'auto':image.naturalWidth*scale+'px';image.style.maxWidth=scale==='fit'?'100%':'none';image.style.maxHeight=scale==='fit'?'100%':'none';};
  for(const [value,label] of [['fit',text('Fit','Ajustar')],[1,text('Actual size','Tamaño real')],[2,text('Zoom 2×','Ampliar 2×')]]){
    const button=element('button',label,actions);button.onclick=()=>{scale=value;resize();};
  }
  image.onload=resize;image.src=item.route;
  dialog.addEventListener('close',()=>{dialog.remove();if(opener.isConnected)opener.focus();},{once:true});
  dialog.showModal();
}

function figureControls(project,area){
  const form=element('form',null,area),label=element('label',text('Import figure (.vfigure)','Importar figura (.vfigure)'),form),input=element('input',null,label);
  form.className='figure-import';input.type='file';input.accept='.vfigure,application/json';
  input.onchange=async()=>{
    const file=input.files[0];if(!file)return;input.disabled=true;$('error').textContent='';
    try{const figure=JSON.parse(await file.text());await api('projects/'+project.id+'/figure','POST',{action:'import',figure});if(projectId===project.id)await openProject(project.id);}
    catch(error){fail(error);}finally{input.value='';input.disabled=false;}
  };
  const captures=project.objects.filter(o=>o.module==='diagram'&&o.kind==='figure');
  if(captures.length)element('p',text('Vector and Layers use this image. The complete diagram source stays with the capture. Activate the destination module above to create a copy.','Vector y Capas utilizan esta imagen. La fuente completa del diagrama queda con la captura. Activa arriba el módulo de destino para crear una copia.'),area);
  for(const item of captures){
    const figure=element('figure',null,area);figure.className='project-figure';
    const button=element('button',null,figure);button.className='figure-image';button.setAttribute('aria-label',text('Enlarge figure','Ampliar figura'));
    const image=element('img',null,button);image.src=item.route;image.alt=item.snapshot.title||text('Retained diagram','Diagrama conservado');button.onclick=()=>inspectFigure(item,button);
    const source=item.snapshot;let caption=(source.title||text('Diagram','Diagrama'))+' · '+text('Revision ','Revisión ')+source.revision;
    if(source.page_id)caption+=' · '+text('Page ','Página ')+source.page_id;if(source.state_id)caption+=' · '+text('State ','Estado ')+source.state_id;
    element('figcaption',caption,figure);
    const actions=element('div',null,figure);actions.className='figure-actions';
    const enlarge=element('button',text('Enlarge figure','Ampliar figura'),actions);enlarge.onclick=()=>inspectFigure(item,enlarge);
    const download=element('a',text('Download figure and source','Descargar figura y fuente'),actions);download.href=item.route.replace(/\.png$/,'.vfigure');download.download='';
    const origin=originLink(source.origin?.editor_url);if(origin){const link=element('a',text('Open source diagram','Abrir diagrama de origen'),actions);link.href=origin;link.target='_blank';link.rel='noreferrer';}
    for(const [action,module,label] of [['vector','vector',text('Create in Vector','Crear en Vector')],['layers','photos',text('Create in Layers','Crear en Capas')]]){
      const create=element('button',label,actions);create.dataset.figureModule=module;
      create.onclick=async()=>{create.dataset.busy='true';create.setAttribute('aria-busy','true');create.textContent=text('Creating…','Creando…');$('error').textContent='';updateFigureTargets();try{await api('projects/'+project.id+'/figure','POST',{action,object_id:item.id});if(projectId===project.id)await openProject(project.id);}catch(error){fail(error);}finally{create.dataset.busy='false';create.removeAttribute('aria-busy');create.textContent=label;updateFigureTargets();}};
    }
  }
  updateFigureTargets();
}
async function openProject(id){
  if(projectId!==id){photoOffset=0;projectId=id;}
  const read=++projectRead,project=await api('projects/'+id),native=await api('objects?offset='+photoOffset),area=$('project');
  if(projectId!==id||read!==projectRead)return;
  area.replaceChildren();element('h3',project.title,area);figureControls(project,area);
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
  for(const object of project.objects){if(object.module==='diagram')continue;const link=element('a',object.module+' · '+object.native_id,area);link.href=object.route;element('p',text('Revision ','Revisión ')+object.revision.slice(0,12),area);
    if(object.kind==='layers'&&object.snapshot.artifact){const artifact=object.snapshot.artifact;
      const download=element('a',text('Download Layers document','Descargar documento de Capas'),area);download.href=artifact.native_url;download.download='';
      const open=element('button',text('Open Layers editor','Abrir editor de Capas'),area);open.dataset.figureModule='photos';
      open.onclick=async()=>{open.dataset.busy='true';$('error').textContent='';updateFigureTargets();try{const r=await fetch('/photos/api/image-engine/editor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({artifact_id:artifact.id,engine:'layers'})});const data=await r.json();if(!r.ok)throw Error(data.message||data.error);}
        catch(error){fail(error);}finally{open.dataset.busy='false';updateFigureTargets();}};
    }
  }
  updateFigureTargets();
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
