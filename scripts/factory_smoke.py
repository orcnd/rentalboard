"""Use ai-code-factory on synthetic RentalBoard telemetry without touching production."""
import argparse
import importlib.util
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory-root',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    factory=Path(args.factory_root).resolve()
    obs=load(factory/'observability-engine/scripts/observer.py','factory_observer')
    dispatch=load(factory/'observability-engine/scripts/worker.py','factory_worker')
    policy=json.loads((factory/'observability-engine/config/policy.json').read_text())
    project=json.loads((root/'.factory/monitor.json').read_text())
    policy['scope']=project['scope']
    config=json.loads((factory/'observability-engine/config/dispatch.json').read_text())
    config['probe_profiles'][policy['probe']['profile_ref']]=project['probe']
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)
        events=[dict(id=str(i),source_id='rentalboard-synthetic-test',**policy['scope'],release='rentalboard-0.1.0',occurred_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),level='error',signature='api.availability') for i in range(3)]
        source=folder/'events.jsonl'
        source.write_text(''.join(json.dumps(e)+'\n' for e in events))
        observer=obs.Observer(folder/'state.sqlite',policy,replay=True)
        worker=dispatch.Worker(folder/'state.sqlite',config,allow_demo=True)
        try:
            observer.poll(source)
            worker.run_once();delivery=worker.run_once()
            incident=json.loads(worker.db.execute('SELECT value FROM incidents').fetchone()[0])
            assert incident['state']=='investigating'  # A healthy real service does not confirm synthetic errors.
            assert worker.db.execute('SELECT COUNT(*) FROM factory_tasks').fetchone()[0]==1
            assert delivery.get('waiting_adapter')==1  # No configured LLM is a visible wait, not success.
            print('PASS: real factory observer/worker consumed synthetic RentalBoard signals; real health probe, one intake, model waiting, no false incident resolution.')
        finally:
            worker.db.close();observer.db.close()


if __name__=='__main__':main()
