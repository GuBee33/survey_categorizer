from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
import os
import uuid
import pandas as pd
from services import *


app = FastAPI()

ALLOWED_EXTENSIONS = {"xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIRECTORY = "uploaded_files"
REPORT_DIRECOTRY="report_files"

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)


if not os.path.exists(REPORT_DIRECOTRY):
    os.makedirs(REPORT_DIRECOTRY)

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

        df=pd.read_excel(file_path)
        
        return JSONResponse(
            status_code=200,
            content={"filename": unique_filename, "temp_path": file_path, "columns":{index:element for index, element in enumerate(df.columns)}},
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()

@app.get("/files/", response_model=List[str])
def list_files():
    try:
        files = [
            f for f in os.listdir(UPLOAD_DIRECTORY)
            if os.path.isfile(os.path.join(UPLOAD_DIRECTORY, f)) and f.lower().endswith('.xlsx')
        ]
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

class ProcessRequest(BaseModel):
    filename: str = Field(..., description="Name of the uploaded Excel file.")
    column_ids: List[int] = Field(..., description="List of column indices to process.")
    categories_per_column_ids: Dict[int, List[str]] = Field(
        ..., 
        description="Mapping of column indices to their respective categories."
    )
    max_categories_per_answer: int = Field(
        ..., 
        gt=0, 
        description="Maximum number of categories allowed per answer."
    )
    aggregation_column_id: Optional[int] = Field(
        None, 
        description="Optional column index for aggregating results."
    )
    answer_limit: Optional[int] = Field(
        None,
        description="Optional limit on the number of answers."
    )
    model_name: str = Field("gpt-4o", description="Optional, name of the model to be used. Default: gpt-4o")
    report_file_name: str = Field("result.xlsx", description="Name of the generated report file.")
    chunk_size: Optional[int] = Field(
        10,
        description="Optional size of chunks for processing."
    )

    @validator('filename')
    def validate_filename(cls, v):
        if not v.endswith('.xlsx'):
            raise ValueError('Filename must have a .xlsx extension.')
        return v


@app.post("/analize/")
async def process_file(request: ProcessRequest):
    # Validate that the file exists in the upload directory
    file_path = os.path.join(UPLOAD_DIRECTORY, request.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found in the upload directory.")
    
    try:
        # Load the Excel file
        df = pd.read_excel(file_path)
        
        total_columns = len(df.columns)
        
        # Validate column_ids
        for col_id in request.column_ids:
            if col_id < 0 or col_id >= total_columns:
                raise HTTPException(
                    status_code=400, 
                    detail=f"column_id {col_id} is out of range. Excel file has {total_columns} columns."
                )
        
        # Validate categories_per_column_ids keys match column_ids
        if set(request.categories_per_column_ids.keys()) != set(request.column_ids):
            raise HTTPException(
                status_code=400,
                detail="Keys of categories_per_column_ids must exactly match the provided column_ids."
            )
        
        # (Optional) Validate that each category list is non-empty
        for col_id, categories in request.categories_per_column_ids.items():
            if not categories:
                raise HTTPException(
                    status_code=400,
                    detail=f"Category list for column_id {col_id} cannot be empty."
                )
        
        # Set chunk_size
        chunk_size = 10
        if request.chunk_size:
            chunk_size = request.chunk_size
        
        # Define result_excel path
        report_file_name=request.report_file_name if request.report_file_name.endswith('.xlsx') else f"{request.report_file_name}.xlsx"
        result_excel = os.path.join(REPORT_DIRECOTRY, report_file_name)
        
        # Initialize and run SurveyAnalyzer
        surveyanalizer = SurveyAnalyzer(
            file_path=file_path,
            model=request.model_name,
            result_excel=result_excel,
            answer_limit=request.answer_limit,
            chunk_size=chunk_size
        )
        surveyanalizer.run(
            columnIds=request.column_ids,
            categories_per_columnId=request.categories_per_column_ids,
            max_categories_per_answer=request.max_categories_per_answer,
            aggregation_column_id=request.aggregation_column_id
        )
        
        return FileResponse(
            path=result_excel,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=report_file_name,
            background=BackgroundTasks().add_task(cleanup_file, result_excel)
        )
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during processing: {str(e)}")