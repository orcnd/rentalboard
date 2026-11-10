"""Connect RentalBoard's normalized local events to the ai-code-factory observer/worker."""
import argparse
import importlib.util
import json
import re
import time
from pathlib import Path


def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory-root',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--once',action='store_true')
    mode.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    factory=Path(args.factory_root).resolve()
    observer_module=load(factory/'observability-engine/scripts/observer.py','factory_observer')
    worker_module=load(factory/'observability-engine/scripts/worker.py','factory_worker')
    settings=json.loads((root/'.factory/monitor.json').read_text())
    policy=json.loads((factory/'observability-engine/config/policy.json').read_text())
    policy['scope']=settings['scope']
    config=json.loads((factory/'observability-engine/config/dispatch.json').read_text())
    config['probe_profiles'][policy['probe']['profile_ref']]=settings['probe']
    folder=root/'.factory/runs'
    folder.mkdir(parents=True,exist_ok=True)
    source=folder/'events.jsonl'
    source.touch(exist_ok=True)
    state_name=re.sub(r'[^a-zA-Z0-9_-]+','-',settings['scope']['environment']).strip('-').lower()
    state_path=folder/f'observation-{state_name}.sqlite'
    observer=observer_module.Observer(state_path,policy)
    worker=worker_module.Worker(state_path,config)
    try:
        while True:
            observer.poll(source)
            print(json.dumps({'observation':observer.summary(),'delivery':worker.run_once()}),flush=True)
            if args.once:break
            time.sleep(policy['poll_seconds'])
    except KeyboardInterrupt:pass
    finally:
        worker.db.close();observer.db.close()


if __name__=='__main__':main()
