#!/usr/bin/env python3
"""Offline regression tests; synthetic media and isolated state under /tmp/opencode."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/f'{name}.py')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise unittest.SkipTest('FFmpeg/FFprobe required')
        temp_root = Path('/tmp/opencode')
        cls.tmp = tempfile.TemporaryDirectory(prefix='dopamine-tests-', dir=temp_root if temp_root.is_dir() else None)
        cls.root = Path(cls.tmp.name)
        cls.good = cls.root/'good.mp4'
        cls.silent = cls.root/'silent.mp4'
        cls.black = cls.root/'black.mp4'
        for path, visual, audio, af in (
            (cls.good, 'testsrc2=size=160x288:rate=30', 'sine=frequency=440:sample_rate=48000', 'loudnorm=I=-14:TP=-1:LRA=7'),
            (cls.silent, 'testsrc2=size=160x288:rate=30', 'anullsrc=r=48000:cl=stereo', 'anull'),
            (cls.black, 'color=black:size=160x288:rate=30', 'sine=frequency=440:sample_rate=48000', 'loudnorm=I=-14:TP=-1:LRA=7'),
        ):
            subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', visual,
                            '-f', 'lavfi', '-i', audio, '-t', '2', '-af', af, '-ar', '48000',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-movflags', '+faststart', str(path)], check=True)
        cls.verify_module = module('verify_render')
        # A controlled CLI stand-in exercises orchestration without network/Chrome.
        cls.bin = cls.root/'bin'
        cls.bin.mkdir()
        fake = cls.bin/'npx'
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
a=sys.argv[1:]
if os.environ.get('HYPERFRAMES_NO_OPTIONAL_INSTALL') != '1': raise SystemExit('optional dependency installs not disabled')
with open(os.environ['TEST_COMMAND_LOG'], 'a') as f: f.write(json.dumps(a)+'\\n')
if '--version' in a: print('0.9.99'); sys.exit(0)
if 'doctor' in a: print(json.dumps({'ok': True, 'checks': []})); sys.exit(0)
if 'timeline' in a: print(os.environ.get('TEST_TIMELINE_JSON', '{"timeline":{"tracks":[]}}')); sys.exit(0)
if 'check' in a:
 print(os.environ.get('TEST_CHECK_JSON', json.dumps({'ok':True,'browserSkipped':False,
  'lint':{'ok':True},'runtime':{'ok':True},'audio':{'ok':True},
  'layout':{'ok':True,'samples':[0.5]},'contrast':{'ok':True,'enabled':True,'samples':[0.5]}}))); sys.exit(0)
if 'snapshot' in a:
 p=pathlib.Path(a[a.index('--output')+1]); p.mkdir(parents=True,exist_ok=True)
 if not os.environ.get('TEST_NO_SNAPSHOT'):
  for i in range(9): (p/f'proof-{i}.png').write_bytes(b'test fixture')
 sys.exit(0)
if 'render' in a: shutil.copyfile(os.environ['TEST_RENDER_VIDEO'], a[a.index('-o')+1]); sys.exit(0)
if 'transcribe' in a:
 if os.environ.get('TEST_WHISPER_FAIL') and a[a.index('--engine')+1]=='whisper': sys.exit(3)
 print('{"ok":true}'); sys.exit(0)
raise SystemExit('unexpected test CLI command: '+repr(a))
''')
        fake.chmod(0o755)
        whisper = cls.bin/'whisper-cli'
        whisper.write_text('#!/usr/bin/env bash\nexit 0\n')
        whisper.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix='case-', dir=self.root))
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
                        TEST_COMMAND_LOG=str(self.case/'commands.jsonl'), TEST_RENDER_VIDEO=str(self.good),
                        DOPAMINE_STATE_DIR=str(self.case/'state'), DOPAMINE_CACHE_DIR=str(self.case/'cache'),
                        DOPAMINE_BRAND_DIR=str(self.case/'branddir'),
                        DOPAMINE_SKIP_PREVIEW='1',
                        PYTHONDONTWRITEBYTECODE='1')
        self.expected = {'duration': 2, 'width': 160, 'height': 288, 'fps': 30, 'expect_audio': True,
                         'expect_music': False, 'music_exception': 'Synthetic regression fixture without music.',
                         'expect_brand': False,
                         'target_lufs': -14, 'lufs_tolerance': 2, 'max_true_peak_dbtp': -1}

    def run_script(self, script, *args, env=None):
        launcher = 'bash' if script.endswith('.sh') else sys.executable
        return subprocess.run([launcher, str(SCRIPTS/script), *map(str, args)], env=env or self.env,
                              capture_output=True, text=True, timeout=120)

    def verify(self, video, expected=None):
        return self.verify_module.verify(video, expected or self.expected,
                                         self.case/'qa.json', self.case/'proof')

    def project(self):
        out = self.case/'output'
        (out/'project').mkdir(parents=True)
        (out/'DELIVERY.json').write_text(json.dumps(self.expected))
        source = self.case/'work/raw/source.mp4'
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.good, source)
        (out/'SOURCE.json').write_text(json.dumps({'path': str(source), 'fingerprint': module('scan_raw').fingerprint(source)}))
        return out

    def test_healthy_render_measured_and_eight_proof_frames(self):
        result = self.verify(self.good)
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(result['frames']), 8)
        self.assertEqual(result['sha256'], self.verify_module.digest(self.good))
        self.assertTrue(Path(result['probe']).is_file())
        self.assertTrue(Path(result['contact']).is_file())

    def test_silence_rejected_even_with_audio_stream(self):
        result = self.verify(self.silent)
        self.assertFalse(result['ok'])
        self.assertIn('audio_silent_or_unmeasurable', result['failures'])

    def test_black_opening_rejected(self):
        result = self.verify(self.black)
        self.assertIn('black_opening', result['failures'])

    def test_wrong_dimensions_rejected(self):
        result = self.verify(self.good, dict(self.expected, width=1920))
        self.assertIn('dimensions_mismatch', result['failures'])

    def test_missing_audio_rejected(self):
        video = self.case/'no-audio.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.good), '-an',
                        '-c:v', 'copy', str(video)], check=True)
        self.assertIn('missing_audio_stream', self.verify(video)['failures'])

    def test_explicit_silent_delivery_accepts_zero_audio_stream(self):
        result = self.verify(self.silent, dict(self.expected, expect_audio=False))
        self.assertTrue(result['ok'], result)

    def test_finish_zero_exit_false_or_skipped_check_is_not_success(self):
        out = self.project()
        for payload in ('{"ok":false,"browserSkipped":false}', '{"ok":true,"browserSkipped":true}', '{}', 'invalid'):
            with self.subTest(payload=payload):
                result = self.run_script('finish.sh', out/'project', 'fixture', env=dict(self.env, TEST_CHECK_JSON=payload))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((out/'final/fixture.mp4').exists())

    def test_snapshot_failure_blocks_render(self):
        out = self.project()
        result = self.run_script('finish.sh', out/'project', 'fixture', env=dict(self.env, TEST_NO_SNAPSHOT='1'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((out/'final/fixture.mp4').exists())

    def test_zero_samples_fail_even_when_check_claims_ok(self):
        out = self.project()
        payload = {'ok': True, 'browserSkipped': False, 'lint': {'ok': True},
                   'runtime': {'ok': True}, 'audio': {'ok': True},
                   'layout': {'ok': True, 'samples': []},
                   'contrast': {'ok': True, 'enabled': True, 'samples': []}}
        result = self.run_script('finish.sh', out/'project', 'fixture',
                                 env=dict(self.env, TEST_CHECK_JSON=json.dumps(payload)))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((out/'final/fixture.mp4').exists())

    def test_silent_successful_encoder_does_not_deliver(self):
        out = self.project()
        result = self.run_script('finish.sh', out/'project', 'fixture', env=dict(self.env, TEST_RENDER_VIDEO=str(self.silent)))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((out/'final/fixture.mp4').exists())

    def test_finish_candidate_and_mark_require_exact_review(self):
        out = self.project()
        result = self.run_script('finish.sh', out/'project', 'fixture', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        candidate = json.loads(result.stdout)
        self.assertEqual(candidate['status'], 'candidate_awaiting_review')
        self.assertTrue(Path(candidate['video']).is_file())
        source = self.case/'work/raw/source.mp4'
        source.parent.mkdir(parents=True, exist_ok=True)
        root = source.parent.parent
        args = ('--root', root, '--mark', source, '--output', out)
        self.assertNotEqual(self.run_script('scan_raw.py', *args).returncode, 0)
        for name in ('ANALYSIS.md', 'REFERENCES.md', 'STYLE.md', 'BRIEF.md', 'STORYBOARD.md', 'EDIT.md'):
            (out/name).write_text('Synthetic fixture for delivery gate tests; no real creative review claimed.\n')
        qa = json.loads(Path(candidate['qa']).read_text())
        scan = module('scan_raw')
        review = {'status': 'passed', 'video': 'final/fixture.mp4', 'sha256': qa['sha256'],
                  'source_fingerprint': scan.fingerprint(source),
                  'audio_review': 'measured', 'limitations': ['Synthetic test fixture; audio not listened to.'],
                  'checks': {k: True for k in ('visual', 'audio', 'captions', 'timing')},
                  'evidence': ['Synthetic fixture: test-only review data to exercise state validation.']}
        (out/'REVIEW.json').write_text(json.dumps(review))
        marked = self.run_script('scan_raw.py', *args)
        self.assertEqual(marked.returncode, 0, marked.stderr)
        original_source = source.read_bytes()
        source.write_bytes(original_source + b'changed raw')
        self.assertNotEqual(self.run_script('scan_raw.py', *args).returncode, 0)
        # Merely updating the review to the new raw fingerprint cannot bless old QA.
        changed_review = dict(review, source_fingerprint=scan.fingerprint(source))
        (out/'REVIEW.json').write_text(json.dumps(changed_review))
        self.assertNotEqual(self.run_script('scan_raw.py', *args).returncode, 0)
        source.write_bytes(original_source)
        review['source_fingerprint'] = scan.fingerprint(source)
        (out/'REVIEW.json').write_text(json.dumps(review))
        # A changed render must invalidate the review even if filename is unchanged.
        with Path(candidate['video']).open('ab') as stream:
            stream.write(b'changed')
        self.assertNotEqual(self.run_script('scan_raw.py', *args).returncode, 0)

    def test_existing_delivery_preserved(self):
        out = self.project()
        (out/'final').mkdir()
        existing = out/'final/fixture.mp4'
        existing.write_bytes(b'previous user output')
        result = self.run_script('finish.sh', out/'project', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(existing.read_bytes(), b'previous user output')
        candidate = json.loads(result.stdout)
        self.assertNotEqual(candidate['video'], str(existing))
        self.assertTrue(Path(candidate['video']).is_file())

    def test_repaired_rerender_returns_new_candidate(self):
        out = self.project()
        first = self.run_script('finish.sh', out/'project', 'fixture')
        second = self.run_script('finish.sh', out/'project', 'fixture')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(json.loads(first.stdout)['video'], json.loads(second.stdout)['video'])

    def test_scan_oldest_first_collision_safe_and_read_only(self):
        root = self.case/'work'
        (root/'raw/nested').mkdir(parents=True)
        old, new = root/'raw/nested/a.mp4', root/'raw/a.mp4'
        old.write_bytes(b'old source')
        new.write_bytes(b'new source')
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        result = self.run_script('scan_raw.py', '--root', root, '--json')
        rows = json.loads(result.stdout)['pending']
        self.assertEqual([r['path'] for r in rows], [str(old), str(new)])
        self.assertNotEqual(rows[0]['slug'], rows[1]['slug'])
        self.assertEqual(old.read_bytes(), b'old source')
        self.assertFalse((self.case/'state/processed.json').exists())

    def test_hindi_english_only_model_rejected_and_multilingual_forwarded(self):
        result = self.run_script('transcribe.sh', self.good, '--language', 'hi', '--model', 'medium.en')
        self.assertEqual(result.returncode, 2)
        result = self.run_script('transcribe.sh', self.good, '--language', 'hi', '--model', 'medium')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.case/'commands.jsonl').read_text().splitlines()]
        self.assertEqual(calls[-1][calls[-1].index('--language')+1], 'hi')
        self.assertNotIn('hyperframes@latest', calls[-1])
        self.assertIn('--no-runtime-install', calls[-1])
        result = self.run_script('transcribe.sh', self.good, '--engine', 'auto', '--language', 'hi', '--model', 'medium')
        self.assertEqual(result.returncode, 2)

    def test_unknown_language_whisper_failure_never_falls_back(self):
        result = self.run_script('transcribe.sh', self.good, env=dict(self.env, TEST_WHISPER_FAIL='1'))
        self.assertNotEqual(result.returncode, 0)
        calls = [json.loads(line) for line in (self.case/'commands.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][calls[0].index('--engine')+1], 'whisper')

    def test_ingestion_fingerprint_immutable(self):
        source = self.case/'work/raw/input.mp4'
        source.parent.mkdir(parents=True)
        shutil.copyfile(self.good, source)
        out = self.case/'output'
        args = ('--root', source.parent.parent, '--record-source', source, '--output', out)
        self.assertEqual(self.run_script('scan_raw.py', *args).returncode, 0)
        original = (out/'SOURCE.json').read_bytes()
        with source.open('ab') as stream: stream.write(b'changed')
        self.assertNotEqual(self.run_script('scan_raw.py', *args).returncode, 0)
        self.assertEqual((out/'SOURCE.json').read_bytes(), original)

    def test_preflight_does_not_update_or_clone(self):
        result = self.run_script('bootstrap.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.case/'commands.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.case/'cache/awesome-opus5-5-videos').exists())

    def test_delivery_gate_bypass_and_bad_args_rejected(self):
        out = self.project()
        for option in ('--skip-check', '--skip-snapshot', '--allow-failed-check'):
            self.assertEqual(self.run_script('finish.sh', out/'project', 'fixture', option).returncode, 2)
        self.assertEqual(self.run_script('transcribe.sh', self.good, '--model').returncode, 2)
        self.assertEqual(self.run_script('matte.sh', self.good, self.case/'matte', '--device').returncode, 2)

    def test_corrupt_state_not_overwritten_by_mutation(self):
        state = self.case/'processed.json'
        state.write_text('{unreadable user state')
        result = self.run_script('scan_raw.py', '--state', state, '--unmark', self.good)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state.read_text(), '{unreadable user state')

    def test_missing_recorded_delivery_becomes_pending(self):
        root = self.case/'work'
        source = root/'raw/source.mp4'
        source.parent.mkdir(parents=True)
        shutil.copyfile(self.good, source)
        scan = module('scan_raw')
        state = self.case/'processed.json'
        state.write_text(json.dumps({'sources': {str(source): {
            'fingerprint': scan.fingerprint(source), 'video': str(self.case/'missing.mp4')
        }}}))
        result = self.run_script('scan_raw.py', '--root', root, '--state', state, '--json')
        rows = json.loads(result.stdout)['pending']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['reason'], 'recorded_delivery_missing')

    def test_invalid_expectation_numbers_rejected(self):
        path = self.case/'DELIVERY.json'
        for invalid in ('2', -1, float('inf'), True):
            with self.subTest(invalid=invalid):
                path.write_text(json.dumps(dict(self.expected, duration=invalid)))
                with self.assertRaises(ValueError):
                    self.verify_module.expectations(path)

    def test_watcher_service_preserves_overrides_without_enabling_real_service(self):
        fake_systemctl = self.case/'systemctl'
        fake_systemctl.write_text('#!/usr/bin/env bash\nexit 0\n')
        fake_systemctl.chmod(0o755)
        home = self.case/'isolated home'
        env = dict(self.env, HOME=str(home), PATH=str(self.case)+os.pathsep+self.env['PATH'],
                   DOPAMINE_ROOT=str(self.case/'work with spaces'), DOPAMINE_DEBOUNCE='23',
                   DOPAMINE_HF_VERSION='0.9.15')
        result = self.run_script('watch.sh', '--install-service', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = (home/'.config/systemd/user/dopamine-edit-watch.service').read_text()
        self.assertIn('"DOPAMINE_DEBOUNCE=23"', unit)
        self.assertIn('"DOPAMINE_HF_VERSION=0.9.15"', unit)
        self.assertIn('"DOPAMINE_STATE_DIR='+env['DOPAMINE_STATE_DIR']+'"', unit)
        self.assertIn('WorkingDirectory="'+env['DOPAMINE_ROOT']+'"', unit)

    def music_fixture(self, out, builtin=False):
        music = module('music')
        bed = out/'project/assets/audio/music/test/bed.wav'
        bed.parent.mkdir(parents=True)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.good), '-vn',
                        '-c:a', 'pcm_s16le', str(bed)], check=True)
        expected = dict(self.expected, expect_music=True)
        (out/'DELIVERY.json').write_text(json.dumps(expected))
        attribution = 'Synthetic fixture attribution for tests only.\n'
        record = {'status': 'ready', 'choice_reason': 'Sparse instrumental matches the educational synthetic fixture.',
                  'track_id': 'TEST-MUSIC', 'license': 'CC BY 4.0',
                  'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                  'license_evidence': {'statement': 'Synthetic test metadata, not real license proof.'},
                  'attribution': attribution,
                  'asset': {'path': str(bed.relative_to(out/'project')), 'sha256': music.sha(bed),
                            'duration': 2, 'integrated_lufs': -30, 'target_lufs': -30},
                  'timeline_id': 'bgm-bed'}
        if builtin:
            folder = bed.parent
            (folder/'license-evidence.html').write_text('Attribution Code Kevin MacLeod ' + music.LICENSE)
            (folder/'catalog-record.json').write_text('{"title": "Test"}')
            (folder/'original.mp3').write_bytes(bed.read_bytes())
            (folder/'ATTRIBUTION.txt').write_text(attribution)
            record.update({
                'provider': 'incompetech',
                'license_evidence': {'file': str((folder/'license-evidence.html').relative_to(out/'project')),
                                     'sha256': music.sha(folder/'license-evidence.html')},
                'catalog_record': {'path': str((folder/'catalog-record.json').relative_to(out/'project')),
                                   'sha256': music.sha(folder/'catalog-record.json')},
                'original': {'path': str((folder/'original.mp3').relative_to(out/'project')),
                             'sha256': music.sha(folder/'original.mp3'), 'duration': 2},
                'attribution_file': str((folder/'ATTRIBUTION.txt').relative_to(out/'project')),
            })
            record['identity'] = music.identity(record)
        (out/'MUSIC.json').write_text(json.dumps(record))
        timeline = {'timeline': {'tracks': [{'kind': 'audio', 'rows': [{
            'id': 'bgm-bed', 'kind': 'audio', 'src': record['asset']['path'],
            'absStart': 0, 'absEnd': 2, 'duration': 2, 'mediaStart': 0, 'volume': .3,
            'playbackRate': None, 'pendingReason': None, 'laneError': None, 'lanes': []
        }]}]}}
        return music, record, timeline

    def test_music_missing_or_not_mounted_blocks_finish(self):
        out = self.project()
        (out/'DELIVERY.json').write_text(json.dumps(dict(self.expected, expect_music=True)))
        self.assertNotEqual(self.run_script('finish.sh', out/'project', 'fixture').returncode, 0)
        music, record, timeline = self.music_fixture(out)
        result = self.run_script('finish.sh', out/'project', 'fixture')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((out/'final/fixture.mp4').exists())

    def test_required_music_gated_and_credits_packaged(self):
        out = self.project()
        music, record, timeline = self.music_fixture(out, builtin=True)
        result = self.run_script('finish.sh', out/'project', 'fixture',
                                 env=dict(self.env, TEST_TIMELINE_JSON=json.dumps(timeline)))
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = json.loads(result.stdout)
        self.assertEqual(Path(paths['music_credits']).read_text(), record['attribution'])
        qa = json.loads(Path(paths['qa']).read_text())
        self.assertEqual(qa['music']['sha256'], record['asset']['sha256'])
        self.assertEqual(qa['music']['identity'], record['identity'])
        with (out/'project'/record['asset']['path']).open('ab') as stream:
            stream.write(b'changed bed')
        with self.assertRaises(ValueError):
            music.check_music(out, timeline)

    def test_music_provenance_and_identity_tamper_rejected(self):
        out = self.project()
        music, record, timeline = self.music_fixture(out, builtin=True)
        music.check_music(out, timeline)
        credits = out/'project'/record['attribution_file']
        credits.write_text('different credit text\n')
        with self.assertRaises(ValueError):
            music.check_music(out)
        credits.write_text(record['attribution'])
        (out/'project'/record['license_evidence']['file']).write_text('rewritten license')
        with self.assertRaises(ValueError):
            music.check_music(out)
        (out/'project'/record['license_evidence']['file']).write_text(
            'Attribution Code Kevin MacLeod ' + music.LICENSE)
        record['title'] = 'Different track'
        (out/'MUSIC.json').write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            music.check_music(out)

    def test_music_timeline_gain_offset_and_rate_rejected(self):
        out = self.project()
        music, record, timeline = self.music_fixture(out)
        row = timeline['timeline']['tracks'][0]['rows'][0]
        variants = (
            {'volume': 0},
            {'volume': 1, 'lanes': [{'target': 'volume', 'points': [{'t': 0, 'v': 0}, {'t': 2, 'v': 0}]}]},
            {'playbackRate': 1.5},
            {'mediaStart': 1.5},
            {'laneError': 'Automation is not valid JSON'},
            {'pendingReason': 'unresolved duration'},
            {'absEnd': 1.0, 'duration': 1.0},
        )
        for change in variants:
            candidate = json.loads(json.dumps(timeline))
            candidate['timeline']['tracks'][0]['rows'][0].update(change)
            with self.assertRaises(ValueError, msg=str(change)):
                music.check_music(out, candidate)

    def test_music_wrong_duration_or_silent_bed_rejected(self):
        out = self.project()
        music, record, timeline = self.music_fixture(out)
        record['asset']['duration'] = 1
        (out/'MUSIC.json').write_text(json.dumps(record))
        with self.assertRaises(ValueError): music.check_music(out)
        record['asset']['duration'] = 2
        bed = out/'project'/record['asset']['path']
        bed.unlink()
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                        '-t', '2', '-c:a', 'pcm_s16le', str(bed)], check=True)
        record['asset']['sha256'] = music.sha(bed)
        (out/'MUSIC.json').write_text(json.dumps(record))
        with self.assertRaises(ValueError): music.check_music(out)

    def test_music_search_excludes_vocals_and_too_short(self):
        music = module('music')
        data = [
            {'title': 'Valid', 'isrc': 'VALID', 'length': '00:02:00', 'instruments': 'Piano', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Voice', 'isrc': 'VOICE', 'length': '00:02:00', 'instruments': 'Piano, Voice', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Choir', 'isrc': 'CHOIR', 'length': '00:02:00', 'instruments': 'Piano, Choirs', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Sung', 'isrc': 'SUNG', 'length': '00:02:00', 'instruments': 'Piano', 'description': 'A piece with wordless vocals.', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Clean', 'isrc': 'CLEAN', 'length': '00:02:00', 'instruments': 'Piano', 'description': 'An instrumental without any vocals.', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Short', 'isrc': 'SHORT', 'length': '00:00:01', 'instruments': 'Piano', 'feel': 'Calming', 'bpm': '90'},
            {'title': 'Fast', 'isrc': 'FAST', 'length': '00:02:00', 'instruments': 'Piano', 'feel': 'Calming', 'bpm': '190'},
        ]
        ranked = music.rank(data, 'calming piano', 15, 70, 110)
        self.assertEqual(sorted(r['id'] for r in ranked), ['CLEAN', 'VALID'])

    def test_new_project_requires_explicit_music_policy(self):
        path = self.case/'DELIVERY.json'
        base = {k: v for k, v in self.expected.items() if k not in {'expect_music', 'music_exception'}}
        path.write_text(json.dumps(base))
        with self.assertRaises(ValueError): self.verify_module.expectations(path)
        path.write_text(json.dumps(dict(base, legacy_project=True)))
        self.verify_module.expectations(path)

    def test_new_project_requires_explicit_brand_policy(self):
        path = self.case/'DELIVERY.json'
        base = {k: v for k, v in self.expected.items() if k != 'expect_brand'}
        path.write_text(json.dumps(base))
        with self.assertRaises(ValueError): self.verify_module.expectations(path)
        path.write_text(json.dumps(dict(base, legacy_project=True)))
        self.verify_module.expectations(path)

    def ensure_brand_dir(self):
        folder = self.case/'branddir'
        folder.mkdir(exist_ok=True)
        logo = folder/'logo.png'
        if not logo.is_file():
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                            '-i', 'color=c=0xffcc00:s=64x32', '-frames:v', '1', str(logo)], check=True)
            (folder/'logo.json').write_text(json.dumps({
                'asset_sha256': module('brand').sha(logo), 'width': 64, 'height': 32,
                'source': 'synthetic.png', 'recipe_version': 1,
                'note': 'Synthetic regression brand stand-in; not a real brand asset.'}))
        return folder

    def brand_fixture(self, out):
        self.ensure_brand_dir()
        (out/'DELIVERY.json').write_text(json.dumps(dict(self.expected, expect_brand=True)))
        result = self.run_script('brand.py', 'install', '--project', out/'project')
        self.assertEqual(result.returncode, 0, result.stderr)
        timeline = {'timeline': {'tracks': [
            {'kind': 'video', 'rows': [{'id': 'clip', 'kind': 'video', 'src': 'assets/source.mp4',
                                        'absStart': 0, 'absEnd': 2, 'duration': 2, 'mediaStart': 0,
                                        'pendingReason': None, 'laneError': None}]},
            {'kind': 'graphics', 'rows': [{'id': 'brand-layer', 'kind': 'img', 'src': 'assets/brand/logo.png',
                                           'absStart': 0, 'absEnd': 2, 'duration': 2, 'mediaStart': None,
                                           'pendingReason': None, 'laneError': None}]},
        ]}}
        return timeline

    def test_brand_required_missing_or_unmounted_blocks_finish(self):
        out = self.project()
        (out/'DELIVERY.json').write_text(json.dumps(dict(self.expected, expect_brand=True)))
        self.assertNotEqual(self.run_script('finish.sh', out/'project', 'fixture').returncode, 0)
        self.brand_fixture(out)
        unmounted = self.run_script('finish.sh', out/'project', 'fixture')
        self.assertNotEqual(unmounted.returncode, 0)
        self.assertFalse((out/'final/fixture.mp4').exists())

    def test_brand_gated_installed_and_tamper_rejected(self):
        out = self.project()
        timeline = self.brand_fixture(out)
        brand = module('brand')
        result = self.run_script('finish.sh', out/'project', 'fixture',
                                 env=dict(self.env, TEST_TIMELINE_JSON=json.dumps(timeline)))
        self.assertEqual(result.returncode, 0, result.stderr)
        qa = json.loads(Path(json.loads(result.stdout)['qa']).read_text())
        self.assertEqual(qa['brand']['status'], 'ready')
        target = out/'project/assets/brand/logo.png'
        target.write_bytes(target.read_bytes() + b'x')
        with patch.dict(os.environ, {'DOPAMINE_BRAND_DIR': str(self.ensure_brand_dir())}):
            with self.assertRaises(ValueError):
                brand.check(out, timeline)
        self.assertTrue((out/'project/assets/brand/BRAND.json').is_file())

    def test_brand_timeline_mismatch_rejected(self):
        out = self.project()
        timeline = self.brand_fixture(out)
        brand = module('brand')
        for change in ({'id': 'other'}, {'src': 'assets/brand/other.png'}, {'absEnd': 1.0, 'duration': 1.0},
                       {'laneError': 'bad automation'}):
            candidate = json.loads(json.dumps(timeline))
            candidate['timeline']['tracks'][1]['rows'][0].update(change)
            with patch.dict(os.environ, {'DOPAMINE_BRAND_DIR': str(self.ensure_brand_dir())}):
                with self.assertRaises(ValueError, msg=str(change)):
                    brand.check(out, candidate)

    def preview_approve(self, out, slug='fixture', note='User reviewed the draft in chat.'):
        draft = out/'preview'/f'{slug}-draft.mp4'
        draft.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.good, draft)
        recorded = self.run_script('preview.py', 'record', '--root', out, '--slug', slug,
                                   '--video', draft, '--qa', out/'preview'/'draft-qa.json')
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        approved = self.run_script('preview.py', 'approve', '--root', out, '--note', note)
        self.assertEqual(approved.returncode, 0, approved.stderr)
        return json.loads(approved.stdout)

    def test_delivery_requires_approved_preview(self):
        out = self.project()
        unattended = {k: v for k, v in self.env.items() if k != 'DOPAMINE_SKIP_PREVIEW'}
        blocked = self.run_script('finish.sh', out/'project', 'fixture', env=unattended)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn('approved preview', blocked.stderr)
        self.assertFalse((out/'final/fixture.mp4').exists())
        self.preview_approve(out)
        allowed = self.run_script('finish.sh', out/'project', 'fixture', env=unattended)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(json.loads(allowed.stdout)['status'], 'candidate_awaiting_review')

    def test_preview_approval_invalidated_by_composition_edit(self):
        out = self.project()
        (out/'project/index.html').write_text('<div id="root"></div>\n')
        self.preview_approve(out)
        self.run_script('preview.py', 'verify', '--root', out)
        (out/'project/index.html').write_text('<div id="root">changed</div>\n')
        check = self.run_script('preview.py', 'verify', '--root', out)
        self.assertEqual(json.loads(check.stdout)['status'], 'changed')
        unattended = {k: v for k, v in self.env.items() if k != 'DOPAMINE_SKIP_PREVIEW'}
        blocked = self.run_script('finish.sh', out/'project', 'fixture', env=unattended)
        self.assertNotEqual(blocked.returncode, 0)
        approve_again = self.run_script('preview.py', 'approve', '--root', out)
        self.assertNotEqual(approve_again.returncode, 0)
        self.assertIn('changed since the preview', approve_again.stderr)

    def test_preview_sh_writes_preview_only_and_records(self):
        out = self.project()
        result = self.run_script('preview.sh', out/'project', 'fixture', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['status'], 'awaiting_review')
        self.assertTrue(Path(summary['video']).is_file())
        self.assertIn('preview.py approve', summary['approve_command'])
        record = json.loads((out/'preview/PREVIEW.json').read_text())
        self.assertEqual(record['status'], 'awaiting_review')
        self.assertEqual(record['quality'], 'draft')
        self.assertFalse((out/'final/fixture.mp4').exists())
        preview_video = out/'preview/fixture-preview.mp4'
        with self.assertRaises(ValueError):
            module('preview').record(argparse.Namespace(
                root=str(out), slug='fixture', video=str(out/'preview/missing.mp4'), cover=None,
                contact=None, qa=str(out/'preview/fixture-preview-qa.json'), attempt=None))
        with self.assertRaises(ValueError):
            module('preview').record(argparse.Namespace(
                root=str(out), slug='fixture', video=str(out/'final/fixture.mp4'), cover=None,
                contact=None, qa=None, attempt=None))
        self.assertTrue(preview_video.is_file())

    def test_skip_preview_env_allows_unattended_delivery(self):
        out = self.project()
        result = self.run_script('finish.sh', out/'project', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out/'final/fixture.mp4').is_file())
        self.assertFalse((out/'preview/PREVIEW.json').exists())

    def test_music_level_separation_gate(self):
        out = self.project()
        music, record, timeline = self.music_fixture(out)
        ready = music.check_music(out, timeline)
        self.assertGreaterEqual(ready['separation_db'], 18)
        self.assertAlmostEqual(ready['music_level_lufs'], -30 + 20 * math.log10(.3), places=1)
        loud = json.loads(json.dumps(timeline))
        loud['timeline']['tracks'][0]['rows'][0]['volume'] = 1.0
        record['asset']['integrated_lufs'] = -20
        (out/'MUSIC.json').write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            music.check_music(out, loud)
        relaxed = dict(self.expected, expect_music=True, music_separation_db=6)
        (out/'DELIVERY.json').write_text(json.dumps(relaxed))
        self.assertEqual(music.check_music(out, loud)['status'], 'ready')

    def test_voice_contrast_gate_and_measurement(self):
        out = self.project()
        result = self.verify(self.good)
        self.assertTrue(result['ok'], result['failures'])
        self.assertIn('voice_contrast_db', result['measurements'])
        strict = dict(self.expected, min_voice_contrast_db=40)
        (out/'DELIVERY.json').write_text(json.dumps(strict))
        strict_result = self.verify(self.good, strict)
        self.assertFalse(strict_result['ok'])
        self.assertTrue(any('voice_contrast' in f for f in strict_result['failures']))
        bad = {k: v for k, v in self.expected.items() if k != 'min_voice_contrast_db'}
        bad['min_voice_contrast_db'] = 99
        path = self.case/'DELIVERY.json'
        path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError): self.verify_module.expectations(path)

    def test_brand_cutout_produces_transparent_asset(self):
        if not shutil.which('magick'):
            self.skipTest('ImageMagick required')
        work = self.case/'brandsrc'
        work.mkdir()
        source = work/'source.png'
        subprocess.run(['magick', '-size', '400x300', 'xc:#05070b', '-fill', '#ffe14d',
                        '-draw', 'circle 200,160 200,80', '-fill', '#37c6ff',
                        '-draw', 'circle 300,100 300,70', '-depth', '8', str(source)], check=True)
        out = work/'out'
        result = self.run_script('brand-cutout.sh', source, '--outdir', out, '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((out/'logo.json').read_text())
        self.assertGreater(record['alpha_coverage'], 0.005)
        channels = subprocess.run(['magick', 'identify', '-format', '%[channels]', str(out/'logo.png')],
                                  capture_output=True, text=True, check=True).stdout
        self.assertIn('a', channels)
        again = self.run_script('brand-cutout.sh', source, '--outdir', out, '--json')
        self.assertIn('up to date', again.stdout)

    def test_music_prepare_download_decode_and_license_gate(self):
        music = module('music')
        source = self.case/'track.mp3'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(self.good), '-vn', str(source)], check=True)
        project = self.case/'music-project'
        project.mkdir()
        args = argparse.Namespace(project=str(project), record=str(self.case/'MUSIC.json'), id='USUAN1400037',
                                  query='calming', reason='Matches sparse educational footage', start=0, duration=2)
        track = {'title': 'Test', 'isrc': args.id, 'filename': 'Test.mp3', 'instruments': 'Piano'}
        license_page = ('Attribution Code Kevin MacLeod ' + music.LICENSE).encode()
        def fake_fetch(url, destination=None, max_bytes=music.MAX_BYTES):
            if destination: shutil.copyfile(source, destination); return source.stat().st_size
            return license_page
        with patch.object(music, 'catalog', return_value=[track]), patch.object(music, 'fetch', side_effect=fake_fetch):
            prepared = music.prepare(args)
        self.assertEqual(prepared['status'], 'ready')
        self.assertAlmostEqual(prepared['asset']['duration'], 2, places=1)
        self.assertEqual(prepared['identity'], music.identity(prepared))
        self.assertTrue((project/prepared['asset']['path']).is_file())
        self.assertTrue((project/prepared['attribution_file']).is_file())
        self.assertTrue((project/prepared['license_evidence']['file']).is_file())
        args.record = str(self.case/'bad-license.json')
        with patch.object(music, 'catalog', return_value=[track]), patch.object(music, 'fetch', return_value=b'no license'):
            with self.assertRaises(ValueError): music.prepare(args)

    def test_music_exception_requires_reason(self):
        path = self.case/'DELIVERY.json'
        no_reason = {k: v for k, v in self.expected.items() if k != 'music_exception'}
        path.write_text(json.dumps(no_reason))
        with self.assertRaises(ValueError): self.verify_module.expectations(path)
        path.write_text(json.dumps(dict(no_reason, music_exception='User asked for no music.')))
        self.verify_module.expectations(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
