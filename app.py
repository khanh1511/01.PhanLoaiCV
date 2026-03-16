import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO


st.set_page_config(page_title="Phân loại công việc xây dựng", layout="wide")


@st.cache_data
def load_excel(file):
    # Chỉ đọc file Excel định dạng .xlsx với engine openpyxl
    return pd.read_excel(file, engine="openpyxl")


def clean_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def detect_main_category(task_name: str) -> str:
    """
    Hàm nhận diện nhóm công việc chính dựa trên chuỗi mô tả.
    Tùy biến lại dict KEYWORDS theo nhu cầu thực tế.
    """
    if not isinstance(task_name, str):
        task_name = str(task_name)
    t = task_name.lower()

    KEYWORDS = {
        "Bê tông": [
            "bê tông",
            "bt mác",
            "be tong",
            "btct",
        ],
        "Cốt thép": [
            "cốt thép",
            "cốt thep",
            "thép chịu lực",
        ],
        "Ván khuôn": [
            "ván khuôn",
            "coppha",
            "coffa",
        ],
        "Xây": [
            "xây gạch",
            "xây tường",
            "xây",
        ],
        "Trát": [
            "trát",
            "tô trát",
        ],
        "Sơn": [
            "sơn",
            "sơn nước",
            "sơn dầu",
        ],
    }

    for cat, kws in KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return cat

    return "Khác"


def normalize_unit(unit: str) -> str:
    if pd.isna(unit):
        return ""
    u = str(unit).strip().lower()
    mapping = {
        "m3": ["m3", "m^3", "m khối", "m3 bê tông"],
        "m2": ["m2", "m^2", "m vuông"],
        "m": ["m", "md", "m dài"],
        "kg": ["kg", "kilogram"],
        "tấn": ["tấn", "tan"],
        "công": ["công", "nhân công"],
        "bộ": ["bộ"],
        "cái": ["cái"],
    }
    for std, aliases in mapping.items():
        if u in aliases:
            return std
    return unit


def to_number(x):
    if pd.isna(x):
        return 0.0
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x)
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^\d\.]", "", s)
    try:
        return float(s)
    except ValueError:
        return 0.0


def process_data(
    df: pd.DataFrame,
    col_task: str,
    col_qty: str,
    col_unit: str | None,
    col_unit_price: str | None,
    col_amount: str | None,
) -> pd.DataFrame:
    df = df.copy()

    df[col_task] = df[col_task].apply(clean_text)
    if col_unit:
        df[col_unit] = df[col_unit].apply(normalize_unit)

    df["__qty"] = df[col_qty].apply(to_number)

    if col_amount:
        df["__amount"] = df[col_amount].apply(to_number)
    else:
        if col_unit_price:
            df["__unit_price"] = df[col_unit_price].apply(to_number)
            df["__amount"] = df["__qty"] * df["__unit_price"]
        else:
            df["__amount"] = 0.0

    df["Nhóm chính"] = df[col_task].apply(detect_main_category)

    group_cols = ["Nhóm chính"]
    if col_unit:
        group_cols.append(col_unit)

    agg = (
        df.groupby(group_cols, dropna=False)
        .agg(
            Tổng_khối_lượng=("__qty", "sum"),
            Tổng_giá_trị=("__amount", "sum"),
            Số_dòng=("Nhóm chính", "count"),
        )
        .reset_index()
    )

    return df, agg


