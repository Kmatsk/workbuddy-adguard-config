#!/usr/bin/env bash
# 在 NAS 上运行：用本仓库的配置覆盖当前 AdGuard 配置，并重启容器。
# 会自动备份现有配置，失败可回滚。
#
# 用法:
#   sudo bash scripts/restore-adguard.sh
#
# 可选环境变量:
#   AG_CONF  配置文件路径，默认 /vol1/1000/docker/AdGuard/conf/AdGuardHome.yaml
#   AG_NAME  容器名，默认 adguardhome

set -euo pipefail

AG_CONF=${AG_CONF:-/vol1/1000/docker/AdGuard/conf/AdGuardHome.yaml}
AG_NAME=${AG_NAME:-adguardhome}
REPO=$(cd "$(dirname "$0")/.." && pwd)
SRC="$REPO/config/AdGuardHome.yaml"

[ -f "$SRC" ] || { echo "找不到 $SRC" >&2; exit 1; }

if grep -q 'REPLACE_ME_RUN_scripts' "$SRC"; then
  cat >&2 <<'EOF'
!! 配置里的 password 还是占位符，直接恢复会导致无法登录。

先执行：
    bash scripts/gen-password-hash.sh '你要设的密码'

把输出的哈希替换 config/AdGuardHome.yaml 里这一行：
        password: $2a$10$REPLACE_ME_RUN_scripts/gen-password-hash.sh

然后再跑本脚本。
EOF
  exit 1
fi

TS=$(date +%Y%m%d-%H%M%S)
BACKUP="$AG_CONF.bak.$TS"

echo "==> 备份现有配置 -> $BACKUP"
sudo cp -a "$AG_CONF" "$BACKUP"

echo "==> 写入新配置"
sudo install -m 600 -o root -g root "$SRC" "$AG_CONF"

echo "==> 重启容器 $AG_NAME"
sudo docker restart "$AG_NAME" >/dev/null

echo "==> 等待服务就绪"
for i in $(seq 1 30); do
  if curl -sf -o /dev/null "http://127.0.0.1:3000/" 2>/dev/null; then
    echo "    已就绪 (${i}s)"
    break
  fi
  [ "$i" -eq 30 ] && { echo "!! 30s 内未就绪，回滚" >&2; sudo cp -a "$BACKUP" "$AG_CONF"; sudo docker restart "$AG_NAME" >/dev/null; exit 1; }
  sleep 1
done

cat <<EOF

完成。如果登录不了，回滚：
    sudo cp -a "$BACKUP" "$AG_CONF" && sudo docker restart "$AG_NAME"

注意：过滤列表需要重新下载（首次会花几十秒），期间解析会略慢。
EOF
