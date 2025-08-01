import random
import os
import base64

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from pydantic import BaseModel
from PyPDF2 import PdfMerger
import os
import uuid
import base64
from fastapi import UploadFile, File, FastAPI
from fastapi import BackgroundTasks


from fpdf import FPDF
from docx import Document

app = FastAPI()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
verification_codes = {}

# ---------------- Models ---------------- #

class EmailRequest(BaseModel):
    email: str

class VerificationRequest(BaseModel):
    email: str
    code: str

class TextEmailRequest(BaseModel):
    email: str
    subject: str
    message: str

# ---------------- Helpers ---------------- #

def generate_verification_code():
    return f"{random.randint(100000, 999999)}"

# ---------------- Routes ---------------- #

# ✅ 1. Merge PDF files
@app.post("/merge-pdf/")
async def merge_pdf(files: list[UploadFile] = File(...)):
    merger = PdfMerger()
    filenames = []

    for file in files:
        contents = await file.read()
        with open(file.filename, "wb") as f:
            f.write(contents)
        merger.append(file.filename)
        filenames.append(file.filename)

    output_filename = "merged.pdf"
    merger.write(output_filename)
    merger.close()

    for file in filenames:
        os.remove(file)

    return FileResponse(output_filename, media_type='application/pdf', filename="merged.pdf")

