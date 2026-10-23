import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { act, create } from "react-test-renderer";
import { createServer } from "vite";

test("reject and clear use rating-only patches, preserve drafts and retain rejected state on error", async () => {
  const previousWindow=globalThis.window;
  globalThis.window=new EventTarget();
  globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const server=await createServer({configFile:false,appType:"custom",server:{middlewareMode:true,hmr:false,watch:null},ssr:{external:["react","react-dom","lucide-react"]}});
  let rendered;
  try {
    const {default:EditsPanel}=await server.ssrLoadModule("/src/components/EditsPanel.tsx");
    const {api}=await server.ssrLoadModule("/src/api.ts");
    const {dict}=await server.ssrLoadModule("/src/i18n.ts");
    let saved={photo_id:"qa",rating:3,label:"Blue",keywords:["saved"],recipe:{exposure:1},sidecar:{},write_sidecars:false};
    let fail=false;
    const calls=[],exposures=[];
    api.getEdits=async()=>structuredClone(saved);
    api.setEdits=async(id,patch)=>{
      calls.push({id,patch});
      if(fail){fail=false;throw new Error("Fallo ficticio: reintenta");}
      saved={...saved,...patch};return structuredClone(saved);
    };
    await act(async()=>{rendered=create(React.createElement(EditsPanel,{photoId:"qa",t:dict.en,onExposure:value=>exposures.push(value)}));});
    const button=text=>rendered.root.findAllByType("button").find(item=>item.props.children===text);
    const inputs=()=>rendered.root.findAllByType("input");
    await act(async()=>{inputs()[0].props.onChange({target:{value:"Typed label"}});inputs()[1].props.onChange({target:{value:"typed, keep"}});});
    const beforeExposure=exposures.length;
    await act(async()=>{await button(dict.en.edits_reject).props.onClick();});
    assert.deepEqual(calls,[{id:"qa",patch:{rating:-1}}]);
    assert.equal(button(dict.en.edits_unreject).props["aria-pressed"],true);
    assert.deepEqual(inputs().map(input=>input.props.value),["Typed label","typed, keep"]);
    assert.equal(exposures.length,beforeExposure);
    fail=true;
    await act(async()=>{await button(dict.en.edits_unreject).props.onClick();});
    assert.equal(saved.rating,-1);
    assert.equal(button(dict.en.edits_unreject).props["aria-pressed"],true);
    assert.deepEqual(inputs().map(input=>input.props.value),["Typed label","typed, keep"]);
    assert.ok(rendered.root.findAllByType("p").some(item=>item.props.children==="Fallo ficticio: reintenta"));
    await act(async()=>{await button(dict.en.edits_unreject).props.onClick();});
    assert.equal(saved.rating,0);
    assert.equal(button(dict.en.edits_reject).props["aria-pressed"],false);
    assert.deepEqual(calls.map(call=>call.patch),[{rating:-1},{rating:0},{rating:0}]);
    assert.equal(saved.label,"Blue");assert.deepEqual(saved.keywords,["saved"]);assert.deepEqual(saved.recipe,{exposure:1});
    await act(async()=>{rendered.update(React.createElement(EditsPanel,{photoId:"qa",t:dict.es}));});
    assert.ok(button(dict.es.edits_reject));
    assert.match(dict.es.edits_reject_help,/sin valoración/);
  } finally {
    if(rendered)await act(async()=>rendered.unmount());
    await server.close();globalThis.window=previousWindow;delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});
