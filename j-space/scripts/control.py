#!/usr/bin/env python3
"""J-Space SV1 cooperative host controller. Standard library; no command execution."""
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import unicodedata

SKILL = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.jspace', 'node_modules', '.venv', 'venv', '__pycache__',
            '.pytest_cache', '.mypy_cache', 'vendor', 'dist', 'build'}
EVENTS = ('tool', 'checkpoint', 'handoff', 'failure', 'resume', 'compact')


class ControlError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ControlError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


def linked(path):
    """Reject reparse points even on Python versions without Path.is_junction."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return (stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0)
            & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_path(root, value, exists=True):
    require(nonempty(str(value)), 'Path must not be empty.')
    candidate = Path(value)
    require(not candidate.is_absolute() and not candidate.drive and '..' not in candidate.parts,
            'Use a relative path inside the task directory; traversal is forbidden.')
    root = root.resolve()
    current = root
    for part in candidate.parts:
        current = current / part
        require(not linked(current),
                'Symbolic links and junctions are forbidden: ' + str(value))
    require(current.resolve().is_relative_to(root), 'Path escapes the task directory.')
    if exists:
        require(current.exists(), 'Missing path: ' + str(value))
    return current


def evidence(root, value):
    path = safe_path(root, value)
    require(path.is_file() and '.jspace' not in {part.casefold() for part in Path(value).parts},
            'Evidence must be a task file outside .jspace (case-insensitive reserved name).')
    before = path.stat()
    fingerprint = hashlib.sha256()
    meaningful = False
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            fingerprint.update(block)
            meaningful = meaningful or bool(block.strip())
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            'Evidence changed during reading; retry after its writer finishes.')
    require(meaningful, 'Evidence must not be empty.')
    return {'path': path.relative_to(root).as_posix(), 'sha256': fingerprint.hexdigest()}


def current_evidence(root, item, label=None):
    try:
        return isinstance(item, dict) and evidence(root, item['path']) == item
    except (ControlError, OSError) as exc:
        if label:
            raise ControlError(label + ': ' + str(exc)) from exc
        raise


def atomic(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.control-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def locked(root):
    directory = safe_path(root, '.jspace', exists=False)
    directory.mkdir(exist_ok=True)
    lockpath = safe_path(root, '.jspace/control.lock', exists=False)
    with lockpath.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + 15
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                require(time.monotonic() < deadline, 'State lock timeout; retry when the active writer finishes.')
                time.sleep(0.05)
        try:
            yield directory
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate(state):
    require(isinstance(state, dict) and state.get('schema') == 1, 'Unsupported or malformed state.')
    for key, kind in [('goal', str), ('next', str), ('level', str), ('modules', list),
                      ('agents', dict), ('findings', dict), ('config', dict), ('generation', int),
                      ('core', list), ('checkpoints', list), ('questions', dict), ('solo_reason', str)]:
        require(type(state.get(key)) is kind, 'Malformed state field: ' + key)
    require(state['level'] in ('low', 'medium', 'high', 'xhigh'), 'Malformed level.')
    require(all(nonempty(p) for p in state['modules']), 'Malformed module list.')
    def receipt(item):
        require(isinstance(item, dict) and nonempty(item.get('path')) and
                isinstance(item.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', item['sha256']), 'Malformed evidence receipt.')

    def timestamp(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    require(len(state['core']) <= 2 and all(nonempty(p) for p in state['core']), 'Malformed core.')
    require(isinstance(state.get('parked_core', []), list) and all(nonempty(p) for p in state.get('parked_core', [])), 'Malformed parked core.')
    for checkpoint in state['checkpoints']:
        require(isinstance(checkpoint, dict) and nonempty(checkpoint.get('claim')) and nonempty(checkpoint.get('by'))
                and isinstance(checkpoint.get('evidence'), dict) and type(checkpoint.get('id')) is int
                and checkpoint['id'] > 0 and type(checkpoint.get('active', True)) is bool, 'Malformed checkpoint.')
        receipt(checkpoint['evidence'])
    require(len({item['id'] for item in state['checkpoints']}) == len(state['checkpoints']), 'Duplicate checkpoint ID.')
    for question in state['questions'].values():
        require(isinstance(question, dict) and nonempty(question.get('question')) and nonempty(question.get('settled_by'))
                and type(question.get('closed')) is bool, 'Malformed question.')
        if question['closed']:
            require(type(question.get('checkpoint')) is int and
                    any(item.get('id') == question['checkpoint'] and item.get('active', True)
                        for item in state['checkpoints']),
                    'Closed question has no matching checkpoint.')
    for key in ('pulse_count', 'pulse_seconds', 'read_ttl', 'max_agents', 'max_depth', 'budget'):
        require(type(state['config'].get(key)) is int and state['config'][key] > 0, 'Malformed configuration: ' + key)
    require(type(state.get('spent')) is int and 0 <= state['spent'] <= state['config']['budget'], 'Malformed shared budget.')
    require('root' in state['agents'], 'Missing root agent.')
    for aid, agent in state['agents'].items():
        require(type(agent.get('active', True)) is bool, 'Malformed agent activity: ' + aid)
        if not agent.get('active', True):
            retirement = agent.get('retirement')
            require(aid != 'root' and isinstance(retirement, dict) and nonempty(retirement.get('reason'))
                    and retirement.get('handoff_to') in state['agents'] and timestamp(retirement.get('time')),
                    'Malformed agent retirement: ' + aid)
        require(isinstance(agent, dict) and isinstance(agent.get('reads'), dict) and
                isinstance(agent.get('owns'), list) and isinstance(agent.get('reports'), list) and
                type(agent.get('tools')) is int and agent['tools'] >= 0 and timestamp(agent.get('last_pulse')) and
                type(agent.get('depth')) is int and nonempty(agent.get('task')) and type(agent.get('broadcast')) is bool and
                bool(agent['owns']) and all(nonempty(path) for path in agent['owns']) and
                (agent.get('view') is None or nonempty(agent['view'])), 'Malformed agent: ' + aid)
        require((aid == 'root' and agent.get('parent') is None and agent['depth'] == 0) or
                (aid != 'root' and agent.get('parent') in state['agents'] and agent['depth'] > 0 and
                 agent['depth'] == state['agents'][agent['parent']]['depth'] + 1), 'Malformed agent parent/depth.')
        for reading in agent['reads'].values():
            require(isinstance(reading, dict) and timestamp(reading.get('time')) and
                    isinstance(reading.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', reading['sha256']), 'Malformed read receipt.')
        for report in agent['reports']:
            require(isinstance(report, dict) and report.get('round') in (1, 2) and
                    nonempty(report.get('summary')) and isinstance(report.get('evidence'), dict) and
                    nonempty(report.get('next')) and isinstance(report.get('sources'), list), 'Malformed report.')
            receipt(report['evidence'])
            for source in report['sources']:
                receipt(source)
            if report.get('completion') is not None:
                receipt(report['completion'])
            review = report.get('review')
            if review is not None:
                require(isinstance(review, dict) and review.get('verdict') in ('accepted', 'revise') and
                        review.get('agent') in state['agents'] and nonempty(review.get('report_sha256')), 'Malformed review.')
                receipt(review.get('evidence'))
    repo = state.get('repo')
    require(repo is None or (isinstance(repo, dict) and isinstance(repo.get('inventory'), dict) and
            isinstance(repo.get('map'), dict) and nonempty(repo.get('fingerprint')) and
            isinstance(repo.get('map_evidence'), dict)), 'Malformed repository state.')
    if repo is not None:
        require('branch' in repo and (repo['branch'] is None or repo['branch'] == 'linked-git-not-followed'
                or (isinstance(repo['branch'], str) and re.fullmatch(r'[0-9a-f]{64}', repo['branch']))),
                'Malformed repository branch marker.')
        facts = repo['map'].get('facts', [])
        require(isinstance(facts, list), 'Malformed map facts.')
        for fact in facts:
            require(isinstance(fact, dict) and nonempty(fact.get('claim')) and nonempty(fact.get('evidence')),
                    'Malformed map fact.')
            receipt(fact.get('receipt'))
    for finding in state['findings'].values():
        require(isinstance(finding, dict) and finding.get('status') in ('candidate', 'confirmed', 'rejected', 'fixed') and
                all(nonempty(finding.get(k)) for k in ('claim', 'scope', 'expected', 'observed')) and
                isinstance(finding.get('repro'), dict) and isinstance(finding.get('negative'), dict), 'Malformed security finding.')
        receipt(finding['repro'])
        receipt(finding['negative'])
        if finding['status'] != 'candidate':
            receipt(finding.get('resolution'))
            require(finding.get('disposition') in ('report', 'remediate') and isinstance(finding.get('history'), list),
                    'Malformed security resolution.')
            for assessment in finding['history']:
                require(isinstance(assessment, dict) and assessment.get('status') in ('confirmed', 'fixed', 'rejected'), 'Malformed assessment history.')
                receipt(assessment.get('evidence'))


def markdown(state):
    # A view only: never parse Markdown back into authoritative state.
    def quote(value):
        # Keep all task text inside a data block, including headings and newlines.
        return '\n'.join('> ' + line for line in str(value).splitlines()) or '>'

    lines = ['# J-Space shared control state', '', 'Generated from control.json; use the CLI to update.', '',
             '## Goal', quote(state['goal']), '', '## Next', quote(state['next']), '',
             'Level: ' + state['level'], 'Shared credits: %s / %s' % (state['spent'], state['config']['budget']), '',
             'Solo limitation:', quote(state['solo_reason']), '', '## Core', *map(quote, state['core']), '',
             '## Parked core', *map(quote, state.get('parked_core', [])), '', '## Verified checkpoints',
             json.dumps(state['checkpoints'], ensure_ascii=False, indent=2), '', '## Questions',
             json.dumps(state['questions'], ensure_ascii=False, indent=2), '', '## Agents']
    for aid, agent in state['agents'].items():
        lines += ['', '### Agent', quote(aid), 'Parent:', quote(agent['parent']), 'Task:', quote(agent['task']),
                  'Owns:', quote(', '.join(agent['owns'])), 'Active: ' + str(agent.get('active', True)),
                  'Retirement: ' + json.dumps(agent.get('retirement'), ensure_ascii=False)]
        for report in agent['reports']:
            lines += ['Round %s:' % report['round'], quote(report['summary']),
                      'Evidence: ' + json.dumps(report['evidence'], ensure_ascii=False), 'Next:', quote(report['next']),
                      'Sources: ' + json.dumps(report['sources'], ensure_ascii=False),
                      'Completion: ' + json.dumps(report.get('completion'), ensure_ascii=False),
                      'Review: ' + json.dumps(report.get('review'), ensure_ascii=False)]
    lines += ['', '## Repository map', json.dumps(state.get('repo', {}).get('map') if state.get('repo') else None,
                                                ensure_ascii=False, indent=2), '', '## Security findings']
    for fid, finding in state['findings'].items():
        lines += ['', '### Finding', quote(fid), json.dumps(finding, ensure_ascii=False, indent=2)]
    return ('\n'.join(lines) + '\n').encode('utf-8')


def save(root, state):
    validate(state)
    state['generation'] += 1
    # Commit canonical JSON first. A crash can leave a stale view, never divergent sources of truth.
    atomic(safe_path(root, '.jspace/control.json', False), encoded(state))
    atomic(safe_path(root, '.jspace/CONTROL.md', False), markdown(state))


def new_agent(parent, task, owns, depth):
    return {'parent': parent, 'task': task, 'owns': owns, 'depth': depth, 'reads': {},
            'reports': [], 'tools': 0, 'last_pulse': 0, 'view': None, 'broadcast': True}


def get_agent(state, aid):
    require(aid in state['agents'], 'Unknown agent: ' + aid)
    require(state['agents'][aid].get('active', True), 'Agent is retired: ' + aid)
    return state['agents'][aid]


def active_agents(state):
    return {aid: agent for aid, agent in state['agents'].items() if agent.get('active', True)}


def spend(state):
    require(state['spent'] < state['config']['budget'], 'Shared controller credit budget exhausted.')
    state['spent'] += 1


def skill_files(state):
    return list(dict.fromkeys(['SKILL.md'] + state['modules']))


def default_modules(level):
    if level == 'xhigh':
        return ['modules/capacity.md', 'modules/orchestration.md']
    if level == 'high':
        return ['modules/capacity.md', 'modules/broadcast.md']
    return ['modules/self-monitoring.md']


def contract_fingerprint(state):
    return digest(encoded({key: state[key] for key in ('goal', 'core', 'level', 'modules')}))


def read_files(state, aid, paths):
    agent = get_agent(state, aid)
    output = []
    for name in paths:
        path = safe_path(SKILL, name)
        require(path.is_file(), 'Skill read requires a file: ' + name)
        data = path.read_bytes()
        output += ['--- BEGIN ' + name + ' SHA256 ' + digest(data) + ' ---', data.decode('utf-8'),
                   '--- END ' + name + ' ---']
        agent['reads'][name] = {'sha256': digest(data), 'time': time.time()}
    required = skill_files(state)
    if (not agent['broadcast'] or set(required).issubset(paths)) and all(name in agent['reads'] and 0 <= time.time() - agent['reads'][name]['time'] <= state['config']['read_ttl']
           and agent['reads'][name]['sha256'] == digest(safe_path(SKILL, name).read_bytes()) for name in required):
        agent['broadcast'] = False
    return '\n'.join(output)


def check_reads(state, aid):
    agent = get_agent(state, aid)
    for name in skill_files(state):
        receipt = agent['reads'].get(name)
        require(receipt is not None, aid + ' must actually read ' + name)
        age = time.time() - receipt['time']
        require(0 <= age <= state['config']['read_ttl'], aid + ' has expired read: ' + name)
        require(digest(safe_path(SKILL, name).read_bytes()) == receipt['sha256'], 'Skill source changed: ' + name)
    require(not agent.get('broadcast'), aid + ' must pulse to receive the pending context broadcast.')


def inventory(root):
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if d.casefold() not in EXCLUDED and not linked(base / d))
        for name in sorted(files):
            path = base / name
            if linked(path):
                continue
            require(path.is_file(), 'Inventory encountered an unsupported filesystem entry.')
            before = path.stat()
            content_hash = file_digest(path)
            after = path.stat()
            require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                    'Repository changed during inventory; retry after writers finish.')
            result[path.relative_to(root).as_posix()] = content_hash
    return result


def branch(root):
    # Observe branch switches without executing git or following an external worktree pointer.
    git = root / '.git'
    if linked(git):
        return 'linked-git-not-followed'
    head = git / 'HEAD' if git.is_dir() else git
    if head.is_file() and not linked(head):
        return digest(head.read_bytes())
    return None


def check_repo(root, state):
    repo = state['repo']
    require(repo is not None, 'Repository map missing: run repo sync --map PATH, then repo view.')
    require(current_evidence(root, repo['map_evidence']), 'Semantic map source changed; sync it.')
    for index, fact in enumerate(repo['map'].get('facts', []), 1):
        label = 'Map fact ' + str(index) + ' (' + fact['evidence'] + ')'
        require(current_evidence(root, fact['receipt'], label), label + ' evidence changed; update the map and sync it.')
    require(repo['inventory'] == inventory(root) and repo['branch'] == branch(root),
            'Repository changed; update the semantic map and run repo sync.')
    return repo


def map_input(root, filename):
    item = evidence(root, filename)
    value = json.loads(safe_path(root, filename).read_text(encoding='utf-8-sig'))
    require(isinstance(value, dict) and nonempty(value.get('summary')) and isinstance(value.get('areas'), list)
            and bool(value['areas']), 'Map needs summary and a nonempty areas array.')
    for area in value['areas']:
        require(isinstance(area, dict) and nonempty(area.get('path')) and nonempty(area.get('purpose')),
                'Each map area needs path and purpose.')
        safe_path(root, area['path'])
    require(isinstance(value.get('facts', []), list), 'Map facts must be an array.')
    for item_data in value.get('facts', []):
        require(isinstance(item_data, dict) and nonempty(item_data.get('claim')) and
                nonempty(item_data.get('evidence')), 'Map facts need claim and evidence path.')
        item_data['receipt'] = evidence(root, item_data['evidence'])
    return value, item


def repo_enabled(state):
    return state['repo'] is not None or any(name in state['modules'] for name in ('modules/repository.md', 'modules/cyber.md'))


def shared_context(state):
    pending = [aid for aid, a in active_agents(state).items() if a['broadcast']]
    questions = [qid + ': ' + q['question'] for qid, q in state['questions'].items() if not q['closed']]
    reports = [aid + ': ' + a['reports'][-1]['summary'] for aid, a in state['agents'].items() if a['reports']]
    verified = [str(item['id']) + ': ' + item['claim'] + ' [evidence: ' + item['evidence']['path'] + ']'
                for item in state['checkpoints'] if item.get('active', True)]
    return ('Goal: ' + state['goal'] + '\nNext: ' + state['next'] + '\nCore: ' + '; '.join(state['core']) +
            '\nVerified (latest active): ' + '; '.join(verified[-3:]) +
            '\nOpen: ' + '; '.join(questions) + '\nLatest reports: ' + '; '.join(reports) +
            '\nActive agents: ' + ', '.join(active_agents(state)) +
            '\nRetirements: ' + json.dumps({aid: a['retirement'] for aid, a in state['agents'].items()
                                           if not a.get('active', True)}, ensure_ascii=False) +
            '\nPending source broadcasts: ' + ', '.join(pending))


def broadcast_children(state):
    for aid, child in active_agents(state).items():
        if aid != 'root':
            child['broadcast'] = True


def gate(root, state, aid, stage):
    require(nonempty(state['goal']) and nonempty(state['next']), 'Goal and next action are required.')
    check_reads(state, aid)
    agent = get_agent(state, aid)
    if repo_enabled(state):
        repo = check_repo(root, state)
        require(agent.get('view') == repo['fingerprint'], aid + ' must run repo view before work.')
    for checkpoint in state['checkpoints']:
        if checkpoint.get('active', True):
            require(current_evidence(root, checkpoint['evidence'], 'Active checkpoint ' + str(checkpoint['id'])),
                    'Active checkpoint evidence changed: ' + str(checkpoint['id']) +
                    '. Reopen a dependent question or record a new checkpoint with --supersede ID.')
    for qid, question in state['questions'].items():
        if question['closed']:
            checkpoint = next(item for item in state['checkpoints'] if item['id'] == question['checkpoint'])
            require(current_evidence(root, checkpoint['evidence']),
                    'Closed question evidence changed: ' + qid + '. Use note --reopen ' + qid + ' and reverify.')
    if stage == 'ship':
        require(not any(not question['closed'] for question in state['questions'].values()), 'Open questions require evidence-backed closure.')
        require(state['level'] != 'xhigh' or len(active_agents(state)) > 1 or nonempty(state['solo_reason']),
                'xhigh needs participating agents or an explicit --solo-reason describing unavailable host delegation.')
        for member, details in active_agents(state).items():
            check_reads(state, member)
            if repo_enabled(state):
                require(details.get('view') == repo['fingerprint'], member + ' must run repo view before shipment.')
            require(details['reports'], member + ' has no delivery report.')
            report = details['reports'][-1]
            if member != 'root':
                require(report.get('contract_sha256') == contract_fingerprint(state),
                        member + ' task contract changed; begin a fresh two-round report cycle and review.')
            require(current_evidence(root, report['evidence']), member + ' report evidence changed.')
            for source in report['sources']:
                require(current_evidence(root, source), member + ' report source changed: ' + source['path'])
            if repo_enabled(state):
                require(bool(report['sources']), member + ' needs explicit --source dependencies.')
            if member == 'root':
                require(report.get('completion') and current_evidence(root, report['completion']),
                        'Root needs current --completion evidence checking the goal and deliverable.')
                require(report.get('goal') == state['goal'], 'Goal changed after root completion; submit a fresh root report.')
                require(report.get('contract_sha256') == contract_fingerprint(state),
                        'Task contract or route changed after root completion; submit a fresh root report.')
                require(all(report.get('time', 0) >= a.get('retirement', {}).get('time', 0)
                            for a in state['agents'].values()),
                        'Agent retirement changed integration scope; submit a fresh root completion report.')
                continue
            if state['level'] in ('high', 'xhigh'):
                require(report['round'] == 2, member + ' requires a second-thinking report.')
            review = report.get('review')
            require(review and review['verdict'] == 'accepted', member + ' latest report is not independently accepted.')
            require(review['agent'] in state['agents'] and review['agent'] != member and
                    review['report_sha256'] == digest(encoded({k: v for k, v in report.items() if k != 'review'})),
                    member + ' review is not bound to the current report.')
            require(current_evidence(root, review['evidence']), member + ' review evidence changed.')
        for fid, finding in state['findings'].items():
            require(finding['status'] in ('rejected', 'fixed') or
                    (finding['status'] == 'confirmed' and finding.get('disposition') == 'report'),
                    'Unresolved security finding: ' + fid)
            for key in ('repro', 'negative', 'resolution'):
                require(current_evidence(root, finding[key]), 'Stale security evidence: ' + fid + '/' + key)
            if finding['status'] == 'fixed':
                confirmations = [item['evidence'] for item in finding.get('history', []) if item['status'] == 'confirmed']
                confirmation = finding.get('confirmation', confirmations[-1] if confirmations else None)
                require(confirmation is not None and current_evidence(root, confirmation), 'Stale confirmed assessment supporting fix: ' + fid)
    return 'ALLOW ' + stage + ': goals, reads, map and required evidence are current.'


def run(root, state, args):
    command = args.command
    if command == 'tune':
        require(nonempty(args.reason), 'Refresh tuning requires observed grounds in --reason.')
        updates = {key: getattr(args, key) for key in ('pulse_count', 'pulse_seconds', 'read_ttl')
                   if getattr(args, key) is not None}
        require(bool(updates) and all(value > 0 for value in updates.values()), 'Supply positive refresh intervals.')
        state.setdefault('tuning', []).append({'reason': args.reason, 'time': time.time(),
            'previous': {key: state['config'][key] for key in updates}, 'updated': updates})
        state['config'].update(updates)
        for agent in state['agents'].values():
            agent['broadcast'] = True
        return 'Refresh schedule updated; consume a full read or pulse before further work.'
    if command == 'route':
        require(nonempty(args.reason), 'A routing change requires a reason.')
        level = ('medium' if args.level == 'media' else args.level) or state['level']
        levels = ('low', 'medium', 'high', 'xhigh')
        require(levels.index(level) >= levels.index(state['level']),
                'Do not lower an active task level to bypass its outstanding obligations.')
        modules = list(dict.fromkeys(default_modules(level) + args.module))
        for name in modules:
            require(safe_path(SKILL, name).is_file() and name.endswith('.md'),
                    'Active sources must be existing skill Markdown files.')
        state.setdefault('routes', []).append({'level': level, 'modules': modules,
                                               'reason': args.reason, 'time': time.time()})
        state['level'], state['modules'] = level, modules
        for agent in state['agents'].values():
            agent['broadcast'] = True
        return 'Route updated. Every agent must read the current entry and active sources before work.'
    if command == 'note':
        previous_contract = (state['goal'], list(state['core']))
        require(any(getattr(args, key) is not None for key in ('goal', 'next', 'solo_reason', 'core', 'check', 'open', 'close', 'reopen')),
                'Set goal, next, core, checkpoint, question, or solo reason.')
        require(args.goal is not None or not args.inherit, '--inherit requires --goal.')
        prior_goal, prior_snapshot = state['goal'], encoded(state)
        for key in ('goal', 'next', 'solo_reason'):
            value = getattr(args, key)
            if value is not None:
                require(nonempty(value), key + ' cannot be empty.')
                state[key] = value
        # A new goal can be a task boundary. Core, checkpoints and questions recorded for
        # the previous task are not facts of the next one; left active they read as current
        # verification, and when their evidence changes they block every gate. A changed
        # goal string cannot tell a new task from the same task reworded, so the caller
        # chooses: --new-task archives the previous state verbatim and starts clean,
        # --inherit keeps it. With state to carry and neither flag, a changed goal is
        # refused. Security findings stay: they describe the repository, not the goal.
        archived = None
        carried = {'checkpoints': len(state['checkpoints']), 'questions': len(state['questions']),
                   'core': len(state['core']) + len(state.get('parked_core', []))}
        same = lambda a, b: unicodedata.normalize('NFC', a).strip() == unicodedata.normalize('NFC', b).strip()
        require(not (args.new_task and args.inherit), '--new-task and --inherit are exclusive.')
        require(args.goal is not None or not args.new_task, '--new-task requires --goal.')
        if args.goal is not None and not same(args.goal, prior_goal) and not args.inherit and any(carried.values()):
            require(args.new_task,
                    'The goal changed while ' + ', '.join(str(v) + ' ' + k for k, v in carried.items() if v) +
                    ' are recorded. Same task reworded: add --inherit to keep them. New task: add --new-task '
                    '(with --next) to archive them and start clean.')
            require(args.supersede is None and args.close is None and args.reopen is None,
                    '--supersede, --close and --reopen point at the previous task, which a new --goal archives '
                    'and clears; run them without --goal first, or pass --inherit.')
            require(args.next is not None, 'A new goal needs --next: the current next action belongs to the previous task.')
            open_q = sum(1 for q in state['questions'].values() if not q['closed'])
            stamp = time.strftime('%Y%m%d-%H%M%S')
            name, n = '.jspace/control-' + stamp + '.json', 1
            while safe_path(root, name, False).exists():
                n += 1
                name = '.jspace/control-' + stamp + '-' + str(n) + '.json'
            archived = (name, carried, open_q)
            state['core'], state['checkpoints'], state['questions'] = [], [], {}
            state.pop('parked_core', None)
        if args.core is not None:
            require(nonempty(args.core), 'Core entry cannot be empty.')
            active = [item for item in state['core'] if item != args.core] + [args.core]
            parked = state.setdefault('parked_core', [])
            for item in active[:-2]:
                if item not in parked:
                    parked.append(item)
            state['core'] = active[-2:]
            state['parked_core'] = [item for item in parked if item not in state['core']]
        checkpoint = None
        if args.check is not None:
            require(nonempty(args.check) and nonempty(args.by) and nonempty(args.evidence),
                    'Checkpoint requires --check, --by (method and coverage), and --evidence.')
            checkpoint = {'id': len(state['checkpoints']) + 1, 'claim': args.check, 'by': args.by,
                          'evidence': evidence(root, args.evidence), 'active': True}
            state['checkpoints'].append(checkpoint)
        else:
            require(args.by is None and args.evidence is None, '--by and --evidence require --check.')
        if args.supersede is not None:
            require(checkpoint is not None, '--supersede requires a new checkpoint and evidence in the same command.')
            older = next((item for item in state['checkpoints'] if item['id'] == args.supersede
                          and item['id'] != checkpoint['id']), None)
            require(older is not None and older.get('active', True), 'Superseded checkpoint is missing or already inactive.')
            require(not any(q['closed'] and q['checkpoint'] == args.supersede for q in state['questions'].values()),
                    'Reopen dependent questions before superseding their checkpoint.')
            older.update(active=False, superseded_by=checkpoint['id'])
        if args.open is not None:
            require(nonempty(args.open) and nonempty(args.settled_by), 'Open question requires --open and --settled-by.')
            qid = 'Q' + str(len(state['questions']) + 1)
            state['questions'][qid] = {'question': args.open, 'settled_by': args.settled_by, 'closed': False}
        else:
            require(args.settled_by is None, '--settled-by requires --open.')
        if args.reopen is not None:
            require(args.close is None, 'Reopen and reverify in separate commands.')
            require(args.reopen in state['questions'] and state['questions'][args.reopen]['closed'], 'Question is unknown or already open.')
            question = state['questions'][args.reopen]
            question.setdefault('closure_history', []).append(question['checkpoint'])
            previous_id = question['checkpoint']
            question['closed'] = False
            del question['checkpoint']
            if not any(q['closed'] and q['checkpoint'] == previous_id for q in state['questions'].values()):
                previous = next(item for item in state['checkpoints'] if item['id'] == previous_id)
                previous.update(active=False, retired_by='Reopened question ' + args.reopen)
        if args.close is not None:
            require(checkpoint is not None, 'Closing a question requires a checkpoint with evidence in the same command.')
            require(args.close in state['questions'] and not state['questions'][args.close]['closed'], 'Question is unknown or already closed.')
            state['questions'][args.close].update(closed=True, checkpoint=checkpoint['id'])
        if previous_contract != (state['goal'], state['core']):
            broadcast_children(state)
        if archived is not None:
            atomic(safe_path(root, archived[0], False), prior_snapshot)
            left = ', '.join(str(v) + ' ' + k for k, v in archived[1].items() if v)
            gated = (' (' + str(archived[2]) + ' open questions no longer gate shipment)') if archived[2] else ''
            return ('Archived the previous task state (goal: ' + prior_goal + ') to ' + archived[0] + ' — ' + left +
                    ' left behind' + gated + '. To undo, copy that file back to .jspace/control.json.\n' +
                    shared_context(state))
        return shared_context(state)
    if command == 'read':
        sources = read_files(state, args.agent, args.paths or skill_files(state))
        return shared_context(state) + '\n' + sources
    if command == 'pulse':
        agent = get_agent(state, args.agent)
        if args.event == 'tool':
            agent['tools'] += 1
        now = time.time()
        stale = False
        try:
            check_reads(state, args.agent)
        except ControlError:
            stale = True
        due = (args.event != 'tool' or agent['broadcast'] or agent['tools'] >= state['config']['pulse_count']
               or now - agent['last_pulse'] >= state['config']['pulse_seconds'] or stale)
        if not due:
            return shared_context(state) + '\nPulse recorded; next source injection is not due.'
        if args.agent == 'root' and args.event in ('handoff', 'failure', 'resume', 'compact'):
            broadcast_children(state)
        agent['tools'] = 0
        agent['last_pulse'] = now
        agent['broadcast'] = False
        return (shared_context(state) + '\nEvery agent must consume its own pending broadcast via pulse.\n' +
                read_files(state, args.agent, skill_files(state)))
    if command == 'check':
        return gate(root, state, args.agent, args.stage)
    if command == 'repo':
        if args.repo_command == 'sync':
            semantic, receipt = map_input(root, args.map)
            files = inventory(root)
            current_branch = branch(root)
            fingerprint = digest(encoded({'inventory': files, 'map': semantic, 'branch': current_branch}))
            if state['repo'] is None or state['repo']['fingerprint'] != fingerprint:
                broadcast_children(state)
            state['repo'] = {'inventory': files, 'map': semantic, 'map_evidence': receipt,
                             'branch': current_branch, 'fingerprint': fingerprint}
            return 'Repository and semantic map synchronized: ' + fingerprint
        repo = check_repo(root, state)
        if args.repo_command == 'view':
            get_agent(state, args.agent)['view'] = repo['fingerprint']
            return json.dumps(repo, ensure_ascii=False, indent=2)
        return 'Repository fingerprint and semantic map are current.'
    if command == 'agent':
        if args.agent_command == 'retire':
            require(args.id != 'root', 'Root cannot retire.')
            agent = get_agent(state, args.id)
            require(nonempty(args.reason), 'Retirement requires a reason.')
            successor = args.handoff_to or agent['parent']
            get_agent(state, successor)
            require(successor != args.id, 'Retirement must hand off to another active agent.')
            require(not any(a['parent'] == args.id for a in active_agents(state).values()),
                    'Retire or complete and retire active children first.')
            agent.update(active=False, broadcast=False, retirement={
                'reason': args.reason, 'handoff_to': successor, 'time': time.time(),
                'owns': list(agent['owns']), 'task': agent['task']})
            # Preserve provenance and budget usage; the host must stop the actual process.
            state['agents'][successor]['broadcast'] = True
            state['agents']['root']['broadcast'] = True
            return 'Agent retired; host must stop its process and transfer unfinished scope to ' + successor + ': ' + args.id
        require(re.fullmatch(r'[A-Za-z0-9_-]+', args.id) and args.id not in state['agents'], 'Agent ID is invalid or already used.')
        parent = get_agent(state, args.parent)
        require(nonempty(args.task), 'Agent task is required.')
        require(len(state['agents']) < state['config']['max_agents'], 'Agent limit reached.')
        require(parent['depth'] < state['config']['max_depth'], 'Recursion depth limit reached.')
        for ownership in args.owns:
            safe_path(root, ownership, exists=False)
        spend(state)
        state['agents'][args.id] = new_agent(args.parent, args.task, args.owns, parent['depth'] + 1)
        return 'Agent registered; the host must launch it and deliver its own pulse output: ' + args.id
    if command == 'report':
        agent = get_agent(state, args.agent)
        check_reads(state, args.agent)
        require(nonempty(args.summary) and nonempty(args.next), 'Report summary and next action are required.')
        require(args.round == 1 or (agent['reports'] and agent['reports'][-1]['round'] == 1),
                'Round 2 must immediately follow this same agent\'s round 1.')
        receipt = evidence(root, args.evidence)
        sources = [evidence(root, name) for name in args.source]
        require(not repo_enabled(state) or sources, 'Repository reports require at least one --source dependency.')
        completion = evidence(root, args.completion) if args.completion else None
        require(completion is None or completion != receipt, 'Completion checklist must be distinct from report evidence.')
        require(all(source != receipt and source != completion for source in sources), 'Source dependencies must be distinct from report and completion artifacts.')
        if args.round == 2:
            require(agent['reports'][-1].get('contract_sha256') == contract_fingerprint(state),
                    'Task contract changed since round 1; begin a fresh report cycle.')
            previous = agent['reports'][-1]['evidence']
            require(receipt['path'] != previous['path'], 'Round 2 needs a new evidence path; preserve round 1.')
            require(current_evidence(root, previous), 'Round 1 evidence changed; restore it or begin a fresh report cycle.')
        spend(state)
        agent['reports'].append({'round': args.round, 'summary': args.summary, 'next': args.next,
                                 'evidence': receipt, 'sources': sources, 'completion': completion,
                                 'goal': state['goal'], 'contract_sha256': contract_fingerprint(state),
                                 'time': time.time(), 'review': None})
        return 'Report persisted to the shared state; its review is pending.'
    if command == 'review':
        require(args.agent != args.target, 'Self-review is forbidden.')
        get_agent(state, args.agent)
        check_reads(state, args.agent)
        reports = get_agent(state, args.target)['reports']
        require(bool(reports), 'Target has no report.')
        report = reports[-1]
        require(report.get('contract_sha256') == contract_fingerprint(state),
                'Target task contract changed; submit a fresh report cycle.')
        require(current_evidence(root, report['evidence']), 'Target report evidence changed; submit a fresh report.')
        require(all(current_evidence(root, source) for source in report['sources']), 'Target source dependencies changed; submit a fresh report.')
        receipt = evidence(root, args.evidence)
        require(receipt != report['evidence'], 'Review needs independent evidence, not the target artifact.')
        spend(state)
        report['review'] = {'agent': args.agent, 'verdict': args.verdict, 'evidence': receipt,
                            'report_sha256': digest(encoded({k: v for k, v in report.items() if k != 'review'}))}
        return 'Independent review attached to the latest report.'
    if command == 'security':
        if args.security_command == 'add':
            require(args.id not in state['findings'] and nonempty(args.id), 'Finding ID is empty or already used.')
            fields = {k: getattr(args, k) for k in ('claim', 'scope', 'expected', 'observed')}
            require(all(nonempty(v) for v in fields.values()), 'Finding claim, scope, expected and observed are required.')
            fields.update(repro=evidence(root, args.repro), negative=evidence(root, args.negative), status='candidate')
            require(fields['repro'] != fields['negative'], 'Negative control must be a separate evidence artifact.')
            state['findings'][args.id] = fields
            return 'Candidate recorded; no vulnerability is confirmed yet.'
        require(args.id in state['findings'], 'Unknown finding.')
        finding = state['findings'][args.id]
        require(current_evidence(root, finding['repro']) and current_evidence(root, finding['negative']),
                'Reproduction or negative-control evidence changed; restore the recorded artifacts.')
        receipt = evidence(root, args.evidence)
        require(receipt not in (finding['repro'], finding['negative']), 'Resolution needs a separate assessment or fix-verification artifact.')
        if args.status == 'fixed':
            confirmations = [item['evidence'] for item in finding.get('history', []) if item['status'] == 'confirmed']
            require(bool(confirmations), 'A fix requires a prior confirmed assessment.')
            require(current_evidence(root, confirmations[-1]), 'Confirmed assessment changed; submit a fresh confirmation before fixing.')
            finding['confirmation'] = confirmations[-1]
            require(all(receipt != item['evidence'] for item in finding.get('history', [])), 'Fix verification must be distinct from earlier assessments.')
        finding['status'] = args.status
        finding['disposition'] = args.disposition
        finding['resolution'] = receipt
        finding.setdefault('history', []).append({'status': args.status, 'evidence': receipt})
        return 'Finding assessment recorded: ' + args.status
    if command == 'status':
        result = json.dumps(state, ensure_ascii=False, indent=2)
        if len(active_agents(state)) == 1:
            result += '\nOnly root is registered. This controller cannot launch agents; the host must provide delegation. xhigh shipping needs a recorded solo reason if the host cannot delegate.'
        return result
    raise ControlError('Unknown command.')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.', help='Task directory (defaults to cwd).')
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name in ('goal', 'next'):
        init.add_argument('--' + name, required=True)
    init.add_argument('--level', choices=('low', 'medium', 'media', 'high', 'xhigh'), required=True)
    init.add_argument('--module', action='append', default=[])
    init.add_argument('--solo-reason', default='')
    for name, default in [('pulse-count', 5), ('pulse-seconds', 600), ('read-ttl', 1800),
                          ('max-agents', 8), ('max-depth', 2), ('budget', 100)]:
        init.add_argument('--' + name, type=int, default=default)
    note = sub.add_parser('note')
    for name in ('goal', 'next', 'solo-reason', 'core', 'check', 'by', 'evidence', 'open', 'settled-by', 'close', 'reopen'):
        note.add_argument('--' + name)
    note.add_argument('--supersede', type=int)
    note.add_argument('--inherit', action='store_true',
                      help='with --goal: same task reworded; keep the recorded core, checkpoints and questions')
    note.add_argument('--new-task', action='store_true',
                      help='with --goal: a new task; archive the recorded core, checkpoints and questions and start clean')
    route = sub.add_parser('route')
    route.add_argument('--level', choices=('low', 'medium', 'media', 'high', 'xhigh'))
    route.add_argument('--module', action='append', default=[])
    route.add_argument('--reason', required=True)
    tune = sub.add_parser('tune')
    for name in ('pulse-count', 'pulse-seconds', 'read-ttl'):
        tune.add_argument('--' + name, type=int)
    tune.add_argument('--reason', required=True)
    read = sub.add_parser('read')
    read.add_argument('paths', nargs='*')
    read.add_argument('--agent', default='root')
    pulse = sub.add_parser('pulse')
    pulse.add_argument('--event', choices=EVENTS, required=True)
    pulse.add_argument('--agent', default='root')
    check = sub.add_parser('check')
    check.add_argument('--stage', choices=('work', 'ship'), required=True)
    check.add_argument('--agent', default='root')
    repo = sub.add_parser('repo').add_subparsers(dest='repo_command', required=True)
    repo.add_parser('sync').add_argument('--map', required=True)
    repo.add_parser('view').add_argument('--agent', default='root')
    repo.add_parser('check')
    agents = sub.add_parser('agent').add_subparsers(dest='agent_command', required=True)
    add = agents.add_parser('add')
    for name in ('id', 'parent', 'task'):
        add.add_argument('--' + name, required=True)
    add.add_argument('--owns', action='append', required=True)
    retire = agents.add_parser('retire')
    retire.add_argument('--id', required=True)
    retire.add_argument('--reason', required=True)
    retire.add_argument('--handoff-to', help='Active successor; defaults to the registered parent.')
    report = sub.add_parser('report')
    for name in ('agent', 'summary', 'evidence', 'next'):
        report.add_argument('--' + name, required=True)
    report.add_argument('--round', type=int, choices=(1, 2), required=True)
    report.add_argument('--source', action='append', default=[])
    report.add_argument('--completion')
    review = sub.add_parser('review')
    for name in ('agent', 'target', 'evidence'):
        review.add_argument('--' + name, required=True)
    review.add_argument('--verdict', choices=('accepted', 'revise'), required=True)
    sec = sub.add_parser('security').add_subparsers(dest='security_command', required=True)
    finding = sec.add_parser('add')
    for name in ('id', 'claim', 'scope', 'repro', 'expected', 'observed', 'negative'):
        finding.add_argument('--' + name, required=True)
    resolve = sec.add_parser('resolve')
    for name in ('id', 'evidence'):
        resolve.add_argument('--' + name, required=True)
    resolve.add_argument('--status', choices=('confirmed', 'rejected', 'fixed'), required=True)
    resolve.add_argument('--disposition', choices=('report', 'remediate'), default='remediate')
    sub.add_parser('status')
    return p


def load_state(path):
    require(path.is_file(), 'Controller is not initialized. Run init first.')
    snapshot = path.read_bytes()
    try:
        state = json.loads(snapshot.decode('utf-8'))
        validate(state)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ControlError('Malformed canonical state: ' + str(exc)) from exc
    return state, snapshot


def repair_view(root, state):
    """Repair a missing/stale projection without advancing canonical generation."""
    path = safe_path(root, '.jspace/CONTROL.md', False)
    expected = markdown(state)
    if not path.is_file() or path.read_bytes() != expected:
        atomic(path, expected)


def main(argv=None):
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        require(root.is_dir(), 'Task root must be an existing directory.')
        readonly = args.command in ('status', 'check') or (args.command == 'repo' and args.repo_command == 'check')
        if readonly:
            # Hash task files without holding the writer lock. Never issue ALLOW against
            # a state snapshot changed by a concurrent controller operation.
            with locked(root):
                state_path = safe_path(root, '.jspace/control.json', False)
                state, snapshot = load_state(state_path)
            output = run(root, state, args)
            with locked(root):
                require(safe_path(root, '.jspace/control.json').read_bytes() == snapshot,
                        'Control state changed during inspection; retry the read-only command.')
                repair_view(root, state)
            print(output, flush=True)
            return 0
        with locked(root):
            state_path = safe_path(root, '.jspace/control.json', False)
            if args.command == 'init':
                require(not state_path.exists(), 'Controller already initialized; use note to update goal or next '
                        '(a new task: note --goal ... --next ... --new-task archives the previous state; '
                        'the same task: --inherit keeps it).')
                level = 'medium' if args.level == 'media' else args.level
                modules = list(dict.fromkeys(default_modules(level) + args.module))
                for name in modules:
                    require(safe_path(SKILL, name).is_file() and name.endswith('.md'),
                            'Active sources must be existing skill Markdown files.')
                require(nonempty(args.goal) and nonempty(args.next), 'Goal and next action must not be empty.')
                config = {key: getattr(args, key) for key in ('pulse_count', 'pulse_seconds', 'read_ttl', 'max_agents', 'max_depth', 'budget')}
                state = {'schema': 1, 'generation': 0, 'goal': args.goal, 'next': args.next, 'level': level,
                         'modules': modules, 'config': config, 'spent': 0, 'repo': None, 'findings': {},
                         'core': [], 'checkpoints': [], 'questions': {}, 'solo_reason': args.solo_reason,
                         'agents': {'root': new_agent(None, args.goal, ['.'], 0)}}
                validate(state)
                output = 'Initialized. Run pulse --event resume before work.'
                if repo_enabled(state):
                    output += ' Repository work also requires repo sync --map PATH and repo view.'
            else:
                state, _ = load_state(state_path)
                output = run(root, state, args)
            save(root, state)
            print(output, flush=True)
        return 0
    except (ControlError, OSError, ValueError) as exc:
        print('BLOCK: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', newline='')
        sys.stderr.reconfigure(encoding='utf-8', newline='')
    sys.exit(main())
