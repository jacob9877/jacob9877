from fastapi import APIRouter, Path, Query, status

from app.models.common_models import ResponseModel

router = APIRouter(
    prefix="/pediatric-appendicitis-patients",
    tags=["Pediatric Appendicitis Patients"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)


@router.post("/images")
def create_presigned_uploads(
    num_images: int = Query(
        description="Number of images to upload (number of pre-signed URLs to return)"
    ),
):
    # For each image to be uploaded,
    #   create an upload id.
    #   Set the key of the pre-signed S3 upload to be something like /{user_id}/{upload_id}
    #   Generate the pre-signed URL with this key.
    # Return these pre-signed URLs and corresponding upload_ids
    return


@router.post("")
def add_patient():
    # Take in a list of upload_ids plus the patient info.
    # For each upload id, create the corresponding S3 key where the image is located (/{user_id}/{upload_id})
    #   If one of the upload ids is not found or the file type is not right, throw an error.
    # Pass the patient info plus the image S3 keys to the SageMaker endpoint.
    # The SageMaker endpoint will then download these from S3 upon invocation
    # Store the images in a pediatric_appendicitis_images table
    # Create pre-signed GET URLs for the images to be displayed back to the user
    # Return the new patient info and image URLs
    return


@router.get("/{patient_id}")
def get_patient(patient_id=Path()):
    # Get the normal patient info from the DB
    # Get the images for that patient
    # For each image, generate a pre-signed GET URL
    # Return those URLs along with the patient info
    return


@router.get("")
def get_patients():
    # Get the patients for the logged in user
    # Dont worry about the images
    return


"""
Add patients flow:
    1. If no images to be uploaded, proceed to step 3. 
       Otherwise, frontend initiates photo upload of N images with POST /images and receives N pre-signed POST URLs & upload_ids.
    2. Frontend uploads each image to a different URL.
    3. Frontend calls the add patient endpoint with the patient info and the (potential) upload_ids
    4. Frontend receives response with patient info, predictions, and pre-signed GET URLs for the images
"""
