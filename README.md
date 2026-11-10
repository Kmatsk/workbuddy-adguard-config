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
| 自定义规则 | 127 条（含家长控制、App 广告 SDK、误杀豁免） |
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
| `config/user-rules.txt` | 127 条自定义过滤规则 |
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

## 字节系 / 小米系 App 广告（2026-11-10）

| App | 广告来源 | DNS 层覆盖 |
|---|---|---|
| 番茄小说 / 番茄畅听 | 穿山甲（CSJ） | ✅ `pangolin-sdk-toutiao*.com`、`pglstatp-toutiao.com`、`gromore`、`sf*-fe-tos` 全拦 |
| 红果免费短剧（`com.phoenix.read`） | 穿山甲 + 优量汇 | ✅ 同上，加 `gdt.qq.com`/`e.qq.com` |
| 喜番短剧 | 快手联盟 + 穿山甲 | ✅ `ad.kuaishou.com`、`gdfp.gifshow.com`、`adlog.e.kuaishou.*` |
| 西瓜视频（`com.ss.android.article.video`） | 穿山甲 | ✅ |
| 小米视频 | 小米广告 | ✅ `api.ad.xiaomi.com`、`ad.xiaomi.com`、`ad.mi.com`、`ad.miui.com`、`adv.sec.miui.com` |

本次新增 3 条旁路封堵（都是日志 + nslookup 实测「仍在放行」的）：

| 规则 | 说明 |
|---|---|
| `||b9ad.com^` | B9 广告平台，`t.b9ad.com` 埋点 / `dmmc.b9ad.com` 监测实测活跃 |
| `||ad.douyin.com^` | 抖音广告投放接口，实测解析到 39.106.179.250 |
| `||httpdns.bytedance.com^` | 字节 HTTPDNS。不封这条，App 可以绕过本地 DNS 直接拿到广告域名真 IP，前面所有规则都白配 |

**DNS 层做不到的部分（务必知情）**：

- **信息流原生广告**由 App 自己的内容接口下发，与视频/图文同域（`api.dragon.read`、`api.ixigua.com`），拦掉就是白屏
- **广告素材与内容共用 CDN**：`fqnovelvod.com`（番茄小说视频）、`pstatp.com`、`douyincdn.com`，拦域名会连内容一起拦
- **SDK 预加载缓存**：规则生效后，已缓存的广告素材仍可能显示几小时到一两天
- **IP 直连**：App 若缓存了广告服务器 IP，连接不经 DNS，完全不受影响

所以这五款的正确姿势是：DNS 把联盟广告的填充率压到最低，剩下的原生位/缓存位靠无障碍点击跳过（GKD、李跳跳）。

**回滚**：`||httpdns.bytedance.com^` 若导致字节系 App 首次加载变慢或网络异常，删这一行即可；
`||b9ad.com^`、`||ad.douyin.com^` 可直接删，不影响其他规则。

## 今日头条 / 剪映（2026-11-10）

**今日头条**：信息流广告主体走穿山甲/巨量，`ad.toutiao.com`、`pangolin-sdk-toutiao*.com`、
`pglstatp-toutiao.com`、`dm.toutiao.com`、`monsetting.toutiao.com` 都已被内置列表拦下
（日志里能看到请求与被拦记录）。本次补三条实测「仍在放行」的通道：

| 规则 | 依据 |
|---|---|
| `||ads.toutiao.com^` | 头条自售广告接口，12h 日志内 4 次，任何列表都没覆盖 |
| `||dns.toutiao.com^` | 头条 HTTPDNS，12h 内 6 次；不封可自行解析广告域名绕过过滤 |
| `||httpdns.toutiao.com^` | 同上，6 次 |

**剪映**：2026-11-10 21:53 实测抓到完整会话（20 条查询 / 12 个域名 / 0 失败），结论如下。

| 类别 | 域名 | 处理 |
|---|---|---|
| 内容接口 | `lv-api*.ulikecam.com`、`lv-biz-api-*.ulikecam.com`、`lv-qos-api-*.ulikecam.com` | 放行（主 API，拦了白屏） |
| 素材 CDN | `lv.ulikecam.com`、`lv-effect.ulikecam.com` | 放行（贴纸/特效素材） |
| 模板预览 | `v6/v9/v26-jianying.vlabvod.com` | 放行（剪同款预览视频） |
| 资源下发 | `n98-lf-jianying-app-ncdn-ncdn.bytetos.com` | 放行（安装资源/皮肤） |
| 广告 | `api-access.pangolin-sdk-toutiao{,1,-b}.com`、`log-api.pangolin-sdk-toutiao.com`、`gromore.pangolin-sdk-toutiao.com`、`sf3/sf6-fe-tos.pglstatp-toutiao.com`、`ads.toutiao.com` | **已拦**（内置列表） |
| 广告归因 | `toblog/tobapplog.ctobsnssdk.com`、`mssdk.volces.com`、`apmplus.volces.com` | **已拦**（内置列表） |

剪映自有广告子域全部不存在（`ad/ads/lv-ad.ulikecam.com`、`ad.lemon.lv`、`ad.capcut.cn`
实测 NXDOMAIN），所以**没有可补的自有规则**；它的开屏与模板页广告 100% 走穿山甲/巨量。

剩下的「像广告」的内容是剪映自营推广位（会员、模板推荐、剪同款榜单），由 `lv-api.ulikecam.com`
与内容一起下发，DNS 层无法区分，拦域名等于禁用 App。

## 抖音开屏广告（2026-11-10）

抖音开屏是**自营广告**，不走穿山甲，所以前面封的 CSJ/GDT 域名对它无效：

- 广告数据由主接口 `aweme.snssdk.com` 下发，与信息流同一个域名 → 拦了刷不了视频
- 广告素材托管在独立的 **`ad-sign`** 主机上，与内容图床 **`sign`** 主机是两套
  （实测 `p3-ad-sign.douyinpic.com` 存在，而 `p3-sign.douyinpic.com` 是内容图床）
- 因此可以只封 ad-sign，正文图片/视频完全不受影响

| 规则 | 作用 |
|---|---|
| `||p3-ad-sign.douyinpic.com^` | 抖音开屏/信息流广告图片素材 |
| `||p3-ad-sign.byteimg.com^` | 字节系（头条/西瓜/剪映）广告图片素材 |

生效验证：两个 ad-sign 域名返回 `0.0.0.0/::`；`p3-sign.douyinpic.com`、`p26-sign.douyinpic.com`、
`p11.douyinpic.com`、`v3.douyinvod.com`、`aweme.snssdk.com`、`api.amemv.com` 全部正常放行。

**注意**：抖音会把开屏素材缓存在 App 本地，规则生效后仍可能看到一两次旧广告。
彻底生效需要清一次抖音缓存（设置 → 通用 → 清理占用空间）或等缓存自然过期。

DNS 仍然拦不到的部分：视频类开屏（素材与正片共用 `douyinvod` CDN）、
广告内容由主接口下发这一点本身。

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
