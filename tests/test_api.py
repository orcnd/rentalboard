import concurrent.futures
import sqlite3
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app,today


@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv('PUBLIC_ORIGIN','http://testserver')
    monkeypatch.setenv('DEMO_ENABLED','true')
    path=tmp_path/'test.sqlite'
    app=create_app(path)
    with TestClient(app) as client:
        result=client.post('/api/auth/demo',headers={'origin':'http://testserver'})
        assert result.status_code==200
        headers={'origin':'http://testserver','X-CSRF-Token':result.json()['csrf']}
        yield client,headers,path,app


def booking(client,offset=10):
    board=client.get('/api/board').json()
    return dict(equipment_id=next(e['id'] for e in board['equipment'] if e['state']=='available'),customer_id=board['customers'][0]['id'],starts_on=(today()+timedelta(days=offset)).isoformat(),ends_on=(today()+timedelta(days=offset+2)).isoformat(),notes='Test')


def test_auth_required_and_session_cookie(env):
    client,headers,path,app=env
    assert client.get('/api/session').json()['user']['role']=='owner'
    assert client.cookies.get('rb_session')
    assert client.post('/api/auth/logout',headers=headers).status_code==200
    assert client.get('/api/board').status_code==401


def test_origin_and_csrf_are_required(env):
    client,headers,*_=env
    body={'name':'Test müşteri'}
    assert client.post('/api/customers',json=body).status_code==403
    assert client.post('/api/customers',json=body,headers={'origin':'http://testserver'}).status_code==403
    assert client.post('/api/customers',json=body,headers={**headers,'origin':'https://evil.invalid'}).status_code==403


def test_booking_conflict_and_adjacent_dates(env):
    client,headers,*_=env
    data=booking(client)
    first=client.post('/api/reservations',json=data,headers=headers)
    assert first.status_code==201
    assert first.json()['total']==2*next(e['day_rate'] for e in client.get('/api/board').json()['equipment'] if e['id']==data['equipment_id'])
    assert client.post('/api/reservations',json=data,headers=headers).status_code==409
    adjacent={**data,'starts_on':data['ends_on'],'ends_on':(today()+timedelta(days=14)).isoformat()}
    assert client.post('/api/reservations',json=adjacent,headers=headers).status_code==201


def test_cancellation_releases_dates(env):
    client,headers,*_=env
    data=booking(client)
    identifier=client.post('/api/reservations',json=data,headers=headers).json()['id']
    assert client.patch('/api/reservations/'+identifier,json={'status':'cancelled'},headers=headers).status_code==200
    assert client.post('/api/reservations',json=data,headers=headers).status_code==201


def test_tenant_isolation(env):
    client,headers,path,app=env
    other=TestClient(app)
    try:
        response=other.post('/api/auth/demo',headers={'origin':'http://testserver'})
        other_headers={**headers,'X-CSRF-Token':response.json()['csrf']}
        foreign=booking(client)
        assert other.post('/api/reservations',json=foreign,headers=other_headers).status_code==404
        assert other.patch('/api/equipment/'+foreign['equipment_id'],json={'state':'maintenance'},headers=other_headers).status_code==404
        own={e['id'] for e in other.get('/api/board').json()['equipment']}
        assert foreign['equipment_id'] not in own
    finally:other.close()


def test_viewer_cannot_mutate(env):
    client,headers,path,_=env
    user=client.get('/api/session').json()['user']
    with sqlite3.connect(path) as db:db.execute("UPDATE users SET role='viewer' WHERE id=?",(user['id'],))
    assert client.get('/api/board').status_code==200
    assert client.post('/api/customers',json={'name':'Blocked'},headers=headers).status_code==403
    assert client.post('/api/reservations',json=booking(client),headers=headers).status_code==403


def test_status_machine_and_maintenance_guard(env):
    client,headers,*_=env
    board=client.get('/api/board').json()
    out=next(r for r in board['reservations'] if r['status']=='out')
    assert client.patch('/api/reservations/'+out['id'],json={'status':'returned'},headers=headers).status_code==200
    assert client.patch('/api/reservations/'+out['id'],json={'status':'out'},headers=headers).status_code==409
    data=booking(client,offset=0)
    data['equipment_id']=out['equipment_id']
    response=client.post('/api/reservations',json=data,headers=headers)
    assert response.status_code==201
    identifier=response.json()['id']
    assert client.patch('/api/equipment/'+data['equipment_id'],json={'state':'maintenance'},headers=headers).status_code==200
    assert client.patch('/api/reservations/'+identifier,json={'status':'out'},headers=headers).status_code==409


