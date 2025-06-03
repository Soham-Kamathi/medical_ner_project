# Required libraries
import os
import fitz  # PyMuPDF
import mysql.connector
import streamlit as st
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
import tempfile
import pandas as pd
from collections import Counter
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === Set your NER model here ===
MODEL_NAME = "d4data/biomedical-ner-all"  # Change this to any HuggingFace NER model

# Load NER model
@st.cache_resource
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
    return pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

ner_pipeline = load_model()

# Extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Extract patient details (simple keyword search for demonstration)
def extract_patient_details(text):
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

# Store data in MySQL
def store_to_mysql(patient, entities):
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'medical_ner')
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            age VARCHAR(50),
            gender VARCHAR(10)
        )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ner_entities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT,
            entity TEXT,
            label TEXT,
            FOREIGN KEY(patient_id) REFERENCES patient_data(id)
        )""")

    cursor.execute("INSERT INTO patient_data (name, age, gender) VALUES (%s, %s, %s)",
                   (patient['name'], patient['age'], patient['gender']))
    patient_id = cursor.lastrowid

    for entity in entities:
        cursor.execute("INSERT INTO ner_entities (patient_id, entity, label) VALUES (%s, %s, %s)",
                       (patient_id, entity['word'], entity['entity_group']))

    conn.commit()
    cursor.close()
    conn.close()

# View reports from database
def fetch_all_reports():
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'medical_ner')
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patient_data")
    patients = cursor.fetchall()

    for patient in patients:
        cursor.execute("SELECT entity, label FROM ner_entities WHERE patient_id = %s", (patient['id'],))
        patient['entities'] = cursor.fetchall()

    cursor.close()
    conn.close()
    return patients

# Search reports
def search_reports(query):
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'medical_ner')
    )
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT DISTINCT pd.* FROM patient_data pd
        LEFT JOIN ner_entities ne ON pd.id = ne.patient_id
        WHERE pd.name LIKE %s OR pd.id = %s OR ne.entity LIKE %s
    """, (f"%{query}%", query if query.isdigit() else -1, f"%{query}%"))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

# Get statistics
def get_entity_statistics():
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'medical_ner')
    )
    cursor = conn.cursor()
    cursor.execute("SELECT label FROM ner_entities")
    labels = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return dict(Counter(labels))

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
            ner_results = ner_pipeline(text)
            st.write("**Extracted Medical Entities:**")
            for ent in ner_results:
                st.markdown(f"- **{ent['entity_group']}**: {ent['word']}")

            store_to_mysql(patient_details, ner_results)

            os.remove(tmp_file_path)

        st.success("All files processed and stored in the database.")

elif menu == "View Reports":
    reports = fetch_all_reports()
    for report in reports:
        st.markdown(f"### Patient ID: {report['id']} | Name: {report['name']}")
        st.write(f"**Age**: {report['age']}, **Gender**: {report['gender']}")
        st.write("**Medical Entities:**")
        for ent in report['entities']:
            st.markdown(f"- **{ent['label']}**: {ent['entity']}")

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
