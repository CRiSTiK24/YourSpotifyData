import os
import zipfile

import pytest

from src.upload import service as upload_service


def _make_zip(tmp_path, entries: dict[str, bytes]) -> str:
    zip_path = str(tmp_path / "export.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return zip_path


def test_validate_and_list_matches_only_keeps_files_matching_spotify_export_patterns(tmp_path):
    zip_path = _make_zip(
        tmp_path,
        {
            "Streaming_History_Audio_2024_1.json": b"[]",
            "irrelevant.txt": b"hello",
            "YourLibrary.json": b"{}",
        },
    )
    zf, matches = upload_service.validate_and_list_matches(zip_path)
    zf.close()
    assert [basename for _info, basename in matches] == ["Streaming_History_Audio_2024_1.json"]


def test_validate_and_list_matches_rejects_a_zip_with_no_recognizable_export_files(tmp_path):
    zip_path = _make_zip(tmp_path, {"random.txt": b"hello"})
    with pytest.raises(upload_service.InvalidZip):
        upload_service.validate_and_list_matches(zip_path)


def test_validate_and_list_matches_rejects_a_corrupt_zip_file(tmp_path):
    bad_path = str(tmp_path / "not_a_zip.zip")
    with open(bad_path, "wb") as f:
        f.write(b"this is not a zip file")
    with pytest.raises(upload_service.InvalidZip):
        upload_service.validate_and_list_matches(bad_path)


def test_extract_matches_strips_directory_traversal_from_zip_entry_names(tmp_path):
    dest_dir = str(tmp_path / "dest")
    zip_path = _make_zip(
        tmp_path, {"../../etc/Streaming_History_Audio_evil.json": b'{"pwned": true}'}
    )
    zf = zipfile.ZipFile(zip_path)
    matches = [(info, os.path.basename(info.filename)) for info in zf.infolist()]

    extracted = upload_service.extract_matches_to_sanitized_paths(zf, matches, dest_dir)

    assert extracted == ["Streaming_History_Audio_evil.json"]
    extracted_files = os.listdir(dest_dir)
    assert extracted_files == ["Streaming_History_Audio_evil.json"]
    assert not os.path.exists(os.path.join(tmp_path, "etc"))


def test_parse_summary_finds_the_last_json_line_in_noisy_stdout():
    stdout = 'some log line\nanother line\n{"new_history_rows": 42}\n'
    assert upload_service._parse_summary(stdout) == {"new_history_rows": 42}


def test_parse_summary_returns_empty_dict_when_no_json_line_is_present():
    assert upload_service._parse_summary("just plain log output\nno json here\n") == {}
