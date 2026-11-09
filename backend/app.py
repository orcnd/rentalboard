import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

if __package__:
    from .store import D1Store, SQLiteStore
    from .telemetry import emit
else:
    # Wrangler's Python module root is the entrypoint directory.
    from store import D1Store, SQLiteStore
    from telemetry import emit


def uid():
    return str(uuid.uuid4())


def today():
    return datetime.now(timezone(timedelta(hours=3))).date()


def config(request, key, default=''):
    env = request.scope.get('env')
    return str(getattr(env, key, default)) if env is not None else os.getenv(key, default)


def store(request: Request):
    env = request.scope.get('env')
    return D1Store(env.DB) if env is not None else request.app.state.store


class InputModel(BaseModel):
    model_config = {'extra': 'forbid'}

    @field_validator('*', mode='before')
    @classmethod
    def trim_strings(cls, value, info):
        return value.strip() if isinstance(value,str) and info.field_name!='password' else value


class Account(InputModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=12, max_length=72)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if value.count('@') != 1 or '.' not in value.split('@')[-1] or any(c.isspace() for c in value):
            raise ValueError('Geçerli bir e-posta adresi gir.')
        return value

    @field_validator('password')
    @classmethod
    def password_valid(cls, value):
        if len(value.encode()) > 72:
            raise ValueError('Parola UTF-8 olarak en fazla 72 byte olabilir.')
        return value


class Registration(Account):
    name: str = Field(min_length=2, max_length=80)
    workspace: str = Field(min_length=2, max_length=80)


class EquipmentInput(InputModel):
    name: str = Field(min_length=2, max_length=100)
    category: str = Field(pattern='^(camera|lens|light|audio|accessory)$')
    serial: str = Field(default='', max_length=80)
    day_rate: int = Field(ge=0, le=100_000_000)


