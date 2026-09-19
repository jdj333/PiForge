# Optional local ARM64 Linux container; the guest OS comes from the locked image.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git python3 xz-utils util-linux fdisk e2fsprogs \
    dosfstools shellcheck procps && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
CMD ["bash", "scripts/build-image.sh"]
