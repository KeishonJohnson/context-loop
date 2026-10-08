import contextlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from existing_fixture import make, GOOD
from context_loop.adopt import attach, approve, inspect_project
from context_loop.cli import main
from context_loop.config import load, contract_digest, protected_paths, argv
from context_loop.context import prepare, for_task, source_manifest, validate_citations
from context_loop.runner import Runner
from context_loop.storage import ContextLoopError, read_json, write_json, lock
from context_loop.transport import execute, profile

class ExistingHarness:
    def __init__(self, root, behavior='success'):
        self.root, self.behavior, self.calls, self.prompts = root, behavior, [], []
    def __call__(self, command, cwd, log, timeout, cap, stop, child, prompt=None):
        if prompt is None: return execute(command, cwd, log, timeout, cap, stop, child)
        output = Path(command[command.index('-o')+1])
        config = read_json(self.root / 'context-loop.json')
        ctx = prepare(self.root, config)
        audit = output.name == 'alignment.json'
        self.calls.append('audit' if audit else 'execute')
        self.prompts.append(prompt)
        selected = ctx['sources'] if audit else for_task(ctx, config['tasks'][0])
        citations = [{'id':s['id'], 'sha256':s['sha256']} for s in selected]
        result = {'status':'aligned' if audit else 'done', 'summary':'Fixture alignment' if audit else 'Implemented R1 and R2', 'sources':citations, 'conflicts':[]}
        if audit and self.behavior == 'conflict':
            result.update(status='conflict', summary='Roadmap contradicts decisions', conflicts=['Contradictory documented direction'])
        if not audit:
            (cwd / 'src/app.py').write_text(GOOD)
            result['requirement_ids'] = ['R1', 'R2']
            if self.behavior == 'citation': result['sources'] = []
            if self.behavior == 'requirements': result['requirement_ids'] = ['invented']
            if self.behavior == 'source-drift': (cwd / 'docs/Build.md').write_text('Drifted governing document')
            if self.behavior == 'reported-conflict': result['conflicts'] = ['Scope contradicts a decision']
        output.write_text(json.dumps(result))
        log.write_text(json.dumps({'type':'turn.completed', 'usage':{'input_tokens':100, 'output_tokens':10}})+'\n')
        return {'returncode':0, 'reason':None, 'elapsed':.01}

class ExistingProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.base = Path(self.temp.name)
        self.root, self.vault, self.originals = make(self.base)
    def tearDown(self): self.temp.cleanup()
    def config(self): return read_json(self.root / 'context-loop.json')
    def save(self, config): write_json(self.root / 'context-loop.json', config)
    def run_with(self, behavior='success', check=False):
        h = ExistingHarness(self.root, behavior)
        return Runner(self.root, 'fixture-codex', h, sandbox=False).run(check), h
    def test_attachment_preserves_all_originals(self):
        for relative, original in self.originals.items():
            self.assertEqual((self.root / relative).read_bytes(), original)
    def test_existing_layout_and_independent_completion(self):
        state, h = self.run_with()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(h.calls, ['audit','execute'])
        self.assertTrue((self.root/'src/app.py').is_file())
        self.assertFalse((self.root/'workspace').exists())
        self.assertEqual(state['reported_tokens'],220)
        self.assertIn('execution_sources',state['tasks']['greeting'])
        self.assertIn('R1', (self.root/'Context Loop/Tasks.md').read_text())
    def test_original_output_notes_not_overwritten(self):
        self.run_with()
        for name in ['AGENTS.md','src/AGENTS.md','Progress.md','Tasks.md','.gitignore','README.md','docs/Build.md','docs/Status.md']:
            self.assertEqual((self.root/name).read_bytes(),self.originals[name])
    def test_external_notes_remain_unchanged(self):
        before={p.name:p.read_bytes() for p in self.vault.glob('*.md')}
        self.run_with()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.vault.glob('*.md')})
    def test_prompt_source_order_and_selective_wikilinks(self):
        _,h=self.run_with()
        prompt=h.prompts[-1]
        self.assertLess(prompt.index('"role": "instructions"'),prompt.index('"role": "roadmap"'))
        self.assertIn('Ada should receive Hello, Ada!',prompt)
        self.assertNotIn('UNRELATED_NOTE_MUST_NOT_ENTER_TASK_CONTEXT',prompt)
        self.assertIn('Return exactly Hello, <name>!',prompt)
    def test_declared_conflicts_stop_before_checks_or_edit(self):
        c=self.config();c['context']['conflicts']=['Unresolved direction'];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'conflicts'): load(self.root)
    def test_alignment_conflict_blocks_green_tests(self):
        (self.root/'src/app.py').write_text(GOOD)
        state,h=self.run_with('conflict')
        self.assertEqual(state['status'],'blocked')
        self.assertEqual(h.calls,['audit'])
    def test_conflict_requires_fresh_owner_approval(self):
        self.run_with('conflict')
        with self.assertRaisesRegex(ContextLoopError,'fresh explicit approval'): self.run_with()
        approve(self.root,'Owner resolves conflict and explicitly authorizes a fresh review')
        self.assertEqual(self.run_with()[0]['status'],'complete')
    def test_missing_citations_reject_done_and_persist(self):
        state,_=self.run_with('citation')
        self.assertEqual(state['status'],'error')
        with self.assertRaisesRegex(ContextLoopError,'fresh explicit approval'): self.run_with()
    def test_wrong_requirements_reject_done(self):
        self.assertEqual(self.run_with('requirements')[0]['status'],'error')
    def test_execution_conflict_rejects_completion(self):
        self.assertEqual(self.run_with('reported-conflict')[0]['status'],'error')
    def test_source_drift_during_execution_rejects_acceptance(self):
        self.assertEqual(self.run_with('source-drift')[0]['status'],'error')
    def test_source_drift_between_runs_requires_approval(self):
        (self.root/'docs/Status.md').write_text('New owner status')
        with self.assertRaisesRegex(ContextLoopError,'drifted'): self.run_with()
        approve(self.root,'Owner reviews updated status')
        self.assertEqual(self.run_with()[0]['status'],'complete')
    def test_wikilink_note_drift_invalidates_approval(self):
        (self.vault/'Examples.md').write_text('Revised guidance')
        with self.assertRaisesRegex(ContextLoopError,'drifted'): self.run_with()
    def test_check_script_drift_invalidates_approval(self):
        (self.root/'Context Loop/checks/acceptance.py').write_text("print('weak replacement')")
        with self.assertRaisesRegex(ContextLoopError,'drifted'): self.run_with()
    def test_missing_note_fails_closed(self):
        (self.vault/'Examples.md').unlink()
        with self.assertRaisesRegex(ContextLoopError,'Missing or ambiguous'): load(self.root)
    def test_ambiguous_note_fails_closed(self):
        (self.root/'Guidance.md').write_text('Ambiguous local source')
        with self.assertRaisesRegex(ContextLoopError,'ambiguous'): load(self.root)
    def test_unknown_requirement_rejected(self):
        c=self.config();c['tasks'][0]['requirements']=['R404'];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'requirement IDs'):load(self.root)
    def test_inexact_requirement_quote_rejected(self):
        c=self.config();c['context']['requirements']['R1']['quote']='Invented requirement';self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'exact text'):load(self.root)
    def test_research_cannot_be_requirement_authority(self):
        c=self.config();c['context']['sources'].append({'id':'supporting-research','role':'research','path':str(self.vault/'Examples.md')})
        c['context']['requirements']['R1']={'source':'supporting-research','quote':'Ada should receive Hello, Ada!'};self.save(c)
        with self.assertRaises(ContextLoopError):load(self.root)
    def test_new_nested_instructions_require_mapping(self):
        (self.root/'src/extra').mkdir();(self.root/'src/extra/AGENTS.md').write_text('New local instructions')
        with self.assertRaisesRegex(ContextLoopError,'Unmapped'):load(self.root)
    def test_unapproved_project_cannot_run(self):
        (self.root/'Context Loop/Approval.json').unlink()
        with self.assertRaisesRegex(ContextLoopError,'not been approved'):self.run_with()
    def test_empty_checks_cannot_be_approved(self):
        c=self.config();c['tasks'][0]['checks']=[];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'independent checks'):approve(self.root,'Invalid approval')
    def test_whole_root_write_refused(self):
        c=self.config();c['write_paths']=['.'];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'project root'):load(self.root)
    def test_control_and_case_alias_write_refused(self):
        for path in ['Context Loop','context loop','.git','.GIT','AGENTS.md','../outside']:
            c=self.config();c['write_paths']=[path];self.save(c)
            with self.subTest(path=path),self.assertRaises(ContextLoopError):load(self.root)
    def test_external_sources_need_explicit_vault_root(self):
        outside=self.base/'other.md';outside.write_text('Outside research')
        c=self.config();c['context']['sources'].append({'id':'outside','role':'research','path':str(outside)});self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'outside declared'):load(self.root)
    def test_symlink_source_refused(self):
        path=self.vault/'Examples.md';path.unlink();path.symlink_to(self.vault/'Guidance.md')
        with self.assertRaisesRegex(ContextLoopError,'symlink'):load(self.root)
    def test_symlink_write_scope_refused(self):
        (self.root/'shortcut').symlink_to(self.vault,target_is_directory=True)
        c=self.config();c['write_paths']=['shortcut'];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'symlink'):load(self.root)
    def test_context_budget_fails_without_truncation(self):
        c=self.config();c['context']['max_context_bytes']=1000;self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'exceeds budget'):load(self.root)
    def test_existing_attach_paths_refused(self):
        with self.assertRaisesRegex(ContextLoopError,'already exist'):attach(self.root)
    def test_inspect_is_read_only(self):
        before=set(self.root.rglob('*')); data=inspect_project(self.root)
        self.assertIn('docs/Build.md',data['document_candidates'])
        self.assertEqual(before,set(self.root.rglob('*')))
    def test_approve_refuses_active_runner(self):
        with lock(self.root),self.assertRaisesRegex(ContextLoopError,'already active'):approve(self.root,'Cannot approve during run')
    def test_check_only_does_not_invoke_model_or_claim_alignment(self):
        (self.root/'src/app.py').write_text(GOOD)
        state,h=self.run_with(check=True)
        self.assertEqual(state['status'],'checks_passed');self.assertEqual(h.calls,[])
    def test_resume_reaudits_and_revalidates(self):
        self.run_with()
        state,h=self.run_with()
        self.assertEqual(state['status'],'complete');self.assertEqual(h.calls,['audit'])
    def test_status_reports_drift_instead_of_stale_complete(self):
        self.run_with();(self.vault/'Examples.md').write_text('New note')
        output=io.StringIO()
        with contextlib.redirect_stdout(output): result=main(['status',str(self.root)])
        self.assertEqual(result,1);self.assertEqual(json.loads(output.getvalue())['status'],'context_unready')
    def test_profile_protects_nested_sources_and_controls(self):
        config=self.config();text=' '.join(profile(self.root,'fixture',True,config))
        self.assertIn(str(self.root/'src/Policy.md'),text)
        self.assertIn(str(self.root/'Context Loop'),text)
        self.assertIn('"read"',text);self.assertIn('"write"',text)
    def test_control_placeholder_resolves_correctly(self):
        command=argv(self.config()['tasks'][0]['checks'][0],self.root,self.config())
        self.assertEqual(command[-1],str(self.root/'Context Loop/checks/acceptance.py'))
    def test_nonselected_vault_note_changes_do_not_load_or_reset_context(self):
        (self.vault/'Unused.md').write_text('Unselected note changed')
        self.assertEqual(self.run_with()[0]['status'],'complete')
    def test_nested_check_named_like_generated_output_is_frozen(self):
        p=self.root/'Context Loop/checks/Progress.md';p.write_text('Owner acceptance definition')
        approve(self.root,'Owner pins additional acceptance file')
        p.write_text('Changed acceptance definition')
        with self.assertRaisesRegex(ContextLoopError,'drifted'):self.run_with()
    def test_malformed_source_is_clear_error(self):
        c=self.config();c['context']['sources'].append(None);self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'objects'):load(self.root)
    def test_malformed_requirement_reference_is_clear_error(self):
        c=self.config();c['tasks'][0]['requirements']=[{}];self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'requirement IDs'):load(self.root)
    def test_malformed_citation_rejected(self):
        ctx=prepare(self.root,self.config())
        with self.assertRaises(ContextLoopError):validate_citations({'sources':[{'id':[],'sha256':None}]},ctx['sources'])
    def test_unsafe_note_traversal_refused(self):
        (self.vault/'Project Index.md').write_text('[[../outside]]')
        with self.assertRaisesRegex(ContextLoopError,'Unsafe'):load(self.root)
    def test_generated_progress_cannot_govern_itself(self):
        c=self.config();c['context']['sources'].append({'id':'circular','role':'status','path':'Context Loop/Progress.md'});self.save(c)
        with self.assertRaisesRegex(ContextLoopError,'cannot govern'):load(self.root)
    def test_source_hash_pins_exact_bytes_including_line_endings(self):
        p=self.root/'docs/Status.md'
        p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'))
        with self.assertRaisesRegex(ContextLoopError,'drifted'):self.run_with()
    def test_git_head_and_original_documents_preserved(self):
        with tempfile.TemporaryDirectory(dir=self.base) as directory:
            root,vault,originals=make(Path(directory),git=True)
            before=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'])
            h=ExistingHarness(root);state=Runner(root,'fixture',h,sandbox=False).run()
            self.assertEqual(state['status'],'complete')
            self.assertEqual(before,subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']))
            for name,contents in originals.items():
                if name!='src/app.py':self.assertEqual((root/name).read_bytes(),contents)

if __name__=='__main__':unittest.main()
