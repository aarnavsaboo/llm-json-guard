import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from jsonschema.exceptions import SchemaError
from llm_json_guard import (OutputParseError, extract_json, require_keys, OutputGuard,
    generate_validated, agenerate_validated, GenerationFailed, validate_entity_spans)

SCHEMA = {"type":"object", "properties":{"score":{"type":"number","minimum":0,"maximum":1}},
          "required":["score"], "additionalProperties":False}

class ParsingTests(unittest.TestCase):
    def test_plain(self): self.assertEqual(extract_json('{"a":1}'), {"a":1})
    def test_fenced(self): self.assertEqual(extract_json('Result:\n```json\n{"a":1}\n```'), {"a":1})
    def test_arrays_and_scalars(self):
        for raw, value in [('[]',[]),('false',False),('null',None),('2',2)]:
            self.assertEqual(extract_json(raw), value)
    def test_prose_is_opt_in(self):
        with self.assertRaises(OutputParseError): extract_json('Result {"a":1} done')
        self.assertEqual(extract_json('Result {"a":1} done',allow_prose=True), {"a":1})
    def test_ambiguity(self):
        with self.assertRaises(OutputParseError): extract_json('{"a":1} {"a":2}',allow_prose=True)
    def test_multiple_fences(self):
        with self.assertRaises(OutputParseError): extract_json('```json\n{}\n```\n```json\n{}\n```')
    def test_duplicate_keys(self):
        with self.assertRaises(OutputParseError): extract_json('{"a":1,"a":2}')
    def test_nonfinite(self):
        for value in ('NaN','Infinity','-Infinity','1e999'):
            with self.assertRaises(OutputParseError): extract_json(value)
    def test_invalid(self):
        for value in ('',"{'a':1}",'{"a":1,}'):
            with self.assertRaises(OutputParseError): extract_json(value)
    def test_braces_in_strings(self):
        self.assertEqual(extract_json('before {"a":"} ["} after',allow_prose=True), {"a":"} ["})
    def test_character_budget(self):
        with self.assertRaises(OutputParseError): extract_json('{}',max_chars=1)
    def test_require_keys(self):
        self.assertEqual(require_keys({"x":1},["x"]), {"x":1})
        with self.assertRaises(ValueError): require_keys({},['x'])

class SchemaTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(OutputGuard(SCHEMA).validate('{"score":0.4}').valid)
    def test_no_coercion(self): self.assertFalse(OutputGuard(SCHEMA).validate('{"score":"0.4"}').valid)
    def test_issue_path(self):
        result = OutputGuard(SCHEMA).validate('{"score":2}')
        self.assertEqual((result.issues[0].path,result.issues[0].keyword), ('/score','maximum'))
    def test_additional_properties(self):
        self.assertFalse(OutputGuard(SCHEMA).validate('{"score":0.2,"other":1}').valid)
    def test_boolean_not_integer(self):
        self.assertFalse(OutputGuard({"type":"integer"}).validate('true').valid)
    def test_local_reference(self):
        guard=OutputGuard({"$defs":{"score":SCHEMA},"$ref":"#/$defs/score"})
        self.assertTrue(guard.validate('{"score":0.5}').valid)
    def test_bad_schema(self):
        with self.assertRaises(SchemaError): OutputGuard({"type":"nonsense"})
    def test_external_reference(self):
        with self.assertRaises(ValueError): OutputGuard({"$ref":"https://example.com/schema"})
    def test_parse_failure(self): self.assertEqual(OutputGuard(SCHEMA).validate('hello').issues[0].keyword,'parse')
    def test_span_checks(self):
        self.assertEqual(validate_entity_spans({"entities":[{"text":"Ada","start":0,"end":3}]},'Ada here'),[])
        self.assertTrue(validate_entity_spans({"entities":[{"text":"Ada","start":1,"end":3}]},'Ada here'))
        self.assertTrue(validate_entity_spans({"entities":[{"text":"Ada","start":True,"end":3}]},'Ada here'))
    def test_post_validator(self):
        guard=OutputGuard({"type":"object"},post_validate=lambda value:validate_entity_spans(value,'Ada'))
        self.assertFalse(guard.validate('{}').valid)
    def test_format_opt_in(self):
        schema={"type":"string","format":"ipv4"}
        self.assertFalse(OutputGuard(schema,check_formats=True).validate('"not-an-ip"').valid)
        self.assertTrue(OutputGuard(schema).validate('"not-an-ip"').valid)

class GenerationTests(unittest.TestCase):
    def test_feedback_and_recovery(self):
        replies=iter(['{"score":2}','{"score":0.4}']); prompts=[]
        def generate(prompt): prompts.append(prompt); return next(replies)
        result=generate_validated(generate,'Score this',OutputGuard(SCHEMA))
        self.assertEqual(len(result.attempts),2)
        self.assertIn('/score',prompts[1])
    def test_bounded_failure(self):
        with self.assertRaises(GenerationFailed) as ctx:
            generate_validated(lambda p:'no','test',OutputGuard(SCHEMA),2)
        self.assertEqual(len(ctx.exception.attempts),2)
    def test_generator_exception_not_retried(self):
        def generate(prompt): raise RuntimeError('offline')
        with self.assertRaises(RuntimeError): generate_validated(generate,'test',OutputGuard(SCHEMA))
    def test_attempt_limit(self):
        for n in (0,11,True):
            with self.assertRaises(ValueError): generate_validated(lambda p:'{}','test',OutputGuard(SCHEMA),n)
    def test_async(self):
        async def generate(prompt): return '{"score":0.7}'
        result=asyncio.run(agenerate_validated(generate,'score',OutputGuard(SCHEMA)))
        self.assertEqual(result.data['score'],0.7)
    def test_batch_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory); (p/'schema.json').write_text(json.dumps(SCHEMA))
            (p/'outputs.jsonl').write_text(json.dumps({'id':'one','output':'{"score":0.5}'})+'\nnot-json\n')
            result=subprocess.run([sys.executable,'-m','llm_json_guard','batch',str(p/'outputs.jsonl'),'--schema',str(p/'schema.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertEqual(json.loads(result.stdout)['pass_rate'],0.5)

if __name__ == '__main__': unittest.main()
