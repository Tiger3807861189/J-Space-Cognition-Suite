"""Regression checks for changing the controller goal while task state is recorded."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'j-space' / 'scripts' / 'control.py'
OLD = 'Parser skips blank lines'


class GoalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='j space 中文 ')
        self.root = Path(self.temp.name).resolve()
        self.write('evidence/a.txt', 'evidence A\n')
        self.write('evidence/b.txt', 'evidence B\n')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                                capture_output=True, text=True, encoding='utf-8', timeout=25)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def state(self):
        return json.loads((self.root / '.jspace/control.json').read_text(encoding='utf-8'))

    def archives(self):
        return sorted((self.root / '.jspace').glob('control-*.json'))

    def seed(self, goal='Fix the log parser'):
        self.cli('init', '--goal', goal, '--next', 'Read the parser', '--level', 'high')
        self.cli('note', '--check', OLD, '--by', 'Fixture over three lines', '--evidence', 'evidence/a.txt')
        self.cli('note', '--core', 'Parser output is stable', '--open', 'Does CRLF input parse?', '--settled-by', 'A CRLF fixture')

    def assert_unchanged(self, goal='Fix the log parser'):
        state = self.state()
        self.assertEqual((state['goal'], len(state['checkpoints']), self.archives()), (goal, 1, []))

    def test_changed_goal_with_recorded_state_requires_a_choice(self):
        self.seed()
        output = self.cli('note', '--goal', 'Fix the log parser and its CRLF handling', ok=False)
        self.assertIn('Same task reworded: add --inherit', output)
        self.assertIn('New task: add --new-task', output)
        self.assert_unchanged()

    def test_reworded_goal_keeps_state_with_inherit(self):
        self.seed()
        self.cli('note', '--goal', 'Fix the log parser and its CRLF handling', '--inherit')
        state = self.state()
        self.assertEqual([item['active'] for item in state['checkpoints']], [True])
        self.assertEqual((len(state['questions']), self.archives()), (1, []))

    def test_new_task_archives_and_clears(self):
        self.seed()
        output = self.cli('note', '--goal', 'Add a retry policy', '--next', 'Read the client', '--new-task')
        self.assertIn('Archived the previous task state (goal: Fix the log parser)', output)
        self.assertIn('1 open questions no longer gate shipment', output)
        self.assertIn('copy that file back to .jspace/control.json', output)
        state = self.state()
        self.assertEqual((state['goal'], state['next'], state['checkpoints'], state['questions'], state['core']),
                         ('Add a retry policy', 'Read the client', [], {}, []))
        [archive] = self.archives()
        previous = json.loads(archive.read_text(encoding='utf-8'))
        self.assertEqual((previous['goal'], [item['claim'] for item in previous['checkpoints']]),
                         ('Fix the log parser', [OLD]))
        self.assertNotIn(OLD, self.cli('read', '--agent', 'root'))

    def test_new_task_clears_stale_evidence_that_blocked_the_gate(self):
        self.seed()
        self.cli('read', '--agent', 'root')
        self.write('evidence/a.txt', 'changed later\n')
        self.assertIn('Active checkpoint evidence changed: 1', self.cli('check', '--stage', 'work', '--agent', 'root', ok=False))
        self.cli('note', '--goal', 'Add a retry policy', '--next', 'Read the client', '--new-task')
        self.cli('read', '--agent', 'root')
        self.assertIn('ALLOW work', self.cli('check', '--stage', 'work', '--agent', 'root'))

    def test_same_goal_modulo_whitespace_and_normalization_is_not_a_change(self):
        self.seed(goal='café parser')
        self.cli('note', '--goal', ' café parser ')
        self.assertEqual((len(self.state()['checkpoints']), self.archives()), (1, []))

    def test_goal_change_without_recorded_state_needs_no_flag(self):
        self.cli('init', '--goal', 'Fix the log parser', '--next', 'Read the parser', '--level', 'high')
        self.cli('note', '--goal', 'Add a retry policy')
        self.assertEqual((self.state()['goal'], self.archives()), ('Add a retry policy', []))

    def test_flag_rules(self):
        self.seed()
        self.assertIn('exclusive', self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task', '--inherit', ok=False))
        self.assertIn('--new-task requires --goal', self.cli('note', '--next', 'x', '--new-task', ok=False))
        self.assertIn('--inherit requires --goal', self.cli('note', '--next', 'x', '--inherit', ok=False))
        self.assertIn('A new goal needs --next', self.cli('note', '--goal', 'Add a retry policy', '--new-task', ok=False))
        self.assert_unchanged()

    def test_new_task_refuses_references_to_the_previous_task(self):
        self.seed()
        for extra in (['--supersede', '1'], ['--close', 'Q1']):
            output = self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task', '--check', 'c',
                              '--by', 'Fixture over one line', '--evidence', 'evidence/b.txt', *extra, ok=False)
            self.assertIn('point at the previous task', output)
            self.assert_unchanged()

    def test_rejected_new_task_leaves_no_archive(self):
        self.seed()
        self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task', '--check', 'c',
                 '--by', 'Fixture over one line', '--evidence', 'evidence/missing.txt', ok=False)
        self.assert_unchanged()

    def test_checkpoint_in_the_same_command_belongs_to_the_new_task(self):
        self.seed()
        self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task', '--check', 'Retry is bounded',
                 '--by', 'Fixture over one line', '--evidence', 'evidence/b.txt')
        self.assertEqual([(item['id'], item['claim'], item['active']) for item in self.state()['checkpoints']],
                         [(1, 'Retry is bounded', True)])

    def test_security_findings_survive_a_new_task(self):
        self.seed()
        self.write('evidence/repro.txt', 'repro\n')
        self.write('evidence/negative.txt', 'negative\n')
        self.cli('security', 'add', '--id', 'F1', '--claim', 'c', '--scope', 's', '--repro', 'evidence/repro.txt',
                 '--expected', 'e', '--observed', 'o', '--negative', 'evidence/negative.txt')
        self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task')
        self.assertEqual(list(self.state()['findings']), ['F1'])

    def test_archive_name_collision_gets_a_suffix(self):
        self.seed()
        now = time.time()
        for offset in range(6):
            self.write('.jspace/control-' + time.strftime('%Y%m%d-%H%M%S', time.localtime(now + offset)) + '.json', '{}')
        self.cli('note', '--goal', 'Add a retry policy', '--next', 'x', '--new-task')
        self.assertEqual(len([path for path in self.archives() if path.name.endswith('-2.json')]), 1)

    def test_repeated_init_names_both_paths(self):
        self.cli('init', '--goal', 'Fix the log parser', '--next', 'Read the parser', '--level', 'high')
        output = self.cli('init', '--goal', 'Add a retry policy', '--next', 'x', '--level', 'high', ok=False)
        self.assertIn('--new-task archives the previous state', output)
        self.assertIn('--inherit keeps it', output)


if __name__ == '__main__':
    unittest.main()
