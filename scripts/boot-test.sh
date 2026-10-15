#!/usr/bin/env bash
# Acceptance test FR-002: boot a Debian cloud image with a generated seed drive and check
# that cloud-init applied the configuration.
#
# Requires: a running app (APP_URL), qemu-system-x86_64 with KVM, ssh-keygen, curl, python3.
# QEMU runs via sudo unless the user may access /dev/kvm.
#
#   scripts/boot-test.sh [iso|raw|qcow2 ...]      (default: all three formats)
#
# Environment: APP_URL (default http://127.0.0.1:8000), DEBIAN_IMAGE (path to a Debian 13
# genericcloud qcow2; downloaded to WORKDIR if unset), WORKDIR, BOOT_TIMEOUT (seconds).
set -euo pipefail

APP_URL="${APP_URL:-http://127.0.0.1:8000}"
WORKDIR="${WORKDIR:-${TMPDIR:-/tmp}/cnc-boot-test}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-240}"
FORMATS=("${@:-iso raw qcow2}")
read -r -a FORMATS <<<"${FORMATS[*]}"
IMAGE_URL="https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2"

mkdir -p "$WORKDIR"
cd "$WORKDIR"

DEBIAN_IMAGE="${DEBIAN_IMAGE:-$WORKDIR/debian-13-genericcloud-amd64.qcow2}"
if [ ! -f "$DEBIAN_IMAGE" ]; then
  echo "==> Downloading $IMAGE_URL"
  curl -sSfL -o "$DEBIAN_IMAGE" "$IMAGE_URL"
fi

QEMU=(qemu-system-x86_64)
[ -r /dev/kvm ] && [ -w /dev/kvm ] || QEMU=(sudo -n qemu-system-x86_64)
# Debian 13 cloud images boot via UEFI (package ovmf).
OVMF_CODE="${OVMF_CODE:-/usr/share/OVMF/OVMF_CODE_4M.fd}"
OVMF_VARS="${OVMF_VARS:-/usr/share/OVMF/OVMF_VARS_4M.fd}"
[ -f "$OVMF_CODE" ] || { echo "FAIL: UEFI firmware not found ($OVMF_CODE); install ovmf"; exit 1; }

rm -f test_key test_key.pub
ssh-keygen -q -t ed25519 -N "" -C boot-test -f test_key
SSH_KEY="$(cat test_key.pub)"

echo "==> Creating the configuration via the API"
BODY="$(SSH_KEY="$SSH_KEY" python3 - <<'EOF'
import json, os
print(json.dumps({
    "name": "Boot test",
    "basics": {"hostname": "cnc-boot", "fqdn": "cnc-boot.example.test", "timezone": "Europe/Berlin"},
    "network": {"ethernets": [{"name": "lan0", "match_mac": "52:54:00:12:34:56", "dhcp4": True}]},
    "users": {
        "users": [{
            "name": "tester", "gecos": "Boot Tester", "admin": True,
            "sudo": "ALL=(ALL) NOPASSWD:ALL", "password": "tester-pw", "lock_passwd": False,
            "groups": ["devs"], "ssh_authorized_keys": [os.environ["SSH_KEY"]],
        }],
        "groups": [{"name": "devs"}],
    },
    "ssh": {"authorized_keys": [os.environ["SSH_KEY"]]},
    "write_files": [
        {"path": "/etc/cnc-test.txt", "content": "written by cloud-init\n", "owner": "tester:tester",
         "permissions": "0640", "defer": True},
    ],
    "commands": {
        "bootcmd": ["echo CNC-BOOTCMD > /dev/ttyS0"],
        "runcmd": [
            "sleep 2",
            "echo \"CNC-RESULT hostname=$(hostname) fqdn=$(hostname -f) tz=$(date +%Z) "
            "groups=$(id -nG tester | tr ' ' ',') file=$(stat -c %U:%a /etc/cnc-test.txt) "
            "content=$(head -c 9 /etc/cnc-test.txt) nic=$(ls /sys/class/net | tr '\\n' ',') "
            "mount=$(findmnt -n -o FSTYPE,LABEL /srv/data | tr ' ' ',') "
            "shadow=$(sudo grep -c '^tester:\\$6\\$' /etc/shadow) "
            "pwauth=$(sshd -T 2>/dev/null | grep -i '^passwordauthentication' | cut -d' ' -f2) "
            "cloudinit_warnings=$(grep -c -E 'WARNING|Traceback' /var/log/cloud-init.log)\" > /dev/ttyS0",
            "grep -E 'WARNING|Traceback' /var/log/cloud-init.log | sed 's/^/CNC-WARN /' > /dev/ttyS0 || true",
            "cloud-init schema --system 2>&1 | grep -E '^ *(Error|[a-z_]+\\.|- )' | sed 's/^/CNC-SCHEMA /' > /dev/ttyS0 || true",
        ],
    },
    "disks": [{
        "device": "/dev/disk/by-id/virtio-cncdata",
        "partitions": [{"size_percent": 100, "filesystem": "ext4", "label": "data", "mount_point": "/srv/data"}],
    }],
}))
EOF
)"
CONFIG_ID="$(curl -sSf -X POST "$APP_URL/api/configurations" -H 'content-type: application/json' -d "$BODY" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
trap 'curl -s -X DELETE "$APP_URL/api/configurations/$CONFIG_ID" >/dev/null' EXIT

