import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper
import io
import zipfile
import json

# ページ基本設定
st.set_page_config(page_title="CraftPoster Web", page_icon="🖼️", layout="wide")

st.title("🖼️ CraftPoster Web")
st.write("Minecraft 1.21.4+ 向けカスタム絵画＆アイテム生成ツール")

# サイドバー：設定オプション
st.sidebar.header("⚙️ 設定オプション")

# 1. 解像度設定（1ブロックあたりのピクセル数）
px_per_block = st.sidebar.selectbox(
    "1ブロックあたりの解像度 (px)",
    options=[16, 32, 64, 128],
    index=0,
    help="標準のマイクラ解像度は16pxです。高い値にすると高精細になります。"
)

# --- 画像処理関数 (変形モード用) ---
def resize_image_stretch(img: Image.Image, width_blocks: int, height_blocks: int, px_per_block: int) -> Image.Image:
    target_w = width_blocks * px_per_block
    target_h = height_blocks * px_per_block
    return img.convert("RGBA").resize((target_w, target_h), Image.Resampling.LANCZOS)

# メイン画面：画像アップロード
uploaded_files = st.file_uploader("ポスターにしたい画像をアップロードしてください", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("📋 ポスター個別設定")
    
    processed_data_list = []
    
    for idx, uploaded_file in enumerate(uploaded_files):
        st.write("---")
        st.write(f"📂 **画像 #{idx+1}: {uploaded_file.name}**")
        
        # 画面レイアウト分割
        col_settings, col_cropper = st.columns([1, 2])
        
        raw_img = Image.open(uploaded_file)
        
        with col_settings:
            poster_id = st.text_input("ポスターID", value=f"poster_{idx+1}", key=f"id_{idx}")
            
            c1, c2 = st.columns(2)
            with c1:
                w_blocks = st.number_input("横幅 (ブロック数)", min_value=1, max_value=16, value=2, key=f"w_{idx}")
            with c2:
                h_blocks = st.number_input("高さ (ブロック数)", min_value=1, max_value=16, value=1, key=f"h_{idx}")

            crop_mode = st.radio(
                "画像調整モード",
                options=["自由切り抜き (マウス操作)", "変形 (全域を伸ばしてフィット)"],
                index=0,
                key=f"mode_{idx}",
                help="「自由切り抜き」では、右側の画像上で範囲をマウス操作できます。"
            )
            
            final_processed_img = None

        with col_cropper:
            if crop_mode == "自由切り抜き (マウス操作)":
                st.write("🎯 **切り抜き範囲をドラッグで指定してください**")
                
                # アスペクト比を float (数値) に計算
                aspect_ratio_val = float(w_blocks) / float(h_blocks) if h_blocks > 0 else 1.0
                
                # RGBに安全変換
                raw_img_rgb = raw_img.convert("RGB")
                
                try:
                    # st_cropper 呼び出し
                    cropped_img = st_cropper(
                        raw_img_rgb,
                        realtime_update=True,
                        box_color='#FF0000',
                        aspect_ratio=aspect_ratio_val,
                        frame_width=2,
                        key=f"cropper_{idx}"
                    )
                except Exception as e:
                    # クロップ処理中にエラーが起きた場合は元画像をフォールバック使用
                    cropped_img = raw_img_rgb
                
                # 目標解像度（px）にリサイズ
                target_w_px = w_blocks * px_per_block
                target_h_px = h_blocks * px_per_block
                
                if isinstance(cropped_img, Image.Image):
                    final_processed_img = cropped_img.convert("RGBA").resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
                else:
                    final_processed_img = raw_img.convert("RGBA").resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
                    
            else:
                # 変形モード
                final_processed_img = resize_image_stretch(raw_img, w_blocks, h_blocks, px_per_block)
                st.image(raw_img, caption="元画像プレビュー (変形適用前)", use_container_width=True)

        # プレビュー表示とデータ格納
        with col_settings:
            if final_processed_img:
                st.write(f"🎮 **最終出力サイズ:** {w_blocks * px_per_block} x {h_blocks * px_per_block} px")
                st.image(final_processed_img, caption="生成プレビュー（ゲーム内テクスチャ）", width=300)
                
                processed_data_list.append({
                    "id": poster_id,
                    "w": w_blocks,
                    "h": h_blocks,
                    "img": final_processed_img
                })

    st.write("---")

    # パック生成処理（Zipダウンロード用）
    if st.button("🚀 パック生成 (Zipダウンロード)", type="primary"):
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            namespace = "custom_poster"
            
            # mcmeta作成
            zip_file.writestr("resourcepack/pack.mcmeta", '{"pack":{"pack_format":48,"description":"Custom Poster Resources"}}')
            zip_file.writestr("datapack/pack.mcmeta", '{"pack":{"pack_format":61,"description":"Custom Poster Data"}}')
            
            placeable_variants = []

            for data in processed_data_list:
                p_id = data["id"]
                w = data["w"]
                h = data["h"]
                img = data["img"]
                
                # 画像をBytesに変換して追加
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                
                # テクスチャ
                zip_file.writestr(f"resourcepack/assets/{namespace}/textures/item/{p_id}.png", img_bytes)
                zip_file.writestr(f"resourcepack/assets/{namespace}/textures/painting/{p_id}.png", img_bytes)
                
                # 1.21.4 item_model & model
                zip_file.writestr(
                    f"resourcepack/assets/{namespace}/items/{p_id}.json",
                    f'{{"model":{{"type":"minecraft:model","model":"{namespace}:item/{p_id}"}}}}'
                )
                zip_file.writestr(
                    f"resourcepack/assets/{namespace}/models/item/{p_id}.json",
                    f'{{"parent":"minecraft:item/generated","textures":{{"layer0":"{namespace}:item/{p_id}"}}}}'
                )
                
                # Data Pack: painting_variant
                zip_file.writestr(
                    f"datapack/data/{namespace}/painting_variant/{p_id}.json",
                    f'{{"width":{w},"height":{h},"asset_id":"{namespace}:{p_id}"}}'
                )
                
                placeable_variants.append(f"{namespace}:{p_id}")
            
            # placeable.json タグ登録
            placeable_json_content = json.dumps({"values": placeable_variants})
            zip_file.writestr("datapack/data/minecraft/tags/painting_variant/placeable.json", placeable_json_content)

        st.success("🎉 パックの作成が完了しました！")
        st.download_button(
            label="📦 生成したパックをダウンロード (.zip)",
            data=zip_buffer.getvalue(),
            file_name="CraftPoster_Packs.zip",
            mime="application/zip"
        )