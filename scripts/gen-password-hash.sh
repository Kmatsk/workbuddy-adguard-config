#!/usr/bin/env bash
# 生成 bcrypt 哈希，用于 config/AdGuardHome.yaml 的 password 字段。
#
# 用法:
#   bash scripts/gen-password-hash.sh '你的密码'
#
# 把输出整行替换到 yaml 里：
#     password: $2a$10$xxxxxxxx...

set -euo pipefail

PW=${1:-}
if [ -z "$PW" ]; then
  echo "用法: $0 '密码'" >&2
  exit 1
fi

if command -v htpasswd >/dev/null 2>&1; then
  HASH=$(htpasswd -nbBC 10 "" "$PW" | tr -d ':\n')
elif command -v docker >/dev/null 2>&1; then
  HASH=$(docker run --rm httpd:alpine htpasswd -nbBC 10 "" "$PW" | tr -d ':\n')
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import bcrypt' 2>/dev/null; then
  HASH=$(python3 -c 'import bcrypt,sys;print(bcrypt.hashpw(sys.argv[1].encode(),bcrypt.gensalt(10)).decode())' "$PW")
else
  echo "需要 htpasswd / docker / python3+bcrypt 三者之一" >&2
  exit 1
fi

# htpasswd 出的是 \$2y\$，AdGuard 两种都认，统一成 \$2a\$ 更通用
echo "${HASH/\$2y\$/\$2a\$}"
