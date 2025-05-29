import redis
import json
import dotenv
import os
from supabase import create_client, Client
# Import pipeline and log setup
from src.main import run_pipeline  
from src.logger import Logger

dotenv.load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
log = Logger.get_logger()
r = redis.from_url(redis_url)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def process_job(job):
    try:
        
        pdf_path = job["filePath"]  # e.g., "pdfs/user-1234-file.pdf"
        column = job.get("column", "one")
        journal = job.get("journal", "elsevier")

        log.info(f"Running pipeline for job_id: {job['job_id']}")

        # --- Step 1: PDF Direct download from Supabase  ---
        file_data = supabase.storage.from_("latexgenie").download(pdf_path)

        # --- Step 2: Save the file locally ---
        with open("LaTeXGenie-Worker/data/input.pdf", "wb") as f:
            f.write(file_data)

        # --- Step 3: Process file ---
        output = run_pipeline('../data/input.pdf', column, journal)

        # --- Step 4: upload zip to bucket ---
        output_path = pdf_path.replace("pdfs/", "output/").replace(".pdf", ".zip")
        with open(output, "rb") as f:
            supabase.storage.from_("zips").upload(output_path, f.read())
        
        return {
            "usage_id": job["usage_id"],
            "owner": job["owner"],
            "job_id": job["job_id"],
            "user_id": job["user_id"],
            "org_id": job["org_id"],
            "is_pdf": job["is_pdf"],
            "input_file": pdf_path,
            "creditsRequired": job["creditsRequired"],
            "status":"COMPLETED",
            "zip": {
                "file_name": output_path
            }
        }

    except Exception as e:
        log.error(f"Failed to process job {job.get('job_id')}: {str(e)}")
        return {
            "usage_id": job["usage_id"],
            "owner": job["owner"],
            "job_id": job["job_id"],
            "user_id": job["user_id"],
            "org_id": job["org_id"],
            "is_pdf": job["is_pdf"],
            "input_file": pdf_path,
            "creditsRequired": job["creditsRequired"],
            "status":"FAILED",
            "zip": {
                "file_name": ""
            },
            "error": str(e)
        }

def main():
    try:
        while True:
            result = r.blpop("fileProcessingQueue", timeout=5)
            if result:
                _, job_raw = result
                job = json.loads(job_raw)
                output = process_job(job)
                count = r.publish("latex_results", json.dumps(output))
                log.info(f"Published {count} messages to 'latex_results' channel.")
            else:
                log.info("No jobs in the queue, waiting...")
    except KeyboardInterrupt:
        log.info("Worker stopped by user.")


