import os

from dotenv import find_dotenv, load_dotenv
from google import genai
from google.genai import types

from app.models.chat_models import Message

load_dotenv(find_dotenv(), override=True)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

BREAST_CANCER_DOCUMENTS = """
TYPES OF BREAST CANCER:
1. DUCTAL CARCINOMA IN SITU (DCIS) - Non-invasive cancer in milk ducts
2. INVASIVE DUCTAL CARCINOMA (IDC) - Most common type, starts in ducts and spreads
3. INVASIVE LOBULAR CARCINOMA (ILC) - Starts in milk-producing glands
4. TRIPLE-NEGATIVE BREAST CANCER - Lacks estrogen, progesterone receptors, and HER2
5. HER2-POSITIVE BREAST CANCER - Has excess HER2 protein

RISK FACTORS:
- Age (risk increases after 50)
- Family history and genetic mutations (BRCA1, BRCA2)
- Dense breast tissue
- Hormone replacement therapy
- Obesity, alcohol consumption, lack of physical activity

SCREENING AND DIAGNOSIS:
- Mammography: Primary screening tool
- Ultrasound: For dense breasts or younger women
- MRI: For high-risk patients
- Biopsy: Definitive diagnosis
- Tumor markers: ER, PR, HER2 status

TREATMENT OPTIONS:
- Surgery: Lumpectomy or mastectomy
- Radiation therapy
- Chemotherapy
- Hormone therapy (for hormone receptor-positive cancers)
- Targeted therapy (e.g., for HER2-positive)

PREDICTION MODEL INFORMATION:
- Uses features: mean_radius, mean_texture, mean_perimeter, mean_area, mean_smoothness
- Predicts diagnosis: 0 (benign) or 1 (malignant)
- Provides SHAP analysis to explain feature importance in predictions

GENERAL INFORMATION:
- Early detection significantly improves outcomes
- Importance of regular screening
- Lifestyle factors for prevention
- Support resources for patients
"""

SYSTEM_PROMPT = f"""
You are a specialized medical AI assistant focused on breast cancer named Barry. You have access to comprehensive information about breast cancer and a prediction model that analyzes tumor features to predict malignancy.

IMPORTANT INSTRUCTIONS:
1. Always prioritize information from the provided knowledge base
2. If the question is answered in the knowledge base, reference that information
3. If the question is not fully covered in the knowledge base, use your general medical knowledge but clearly indicate this
4. Always recommend consulting with healthcare providers for personalized medical advice
5. Be empathetic and supportive when discussing patient concerns
6. Focus specifically on breast cancer topics
7. Keep responses brief. For example, one paragraph or up to 5 bullet points.
8. When provided with prediction model results (in JSON format), explain them in natural language, including the diagnosis (benign (0) / malignant (1)) and the most important features from SHAP analysis that contributed to the prediction

KNOWLEDGE BASE:
{BREAST_CANCER_DOCUMENTS}

Please provide helpful, accurate information about breast cancer while emphasizing the importance of professional medical consultation.
"""


def format_history(history: list[Message]) -> list[types.Content]:
    return [
        types.Content(
            role=message.role, parts=[types.Part.from_text(text=message.content)]
        )
        for message in history
    ]


def get_gemini_response(history: list[Message]) -> str:

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=format_history(history),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, temperature=0.0
        ),
    )

    return response.text


TITLE_SYSTEM_PROMPT = """
You are an expert in creating concise but expressive titles.
You will create titles for a chatbot where users can have multiple conversations.
You will take in the user's first message and create a concise title (40 characters or less) for the conversation.
The title should concisely describe what the conversation is about and what the user is asking.
The casing should be that of a sentence: The first word should be capitalized but everything else (except names) should be lowercase
"""


def get_gemini_title(history: list[Message]) -> str:

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=format_history(history),
        config=types.GenerateContentConfig(
            system_instruction=TITLE_SYSTEM_PROMPT, temperature=0.0
        ),
    )

    return response.text.strip()
