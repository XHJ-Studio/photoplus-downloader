# FOR AI AGENTS — Photoplus Downloader Technical Spec

## Project Overview

**Domain**: live.photoplus.cn — Chinese event photography live-streaming platform.

**Goal**: Batch-download original-quality photos from photoplus events without browser automation (for API calls), with Playwright fallback only when necessary for CDN access.

## API Architecture

### Base URL
```
https://live.photoplus.cn
```

### Authentication: Request Signing

Every API request requires two extra query parameters:
- `_t`: Unix timestamp in milliseconds
- `_s`: MD5 signature

**Signature Algorithm** (reverse-engineered from `app.4e28dea63b1465d46039.js`):

```python
import hashlib

def generate_sign(params: dict) -> dict:
    timestamp = str(int(time.time() * 1000))
    params = dict(params)
    params['_t'] = timestamp
    
    # Sort keys alphabetically
    sorted_keys = sorted(params.keys())
    parts = [f"{k}={params[k]}" for k in sorted_keys]
    param_str = '&'.join(parts)
    
    sign = hashlib.md5((param_str + "laxiaoheiwu").encode()).hexdigest()
    params['_s'] = sign
    return params
```

**CRITICAL**: The secret string is `"laxiaoheiwu"` (from Chinese "啦小黑屋").

**Key sort order note**: `_t` sorts BEFORE `activityNo` because underscore `_` comes before `a` in ASCII. The full sorted order for pic/list is:
```
_t, activityNo, count, isNew, key, page, ppSign, size
```

### Core API Endpoints

#### 1. Get Photo List
```
GET /pic/list
```

**Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| activityNo | string | ✅ | Event ID (e.g., `77524334`) |
| key | string | | Filter key (empty for all) |
| isNew | string | | `false` |
| count | string | | Max per page. Use `200` to get all. `100` only returns 100 even if more exist. |
| page | string | | Page number (1-based) |
| size | string | | Page size |
| ppSign | string | | Empty |
| _t | string | ✅ auto | Timestamp (added by sign generator) |
| _s | string | ✅ auto | Signature (added by sign generator) |

**Response Structure**:
```json
{
  "code": 1,
  "message": "I'am OK",
  "success": true,
  "result": {
    "pics_total": 189,
    "pageTotal": 1.0,
    "key": 336033014,
    "view_count": 5905,
    "pics_array": [
      {
        "id": 336033014,
        "name": "DSC1646",
        "origin_img": "//pb.plusx.cn/plus/immediate/77524334/20231223183101984/DSC1646.heic~tplv-9lv23dm2t1-size:2291661.jpeg?sign=...",
        "big_img": "//pb.plusx.cn/plus/immediate/77524334/20231223183101984/DSC1646.heic~tplv-9lv23dm2t1-resize-animforce-v1:1600:3000:gif.JPG?sign=...",
        "thumbnail": "//pb.plusx.cn/plus/immediate/77524334/20231223183101984/DSC1646.heic~tplv-9lv23dm2t1-resize-animforce-v1:480:1000:gif.avif?sign=...",
        "width": 3160,
        "height": 2106,
        "show_size": 2291661,
        "activity_no": 77524334,
        "activity_name": "...",
        "userName": "摄影师",
        "camer": "JJ_卡口",
        "pic_type": 1
      }
    ]
  }
}
```

#### 2. Get Event Detail
```
GET /live/detail?activityNo={id}&_s={sig}&_t={ts}
```

#### 3. Get Albums
```
GET /album/albums?activityNo={id}&_s={sig}&_t={ts}
```

## Image URL Formats

Photoplus uses **pb.plusx.cn** CDN with tplv (image processing) suffixes.

### URL Structure
```
https://pb.plusx.cn/plus/immediate/{activityNo}/{timestamp}/{filename}.{ext}~tplv-{processor}-{operation}.{output_ext}?sign={signature}
```

### Three Quality Levels

| Field | URL Pattern | Size | Quality | Recommendation |
|-------|-------------|------|---------|----------------|
| `thumbnail` | `~tplv-...-resize-animforce-v1:480:1000:gif.avif` | ~30-80KB | 480px, AVIF | Preview only |
| `big_img` | `~tplv-...-resize-animforce-v1:1600:3000:gif.JPG` | ~200-600KB | 1600px long edge | ❌ Too small |
| `origin_img` | `~tplv-...-size:XXXXXXX.jpeg` | ~1.5-2.5MB | **Original resolution** (e.g., 3160×2106) | ✅ **USE THIS** |

### Important: `origin_img` is NOT raw .heic

The `origin_img` field contains a **high-quality JPEG** processed by the CDN, but it preserves the original image dimensions. The `~tplv-...-size:XXXXXXX.jpeg` suffix indicates:
- `size:2291661` = output file size in bytes
- `.jpeg` = output format

The actual raw `.heic` file (without tplv suffix) requires browser session cookies and returns **403 Forbidden** via pure requests.

### Filename Extraction

When generating download filenames from `origin_img`, extract the extension from the **tplv suffix**, not the base filename:

```python
# Path: .../DSC0981.heic~tplv-9lv23dm2t1-size:2031890.jpeg
# Extension should be .jpeg (from the tplv suffix), not .heic
```

## Error Patterns & Diagnostics

### API Errors
| Code | Meaning | Fix |
|------|---------|-----|
| `1` + `success: true` | Success (counterintuitive: code=1 means OK) | — |
| `1` + `success: false` | Generic error | Check params |
| No `data`/`result` | Invalid signature | Verify MD5 algorithm and param sorting |

### CDN Download Errors
| Error | Cause | Fix |
|-------|-------|-----|
| `403 Forbidden` | Missing/expired `sign` param or wrong Referer | Sign is bound to URL path; use the exact URL from API response |
| `403 Forbidden` on `.heic` (no tplv) | Raw file requires browser session | Use `origin_img` with tplv suffix instead |
| Empty body | Response compressed | Use `response.body()` in Playwright or normal requests |

## Implementation Checklist

When implementing photoplus download:
1. [ ] Extract `activityNo` from URL
2. [ ] Call `/pic/list` with signed params (count=200)
3. [ ] Parse `pics_array` from `result` field
4. [ ] Use `origin_img` for best quality
5. [ ] Add `https:` prefix to `//pb.plusx.cn` URLs
6. [ ] Download with standard requests (CDN accessible)
7. [ ] Extract `.jpeg` extension from tplv suffix for filename
8. [ ] Skip existing files > 1KB

## Comparison with Pailixiang

| Feature | Pailixiang | Photoplus |
|---------|-----------|-----------|
| Domain | pailixiang.com | live.photoplus.cn |
| Auth | `ak` token (intercepted from browser) | MD5 signature (self-computable) |
| API | `AlbumSearchPhoto`, `GetPhotoOriginalUrl` | `pic/list` |
| Storage | Direct OSS + Transfer/BaiduPan | pb.plusx.cn CDN with tplv processing |
| Raw format | `.jpg` | `.heic` (with JPEG fallback) |
| Sign secret | N/A (dynamic token) | `"laxiaoheiwu"` |
| Download method | Often needs Playwright for `ak` | Pure requests work for API + CDN |
