#!/usr/bin/env python3
"""
Photoplus 照片批量下载器
支持从 live.photoplus.cn 活动页面下载原始照片
"""

import os
import re
import sys
import time
import hashlib
import json
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = 'https://live.photoplus.cn'
SIGN_SECRET = 'laxiaoheiwu'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': '',
}


def generate_sign(params: dict) -> dict:
    """生成 photoplus API 签名"""
    timestamp = str(int(time.time() * 1000))
    params = dict(params)
    params['_t'] = timestamp
    
    sorted_keys = sorted(params.keys())
    parts = [f"{k}={params[k]}" for k in sorted_keys]
    param_str = '&'.join(parts)
    
    sign = hashlib.md5((param_str + SIGN_SECRET).encode()).hexdigest()
    params['_s'] = sign
    return params


def fetch_photo_list(activity_no: str, page: int = 1, size: int = 200) -> list:
    """获取照片列表"""
    params = {
        'activityNo': activity_no,
        'key': '',
        'isNew': 'false',
        'count': '200',
        'page': str(page),
        'size': str(size),
        'ppSign': '',
    }
    signed = generate_sign(params)
    
    headers = dict(HEADERS)
    headers['Referer'] = f'https://live.photoplus.cn/live/pc/{activity_no}/'
    
    try:
        r = requests.get(f'{BASE_URL}/pic/list', params=signed, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if data.get('success') and data.get('result'):
            return data['result'].get('pics_array', [])
        else:
            print(f'  API warning: code={data.get("code")}, msg={data.get("message")}')
            return []
    except Exception as e:
        print(f'  Error fetching page {page}: {e}')
        return []


def get_best_url(pic: dict) -> str:
    """获取最佳下载 URL
    
    origin_img 包含 ~tplv-...-size:XXXXXXX.jpeg 后缀，是高质量 JPEG 版本，
    保留了原图分辨率（如 3160x2106），单张约 1.5-2.5MB。
    big_img 是 ~tplv-...-resize-animforce-v1:1600:3000:gif.JPG，只有 1600px 长边。
    
    策略：优先使用 origin_img（高质量 JPEG）。
    """
    url = pic.get('origin_img', '')
    if not url:
        url = pic.get('big_img', '')
    
    if url.startswith('//'):
        url = 'https:' + url
    
    return url


def get_safe_filename(pic: dict, idx: int) -> str:
    """生成安全的文件名"""
    name = pic.get('name', '')
    if not name:
        name = f"photo_{idx:04d}"
    
    # Clean filename
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    
    # Ensure extension from URL
    url = get_best_url(pic)
    parsed = urlparse(url)
    path = parsed.path
    
    # Extract extension from the path, handling ~tplv- suffixes
    # e.g. DSC0981.heic~tplv-9lv23dm2t1-size:2031890.jpeg -> .jpeg
    # e.g. DSC1646.heic~tplv-9lv23dm2t1-resize-animforce-v1:1600:3000:gif.JPG -> .JPG
    ext = ''
    if '~' in path:
        # The processed extension is after the last dot in the tplv suffix
        suffix_part = path.split('~')[1]  # tplv-...-size:2031890.jpeg
        if '.' in suffix_part:
            ext = '.' + suffix_part.split('.')[-1]
    else:
        ext = os.path.splitext(path)[1]
    
    if ext and not name.lower().endswith(ext.lower()):
        name = name + ext
    
    # If still no extension, use .jpg
    if not os.path.splitext(name)[1]:
        name += '.jpg'
    
    return name


def download_with_requests(url: str, filepath: str, headers: dict, retries: int = 3) -> bool:
    """使用 requests 下载"""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=60, stream=True)
            r.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            size = os.path.getsize(filepath)
            if size > 1000:
                return True
            else:
                os.remove(filepath)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
    return False


def download_with_playwright(url: str, filepath: str, page) -> bool:
    """使用 Playwright 下载（用于有防盗链的图片）"""
    try:
        # 在浏览器中 fetch 图片数据
        result = page.evaluate("""async (url) => {
            const resp = await fetch(url, { credentials: 'include' });
            if (!resp.ok) return { ok: false, status: resp.status };
            const blob = await resp.blob();
            const reader = new FileReader();
            return new Promise((resolve) => {
                reader.onloadend = () => {
                    const base64 = reader.result.split(',')[1];
                    resolve({ ok: true, size: blob.size, data: base64 });
                };
                reader.readAsDataURL(blob);
            });
        }""", url)
        
        if not result.get('ok'):
            print(f'    Browser fetch failed: {result.get("status")}')
            return False
        
        import base64
        data = base64.b64decode(result['data'])
        with open(filepath, 'wb') as f:
            f.write(data)
        
        return len(data) > 1000
    except Exception as e:
        print(f'    Browser download error: {e}')
        return False