EXPECTED=(
  "hostname=cnc-boot"
  "fqdn=cnc-boot.example.test"
  "tz=CE"                       # CET or CEST
  "groups=tester,"
  ",sudo"
  ",devs"
  "file=tester:640"
  "content=written b"
  "nic=lan0,lo,"
  "mount=ext4,data"
  "shadow=1"
  "pwauth=no"
)

failed=0
for format in "${FORMATS[@]}"; do
  echo "==> [$format] Downloading the seed image"
  seed="seed-$format"
  curl -sSf -o "$seed" "$APP_URL/api/configurations/$CONFIG_ID/image?format=$format"

  rm -f root.qcow2 data.qcow2 console.log efivars.fd
  cp "$OVMF_VARS" efivars.fd
  qemu-img create -q -f qcow2 -F qcow2 -b "$DEBIAN_IMAGE" root.qcow2 6G
  qemu-img create -q -f qcow2 data.qcow2 1G
  case "$format" in
    iso) seed_drive=(-drive "file=$seed,media=cdrom,readonly=on") ;;
    raw) seed_drive=(-drive "file=$seed,if=virtio,format=raw,readonly=on") ;;
    qcow2) seed_drive=(-drive "file=$seed,if=virtio,format=qcow2,readonly=on") ;;
  esac

  echo "==> [$format] Booting Debian (timeout ${BOOT_TIMEOUT}s)"
  "${QEMU[@]}" -enable-kvm -cpu host -m 1024 -smp 2 -nographic -no-reboot \
    -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
    -drive if=pflash,format=raw,file=efivars.fd \
    -drive file=root.qcow2,if=virtio,format=qcow2 \
    "${seed_drive[@]}" \
    -drive file=data.qcow2,if=none,id=data,format=qcow2 -device virtio-blk-pci,drive=data,serial=cncdata \
    -netdev user,id=net0 -device virtio-net-pci,netdev=net0,mac=52:54:00:12:34:56 \
    -serial file:console.log -monitor none -display none &
  qemu_pid=$!

  result=""
  for _ in $(seq 1 "$BOOT_TIMEOUT"); do
    if result="$(grep -a -m1 'CNC-RESULT' console.log 2>/dev/null)"; then break; fi
    sleep 1
  done
  sudo -n kill "$qemu_pid" 2>/dev/null || kill "$qemu_pid" 2>/dev/null || true
  wait "$qemu_pid" 2>/dev/null || true

  if [ -z "$result" ]; then
    echo "FAIL [$format]: no result within ${BOOT_TIMEOUT}s; last console lines:"
    tail -n 20 console.log | tr -d '\r'
    failed=1
    continue
  fi
  echo "    ${result//$'\r'/}"
  grep -aq 'CNC-BOOTCMD' console.log || { echo "FAIL [$format]: bootcmd did not run"; failed=1; }
  for expected in "${EXPECTED[@]}"; do
    case "$result" in
      *"$expected"*) ;;
      *) echo "FAIL [$format]: expected '$expected'"; failed=1 ;;
    esac
  done
  grep -a -E 'CNC-(WARN|SCHEMA)' console.log | tr -d '\r' | sed 's/^/    /' || true
  [ "$failed" = 0 ] && echo "ok [$format]"
done

[ "$failed" = 0 ] && echo "All boot tests passed." || { echo "Boot tests FAILED."; exit 1; }
