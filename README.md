# 👋 Hi, I'm Jacob!

🎓 CS Student @ UCF | Graduated on Dec 2025  
☁️ Backend • Cloud • Machine Learning • FastAPI • AWS  
🔍 Seeking 2025 SWE / Backend / Cloud Internships & Full-time roles

## 🛠 Tech Stack
**Languages:** Python, Java, C++, SQL, JavaScript  
**Backend:** FastAPI, Node.js, REST APIs  
**ML:** TensorFlow, scikit-learn, XGBoost  
**Cloud:** AWS Lambda, AWS SageMaker, API Gateway, Docker  
**Databases:** MySQL, MongoDB  

## 📌 Featured Projects
### 🔹 AI for Medical Outcomes – Backend + Model Deployment
FastAPI backend that integrates AWS SageMaker for complication prediction models.  
Role-based authentication, secure cookies, Dockerized Lambda deployment.

### 🔹 Contacts App – Node.js + MongoDB
REST API for user auth + contact management (CRUD).

### 🔹 FlashCard App – API + Remote DB
JWT auth, card management, DigitalOcean DB integration.

## 📫 Connect with me  
LinkedIn: https://www.linkedin.com/in/jacob-m-26883120b/  
Email: jacobrajan9876@gmail.com
# AI for Medical Outcomes API

## Environment setup

1. Install any version of Python 3.11 (make sure to add it to PATH during installation).
2. Create a virtual environment (venv) either by running the command `python -m venv .venv` in the `api` directory (make sure it uses Python version 3.11), or by typing `>Python: Create Environment` in the VS code search bar, selecting the command, and selecting `venv` and the correct Python version 3.11.
3. Activate the virtual environment by running the command `.\.venv\Scripts\activate` (for Windows at least) in the `api` directory.
4. Select the proper interpreter (optional but recommended for intellisense) by typing `>Python: Select Interpreter` in the VS code search bar and select the correct Python version 3.11
5. Install the dependencies by running the command `pip install -r requirements.txt` in the `api` directory.
6. Make sure the `.env` file is present in the `api` directory. In its file content, it must include the variables outlinted in `.env.example`

## Running the API

In the `api` directory, run `fastapi dev app/app.py`.
Once you see `Application startup complete`, good to go! You can send requests to `http://127.0.0.1:8000`.

## Testing the API

Go to `http://127.0.0.1:8000/docs` \
Use `/auth/login` with your credentials to get an access token \
Click the "Authorize" button at the top of the docs and insert this access token \
Now all subsequent requests will use this access token
