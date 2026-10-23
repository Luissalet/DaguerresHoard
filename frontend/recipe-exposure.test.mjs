import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

test("stored exposure uses partial native patches, retains later drafts and cannot cross photo identity", async () => {
  const previousWindow=globalThis.window;globalThis.window=new EventTarget();globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const server=await createServer({configFile:false,appType:"custom",optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,hmr:false,watch:null},ssr:{external:["react","react-dom","lucide-react"]}});
  let rendered;
  try {
    const {default:EditsPanel}=await server.ssrLoadModule("/src/components/EditsPanel.tsx");
    const {api}=await server.ssrLoadModule("/src/api.ts");const {dict}=await server.ssrLoadModule("/src/i18n.ts");
    const stored=Object.fromEntries(["A","B"].map(id=>[id,{photo_id:id,rating:3,label:`Label ${id}`,keywords:[id],recipe:{exposure:id==="A"?0.5:-1,contrast:12,crop:{left:0.1,top:0,right:1,bottom:1}},sidecar:{},write_sidecars:false}]));
    let fail=false;const pending=[],calls=[];
    api.getEdits=async id=>structuredClone(stored[id]);
    api.setEdits=(id,patch)=>{calls.push({id,patch});if(fail){fail=false;return Promise.reject(new Error("Retry exposure"));}return new Promise(resolve=>pending.push(()=>{const value=patch.recipe.exposure;if(value===null)delete stored[id].recipe.exposure;else stored[id].recipe.exposure=value;resolve(structuredClone(stored[id]));}));};
    const props=id=>({photoId:id,t:dict.en});const input=()=>rendered.root.findAllByType("input").find(i=>i.props.type==="number");
    const labels=()=>rendered.root.findAllByType("input").filter(i=>i.props.type!=="number");
    const button=text=>rendered.root.findAllByType("button").find(b=>b.props.children===text);
    const form=()=>rendered.root.findAllByType("form").find(f=>f.findAllByType("input").some(i=>i.props.type==="number"));
    const submit=async()=>act(async()=>form().props.onSubmit({preventDefault(){}}));
    await act(async()=>{rendered=create(React.createElement(EditsPanel,props("A")));});
    await act(async()=>{labels()[0].props.onChange({target:{value:"Draft label"}});labels()[1].props.onChange({target:{value:"draft, keep"}});input().props.onChange({target:{value:"1.25"}});});
    fail=true;await submit();assert.equal(input().props.value,"1.25");assert.equal(stored.A.recipe.exposure,0.5);
    assert.ok(rendered.root.findAllByType("p").some(p=>p.props.children==="Retry exposure"));
    await submit();await act(async()=>input().props.onChange({target:{value:"2.5"}}));
    await act(async()=>pending.shift()());assert.equal(input().props.value,"2.5");assert.equal(stored.A.recipe.exposure,1.25);
    assert.deepEqual(labels().map(i=>i.props.value),["Draft label","draft, keep"]);
    await act(async()=>input().props.onChange({target:{value:"0"}}));await submit();await act(async()=>pending.shift()());
    assert.equal(stored.A.recipe.exposure,0);assert.equal(input().props.value,"0");
    await act(async()=>button(dict.en.recipe_exposure_clear).props.onClick());await act(async()=>pending.shift()());
    assert.equal("exposure" in stored.A.recipe,false);assert.equal(input().props.value,"");
    assert.equal(input().props.placeholder,dict.en.recipe_exposure_absent);
    assert.deepEqual(stored.A.recipe,{contrast:12,crop:{left:0.1,top:0,right:1,bottom:1}});
    assert.equal(stored.A.rating,3);assert.equal(stored.A.label,"Label A");assert.deepEqual(stored.A.keywords,["A"]);
    await act(async()=>input().props.onChange({target:{value:"2.75"}}));await submit();
    await act(async()=>rendered.update(React.createElement(EditsPanel,props("B"))));
    assert.equal(input().props.value,"-1");await act(async()=>pending.shift()());
    assert.equal(input().props.value,"-1");assert.equal(labels()[0].props.value,"Label B");assert.equal(stored.B.recipe.exposure,-1);
    assert.deepEqual(calls,[{id:"A",patch:{recipe:{exposure:1.25}}},{id:"A",patch:{recipe:{exposure:1.25}}},{id:"A",patch:{recipe:{exposure:0}}},{id:"A",patch:{recipe:{exposure:null}}},{id:"A",patch:{recipe:{exposure:2.75}}}]);
  } finally {if(rendered)await act(async()=>rendered.unmount());await server.close();globalThis.window=previousWindow;delete globalThis.IS_REACT_ACT_ENVIRONMENT;}
});
