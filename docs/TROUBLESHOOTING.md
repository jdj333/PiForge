# Troubleshooting

| Symptom | Check and response |
| --- | --- |
| Host rejected | Run inside native aarch64 Linux, not the macOS shell or an x86 container. |
| Loop/mount permission denied | Use a dedicated Linux host with root or a privileged container in a Linux VM; check `/dev/loop-control`. |
| Git ownership error in a container | The builder trusts only its exact checkout and pinned cache paths. Check the failing path and preserve logs; do not add a global safe-directory wildcard. |
| Checksum mismatch | Stop. Remove only the corrupt cached download and retry the official URL; never bypass verification. |
| APT 404 / missing package | Save logs and indexes. Bookworm repositories are moving; investigate official repository changes before updating pins or package names. |
| Locked version unavailable / package drift | Do not drop the lock. Restore access to the exact version or deliberately bootstrap, review and commit a refreshed lock as described in BUILDING. |
| Unpinned Git repository | Review the upstream recipe and source license/origin, add an immutable lock, run tests and commit. Never fall back to master. |
| Source compilation fails | Read the per-module log under `dist/*/guest-logs/`; retain the work image. Do not silently skip the emulator or switch architectures. |
| Process killed / out of space | Increase host RAM/disk or lower `build_jobs`. Workspace needs at least 30 GiB available. Guest swap is deliberately disabled. |
| Firmware config rejected | Compare with the pinned official image. Conditional/include syntax beyond the supported validator requires review; do not overwrite config.txt with Pi 4 settings. |
| No systems in EmulationStation | The image contains no games. Supply legal content in the configured ROM directories. |
| Vulkan libraries pass but no GPU | Build tests check the loader/driver files; only hardware can validate V3DV. RetroArch's Vulkan renderer is disabled by upstream Pi flags. |
| First boot login unavailable | Use a physical keyboard/display and complete local password provisioning. Inspect the firstboot service via serial if it fails. |

## Failed build recovery

The EXIT/INT/TERM traps restore temporary guest DNS/service policy, unmount
tracked mounts in reverse order, and detach only the allocated loop device.
They do not force or lazily unmount busy filesystems. A failed unmount is
reported explicitly. SIGKILL and host power loss cannot run cleanup.

Before removing `build/run.*`, inspect `findmnt` and `losetup --list` on the
Linux build host. Match the loop backing file to the exact failed image. Stop
processes using that mount, unmount its children first, and detach that specific
loop. Do not run global `losetup -D`, recursive deletes through mounted guest
directories, or commands against an SD card/device to recover a build.

## What constitutes a pass

`scripts/validate.sh` passing means local static/unit checks passed.
`tests/image-mechanics.sh` passing means synthetic filesystem operations worked.
An image-build job passing means all configured components, image checks,
compression, metadata and checksums succeeded for that attempt. Only a report
from the physical hardware plan establishes tested Pi 5 behavior. Keep those
claims separate in bug reports and release notes.
