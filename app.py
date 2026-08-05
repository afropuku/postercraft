import streamlit as st
from PIL import Image, ImageOps
import io
import zipfile

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

# 2. トリミング・リサイズモード選択
crop_mode = st.sidebar.radio(
    "画像調整モード",
    options=["自動センタークロップ (アスペクト比維持)", "変形（全域を伸ばしてフィット）"],
    index=0,
    help="「自動センタークロップ」を選ぶと、指定したサイズ比率に合わせて画像の中央を切り抜き、引き伸ばし・歪みを防ぎます。"
)

# 画像処理関数
def process_image(img: Image.Image, width_blocks: int, height_blocks: int, px_per_block: int, mode: str) -> Image.Image:
    # 最終的な目標解像度（ピクセル）
    target_w = width_blocks * px_per_block
    target_h = height_blocks * px_per_block
    
    # RGBAへ変換（透過対応）
    img = img.convert("RGBA")
    
    if mode == "自動センタークロップ (アスペクト比維持)":
        # 目的のアスペクト比に合わせて中央をトリミング＆リサイズ
        processed_img = ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
    else:
        # 画像全体をリサイズ（アスペクト比無視）
        processed_img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
    return processed_img

# メイン画面：画像アップロード
uploaded_files = st.file_uploader("ポスターにしたい画像をアップロードしてください", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("📋 ポスター個別設定")
    
    processed_data_list = []
    
    for idx, uploaded_file in enumerate(uploaded_files):
        col1, col2 = st.columns([1, 2])
        
        # アップロードされた元画像を開く
        raw_img = Image.open(uploaded_file)
        
        with col1:
            st.image(raw_img, caption=f"元画像: {uploaded_file.name}", use_column_width=True)
            
        with col2:
            default_id = f"poster_{idx+1}"
            poster_id = st.text_input(f"ポスターID (小文字英数・アンダースコア)", value=default_id, key=f"id_{idx}")
            
            c1, c2 = st.columns(2)
            with c1:
                w_blocks = st.number_input(f"横幅 (ブロック数)", min_value=1, max_value=16, value=2, key=f"w_{idx}")
            with c2:
                h_blocks = st.number_input(f"高さ (ブロック数)", min_value=1, max_value=1, value=1, key=f"h_{idx}")
            
            # 画像のトリミング・リサイズ処理を実行
            processed_img = process_image(raw_img, w_blocks, h_blocks, px_per_block, crop_mode)
            
            # プレビュー表示
            st.write(f"🎮 出力サイズ: {w_blocks * px_per_block} x {h_blocks * px_per_block} px")
            st.image(processed_img, caption="生成プレビュー", width=min(w_blocks * px_per_block * 3, 300))
            
            processed_data_list.append({
                "id": poster_id,
                "w": w_blocks,
                "h": h_blocks,
                "img": processed_img
            })
        st.divider()

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
            placeable_json_content = f'{{"values":{str(placeable_variants).replace("\'", '"')}}}'
            zip_file.writestr("datapack/data/minecraft/tags/painting_variant/placeable.json", placeable_json_content)

        st.success("🎉 パックの作成が完了しました！")
        st.download_button(
            label="📦 生成したパックをダウンロード (.zip)",
            data=zip_buffer.getvalue(),
            file_name="CraftPoster_Packs.zip",
            mime="application/zip"
        )