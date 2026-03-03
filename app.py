import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
from streamlit_ace import st_ace
import openai

# --- PAGE CONFIG ---
st.set_page_config(page_title="Project Sentinel: AI-Native STR", layout="wide")

# --- SIDEBAR FOR OPENAI KEY ---
st.sidebar.header("🔑 Configuration")
OPENAI_API_KEY = st.sidebar.text_input(
    "Enter your OpenAI API Key",
    type="password",
    placeholder="sk-..."
)

if not OPENAI_API_KEY:
    st.sidebar.warning("Please enter your OpenAI API key to enable AI functions.")

st.sidebar.info("Your API key is used only locally in this session.")

# --- SESSION STATE INITIALIZATION ---
if 'stage' not in st.session_state: st.session_state.stage = 'ready'
if 'case_data' not in st.session_state: st.session_state.case_data = {}
if 'json_buffer' not in st.session_state: st.session_state.json_buffer = ""

# --- AI AGENT CORE LOGIC ---
def run_adversarial_swarm(context):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    # 1. Prosecutor
    p = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are the Lead AML Prosecutor. Identify criminal intent, structuring, and red flags. Be assertive."},
                  {"role": "user", "content": context}]
    ).choices[0].message.content
    
    # 2. Red Team
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are the Red Team Auditor. Challenge the Prosecutor's bias. Provide legitimate business justifications for the activity."},
                  {"role": "user", "content": f"Data: {context}\nProsecutor's Argument: {p}"}]
    ).choices[0].message.content
    
    # 3. Narrator
    n = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are the Senior Compliance Adjudicator. Synthesize the debate into a final, objective risk brief for a FINTRAC STR."},
                  {"role": "user", "content": f"Debate: Prosecutor said '{p}' vs Red Team said '{r}'"}]
    ).choices[0].message.content
    
    return p, r, n


