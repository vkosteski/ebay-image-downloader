"""
download_ebay_images.py

Downloads main images from eBay listings provided in a JSON file.
Saves images into organized folders and writes a summary JSON.

Usage:
    python download_ebay_images.py --input gallery.json --output gallery_test5.json --img_root ebay_by_title
"""

import json
import os
import asyncio
import argparse
from typing import Optional, Dict, List, Any
from playwright.async_api import async_playwright, Page


async def get_main_img_url(page: Page, ebay_url: str) -> Optional[str]:
    """
    Extracts the main image URL from an eBay item page.

    Args:
        page (Page): Playwright page object.
        ebay_url (str): The URL of the eBay item.

    Returns:
        Optional[str]: The image URL if found, otherwise None.
    """
    await page.goto(ebay_url, timeout=60000)
    await page.wait_for_timeout(2500)
    # Try og:image
    og_image = await page.locator("meta[property='og:image']").get_attribute("content")
    if og_image:
        return og_image
    # Try img#icImg
    img_src = await page.locator("#icImg").get_attribute("src")
    if img_src:
        # Try to upgrade to highest resolution
        if "s-l" in img_src:
            return img_src.replace("s-l500", "s-l1600").replace("s-l1200", "s-l1600")
        return img_src
    return None


async def download_image(page: Page, img_url: str, save_path: str) -> bool:
    """
    Downloads an image from the given URL using Playwright.

    Args:
        page (Page): Playwright page object.
        img_url (str): Image URL.
        save_path (str): Local file path to save the image.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        img_resp = await page.goto(img_url)
        img_bytes = await img_resp.body()
        with open(save_path, "wb") as f:
            f.write(img_bytes)
        return True
    except Exception as e:
        print(f"  [!] Exception: {e} for {img_url}")
        return False


async def process_gallery(
    input_file: str, output_file: str, img_root: str
) -> None:
    """
    Loads the gallery JSON, downloads images, and saves the results.

    Args:
        input_file (str): Path to input JSON.
        output_file (str): Path to output JSON.
        img_root (str): Root directory for images.
    """
    with open(input_file, encoding="utf-8") as f:
        gallery = json.load(f)

    output: List[Dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for item in gallery:
            ebay_url = item.get("ebay_url", "")
            item_id = item.get("id")
            folder = item.get("folder", "Unknown").strip()
            if not ebay_url or not item_id:
                print(f"  [!] Skipping item missing ebay_url or id: {item}")
                continue
            print(f"Processing: {item_id} - {ebay_url}")
            img_url = await get_main_img_url(page, ebay_url)
            if not img_url:
                print(f"  [!] No main image for: {ebay_url}")
                continue
            print(f"  [*] Image URL: {img_url}")
            folder_path = os.path.join(img_root, folder)
            os.makedirs(folder_path, exist_ok=True)
            img_fn = f"{item_id}.jpg"
            img_fp = os.path.join(folder_path, img_fn)
            success = await download_image(page, img_url, img_fp)
            if success:
                item["filename"] = img_fn
                output.append(item)
                print(f"  [*] Image saved: {img_fp}")
            else:
                print(f"  [!] Failed to save image for: {ebay_url}")
        await browser.close()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nAll done! See {output_file} and images in {img_root}/")


def parse_args():
    parser = argparse.ArgumentParser(description="Download main images from eBay listings.")
    parser.add_argument("--input", default="gallery.json", help="Input JSON file (default: gallery.json)")
    parser.add_argument("--output", default="gallery_test5.json", help="Output JSON file (default: gallery_test5.json)")
    parser.add_argument("--img_root", default="ebay_by_title", help="Root folder to save images (default: ebay_by_title)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(process_gallery(args.input, args.output, args.img_root))
