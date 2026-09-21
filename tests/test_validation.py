import copy
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from config import load, validate
from boot_config import validate_boot
from smoke import check_content, check_elf, check_component
from packages import compare_packages, validate_lock, input_digest

spec = importlib.util.spec_from_file_location("layout", ROOT / "scripts/image-layout.py")
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config, self.lock = load()

    def test_default_configuration(self):
        validate(self.config, self.lock)
        self.assertEqual(len(self.config["emulators"]), 8)

    def test_reject_moving_commits(self):
        for key in ("retropie_commit", "base_image_sha256"):
            with self.subTest(key=key):
                config = {**self.config, key: "master"}
                with self.assertRaises(ValueError):
                    validate(config, self.lock)

    def test_reject_shell_injection_and_path_traversal(self):
        for name in ("../../dev/sda", "x;touch /tmp/unsafe", "$(whoami)", "a\nb", "-oops"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate({**self.config, "output_image_name": name}, self.lock)

    def test_reject_nonofficial_download(self):
        with self.assertRaises(ValueError):
            validate({**self.config, "base_image_url": self.config["base_image_url"].replace(
                "downloads.raspberrypi.com", "example.org")}, self.lock)

    def test_reject_missing_emulator_lock(self):
        del self.lock["sources"]["lr-mgba"]
        with self.assertRaises(ValueError):
            validate(self.config, self.lock)

    def test_reject_moving_child_source(self):
        self.lock["sources"]["lr-mgba"]["commit"] = "master"
        with self.assertRaises(ValueError):
            validate(self.config, self.lock)

    def test_reject_invalid_sizes_and_duplicates(self):
        for change in ({"image_size_gib": 0}, {"build_jobs": True}, {"shrink_headroom_mib": 0},
                       {"emulators": ["retroarch", "lr-mgba", "lr-mgba"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**self.config, **change}, self.lock)


class PackageLockTests(unittest.TestCase):
    def test_accept_matching_inventory(self):
        compare_packages({"libsdl2-2.0-0:arm64": "2.26.5+dfsg-1"},
                         {"libsdl2-2.0-0:arm64": "2.26.5+dfsg-1"})

    def test_reject_added_removed_and_changed_packages(self):
        for actual in ({}, {"a": "2"}, {"a": "1", "b": "1"}):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                compare_packages({"a": "1"}, actual)

    def test_lock_is_tied_to_recipe_inputs(self):
        lock = {"schema_version": 1, "inputs_sha256": input_digest(), "packages": {"libc6:arm64": "2.36-1"}}
        validate_lock(lock)
        lock["inputs_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_lock(lock)

    def test_reject_malformed_package_arguments(self):
        for package in ("--allow-unauthenticated", "foo=bar", "x;command", "libc6:amd64"):
            with self.subTest(package=package), self.assertRaises(ValueError):
                validate_lock({"schema_version": 1, "inputs_sha256": input_digest(), "packages": {package: "1"}})


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.table = {"partitiontable": {"label": "dos", "sectorsize": 512, "partitions": [
            {"start": 8192, "size": 1048576, "type": "c"},
            {"start": 1056768, "size": 4000000, "type": "83"}]}}

    def test_valid(self):
        self.assertEqual(layout.inspect(self.table), 1056768)

    def test_reject_gpt_extra_partitions_and_overlap(self):
        changes = [lambda t: t.update(label="gpt"), lambda t: t.update(sectorsize=4096),
                   lambda t: t["partitions"].append(t["partitions"][1]),
                   lambda t: t["partitions"][1].update(start=8192),
                   lambda t: t["partitions"][1].update(type="7")]
        for change in changes:
            table = copy.deepcopy(self.table)
            change(table["partitiontable"])
            with self.assertRaises(ValueError):
                layout.inspect(table)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boot = self.root / "boot/firmware"
        self.boot.mkdir(parents=True)
        self.good = "[all]\narm_64bit=1\ndtoverlay=vc4-kms-v3d\n[pi4]\narm_64bit=0\n[all]\n"
        (self.boot / "config.txt").write_text(self.good)
        (self.boot / "cmdline.txt").write_text("console=tty1 root=PARTUUID=12345678-02 rootwait\n")

    def test_boot_configuration(self):
        validate_boot(self.boot)

    def test_reject_wrong_target_kms(self):
        (self.boot / "config.txt").write_text("arm_64bit=1\n[pi4]\ndtoverlay=vc4-kms-v3d\n")
        with self.assertRaises(ValueError):
            validate_boot(self.boot)

    def test_reject_fkms_and_duplicate_overlay(self):
        for extra in ("dtoverlay=vc4-fkms-v3d\n", "dtoverlay=vc4-kms-v3d\n", "bad syntax\n"):
            (self.boot / "config.txt").write_text(self.good + extra)
            with self.assertRaises(ValueError):
                validate_boot(self.boot)

    def test_include_and_cycle(self):
        (self.boot / "config.txt").write_text("include extra.txt\n")
        (self.boot / "extra.txt").write_text(self.good)
        validate_boot(self.boot)
        (self.boot / "extra.txt").write_text("include config.txt\n")
        with self.assertRaises(ValueError):
            validate_boot(self.boot)

    def test_reject_multiline_command_line(self):
        with (self.boot / "cmdline.txt").open("a") as file:
            file.write("extra=1\n")
        with self.assertRaises(ValueError):
            validate_boot(self.boot)

    def test_content_allowlist_rejects_game_and_symlink(self):
        base = self.root / "home/pi/RetroPie"
        (base / "roms/nes").mkdir(parents=True)
        (base / "BIOS/palettes").mkdir(parents=True)
        palette = self.root / "original.pal"
        palette.write_text("[General]\nBackground0=0\n")
        (base / "BIOS/palettes/default.pal").write_bytes(palette.read_bytes())
        (base / "roms/megadrive").mkdir()
        alias = base / "roms/genesis"
        alias.symlink_to("megadrive")
        check_content(self.root, palette)
        alias.unlink()
        alias.symlink_to("nes")
        with self.assertRaises(ValueError):
            check_content(self.root, palette)
        alias.unlink()
        alias.symlink_to("megadrive")
        sega_game = base / "roms/megadrive/game.bin"
        sega_game.write_text("test fixture, not a ROM")
        with self.assertRaises(ValueError):
            check_content(self.root, palette)
        sega_game.unlink()
        game = base / "roms/nes/game.nes"
        game.write_text("test fixture, not a ROM")
        with self.assertRaises(ValueError):
            check_content(self.root, palette)
        game.unlink()
        game.symlink_to(palette)
        with self.assertRaises(ValueError):
            check_content(self.root, palette)

    def test_elf_wrong_arch_and_missing_core(self):
        binary = self.root / "example.so"
        header = bytearray(20)
        header[:6] = b"\x7fELF\x02\x01"
        header[18:20] = struct.pack("<H", 183)
        binary.write_bytes(header)
        check_elf(binary)
        header[18:20] = struct.pack("<H", 62)
        binary.write_bytes(header)
        with self.assertRaises(ValueError):
            check_elf(binary)
        with self.assertRaises(ValueError):
            check_component("lr-mgba", self.root, execute=False)


if __name__ == "__main__":
    unittest.main()
