"""
Workforce Attrition Warehouse (DMV project)
Star schema built with pandas + interactive dashboard in Streamlit.

Files needed in the same folder:
    app.py
    requirements.txt
    WA_Fn-UseC_-HR-Employee-Attrition.csv
Optional images (shown on the Data Model / Power BI pages if present):
    star_schema.png, model_view.png, page1.png, page2.png, page3.png
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).parent
CSV_FILE = BASE / "WA_Fn-UseC_-HR-Employee-Attrition.csv"

st.set_page_config(page_title="Workforce Attrition Warehouse", layout="wide")

AGE_ORDER = ["Under 25", "25-34", "35-44", "45-54", "55+"]
TENURE_ORDER = ["0-2 yrs", "3-5 yrs", "6-10 yrs", "11+ yrs"]
INCOME_ORDER = ["Low", "Medium", "High", "Very High"]

# (dimension name, columns kept, surrogate key name)
DIMENSIONS = [
    ("Dim_Department", ["Department"], "department_key"),
    ("Dim_JobRole", ["JobRole", "JobLevel"], "jobrole_key"),
    ("Dim_Education", ["Education", "EducationField"], "education_key"),
    ("Dim_Demographic", ["Gender", "MaritalStatus",
     "AgeBand"], "demographic_key"),
    ("Dim_Tenure", ["TenureBand"], "tenure_key"),
]


# ---------------------------------------------------------------------------
# Data preparation: cleaning + star schema
# ---------------------------------------------------------------------------
def make_dim(df, cols, key):
    """One row per unique combination of the descriptive columns + surrogate key."""
    dim = df[cols].drop_duplicates().reset_index(drop=True)
    dim.insert(0, key, dim.index + 1)
    return dim


@st.cache_data
def build_model():
    raw = pd.read_csv(CSV_FILE)

    # 1. Cleaning: drop constant columns, add flag and bands
    df = raw.drop(columns=["EmployeeCount", "Over18", "StandardHours"])
    df["AttritionFlag"] = (df["Attrition"] == "Yes").astype(int)
    df["AgeBand"] = pd.cut(
        df["Age"], bins=[0, 25, 35, 45, 55, 200], labels=AGE_ORDER, right=False
    ).astype(str)
    df["TenureBand"] = pd.cut(
        df["YearsAtCompany"], bins=[-1, 2, 5, 10, 100], labels=TENURE_ORDER
    ).astype(str)
    df["IncomeBand"] = pd.cut(
        df["MonthlyIncome"],
        bins=[0, 3000, 5000, 9000, 10**9],
        labels=INCOME_ORDER,
        right=False,
    ).astype(str)

    # 2. Star schema: dimensions, then fact table holding only keys + measures
    dims = {}
    fact = df.copy()
    descriptive_cols = []
    for name, cols, key in DIMENSIONS:
        dim = make_dim(df, cols, key)
        dims[name] = dim
        fact = fact.merge(dim, on=cols, how="left")
        descriptive_cols += cols
    fact = fact.drop(columns=descriptive_cols)

    # 3. Joined view used by the charts (fact + all dimensions)
    joined = fact.copy()
    for name, cols, key in DIMENSIONS:
        joined = joined.merge(dims[name], on=key, how="left")

    return raw, fact, dims, joined


def rate_by(data, col):
    """Attrition rate, headcount and leavers grouped by one column."""
    return data.groupby(col, as_index=False).agg(
        AttritionRate=("AttritionFlag", "mean"),
        Employees=("AttritionFlag", "size"),
        Left=("AttritionFlag", "sum"),
    )


def pct_axis(fig, axis="x"):
    if axis == "x":
        fig.update_xaxes(tickformat=".0%", title="Attrition rate")
    else:
        fig.update_yaxes(tickformat=".0%", title="Attrition rate")
    return fig


def show_image_if_exists(filename, caption):
    path = BASE / filename
    if path.exists():
        st.image(str(path), caption=caption)
        return True
    return False


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
if not CSV_FILE.exists():
    st.error(
        "Dataset not found. Put WA_Fn-UseC_-HR-Employee-Attrition.csv in the "
        "same folder as app.py."
    )
    st.stop()

raw, fact, dims, joined = build_model()

st.sidebar.title("Workforce Attrition Warehouse")
page = st.sidebar.radio(
    "Go to",
    ["Overview", "What drives attrition", "Drill-down",
        "Data model", "Power BI version"],
)

# ---------------- Page 1: Overview ----------------
if page == "Overview":
    st.title("Workforce Attrition Overview")

    total = len(joined)
    left = int(joined["AttritionFlag"].sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Employees", f"{total:,}")
    c2.metric("Attrition Count", f"{left:,}")
    c3.metric("Attrition Rate", f"{left / total:.2%}")
    c4.metric("Avg Monthly Income", f"{joined['MonthlyIncome'].mean():,.0f}")

    left_col, right_col = st.columns(2)

    with left_col:
        by_dept = rate_by(joined, "Department").sort_values("AttritionRate")
        fig = px.bar(
            by_dept,
            x="AttritionRate",
            y="Department",
            orientation="h",
            text=by_dept["AttritionRate"].map("{:.1%}".format),
            title="Attrition rate by department",
        )
        st.plotly_chart(pct_axis(fig, "x"))

    with right_col:
        by_gender = rate_by(joined, "Gender")
        fig = px.pie(
            by_gender,
            names="Gender",
            values="Left",
            hole=0.5,
            title="Employees who left, by gender (counts)",
        )
        fig.update_traces(textinfo="value+percent")
        st.plotly_chart(fig)

# ---------------- Page 2: Drivers ----------------
elif page == "What drives attrition":
    st.title("What Drives Attrition?")

    col_a, col_b = st.columns(2)

    with col_a:
        by_ot = rate_by(joined, "OverTime").sort_values("AttritionRate")
        fig = px.bar(
            by_ot,
            x="AttritionRate",
            y="OverTime",
            orientation="h",
            text=by_ot["AttritionRate"].map("{:.1%}".format),
            title="Attrition rate by overtime",
        )
        st.plotly_chart(pct_axis(fig, "x"))

    with col_b:
        by_income = rate_by(joined, "IncomeBand")
        fig = px.bar(
            by_income,
            x="IncomeBand",
            y="AttritionRate",
            text=by_income["AttritionRate"].map("{:.1%}".format),
            category_orders={"IncomeBand": INCOME_ORDER},
            title="Attrition rate by income band",
        )
        st.plotly_chart(pct_axis(fig, "y"))

    by_role = rate_by(joined, "JobRole").sort_values("AttritionRate")
    fig = px.bar(
        by_role,
        x="AttritionRate",
        y="JobRole",
        orientation="h",
        text=by_role["AttritionRate"].map("{:.1%}".format),
        title="Attrition rate by job role",
    )
    st.plotly_chart(pct_axis(fig, "x"))

    st.subheader("Attrition by job satisfaction")
    sat = rate_by(joined, "JobSatisfaction").rename(
        columns={
            "JobSatisfaction": "Job Satisfaction",
            "AttritionRate": "Attrition Rate",
            "Employees": "Total Employees",
        }
    )[["Job Satisfaction", "Attrition Rate", "Total Employees"]]
    sat["Attrition Rate"] = sat["Attrition Rate"].map("{:.2%}".format)
    st.dataframe(sat, hide_index=True)

# ---------------- Page 3: Drill-down ----------------
elif page == "Drill-down":
    st.title("Drill-down Explorer")

    st.sidebar.header("Filters")
    dept_sel = st.sidebar.multiselect(
        "Department",
        sorted(joined["Department"].unique()),
        default=sorted(joined["Department"].unique()),
    )
    age_sel = st.sidebar.multiselect(
        "Age band", AGE_ORDER, default=AGE_ORDER
    )
    gender_sel = st.sidebar.multiselect(
        "Gender",
        sorted(joined["Gender"].unique()),
        default=sorted(joined["Gender"].unique()),
    )

    data = joined[
        joined["Department"].isin(dept_sel)
        & joined["AgeBand"].isin(age_sel)
        & joined["Gender"].isin(gender_sel)
    ]

    if data.empty:
        st.warning(
            "No employees match these filters. Select at least one value in each filter.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    c1.metric("Employees (filtered)", f"{len(data):,}")
    c2.metric("Left (filtered)", f"{int(data['AttritionFlag'].sum()):,}")
    c3.metric("Attrition Rate (filtered)",
              f"{data['AttritionFlag'].mean():.2%}")

    st.subheader("Department to Job Role drill-down")
    options = ["All departments"] + sorted(data["Department"].unique())
    choice = st.selectbox("Drill into a department", options)

    if choice == "All departments":
        level = rate_by(data, "Department").sort_values("AttritionRate")
        fig = px.bar(
            level,
            x="AttritionRate",
            y="Department",
            orientation="h",
            text=level["AttritionRate"].map("{:.1%}".format),
            title="Attrition rate by department (select a department above to drill down)",
        )
    else:
        level = rate_by(data[data["Department"] == choice], "JobRole").sort_values(
            "AttritionRate"
        )
        fig = px.bar(
            level,
            x="AttritionRate",
            y="JobRole",
            orientation="h",
            text=level["AttritionRate"].map("{:.1%}".format),
            title=f"Attrition rate by job role in {choice}",
        )
    st.plotly_chart(pct_axis(fig, "x"))

    marital = rate_by(data, "MaritalStatus").sort_values(
        "AttritionRate", ascending=False)
    fig = px.bar(
        marital,
        x="MaritalStatus",
        y="AttritionRate",
        text=marital["AttritionRate"].map("{:.1%}".format),
        title="Attrition rate by marital status",
    )
    st.plotly_chart(pct_axis(fig, "y"))

# ---------------- Data model ----------------
elif page == "Data model":
    st.title("Data Model: Star Schema")
    st.write(
        "**Grain:** one row per employee. `Fact_Employee` sits in the centre and holds "
        "keys and measures. Five dimension tables hold the descriptive attributes. "
        "Every relationship is one-to-many (dimension on the one side). "
        "There is no date dimension because the dataset is a snapshot with no dates, "
        "so tenure bands play the time role."
    )
    st.write(
        "**Hierarchies:** Department to Job Role, and Education to Education Field."
    )

    if not show_image_if_exists("star_schema.png", "Star schema diagram"):
        show_image_if_exists("model_view.png", "Model view (Power BI)")

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows in raw CSV", f"{len(raw):,}")
    c2.metric("Rows in Fact_Employee", f"{len(fact):,}")
    c3.metric(
        "Key columns with nulls",
        int(fact[[k for _, _, k in DIMENSIONS]].isna().any().sum()),
    )

    with st.expander("Fact_Employee (first 10 rows)", expanded=True):
        st.dataframe(fact.head(10))
    for name, cols, key in DIMENSIONS:
        with st.expander(f"{name}  ({len(dims[name])} rows)"):
            st.dataframe(dims[name], hide_index=True)

# ---------------- Power BI version ----------------
else:
    st.title("Power BI Version")
    st.write("The same project built in Power BI Desktop.")
    shown = False
    for fname, cap in [
        ("page1.png", "Page 1: Overview"),
        ("page2.png", "Page 2: What drives attrition"),
        ("page3.png", "Page 3: Drill-down explorer"),
        ("model_view.png", "Model view (star schema)"),
    ]:
        shown = show_image_if_exists(fname, cap) or shown
    if not shown:
        st.info(
            "Add page1.png, page2.png, page3.png and model_view.png to the "
            "repository to show the Power BI screenshots here."
        )
