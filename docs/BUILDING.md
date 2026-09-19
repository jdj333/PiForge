# Building an image

## Host requirements

The initial path is native ARM64 Linux, with root, loop devices, private mount
namespaces, ext4 tools, and outbound HTTPS. It intentionally rejects x86 and
macOS hosts. QEMU user emulation can be added later, but needs its own tests.
Use a dedicated VM/runner: chroot is not a security boundary, and source builds
and distribution maintainer scripts execute with guest root privileges.

Install the packages shown in the README. Provision at least 30 GiB free disk,
4 GiB RAM, and adequate cooling for a physical builder. Source compilation may
take hours. `build_jobs` defaults to 2 to limit memory use. Additional host
swap is an operator decision; the build adapter never activates guest swap.

## Configuration and source review

`configs/build.json` holds the base image URL/SHA256/version, RetroPie commit,
OS, emulator list, output name, build version, image size, shrink headroom,
parallelism, and Vulkan diagnostic setting. `configs/sources.lock.json` pins
the emulator and supporting Git repositories. Branch names document where
the pin was selected; the builder fetches only the immutable commit. Recursive
submodules are checked out at the parent commit and recorded in provenance.

After changing a pin, review upstream module recipes and their dependencies,
run validation, then commit. An unrecognized Git URL fails the build rather
than fetching a branch tip. Upstream scripts may change their download methods;
re-review this boundary when updating RetroPie. PiForge does not claim that a
source lock is a security audit of every transitive source line.

Distribution packages use the official authenticated APT repositories from
the base image. `configs/packages.lock.json` locks the complete installed package
inventory and is tied to the base/source/emulator configuration. Exact versions
are installed before building, temporary APT preferences prevent drift, and the
final smoke test compares the entire inventory. Missing versions fail rather
than silently upgrading. Preferences are removed from the finished image so
normal security updates remain possible after deployment.

For durable historical rebuilds, an immutable archive of both Debian and
Raspberry Pi packages is still needed. Version locks guarantee input selection
when packages are available; they do not guarantee future repository retention
or byte-identical disk images.

To deliberately refresh the package lock after reviewing new inputs, commit
the configuration and run a local bootstrap build:

```bash
sudo env PIFORGE_PACKAGE_BOOTSTRAP=1 bash scripts/build-image.sh
python3 scripts/packages.py from-metadata dist/BUILD/IMAGE.build-info.json
bash scripts/validate.sh
# Review/commit the generated lock, then run a normal locked build.
```

The bootstrap flag is passed explicitly into the guest and recorded in metadata
as `package_versions_locked: false`. It is not exposed by the image workflow.
Only metadata reporting successful build-time checks with matching source
configuration can generate the lock. A bootstrap is not a release candidate.

## Run

```bash
bash scripts/validate.sh
sudo bash tests/image-mechanics.sh  # disposable synthetic image, Linux only
sudo bash scripts/build-image.sh
```

The builder requires a clean Git checkout so its commit identifies its inputs.
It serializes builds within the checkout using `flock`. Work lives in
`build/run.*`; the verified compressed base is cached under `build/cache/`.
Each attempt has a unique directory under `dist/` containing its logs. Success
adds the compressed image, metadata JSON, and checksum file. Failed/partial
images are never uploaded by the success-only artifact step.

Pinned Git objects are cached under `build/cache/git/` and exposed read-only
to the guest. The host fetches only reviewed URLs/commits and runs no emulator
build code. Cached repositories pass a full Git object integrity check; checkout and
linkage checks still run on every image build. Submodules use the parent
commit's recorded revisions. Delete a damaged source cache and rebuild rather
than changing a lock to bypass an integrity failure.

The `install-*`, `configure-pi5`, smoke and finalize scripts require a marker
inside the private guest `/run`; do not execute them against the host. Do not
run failed phases manually against a production filesystem. Start a fresh
build after fixing an error. Download caches are verified on every reuse.

## Optional local container

On a native ARM64 Linux host, or an ARM64 Linux VM backing Docker:

```bash
docker build -f configs/builder.Dockerfile -t piforge-builder:local .
docker run --rm --privileged \
  --mount type=bind,src="$PWD",dst=/workspace \
  piforge-builder:local
```

The privileged container needs loop devices and mount namespaces. It does not
make an unsafe host suitable: use a dedicated VM, and ensure the bind-mounted
workspace supports loop-backed files. The host-tools container tag is not a
reproducibility pin; metadata's package list describes the image userspace.

## Disk mechanics and shutdown

Only a newly decompressed regular file is modified. The builder validates the
DOS partition table, FAT boot partition, ext4 root partition and 512-byte sectors.
It preserves the disk identifier/PARTUUIDs, extends root, then mounts boot at
`/boot/firmware`. Private `/run` and `/dev` avoid host service sockets/disks;
`policy-rc.d` prevents service starts; `/sys` is read-only. DNS and preexisting
service policy are restored before finalization and on failure.

After cleaning and recording metadata, filesystems are unmounted in reverse
order. ext4 is checked, minimized, then expanded by configured headroom before
the root partition and disk file are truncated. The official first-boot disk
expansion mechanism is retained. No third-party shrinking script is downloaded.
`e2fsck` status 1 (errors corrected) is accepted; serious errors stop the build.
Signals trigger cleanup; SIGKILL/power loss cannot run a trap. Inspect loop
devices and mounts before deleting an interrupted work directory.

## CI and release boundaries

PR validation runs shell lint, configuration/unit/static checks, and privileged
synthetic filesystem tests. The manually dispatched image workflow runs all
configured components and uploads image/checksum/metadata on success, with logs
on success or failure. It has no release token, publishing step, or automatic
deployment. A future release job should consume these verified artifacts only
after package reproducibility and hardware acceptance have been established.
