"""
Medical Report Analyzer - Streamlit Application
"""
import os
import fitz  # PyMuPDF
import streamlit as st
import tempfile
import pandas as pd
import re

from config import load_ner_model
from database import store_to_mysql, fetch_all_reports, search_reports, get_entity_statistics

# Load NER model
ner_pipeline = load_ner_model()


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def extract_patient_details(text):
    """Extract patient details using simple keyword search."""
    details = {
        "name": "",
        "age": "",
        "gender": ""
    }
    lines = text.split('\n')
    for line in lines:
        if "Name" in line:
            details["name"] = line.split(":")[-1].strip()
        elif "Age" in line:
            # Extract only digits (and possibly years)
            age_match = re.search(r"\d+", line)
            if age_match:
                details["age"] = age_match.group()
            else:
                details["age"] = line.split(":")[-1].strip()[:10]  # fallback, truncate to 10 chars
        elif "Gender" in line:
            details["gender"] = line.split(":")[-1].strip()
    return details


def extract_ner_entities(text):
    """
    Process text through NER pipeline and standardize entity names.
    
    Args:
        text (str): Medical text to process
        
    Returns:
        list: Processed NER entities with standardized field names
    """
    entities = ner_pipeline(text)
    # Rename the fields for better clarity
    for entity in entities:
        entity['label'] = entity.pop('entity_group')
        entity['text'] = entity.pop('word')
    return entities


# Streamlit UI
st.title("Medical Report Analyzer")

menu = st.sidebar.selectbox("Choose an option", ["Upload Report", "View Reports", "Search Reports", "Statistics"])

if menu == "Upload Report":
    uploaded_files = st.file_uploader("Upload one or more PDF files", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_file_path = tmp_file.name

            st.subheader(f"Processing {uploaded_file.name}")
            text = extract_text_from_pdf(tmp_file_path)
            patient_details = extract_patient_details(text)

            st.write("**Extracted Patient Details:**")
            st.json(patient_details)

            st.write("**Performing Named Entity Recognition...**")
            ner_results = extract_ner_entities(text)
            st.write("**Extracted Medical Entities:**")
            for ent in ner_results:
                st.markdown(f"- **{ent['label']}**: {ent['text']}")

            store_to_mysql(patient_details, ner_results, uploaded_file.name)

            os.remove(tmp_file_path)

        st.success("All files processed and stored in the database.")

elif menu == "View Reports":
    reports = fetch_all_reports()
    for patient in reports:
        st.markdown(f"### Patient ID: {patient['id']} | Name: {patient['name']}")
        st.write(f"**Age**: {patient['age']}, **Gender**: {patient['gender']}")
        
        if patient['reports']:
            for report in patient['reports']:
                st.write(f"**Report**: {report['filename']} | **Processed**: {report['processed']}")
                st.write("**Medical Entities:**")
                for entity in report['entities']:
                    st.markdown(f"- **{entity['label']}**: {entity['text']}")
                st.write("---")
        else:
            st.write("No reports found for this patient.")
        st.write("=" * 50)

elif menu == "Search Reports":
    query = st.text_input("Enter patient name, ID, or medical entity")
    if query:
        results = search_reports(query)
        if results:
            for result in results:
                st.markdown(f"### Patient ID: {result['id']} | Name: {result['name']}")
                st.write(f"**Age**: {result['age']}, **Gender**: {result['gender']}")
        else:
            st.warning("No matching reports found.")

elif menu == "Statistics":
    stats = get_entity_statistics()
    st.subheader("Entity Frequency")
    st.bar_chart(pd.DataFrame.from_dict(stats, orient='index', columns=['Count']))
