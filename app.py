import io
import json
import zipfile
from typing import Tuple

import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(page_title="CraftPoster Web", page_icon="🖼️", layout="wide")
st.title("🖼️ CraftPoster Web")
st.write("Minecraft 1.21.4+ 向けカスタム絵画＆アイテム生成ツール")

# 外部 CSS 読み込み（拡張しやすいスタイル管理）
def load_local_css(file_name: str) -> None:
    with open(file_name, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_local_css("styles.css")

# ==========================================
# サイドバー：設定オプション
# ==========================================
st.sidebar.header("⚙️ 設定オプション")

# 1. 解像度設定（1ブロックあたりのピクセル数）
px_per_block = st.sidebar.selectbox(
    "1ブロックあたりの解像度 (px)",
    options=[16, 32, 64, 128],
    index=0,
    help="標準のマイクラ解像度は16pxです。高い値にすると高精細になります。"
)

# Namespace設定
namespace = st.sidebar.text_input("ネームスペース (namespace)", value="custom", help="英小文字とアンダースコアのみ")

# ==========================================
# 画像処理関数
# ==========================================
def resize_image_stretch(img: Image.Image, width_blocks: int, height_blocks: int, px_per_block: int) -> Image.Image:
    """指定されたブロック数に合わせて変形（ストレッチ）リサイズを行う"""
    target_w = width_blocks * px_per_block
    target_h = height_blocks * px_per_block
    return img.convert("RGBA").resize((target_w, target_h), Image.Resampling.LANCZOS)


def resolve_crop_aspect_ratio(width_blocks: int, height_blocks: int) -> Tuple[int, int]:
    """トリミング枠のアスペクト比をブロックサイズの比率から計算する"""
    width = max(1, int(width_blocks))
    height = max(1, int(height_blocks))
    return (width, height)


def centered_box_algorithm(img: Image.Image, aspect_ratio: Tuple[int, int] = None):
    """初期トリミング枠を画像中央に配置する box_algorithm 互換関数"""
    img_w, img_h = img.size

    if aspect_ratio is None:
        aspect_ratio = (1, 1)

    target_w, target_h = map(float, aspect_ratio)
    target_ratio = target_w / target_h

    # 画像の50%サイズを基準として、アスペクト比に合わせた枠を計算
    max_crop_w = int(img_w * 0.5)
    max_crop_h = int(img_h * 0.5)

    # アスペクト比を保ちながら、max_crop_w と max_crop_h を超えないサイズに調整
    base_ratio = img_w / img_h
    
    if target_ratio > base_ratio:
        # 横が長い比率
        crop_h = max_crop_h
        crop_w = int(crop_h * target_ratio)
        if crop_w > max_crop_w:
            crop_w = max_crop_w
            crop_h = int(crop_w / target_ratio)
    else:
        # 縦が長い比率
        crop_w = max_crop_w
        crop_h = int(crop_w / target_ratio)
        if crop_h > max_crop_h:
            crop_h = max_crop_h
            crop_w = int(crop_h * target_ratio)

    # 中央に配置
    left = (img_w - crop_w) // 2
    top = (img_h - crop_h) // 2

    return {
        "left": left,
        "top": top,
        "width": crop_w,
        "height": crop_h,
    }

# ==========================================
# ZIPパッケージ自動生成関数 (1.21.4+対応)
# ==========================================
def create_packs_zip(posters: list, namespace: str) -> bytes:
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # --- 1. リソースパック (Resource Pack) ---
        # pack.mcmeta (Format 48)
        rp_mcmeta = {
            "pack": {
                "pack_format": 48,
                "description": "CraftPoster Web Generated Resource Pack"
            }
        }
        zip_file.writestr("resource_pack/pack.mcmeta", json.dumps(rp_mcmeta, indent=2))

        # --- 2. データパック (Data Pack) ---
        # pack.mcmeta (Format 61)
        dp_mcmeta = {
            "pack": {
                "pack_format": 61,
                "description": "CraftPoster Web Generated Data Pack"
            }
        }
        zip_file.writestr("data_pack/pack.mcmeta", json.dumps(dp_mcmeta, indent=2))

        # Placeable Painting Tag
        placeable_values = []

        # --- 各ポスターのデータ出力 ---
        for poster in posters:
            p_id = poster["id"]
            w = poster["width"]
            h = poster["height"]
            img = poster["image"]

            # テクスチャ画像出力 (RGBA PNG)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            img_bytes = img_byte_arr.getvalue()

            # Resource Pack Files
            zip_file.writestr(f"resource_pack/assets/{namespace}/textures/item/{p_id}.png", img_bytes)
            zip_file.writestr(f"resource_pack/assets/{namespace}/textures/painting/{p_id}.png", img_bytes)

            # Item Model Definition (1.21.4+)
            item_def = {
                "model": {
                    "type": "minecraft:model",
                    "model": f"{namespace}:item/{p_id}"
                }
            }
            zip_file.writestr(f"resource_pack/assets/{namespace}/items/{p_id}.json", json.dumps(item_def, indent=2))

            # Model JSON
            model_def = {
                "parent": "minecraft:item/generated",
                "textures": {
                    "layer0": f"{namespace}:item/{p_id}"
                }
            }
            zip_file.writestr(f"resource_pack/assets/{namespace}/models/item/{p_id}.json", json.dumps(model_def, indent=2))

            # Data Pack Files: Painting Variant
            painting_variant = {
                "asset_id": f"{namespace}:{p_id}",
                "width": w,
                "height": h
            }
            zip_file.writestr(f"data_pack/data/{namespace}/painting_variant/{p_id}.json", json.dumps(painting_variant, indent=2))

            placeable_values.append(f"{namespace}:{p_id}")

        # Placeable Tag
        placeable_tag = {
            "values": placeable_values
        }
        zip_file.writestr("data_pack/data/minecraft/tags/painting_variant/placeable.json", json.dumps(placeable_tag, indent=2))

    return zip_buffer.getvalue()

# ==========================================
# メイン画面：画像アップロード＆処理
# ==========================================
uploaded_files = st.file_uploader(
    "ポスターにしたい画像をアップロードしてください", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader("📋 ポスター個別設定")
    
    processed_posters = []
    
    for idx, uploaded_file in enumerate(uploaded_files):
        st.markdown(f"### 🖼️ 画像 {idx + 1}: `{uploaded_file.name}`")
        
        try:
            raw_img = Image.open(uploaded_file)
            
            # st_cropper の TypeError 対策 (RGB変換)
            crop_target_img = raw_img.convert("RGB")
            
            col1, col2 = st.columns([1, 1])
            
            default_id = f"poster_{idx + 1}"
            poster_id = st.text_input("ポスターID", value=default_id, key=f"id_{idx}")
            width_b = st.number_input("横サイズ (ブロック)", min_value=1, max_value=16, value=1, key=f"w_{idx}")
            height_b = st.number_input("縦サイズ (ブロック)", min_value=1, max_value=16, value=1, key=f"h_{idx}")
            crop_aspect = resolve_crop_aspect_ratio(width_b, height_b)
            # サイズ変更時に枠を再生成するため、crop_key に width/height を含める
            crop_key = f"cropper_{idx}_{uploaded_file.name}_{width_b}_{height_b}"

            with col1:
                st.write("✂️ **トリミング範囲を選択**")
                cropped_img = st_cropper(
                    crop_target_img,
                    realtime_update=True,
                    box_color='#FF0000',
                    aspect_ratio=crop_aspect,
                    box_algorithm=centered_box_algorithm,
                    key=crop_key
                )
            
            with col2:
                st.write("🔍 **プレビュー & 設定**")
                if cropped_img is not None:
                    cropped_rgba = cropped_img.convert("RGBA")
                    
                    resized_result = resize_image_stretch(cropped_rgba, width_b, height_b, px_per_block)
                    st.image(resized_result, caption=f"出力プレビュー ({width_b*px_per_block}x{height_b*px_per_block}px)", use_container_width=True)
                    
                    processed_posters.append({
                        "id": poster_id,
                        "width": width_b,
                        "height": height_b,
                        "image": resized_result
                    })

        except Exception as e:
            st.error(f"画像の処理中にエラーが発生しました: {e}")

        st.divider()

    # ==========================================
    # パック作成＆ダウンロードセクション
    # ==========================================
    if processed_posters:
        st.subheader("📦 パックの書き出し")
        
        zip_bytes = create_packs_zip(processed_posters, namespace)
        
        st.download_button(
            label="⬇️ リソースパック＆データパック (ZIP) をダウンロード",
            data=zip_bytes,
            file_name="CraftPoster_Packs.zip",
            mime="application/zip",
            use_container_width=True
        )