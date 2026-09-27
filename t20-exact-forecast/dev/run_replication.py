"""Run the predeclared eight-slot batch without embedding credentials in commands."""
from __future__ import annotations
import argparse
import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
from runtime_contract import verify_runtime

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'validation/replication-20260927'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-path', type=Path, required=True)
    parser.add_argument('--claude-token-file', type=Path, required=True)
    parser.add_argument('--codex-auth-file', type=Path, required=True)
    args = parser.parse_args()
    task = args.task_path.resolve()
    verify_runtime(task)
    plan = json.loads((BATCH / 'plan.json').read_text())
    slots = {s['trial_id']: s for s in plan['slots']}
    token = args.claude_token_file.read_text().strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError('Invalid credential file; content is never displayed')
    if not args.codex_auth_file.is_file():
        raise ValueError('Codex native sign-in file is missing')
    jobs = ROOT / 'validation/jobs'
    for slot in slots.values():
        if (jobs / slot['job_name']).exists():
            raise ValueError('A declared job already exists; preserve it and use an explicit linked retry')
    logs = BATCH / 'launcher'
    logs.mkdir(exist_ok=True)
    state = {}
    lock = threading.Lock()

    def save(slot, **changes):
        with lock:
            row = state.setdefault(slot['trial_id'], {'job_name': slot['job_name']})
            row.update(changes)
            temp = BATCH / '.launches.tmp'
            temp.write_text(json.dumps(state, indent=2) + '\n')
            temp.replace(BATCH / 'launches.json')

    def run(slot):
        verify_runtime(task)
        command = ['harbor', 'run', '-p', str(task), '-a', slot['agent'],
                   '-m', slot['model_slug'], '--ak', 'reasoning_effort=high',
                   '--ak', f"version={slot['version']}", '--jobs-dir', str(jobs),
                   '--job-name', slot['job_name'], '--n-attempts', '1',
                   '--n-concurrent', '1', '--max-retries', '0']
        env = dict(os.environ)
        if slot['agent'] == 'claude-code':
            env['CLAUDE_CODE_OAUTH_TOKEN'] = token
            # Keep this switch out of --ae: Harbor would treat the literal 1 as
            # a secret and corrupt every occurrence during final log scrubbing.
            env['CLAUDE_FORCE_OAUTH'] = '1'
            env.pop('ANTHROPIC_API_KEY', None)
            command += ['--ae', 'CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}']
        else:
            env.pop('CLAUDE_CODE_OAUTH_TOKEN', None)
            env.pop('CLAUDE_FORCE_OAUTH', None)
            command += ['--ae', f'CODEX_AUTH_JSON_PATH={args.codex_auth_file.resolve()}']
        started = datetime.now(timezone.utc).isoformat()
        save(slot, status='running', started_at_utc=started, command=command)
        print(json.dumps({'trial_id': slot['trial_id'], 'event': 'started', 'time': started}), flush=True)
        with (logs / (slot['trial_id'] + '.log')).open('w') as output:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, bufsize=1,
                                       start_new_session=True)
            save(slot, process_id=process.pid)
            for line in process.stdout:
                output.write(line.replace(token, '[REDACTED]'))
                output.flush()
            code = process.wait()
        # Harbor finalizes its own redactions before exit. Never publish a job
        # while a known credential remains in any file, including session logs.
        needle = token.encode()
        matches = sum(needle in p.read_bytes() for p in (jobs / slot['job_name']).rglob('*') if p.is_file())
        finished = datetime.now(timezone.utc).isoformat()
        save(slot, status='process_finished', finished_at_utc=finished, exit_code=code,
             credential_matches=matches)
        print(json.dumps({'trial_id': slot['trial_id'], 'event': 'process_finished',
                          'exit_code': code, 'credential_matches': matches, 'time': finished}), flush=True)
        return slot['trial_id'], code, matches

    with concurrent.futures.ThreadPoolExecutor(max_workers=plan['max_concurrent']) as pool:
        futures = [pool.submit(run, slots[name]) for name in plan['execution_order']]
        results = [future.result() for future in futures]
    print(json.dumps({'event': 'batch_processes_finished', 'trials': len(results),
                      'credential_matches': sum(row[2] for row in results)}), flush=True)


if __name__ == '__main__':
    main()