# ✅ 2. Send verification code via email
@app.post("/send-code/")
async def send_code(data: EmailRequest):
    email = data.email
    code = generate_verification_code()
    verification_codes[email] = code

    message = Mail(
        from_email=("no-reply@techapppartners.com", "Nomad"),
        to_emails=email,
        subject="Your Verification Code",
        html_content=f"<p>Your verification code is: <strong>{code}</strong></p>"
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code not in range(200, 300):
            raise HTTPException(status_code=500, detail="Failed to send email")
        return {"message": "Verification code sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 3. Verify email code
@app.post("/verify-code/")
async def verify_code(data: VerificationRequest):
    email = data.email
    code = data.code
    stored_code = verification_codes.get(email)

    if stored_code is None:
        return {"verified": False, "message": "No code sent to this email"}
    if stored_code == code:
        del verification_codes[email]
        return {"verified": True, "message": "Email verified successfully"}
    else:
        return {"verified": False, "message": "Invalid code"}

# ✅ 4. Send text email
@app.post("/send-email/")
async def send_email(data: TextEmailRequest):
    message = Mail(
        from_email=("no-reply@techapppartners.com", "Nomad"),
        to_emails=data.email,
        subject=data.subject,
        html_content=f"<p>{data.message}</p>"
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code not in range(200, 300):
            raise HTTPException(status_code=500, detail="Failed to send email")
        return {"message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 5. Send email with file attachments
@app.post("/send-email-with-files/")
async def send_email_with_files(
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    files: list[UploadFile] = File(...)
):
    mail = Mail(
        from_email=("no-reply@techapppartners.com", "Nomad"),
        to_emails=email,
        subject=subject,
        html_content=f"<p>{message}</p>"
    )

    attachments = []
    for file in files:
        file_data = await file.read()
        encoded_file = base64.b64encode(file_data).decode()

        attachment = Attachment()
        attachment.file_content = FileContent(encoded_file)
        attachment.file_type = FileType(file.content_type)
        attachment.file_name = FileName(file.filename)
        attachment.disposition = Disposition("attachment")

        attachments.append(attachment)

    mail.attachment = attachments

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(mail)
        if response.status_code not in range(200, 300):
            raise HTTPException(status_code=500, detail="Failed to send email")
        return {"message": f"Email sent with {len(attachments)} attachment(s)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
def docx_to_pdf(file_path, output_path):
    doc = Document(file_path)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for para in doc.paragraphs:
        pdf.multi_cell(0, 10, para.text)
    pdf.output(output_path)

def txt_to_pdf(file_path, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            pdf.multi_cell(0, 10, line.strip())
    pdf.output(output_path)





@app.post("/merge-any-to-pdf/")
async def merge_any_to_pdf(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    temp_dir = "temp_files"
    os.makedirs(temp_dir, exist_ok=True)
    pdf_paths = []

    for file in files:
        file_ext = file.filename.split(".")[-1].lower()
        unique_name = f"{uuid.uuid4()}.{file_ext}"
        temp_file_path = os.path.join(temp_dir, unique_name)

        contents = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        output_pdf_path = temp_file_path.replace(f".{file_ext}", ".pdf")

        if file_ext == "pdf":
            pdf_paths.append(temp_file_path)
        elif file_ext == "txt":
            txt_to_pdf(temp_file_path, output_pdf_path)
            pdf_paths.append(output_pdf_path)
        elif file_ext == "docx":
            docx_to_pdf(temp_file_path, output_pdf_path)
            pdf_paths.append(output_pdf_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

    # Merge all PDFs
    merger = PdfMerger()
    for path in pdf_paths:
        merger.append(path)

    final_pdf_path = os.path.join(temp_dir, "final_merged.pdf")
    merger.write(final_pdf_path)
    merger.close()

    # Schedule deletion of temp files AFTER sending response
    def cleanup():
        import time
        time.sleep(3)  # wait a bit to ensure file is sent
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass

    background_tasks.add_task(cleanup)

    return FileResponse(path=final_pdf_path, filename="merged.pdf", media_type="application/pdf")

    temp_dir = "temp_files"
    os.makedirs(temp_dir, exist_ok=True)
    pdf_paths = []

    for file in files:
        file_ext = file.filename.split(".")[-1].lower()
        unique_name = f"{uuid.uuid4()}.{file_ext}"
        temp_file_path = os.path.join(temp_dir, unique_name)

        contents = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        output_pdf_path = temp_file_path.replace(f".{file_ext}", ".pdf")

        if file_ext == "pdf":
            pdf_paths.append(temp_file_path)
        elif file_ext == "txt":
            txt_to_pdf(temp_file_path, output_pdf_path)
            pdf_paths.append(output_pdf_path)
        elif file_ext == "docx":
            docx_to_pdf(temp_file_path, output_pdf_path)
            pdf_paths.append(output_pdf_path)
        else:
            return {"error": f"Unsupported file type: {file_ext}"}

    merger = PdfMerger()
    for path in pdf_paths:
        merger.append(path)

    final_pdf_path = os.path.join(temp_dir, "final_merged.pdf")
    merger.write(final_pdf_path)
    merger.close()

    # Schedule cleanup after response is sent
    def cleanup():
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass

    if background_tasks:
        background_tasks.add_task(cleanup)

    return FileResponse(final_pdf_path, filename="merged.pdf", media_type="application/pdf")

    temp_dir = "temp_files"
    os.makedirs(temp_dir, exist_ok=True)
    pdf_paths = []

    try:
        for file in files:
            file_ext = file.filename.split(".")[-1].lower()
            unique_name = f"{uuid.uuid4()}.{file_ext}"
            temp_file_path = os.path.join(temp_dir, unique_name)

            contents = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(contents)

            output_pdf_path = temp_file_path.replace(f".{file_ext}", ".pdf")

            if file_ext == "pdf":
                pdf_paths.append(temp_file_path)
            elif file_ext == "txt":
                txt_to_pdf(temp_file_path, output_pdf_path)
                pdf_paths.append(output_pdf_path)
            elif file_ext == "docx":
                docx_to_pdf(temp_file_path, output_pdf_path)
                pdf_paths.append(output_pdf_path)
            else:
                return {"error": f"Unsupported file type: {file_ext}"}

        merger = PdfMerger()
        for path in pdf_paths:
            merger.append(path)

        final_pdf_path = os.path.join(temp_dir, "final_merged.pdf")
        merger.write(final_pdf_path)
        merger.close()

        return FileResponse(final_pdf_path, filename="merged.pdf", media_type="application/pdf")

    finally:
        # Clean up temp files
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))