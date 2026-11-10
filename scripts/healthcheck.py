#!/usr/bin/env python3
"""AdGuard Home 体检脚本 —— 纯标准库，无需 dig / 第三方包。

用法:
    python3 healthcheck.py --host 192.168.3.100 --port 3000 \
        --dns 192.168.3.100 --user Kmatsk --password 'xxx'

退出码: 0 全部通过, 1 有失败项。
"""

import argparse
import http.cookiejar
import json
import random
import socket
import struct
import sys
import time
import urllib.parse
import urllib.request
from urllib.error import URLError

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []


def record(name, status, detail=""):
    results.append((name, status, detail))
    mark = {PASS: "[ok]  ", FAIL: "[FAIL]", WARN: "[warn]"}[status]
    print(f"{mark} {name}" + (f"  — {detail}" if detail else ""))


class AdGuard:
    def __init__(self, host, port, timeout=10):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def api(self, path, payload=None):
        raw = self.api_raw(path, payload)
        return json.loads(raw) if raw else {}

    def api_raw(self, path, payload=None):
        url = self.base + path
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self.opener.open(req, timeout=self.timeout) as resp:
            return resp.read().decode()

    def login(self, user, password):
        # AdGuard 的 /control/login 成功时返回空 body, 只下发 cookie
        self.api_raw("/control/login", {"name": user, "password": password})
        return self

    def status(self):
        return self.api("/control/status")

    def filtering(self):
        return self.api("/control/filtering/status")

    def check_host(self, name):
        q = urllib.parse.urlencode({"name": name})
        return self.api("/control/filtering/check_host?" + q)

    def clear_cache(self):
        try:
            self.api("/control/cache_clear", {})
        except Exception:
            pass


