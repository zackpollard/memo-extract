import json

from memo_extract.data import load_memos, read_jsonl

VALID = {"id": "m1", "text": "Sam loves chess", "spans": [{"id": "p1", "type": "PERSON", "text": "Sam", "pronoun": "he"}]}
INVALID = {"id": "m2", "text": "Sam loves chess", "spans": [{"id": "p1", "type": "PERSON", "text": "Bob", "pronoun": "he"}]}


def write_jsonl(path, lines):
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


class TestReadJsonl:
    def test_reads_every_file_in_order_and_skips_blank_lines(self, tmp_path):
        first = write_jsonl(tmp_path / "a.jsonl", ['{"id": 1}', "", "   ", '{"id": 2}'])
        second = write_jsonl(tmp_path / "b.jsonl", ['{"id": 3}'])

        records = read_jsonl([first, second])

        assert [r["id"] for r in records] == [1, 2, 3]

    def test_keeps_non_ascii_text(self, tmp_path):
        path = write_jsonl(tmp_path / "a.jsonl", [json.dumps({"text": "Lucía ☕"}, ensure_ascii=False)])

        assert read_jsonl([path]) == [{"text": "Lucía ☕"}]


class TestLoadMemos:
    def test_returns_valid_memos_and_the_ids_of_invalid_records(self, tmp_path):
        path = write_jsonl(tmp_path / "a.jsonl", [json.dumps(VALID), json.dumps(INVALID)])

        memos, rejected = load_memos([path])

        assert [m.id for m in memos] == ["m1"]
        assert rejected == ["m2"]
