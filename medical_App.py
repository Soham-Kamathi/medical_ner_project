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

# Add this function after the ner_pipeline definition
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

# Store data in MySQL
def store_to_mysql(patient, entities, filename):
    conn = mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'medical_ner')
    )
    cursor = conn.cursor()
    
    # Create patients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            age INT,
            gender ENUM('Male', 'Female', 'Other', 'Unknown') DEFAULT 'Unknown'
        )""")

    # Create reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT,
            filename VARCHAR(255),
            processed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )""")

    # Create ner_results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ner_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            report_id INT,
            text TEXT,
            label VARCHAR(255),
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
        )""")

    # Insert patient data
    # Convert age to integer, handle edge cases
    age_int = None
    if patient['age'].isdigit():
        age_int = int(patient['age'])
    
    # Normalize gender values
    gender_normalized = 'Unknown'
    if patient['gender'].lower() in ['male', 'm']:
        gender_normalized = 'Male'
    elif patient['gender'].lower() in ['female', 'f']:
        gender_normalized = 'Female'
    
    cursor.execute("INSERT INTO patients (name, age, gender) VALUES (%s, %s, %s)",
                   (patient['name'], age_int, gender_normalized))
    patient_id = cursor.lastrowid

    # Insert report data
    cursor.execute("INSERT INTO reports (patient_id, filename, processed) VALUES (%s, %s, %s)",
                   (patient_id, filename, True))
    report_id = cursor.lastrowid

    # Insert NER entities
    for entity in entities:
        cursor.execute("INSERT INTO ner_results (report_id, text, label) VALUES (%s, %s, %s)",
                       (report_id, entity['text'], entity['label']))

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

    # Get all patients with their reports and NER results
    cursor.execute("""
        SELECT p.id, p.name, p.age, p.gender, r.id as report_id, r.filename, r.processed
        FROM patients p
        LEFT JOIN reports r ON p.id = r.patient_id
        ORDER BY p.id, r.id
    """)
    rows = cursor.fetchall()

    # Group by patient and organize data
    patients = {}
    for row in rows:
        patient_id = row['id']
        if patient_id not in patients:
            patients[patient_id] = {
                'id': row['id'],
                'name': row['name'],
                'age': row['age'],
                'gender': row['gender'],
                'reports': []
            }
        
        if row['report_id']:
            # Get NER entities for this report
            cursor.execute("SELECT text, label FROM ner_results WHERE report_id = %s", (row['report_id'],))
            entities = cursor.fetchall()
            
            patients[patient_id]['reports'].append({
                'report_id': row['report_id'],
                'filename': row['filename'],
                'processed': row['processed'],
                'entities': entities
            })

    cursor.close()
    conn.close()
    return list(patients.values())

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
        SELECT DISTINCT p.id, p.name, p.age, p.gender, r.filename
        FROM patients p
        LEFT JOIN reports r ON p.id = r.patient_id
        LEFT JOIN ner_results nr ON r.id = nr.report_id
        WHERE p.name LIKE %s OR p.id = %s OR nr.text LIKE %s OR nr.label LIKE %s
    """, (f"%{query}%", query if query.isdigit() else -1, f"%{query}%", f"%{query}%"))
    results = cursor.fetchall()
    
    # Get entities for each result
    for result in results:
        cursor.execute("""
            SELECT nr.text, nr.label, r.filename
            FROM ner_results nr
            JOIN reports r ON nr.report_id = r.id
            WHERE r.patient_id = %s
        """, (result['id'],))
        result['entities'] = cursor.fetchall()
    
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
    cursor.execute("SELECT label FROM ner_results")
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
