"""
Regression coverage for the Boson SDK search path.

The SDK used to be searched for at
thermal_inspection/sdk/3.0 IDD & SDK/SDK_USER_PERMISSIONS/SDK_USER_PERMISSIONS/
— three directories deep inside the Python package itself, with a repeated
folder name, and no indication anywhere obvious that this is where a
proprietary third-party drop-in belongs. Moved to a top-level boson_sdk/
folder (see boson_sdk/README.md) with flexible depth handling, since FLIR's
own SDK zip layout has shipped both a flat SDK_USER_PERMISSIONS/
ClientFiles_Python and a double-nested SDK_USER_PERMISSIONS/
SDK_USER_PERMISSIONS/ClientFiles_Python across releases.

_find_sdk_base's own first cut had a bug caught here: it accepted a directory
as soon as *any* subfolder happened to be named SDK_USER_PERMISSIONS, without
checking that ClientFiles_Python was actually inside it — which is exactly
true of the *outer* wrapper in the double-nested layout, so it returned one
level too shallow for that case.
"""
import os

from thermal_inspection.sdk.boson_sdk_wrapper import _find_sdk_base


def _make_sdk_layout(tmp_path, *nested_levels):
    """Build tmp_path/boson_sdk/SDK_USER_PERMISSIONS/[.../]ClientFiles_Python."""
    root = tmp_path / "boson_sdk"
    current = root
    for _ in range(nested_levels[0] if nested_levels else 1):
        current = current / "SDK_USER_PERMISSIONS"
    (current / "ClientFiles_Python").mkdir(parents=True)
    (current / "ClientFiles_Python" / "Client_API.py").write_text("# stub")
    return str(root)


class TestFindSdkBase:

    def test_finds_flat_layout(self, tmp_path):
        root = _make_sdk_layout(tmp_path, 1)
        assert _find_sdk_base(root) == root

    def test_finds_double_nested_layout(self, tmp_path):
        root = _make_sdk_layout(tmp_path, 2)
        assert _find_sdk_base(root) == os.path.join(root, "SDK_USER_PERMISSIONS")

    def test_an_sdk_user_permissions_folder_alone_is_not_sufficient(self, tmp_path):
        # Regression: the first version of this function accepted a
        # directory as soon as an SDK_USER_PERMISSIONS-named subfolder
        # existed, without checking ClientFiles_Python was inside it — which
        # is exactly the shape of the *outer* wrapper in a double-nested
        # layout, so it stopped one level too early.
        root = tmp_path / "boson_sdk"
        (root / "SDK_USER_PERMISSIONS" / "SDK_USER_PERMISSIONS" / "ClientFiles_Python").mkdir(parents=True)

        found = _find_sdk_base(str(root))

        assert found == str(root / "SDK_USER_PERMISSIONS")
        assert found != str(root)

    def test_missing_directory_returns_none(self, tmp_path):
        assert _find_sdk_base(str(tmp_path / "does_not_exist")) is None

    def test_directory_with_no_sdk_returns_none(self, tmp_path):
        empty = tmp_path / "boson_sdk"
        empty.mkdir()
        assert _find_sdk_base(str(empty)) is None

    def test_checks_multiple_roots_in_order(self, tmp_path):
        # First (primary) root has nothing; second (legacy) root has the SDK.
        primary = tmp_path / "boson_sdk"
        primary.mkdir()
        legacy_root = _make_sdk_layout(tmp_path, 1)

        assert _find_sdk_base(str(primary), legacy_root) == legacy_root

    def test_primary_root_wins_when_both_present(self, tmp_path):
        (tmp_path / "primary" / "boson_sdk" / "SDK_USER_PERMISSIONS" / "ClientFiles_Python").mkdir(parents=True)
        (tmp_path / "legacy" / "boson_sdk" / "SDK_USER_PERMISSIONS" / "ClientFiles_Python").mkdir(parents=True)
        primary = str(tmp_path / "primary" / "boson_sdk")
        legacy = str(tmp_path / "legacy" / "boson_sdk")

        assert _find_sdk_base(primary, legacy) == primary
