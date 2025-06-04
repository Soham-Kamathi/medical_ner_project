

# 🏥 Medical Report Analyzer

A Streamlit-based web application for extracting, analyzing, and storing medical information from PDF reports using state-of-the-art Named Entity Recognition (NER) models. The app supports uploading medical PDFs, extracting patient details, performing NER on the content, and storing results in a MySQL database for search and statistics.

---

## 📁 Project Structure

```
medical_ner_project/
├── app.py              # Main Streamlit application
├── config.py           # Configuration and model loading
├── database.py         # Database operations
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (create this)
└── README.md          # Project documentation
```

---

## 🚀 Features

- **PDF Upload:** Upload one or more medical PDF reports.
- **Text Extraction:** Extracts text from uploaded PDFs using PyMuPDF.
- **Patient Details Extraction:** Automatically extracts patient name, age, and gender.
- **Named Entity Recognition:** Uses HuggingFace NER models (default: `d4data/biomedical-ner-all`) to identify medical entities.
- **Database Storage:** Stores patient details and extracted entities in a MySQL database.
- **View Reports:** Browse all stored reports and their extracted entities.
- **Search Reports:** Search reports by patient name, ID, or medical entity.
- **Statistics:** Visualize the frequency of extracted medical entities.

---

## 🛠️ Tech Stack

- **Frontend:** [Streamlit](https://streamlit.io/)
- **NER Model:** [HuggingFace Transformers](https://huggingface.co/models?pipeline_tag=token-classification)
- **PDF Parsing:** [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)
- **Database:** [MySQL](https://www.mysql.com/)
- **ORM/Connector:** [mysql-connector-python](https://pypi.org/project/mysql-connector-python/)

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Soham-Kamathi/medical_ner_project.git
cd medical-report-analyzer
```

\
### 2. Install Python dependencies

It’s recommended to use a virtual environment.

```bash
pip install -r requirements.txt
```

**If you don’t have a `requirements.txt`, use:**

```bash
pip install streamlit pymupdf mysql-connector-python transformers pandas
```

### 3. Set up MySQL

- Install MySQL and start the server.
- Create a database named `medical_ner`:

```sql
CREATE DATABASE medical_ner;
```

- Update the MySQL connection parameters in `medical_App.py` if needed (host, user, password).

---

## ⚙️ Configuration

### Change the NER Model

In `config.py`, set the model you want to use:

```python
MODEL_NAME = "d4data/biomedical-ner-all"  # Or any other HuggingFace NER model
```

You can find more models [here](https://huggingface.co/models?pipeline_tag=token-classification).

---

## ▶️ Usage

### Run the application
```bash
streamlit run app.py
```

Open the provided local URL in your browser.

---

## 🖥️ App Workflow

1. **Upload Report:**  
   - Upload one or more PDF files.
   - The app extracts text, patient details, and medical entities.
   - All data is stored in the MySQL database.

2. **View Reports:**  
   - Browse all stored patient reports and their extracted entities.

3. **Search Reports:**  
   - Search by patient name, ID, or medical entity.

4. **Statistics:**  
   - View a bar chart of the frequency of extracted medical entities.

---

## 📝 Example

![App Screenshot](screenshot.png) <!-- Add a screenshot of your app here if available -->

---

## 🧩 File Structure

```
medical_ner_project/
├── app.py              # Main Streamlit application
├── config.py           # Configuration and model loading  
├── database.py         # Database operations
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

---

## ❓ FAQ

**Q: How do I change the NER model?**  
A: Edit the `MODEL_NAME` variable in `config.py`.

**Q: I get a MySQL connection error!**  
A: Make sure your MySQL server is running and the credentials in the script are correct.

**Q: The app says "Data too long for column 'age'"!**  
A: The app now extracts only numeric age values. If you still get this error, check your database schema and the extracted data.

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

[MIT](LICENSE)

---

## 🙏 Acknowledgements

- [HuggingFace Transformers](https://huggingface.co/)
- [Streamlit](https://streamlit.io/)
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- [MySQL](https://www.mysql.com/)

