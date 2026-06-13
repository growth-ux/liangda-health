from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT_DIR / "frontend" / "public" / "mall-products"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_CATEGORIES = {
    "oil": "http://www.fu800.cn/index.php/Mall/productlist.html?cid=422",
}

PRODUCT_CATEGORY = {
    "prod_low_sodium_soy": "seasoning",
    "prod_low_gi_rice": "rice_flour",
    "prod_high_calcium_milk": "dairy",
    "prod_olive_oil": "oil",
    "prod_sugar_free_yogurt": "dairy",
    "prod_buckwheat_noodle": "rice_flour",
    "prod_low_sodium_salt": "seasoning",
    "prod_calcium_biscuit": "snacks",
    "prod_walnut_oil": "oil",
    "prod_oat_milk": "beverages",
    "prod_brown_rice": "grains",
    "prod_canola_oil": "oil",
}

PRODUCT_MATCH_RULES = {
    "prod_olive_oil": [["橄榄油"]],
    "prod_walnut_oil": [["核桃油"], ["亚麻籽油"], ["红花籽油"]],
    "prod_canola_oil": [["菜籽油"], ["双低"], ["玉米油"]],
    "prod_low_gi_rice": [["大米"], ["胚芽米"], ["稻米"]],
    "prod_brown_rice": [["糙米"], ["杂粮", "礼盒"]],
    "prod_buckwheat_noodle": [["荞麦"], ["面"]],
    "prod_low_sodium_soy": [["生抽"], ["酱油"]],
    "prod_low_sodium_salt": [["低钠盐"], ["食用盐"]],
    "prod_calcium_biscuit": [["饼干"]],
    "prod_oat_milk": [["燕麦"]],
    "prod_high_calcium_milk": [["高钙", "牛奶"], ["牛奶"]],
    "prod_sugar_free_yogurt": [["酸奶"]],
}


@dataclass(frozen=True)
class RemoteProductImage:
    title: str
    url: str
    source_page: str
    goods_id: str | None = None


class ProductImageParser(HTMLParser):
    def __init__(self, page_url: str):
        super().__init__()
        self.page_url = page_url
        self.images: list[RemoteProductImage] = []
        self._current_goods_id: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if value}

        if tag.lower() == "a":
            href = attr_map.get("href", "")
            match = re.search(r"(?:productinfo\.html\?id=|goods\.php\?id=)(\d+)", href)
            self._current_goods_id = match.group(1) if match else None
            return

        if tag.lower() != "img":
            return

        title = attr_map.get("title") or attr_map.get("alt") or ""
        image_url = attr_map.get("data-original") or attr_map.get("src") or ""
        if not title or "/upfiles/good/" not in image_url:
            return

        self.images.append(
            RemoteProductImage(
                title=title.strip(),
                url=urljoin(self.page_url, image_url),
                source_page=self.page_url,
                goods_id=self._current_goods_id,
            )
        )


def fetch_category_images(url: str) -> list[RemoteProductImage]:
    if url.startswith("@"):
        return read_local_images(Path(url[1:]))
    if "mall.jd.com/view_search-" in url:
        return fetch_jd_shop_images(url)

    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    parser = ProductImageParser(url)
    parser.feed(response.text)
    return parser.images


def fetch_jd_shop_images(url: str) -> list[RemoteProductImage]:
    parsed = urlparse(url)
    parts = Path(parsed.path).stem.split("-")
    if len(parts) < 7 or parts[0] != "view_search":
        return []

    page_response = requests.get(url, headers=HEADERS, timeout=20)
    page_response.raise_for_status()
    page_html = page_response.text
    shop_id = extract_first(page_html, r'var shopId = "(\d+)"') or parts[3]
    vender_id = (
        extract_first(page_html, r"params\.venderId\s*=\s*(\d+)")
        or extract_first(page_html, r"\+\s*-\s*'(\d+)'\s*\+\s*-\s*'\d+'")
        or extract_first(page_html, r"venderId=(\d+)")
        or parts[2]
    )
    page_instance_id = extract_first(page_html, r'id="pageInstance_id"\s+value="(\d+)"') or ""
    render = extract_jd_render_params(page_html)

    category_id = parts[2]
    order_by = parts[3]
    direction = parts[4]
    page_size = parts[5]
    page_no = parts[6]
    params = {
        "pageNo": page_no,
        "pagePrototypeId": "8",
        "orderBy": order_by,
        "pageSize": page_size,
        "categoryId": category_id,
        "direction": direction,
        "pageInstanceId": render.get("page") or page_instance_id,
        "moduleInstanceId": render.get("instance") or "",
        "prototypeId": render.get("prototype") or "55555",
        "templateId": render.get("template") or "905542",
        "appId": parts[1],
        "layoutInstanceId": render.get("layout") or render.get("instance") or "",
        "origin": "0",
        "shopId": shop_id,
        "venderId": vender_id,
        "callback": "jshop_module_render_callback",
    }
    module_url = f"https://module-jshop.jd.com/module/getModuleHtml.html?{urlencode(params)}"
    response = requests.get(module_url, headers={**HEADERS, "Referer": url}, timeout=20)
    response.raise_for_status()
    return parse_jd_module_images(response.text, url)


