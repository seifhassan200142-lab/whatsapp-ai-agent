import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from groq import AsyncGroq
from pydantic import SecretStr

from app.config import ROOT, Settings
from app.database import Database
from app.handoff import asks_for_human
from app.main import create_app
from app.models import Inbound
from app.whatsapp import WhatsApp, verify_signature


def payload(text="مواعيد الشغل؟", ident="wamid.in.1", kind="text", timestamp=None):
    message = {"from":"201000000001", "id":ident, "timestamp":str(timestamp or int(time.time())), "type":kind}
    message[kind] = {"body":text} if kind=="text" else {"id":"1234", "mime_type":"audio/ogg; codecs=opus", "voice":True}
    return {"object":"whatsapp_business_account", "entry":[{"id":"WABA_ID", "changes":[{"field":"messages", "value":{"messaging_product":"whatsapp", "metadata":{"display_phone_number":"15550000000", "phone_number_id":"123456"}, "contacts":[{"profile":{"name":"Test Customer"},"wa_id":"201000000001"}], "messages":[message]}}]}]}


def signed(data):
    body=json.dumps(data,ensure_ascii=False).encode()
    digest=hmac.new(b"test-app-secret",body,hashlib.sha256).hexdigest()
    return body,{"X-Hub-Signature-256":"sha256="+digest,"Content-Type":"application/json"}


def post(client,data):
    body,headers=signed(data)
    return client.post('/webhook',content=body,headers=headers)


def wait_done(client, count=1):
    end=time.monotonic()+5
    while time.monotonic()<end:
        rows=client.get('/admin/conversations/201000000001',headers={'X-Admin-Key':'a'*40})
        if rows.status_code==200:
            incoming=[m for m in rows.json()['messages'] if m['direction']=='incoming']
            if len(incoming)>=count and all(m['state'] not in ('queued','processing') for m in incoming):
                return rows.json()
        time.sleep(.02)
    raise AssertionError('Worker did not finish within 5 seconds')


