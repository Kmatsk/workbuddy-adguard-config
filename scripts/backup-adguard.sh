#!/usr/bin/env bash
# 在 NAS 上运行：把当前 AdGuard 配置抓取并脱敏后写回本仓库。
#
# 用法:
#   AG_USER=Kmatsk AG_PASS='你的面板密码' bash scripts/backup-adguard.sh
#
# 可选环境变量:
#   AG_API  面板地址，默认 http://127.0.0.1:3000
#   AG_CONF 配置文件路径，默认 /vol1/1000/docker/AdGuard/conf/AdGuardHome.yaml

set -euo pipefail

AG_API=${AG_API:-http://127.0.0.1:3000}
AG_CONF=${AG_CONF:-/vol1/1000/docker/AdGuard/conf/AdGuardHome.yaml}
: "${AG_USER:?请设置 AG_USER}"
: "${AG_PASS:?请设置 AG_PASS}"

REPO=$(cd "$(dirname "$0")/.." && pwd)
COOKIE=$(mktemp)
trap 'rm -f "$COOKIE"' EXIT

echo "==> 登录 $AG_API"
curl -sS -c "$COOKIE" -X POST "$AG_API/control/login" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$AG_USER\",\"password\":\"$AG_PASS\"}" -o /dev/null

echo "==> 读取配置文件 $AG_CONF"
TMP=$(mktemp)
sudo cat "$AG_CONF" > "$TMP"

if ! grep -qE '^    password: \$2[aby]\$' "$TMP"; then
  echo "!! 配置里没找到 bcrypt 密码行，格式可能变了，请人工确认" >&2
  exit 1
fi

# 脱敏：把 bcrypt 哈希替换成占位符
sed -E 's|^(    password: ).*|\1$2a$10$REPLACE_ME_RUN_scripts/gen-password-hash.sh|' \
  "$TMP" > "$REPO/config/AdGuardHome.yaml"
rm -f "$TMP"
echo "    已脱敏 password 字段"

echo "==> 导出自定义规则"
curl -sS -b "$COOKIE" "$AG_API/control/filtering/status" -o /tmp/_ag_fs.json
python3 - "$REPO" <<'PY'
import json, sys
repo = sys.argv[1]
o = json.load(open('/tmp/_ag_fs.json', encoding='utf-8'))
rules = o.get('user_rules') or []
with open(f'{repo}/config/user-rules.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(rules) + '\n')

fl = [{"name": f.get("name"), "url": f.get("url"),
       "enabled": f.get("enabled"), "rules_count": f.get("rules_count")}
      for f in (o.get('filters') or [])]
with open(f'{repo}/config/filters.json', 'w', encoding='utf-8') as f:
    json.dump(fl, f, ensure_ascii=False, indent=1)

print(f'    自定义规则 {len(rules)} 条, 列表 {len(fl)} 个')
PY

echo "==> 导出运行态快照"
curl -sS -b "$COOKIE" "$AG_API/control/dns_info"         -o /tmp/_ag_dns.json
curl -sS -b "$COOKIE" "$AG_API/control/safesearch/status" -o /tmp/_ag_ss.json
curl -sS -b "$COOKIE" "$AG_API/control/safebrowsing/status" -o /tmp/_ag_sb.json
curl -sS -b "$COOKIE" "$AG_API/control/stats"            -o /tmp/_ag_st.json
python3 - "$REPO" <<'PY'
import json, sys
repo = sys.argv[1]
load = lambda p: json.load(open(p, encoding='utf-8'))
d, ss, sb, st = (load(f'/tmp/_ag_{n}.json') for n in ('dns', 'ss', 'sb', 'st'))
snap = {
    "_note": "AdGuard Home 运行态快照，仅作记录；恢复以 config/AdGuardHome.yaml 为准",
    "dns": {k: d.get(k) for k in [
        "upstream_dns", "fallback_dns", "bootstrap_dns", "upstream_mode",
        "upstream_timeout", "cache_enabled", "cache_size", "cache_ttl_min",
        "cache_ttl_max", "cache_optimistic", "dnssec_enabled", "ratelimit",
        "blocking_mode", "resolve_clients", "use_private_ptr_resolvers",
        "local_ptr_upstreams"]},
    "safe_search": ss,
    "safe_browsing": sb,
    "stats": {
        "num_dns_queries": st.get("num_dns_queries"),
        "num_blocked_filtering": st.get("num_blocked_filtering"),
        "num_replaced_safebrowsing": st.get("num_replaced_safebrowsing"),
        "num_replaced_safesearch": st.get("num_replaced_safesearch"),
        "avg_processing_time_ms": round((st.get("avg_processing_time") or 0) * 1000, 1),
    },
}
with open(f'{repo}/config/settings.json', 'w', encoding='utf-8') as f:
    json.dump(snap, f, ensure_ascii=False, indent=1)
print('    settings.json 已更新')
PY

rm -f /tmp/_ag_*.json

echo
echo "完成。变更："
cd "$REPO" && git status --short 2>/dev/null || echo "(此目录不是 git 仓库)"
echo
echo "下一步：git add -A && git commit -m 'chore: sync adguard config' && git push"
