"""Exercise the real source adapter with a local Git fixture and no network."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "configs", self.root / "configs")
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        self.env = {**os.environ, "PIFORGE_ROOT": str(self.root),
                    "PIFORGE_GIT_CACHE": str(self.root / "cache"),
                    "PIFORGE_LOG_DIR": str(self.root / "logs"),
                    "GIT_CONFIG_GLOBAL": str(self.root / "gitconfig"),
                    "GIT_CONFIG_NOSYSTEM": "1", "DEST": str(self.root / "checkout")}
        (self.root / "logs").mkdir()
        repo = self.root / "original"
        self.run_git("init", "-q", str(repo))
        (repo / "payload.txt").write_text("source fixture\n")
        self.run_git("-C", str(repo), "add", "payload.txt")
        self.run_git("-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                     "commit", "-qm", "fixture")
        self.commit = self.run_git("-C", str(repo), "rev-parse", "HEAD").strip()
        cache = self.root / "cache" / (self.commit + ".git")
        cache.parent.mkdir()
        self.run_git("clone", "-q", "--bare", str(repo), str(cache))
        lock_path = self.root / "configs/sources.lock.json"
        lock = json.loads(lock_path.read_text())
        lock["sources"]["lr-gambatte"]["commit"] = self.commit
        lock_path.write_text(json.dumps(lock))

    def run_git(self, *arguments):
        return subprocess.check_output(["git", *arguments], env=self.env, text=True, stderr=subprocess.PIPE)

    def invoke(self, url):
        return subprocess.run(["bash", "-c", 'declare -A __mod_info=(); md_id=lr-gambatte; '
                               'source "$PIFORGE_ROOT/scripts/locked-sources.sh"; '
                               'gitPullOrClone "$DEST" "$REPO"'],
                              env={**self.env, "REPO": url}, text=True, capture_output=True)

    def test_fetches_exact_cached_commit_and_records_it(self):
        result = self.invoke("https://github.com/libretro/gambatte-libretro.git")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "checkout/payload.txt").read_text(), "source fixture\n")
        self.assertEqual(self.run_git("-C", str(self.root / "checkout"), "rev-parse", "HEAD").strip(), self.commit)
        record = json.loads((self.root / "logs/sources.jsonl").read_text())
        self.assertEqual(record["commit"], self.commit)

    def test_rejects_unlocked_repository_before_checkout(self):
        result = self.invoke("https://github.com/unreviewed/repo.git")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unpinned Git repository", result.stderr)
        self.assertFalse((self.root / "checkout").exists())

    def test_missing_cache_does_not_fall_back_to_network(self):
        shutil.rmtree(self.root / "cache")
        result = self.invoke("https://github.com/libretro/gambatte-libretro.git")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing pinned source cache", result.stderr)


if __name__ == "__main__":
    unittest.main()
