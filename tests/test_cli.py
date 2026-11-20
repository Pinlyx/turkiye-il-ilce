import json

from turkiye_il_ilce.cli import main


def test_cli_text(capsys):
    assert main(["40.99", "29.03"]) == 0
    out = capsys.readouterr().out
    assert "Kad" in out and "34" in out and "TR-34" in out


def test_cli_json(capsys):
    assert main(["40.99", "29.03", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {"il": "İstanbul", "plaka": 34, "iso": "TR-34", "ilce": "Kadıköy"}


def test_cli_not_found(capsys):
    assert main(["40.70", "28.00"]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_invalid(capsys):
    assert main(["95", "28"]) == 2
