# workbuddy-adguard-config

家里 NAS（192.168.3.100）上 **AdGuard Home** 的配置备份，可随时拉取恢复。

> v2rayA 的分流配置单独维护在 [workbuddy-proxy-config](https://github.com/Kmatsk/workbuddy-proxy-config)，
> 两个仓库刻意分开：一个是 DNS 过滤层，一个是代理分流层，改一个不影响另一个。

## 部署环境

| 项 | 值 |
|---|---|
| 位置 | NAS `192.168.3.100`，Docker `host` 网络模式 |
| 版本 | AdGuard Home v0.107.80 |
| DNS 服务 | `192.168.3.100:53`（UDP + TCP） |
| 管理面板 | `http://192.168.3.100:3000` |
| 配置目录 | `/vol1/1000/docker/AdGuard/conf/AdGuardHome.yaml` |
| 工作目录 | `/vol1/1000/docker/AdGuard/` |

## 当前配置摘要

| 项 | 值 |
|---|---|
| 过滤列表 | 22 个，合计 2,185,604 条规则 |
| 自定义规则 | 102 条（含家长控制、App 广告 SDK、误杀豁免） |
| 主上游 | `tls://223.5.5.5` + `tls://223.6.6.6`（parallel） |
| 备用上游 | `tls://1.12.12.12` |
| 安全搜索 | 开启，7 个引擎（Bing/Google/DuckDuckGo/YouTube/Yandex/Ecosia/Pixabay） |
| 恶意网站拦截 | 开启 |
| DNSSEC 验证 | 关闭（上游已是 DoT，省掉每条冷查询的 DS/DNSKEY 往返） |
| 缓存 | 8 MB，TTL 60–3600 s，乐观模式开启 |
| 拦截响应 TTL | 300 s |

## 文件

| 文件 | 用途 |
|---|---|
| `config/AdGuardHome.yaml` | 完整配置（**密码已脱敏**，恢复后需重新生成） |
| `config/user-rules.txt` | 102 条自定义过滤规则 |
| `config/filters.json` | 22 个订阅列表的清单（名称 / URL / 开关 / 条数） |
| `config/settings.json` | 运行态快照：DNS 参数、安全搜索、安全浏览、统计 |
| `scripts/healthcheck.py` | 体检脚本，纯标准库，任意机器可跑 |
| `scripts/backup-adguard.sh` | 在 NAS 上一键抓取当前配置并写回本仓库 |
| `scripts/restore-adguard.sh` | 在 NAS 上一键恢复（自动备份现有配置） |
| `scripts/gen-password-hash.sh` | 生成 bcrypt 密码哈希 |
| `docs/healthcheck-2026-11-10.md` | 本次完整体检报告 |

## 恢复步骤

在 NAS 上执行（脚本自带备份，失败可回滚）：

```bash
git clone https://github.com/Kmatsk/workbuddy-adguard-config.git
cd workbuddy-adguard-config
bash scripts/gen-password-hash.sh '你的新密码'    # 先拿到哈希
# 把哈希填进 config/AdGuardHome.yaml 的 password: 行
sudo bash scripts/restore-adguard.sh
```

恢复脚本会做三件事：把现有 yaml 备份到 `conf/AdGuardHome.yaml.bak.<时间戳>`、
写入新配置、重启容器。

**必须重启容器**——AdGuard 有配置热加载不彻底的毛病，改完不重启会出现
「yaml 已写入但运行进程还是旧参数」的假象（安全搜索就踩过这个坑）。

## App 广告 SDK 拦截（2026-11-10）

针对小米 K70（192.168.3.104）上的「班级小管家」（`com.banjixiaoguanjia.app`，北京校萌科技）做
DNS 层广告治理。依据是该 App 官方公示的《第三方 SDK 目录》——23 个 SDK 中有 **15 个明确标注
「使用目的：广告」**（友盟、优量汇、穿山甲、快手联盟、Funlink、美数、AdScope/倍孜、亿帆、
优推、Octopus、脉盟、极准瑞量、金丝雀、HX）。

| 分类 | 处理 |
|---|---|
| 已被 218 万条内置列表覆盖 | 优量汇 `gdt.qq.com`/`e.qq.com`、穿山甲 `pangolin-sdk-toutiao.com`/`pglstatp-toutiao.com`、快手 `gdfp.gifshow.com`/`ad.kuaishou.com`、友盟 `umeng.com`、Funlink `adfunlink.com`、倍孜 `beizi.biz`、亿帆 `yfanads.cn`、Octopus `zhangyuyidong.cn`、脉盟 `adwangmai.com`、优推 `ad.gameley.com` |
| 本次新增 11 条自定义规则 | `atdplus.cn`（美数）、`qttunion.com`（趣盟）、`innoads.cn`、`sspapi.qingxuntech.cn`、`vista.divms.cn`、`shunchangzhixing.com`（顺昌之星）、`hzjizhun.cn`/`hzjizhun.com`（极准）、`baihemob.com`（金丝雀）、`dashisx.com`（HX）、`adlog.kuaishou.com` |

新增依据不只是 SDK 名单：当日 12000 条 DNS 日志里，`sdk-n.innoads.cn`、`sspapi.qingxuntech.cn`、
`vista.divms.cn`、`inner-empty/inner-report.shunchangzhixing.com`、`jp/de.ad.gameley.com`
全部处于**放行**状态且持续被请求，说明内置列表漏了这些聚合/监测链路，而它们正是残留广告的来源。

**不能按设备生效**：华为 AX3 做 DNS 代理转发时用 WAN 地址（171.9.89.38）做源，AdGuard 侧
全部请求同源，`$client` 与 per-client 配置全部失效，所以规则是全家全局生效。

**不能碰的域名**（App 自身业务链路，误杀会白屏/无法登录）：`b.welife001.com`、
`allsystemfile.welife001.com`、`service.banjixiaoguanjia.com`、`a.welife001.com`，
以及微信登录支付 `api.weixin.qq.com`、`open.weixin.qq.com`、`payapp.weixin.qq.com`。

## 体检

```bash
python3 scripts/healthcheck.py --host 192.168.3.100 --port 3000 \
    --dns 192.168.3.100 --user <面板账号> --password <面板密码>
```

会依次检查：面板可达、正常域名解析、拦截域名返回 0.0.0.0、安全搜索改写、
列表条数、冷查询延迟。全绿退出码 0，有失败退出码 1。

## 关于密码

`config/AdGuardHome.yaml` 里的 `password:` 已替换为占位符
`$2a$10$REPLACE_ME_RUN_scripts/gen-password-hash.sh`。

这是刻意为之：仓库是公开的，bcrypt 哈希虽然不可逆，但弱密码可被离线爆破。
恢复时用 `scripts/gen-password-hash.sh` 重新生成即可。

## 同步机制

面板里的规则是「事实来源」，本仓库是它的快照。改动流程：

```
面板改配置 → 跑 scripts/backup-adguard.sh → git commit && push
```

不要在仓库里改 yaml 再去覆盖面板，容易和列表自动更新产生冲突。
