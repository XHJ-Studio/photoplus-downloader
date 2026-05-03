# photoplus-downloader

Photoplus (live.photoplus.cn) 照片批量下载器，支持原始高质量 JPEG 下载。

> **核心文件：** `photoplus_downloader.py`（单文件，AI 可直接调用）

---

## 快速开始

```bash
pip install requests

python photoplus_downloader.py "https://live.photoplus.cn/live/pc/77524334/#/live"
```

---

## 面向 AI 的完整技术文档

**如果你是 AI Agent，请先阅读 [`docs/FOR_AI_AGENTS.md`](docs/FOR_AI_AGENTS.md)**

这份文档包含：
- 完整的逆向工程方法论（如何找到签名算法）
- API 详细规格与字段说明
- MD5 签名算法详解
- 图片质量对比（origin_img vs big_img vs raw）
- 常见错误与诊断流程
- AI 直接调用示例

---

## 功能特性

- **原始质量下载**: 下载 `origin_img` 字段的高质量 JPEG（~1.5-2.5MB/张，保留原图分辨率）
- **自动签名**: 内置 MD5 签名算法，无需手动计算
- **双模式下载**: 优先使用 `requests`（快），失败时自动回退到 Playwright（稳）
- **断点续传**: 已存在的文件自动跳过
- **并发下载**: 4 线程并发加速

---

## 使用方法

### 基本用法

```bash
python photoplus_downloader.py <photoplus_url_or_activityNo> [output_dir]
```

### 示例

```bash
# 完整 URL
python photoplus_downloader.py "https://live.photoplus.cn/live/pc/77524334/#/live"

# 简化 URL
python photoplus_downloader.py "https://live.photoplus.cn/live/77524334"

# 仅 activityNo
python photoplus_downloader.py 77524334

# 指定输出目录
python photoplus_downloader.py 77524334 ./my_event
```

### 支持的 URL 格式

- `https://live.photoplus.cn/live/pc/{activityNo}/#/live`
- `https://live.photoplus.cn/live/{activityNo}`
- 直接传数字 activityNo

---

## 技术原理速览

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│               live.photoplus.cn (Vue SPA)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ GET /pic/list?...&_t={ts}&_s={sig}
┌──────────────────────────▼──────────────────────────────────┐
│              API: live.photoplus.cn                         │
│         签名 = md5(排序后参数字符串 + "laxiaoheiwu")        │
└──────────────────────────┬──────────────────────────────────┘
                           │ 返回 pics_array[]
           ┌───────────────┴───────────────┐
           ▼                               ▼
    ┌─────────────┐                ┌─────────────┐
    │ 高质量 JPEG │                │ 1600px 预览 │
    │ origin_img  │                │ big_img     │
    │ ~1.5-2.5MB  │                │ ~200-600KB  │
    │ 原图分辨率   │                │ 1600px 长边 │
    └─────────────┘                └─────────────┘
```

### 关键发现

1. **签名算法**: `md5(按字母排序的参数字符串 + "laxiaoheiwu")`
2. **图片质量**: `origin_img` 是高质量 JPEG（带 `~tplv-...-size:XXXXXXX.jpeg` 后缀）
3. **分页**: 每页最多 200 张，`count=200&size=200`
4. **CDN 访问**: 大部分情况下 `requests` 可直接下载，少数需要 Playwright 回退

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `photoplus_downloader.py` | 主下载脚本，AI 可直接调用 |
| `README.md` | 人类用户快速入口 |
| `docs/FOR_AI_AGENTS.md` | **AI 必读**：完整技术规格、签名算法、诊断流程 |

---

*Created by XHJ-Studio | 2026-05-02*