def download_photo(pic: dict, idx: int, output_dir: str, page=None) -> bool:
    """下载单张照片"""
    url = get_best_url(pic)
    filename = get_safe_filename(pic, idx)
    filepath = os.path.join(output_dir, filename)
    
    # Skip if already exists and not empty
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return True
    
    # Try with requests first
    headers = dict(HEADERS)
    headers['Referer'] = 'https://live.photoplus.cn/'
    
    if download_with_requests(url, filepath, headers):
        return True
    
    # Fallback to Playwright if available
    if page is not None:
        return download_with_playwright(url, filepath, page)
    
    return False


def extract_activity_no(url: str) -> str:
    """从 photoplus URL 中提取 activityNo"""
    m = re.search(r'/live/pc/(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'/live/(\d+)', url)
    if m:
        return m.group(1)
    if url.isdigit():
        return url
    raise ValueError(f'Cannot extract activityNo from: {url}')


def main():
    if len(sys.argv) < 2:
        print('Usage: python photoplus_downloader.py <photoplus_url_or_activityNo> [output_dir]')
        print('Example: python photoplus_downloader.py https://live.photoplus.cn/live/pc/77524334/#/live')
        sys.exit(1)
    
    input_url = sys.argv[1]
    activity_no = extract_activity_no(input_url)
    
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        output_dir = f'photoplus_{activity_no}'
    
    os.makedirs(output_dir, exist_ok=True)
    print(f'Target: activityNo={activity_no}')
    print(f'Output: {os.path.abspath(output_dir)}')
    print()
    
    # Fetch all photos
    print('Fetching photo list...')
    all_photos = []
    page = 1
    while True:
        photos = fetch_photo_list(activity_no, page=page, size=200)
        if not photos:
            break
        all_photos.extend(photos)
        print(f'  Page {page}: got {len(photos)} photos (total: {len(all_photos)})')
        if len(photos) < 200:
            break
        page += 1
        time.sleep(0.5)
    
    print(f'\nTotal photos to download: {len(all_photos)}')
    if not all_photos:
        print('No photos found.')
        return
    
    # Check if we need Playwright fallback
    print('\nTesting CDN access...')
    test_url = get_best_url(all_photos[0])
    test_ok = download_with_requests(test_url, os.path.join(output_dir, '_test.jpg'), {
        'User-Agent': HEADERS['User-Agent'],
        'Referer': 'https://live.photoplus.cn/',
    })
    
    use_playwright = not test_ok
    if use_playwright:
        print('CDN requires browser context. Launching Playwright...')
        os.remove(os.path.join(output_dir, '_test.jpg'))
    else:
        print('CDN accessible via requests.')
        os.remove(os.path.join(output_dir, '_test.jpg'))
    
    # Download photos
    print('\nDownloading...')
    success = 0
    failed = 0
    skipped = 0
    
    if use_playwright:
        # Use Playwright for all downloads
        import asyncio
        from playwright.async_api import async_playwright
        
        async def download_all():
            nonlocal success, failed, skipped
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent=HEADERS['User-Agent']
                )
                page = await ctx.new_page()
                await page.goto(f'https://live.photoplus.cn/live/pc/{activity_no}/', wait_until='domcontentloaded')
                await asyncio.sleep(2)
                
                for idx, pic in enumerate(all_photos, 1):
                    url = get_best_url(pic)
                    filename = get_safe_filename(pic, idx)
                    filepath = os.path.join(output_dir, filename)
                    
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                        skipped += 1
                        continue
                    
                    ok = await asyncio.get_event_loop().run_in_executor(
                        None, download_photo, pic, idx, output_dir, page
                    )
                    if ok:
                        success += 1
                        print(f'  [{idx}/{len(all_photos)}] OK: {filename}')
                    else:
                        failed += 1
                        print(f'  [{idx}/{len(all_photos)}] FAIL: {filename}')
                
                await browser.close()
        
        asyncio.run(download_all())
    else:
        # Use threaded requests
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for idx, pic in enumerate(all_photos, 1):
                filename = get_safe_filename(pic, idx)
                filepath = os.path.join(output_dir, filename)
                
                if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                    skipped += 1
                    continue
                
                future = executor.submit(download_photo, pic, idx, output_dir, None)
                futures[future] = (idx, filename)
            
            for future in as_completed(futures):
                idx, filename = futures[future]
                try:
                    ok = future.result()
                    if ok:
                        success += 1
                        print(f'  [{idx}/{len(all_photos)}] OK: {filename}')
                    else:
                        failed += 1
                        print(f'  [{idx}/{len(all_photos)}] FAIL: {filename}')
                except Exception as e:
                    failed += 1
                    print(f'  [{idx}/{len(all_photos)}] ERROR: {filename} - {e}')
    
    print(f'\nDone! Success: {success}, Failed: {failed}, Skipped: {skipped}')


if __name__ == '__main__':
    main()