@pytest.fixture
def harness(tmp_path):
    state=SimpleNamespace(groq_status=200,summary_fail=False,handoff=False,malformed=False,
                          send_error=False,meta_status=200,no_evidence=False,groq_network=False,groq_requests=[],meta_sends=[],media_url='https://lookaside.fbsbx.com/audio',audio=b'OggS-demo-test-bytes')
    async def groq_handler(request):
        state.groq_requests.append(request)
        if state.groq_network:
            raise httpx.ConnectError('sensitive-provider-text',request=request)
        if state.groq_status!=200:
            return httpx.Response(state.groq_status,json={'error':{'message':'mock error','type':'invalid_request_error','code':'mock'}},headers={'retry-after':'1'})
        if request.url.path.endswith('/audio/transcriptions'):
            return httpx.Response(200,json={'text':'مواعيد الشغل ايه؟'})
        body=json.loads(request.content)
        if 'Summarize' in body['messages'][0]['content']:
            if state.summary_fail:
                return httpx.Response(429,json={'error':{'message':'limited'}})
            content='العميل محتاج مراجعة بشرية؛ المطلوب التواصل معاه.'
        elif state.malformed:
            content='not-json'
        else:
            content=json.dumps({'reply':'من الأحد للخميس من 9 لـ5 بتوقيت القاهرة.', 'handoff':state.handoff,'reason':'needs_human' if state.handoff else '', 'evidence':'' if state.no_evidence else 'Sunday through Thursday, 9:00 AM to 5:00 PM, Cairo local time.', 'kind':'handoff' if state.handoff else 'company_answer'},ensure_ascii=False)
        return httpx.Response(200,json={'id':'mock-completion','object':'chat.completion','created':1,'model':'openai/gpt-oss-20b','choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]})
    async def meta_handler(request):
        if request.method=='POST':
            state.meta_sends.append(json.loads(request.content))
            if state.send_error:
                raise httpx.ReadTimeout('private-token-must-never-be-logged',request=request)
            if state.meta_status!=200:
                return httpx.Response(state.meta_status,json={'error':{'code':190,'message':'private-provider-body'}})
            return httpx.Response(200,json={'messages':[{'id':f'wamid.out.{len(state.meta_sends)}'}]})
        if request.url.host=='graph.facebook.com':
            return httpx.Response(200,json={'url':state.media_url,'mime_type':'audio/ogg; codecs=opus','file_size':len(state.audio),'sha256':hashlib.sha256(state.audio).hexdigest()})
        return httpx.Response(200,content=state.audio)
    settings=Settings(groq_api_key=SecretStr('gsk_test'),meta_access_token=SecretStr('test-meta-token'),meta_app_secret=SecretStr('test-app-secret'),meta_verify_token=SecretStr('v'*40),meta_phone_number_id='123456',admin_api_key=SecretStr('a'*40),db_path=tmp_path/'db.sqlite3',knowledge_path=ROOT/'data/knowledge.md',groq_min_interval_seconds=0)
    def app():
        sdk=AsyncGroq(api_key='gsk_test',max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(groq_handler)))
        return create_app(settings,sdk,httpx.MockTransport(meta_handler))
    return settings,state,app


def test_health_verification_auth(harness):
    _,_,factory=harness
    with TestClient(factory()) as c:
        assert c.get('/health').json()['worker_running'] is True
        assert c.get('/admin/conversations').status_code==401
        assert c.get('/admin').status_code==200
        assert 'Content-Security-Policy' in c.get('/admin').headers
        assert c.get('/docs').status_code==200
        assert c.get('/openapi.json').status_code==200
        params={'hub.mode':'subscribe','hub.verify_token':'v'*40,'hub.challenge':'12345'}
        r=c.get('/webhook',params=params)
        assert r.status_code==200 and r.text=='12345'
        params['hub.verify_token']='wrong'
        assert c.get('/webhook',params=params).status_code==403
        assert c.post('/webhook',json=payload()).status_code==403


def test_text_duplicate_history_and_restart(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        assert post(c,payload()).json()['accepted']==1
        wait_done(c)
        assert post(c,payload()).json()['accepted']==0
        post(c,payload('فاكر كلامي؟','wamid.in.2'))
        result=wait_done(c,2)
        assert len(state.meta_sends)==2
        assert state.meta_sends[0]['messaging_product']=='whatsapp'
        assert result['conversation']['status']=='active'
        last=json.loads(state.groq_requests[-1].content)['messages']
        assert [m['role'] for m in last]==['system','user','assistant','user']
    with TestClient(factory()) as c:
        assert post(c,payload()).json()['accepted']==0
        rows=c.get('/admin/conversations',headers={'X-Admin-Key':'a'*40}).json()
        assert rows[0]['phone']=='201000000001'
        assert len(state.meta_sends)==2


def test_audio_pipeline_uses_real_sdk_multipart(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        post(c,payload(kind='audio'))
        result=wait_done(c)
        assert result['messages'][0]['text']=='مواعيد الشغل ايه؟'
        assert result['messages'][0]['type']=='audio'
        request=state.groq_requests[0]
        assert b'voice.ogg' in request.content
        assert b'whisper-large-v3-turbo' in request.content
        assert len(state.meta_sends)==1


def test_handoff_summary_pause_manual_reply_resume(harness):
    _,state,factory=harness
    headers={'X-Admin-Key':'a'*40}
    with TestClient(factory()) as c:
        post(c,payload('عايز أكلم موظف'))
        result=wait_done(c)
        assert result['conversation']['status']=='human_required'
        assert result['conversation']['summary_source']=='groq'
        assert result['conversation']['wa_link']=='https://wa.me/201000000001'
        calls=len(state.groq_requests)
        post(c,payload('انت موجود؟','wamid.in.2'))
        wait_done(c,2)
        assert len(state.meta_sends)==1 and len(state.groq_requests)==calls
        assert c.post('/admin/conversations/201000000001/reply',headers=headers,json={'text':'أهلًا، معاك مسؤول الدعم.'}).status_code==200
        assert len(state.meta_sends)==2
        c.post('/admin/conversations/201000000001/resume',headers=headers)
        post(c,payload('مواعيدكم؟','wamid.in.3'))
        assert wait_done(c,3)['conversation']['status']=='active'
        assert len(state.meta_sends)==3


@pytest.mark.parametrize('code',[401,403,404,429,500])
def test_groq_failures_pause_with_fallback(harness,code,caplog):
    _,state,factory=harness
    state.groq_status=code
    with TestClient(factory()) as c:
        post(c,payload());result=wait_done(c)
        assert result['conversation']['status']=='human_required'
        assert result['conversation']['summary_source']=='fallback'
        assert len(state.groq_requests)==1
        assert len(state.meta_sends)==1
        assert 'test-meta-token' not in caplog.text and 'gsk_test' not in caplog.text


def test_unknown_question_handoff_and_summary_failure(harness):
    _,state,factory=harness
    state.handoff=True;state.summary_fail=True
    with TestClient(factory()) as c:
        post(c,payload('سعر عقد سنة كام؟'));result=wait_done(c)
        assert result['conversation']['status']=='human_required'
        assert result['conversation']['summary_source']=='fallback'


def test_invalid_llm_json_fails_closed(harness):
    _,state,factory=harness;state.malformed=True
    with TestClient(factory()) as c:
        post(c,payload());result=wait_done(c)
        assert result['conversation']['last_error']=='groq_invalid_output'
        assert result['conversation']['status']=='human_required'


def test_uncertain_send_is_not_retried(harness,caplog):
    _,state,factory=harness;state.send_error=True
    with TestClient(factory()) as c:
        post(c,payload());result=wait_done(c)
        assert result['conversation']['status']=='human_required'
        assert len(state.meta_sends)==1
        assert result['messages'][-1]['state']=='uncertain'
        post(c,payload());time.sleep(.05)
        assert len(state.meta_sends)==1
        assert 'private-token' not in caplog.text


def test_bad_media_host_never_receives_token(harness):
    _,state,factory=harness;state.media_url='https://example.com/steal-token'
    with TestClient(factory()) as c:
        post(c,payload(kind='audio'));result=wait_done(c)
        assert result['conversation']['last_error']=='audio_untrusted_url'
        assert not state.groq_requests


def test_status_notifications_do_not_trigger_groq(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        data=payload();value=data['entry'][0]['changes'][0]['value']
        value.pop('messages');value['statuses']=[{'id':'unknown','status':'delivered','timestamp':str(int(time.time()))}]
        assert post(c,data).json()=={'accepted':0}
        assert not state.groq_requests and not state.meta_sends


def test_delivery_failure_marks_human(harness):
    _,_,factory=harness
    with TestClient(factory()) as c:
        post(c,payload());wait_done(c)
        data=payload();v=data['entry'][0]['changes'][0]['value'];v.pop('messages')
        v['statuses']=[{'id':'wamid.out.1','status':'failed','errors':[{'code':131030}]}]
        post(c,data)
        result=c.get('/admin/conversations/201000000001',headers={'X-Admin-Key':'a'*40}).json()
        assert result['conversation']['last_error']=='meta_delivery_131030'
        assert result['conversation']['status']=='human_required'


def test_old_message_is_not_sent_outside_window(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        post(c,payload(timestamp=int(time.time())-90000));result=wait_done(c)
        assert result['conversation']['last_error']=='whatsapp_24h_window_closed'
        assert not state.groq_requests and not state.meta_sends


def test_database_recovery_and_daily_cap(tmp_path):
    db=Database(tmp_path/'test.sqlite3');db.init()
    m=Inbound(id='wamid.a',phone='201000000001',timestamp=int(time.time()),type='text',text='Hello')
    assert db.receive(m) and not db.receive(m)
    job=db.next_job();db.begin_send(m.phone,'Hello',job['id'],'bot')
    db.recover()
    assert db.conversation(m.phone)['status']=='human_required'
    assert db.messages(m.phone,20)[-1]['state']=='uncertain'
    assert db.reserve_groq_call(1) and not db.reserve_groq_call(1)


@pytest.mark.parametrize('url',["http://lookaside.fbsbx.com/a","https://lookaside.fbsbx.com.evil.org/a","https://127.0.0.1/a","https://x:password@lookaside.fbsbx.com/a","https://lookaside.fbsbx.com:9000/a"])
def test_media_url_validation(url):
    assert not WhatsApp.safe_media_url(url)


@pytest.mark.parametrize('text',['عايز اكلم موظف','عاوز أتكلم مع إنسان','حولني لموظف','I want to speak to a human','Please connect me to an agent'])
def test_human_requests(text):
    assert asks_for_human(text)


def test_signature_tampering():
    body,headers=signed(payload());sig=headers['X-Hub-Signature-256']
    assert verify_signature(body,sig,'test-app-secret')
    assert not verify_signature(body+b' ',sig,'test-app-secret')
    assert not verify_signature(body,sig,'')


def test_batched_messages_preserve_previous_assistant_turn(harness):
    _,state,factory=harness
    data=payload();v=data['entry'][0]['changes'][0]['value']
    v['messages'].append(payload('شكرا، ومواعيدكم؟','wamid.in.2')['entry'][0]['changes'][0]['value']['messages'][0])
    with TestClient(factory()) as c:
        assert post(c,data).json()['accepted']==2
        wait_done(c,2)
        messages=json.loads(state.groq_requests[-1].content)['messages']
        assert [m['role'] for m in messages]==['system','user','assistant','user']
        assert messages[-1]['content']=='شكرا، ومواعيدكم؟'


def test_company_answer_without_evidence_escalates(harness):
    _,state,factory=harness;state.no_evidence=True
    with TestClient(factory()) as c:
        post(c,payload());result=wait_done(c)
        assert result['conversation']['status']=='human_required'
        assert 'Missing verified' in result['conversation']['last_error']


def test_groq_network_failure_is_safe(harness,caplog):
    _,state,factory=harness;state.groq_network=True
    with TestClient(factory()) as c:
        post(c,payload());result=wait_done(c)
        assert result['conversation']['last_error']=='groq_network_or_timeout'
        assert 'sensitive-provider-text' not in caplog.text


def test_audio_size_limit_without_groq_call(harness):
    settings,state,factory=harness;settings.max_audio_bytes=1024;state.audio=b'x'*2048
    with TestClient(factory()) as c:
        post(c,payload(kind='audio'));result=wait_done(c)
        assert result['conversation']['last_error']=='audio_too_large'
        assert not state.groq_requests


def test_admin_unauthorized_mutation_is_denied(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        post(c,payload());wait_done(c)
        for action in ('pause','resume','resolve','reply'):
            assert c.post('/admin/conversations/201000000001/'+action,json={'text':'unauthorized'}).status_code==401
        assert len(state.meta_sends)==1


def test_resolved_stays_paused_on_new_message(harness):
    _,state,factory=harness
    with TestClient(factory()) as c:
        post(c,payload());wait_done(c)
        c.post('/admin/conversations/201000000001/resolve',headers={'X-Admin-Key':'a'*40})
        post(c,payload('new question','wamid.in.2'));result=wait_done(c,2)
        assert result['conversation']['status']=='resolved'
        assert len(state.meta_sends)==1


def test_startup_before_credentials_are_added(tmp_path):
    settings=Settings(db_path=tmp_path/'initial.sqlite3')
    with TestClient(create_app(settings)) as c:
        r=c.get('/health')
        assert r.status_code==200 and r.json()['configured'] is False
        assert r.json()['worker_running'] is True
        assert c.get('/admin/config').status_code==503
        assert c.post('/webhook',json={}).status_code==503
