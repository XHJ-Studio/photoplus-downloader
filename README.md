# photoplus-downloader

Photoplus (live.photoplus.cn) 照片批量下载器。

## 特性

- ✅ 自动逆向 API 签名算法，无需浏览器拦截
- ✅ 下载高质量原图（`~tplv-...-size:XXXXXXX.jpeg`，保留原图分辨率，约 1.5-2.5MB/张）
- ✅ 自动跳过已下载文件
- ✅ 4 线程并发下载

## 安装依赖

```bash
pip install requests
```

## 使用方法

```bash
python photoplus_downloader.py <photoplus_url> [output_dir]
```

### 示例

```bash
# 基本用法
python photoplus_downloader.py "https://live.photoplus.cn/live/pc/77524334/#/live"

# 指定输出目录
python photoplus_downloader.py "https://live.photoplus.cn/live/pc/77524334/#/live" "./my_album"

# 只传 activityNo
python photoplus_downloader.py 77524334
```

## 支持的 URL 格式

- `https://live.photoplus.cn/live/pc/{activityNo}/#/live`
- `https://live.photoplus.cn/live/{activityNo}`
- 直接传数字 activityNo

## 技术说明

### API 签名算法

通过逆向 JS 混淆代码提取：

```
签名 = md5(按字母排序的参数字符串 + "laxiaoheiwu")
```

例如请求 `/pic/list` 时：
```
params = "activityNo=77524334&count=200&isNew=false&key=&page=1&ppSign=&size=200&_t=1777723589890"
sign   = md5(params + "laxiaoheiwu")
       = "d60a7ecc32ea5738565a3da5ea398d3e"
```

### 图片质量

| 字段 | 格式 | 大小 | 说明 |
|------|------|------|------|
| `origin_img` | `~tplv-...-size:XXXXXXX.jpeg` | ~1.5-2.5MB | **推荐**，保留原图分辨率（如 3160×2106） |
| `big_img` | `~tplv-...-resize-animforce-v1:1600:3000:gif.JPG` | ~200-600KB | 1600px 长边压缩版 |
| `raw` | `.heic` (去 tplv 后缀) | 原始文件 | 需要浏览器 session，403 Forbidden |

本工具默认下载 `origin_img`（高质量 JPEG）。

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/pic/list` | GET | 获取照片列表 |
| `/live/detail` | GET | 获取活动详情 |
| `/album/albums` | GET | 获取相册列表 |

## License

MIT
