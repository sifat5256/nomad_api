import random
from fastapi import FastAPI, UploadFile, File
from PyPDF2 import PdfMerger
import os
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from pydantic import BaseModel


class EmailRequest(BaseModel):
    email: str

class VerificationRequest(BaseModel):
    email: str
    code: str

app = FastAPI()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
verification_codes = {} 

def generate_verification_code():
    return f"{random.randint(100000, 999999)}"

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


@app.post("/send-code/")
async def send_code(data: EmailRequest):
    email = data.email
    code = generate_verification_code()
    verification_codes[email] = code

    message = Mail(
        from_email="no-reply@techapppartners.com",
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
    
@app.post("/verify-code/")
async def verify_code(data: VerificationRequest):
    email = data.email
    code = data.code
    stored_code = verification_codes.get(email)
    if stored_code is None:
        return {"verified": False, "message": "No code sent to this email"}
    if stored_code == code:
        # Optional: remove the code after successful verification
        del verification_codes[email]
        return {"verified": True, "message": "Email verified successfully"}
    else:
        return {"verified": False, "message": "Invalid code"}

    

    