def extract_first(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def extract_jd_render_params(page_html: str) -> dict[str, str]:
    structure_match = re.search(r'<div class="m_render_structure\b(?P<attrs>[^>]*)>', page_html)
    if not structure_match:
        return {}

    attrs = dict(re.findall(r'(m_render_[A-Za-z_]+)="([^"]+)"', structure_match.group("attrs")))
    return {
        "page": attrs.get("m_render_pageInstance_id", ""),
        "layout": attrs.get("m_render_layout_instance_id", ""),
        "prototype": attrs.get("m_render_prototype_id", ""),
        "template": attrs.get("m_render_template_id", ""),
        "instance": attrs.get("m_render_instance_id", ""),
        "app": attrs.get("m_render_app_id", ""),
    }


def parse_jd_module_images(raw: str, source_page: str) -> list[RemoteProductImage]:
    callback_match = re.search(r"jshop_module_render_callback\((.*)\)\s*$", raw, re.DOTALL)
    if callback_match:
        data = json.loads(callback_match.group(1))
        raw = data.get("moduleText", "")

    items: list[RemoteProductImage] = []
    blocks = re.findall(
        r'<li class="jSubObject gl-item">(?P<block>.*?)(?=<li class="jSubObject gl-item">|</ul>\s*<span class="clr">)',
        raw,
        re.DOTALL,
    )

    for block in blocks:
        image_match = re.search(r'(?:original|src)="(?P<url>//img[^"]+?/n7/[^"]+?)"', block)
        title_match = re.search(r'<div class="jDesc">\s*<a [^>]* title="(?P<title>.*?)"', block, re.DOTALL)
        sku_match = re.search(r"item\.jd\.com/(?P<sku>\d+)\.html", block)
        if not image_match or not title_match:
            continue
        title = title_match.group("title")
        image_url = image_match.group("url")
        items.append(
            RemoteProductImage(
                title=title,
                url=urljoin("https:", image_url),
                source_page=source_page,
                goods_id=sku_match.group("sku") if sku_match else None,
            )
        )

    deduped: list[RemoteProductImage] = []
    seen: set[str] = set()
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        deduped.append(item)
    return deduped


def read_local_images(path: Path) -> list[RemoteProductImage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("本地图片清单必须是数组")

    images: list[RemoteProductImage] = []
    for index, item in enumerate(data, start=1):
        if isinstance(item, str):
            images.append(
                RemoteProductImage(title=f"image-{index}", url=item, source_page=str(path))
            )
        elif isinstance(item, dict) and item.get("url"):
            images.append(
                RemoteProductImage(
                    title=str(item.get("title") or f"image-{index}"),
                    url=str(item["url"]),
                    source_page=str(path),
                    goods_id=str(item.get("goods_id") or "") or None,
                )
            )
    return images


def guess_category_from_url(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    cid = query.get("cid", ["unknown"])[0]
    return f"cid-{cid}"


def parse_category_arg(value: str) -> tuple[str, str]:
    if "=" in value:
        category, url = value.split("=", 1)
        return category.strip(), url.strip()
    return guess_category_from_url(value), value.strip()


def parse_categories(args: list[str]) -> dict[str, str]:
    if not args:
        return DEFAULT_CATEGORIES
    return dict(parse_category_arg(arg) for arg in args)


def guess_extension(response: requests.Response, url: str) -> str:
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type) if content_type else None
    if extension:
        return ".jpg" if extension == ".jpe" else extension

    match = re.search(r"\.(png|jpg|jpeg|webp)(?:\?|$)", url, re.IGNORECASE)
    if match:
        ext = match.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    return ".png"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-")
    return slug[:48] or "product"


def download_image(category: str, index: int, image: RemoteProductImage) -> str:
    response = requests.get(image.url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    extension = guess_extension(response, image.url)
    digest = hashlib.sha1(image.url.encode("utf-8")).hexdigest()[:8]
    goods_prefix = image.goods_id or f"{index:03d}"
    filename = f"{goods_prefix}-{safe_slug(image.title)}-{digest}{extension}"
    output_dir = OUTPUT_ROOT / category
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_bytes(response.content)
    return f"/mall-products/{category}/{filename}"


def match_score(title: str, keyword_groups: list[list[str]]) -> int:
    normalized_title = title.lower()
    return sum(
        1
        for keywords in keyword_groups
        if all(keyword.lower() in normalized_title for keyword in keywords)
    )


def choose_product_images(manifest: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    chosen: dict[str, str] = {}
    for product_id, category in PRODUCT_CATEGORY.items():
        images = manifest.get(category, [])
        keyword_groups = PRODUCT_MATCH_RULES.get(product_id, [])
        scored = [
            (match_score(image["title"], keyword_groups), image)
            for image in images
            if keyword_groups and match_score(image["title"], keyword_groups) > 0
        ]
        if not scored and images and not keyword_groups:
            scored = [(0, image) for image in images]
        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            chosen[product_id] = scored[0][1]["local_url"]
    return chosen


def update_database(product_images: dict[str, str]) -> None:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

    try:
        from app.db.session import SessionLocal
        from app.models.mall import MallProduct

        db = SessionLocal()
        try:
            for product_id, image_url in product_images.items():
                product = db.query(MallProduct).filter(MallProduct.product_id == product_id).one_or_none()
                if product:
                    product.image_url = image_url
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        print(f"数据库未更新：{exc}")


def write_manifests(manifest: dict[str, list[dict[str, str]]], product_images: dict[str, str]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    root_manifest_path = OUTPUT_ROOT / "manifest.json"

    for category, items in manifest.items():
        category_dir = OUTPUT_ROOT / category
        category_dir.mkdir(parents=True, exist_ok=True)
        (category_dir / "manifest.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    merged_manifest: dict[str, list[dict[str, str]]] = {}
    for category_manifest_path in sorted(OUTPUT_ROOT.glob("*/manifest.json")):
        try:
            items = json.loads(category_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(items, list):
            merged_manifest[category_manifest_path.parent.name] = items

    merged_product_images = choose_product_images(merged_manifest)

    root_manifest_path.write_text(
        json.dumps(
            {
                "categories": merged_manifest,
                "product_images": merged_product_images,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def scrape(categories: dict[str, str]) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    manifest: dict[str, list[dict[str, str]]] = {}
    seen_urls: set[str] = set()

    for category, url in categories.items():
        images = fetch_category_images(url)
        category_items: list[dict[str, str]] = []
        for index, image in enumerate(images, start=1):
            if image.url in seen_urls:
                continue
            seen_urls.add(image.url)
            local_url = download_image(category, index, image)
            category_items.append(
                {
                    "title": image.title,
                    "goods_id": image.goods_id or "",
                    "source_page": image.source_page,
                    "source_url": image.url,
                    "local_url": local_url,
                }
            )
        manifest[category] = category_items

    product_images = choose_product_images(manifest)
    return manifest, product_images


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取福800商城商品图到本地分类目录")
    parser.add_argument(
        "categories",
        nargs="*",
        help="分类配置，格式 category_code=url 或 category_code=@本地图片清单.json；不传时默认抓取 oil=cid422",
    )
    parser.add_argument("--no-db", action="store_true", help="只抓图片，不更新数据库 image_url")
    args = parser.parse_args()

    categories = parse_categories(args.categories)
    manifest, product_images = scrape(categories)
    write_manifests(manifest, product_images)
    if not args.no_db:
        update_database(product_images)

    total = sum(len(items) for items in manifest.values())
    print(f"已抓取 {total} 张商品图")
    for category, items in manifest.items():
        print(f"- {category}: {len(items)} 张 -> {OUTPUT_ROOT / category}")
    print(f"总映射文件：{OUTPUT_ROOT / 'manifest.json'}")


if __name__ == "__main__":
    main()
