# FOR AI AGENTS — Photoplus 系统完整技术规格

> **目标读者：** 其他 AI Agent（Kimi、GPT、Claude 等）
> **文档定位：** 让你读完这份文档后，不需要重新搜索网络，就能独立处理任何 Photoplus 活动的下载任务，并能诊断未知问题。
> **版本：** 2026-05-02 | 基于 11 个真实活动的完整逆向工程

---

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [逆向工程方法论](#2-逆向工程方法论)
3. [API 完整规格](#3-api-完整规格)
4. [签名算法详解](#4-签名算法详解)
5. [图片质量与 CDN](#5-图片质量与cdn)
6. [错误经验录](#6-错误经验录)
7. [新活动诊断 SOP](#7-新活动诊断-sop)
8. [AI 直接调用指南](#8-ai-直接调用指南)

---

## 1. 系统架构总览

### 1.1 前端
- **框架：** Vue 3 单页应用（SPA）
- **页面结构：** `live.photoplus.cn/live/pc/{activityNo}/#/live`
- **图片加载：** 瀑布流 + 懒加载

### 1.2 API 层
- **Base URL：** `https://live.photoplus.cn`
- **通信方式：** GET，URL 参数 + 签名
- **认证方式：** 时间戳 `_t` + MD5 签名 `_s`

### 1.3 存储层
- 图片存储在 CDN，通过 `~tplv-` 处理参数控制输出质量

---

## 2. 逆向工程方法论

### 2.1 签名算法发现过程

**Step 1 — 抓包发现 API：**
```
GET /pic/list?activityNo=77524334&count=200&isNew=false&key=&page=1&ppSign=&size=200&_t=1777723589890&_s=d60a7ecc32ea5738565a3da5ea398d3e
```

**Step 2 — 观察 `_s` 参数：**
- 每次请求都不同
- 与 `_t`（时间戳）相关
- 32 位十六进制，疑似 MD5

**Step 3 — JS 逆向：**
在 `chunk-vendors.{hash}.js` 中搜索 `"_s"` 或 `"sign"`，找到签名函数：
```javascript
// 混淆后的代码，经还原后：
function generateSign(params) {
    var sortedKeys = Object.keys(params).sort();
    var parts = sortedKeys.map(function(k) {
        return k + "=" + params[k];
    });
    var paramStr = parts.join("&");
    return md5(paramStr + "laxiaoheiwu");
}
```

**密钥：** `"laxiaoheiwu"`（拼音：拉小嘿屋）

---

## 3. API 完整规格

### 3.1 获取照片列表

```
GET https://live.photoplus.cn/pic/list
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `activityNo` | string | 是 | 活动 ID，如 `77524334` |
| `count` | string | 是 | 每页数量，最大 `200` |
| `page` | string | 是 | 页码，从 1 开始 |
| `size` | string | 是 | 同 `count`，也是 `200` |
| `isNew` | string | 否 | 固定 `false` |
| `key` | string | 否 | 搜索关键词，空字符串 |
| `ppSign` | string | 否 | 固定空字符串 |
| `_t` | string | 是 | 毫秒时间戳 |
| `_s` | string | 是 | MD5 签名 |

**签名计算：**
```python
import hashlib
import time

def generate_sign(params):
    timestamp = str(int(time.time() * 1000))
    params = dict(params)
    params['_t'] = timestamp
    
    sorted_keys = sorted(params.keys())
    parts = [f"{k}={params[k]}" for k in sorted_keys]
    param_str = '&'.join(parts)
    
    sign = hashlib.md5((param_str + "laxiaoheiwu").encode()).hexdigest()
    params['_s'] = sign
    return params

# 示例
params = {
    'activityNo': '77524334',
    'count': '200',
    'isNew': 'false',
    'key': '',
    'page': '1',
    'ppSign': '',
    'size': '200',
}
signed = generate_sign(params)
# signed['_t'] = "1777723589890"
# signed['_s'] = "d60a7ecc32ea5738565a3da5ea398d3e"
```

**响应结构：**
```json
{
  "success": true,
  "code": "200",
  "message": "success",
  "result": {
    "pics_array": [
      {
        "id": 123456789,
        "name": "DSC0981.heic",
        "origin_img": "//p1-tt.byteimg.com/img/...~tplv-9lv23dm2t1-size:2031890.jpeg",
        "big_img": "//p1-tt.byteimg.com/img/...~tplv-9lv23dm2t1-resize-animforce-v1:1600:3000:gif.JPG",
        "raw": "//p1-tt.byteimg.com/img/...DSC0981.heic",
        "width": 4032,
        "height": 3024,
        "create_time": "2024-01-15 10:30:00",
        "like_num": 5
      }
    ],
    "total": 1500
  }
}
```

**分页逻辑：**
```python
page = 1
all_photos = []
while True:
    photos = fetch_photo_list(activity_no, page=page, size=200)
    if not photos:
        break
    all_photos.extend(photos)
    if len(photos) < 200:
        break
    page += 1
    time.sleep(0.5)  # 礼貌延迟
```

### 3.2 其他 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/live/detail` | GET | 获取活动详情 |
| `/album/albums` | GET | 获取相册列表 |

---

## 4. 签名算法详解

### 4.1 算法流程

```
输入: 参数字典 params（不含 _t 和 _s）
步骤:
  1. 添加 _t = 当前毫秒时间戳
  2. 按字母顺序排序所有参数键
  3. 拼接成 "key1=value1&key2=value2&..." 格式
  4. 在末尾追加字符串 "laxiaoheiwu"
  5. 计算 MD5 哈希
  6. 将 _s = MD5 值添加到参数中
输出: 带 _t 和 _s 的完整参数字典
```

### 4.2 完整示例

```python
import hashlib
import time

params = {
    'activityNo': '77524334',
    'count': '200',
    'isNew': 'false',
    'key': '',
    'page': '1',
    'ppSign': '',
    'size': '200',
}

# Step 1: 添加时间戳
params['_t'] = str(int(time.time() * 1000))
# _t = "1777723589890"

# Step 2: 排序键
sorted_keys = sorted(params.keys())
# ['activityNo', 'count', 'isNew', 'key', 'page', 'ppSign', 'size', '_t']

# Step 3: 拼接
parts = [f"{k}={params[k]}" for k in sorted_keys]
param_str = '&'.join(parts)
# "activityNo=77524334&count=200&isNew=false&key=&page=1&ppSign=&size=200&_t=1777723589890"

# Step 4: 追加密钥
sign_input = param_str + "laxiaoheiwu"

# Step 5: MD5
sign = hashlib.md5(sign_input.encode()).hexdigest()
# "d60a7ecc32ea5738565a3da5ea398d3e"

# Step 6: 添加签名
params['_s'] = sign
```

### 4.3 常见错误

- ❌ 时间戳用秒而不是毫秒 → 签名不匹配
- ❌ 参数排序时大小写不一致 → 签名不匹配
- ❌ 遗漏空字符串参数（如 `key=`）→ 签名不匹配

---

## 5. 图片质量与 CDN

### 5.1 三种图片字段

| 字段 | URL 示例 | 大小 | 分辨率 | 说明 |
|------|---------|------|--------|------|
| `origin_img` | `...~tplv-...-size:2031890.jpeg` | ~1.5-2.5MB | 原图（如 4032×3024） | **推荐**，高质量 JPEG |
| `big_img` | `...~tplv-...-resize-animforce-v1:1600:3000:gif.JPG` | ~200-600KB | 1600px 长边 | 压缩预览版 |
| `raw` | `...DSC0981.heic` | 原始文件 | 原始 | 需要 session，403 |

### 5.2 URL 处理

**协议补全：**
```python
if url.startswith('//'):
    url = 'https:' + url
```

**文件名提取：**
```python
# origin_img: DSC0981.heic~tplv-9lv23dm2t1-size:2031890.jpeg
# 处理后文件名: DSC0981.jpeg
path = urlparse(url).path
if '~' in path:
    suffix_part = path.split('~')[1]  # tplv-...-size:2031890.jpeg
    ext = '.' + suffix_part.split('.')[-1]  # .jpeg
else:
    ext = os.path.splitext(path)[1]
```

### 5.3 下载策略

**优先 requests（快）：**
```python
headers = {
    'User-Agent': 'Mozilla/5.0 ...',
    'Referer': 'https://live.photoplus.cn/',
}
r = requests.get(url, headers=headers, timeout=60, stream=True)
```

**回退 Playwright（稳）：**
当 requests 返回 403 时，在浏览器中使用 `fetch()` 获取 base64 数据：
```python
result = await page.evaluate("""async (url) => {
    const resp = await fetch(url, { credentials: 'include' });
    const blob = await resp.blob();
    const reader = new FileReader();
    return new Promise((resolve) => {
        reader.onloadend = () => {
            resolve({ ok: true, data: reader.result.split(',')[1] });
        };
        reader.readAsDataURL(blob);
    });
}""", url)
data = base64.b64decode(result['data'])
```

---

## 6. 错误经验录

### 6.1 ❌ 签名不匹配 401

**现象：** API 返回 `401 Unauthorized`

**原因：**
- 时间戳不是毫秒级
- 参数排序错误
- 遗漏了空参数

**解决：** 严格按照字母顺序排序，包含所有参数（包括空字符串）。

### 6.2 ❌ 图片下载 403

**现象：** `requests.get(img_url)` 返回 403

**原因：** CDN 需要 Referer

**解决：**
```python
headers = {
    'User-Agent': 'Mozilla/5.0 ...',
    'Referer': 'https://live.photoplus.cn/',
}
```

### 6.3 ❌ Playwright fetch 跨域失败

**现象：** `page.evaluate` 中的 `fetch()` 返回 `Failed to fetch`

**原因：** CDN 没有设置 CORS 头

**解决：** 使用 `page.evaluate` + `FileReader` 读取 blob 为 base64，或者直接用 `requests` + Referer。

### 6.4 ❌ 文件名无扩展名

**现象：** 保存的文件没有 `.jpg` 后缀

**原因：** 原文件名是 `.heic`，但 URL 处理后的扩展名在 `~tplv` 后缀中

**解决：** 从 `~tplv` 后缀中提取实际输出格式（`.jpeg` 或 `.JPG`）。

---

## 7. 新活动诊断 SOP

### Step 1 — 确认 activityNo
从 URL 中提取：
```python
import re
url = "https://live.photoplus.cn/live/pc/77524334/#/live"
m = re.search(r'/live/pc/(\d+)', url)
activity_no = m.group(1) if m else url  # 或者直接传数字
```

### Step 2 — 测试 API
```python
photos = fetch_photo_list(activity_no, page=1, size=10)
print(f"Got {len(photos)} photos")
if photos:
    print(photos[0].get('origin_img', 'NO origin_img'))
```

### Step 3 — 测试签名
如果 API 返回 401：
- 检查 `_t` 是否为毫秒时间戳
- 检查参数排序是否为字母顺序
- 检查是否包含密钥 `"laxiaoheiwu"`

### Step 4 — 测试图片下载
```python
test_url = photos[0]['origin_img']
if test_url.startswith('//'):
    test_url = 'https:' + test_url
r = requests.get(test_url, headers={'Referer': 'https://live.photoplus.cn/'}, timeout=30)
print(r.status_code, len(r.content))
```

### Step 5 — 全量下载
```bash
python photoplus_downloader.py {activity_no}
```

---

## 8. AI 直接调用指南

### 8.1 最小可运行示例

```python
import hashlib
import time
import os
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = 'https://live.photoplus.cn'
SECRET = 'laxiaoheiwu'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://live.photoplus.cn/',
}

def generate_sign(params):
    params = dict(params)
    params['_t'] = str(int(time.time() * 1000))
    sorted_keys = sorted(params.keys())
    param_str = '&'.join(f"{k}={params[k]}" for k in sorted_keys)
    params['_s'] = hashlib.md5((param_str + SECRET).encode()).hexdigest()
    return params

def get_photos(activity_no):
    photos = []
    page = 1
    while True:
        params = generate_sign({
            'activityNo': activity_no,
            'count': '200',
            'isNew': 'false',
            'key': '',
            'page': str(page),
            'ppSign': '',
            'size': '200',
        })
        r = requests.get(f'{BASE_URL}/pic/list', params=params, headers=HEADERS)
        batch = r.json()['result']['pics_array']
        if not batch:
            break
        photos.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        time.sleep(0.5)
    return photos

def download_photo(pic, output_dir):
    url = pic.get('origin_img', pic.get('big_img', ''))
    if url.startswith('//'):
        url = 'https:' + url
    name = pic.get('name', 'photo')
    # 简单处理扩展名
    if '~' in url:
        ext = '.' + url.split('~')[1].split('.')[-1]
        if not name.endswith(ext):
            name = os.path.splitext(name)[0] + ext
    filepath = os.path.join(output_dir, name)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return True
    r = requests.get(url, headers=HEADERS, timeout=60)
    if r.status_code == 200 and len(r.content) > 1000:
        with open(filepath, 'wb') as f:
            f.write(r.content)
        return True
    return False

# 主流程
ACTIVITY_NO = '77524334'
OUTPUT_DIR = f'photoplus_{ACTIVITY_NO}'
os.makedirs(OUTPUT_DIR, exist_ok=True)

photos = get_photos(ACTIVITY_NO)
print(f"Total: {len(photos)}")

with ThreadPoolExecutor(max_workers=4) as ex:
    futures = [ex.submit(download_photo, p, OUTPUT_DIR) for p in photos]
    results = [f.result() for f in futures]

print(f"Success: {sum(results)}, Failed: {len(results)-sum(results)}")
```

### 8.2 常见调用模式

**下载新活动：**
```bash
python photoplus_downloader.py 12345678
```

**指定输出目录：**
```bash
python photoplus_downloader.py "https://live.photoplus.cn/live/pc/12345678/#/live" ./my_event
```

---

*Document version: 2026-05-02 | For AI Agents*
