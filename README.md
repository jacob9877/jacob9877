# AI for Bariatric Surgery API

## Environment setup

1. Install any version of Python 3.11 (make sure to add it to PATH during installation).
2. Create a virtual environment (venv) either by running the command `python -m venv .venv` in the `api` directory, or by typing `>Python: Create Environment` in the VS code search bar, selecting the command, and selecting `venv` and the correct Python version 3.11.
3. Activate the virtual environment by running the command `.\.venv\Scripts\activate` (for Windows at least) in the `api` directory.
4. Select the proper interpreter (optional but recommended for intellisense) by typing `>Python: Select Interpreter` in the VS code search bar and select the correct Python version 3.11
5. Install the dependencies by running the command `pip install -r requirements.txt` in the `api` directory.
6. Make sure the `.env` file is present in the `api` directory. In its file content, it must include the following environment variables:

- No environment variables required for now

## Running the API

In the `api` directory, run `fastapi dev app/app.py`.
Once you see `Application startup complete`, good to go! You can send requests to `http://127.0.0.1:8000`.
