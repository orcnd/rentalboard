"""Destructive test data is allowed only in a loopback local Workers/D1 instance."""
import concurrent.futures
from datetime import timedelta
from urllib.parse import urlsplit
import httpx
from backend.app import today


def main():
    base='http://127.0.0.1:8790'
    if urlsplit(base).hostname not in {'127.0.0.1','localhost'}:
        raise RuntimeError('This smoke test is local-only')
    with httpx.Client(base_url=base,timeout=30) as client:
        assert client.get('/api/config').json()['demo_enabled']
        login=client.post('/api/auth/demo',headers={'origin':base})
        assert login.status_code==200,login.status_code
        headers={'origin':base,'X-CSRF-Token':login.json()['csrf']}
        board=client.get('/api/board').json()
        equipment=next(e for e in board['equipment'] if e['state']=='available')
        body=dict(equipment_id=equipment['id'],customer_id=board['customers'][0]['id'],starts_on=(today()+timedelta(days=35)).isoformat(),ends_on=(today()+timedelta(days=37)).isoformat())
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:client.post('/api/reservations',headers=headers,json=body).status_code,range(5)))
        assert results.count(201)==1,results
        assert results.count(409)==4,results
        me=client.get('/api/session').json()['user']
        assert me['workspace_id']==equipment['workspace_id']
        assert client.get('/api/health').json()['status']=='healthy'
        assert client.post('/api/customers',headers={'origin':'https://evil.invalid'},json={'name':'Must not create'}).status_code==403
        assert client.post('/api/auth/logout',headers=headers).status_code==200
        assert client.get('/api/board').status_code==401
    print('PASS: real local Workers/Pyodide + D1: 1 created / 4 conflicts, workspace session, health, Origin rejection and logout.')


if __name__=='__main__':main()
