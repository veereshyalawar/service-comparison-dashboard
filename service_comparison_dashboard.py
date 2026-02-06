import streamlit as st
from db_connection import execute_query

# ============================================
# 1. PAGE CONFIG
# ============================================
st.set_page_config(
    page_title="Service Comparison | Topmate",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================
# 2. DESIGN SYSTEM (matches advance dashboard)
# ============================================
PRIMARY = "#2563EB"
PRIMARY_LIGHT = "#EFF6FF"
SUCCESS = "#10B981"
SUCCESS_LIGHT = "#ECFDF5"
WARNING = "#F59E0B"
ERROR = "#EF4444"
ERROR_LIGHT = "#FEF2F2"
TEXT_PRIMARY = "#18181B"
TEXT_SECONDARY = "#71717A"
TEXT_MUTED = "#A1A1AA"
BORDER = "#E4E4E7"
BG = "#FAFAFA"
SURFACE = "#FFFFFF"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    div[data-testid="stVerticalBlock"] > div {
        gap: 0.5rem !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.75rem !important;
    }
    hr {
        margin: 0.75rem 0 !important;
        border-color: #E4E4E7 !important;
    }

    h3 {
        color: #18181B !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# 3. QUERIES (inline)
# ============================================
def get_service_comparison_data(sid1, sid2):
    """
    Total, organic, and non-organic booking counts for two services.
    Organic = utm_source ILIKE '%instagram%' in booking_bookingmeta.utm_params.
    Only completed, ongoing, upcoming bookings.
    """
    query = """
    SELECT
        ab.service_id,
        COUNT(*) AS total,
        COUNT(*) FILTER (
            WHERE bm.utm_params->>'utm_source' ILIKE '%%instagram%%'
        ) AS organic,
        COUNT(*) FILTER (
            WHERE bm.utm_params->>'utm_source' NOT ILIKE '%%instagram%%'
               OR bm.utm_params->>'utm_source' IS NULL
               OR bm.utm_params->>'utm_source' = ''
        ) AS non_organic
    FROM all_bookings_new ab
    LEFT JOIN booking_bookingmeta bm ON bm.id = ab.bookingmeta_id
    WHERE ab.service_id IN (%s, %s)
      AND ab.status IN ('completed', 'ongoing', 'upcoming')
    GROUP BY ab.service_id
    """
    rows = execute_query(query, (sid1, sid2))
    empty = {"total": 0, "organic": 0, "non_organic": 0}
    result = {}
    for r in (rows or []):
        result[int(r["service_id"])] = {
            "total": int(r["total"]),
            "organic": int(r["organic"]),
            "non_organic": int(r["non_organic"]),
        }
    for sid in (sid1, sid2):
        if sid not in result:
            result[sid] = dict(empty)
    return result


def get_username_for_service(service_id):
    """Look up the expert username who owns this service."""
    query = """
    SELECT u.username
    FROM services_service s
    JOIN user_user u ON u.id = s.user_id
    WHERE s.id = %s
    """
    rows = execute_query(query, (service_id,))
    if rows:
        return rows[0]["username"] or "—"
    return "—"


# ============================================
# 4. COMPARISON TABLE HTML BUILDER
# ============================================
def _diff_cell(v1, v2):
    """Difference = service1 - service2. Red ▼ if >0, green ▲ if <0."""
    diff = v1 - v2
    if diff > 0:
        return f'<span style="color:{ERROR};font-weight:700;">&#x25BC; +{diff:,}</span>'
    elif diff < 0:
        return f'<span style="color:{SUCCESS};font-weight:700;">&#x25B2; {diff:,}</span>'
    return f'<span style="color:{TEXT_MUTED};font-weight:700;">0</span>'


def comparison_table_html(sid1, sid2, d1, d2, user1, user2):
    """
    Flat single-row table grouped as:
    USERNAME | Svc1 Organic | Svc2 Organic | Organic Diff | Svc1 Non-Organic | Svc2 Non-Organic | Non-Organic Diff
    """
    org_diff = _diff_cell(d1["organic"], d2["organic"])
    non_org_diff = _diff_cell(d1["non_organic"], d2["non_organic"])

    username_display = user1 if user1 == user2 else f"{user1} / {user2}"

    th = f'padding:10px 8px;font-size:0.65rem;font-weight:600;color:{TEXT_MUTED};text-align:center;text-transform:uppercase;letter-spacing:0.03em;'
    td = f'padding:16px 8px;font-size:1rem;font-weight:700;color:{TEXT_PRIMARY};text-align:center;'
    td_name = f'padding:16px 8px;font-size:0.85rem;font-weight:600;color:{TEXT_SECONDARY};text-align:center;'

    return f"""
    <div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;padding:1.25rem;font-family:Inter,sans-serif;overflow-x:auto;">
        <p style="font-size:0.75rem;font-weight:600;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px 0;">
            Service Comparison
        </p>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="border-bottom:2px solid {BORDER};">
                    <th style="{th}" rowspan="2">Username</th>
                    <th style="{th}color:{PRIMARY};" colspan="3">Organic</th>
                    <th style="{th}color:{PRIMARY};" colspan="3">Non-Organic</th>
                </tr>
                <tr style="border-bottom:1px solid {BORDER};">
                    <th style="{th}">Svc {sid1}</th>
                    <th style="{th}">Svc {sid2}</th>
                    <th style="{th}">Diff</th>
                    <th style="{th}">Svc {sid1}</th>
                    <th style="{th}">Svc {sid2}</th>
                    <th style="{th}">Diff</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="{td_name}">{username_display}</td>
                    <td style="{td}">{d1["organic"]:,}</td>
                    <td style="{td}">{d2["organic"]:,}</td>
                    <td style="{td}">{org_diff}</td>
                    <td style="{td}">{d1["non_organic"]:,}</td>
                    <td style="{td}">{d2["non_organic"]:,}</td>
                    <td style="{td}">{non_org_diff}</td>
                </tr>
            </tbody>
        </table>
    </div>"""


# ============================================
# 5. HEADER
# ============================================
st.markdown(f"""
    <div style="margin-bottom:4px;">
        <span style="font-size:1.5rem; font-weight:700; color:{TEXT_PRIMARY};">Service Comparison</span>
    </div>
    <span style="font-size:0.875rem; color:{TEXT_SECONDARY};">Compare two services side by side</span>
""", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# 6. FILTERS & COMPARISON
# ============================================
try:
    filter_cols = st.columns(2)

    with filter_cols[0]:
        sid1 = st.number_input("Service 1 ID", min_value=1, step=1, value=None, placeholder="Enter service ID")
    with filter_cols[1]:
        sid2 = st.number_input("Service 2 ID", min_value=1, step=1, value=None, placeholder="Enter service ID")

    if sid1 is None or sid2 is None:
        st.info("Enter two service IDs above to compare.")
        st.stop()

    sid1 = int(sid1)
    sid2 = int(sid2)

    if sid1 == sid2:
        st.warning("Please enter two different service IDs.")
        st.stop()

    st.markdown("---")

    # Get booking data and usernames
    data = get_service_comparison_data(sid1, sid2)
    user1 = get_username_for_service(sid1)
    user2 = get_username_for_service(sid2)

    # Render
    st.html(comparison_table_html(sid1, sid2, data[sid1], data[sid2], user1, user2))

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Please check that the database connection is properly configured.")

# Footer
st.markdown("---")
st.markdown(
    f'<p style="text-align:center;font-size:0.75rem;color:{TEXT_MUTED};">'
    f"Topmate Service Comparison &middot; Powered by Streamlit</p>",
    unsafe_allow_html=True,
)
