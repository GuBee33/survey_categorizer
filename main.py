from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
# import shutil
# import tempfile
import os
import uuid
import pandas as pd

app = FastAPI()

ALLOWED_EXTENSIONS = {"xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIRECTORY = "uploaded_files"

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

def cleanup_file(path: str):
    try:
        os.remove(path)
        print(f"Deleted temporary file: {path}")
    except Exception as e:
        print(f"Error deleting file {path}: {e}")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    # Validate file extension
    extension = file.filename.split(".")[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed.")
    
    # Generate a unique filename to prevent collisions
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    
    
    file_path = os.path.join(UPLOAD_DIRECTORY, unique_filename)
    
    try:
        # Save the file with size limit
        size = 0
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024)  # Read in chunks of 1KB
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="File size exceeds limit.")
                buffer.write(chunk)
        
        # Schedule cleanup after use or after a certain condition
        # if background_tasks:
        #     background_tasks.add_task(cleanup_file, file_path)
        df=pd.read_excel(file_path)
        
        return JSONResponse(
            status_code=200,
            content={"filename": unique_filename, "temp_path": file_path, "columns":[f"{index} {element}" for index, element in enumerate(df.columns)]},
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()