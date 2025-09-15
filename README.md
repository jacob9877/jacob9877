# AI for Bariatric Surgery API

## Environment setup

1. Install any version of Python 3.11 (make sure to add it to PATH during installation).
2. Create a virtual environment (venv) either by running the command `python -m venv .venv` in the `api` directory (make sure it uses Python version 3.11), or by typing `>Python: Create Environment` in the VS code search bar, selecting the command, and selecting `venv` and the correct Python version 3.11.
3. Activate the virtual environment by running the command `.\.venv\Scripts\activate` (for Windows at least) in the `api` directory.
4. Select the proper interpreter (optional but recommended for intellisense) by typing `>Python: Select Interpreter` in the VS code search bar and select the correct Python version 3.11
5. Install the dependencies by running the command `pip install -r requirements.txt` in the `api` directory.
6. Make sure the `.env` file is present in the `api` directory. In its file content, it must include the following environment variables:

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=
SAGEMAKER_ROLE=
S3_MODELS_BUCKET=
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=
GOOGLE_API_KEY=
JWT_SECRET=
JWT_ALGORITHM=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=
MAIL_PORT=
MAIL_SERVER=
FRONTEND_URL=
BREAST_CANCER_EXPLANATION_QUEUE_URL=
ACCESS_TOKEN_TTL_SECONDS=
REFRESH_TOKEN_TTL_SECONDS=6

## Running the API

In the `api` directory, run `fastapi dev app/app.py`.
Once you see `Application startup complete`, good to go! You can send requests to `http://127.0.0.1:8000`.

## Testing the API

Go to `http://127.0.0.1:8000/docs` \
Use `/auth/login` with your credentials to get an access token \
Click the "Authorize" button at the top of the docs and insert this access token \
Now all subsequent requests will use this access token, and go to go!
