from roffio import Format, read, write


def test_file_mode_creation(tmp_path):
    test_file = tmp_path / "test.roff"

    with open(test_file, "bw") as f:
        f.write(b"roff-bin\0tag\0a\0int\0b\0\0\0\0\0endtag\0")

    assert read(test_file) == {"a": {"b": 0}}

    with open(test_file, "w") as f:
        f.write("roff-asc tag a int σ 0 endtag")

    assert read(test_file) == {"a": {"σ": 0}}


def test_read_handles_single_quotation_marks(tmpdir):
    contents = {"tagname": [("keyname", "'")]}

    with tmpdir.as_cwd():
        write("file.roff", contents, roff_format=Format.ASCII)
        read("file.roff")
