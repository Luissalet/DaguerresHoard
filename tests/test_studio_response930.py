"""Native URL declarations and document content have different contracts."""
import pytest
from daguerre_hoard.studio_response import NativeResponse, scoped_json


def test_only_declared_photo_links_change_namespace():
    content={'title':'/api/retained title','file_path':'/assets/original.png',
        'prompt':'/api/unchanged prompt','manifest':{'url':'/api/native-content'},
        'sample_thumbnail_url':'/api/photos/a/thumbnail',
        'cover_thumbnail_url':'/api/photos/b/thumbnail'}
    scoped=scoped_json(content,'photos',1)
    assert scoped | {key:content[key] for key in ('sample_thumbnail_url','cover_thumbnail_url')} == content
    assert scoped['sample_thumbnail_url']=='/photos/api/photos/a/thumbnail'
    assert scoped['cover_thumbnail_url']=='/photos/api/photos/b/thumbnail'


@pytest.mark.asyncio
async def test_partial_native_binary_response_retains_status_headers_and_exact_bytes():
    messages=[]
    async def send(message):messages.append(message)
    response=NativeResponse(send,'vector',1)
    start={'type':'http.response.start','status':206,'headers':[
        (b'content-type',b'image/png'),(b'content-range',b'bytes 4-7/20'),(b'content-length',b'4')]}
    body={'type':'http.response.body','body':b'\x00\xff\x88\x01','more_body':False}
    await response(start);await response(body)
    assert messages==[start,body]


@pytest.mark.asyncio
@pytest.mark.parametrize('path,portable', [('/api/exports/selection/gallery.html', True),
    ('/api/exports/selection/manifest.json', True), ('/', False)])
async def test_photo_exports_keep_artifact_bytes_outside_editor_shell(tmp_path,path,portable):
    from types import SimpleNamespace
    from daguerre_hoard.studio import Studio
    messages=[]
    payload=b'<html><body><img src="data:image/jpeg;base64,abcd"></body></html>'
    async def send(message):messages.append(message)
    async def receive():return {'type':'http.request','body':b''}
    async def request(scope,receive,output):
        assert scope['path']==path and scope['root_path']==''
        await output({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/html')]})
        await output({'type':'http.response.body','body':payload})
    studio=Studio(tmp_path/'cold',port=63397)
    studio.modules['photos']=SimpleNamespace(request=request)
    await studio.native('photos',path,{'path':'/photos'+path},receive,send)
    body=b''.join(message.get('body',b'') for message in messages)
    if portable:
        assert body==payload
    else:
        assert b'/studio-assets/' in body
