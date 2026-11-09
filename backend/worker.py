from fastapi import Request
from fastapi.responses import Response
from workers import asgi
from app import create_app

app = create_app(cloudflare=True)


@app.get('/{path:path}')
async def frontend(path: str, request: Request):
    if path=='api' or path.startswith('api/'):
        return Response(status_code=404)
    result = await request.scope['env'].ASSETS.fetch('https://assets.local/'+path)
    headers = {}
    for name in ('content-type','cache-control','etag'):
        value = result.headers.get(name)
        if value:headers[name]=str(value)
    return Response(content=bytes(await result.bytes()),status_code=result.status,headers=headers)


Default = asgi.entrypoint(app)