def main():
    # Khởi tạo state lưu dữ liệu đã xử lý
    if "detailed_df" not in st.session_state:
        st.session_state["detailed_df"] = None
    if "summary_df" not in st.session_state:
        st.session_state["summary_df"] = None
    if "group_unit_col" not in st.session_state:
        st.session_state["group_unit_col"] = None

    st.title("Phân loại và tổng hợp công việc từ Excel")
    st.write(
        "Tải lên file Excel chứa danh sách công việc để phân loại theo **nhóm công việc chính** "
        "và tổng hợp **khối lượng / giá trị**."
    )

    uploaded_file = st.file_uploader(
        "Chọn file Excel (.xlsx)", type=["xlsx"]
    )

    if not uploaded_file:
        st.info("Hãy tải lên 1 file Excel để bắt đầu.")
        return

    df = load_excel(uploaded_file)

    st.subheader("Xem nhanh dữ liệu gốc")
    st.dataframe(df.head(20), use_container_width=True)

    st.markdown("---")
    st.subheader("Cấu hình cột dữ liệu")

    cols = list(df.columns)
    col_task = st.selectbox(
        "Chọn cột mô tả công việc", options=cols, index=0 if cols else None
    )

    col_qty = st.selectbox(
        "Chọn cột khối lượng", options=cols, index=1 if len(cols) > 1 else 0
    )

    col_unit = st.selectbox(
        "Chọn cột đơn vị (nếu có)",
        options=["<Không dùng>"] + cols,
        index=0,
    )
    if col_unit == "<Không dùng>":
        col_unit = None

    col_unit_price = st.selectbox(
        "Chọn cột đơn giá (nếu có - dùng để tính thành tiền nếu chưa có cột giá trị)",
        options=["<Không dùng>"] + cols,
        index=0,
    )
    if col_unit_price == "<Không dùng>":
        col_unit_price = None

    col_amount = st.selectbox(
        "Chọn cột giá trị/thành tiền (nếu đã có sẵn trong file)",
        options=["<Không dùng>"] + cols,
        index=0,
    )
    if col_amount == "<Không dùng>":
        col_amount = None

    if st.button("Xử lý & phân loại", type="primary"):
        with st.spinner("Đang xử lý dữ liệu..."):
            detailed_df, summary_df = process_data(
                df,
                col_task=col_task,
                col_qty=col_qty,
                col_unit=col_unit,
                col_unit_price=col_unit_price,
                col_amount=col_amount,
            )
            st.session_state["detailed_df"] = detailed_df
            st.session_state["summary_df"] = summary_df
            st.session_state["group_unit_col"] = col_unit

        st.success("Đã phân loại xong! Bạn có thể chỉnh sửa lại cột 'Nhóm chính' nếu cần.")

    # Nếu đã có dữ liệu trong session_state thì hiển thị phần chỉnh sửa & tổng hợp
    if st.session_state["detailed_df"] is not None:
        st.markdown("---")
        st.subheader("Dữ liệu chi tiết (có thể chỉnh sửa cột 'Nhóm chính')")
        st.caption(
            "Nếu phân loại bị nhầm hoặc bạn muốn thêm nhóm mới, hãy sửa trực tiếp giá trị trong cột 'Nhóm chính'."
        )

        edited_df = st.data_editor(
            st.session_state["detailed_df"],
            use_container_width=True,
            num_rows="dynamic",
            key="editor_detailed_df",
        )

        if st.button("Cập nhật bảng tổng hợp từ dữ liệu đã chỉnh sửa"):
            df_updated = edited_df.copy()
            group_cols = ["Nhóm chính"]
            unit_col = st.session_state.get("group_unit_col")
            if unit_col:
                group_cols.append(unit_col)

            summary_updated = (
                df_updated.groupby(group_cols, dropna=False)
                .agg(
                    Tổng_khối_lượng=("__qty", "sum"),
                    Tổng_giá_trị=("__amount", "sum"),
                    Số_dòng=("Nhóm chính", "count"),
                )
                .reset_index()
            )

            st.session_state["detailed_df"] = df_updated
            st.session_state["summary_df"] = summary_updated

            st.success("Đã cập nhật lại bảng tổng hợp theo phân loại mới!")

    if st.session_state["summary_df"] is not None:
        summary_df = st.session_state["summary_df"]

        st.markdown("---")
        st.subheader("Kết quả tổng hợp theo nhóm công việc chính (mới nhất)")
        st.dataframe(summary_df, use_container_width=True)

        total_amount = summary_df["Tổng_giá_trị"].sum()
        st.metric("Tổng giá trị tất cả nhóm", f"{total_amount:,.0f}")

        # Chuẩn bị file Excel trong bộ nhớ để tải về
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Tong hop")
        buffer.seek(0)

        st.download_button(
            "Tải về bảng tổng hợp (Excel)",
            data=buffer,
            file_name="tong_hop_nhom_cong_viec.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()