class CustomerInput(InputModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(default='', max_length=200)
    phone: str = Field(default='', max_length=30)


class ReservationInput(InputModel):
    equipment_id: str = Field(max_length=60)
    customer_id: str = Field(max_length=60)
    starts_on: date
    ends_on: date
    notes: str = Field(default='', max_length=1000)


class StatusInput(InputModel):
    status: str = Field(pattern='^(out|returned|cancelled)$')


class EquipmentState(InputModel):
    state: str | None = Field(default=None,pattern='^(available|maintenance|retired)$')
    name: str | None = Field(default=None,min_length=2,max_length=100)
    category: str | None = Field(default=None,pattern='^(camera|lens|light|audio|accessory)$')
    serial: str | None = Field(default=None,max_length=80)
    day_rate: int | None = Field(default=None,ge=0,le=100_000_000)


async def actor(request: Request):
    token = request.cookies.get('rb_session', '')
    if not token:
        raise HTTPException(401, 'Oturum açman gerekiyor.')
    rows = await store(request).query('SELECT u.id,u.name,u.email,u.role,u.workspace_id,w.name AS workspace_name,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id JOIN workspaces w ON w.id=u.workspace_id WHERE s.token_hash=? AND s.expires_at>?', (hashlib.sha256(token.encode()).hexdigest(), int(time.time())))
    if not rows:
        raise HTTPException(401, 'Oturumun sona erdi. Yeniden giriş yap.')
    user = rows[0]
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and not hmac.compare_digest(request.headers.get('X-CSRF-Token', '').encode(), user['csrf'].encode()):
        raise HTTPException(403, 'İstek doğrulanamadı. Sayfayı yenile.')
    return user


async def editor(user=Depends(actor)):
    if user['role'] not in {'owner', 'operator'}:
        raise HTTPException(403, 'Bu işlem için düzenleme yetkin yok.')
    return user


async def limit_auth(request, scope):
    ip = request.headers.get('cf-connecting-ip', 'unknown') if request.scope.get('env') is not None else (request.client.host if request.client else 'local')
    key = hashlib.sha256(f'{ip}:{scope}:{int(time.time())//900}'.encode()).hexdigest()
    rows = await store(request).query('INSERT INTO auth_limits(id,attempts) VALUES (?,1) ON CONFLICT(id) DO UPDATE SET attempts=attempts+1 RETURNING attempts', (key,))
    if rows[0]['attempts'] > 20:
        raise HTTPException(429, 'Çok fazla deneme. Biraz sonra tekrar dene.')


async def session(request, user_id, response, demo=False):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    seconds = 86400 if demo else 604800
    await store(request).query('INSERT INTO sessions VALUES (?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf, int(time.time())+seconds))
    response.set_cookie('rb_session', token, max_age=seconds, httponly=True, secure=request.url.scheme == 'https', samesite='lax', path='/')
    return {'csrf': csrf}


def db_error(error):
    message = str(error)
    for code, text in {
        'reservation_conflict': 'Bu ekipman seçilen tarihlerde zaten rezerve. Başka tarih veya ekipman seç.',
        'equipment_unavailable': 'Bu ekipman şu anda rezervasyona kapalı.',
        'equipment_already_out': 'Bu ekipmanın önceki kiralaması henüz iade edilmedi.',
        'equipment_limit': 'Başlangıç planında en fazla 50 ekipman ekleyebilirsin.'
    }.items():
        if code in message:
            return HTTPException(409, text)
    return HTTPException(500, 'Sunucu işlemi tamamlayamadı. Biraz sonra tekrar dene.')


def create_app(db_path=None, cloudflare=False):
    @asynccontextmanager
    async def lifespan(app):
        if not cloudflare:
            path = Path(db_path or os.getenv('DATABASE_PATH', '.data/rentalboard.sqlite'))
            path.parent.mkdir(parents=True, exist_ok=True)
            app.state.store = SQLiteStore(path)
            connection = app.state.store.connect()
            try:
                connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY)')
                for migration in sorted((Path(__file__).resolve().parents[1]/'migrations').glob('*.sql')):
                    if not connection.execute('SELECT 1 FROM schema_migrations WHERE name=?',(migration.name,)).fetchone():
                        connection.executescript('BEGIN;\n'+migration.read_text())
                        connection.execute('INSERT INTO schema_migrations VALUES (?)',(migration.name,))
                        connection.commit()
            finally:
                connection.close()
        yield

    app = FastAPI(title='RentalBoard API', version='0.1.0', lifespan=lifespan, docs_url=None if cloudflare else '/api/docs')

    @app.middleware('http')
    async def boundary(request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            expected = config(request, 'PUBLIC_ORIGIN', 'http://127.0.0.1:5174').rstrip('/')
            if request.headers.get('origin', '').rstrip('/') != expected or request.headers.get('sec-fetch-site') == 'cross-site':
                return Response(json.dumps({'detail': 'İstek kaynağına izin verilmiyor.'}), status_code=403, media_type='application/json')
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length)>16384):
                return Response(status_code=413)
            collected=[]
            size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>16384:return Response(status_code=413)
                collected.append(chunk)
            request._body=b''.join(collected)
        try:
            response = await call_next(request)
        except Exception:
            emit(config(request,'ENVIRONMENT','development'),config(request,'RELEASE_ID','rentalboard-0.1.0'),local=request.scope.get('env') is None)
            return Response(json.dumps({'detail':'Sunucu işlemi tamamlayamadı.'}),status_code=500,media_type='application/json',headers={'Cache-Control':'no-store'})
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if request.url.scheme=='https':
            response.headers['Strict-Transport-Security']='max-age=31536000'
        if response.status_code >= 500:
            emit(config(request,'ENVIRONMENT','development'),config(request,'RELEASE_ID','rentalboard-0.1.0'),local=request.scope.get('env') is None)
        return response

    @app.get('/api/health')
    async def health(request: Request, response: Response):
        status = 'healthy'
        try:
            await store(request).query('SELECT id FROM equipment LIMIT 1')
        except Exception:
            response.status_code, status = 503, 'degraded'
        return dict(service='rentalboard-api',environment=config(request,'ENVIRONMENT','development'),release=config(request,'RELEASE_ID','rentalboard-0.1.0'),status=status,signature='api.availability')

    @app.get('/api/config')
    async def public_config(request: Request):
        return {'demo_enabled':config(request,'DEMO_ENABLED','true' if not cloudflare else 'false')=='true'}

    @app.get('/api/session')
    async def me(request: Request, user=Depends(actor)):
        return dict(user=user, today=today().isoformat(), demo_enabled=config(request,'DEMO_ENABLED','true' if not cloudflare else 'false')=='true', plan=dict(name='Başlangıç',equipment_limit=50))

    @app.post('/api/auth/register', status_code=201)
    async def register(data: Registration, request: Request, response: Response):
        await limit_auth(request, 'register')
        user_id, workspace_id = uid(), uid()
        hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt(rounds=12)).decode()
        try:
            await store(request).batch([
                ('INSERT INTO workspaces VALUES (?,?,?)',(workspace_id,data.workspace.strip(),datetime.now(timezone.utc).isoformat())),
                ('INSERT INTO users VALUES (?,?,?,?,?,?)',(user_id,workspace_id,data.name.strip(),data.email,hashed,'owner'))])
        except Exception as error:
            if 'UNIQUE' in str(error):
                raise HTTPException(409,'Bu e-posta ile hesap oluşturulamadı.') from error
            raise HTTPException(500,'Hesap oluşturulamadı. Biraz sonra tekrar dene.') from error
        return await session(request,user_id,response)

    @app.post('/api/auth/login')
    async def login(data: Account, request: Request, response: Response):
        await limit_auth(request, 'login')
        await limit_auth(request, 'email:'+data.email)
        rows=await store(request).query('SELECT id,password_hash FROM users WHERE email=?',(data.email,))
        # A valid precomputed cost-12 hash keeps unknown-user work comparable.
        candidate=rows[0]['password_hash'] if rows else '$2b$12$C6UzMDM.H6dfI/f/IKcEe.5HpC2gKRk87m7sawUN4j0W.1m/zGtpK'
        valid=bcrypt.checkpw(data.password.encode(),candidate.encode())
        if not rows or not valid:
            raise HTTPException(401,'E-posta veya parola doğru değil.')
        return await session(request,rows[0]['id'],response)

    @app.post('/api/auth/logout')
    async def logout(request: Request, response: Response, user=Depends(actor)):
        token=request.cookies.get('rb_session','')
        await store(request).query('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
        response.delete_cookie('rb_session',path='/')
        return {'ok': True}

    @app.post('/api/auth/demo')
    async def demo(request: Request, response: Response):
        if config(request,'DEMO_ENABLED','true' if not cloudflare else 'false')!='true':
            raise HTTPException(404,'Demo açık değil.')
        await limit_auth(request,'demo')
        user_id,ws=uid(),uid()
        monday=today()-timedelta(days=today().weekday())
        statements=[('INSERT INTO workspaces VALUES (?,?,?)',(ws,'Kadraja Kiralama',datetime.now(timezone.utc).isoformat())),('INSERT INTO users VALUES (?,?,?,?,?,?)',(user_id,ws,'Deniz Aksoy','demo-'+user_id+'@example.invalid',bcrypt.hashpw(secrets.token_bytes(24),bcrypt.gensalt(rounds=12)).decode(),'owner'))]
        items=[('Sony A7 IV','camera','SN-0421',185000),('Canon EOS R6 II','camera','SN-0419',165000),('Sony FE 24–70mm GM II','lens','LN-0108',95000),('Sigma 85mm f/1.4','lens','LN-0124',65000),('Aputure 300d II','light','LT-0032',85000),('DJI RS 4 Pro','accessory','AC-0018',75000),('RØDE Wireless PRO','audio','AU-0007',45000),('Godox AD600 Pro','light','LT-0041',70000)]
        gear=[uid() for _ in items]
        for identifier,item in zip(gear,items):
            statements.append(('INSERT INTO equipment(id,workspace_id,name,category,serial,day_rate,state) VALUES (?,?,?,?,?,?,?)',(identifier,ws,*item,'maintenance' if item[0].startswith('Godox') else 'available')))
        clients=[uid() for _ in range(4)]
        for identifier,name in zip(clients,['Mavi Film','Ece Yılmaz','Studio Kestane','Atlas Prodüksiyon']):
            statements.append(('INSERT INTO customers VALUES (?,?,?,?,?)',(identifier,ws,name,'','')))
        plans=[(0,0,0,3,'out'),(1,1,1,4,'reserved'),(2,0,0,3,'out'),(3,2,3,6,'reserved'),(4,3,0,2,'reserved'),(5,3,4,7,'reserved'),(6,1,2,5,'reserved'),(0,2,4,7,'reserved')]
        for g,c,start,end,status in plans:
            statements.append(('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?,?)',(uid(),ws,gear[g],clients[c],(monday+timedelta(days=start)).isoformat(),(monday+timedelta(days=end)).isoformat(),items[g][3],status,'Sentetik demo rezervasyonu',datetime.now(timezone.utc).isoformat())))
        await store(request).batch(statements)
        return await session(request,user_id,response,demo=True)

    @app.get('/api/board')
    async def board(request: Request, user=Depends(actor)):
        db,ws=store(request),user['workspace_id']
        return dict(equipment=await db.query('SELECT * FROM equipment WHERE workspace_id=? ORDER BY category,name',(ws,)),customers=await db.query('SELECT * FROM customers WHERE workspace_id=? ORDER BY name',(ws,)),reservations=await db.query('SELECT r.*,e.name AS equipment_name,e.category,c.name AS customer_name FROM reservations r JOIN equipment e ON e.id=r.equipment_id JOIN customers c ON c.id=r.customer_id WHERE r.workspace_id=? ORDER BY starts_on,created_at',(ws,)))

    @app.post('/api/equipment',status_code=201)
    async def add_equipment(data: EquipmentInput,request: Request,user=Depends(editor)):
        identifier=uid()
        try:
            await store(request).query('INSERT INTO equipment(id,workspace_id,name,category,serial,day_rate) VALUES (?,?,?,?,?,?)',(identifier,user['workspace_id'],data.name.strip(),data.category,data.serial.strip(),data.day_rate))
        except Exception as error:raise db_error(error) from error
        return {'id':identifier}

    @app.patch('/api/equipment/{identifier}')
    async def equipment_state(identifier: str,data: EquipmentState,request: Request,user=Depends(editor)):
        rows=await store(request).query('UPDATE equipment SET state=COALESCE(?,state),name=COALESCE(?,name),category=COALESCE(?,category),serial=COALESCE(?,serial),day_rate=COALESCE(?,day_rate) WHERE id=? AND workspace_id=? RETURNING id',(data.state,data.name,data.category,data.serial,data.day_rate,identifier,user['workspace_id']))
        if not rows:raise HTTPException(404,'Ekipman bulunamadı.')
        return {'ok':True}

    @app.post('/api/customers',status_code=201)
    async def add_customer(data: CustomerInput,request: Request,user=Depends(editor)):
        identifier=uid()
        await store(request).query('INSERT INTO customers VALUES (?,?,?,?,?)',(identifier,user['workspace_id'],data.name.strip(),data.email.strip(),data.phone.strip()))
        return {'id':identifier}

    @app.post('/api/reservations',status_code=201)
    async def reserve(data: ReservationInput,request: Request,user=Depends(editor)):
        if not 1 <= (data.ends_on-data.starts_on).days <= 90:
            raise HTTPException(422,'İade tarihi başlangıçtan sonra olmalı; süre en fazla 90 gün olabilir.')
        db,ws=store(request),user['workspace_id']
        gear=await db.query('SELECT day_rate FROM equipment WHERE id=? AND workspace_id=?',(data.equipment_id,ws))
        client=await db.query('SELECT id FROM customers WHERE id=? AND workspace_id=?',(data.customer_id,ws))
        if not gear or not client:raise HTTPException(404,'Ekipman veya müşteri bulunamadı.')
        identifier=uid()
        try:
            await db.query('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?,?)',(identifier,ws,data.equipment_id,data.customer_id,data.starts_on.isoformat(),data.ends_on.isoformat(),gear[0]['day_rate'],'reserved',data.notes.strip(),datetime.now(timezone.utc).isoformat()))
        except Exception as error:raise db_error(error) from error
        return {'id':identifier,'total':gear[0]['day_rate']*(data.ends_on-data.starts_on).days}

    @app.patch('/api/reservations/{identifier}')
    async def transition(identifier: str,data: StatusInput,request: Request,user=Depends(editor)):
        db,ws=store(request),user['workspace_id']
        rows=await db.query('SELECT status,starts_on FROM reservations WHERE id=? AND workspace_id=?',(identifier,ws))
        if not rows:raise HTTPException(404,'Rezervasyon bulunamadı.')
        current=rows[0]['status']
        if data.status not in {'reserved':{'out','cancelled'},'out':{'returned'}}.get(current,set()):
            raise HTTPException(409,'Bu rezervasyonda istenen durum geçişi yapılamaz.')
        if data.status=='out' and rows[0]['starts_on']>today().isoformat():
            raise HTTPException(409,'Başlangıç tarihi gelmeden teslim yapılamaz.')
        try:
            changed=await db.query('UPDATE reservations SET status=? WHERE id=? AND workspace_id=? AND status=? RETURNING id',(data.status,identifier,ws,current))
        except Exception as error:raise db_error(error) from error
        if not changed:raise HTTPException(409,'Rezervasyon başka bir işlemde güncellendi. Sayfayı yenile.')
        return {'ok':True}

    @app.get('/api/team')
    async def team(request: Request,user=Depends(actor)):
        return await store(request).query('SELECT name,email,role FROM users WHERE workspace_id=? ORDER BY name',(user['workspace_id'],))

    return app


app = create_app()
