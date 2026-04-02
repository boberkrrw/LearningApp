import streamlit as st

st.set_page_config(
    page_title="DE Senior Prep",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Run seed on first launch
from db.database import init_db
init_db()

dashboard = st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📊", default=True)
learn = st.Page("pages/2_Learn.py", title="Learn", icon="📖")
practice = st.Page("pages/3_Practice.py", title="Practice", icon="💪")
evaluate = st.Page("pages/4_Evaluate.py", title="Evaluate", icon="🔍")
next_step = st.Page("pages/5_Next_Step.py", title="Next Step", icon="🚀")

pg = st.navigation([dashboard, learn, practice, evaluate, next_step])
pg.run()
