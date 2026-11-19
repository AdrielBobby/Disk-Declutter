from declutter.cli import build_parser


def test_parser_has_commands():
    p = build_parser()
    assert p.parse_args(["scan", "--ai"]).command == "scan"
    assert p.parse_args(["report"]).command == "report"
    assert p.parse_args(["clean"]).apply is False  # dry run by default


def test_go_command_accepts_scan_options():
    a = build_parser().parse_args(["go", "--ai", "--stale-days", "60", "--skip", "apps"])
    assert a.command == "go" and a.ai and a.stale_days == 60 and a.skip == ["apps"]
