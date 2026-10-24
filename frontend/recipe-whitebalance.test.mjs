import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {act,create} from "react-test-renderer";
import {createServer} from "vite";

test("white balance patches preserve drafts, zero/absence and photo identity through the final context consumer", async()=>{
  const oldWindow=globalThis.window;globalThis.window=new EventTarget();globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const server=await createServer({configFile:false,appType:"custom",optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,hmr:false,watch:null},ssr:{external:["react","react-dom","lucide-react"]}});
  let tree;
  try {
    const {default:Panel}=await server.ssrLoadModule("/src/components/EditsPanel.tsx");
    const {api}=await server.ssrLoadModule("/src/api.ts");const {dict}=await server.ssrLoadModule("/src/i18n.ts");
    const ctx=await server.ssrLoadModule("/src/copilot-context.ts");
    const stored=Object.fromEntries(["A","B"].map(id=>[id,{photo_id:id,rating:3,label:`Label ${id}`,keywords:[id],recipe:{exposure:0.5,contrast:12,crop:{left:.1,top:0,right:1,bottom:1},...(id==="B"?{temperature:4800,tint:3}:{})},sidecar:{},write_sidecars:false}]));
    const calls=[],pending=[];let fail=false;
    api.getEdits=async id=>structuredClone(stored[id]);
    api.setEdits=(id,patch)=>{calls.push({id,patch});if(fail){fail=false;return Promise.reject(Error("Retry white balance"));}
      return new Promise(resolve=>pending.push(()=>{for(const [key,value]of Object.entries(patch.recipe)){if(value===null)delete stored[id].recipe[key];else stored[id].recipe[key]=value;}resolve(structuredClone(stored[id]));}));};
    const form=()=>tree.root.findAllByType("form").find(f=>f.props["aria-label"]===dict.en.recipe_wb_title);
    const wb=key=>form().findAllByType("input")[key==="temperature"?0:1];
    const edit=async(key,value)=>act(async()=>wb(key).props.onChange({target:{value}}));
    const submit=async()=>act(async()=>form().props.onSubmit({preventDefault(){}}));
    const finish=async()=>act(async()=>pending.shift()());
    const button=text=>tree.root.findAllByType("button").find(b=>b.props.children===text);
    await act(async()=>{tree=create(React.createElement(Panel,{photoId:"A",t:dict.en}));});
    const label=tree.root.findAllByType("input").find(i=>i.props.placeholder===dict.en.edits_label);
    await act(async()=>label.props.onChange({target:{value:"Pending label ñ"}}));
    await edit("temperature","6100");await edit("tint","-8");
    fail=true;await submit();assert.equal(wb("temperature").props.value,"6100");assert.equal(wb("tint").props.value,"-8");
    await submit();await edit("temperature","6200");await finish();
    assert.equal(stored.A.recipe.temperature,6100);assert.equal(wb("temperature").props.value,"6200");
    assert.equal(label.props.value,"Pending label ñ");
    const context=await ctx.buildContext({getPhoto:async id=>({id,path:id+".jpg"}),getEdits:api.getEdits,getAlbum:async()=>null,getVideo:async()=>null},{page:"library",photo:{id:"A",name:"A.jpg"},album:null,video:null,search:null},ctx.collectEditors());
    const snapshot=context.view.editors.find(e=>e.kind==="photo-white-balance");
    assert.equal(snapshot.fields.temperature,"6200");assert.equal(snapshot.fields.saved_recipe.temperature,6100);assert.equal(snapshot.dirty,true);
    assert.equal(context.view.editors.find(e=>e.kind==="photo-edits").fields.label,"Pending label ñ");
    await edit("temperature","6100");await edit("tint","0");await submit();await finish();
    assert.deepEqual(calls.at(-1),{id:"A",patch:{recipe:{tint:0}}});assert.equal(stored.A.recipe.temperature,6100);
    await act(async()=>button(dict.en.recipe_wb_clear_temperature).props.onClick());await finish();
    assert.equal("temperature"in stored.A.recipe,false);assert.equal(stored.A.recipe.tint,0);
    await act(async()=>button(dict.en.recipe_wb_clear_tint).props.onClick());await finish();
    assert.equal("tint"in stored.A.recipe,false);await edit("temperature","");assert.equal(button(dict.en.recipe_wb_save).props.disabled,true);
    assert.deepEqual(stored.A.recipe,{exposure:.5,contrast:12,crop:{left:.1,top:0,right:1,bottom:1}});assert.equal(stored.A.label,"Label A");
    await edit("temperature","7000");await submit();
    await act(async()=>tree.update(React.createElement(Panel,{photoId:"B",t:dict.en})));
    assert.equal(wb("temperature").props.value,"4800");await finish();assert.equal(wb("temperature").props.value,"4800");assert.equal(wb("tint").props.value,"3");
    await edit("tint","7");await submit();await act(async()=>tree.unmount());tree=null;await finish();
    assert.equal(stored.B.recipe.tint,7);assert.deepEqual(calls.map(c=>c.patch.recipe),[{temperature:6100,tint:-8},{temperature:6100,tint:-8},{tint:0},{temperature:null},{tint:null},{temperature:7000},{tint:7}]);
  } finally {if(tree)await act(async()=>tree.unmount());await server.close();globalThis.window=oldWindow;delete globalThis.IS_REACT_ACT_ENVIRONMENT;}
});
