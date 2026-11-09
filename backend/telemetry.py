"""Only normalized operational signals. Never include cookies, bodies or customer PII."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def emit(environment, release, local=False):
    event = dict(id=str(uuid.uuid4()),source_id='rentalboard-api',project='rentalboard',environment=environment,
                 service='rentalboard-api',release=release,occurred_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                 level='error',signature='api.availability')
    line=json.dumps(event)
    print(line,flush=True)
    path=os.getenv('EVENT_LOG_PATH') if local else None
    if path:
        try:
            destination=Path(path)
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('a',encoding='utf-8') as stream:stream.write(line+'\n')
        except OSError:
            # Telemetry storage must not break the customer request.
            print('{"telemetry_write_failed":true}',flush=True)
