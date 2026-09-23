# Validation commands

Run repository commands from the PiForge checkout root. Start with the fast
checks; rebuild the image when build scripts, source pins, packages, or image
configuration change. Documentation-only changes do not require recompilation.
Do not edit an active build's checkout. See [BUILDING](BUILDING.md) for host
requirements and [HARDWARE_TESTING](HARDWARE_TESTING.md) for physical Pi tests.

## 1. Fast checks — no root or image build

Requires Python 3, Git, Bash, and ShellCheck. On Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3 git bash shellcheck
```

Run the same fast checks used by CI:

```bash
bash scripts/validate.sh
```

Expected: valid configuration/source/package locks, 23 passing unit tests,
successful ShellCheck and Bash syntax checks, and no whitespace errors.
These checks work on macOS with the required tools installed too.

For a narrower development loop:

```bash
python3 scripts/config.py validate
python3 scripts/packages.py validate
python3 -m unittest discover -s tests -p 'test_validation.py' -v
python3 -m unittest discover -s tests -p 'test_sources.py' -v
shellcheck -x scripts/*.sh tests/*.sh
git diff --check
```

The source adapter tests use local Git fixtures and need no network. They
verify exact pinned checkouts, source records, and rejection of missing caches
or unlocked repositories. If Actionlint is installed, validate workflows with:

```bash
actionlint
```

## 2. Filesystem integration — Linux, root, no full build

These tests create disposable synthetic image files. They do not flash disks.
Use a dedicated Linux VM/runner with loop devices and mount namespaces:

```bash
sudo apt-get install -y util-linux fdisk e2fsprogs dosfstools
sudo bash tests/image-mechanics.sh
sudo bash tests/prepare-image.sh
```

Expected: `PASS` for shrinking, filesystem integrity, payload/PARTUUID
preservation, expansion, mount setup, isolated `/run` and `/dev`, read-only
`/sys`, and temporary configuration backups.

Alternatively, use the repository's container on an ARM64 Linux Docker VM:

```bash
docker build -f configs/builder.Dockerfile -t piforge-builder:local .
docker run --rm --privileged \
  --mount type=bind,src="$PWD",dst=/workspace \
  --entrypoint bash piforge-builder:local -c '
    git config --global --add safe.directory /workspace &&
    bash scripts/validate.sh &&
    bash tests/image-mechanics.sh &&
    bash tests/prepare-image.sh
  '
```

The exact Git trust setting supports bind mounts with different ownership.
The container needs a dedicated VM and working loop-backed bind-mounted files.

## 3. Complete locked image — native ARM64 Linux

This is the slower end-to-end check. Commit changes first; the builder requires
a clean checkout. Cached downloads and Git objects are reused and verified.

```bash
bash scripts/validate.sh
sudo bash scripts/build-image.sh
```

Or, after building the container above:

```bash
docker run --rm --privileged \
  --mount type=bind,src="$PWD",dst=/workspace \
  piforge-builder:local
```

Do not set `PIFORGE_PACKAGE_BOOTSTRAP` for normal validation. Refreshing package
locks is a separate deliberate procedure described in [BUILDING](BUILDING.md).

Each emulator gets its own ARM64 ELF, linkage, and CLI/libretro API checks.
The full smoke test also checks the OS, complete package inventory, RetroPie,
EmulationStation, graphics libraries, SDL2 KMSDRM, Vulkan diagnostics, boot
configuration, account provisioning, and absence of ROM/BIOS content. Success
ends with `Image artifacts ready:` and a unique output directory under `dist/`.
Guest installation/smoke scripts are internal build phases; do not run them
directly on the host to save time.

## 4. Verify an existing artifact — no rebuild

Use the exact output directory printed by the successful build, not an older
or partial attempt. Replace the example path below:

```bash
cd dist/BUILD_DIRECTORY
xz --test piforge-pi5-bookworm-arm64.img.xz
sha256sum --check piforge-pi5-bookworm-arm64.sha256
# On macOS, use this checksum command instead:
# shasum -a 256 -c piforge-pi5-bookworm-arm64.sha256
python3 - <<'PY'
import json
from pathlib import Path
info = json.loads(Path('piforge-pi5-bookworm-arm64.build-info.json').read_text())
assert info['validation']['build_time'] == 'passed'
assert info['reproducibility']['package_versions_locked'] is True
assert info['reproducibility']['base_and_git_sources_pinned'] is True
print('PiForge commit:', info['piforge_commit'])
print('Built:', info['build_date'])
print('Packages:', len(info['packages']))
print('Hardware validation:', info['validation']['physical_pi5'])
PY
```

Expected: XZ exits zero, both checksum entries report `OK`, and metadata
assertions pass. Checksums detect corruption; they do not establish hardware
compatibility or the authenticity of an independently obtained checksum file.

## 5. Inspect a failed build quickly

From the checkout root, replace `BUILD_DIRECTORY` with the failed attempt:

```bash
tail -n 80 dist/BUILD_DIRECTORY/build.log
rg -n 'Failed|ERROR|Traceback|PASS|\[PiForge\]' dist/BUILD_DIRECTORY/build.log
ls dist/BUILD_DIRECTORY/guest-logs
```

Per-module logs identify the failing component. Fix and commit the cause, then
start a fresh build. Do not bypass failed checks, resume guest phases manually,
or delete work directories until their mounts and loop devices are detached.

## 6. GitHub and physical hardware

Pushes to `main` and pull requests run the **Validate** workflow. Check that
run's result for the exact pushed commit. To exercise the hosted image builder,
select **Actions → Build experimental Pi 5 image → Run workflow**. Download
both `piforge-image-*` and `piforge-logs-*`, then run the artifact checks above.
The image workflow is manual and does not publish a release.

Physical boot, root expansion, password provisioning, accelerated graphics,
audio, controllers, and gameplay require the separate
[Pi 5 hardware checklist](HARDWARE_TESTING.md). A chroot success cannot replace it.

## Recorded local result

The normal locked build at `629ead69c048585643ca9c035809687d38085b65`
completed on 2026-09-21 UTC in a native ARM64 Linux Docker VM. All requested
components and full image checks passed with 962 exact package versions.
Linux lint/unit and both filesystem integration tests passed; Actionlint passed.
The completed XZ stream and both SHA256 entries were independently verified.
GitHub's [Validate run for that commit](https://github.com/jdj333/PiForge/actions/runs/35770264276)
also completed successfully.

Artifact directory:
`dist/piforge-pi5-bookworm-arm64-0.1.0-dev-629ead69c048-20260921T053227Z/`

Image size: 1,061,052,732 bytes. Image SHA256:

```text
8d5cae4a230e17b42d8ec9370e3eba0d6dfff1c05503d8a3ba29379842e46eb1
```

Artifacts are local ignored build outputs, not files committed to Git. This
result does not claim a successful GitHub-hosted image build or physical Pi 5
validation. Package archive retention and bit-identical output remain outside
the current reproducibility guarantee.
