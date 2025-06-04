"""
Database operations for Medical NER application.
"""
import mysql.connector
from collections import Counter
from config import DB_CONFIG


def get_db_connection():
    """Create and return database connection."""
    return mysql.connector.connect(**DB_CONFIG)


def create_tables():
    """Create necessary database tables."""
    conn = get_db_connection()
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
    
    conn.commit()
    cursor.close()
    conn.close()


def store_to_mysql(patient, entities, filename):
    """Store patient data, report, and NER entities to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure tables exist
    create_tables()
    
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
    
    # Insert patient data
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


def fetch_all_reports():
    """Fetch all patients with their reports and NER results."""
    conn = get_db_connection()
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


def search_reports(query):
    """Search reports by patient name, ID, or medical entities."""
    conn = get_db_connection()
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


def get_entity_statistics():
    """Get statistics of entity labels."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT label FROM ner_results")
    labels = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return dict(Counter(labels))