def dns_query(name, server, timeout=4.0):
    """返回 A 记录列表, 超时返回 None。"""
    qid = random.randint(0, 65535)
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    msg = header + qname + struct.pack(">HH", 1, 1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    t0 = time.time()
    try:
        sock.sendto(msg, (server, 53))
        data, _ = sock.recvfrom(4096)
    except Exception:
        return None
    finally:
        sock.close()
    elapsed = (time.time() - t0) * 1000

    def read_name(buf, i):
        parts = []
        while True:
            if i >= len(buf):
                return ".".join(parts), i
            ln = buf[i]
            if ln == 0:
                return ".".join(parts), i + 1
            if ln & 0xC0 == 0xC0:
                return ".".join(parts), i + 2
            parts.append(buf[i + 1 : i + 1 + ln].decode("latin1"))
            i += 1 + ln

    try:
        _, i = read_name(data, 12)
        i += 4
        ancount = struct.unpack(">H", data[6:8])[0]
        ips = []
        for _ in range(ancount):
            _, i = read_name(data, i)
            if i + 10 > len(data):
                break
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[i : i + 10])
            i += 10
            if rtype == 1 and rdlen == 4:
                ips.append(".".join(str(b) for b in data[i : i + 4]))
            i += rdlen
    except Exception:
        ips = []
    return {"ips": sorted(set(ips)), "ms": elapsed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.3.100")
    ap.add_argument("--port", type=int, default=3000)
    ap.add_argument("--dns", default="192.168.3.100")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--expect-blocked", default="pornhub.com,bet365.com")
    ap.add_argument("--expect-ok", default="www.baidu.com,www.bilibili.com,www.douyin.com")
    args = ap.parse_args()

    print(f"目标: {args.host}:{args.port}  DNS: {args.dns}\n")

    try:
        ag = AdGuard(args.host, args.port).login(args.user, args.password)
    except URLError as exc:
        record("面板可达", FAIL, f"连接失败: {exc}")
        summarize()
        return
    except Exception as exc:
        record("面板登录", FAIL, str(exc))
        summarize()
        return

    try:
        st = ag.status()
        record("面板登录", PASS, f"AdGuard {st.get('version')}")
        record("服务运行", PASS if st.get("running") else FAIL,
               "running" if st.get("running") else "未运行")
        record("防护开关", PASS if st.get("protection_enabled") else FAIL,
               "已开启" if st.get("protection_enabled") else "已关闭")
    except Exception as exc:
        record("读取状态", FAIL, str(exc))

    for dom in [d.strip() for d in args.expect_ok.split(",") if d.strip()]:
        r = dns_query(dom, args.dns)
        if r is None:
            record(f"解析 {dom}", FAIL, "查询超时")
        elif not r["ips"]:
            record(f"解析 {dom}", FAIL, "无 A 记录")
        elif "0.0.0.0" in r["ips"]:
            record(f"解析 {dom}", FAIL, "被误拦为 0.0.0.0")
        else:
            record(f"解析 {dom}", PASS, f"{r['ips'][0]}  {r['ms']:.0f}ms")

    for dom in [d.strip() for d in args.expect_blocked.split(",") if d.strip()]:
        r = dns_query(dom, args.dns)
        if r is None:
            record(f"拦截 {dom}", WARN, "查询超时（可能已被丢弃）")
        elif "0.0.0.0" in r["ips"] or "::" in r["ips"]:
            record(f"拦截 {dom}", PASS, "返回 0.0.0.0")
        elif not r["ips"]:
            record(f"拦截 {dom}", PASS, "无解析结果")
        else:
            record(f"拦截 {dom}", FAIL, f"未拦截，解析到 {r['ips'][0]}")

    try:
        plain = dns_query("www.bing.com", args.dns)
        strict = dns_query("strict.bing.com", args.dns)
        if plain and strict and plain["ips"] and plain["ips"] == strict["ips"]:
            record("安全搜索改写", PASS, "Bing 已指向 strict.bing.com")
        else:
            record("安全搜索改写", WARN,
                   f"Bing={plain['ips'] if plain else '?'} strict={strict['ips'] if strict else '?'}")
        g = dns_query("www.google.com", args.dns)
        gf = dns_query("forcesafesearch.google.com", args.dns)
        if g and gf and g["ips"] and g["ips"] == gf["ips"]:
            record("Google 安全搜索", PASS, "已指向 forcesafesearch")
        else:
            record("Google 安全搜索", WARN, "未改写或域名被污染")
    except Exception as exc:
        record("安全搜索改写", WARN, str(exc))

    try:
        fs = ag.filtering()
        filters = fs.get("filters") or []
        on = [f for f in filters if f.get("enabled")]
        total = sum(f.get("rules_count") or 0 for f in on)
        rules = fs.get("user_rules") or []
        record("过滤列表", PASS if on else WARN, f"{len(on)} 个启用 / 共 {len(filters)} 个")
        record("规则总量", PASS if total > 100000 else WARN, f"{total:,} 条")
        record("自定义规则", PASS if rules else WARN, f"{len(rules)} 条")
        parent = [f for f in on if "家长控制" in (f.get("name") or "")]
        if parent:
            record("家长控制列表", PASS,
                   f"{len(parent)} 个 / {sum(f.get('rules_count') or 0 for f in parent):,} 条")
        else:
            record("家长控制列表", WARN, "未检测到")
    except Exception as exc:
        record("读取过滤列表", FAIL, str(exc))

    try:
        ag.clear_cache()
        probe = ["www.12306.cn", "www.ctrip.com", "www.dianping.com",
                 "www.meituan.com", "www.zhihu.com", "www.163.com"]
        # 第一轮是冷递归(要回源逐级查), 不计入; 第二轮才是稳态体感
        for dom in probe:
            dns_query(dom, args.dns)
        lat = []
        for dom in probe:
            r = dns_query(dom, args.dns)
            if r and r["ips"]:
                lat.append(r["ms"])
        if lat:
            lat.sort()
            med = lat[len(lat) // 2]
            ok = med < 100
            record("稳态解析延迟", PASS if ok else WARN,
                   f"中位 {med:.0f}ms  最大 {lat[-1]:.0f}ms  ({len(lat)}/{len(probe)} 成功)")
        else:
            record("稳态解析延迟", FAIL, "全部超时")
    except Exception as exc:
        record("稳态解析延迟", WARN, str(exc))

    summarize()


def summarize():
    fails = [r for r in results if r[1] == FAIL]
    warns = [r for r in results if r[1] == WARN]
    oks = [r for r in results if r[1] == PASS]
    print(f"\n汇总: {len(oks)} 通过 / {len(warns)} 警告 / {len(fails)} 失败")
    if fails:
        print("失败项: " + ", ".join(r[0] for r in fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
