import io
import json
import os
import shutil
import zipfile
from PIL import Image
import streamlit as st

# ==========================================
# 定数・初期設定
# ==========================================
DEFAULT_MC_PATH = os.path.expanduser(r"~\AppData\Roaming\.minecraft")
DEFAULT_RP_NAME = "custom_resources"
DEFAULT_DP_NAME = "custom_pack"
DEFAULT_NAMESPACE = "poster"

st.set_page_config(
    page_title="CraftPoster Web - マイクラポスター生成ツール",
    page_icon="🖼️",
    layout="wide",
)

# カスタムCSSでデザイン調整
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2e7d32;
        margin-bottom: 0.5rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def clean_id(filename: str) -> str:
    """ファイル名からアルファベット・数字・アンダースコアのみのIDを抽出"""
    name_without_ext = os.path.splitext(filename)[0]
    cleaned = "".join(
        c.lower() for c in name_without_ext if c.isalnum() or c in ("_", "-")
    )
    return cleaned if cleaned else "poster_item"


def create_pack_mcmeta(description: str, pack_format: int):
    return {"pack": {"pack_format": pack_format, "description": description}}


def build_packs(
    posters_data,
    mc_path,
    world_name,
    rp_name,
    dp_name,
    namespace,
    mode="local",
):
    """
    データパック・リソースパックの生成処理
    mode="local": PCの.minecraftフォルダに直接出力
    mode="zip": メモリ上のZipバイナリとして出力
    """
    rp_base = os.path.join(mc_path, "resourcepacks", rp_name)
    dp_base = os.path.join(mc_path, "saves", world_name, "datapacks", dp_name)

    placeable_ids = []
    zip_buffer = io.BytesIO() if mode == "zip" else None
    zf = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) if mode == "zip" else None

    # pack.mcmeta の作成
    rp_mcmeta = create_pack_mcmeta("CraftPoster Custom Resource Pack", 48)
    dp_mcmeta = create_pack_mcmeta("CraftPoster Custom Data Pack", 61)

    if mode == "local":
        ensure_dir(rp_base)
        ensure_dir(dp_base)
        with open(
            os.path.join(rp_base, "pack.mcmeta"), "w", encoding="utf-8"
        ) as f:
            json.dump(rp_mcmeta, f, indent=2)
        with open(
            os.path.join(dp_base, "pack.mcmeta"), "w", encoding="utf-8"
        ) as f:
            json.dump(dp_mcmeta, f, indent=2)
    else:
        zf.writestr(
            f"resourcepacks/{rp_name}/pack.mcmeta", json.dumps(rp_mcmeta, indent=2)
        )
        zf.writestr(
            f"datapacks/{dp_name}/pack.mcmeta", json.dumps(dp_mcmeta, indent=2)
        )

    for item in posters_data:
        p_id = item["id"]
        width = item["width"]
        height = item["height"]
        img_bytes = item["img_bytes"]

        full_asset_id = f"{namespace}:{p_id}"
        placeable_ids.append(full_asset_id)

        # 1. 画像ファイルのコピー (item & painting)
        for sub_dir in ["item", "painting"]:
            rel_img_path = f"assets/{namespace}/textures/{sub_dir}/{p_id}.png"
            if mode == "local":
                dst_dir = os.path.join(
                    rp_base, "assets", namespace, "textures", sub_dir
                )
                ensure_dir(dst_dir)
                with open(os.path.join(dst_dir, f"{p_id}.png"), "wb") as f:
                    f.write(img_bytes)
            else:
                zf.writestr(f"resourcepacks/{rp_name}/{rel_img_path}", img_bytes)

        # 2. assets/{namespace}/items/{id}.json (リソースパック)
        items_json = {
            "model": {
                "type": "minecraft:model",
                "model": f"{namespace}:item/{p_id}",
            }
        }
        if mode == "local":
            items_dir = os.path.join(rp_base, "assets", namespace, "items")
            ensure_dir(items_dir)
            with open(
                os.path.join(items_dir, f"{p_id}.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(items_json, f, indent=2)
        else:
            zf.writestr(
                f"resourcepacks/{rp_name}/assets/{namespace}/items/{p_id}.json",
                json.dumps(items_json, indent=2),
            )

        # 3. assets/{namespace}/models/item/{id}.json (リソースパック)
        models_json = {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"{namespace}:item/{p_id}"},
        }
        if mode == "local":
            models_dir = os.path.join(
                rp_base, "assets", namespace, "models", "item"
            )
            ensure_dir(models_dir)
            with open(
                os.path.join(models_dir, f"{p_id}.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(models_json, f, indent=2)
        else:
            zf.writestr(
                f"resourcepacks/{rp_name}/assets/{namespace}/models/item/{p_id}.json",
                json.dumps(models_json, indent=2),
            )

        # 4. data/{namespace}/painting_variant/{id}.json (データパック)
        variant_json = {
            "asset_id": full_asset_id,
            "width": width,
            "height": height,
        }
        if mode == "local":
            dp_variant_dir = os.path.join(
                dp_base, "data", namespace, "painting_variant"
            )
            ensure_dir(dp_variant_dir)
            with open(
                os.path.join(dp_variant_dir, f"{p_id}.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(variant_json, f, indent=2)
        else:
            zf.writestr(
                f"datapacks/{dp_name}/data/{namespace}/painting_variant/{p_id}.json",
                json.dumps(variant_json, indent=2),
            )

    # 5. data/minecraft/tags/painting_variant/placeable.json (一括更新)
    placeable_json = {"values": placeable_ids}
    if mode == "local":
        tag_dir = os.path.join(
            dp_base, "data", "minecraft", "tags", "painting_variant"
        )
        ensure_dir(tag_dir)
        with open(
            os.path.join(tag_dir, "placeable.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(placeable_json, f, indent=2)
    else:
        zf.writestr(
            f"datapacks/{dp_name}/data/minecraft/tags/painting_variant/placeable.json",
            json.dumps(placeable_json, indent=2),
        )

    if mode == "zip":
        zf.close()
        zip_buffer.seek(0)
        return zip_buffer.getvalue()


# ==========================================
# UIメイン画面
# ==========================================
st.markdown(
    '<div class="main-title">🖼️ CraftPoster Web</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-title">マイクラ（1.21.4 / 26.x対応）ポスター＆カスタム絵画全自動作成ツール</div>',
    unsafe_allow_html=True,
)

# サイドバー: マイクラの設定
st.sidebar.header("⚙️ マイクラ接続設定")
mc_path = st.sidebar.text_input("マイクラフォルダ (.minecraft)", DEFAULT_MC_PATH)
world_name = st.sidebar.text_input("ワールド名", "新しい世界")
namespace = st.sidebar.text_input("ネームスペース (IDプレフィックス)", DEFAULT_NAMESPACE)
rp_name = st.sidebar.text_input("リソースパック名", DEFAULT_RP_NAME)
dp_name = st.sidebar.text_input("データパック名", DEFAULT_DP_NAME)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **ヒント**: 将来的にWebサーバーに公開する際は、Zipダウンロード機能を利用することでサーバーへのファイル書き込みなしで動作します。"
)

# メインコンテンツエリア
st.header("1. ポスター画像の一括アップロード")
uploaded_files = st.file_uploader(
    "画像ファイルをドラッグ＆ドロップまたは選択してください (.png, .jpg, .jpeg)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

posters_config = []

if uploaded_files:
    st.header("2. ポスター個別のIDとサイズ設定")
    st.caption("マイクラ内でのブロック数（幅×高さ）やIDを調整してください。")

    for idx, file in enumerate(uploaded_files):
        default_id = clean_id(file.name)
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))

        col_img, col_form = st.columns([1, 3])

        with col_img:
            st.image(image, caption=f"プレビュー ({image.width}x{image.height} px)", use_container_width=True)

        with col_form:
            p_col1, p_col2, p_col3 = st.columns([2, 1, 1])
            with p_col1:
                p_id = st.text_input(
                    f"ポスターID #{idx+1}",
                    value=default_id,
                    key=f"id_{idx}",
                    help="英数字とアンダースコアのみ使用可能です。",
                )
            with p_col2:
                width = st.number_input(
                    "幅 (ブロック)",
                    min_value=1,
                    max_value=16,
                    value=1,
                    key=f"w_{idx}",
                )
            with p_col3:
                height = st.number_input(
                    "高さ (ブロック)",
                    min_value=1,
                    max_value=16,
                    value=1,
                    key=f"h_{idx}",
                )

            posters_config.append(
                {
                    "id": p_id,
                    "width": int(width),
                    "height": int(height),
                    "img_bytes": img_bytes,
                }
            )

        st.markdown("---")

    # 3. 実行アクション
    st.header("3. データパック・リソースパックの生成")

    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("🚀 PCのマイクラフォルダへ直接生成・配置"):
            if not os.path.exists(mc_path):
                st.error(f"マイクラフォルダが見つかりません: {mc_path}")
            else:
                try:
                    build_packs(
                        posters_config,
                        mc_path,
                        world_name,
                        rp_name,
                        dp_name,
                        namespace,
                        mode="local",
                    )
                    st.success("🎉 マイクラへの自動配置が完了しました！")
                    st.info("🎮 **マイクラ内での操作**:\n1. チャットで `/reload` を実行\n2. 以下の入手コマンドを実行:")

                    for p in posters_config:
                        cmd = f'/give @s minecraft:painting[minecraft:painting/variant="{namespace}:{p["id"]}", minecraft:item_model="{namespace}:{p["id"]}"]'
                        st.code(cmd, language="mcfunction")
                except Exception as e:
                    st.error(f"生成中にエラーが発生しました: {e}")

    with btn_col2:
        try:
            zip_data = build_packs(
                posters_config,
                mc_path,
                world_name,
                rp_name,
                dp_name,
                namespace,
                mode="zip",
            )
            st.download_button(
                label="📦 Pack一式をZipファイルでダウンロード",
                data=zip_data,
                file_name="CraftPoster_Packs.zip",
                mime="application/zip",
            )
        except Exception as e:
            st.error(f"Zip生成エラー: {e}")

else:
    st.info("👆 上のエリアに画像をアップロードすると設定項目が表示されます。")