import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {createServer} from 'vite';

test('shipping similar explorer pages with native offsets, keeps failed pages and ignores an unmounted source',async()=>{
 globalThis.IS_REACT_ACT_ENVIRONMENT=true;
 const oldWindow=globalThis.window;globalThis.window=new EventTarget();
 const server=await createServer({configFile:false,appType:'custom',optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,hmr:false,watch:null},ssr:{external:['react','react-dom','lucide-react']}});
 let view;
 try{
  const {default:SimilarPhotos}=await server.ssrLoadModule('/src/components/SimilarPhotos.tsx');
  const {api}=await server.ssrLoadModule('/src/api.ts');const {dict}=await server.ssrLoadModule('/src/i18n.ts');
  const {CONTEXT_EVENT,buildContext}=await server.ssrLoadModule('/src/copilot-context.ts');
  const pending=[],calls=[],opened=[];
  api.similar=(id,limit,offset)=>{calls.push({id,limit,offset});return new Promise((resolve,reject)=>pending.push({resolve,reject}));};
  const photo=id=>({id,path:`C:/fake/${id}.jpg`,thumbnail_url:`/fake/${id}`,relevance:'medium'});
  const props=id=>({key:id,photo:photo(id),t:dict.en,onOpen:p=>opened.push(p.id)});
  const page=(start,n,total,next)=>({results:Array.from({length:n},(_,i)=>photo(`A${start+i}`)),returned:n,indexed_total:total,has_more:next!==null,next_offset:next,embedder:'fake-colorhist-v1',note:'Only colour similarity'});
  const text=()=>JSON.stringify(view.toJSON());
  const load=()=>act(async()=>view.root.findAllByType('button').at(-1).props.onClick());
  await act(async()=>{view=create(React.createElement(SimilarPhotos,props('A')));});
  await act(async()=>pending.shift().resolve(page(1,12,25,12)));
  assert.match(text(),/12 shown of 25 indexed/);assert.match(text(),/Only colour similarity/);
  await load();assert.deepEqual(calls.at(-1),{id:'A',limit:12,offset:12});
  await act(async()=>pending.shift().reject(new Error('Own page failure')));
  assert.equal(view.root.findAllByType('li').length,12);assert.match(text(),/Own page failure/);
  await load();assert.equal(calls.at(-1).offset,12);
  await act(async()=>pending.shift().resolve(page(13,12,25,24)));
  await act(async()=>view.root.findAllByType('button')[17].props.onClick());assert.deepEqual(opened,['A18']);
  await load();await act(async()=>pending.shift().resolve(page(25,1,25,null)));
  assert.equal(view.root.findAllByType('li').length,25);assert.match(text(),/25 shown of 25 indexed/);assert.equal(view.root.findAllByType('button').length,25);
  let snapshot;const event=new Event(CONTEXT_EVENT);event.detail={provide:s=>{snapshot=s;}};window.dispatchEvent(event);
  assert.equal(snapshot.object_id,'A');assert.equal(snapshot.fields.shown_ids.length,25);assert.equal(snapshot.fields.next_offset,null);
  const final=await buildContext({getPhoto:async id=>photo(id),getEdits:async()=>({recipe:{}}),getAlbum:async()=>null,getVideo:async()=>null},
   {page:'library',photo:{id:'A',name:'A.jpg'},album:null,video:null,search:null},
   [{kind:'album-add',object_id:'A',dirty:true,fields:{name:'Pending album'}},snapshot]);
  assert.equal(final.view.editor.fields.name,'Pending album');
  assert.deepEqual(final.view.editors.find(e=>e.kind==='similar-photos').fields.shown_ids,snapshot.fields.shown_ids);
  await act(async()=>view.update(React.createElement(SimilarPhotos,props('B'))));
  const old=pending.shift();await act(async()=>view.update(React.createElement(SimilarPhotos,props('C'))));
  await act(async()=>old.resolve(page(90,2,2,null)));assert.doesNotMatch(text(),/A90|A91/);
  await act(async()=>pending.shift().resolve({results:[],returned:0,indexed_total:0,has_more:false}));
  assert.match(text(),/No other photos are indexed/);assert.equal(view.root.findAllByType('li').length,0);
 }finally{if(view)await act(async()=>view.unmount());await server.close();globalThis.window=oldWindow;delete globalThis.IS_REACT_ACT_ENVIRONMENT;}
});
