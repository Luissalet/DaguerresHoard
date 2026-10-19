"""Actual owned sync consumer, inert HTTP only; no SDK mutation or model call."""
import json
import httpx
import pytest
from daguerre_hoard import global_model
from daguerre_hoard.hoard_link.config import LinkConfig,CapabilityConfig


def test_exact_global_pin_ignores_saved_local_model_and_refreshes_next_job(monkeypatch):
    choices,posts=[],[]
    def descriptor(config):
        choices.append(1)
        return dict(endpoint_id='exact',model='chosen',connection_revision=str(len(choices)),vision=True,
            url='http://faustus.invalid/api/global-model/v1/chat/completions',headers={'Authorization':'Bearer inert-family'})
    monkeypatch.setattr(global_model,'descriptor',descriptor)
    def transport(request):
        data=json.loads(request.content);posts.append(data)
        assert data['model']==data['expected_model']=='chosen'
        assert data['expected_endpoint_id']=='exact'
        assert request.headers['Authorization']=='Bearer inert-family'
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'{}'},'finish_reason':'stop'}]})
    config=LinkConfig(capabilities={'llm':CapabilityConfig(url='http://retired.invalid',model='old',api='ollama')})
    link=global_model.GlobalLink(config,client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    try:
        with global_model.scope():
            link.sync.chat([{'role':'user','content':'first'}],response_format={'type':'json_object'})
            link.sync.chat([{'role':'user','content':'repair'}],response_format={'type':'json_object'})
        assert len(choices)==1 and all(p['expected_connection_revision']=='1' for p in posts)
        assert all(p['response_format']=={'type':'json_object'} for p in posts)
        with global_model.scope():link.sync.chat([{'role':'user','content':'next'}])
        assert len(choices)==2 and posts[-1]['expected_connection_revision']=='2'
    finally:
        link.sync.close()


@pytest.mark.parametrize('status,finish',[(409,'stop'),(200,'length'),(200,None)])
def test_stale_or_truncated_global_response_has_no_retry(monkeypatch,status,finish):
    monkeypatch.setattr(global_model,'descriptor',lambda _:dict(endpoint_id='e',model='m',connection_revision='r',
        vision=True,url='http://faustus.invalid/api/global-model/v1/chat/completions',headers={}))
    calls=[]
    def transport(request):
        calls.append(request)
        return httpx.Response(status,json={'choices':[{'message':{'role':'assistant','content':'partial'},'finish_reason':finish}]})
    link=global_model.GlobalLink(LinkConfig(),client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    try:
        with global_model.scope(),pytest.raises(Exception):link.sync.chat([{'role':'user','content':'inert'}])
        assert len(calls)==1
    finally:link.sync.close()
