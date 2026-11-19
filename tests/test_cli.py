from declutter.cli import build_parser


def test_parser_has_commands():
    p = build_parser()
    assert p.parse_args(["scan", "--ai"]).command == "scan"
    assert p.parse_args(["report"]).command == "report"
    assert p.parse_args(["clean"]).apply is False  # dry run by default