def generate_fintrac_payload(brief, kyc_data, txn_list):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    mapping_prompt = f"""
    Map this AML investigation into the following JSON structure exactly.
    KYC: {kyc_data}
    TXNS: {txn_list}
    BRIEF: {brief}
    SCHEMA:
    {{
      "fileHeader": {{ "submittingReportingEntityNumber": "1035", "reportingEntityBulkReference": "REF-2026" }},
      "reports": [
          {{
              "reportDetails": {{ "reportType": "STR" }},
              "detailsOfSuspicion": "...",
              "Transactions": [ {{ "date": "...", "amount": "...", "mode": "..." }} ]
          }}
      ],
      "actionTaken": "..."
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a FINTRAC STR AI Mapper. Output ONLY valid JSON strictly following the SCHEMA above. No extra text, no markdown."},
            {"role": "user", "content": mapping_prompt}
        ],
        response_format={"type": "json_object"}
    )

    raw_content = response.choices[0].message.content

    try:
        parsed = json.loads(raw_content)
        final_json = {
            "fileHeader": parsed.get("fileHeader", {"submittingReportingEntityNumber": "1035", "reportingEntityBulkReference": "REF-2026"}),
            "reports": [],
            "actionTaken": parsed.get("actionTaken", "...")
        }

        if "reports" in parsed and isinstance(parsed["reports"], list):
            for r in parsed["reports"]:
                report = {
                    "reportDetails": r.get("reportDetails", {"reportType": "STR"}),
                    "detailsOfSuspicion": r.get("detailsOfSuspicion", "..."),
                    "Transactions": []
                }
                if "Transactions" in r and isinstance(r["Transactions"], list):
                    for t in r["Transactions"]:
                        txn = {
                            "date": t.get("date", "..."),
                            "amount": t.get("amount", "..."),
                            "mode": t.get("mode", "...")
                        }
                        report["Transactions"].append(txn)
                final_json["reports"].append(report)

        return json.dumps(final_json, indent=2)

    except json.JSONDecodeError:
        return raw_content

# --- UI INTERFACE ---
st.title("🛡️ Project Sentinel")
st.caption("AI-Native Suspicious Transaction Report (STR) Generator")

# --- STAGE 1: INGESTION ---
if st.session_state.stage == 'ready':
    with st.container():
        st.markdown("### 📥 1. Load Case Files")
        files = st.file_uploader("KYC, Alerts, Transactions files", accept_multiple_files=True, type="csv")
        
        if st.button("🚀 Run Analysis", disabled=len(files) < 3):
            if not OPENAI_API_KEY:
                st.warning("Enter your OpenAI API key in the sidebar to proceed.")
            else:
                temp_data = {}
                for f in files:
                    df = pd.read_csv(f)
                    fname = f.name.lower()
                    if "kyc" in fname: temp_data['kyc'] = df
                    elif "alert" in fname: temp_data['al'] = df
                    else: temp_data['tx'] = df
                
                st.session_state.case_data = {
                    "kyc": temp_data['kyc'], "al": temp_data['al'], "tx": temp_data['tx'],
                    "summary": f"KYC: {temp_data['kyc'].to_dict()} | Txns: {temp_data['tx'].to_dict()}"
                }
                
                with st.spinner("Deploying Agents..."):
                    p, r, n = run_adversarial_swarm(st.session_state.case_data['summary'])
                    st.session_state.prosecutor, st.session_state.red_team, st.session_state.narrative = p, r, n
                    st.session_state.stage = 'review'
                    st.rerun()

# --- STAGE 2: REVIEW / ADJUDICATION ---
if st.session_state.stage == 'review':
    st.header("⚖️ 2. Review & Adjudication")
    
    # KYC & Transactions Display
    col_k, col_t = st.columns(2)
    col_k.write("**Subject Profile**")
    col_k.table(st.session_state.case_data['kyc'])
    col_t.write("**Transactions**")
    col_t.dataframe(st.session_state.case_data['tx'], hide_index=True)

    # Tabs for AI outputs
    tab1, tab2, tab3 = st.tabs(["Prosecutor", "Red Team", "Narrative Synthesis"])
    tab1.write(st.session_state.prosecutor)
    tab2.write(st.session_state.red_team)
    tab3.info("Summary:")
    tab3.write(st.session_state.narrative)

    st.divider()

    # JSON Generation & Editing
    if st.session_state.json_buffer == "":
        st.markdown("### 🛠️ Final Step: Action Required")
        c1, c2 = st.columns(2)
        
        if c1.button("📑 Generate FINTRAC Draft", use_container_width=True):
            with st.spinner("Mapping to FINTRAC Schema..."):
                st.session_state.json_buffer = generate_fintrac_payload(
                    st.session_state.narrative,
                    st.session_state.case_data['kyc'].to_dict(orient='records'),
                    st.session_state.case_data['tx'].to_dict(orient='records')
                )
                st.rerun()

        if c2.button("🗑️ Discard / New Case", use_container_width=True):
            st.session_state.stage = 'ready'
            st.session_state.json_buffer = ""
            st.rerun()
    
    else:
        st.markdown("### 📝 Final JSON Editorial (Editable)")
        edited_json = st_ace(
            value=st.session_state.json_buffer,
            language="json",
            theme="chrome",
            height=400,
            show_gutter=True
        )

        col_sub, col_res = st.columns([2,1])

        if col_sub.button("📡 Final Submit to FINTRAC", use_container_width=True):
            try:
                final_check = json.loads(edited_json)
                st.session_state.json_buffer = json.dumps(final_check, indent=2)
                st.session_state.stage = 'submitted'
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"🚨 Invalid JSON: {str(e)}.")

        if col_res.button("🗑️ Reset Case", use_container_width=True):
            st.session_state.stage = 'ready'
            st.session_state.json_buffer = ""
            st.rerun()

# --- STAGE 3: SUBMITTED ---
if st.session_state.stage == 'submitted':
    st.success("✅ STR Successfully Submitted to FINTRAC")
    st.code(st.session_state.json_buffer, language='json')
    if st.button("Start New Case"):
        st.session_state.stage = 'ready'
        st.session_state.json_buffer = ""
        st.rerun()