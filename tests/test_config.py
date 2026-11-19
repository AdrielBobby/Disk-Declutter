import os

from declutter import config


def test_windows_dir_is_protected():
    assert config.is_protected(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "x.dll"))


def test_user_profile_root_is_protected():
    assert config.is_protected(config.HOME)


def test_random_downloads_file_is_not_protected():
    assert not config.is_protected(config.HOME / "Downloads" / "old-installer.exe")