def test_invalid_dates_money_and_whitespace(env):
    client,headers,*_=env
    data=booking(client)
    assert client.post('/api/reservations',json={**data,'ends_on':data['starts_on']},headers=headers).status_code==422
    assert client.post('/api/equipment',json={'name':'Lens','category':'lens','day_rate':-1},headers=headers).status_code==422
    assert client.post('/api/customers',json={'name':'   '},headers=headers).status_code==422
    assert client.post('/api/equipment',json={'name':'Lens','category':'lens','day_rate':100,'workspace_id':'other'},headers=headers).status_code==422


def test_unknown_user_and_registration(env):
    client,headers,*_=env
    assert client.post('/api/auth/login',json={'email':'missing@example.com','password':'not-the-password'},headers={'origin':'http://testserver'}).status_code==401
    data={'email':'owner@example.com','password':'safe-test-passphrase','name':'Deniz','workspace':'Yeni İşletme'}
    response=client.post('/api/auth/register',json=data,headers={'origin':'http://testserver'})
    assert response.status_code==201
    assert client.get('/api/board').json()['equipment']==[]
    assert client.post('/api/auth/login',json={k:data[k] for k in ('email','password')},headers={'origin':'http://testserver'}).status_code==200


def test_db_serializes_competing_reservations(env):
    client,headers,path,_=env
    data=booking(client,offset=30)
    workspace=client.get('/api/session').json()['user']['workspace_id']
    def insert(_):
        db=sqlite3.connect(path,timeout=10)
        try:
            with db:
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),workspace,data['equipment_id'],data['customer_id'],data['starts_on'],data['ends_on'],100,'reserved','','test'))
            return 'created'
        except sqlite3.IntegrityError as error:
            assert 'reservation_conflict' in str(error)
            return 'conflict'
        finally:db.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(insert,range(5)))
    assert results.count('created')==1
    assert results.count('conflict')==4


def test_overdue_equipment_cannot_be_handed_out_twice(env):
    client,headers,path,_=env
    out=next(r for r in client.get('/api/board').json()['reservations'] if r['status']=='out')
    with sqlite3.connect(path) as db:
        db.execute('UPDATE reservations SET starts_on=?,ends_on=? WHERE id=?',((today()-timedelta(days=4)).isoformat(),(today()-timedelta(days=1)).isoformat(),out['id']))
    data={**booking(client,offset=0),'equipment_id':out['equipment_id']}
    identifier=client.post('/api/reservations',json=data,headers=headers).json()['id']
    response=client.patch('/api/reservations/'+identifier,json={'status':'out'},headers=headers)
    assert response.status_code==409
    assert 'iade edilmedi' in response.json()['detail']


def test_chunked_oversized_body_is_rejected(env):
    client,headers,*_=env
    response=client.post('/api/customers',content=iter([b'x'*9000,b'y'*9000]),headers={**headers,'content-type':'application/json'})
    assert response.status_code==413


def test_health_degradation_emits_no_customer_or_credential_data(env,tmp_path,monkeypatch):
    import json
    client,_,_,app=env
    log=tmp_path/'events.jsonl'
    monkeypatch.setenv('EVENT_LOG_PATH',str(log))
    async def failing(*args,**kwargs):raise RuntimeError('sensitive-customer-do-not-log')
    monkeypatch.setattr(app.state.store,'query',failing)
    for _ in range(3):
        response=client.get('/api/health')
        assert response.status_code==503
        assert response.json()['status']=='degraded'
    text=log.read_text()
    assert 'sensitive-customer-do-not-log' not in text
    events=[json.loads(line) for line in text.splitlines()]
    assert len(events)==3
    assert all(e['signature']=='api.availability' for e in events)
    assert all('password' not in e and 'email' not in e for e in events)


def test_existing_quote_preserves_rate_when_inventory_price_changes(env):
    client,headers,*_=env
    data=booking(client)
    result=client.post('/api/reservations',json=data,headers=headers)
    amount=result.json()['total']
    assert client.patch('/api/equipment/'+data['equipment_id'],json={'day_rate':999999},headers=headers).status_code==200
    reservation=next(r for r in client.get('/api/board').json()['reservations'] if r['id']==result.json()['id'])
    assert reservation['day_rate']*2==amount
